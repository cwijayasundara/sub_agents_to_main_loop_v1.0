"""Run scenarios against an agent and record one JSONL row per scenario.

Agent-agnostic by design: Stage 5's A/B plugs two different agents (folded
single loop vs parent+subagents) into the same suite with zero changes here.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Protocol

from .fixtures import anchor
from .scenarios import Scenario


class RunResult:
    """What an agent run returns, with usage instrumentation."""

    def __init__(
        self,
        text: str,
        tool_calls: list[str],
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float = 0.0,
        latency_ms: int = 0,
    ) -> None:
        self.text = text
        self.tool_calls = list(tool_calls)
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.cost_usd = cost_usd
        self.latency_ms = latency_ms


class AgentUnderTest(Protocol):
    def run(self, scenario: Scenario) -> RunResult: ...


def run_suite(
    agent: AgentUnderTest, scenarios: list[Scenario], out_path: str | Path
) -> list[dict]:
    """Run every scenario, writing one JSONL row each; agent errors become `failed` rows."""
    rows: list[dict] = []
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        for scenario in scenarios:
            row: dict = {
                "scenario_id": scenario.id,
                "entry_point": scenario.entry_point,
                "category": scenario.category,
                "anchor": anchor().isoformat(),
                "timestamp": dt.datetime.now(dt.UTC).isoformat(),
            }
            started = time.perf_counter()
            try:
                result = agent.run(scenario)
                row.update(
                    status="ok",
                    text=result.text,
                    tool_calls=result.tool_calls,
                    tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out,
                    cost_usd=result.cost_usd,
                    latency_ms=result.latency_ms or int((time.perf_counter() - started) * 1000),
                    error=None,
                )
            except Exception as e:  # noqa: BLE001 - a failed run is data, not a crash
                row.update(
                    status="failed",
                    text="",
                    tool_calls=[],
                    tokens_in=0,
                    tokens_out=0,
                    cost_usd=0.0,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    error=f"{type(e).__name__}: {e}",
                )
            fh.write(json.dumps(row) + "\n")
            rows.append(row)
    return rows
