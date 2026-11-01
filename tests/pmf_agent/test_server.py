import json
import threading
import urllib.request


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return json.loads(r.read())


def _post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:  # refusal bodies are JSON too
        return json.loads(e.read())


def _start_server(monkeypatch, tmp_path):
    """Server on an ephemeral port with the Echo agent standing in for live LLM runs."""
    from pmf_agent.server import make_server

    monkeypatch.setenv("PMF_STORE_DIR", str(tmp_path / "store"))
    (tmp_path / "store").mkdir(exist_ok=True)
    (tmp_path / "store" / "approvers.txt").write_text("U123\n")
    server = make_server(port=0, agent_factory="echo", results_dir=tmp_path / "results")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_index_serves_comparison_page(monkeypatch, tmp_path):
    url = next(_start_server(monkeypatch, tmp_path))
    html = urllib.request.urlopen(f"{url}/", timeout=5).read().decode()
    assert "Folded single loop" in html
    assert "<svg" in html
    assert "api/state" in html  # live polling wired


def test_run_executes_and_state_reports_live(monkeypatch, tmp_path):
    url = next(_start_server(monkeypatch, tmp_path))

    job = _post(f"{url}/api/run", {"arch": "folded"})
    assert job["job_id"]
    assert job["status"] in ("running", "done")

    state = _get(f"{url}/api/state")
    while state["job"] and state["job"]["status"] == "running":
        assert len(state["job"]["scenarios"]) == 15  # live progress visible
        state = _get(f"{url}/api/state")

    assert state["job"]["status"] == "done"
    assert state["job"]["summary"]["pass"] == "15/15"
    # verdicts per scenario are in the state
    verdicts = {s["scenario_id"]: s["verdict"] for s in state["job"]["scenarios"]}
    assert set(verdicts.values()) == {"figures_only"}


def test_ab_comparison_and_traces(monkeypatch, tmp_path):
    url = next(_start_server(monkeypatch, tmp_path))
    _post(f"{url}/api/run", {"arch": "folded"})
    state = _get(f"{url}/api/state")
    while state["job"]["status"] == "running":
        state = _get(f"{url}/api/state")
    _post(f"{url}/api/run", {"arch": "hierarchical"})
    state = _get(f"{url}/api/state")
    while state["job"]["status"] == "running":
        state = _get(f"{url}/api/state")

    assert state["flips"] is not None  # A/B computed once both archs ran
    trace = urllib.request.urlopen(
        f"{url}/api/trace?arch=folded&scenario=q01_weekly_spend_wow", timeout=5
    ).read().decode()
    assert "q01_weekly_spend_wow" in trace and "[answer]" in trace.lower() or "prompt:" in trace


def test_proposals_endpoints(monkeypatch, tmp_path):
    url = next(_start_server(monkeypatch, tmp_path))
    # seed a proposal through the store the server uses
    import os

    os.environ["PMF_STORE_DIR"] = str(tmp_path / "store")
    from pmf_agent.tools import propose_campaign_change

    p = propose_campaign_change.invoke(
        {"platform": "meta_ads", "change_type": "update_budget", "details": "x", "rationale": "y"}
    )

    state = _get(f"{url}/api/state")
    assert any(pr["proposal_id"] == p["proposal_id"] for pr in state["proposals"])

    # unauthorized approve -> refused, still pending
    resp = _post(f"{url}/api/proposals", {"action": "approve", "proposal_id": p["proposal_id"], "approver": "U999"})
    assert resp["ok"] is False
    # authorized approve + apply
    resp = _post(f"{url}/api/proposals", {"action": "approve", "proposal_id": p["proposal_id"], "approver": "U123"})
    assert resp["ok"] is True
    resp = _post(f"{url}/api/proposals", {"action": "apply", "proposal_id": p["proposal_id"]})
    assert resp["ok"] is True and resp["result"]["verified"] is True
