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
        # behave like a well-routed agent: call what the scenario expects
        tool_calls = [scenario.expected_tools[0]] if scenario.expected_tools else ["echo"]
        return RunResult(
            text="; ".join(parts),
            tool_calls=tool_calls,
            tokens_in=len(scenario.prompt) // 4,
            tokens_out=50,
            cost_usd=0.0001,
            latency_ms=10,
            trace=[
                {"role": "human", "content": scenario.prompt},
                {"role": "ai", "content": "; ".join(parts), "tool_calls": [
                    {"name": name, "args": {}} for name in tool_calls
                ]},
            ],
        )
