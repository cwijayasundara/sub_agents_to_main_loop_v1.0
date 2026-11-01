import json
import subprocess
import sys

from pmf_evals.echo_agent import EchoAgent
from pmf_evals.grader import grade_result
from pmf_evals.runner import run_suite
from pmf_evals.scenarios import GOLDEN_PATH, load_scenarios


def test_echo_agent_end_to_end_all_figures_found(tmp_path):
    scenarios = load_scenarios(GOLDEN_PATH)
    out = tmp_path / "results.jsonl"
    rows = run_suite(EchoAgent(), scenarios, out)
    assert len(rows) == 15
    graded = [grade_result(r, scenarios) for r in rows]
    with_figures = [g for g in graded if g["figures"]]
    assert len(with_figures) >= 10  # most scenarios have deterministic figures
    assert all(
        f["found"] for g in with_figures for f in g["figures"]
    ), "EchoAgent quotes ground truth, so every figure check must pass"
    assert all(g["verdict"] != "error" for g in graded)


def test_cli_run_and_compare(tmp_path):
    results = tmp_path / "results.jsonl"
    r1 = subprocess.run(
        [sys.executable, "-m", "pmf_evals", "run", "--agent", "echo", "--out", str(results)],
        capture_output=True, text=True,
    )
    assert r1.returncode == 0, r1.stderr
    assert len(results.read_text().splitlines()) == 15

    graded_out = tmp_path / "graded.json"
    r2 = subprocess.run(
        [sys.executable, "-m", "pmf_evals", "grade", "--results", str(results), "--out", str(graded_out)],
        capture_output=True, text=True,
    )
    assert r2.returncode == 0, r2.stderr
    graded = json.loads(graded_out.read_text())
    assert len(graded["reports"]) == 15

    r3 = subprocess.run(
        [sys.executable, "-m", "pmf_evals", "compare", str(results), str(results)],
        capture_output=True, text=True,
    )
    assert r3.returncode == 0, r3.stderr
    assert json.loads(r3.stdout)["flipped"] == {}


def test_fireworks_agent_registered_lazily():
    """--agent fireworks resolves; pmf_agent is imported only when selected."""
    import subprocess
    import sys

    from pmf_evals.__main__ import _AGENTS

    assert "fireworks" in _AGENTS
    # laziness must hold in a fresh interpreter that only imports the CLI module
    out = subprocess.run(
        [sys.executable, "-c", "import pmf_evals.__main__, sys; print('pmf_agent' in sys.modules)"],
        capture_output=True, text=True, check=True,
    )
    assert out.stdout.strip() == "False"


def test_fireworks_routed_registered_lazily():
    from pmf_evals.__main__ import _AGENTS

    assert "fireworks-routed" in _AGENTS


def test_fireworks_skills_registered_lazily():
    from pmf_evals.__main__ import _AGENTS

    assert "fireworks-skills" in _AGENTS


def test_fireworks_hierarchical_registered_lazily():
    from pmf_evals.__main__ import _AGENTS

    assert "fireworks-hierarchical" in _AGENTS


def test_50_tool_agents_registered():
    from pmf_evals.__main__ import _AGENTS

    assert "fireworks-50" in _AGENTS
    assert "fireworks-50-routed" in _AGENTS


def test_grade_accepts_arch_flag(tmp_path):
    """grade --arch hierarchical counts task-delegation as correct routing."""
    import json as _json

    from pmf_evals.grader import grade_result  # noqa: F401

    results = tmp_path / "results.jsonl"
    r1 = subprocess.run(
        [sys.executable, "-m", "pmf_evals", "run", "--agent", "echo", "--out", str(results)],
        capture_output=True, text=True,
    )
    assert r1.returncode == 0
    graded = tmp_path / "graded.json"
    r2 = subprocess.run(
        [sys.executable, "-m", "pmf_evals", "grade", "--results", str(results),
         "--out", str(graded), "--arch", "hierarchical"],
        capture_output=True, text=True,
    )
    assert r2.returncode == 0, r2.stderr
    assert _json.loads(graded.read_text())["arch"] == "hierarchical"


def test_run_writes_trace_logs(tmp_path):
    """run --trace-dir writes one human-readable log per scenario."""
    traces = tmp_path / "traces"
    r = subprocess.run(
        [sys.executable, "-m", "pmf_evals", "run", "--agent", "echo",
         "--out", str(tmp_path / "results.jsonl"), "--trace-dir", str(traces)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    logs = list(traces.glob("*.log"))
    assert len(logs) == 15
    content = logs[0].read_text()
    assert "tool" in content.lower() or "answer" in content.lower()
