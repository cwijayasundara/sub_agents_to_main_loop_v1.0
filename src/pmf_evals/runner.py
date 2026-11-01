"""Run scenarios against an agent and record one JSONL row per scenario.

Agent-agnostic by design: Stage 5's A/B plugs two different agents (folded
single loop vs parent+subagents) into the same suite with zero changes here.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Protocol, runtime_checkable

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
        selections: list[dict] | None = None,
        trace: list[dict] | None = None,
    ) -> None:
        self.text = text
        self.tool_calls = list(tool_calls)
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.cost_usd = cost_usd
        self.latency_ms = latency_ms
        self.selections = selections
        self.trace = trace


@runtime_checkable
class AgentUnderTest(Protocol):
    def run(self, scenario: Scenario) -> RunResult: ...


def _write_trace(
    path: Path, scenario: Scenario, row: dict, trace: list[dict] | None = None
) -> None:
    """Human-readable transcript: per-message blocks when available, else a summary."""
    lines = [
        f"scenario: {scenario.id} ({scenario.category}, {scenario.entry_point})",
        f"prompt:   {scenario.prompt}",
        f"anchor:   {row.get('anchor')}  latency: {row.get('latency_ms')}ms  "
        f"tokens: {row.get('tokens_in')}/{row.get('tokens_out')}  cost: ${row.get('cost_usd', 0):.4f}",
        "=" * 70,
    ]
    if trace:
        for m in trace:
            lines.append(f"[{m.get('role', '?')}]")
            content = str(m.get("content", ""))
            if content.strip():
                lines.append(content)
            for call in m.get("tool_calls", []) or []:
                lines.append(f"  -> tool: {call.get('name')}({json.dumps(call.get('args', {}), default=str)})")
            lines.append("")
    else:
        # agent-level summary only (agent did not surface message-level detail)
        for name in row.get("tool_calls", []) or []:
            lines.append(f"[tool] {name}")
        lines.append("[answer]")
        lines.append(row.get("text", ""))
    path.write_text("\n".join(lines))


def run_suite(
    agent: AgentUnderTest, scenarios: list[Scenario], out_path: str | Path,
    trace_dir: str | Path | None = None,
) -> list[dict]:
    """Run every scenario, writing one JSONL row each; agent errors become `failed` rows.

    trace_dir: when set (and the agent supplies RunResult.trace), one
    human-readable transcript per scenario is written there.
    """
    rows: list[dict] = []
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    trace_root = Path(trace_dir) if trace_dir else None
    if trace_root:
        trace_root.mkdir(parents=True, exist_ok=True)
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
                    selections=result.selections,
                    trace=result.trace,
                    error=None,
                )
                if trace_root:
                    _write_trace(
                        trace_root / f"{scenario.id}.log", scenario, row,
                        trace=result.trace,
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
                    selections=None,
                    trace=None,
                    error=f"{type(e).__name__}: {e}",
                )
            fh.write(json.dumps(row) + "\n")
            rows.append(row)
    return rows
