"""EchoAgent: a trivial agent that quotes the fixture ground truth.

It exists to prove the eval pipeline end to end — if the runner, grader, and
report are wired correctly, EchoAgent passes every deterministic figure check.
"""

from __future__ import annotations

from .fixtures import load_dataset, shipped_offset, shift_dataset
from .runner import RunResult
from .scenarios import Scenario


class EchoAgent:
    def run(self, scenario: Scenario) -> RunResult:
        shifted = shift_dataset(load_dataset(), shipped_offset())
        parts = [f"[echo] {scenario.entry_point}/{scenario.category}"]
        for spec in scenario.figure_specs:
            value = spec.expected_value()
            metric = spec.metric
            parts.append(f"{spec.platform} {spec.window} {metric} = {value:,.2f}")
        # keep a date in the text on purpose: graders must never match it
        parts.append(f"as of {shifted['google_ads'][-1]['date']}")
        return RunResult(
            text="; ".join(parts),
            tool_calls=["echo"],
            tokens_in=len(scenario.prompt) // 4,
            tokens_out=50,
            cost_usd=0.0001,
            latency_ms=10,
        )
