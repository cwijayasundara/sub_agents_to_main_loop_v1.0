"""Live comparison server: watch the two architectures run, in the browser.

    python -m pmf_evals serve            # http://127.0.0.1:8765

One stdlib HTTP server, embedded single-file frontend. What you can do live:

- launch the folded loop or the hierarchical architecture over the 15 golden
  scenarios and watch scenarios complete one by one (progress, verdicts,
  latency, tokens per scenario);
- click any scenario to read its turn-by-turn transcript (every tool call,
  args, and result);
- see the flip report computed live once both architectures have run;
- list/approve/apply proposals through the real permission-checked store.

The runs are the same harness the CLI uses (run_suite + grade_result), so the
numbers here and in results/*.jsonl agree.
"""

from __future__ import annotations

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pmf_evals.grader import grade_result
from pmf_evals.report import compare
from pmf_evals.scenarios import GOLDEN_PATH, load_scenarios
from pmf_evals.fixtures import anchor as fixture_anchor

from pmf_evals.comparison_page import _svg_folded, _svg_hierarchical

_ARCHES = ("folded", "hierarchical", "folded-50")


# --------------------------------------------------------------------- state

class LiveState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.job: dict | None = None
        self.results: dict[str, dict] = {}  # arch -> {"rows": [...], "traces": {id: text}}

    def start_run(self, arch: str, agent, scenarios: list, results_dir: Path | None) -> dict:
        with self.lock:
            if self.job and self.job["status"] == "running":
                raise RuntimeError("a run is already in progress")
            job = {
                "job_id": uuid.uuid4().hex[:8],
                "arch": arch,
                "status": "running",
                "started_at": _now(),
                "scenarios": [
                    {"scenario_id": s.id, "category": s.category, "status": "pending",
                     "verdict": None, "latency_ms": None, "tokens_in": None, "cost_usd": None}
                    for s in scenarios
                ],
                "summary": None,
            }
            self.job = job
        t = threading.Thread(target=self._run, args=(job, agent, scenarios, results_dir), daemon=True)
        t.start()
        return job

    def _run(self, job: dict, agent, scenarios: list, results_dir: Path | None) -> None:
        rows: list[dict] = []
        traces: dict[str, str] = {}
        with self.lock:
            self.results.setdefault(job["arch"], {"rows": [], "traces": {}})  # traces stream in live
        import time as _time

        for entry in job["scenarios"]:
            scenario = next(s for s in scenarios if s.id == entry["scenario_id"])
            entry["status"] = "running"
            started = _time.perf_counter()
            try:
                result = agent.run(scenario)
                from pmf_evals.runner import RunResult  # typing only

                row = {
                    "scenario_id": scenario.id,
                    "entry_point": scenario.entry_point,
                    "category": scenario.category,
                    "anchor": fixture_anchor().isoformat(),
                    "status": "ok",
                    "text": result.text,
                    "tool_calls": result.tool_calls,
                    "tokens_in": result.tokens_in,
                    "tokens_out": result.tokens_out,
                    "cost_usd": result.cost_usd,
                    "latency_ms": result.latency_ms or int((_time.perf_counter() - started) * 1000),
                    "trace": result.trace,
                }
                graded = grade_result(row, scenarios, arch=job["arch"])
                entry.update(status="done", verdict=graded["verdict"],
                             latency_ms=row["latency_ms"], tokens_in=row["tokens_in"],
                             cost_usd=row["cost_usd"])
                rows.append(row)
                traces[scenario.id] = _trace_text(scenario, row)
                with self.lock:  # trace visible the moment the scenario completes
                    self.results[job["arch"]]["traces"][scenario.id] = traces[scenario.id]
            except Exception as e:  # noqa: BLE001 - a failed run is data
                entry.update(status="failed", verdict="error",
                             error=f"{type(e).__name__}: {e}")
                rows.append({"scenario_id": scenario.id, "status": "failed", "text": "",
                             "tool_calls": [], "trace": None, "latency_ms": 0, "cost_usd": 0.0,
                             "tokens_in": 0, "tokens_out": 0})

        done = sum(1 for e in job["scenarios"] if e["status"] == "done" and e["verdict"] in ("pass", "figures_only"))
        total = len(job["scenarios"])
        with self.lock:
            job["status"] = "done"
            job["summary"] = {
                "pass": f"{done}/{total}",
                "latency": f"{sum(r['latency_ms'] for r in rows if r.get('latency_ms')) / max(1, len(rows)) / 1000:.1f}",
                "cost": f"${sum(r['cost_usd'] for r in rows) / max(1, len(rows)):.4f}",
                "tokens": f"{sum(r.get('tokens_in', 0) for r in rows) / max(1, len(rows)) / 1000:.1f}K",
            }
            self.results[job["arch"]] = {"rows": rows, "traces": traces}
        if results_dir:
            _persist(results_dir, job["arch"], rows)


def _trace_text(scenario, row: dict) -> str:
    lines = [
        f"scenario: {scenario.id} ({scenario.category}, {scenario.entry_point})",
        f"prompt:   {scenario.prompt}",
        f"anchor:   {row.get('anchor')}  latency: {row.get('latency_ms')}ms  "
        f"tokens: {row.get('tokens_in')}/{row.get('tokens_out')}  cost: ${row.get('cost_usd', 0):.4f}",
        "=" * 70,
    ]
    trace = row.get("trace")
    if trace:
        for m in trace:
            lines.append(f"[{m.get('role', '?')}]")
            if str(m.get("content", "")).strip():
                lines.append(str(m.get("content")))
            for call in m.get("tool_calls", []) or []:
                lines.append(f"  -> tool: {call.get('name')}({json.dumps(call.get('args', {}), default=str)})")
            lines.append("")
    else:
        for name in row.get("tool_calls", []) or []:
            lines.append(f"[tool] {name}")
        lines.append("[answer]")
        lines.append(row.get("text", ""))
    return "\n".join(lines)


def _persist(results_dir: Path, arch: str, rows: list[dict]) -> None:
    results_dir.mkdir(parents=True, exist_ok=True)
    out = results_dir / f"live-{arch}.jsonl"
    with out.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def _now() -> str:
    import datetime as dt

    return dt.datetime.now(dt.UTC).isoformat()


# ------------------------------------------------------------------ handlers

def make_server(port: int = 8765, agent_factory: str = "live", results_dir: Path | None = None):
    """Build the server. agent_factory: "live" (Fireworks) or "echo" (offline demo)."""
    state = LiveState()
    scenarios = load_scenarios(GOLDEN_PATH)

    def build_agent(arch: str):
        if agent_factory == "echo":
            from pmf_evals.echo_agent import EchoAgent

            return EchoAgent()
        from pmf_agent.adapter import FireworksAgentUnderTest

        kwargs: dict = {"entry_point": "slack", "skills_root": "workspace"}
        if arch == "hierarchical":
            kwargs["arch"] = "hierarchical"
        elif arch == "folded-50":
            kwargs["tools_surface"] = "full50"
        return FireworksAgentUnderTest(**kwargs)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _json(self, obj, code: int = 200):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                body = _page().encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/state":
                self._json(_state_payload())
            elif self.path.startswith("/api/trace"):
                from urllib.parse import parse_qs, urlparse

                qs = parse_qs(urlparse(self.path).query)
                arch, sid = qs.get("arch", ["folded"])[0], qs.get("scenario", [""])[0]
                result = state.results.get(arch)
                text = result["traces"].get(sid) if result else None
                if text is None:
                    self._json({"error": f"no trace for {arch}/{sid} — run it first"}, 404)
                else:
                    body = text.encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/run":
                arch = payload.get("arch", "folded")
                if arch not in _ARCHES:
                    self._json({"error": f"arch must be one of {_ARCHES}"}, 400)
                    return
                try:
                    job = state.start_run(arch, build_agent(arch), scenarios, results_dir)
                    self._json({"job_id": job["job_id"], "status": job["status"], "arch": arch})
                except RuntimeError as e:
                    self._json({"error": str(e)}, 409)
            elif self.path == "/api/proposals":
                try:
                    self._json(_proposals_action(payload))
                except (PermissionError, RuntimeError, KeyError, ValueError) as e:
                    self._json({"ok": False, "error": str(e)}, 400)
            else:
                self._json({"error": "not found"}, 404)

    def _state_payload() -> dict:
        from .tools import get_proposal_store

        with state.lock:
            job = json.loads(json.dumps(state.job)) if state.job else None
            results = {
                arch: {"summary": data.get("summary") and json.loads(json.dumps(data["summary"]))}
                for arch, data in state.results.items()
            }
        flips = None
        if "folded" in state.results and "hierarchical" in state.results:
            def graded(arch):
                out = []
                for r in state.results[arch]["rows"]:
                    g = grade_result(
                        r, scenarios,
                        arch="hierarchical" if arch == "hierarchical" else "folded",
                    )
                    g["latency_ms"] = r.get("latency_ms", 0)
                    g["cost_usd"] = r.get("cost_usd", 0.0)
                    out.append(g)
                return out

            flips = compare(graded("folded"), graded("hierarchical"))["flipped"]
        import os

        proposals = []
        try:
            proposals = get_proposal_store().list()
        except Exception:
            pass
        return {
            "job": job,
            "results": results,
            "flips": flips,
            "proposals": proposals,
            "meta": {
                "anchor": fixture_anchor().isoformat(),
                "model": "accounts/fireworks/models/glm-5p3-flash",
                "fireworks_key": bool(os.environ.get("FIREWORKS_API_KEY")),
                "agent_factory": agent_factory,
            },
        }

    def _proposals_action(payload: dict) -> dict:
        from .tools import get_proposal_store

        store = get_proposal_store()
        action = payload.get("action")
        pid = payload.get("proposal_id")
        if action == "approve":
            p = store.approve(pid, approver_id=payload.get("approver", ""))
            return {"ok": True, "result": p}
        if action == "apply":
            return {"ok": True, "result": store.apply(pid)}
        return {"ok": False, "error": f"unknown action {action!r}"}

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server


# ------------------------------------------------------------------- frontend

def _page() -> str:
    """The live frontend: diagrams, run buttons, polling state, trace viewer."""
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>pmf_agent live — folded loop vs subagents</title>
<style>
  body { font-family: -apple-system, 'Segoe UI', sans-serif; background: #faf9f7; color: #1a1a1a; margin: 0; padding: 32px; }
  h1 { font-size: 24px; font-weight: 600; margin: 0 0 4px; }
  .sub { color: #6b6b6b; font-size: 13.5px; margin-bottom: 24px; }
  .controls { background:#fff; border:1px solid #e8e5e0; border-radius: 12px; padding: 18px; margin-bottom: 24px;
              display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
  button { border: 1px solid #d97757; background: #fdf0ea; color: #b45309; font-weight: 600;
           padding: 9px 18px; border-radius: 8px; cursor: pointer; font-size: 13.5px; }
  button:disabled { opacity: .45; cursor: default; }
  button.dark { border-color:#1a1a1a; background:#1a1a1a; color:#fff; }
  .meta { margin-left:auto; font-size: 12px; color:#6b6b6b; }
  .bar { height: 8px; background: #eee; border-radius: 4px; overflow: hidden; flex: 1 1 200px; }
  .bar > div { height: 100%; background: #d97757; width: 0; transition: width .4s; }
  .row { display: flex; gap: 24px; flex-wrap: wrap; }
  .panel { background: #fff; border: 1px solid #e8e5e0; border-radius: 12px; padding: 20px; flex: 1 1 480px; }
  .panel h2 { font-size: 16px; margin: 0 0 8px; }
  .metrics { display:flex; gap:10px; flex-wrap:wrap; margin-top: 10px; }
  .metric { background:#faf9f7; border:1px solid #e8e5e0; border-radius:8px; padding:7px 12px; font-size:12px; color:#6b6b6b; }
  .metric b { display:block; font-size:16px; color:#1a1a1a; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; color: #6b6b6b; font-weight: 500; padding: 6px 8px; border-bottom: 1px solid #e8e5e0; }
  td { padding: 7px 8px; border-bottom: 1px solid #f0ede8; cursor: pointer; }
  tr:hover td { background: #faf9f7; }
  .pill { font-size: 11px; padding: 2px 8px; border-radius: 10px; }
  .pending { background:#eee; color:#666; } .running { background:#dbeafe; color:#1d4ed8; }
  .pass, .figures_only { background:#dcfce7; color:#15803d; } .fail { background:#fee2e2; color:#b91c1c; }
  .error { background:#fef3c7; color:#b45309; }
  .viewer { background: #1a1a1a; color: #d4d4d4; border-radius: 12px; padding: 18px;
            font-family: ui-monospace, monospace; font-size: 12px; white-space: pre-wrap;
            max-height: 420px; overflow: auto; display: none; }
  .flip { font-family: ui-monospace, monospace; font-size: 12px; color:#b45309; background:#fef3c7;
          border-radius: 6px; padding: 2px 8px; display:inline-block; margin:2px; }
  .muted { color:#6b6b6b; font-size: 13px; }
  input { padding: 8px; border: 1px solid #d7d3cc; border-radius: 8px; font-size: 13px; width: 90px; }
  .small-btn { padding: 4px 10px; font-size: 12px; margin: 0 2px; }
</style></head>
<body>
<h1>pmf_agent live — folded loop vs parent+subagents</h1>
<div class="sub">Same model (<code id="meta-model"></code>), same 15 golden scenarios — launch either harness and watch it run. <span id="meta-anchor"></span></div>

<div class="controls">
  <button id="btn-folded" onclick="runArch('folded')">Run folded loop</button>
  <button id="btn-hier" onclick="runArch('hierarchical')">Run hierarchical</button>
  <button id="btn-50" class="dark" onclick="runArch('folded-50')">Run 50-tool loop</button>
  <div class="bar"><div id="progress"></div></div>
  <span id="progress-label" class="muted">idle</span>
  <span class="meta" id="meta-right"></span>
</div>

<div class="row">
  <div class="panel">
    <h2>Scenarios</h2>
    <table><thead><tr><th>scenario</th><th>category</th><th>status</th><th>verdict</th><th>latency</th><th>tok in</th></tr></thead>
    <tbody id="scenarios"><tr><td colspan="6" class="muted">launch a run to see scenarios execute</td></tr></tbody></table>
    <div id="flip-report" style="margin-top:10px"></div>
  </div>
  <div class="panel">
    <h2>Run summary</h2>
    <div id="summaries" class="metrics"><span class="muted">no runs yet</span></div>
    <h2 style="margin-top:18px">Transcript</h2>
    <div class="muted" style="font-size:12px">click a scenario row to see its full trace (tool calls, args, results)</div>
    <div class="viewer" id="trace"></div>
    <h2 style="margin-top:18px">Proposals <span class="muted" style="font-size:12px">(approval is fail-closed)</span></h2>
    <div style="margin-bottom:8px">approver id: <input id="approver" value="U123"> <span class="muted" style="font-size:12px">allowlist: workspace/approvers.txt / PMF_APPROVERS</span></div>
    <table><tbody id="proposals"><tr><td class="muted">no pending proposals</td></tr></tbody></table>
  </div>
</div>

<div class="row" style="margin-top:24px">
  <div class="panel">__SVG_FOLDED__<h2 style="margin-top:8px">Folded single loop</h2></div>
  <div class="panel">__SVG_HIER__<h2 style="margin-top:8px">Parent + per-platform subagents</h2></div>
</div>

<script>
let timer = null;
async function state() {
  const s = await (await fetch('/api/state')).json();
  render(s);
  if (s.job && s.job.status === 'running') { if (!timer) timer = setInterval(state, 1000); }
  else { if (timer) { clearInterval(timer); timer = null; if (s.job) state(); } }
  return s;
}
async function runArch(arch) {
  ['btn-folded','btn-hier','btn-50'].forEach(id => document.getElementById(id).disabled = true);
  await fetch('/api/run', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({arch})});
  timer = setInterval(state, 1000); state();
}
async function showTrace(arch, sid) {
  const el = document.getElementById('trace');
  el.style.display = 'block';
  el.textContent = 'loading…';
  const r = await fetch(`/api/trace?arch=${arch}&scenario=${sid}`);
  el.textContent = await r.text();
}
async function proposalAction(action, proposal_id) {
  const approver = document.getElementById('approver').value;
  const r = await fetch('/api/proposals', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({action, proposal_id, approver})});
  const j = await r.json();
  if (!j.ok) alert('refused: ' + j.error);
  state();
}
function esc(s){ const d = document.createElement('div'); d.textContent = s ?? ''; return d.innerHTML; }
function render(s) {
  document.getElementById('meta-model').textContent = s.meta.model;
  document.getElementById('meta-anchor').textContent = 'fixture anchor ' + s.meta.anchor;
  document.getElementById('meta-right').textContent =
    (s.meta.fireworks_key ? 'FIREWORKS_API_KEY ✓' : 'no FIREWORKS_API_KEY — runs will fail') +
    ' · factory: ' + s.meta.agent_factory;
  const running = s.job && s.job.status === 'running';
  ['btn-folded','btn-hier','btn-50'].forEach(id => document.getElementById(id).disabled = running);
  const done = s.job ? s.job.scenarios.filter(x => x.status === 'done' || x.status === 'failed').length : 0;
  document.getElementById('progress').style.width = (s.job ? done / s.job.scenarios.length * 100 : 0) + '%';
  document.getElementById('progress-label').textContent =
    !s.job ? 'idle' : s.job.status === 'running' ? `running ${s.job.arch}: ${done}/${s.job.scenarios.length}` : `last run: ${s.job.arch} — ${s.job.summary?.pass || ''}`;
  const tb = document.getElementById('scenarios');
  if (s.job) {
    tb.innerHTML = s.job.scenarios.map(x => `<tr onclick="showTrace('${s.job.arch}','${x.scenario_id}')">
      <td>${esc(x.scenario_id)}</td><td>${esc(x.category)}</td>
      <td><span class="pill ${x.status}">${x.status}</span></td>
      <td><span class="pill ${x.verdict || ''}">${x.verdict || '—'}</span></td>
      <td>${x.latency_ms ? (x.latency_ms/1000).toFixed(1)+'s' : '—'}</td>
      <td>${x.tokens_in ?? '—'}</td></tr>`).join('');
  }
  const sm = document.getElementById('summaries');
  const entries = Object.entries(s.results).filter(([,v]) => v.summary);
  sm.innerHTML = entries.length
    ? entries.map(([arch, v]) => `<div class="metric"><b>${esc(v.summary.pass)}</b>${esc(arch)} · ${esc(v.summary.latency)}s · ${esc(v.summary.tokens)} in · ${esc(v.summary.cost)}</div>`).join('')
    : '<span class="muted">no runs yet</span>';
  document.getElementById('flip-report').innerHTML = s.flips
    ? '<span class="muted">flips (folded → hierarchical):</span><br>' + Object.entries(s.flips).map(([k,v]) => `<span class="flip">${esc(k)}: ${esc(v)}</span>`).join(' ')
    : (Object.keys(s.results).length >= 2 ? '<span class="muted">flips: none — identical verdicts</span>' : '');
  const pb = document.getElementById('proposals');
  pb.innerHTML = s.proposals.length ? s.proposals.map(p => `<tr>
      <td>${esc(p.proposal_id)}</td><td>${esc(p.status)}</td><td>${esc(p.platform)} ${esc(p.change_type)}</td>
      <td style="text-align:right">
        ${p.status === 'pending' ? `<button class="small-btn" onclick="proposalAction('approve','${p.proposal_id}')">approve</button>` : ''}
        ${p.status === 'approved' ? `<button class="small-btn" onclick="proposalAction('apply','${p.proposal_id}')">apply</button>` : ''}
        ${p.status === 'applied' ? '<span class="muted">verified ✓</span>' : ''}</td></tr>`).join('')
    : '<tr><td class="muted">no pending proposals</td></tr>';
}
state();
</script>
</body></html>""".replace("__SVG_FOLDED__", _svg_folded()).replace("__SVG_HIER__", _svg_hierarchical())


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="pmf_evals serve")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--offline", action="store_true",
                        help="EchoAgent instead of live LLM runs (demo the UI without keys)")
    parser.add_argument("--open", action="store_true", help="open the browser on start")
    args = parser.parse_args(argv)

    server = make_server(port=args.port, agent_factory="echo" if args.offline else "live",
                         results_dir=Path("results"))
    url = f"http://127.0.0.1:{args.port}"
    print(f"live comparison server on {url}  (factory: {'echo' if args.offline else 'live fireworks'})")
    if args.open:
        import webbrowser

        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
