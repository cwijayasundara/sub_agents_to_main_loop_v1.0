import json

import pytest

from pmf_evals.runner import AgentUnderTest, RunResult, run_suite
from pmf_evals.scenarios import FigureSpec, Scenario


def _scenario(i: int = 1) -> Scenario:
    return Scenario(
        id=f"q{i:02d}_x",
        entry_point="slack",
        category="q_and_a",
        prompt="p",
        rubric=["r"],
        figure_specs=(FigureSpec(platform="google_ads", window="last_week", metric="spend"),),
    )


class EchoAgent:
    """Minimal AgentUnderTest used by tests."""

    def run(self, scenario: Scenario) -> RunResult:
        return RunResult(
            text=f"answer to {scenario.id}",
            tool_calls=["get_spend"],
            tokens_in=100,
            tokens_out=20,
            cost_usd=0.001,
            latency_ms=250,
        )


class FlakyAgent:
    """Fails on q02 to prove the suite continues and records the failure."""

    def run(self, scenario: Scenario) -> RunResult:
        if scenario.id.startswith("q02"):
            raise RuntimeError("boom")
        return RunResult(text="ok", tool_calls=[], tokens_in=1, tokens_out=1,
                         cost_usd=0.0, latency_ms=5)


def test_protocol_satisfied():
    assert isinstance(EchoAgent(), AgentUnderTest)


def test_suite_writes_one_jsonl_row_per_scenario(tmp_path):
    out = tmp_path / "results.jsonl"
    scenarios = [_scenario(1), _scenario(2)]
    run_suite(EchoAgent(), scenarios, out)
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert [r["scenario_id"] for r in rows] == ["q01_x", "q02_x"]
    row = rows[0]
    assert row["status"] == "ok"
    assert row["text"] == "answer to q01_x"
    assert row["tool_calls"] == ["get_spend"]
    assert row["tokens_in"] == 100 and row["cost_usd"] == 0.001
    assert "anchor" in row and "timestamp" in row


def test_suite_survives_agent_failure(tmp_path):
    out = tmp_path / "results.jsonl"
    scenarios = [_scenario(1), _scenario(2), _scenario(3)]
    run_suite(FlakyAgent(), scenarios, out)
    rows = [json.loads(l) for l in out.read_text().splitlines()]
    assert len(rows) == 3
    failed = [r for r in rows if r["status"] == "failed"]
    assert len(failed) == 1
    assert failed[0]["scenario_id"] == "q02_x"
    assert "boom" in failed[0]["error"]
