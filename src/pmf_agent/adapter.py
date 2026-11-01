"""Bridge from the deepagents graph to the Stage 0 eval harness.

`FireworksAgentUnderTest` implements the harness's `AgentUnderTest` protocol so
the folded single loop runs in the same suite as any other candidate
architecture (Stage 5's parent+subagents variant plugs in identically).

With `routed=True`, a decision_harness ToolSelectionMiddleware filters the tool
surface per intent and the per-turn selections are surfaced on the RunResult
for routing-accuracy measurement.
"""

from __future__ import annotations

import time

from pmf_evals.runner import RunResult
from pmf_evals.scenarios import Scenario

from .agent import ENTRY_POINTS, create_agent
from .fw import estimate_cost_usd


def _full50_if_requested(surface: str):
    if surface == "full50":
        from .catalog50 import build_catalog_50

        return build_catalog_50()
    return None


def extract_text(messages: list) -> str:
    """Text of the last AI message."""
    for m in reversed(messages):
        if m.type == "ai" and isinstance(m.content, str) and m.content.strip():
            return m.content
    return ""


def extract_tool_calls(messages: list) -> list[str]:
    """Tool names invoked across all turns, deduped preserving first-seen order."""
    seen: dict[str, None] = {}
    for m in messages:
        if m.type == "ai":
            for call in m.tool_calls or []:
                seen.setdefault(call["name"], None)
    return list(seen)


def extract_usage(messages: list) -> dict[str, int]:
    """Sum token usage across every model turn (not just the last)."""
    usage = {"input_tokens": 0, "output_tokens": 0}
    for m in messages:
        if m.type == "ai" and m.usage_metadata:
            usage["input_tokens"] += m.usage_metadata.get("input_tokens", 0)
            usage["output_tokens"] += m.usage_metadata.get("output_tokens", 0)
    return usage


def serialize_messages(messages: list) -> list[dict]:
    """Message list -> JSON-safe dicts for trace logs."""
    out = []
    for m in messages:
        entry: dict = {"role": m.type, "content": m.content if isinstance(m.content, str) else str(m.content)}
        if m.type == "ai" and m.tool_calls:
            entry["tool_calls"] = [
                {"name": c["name"], "args": c.get("args", {})} for c in m.tool_calls
            ]
        if m.type == "tool":
            entry["tool_call_id"] = getattr(m, "tool_call_id", None)
        out.append(entry)
    return out


class FireworksAgentUnderTest:
    """AgentUnderTest implementation.

    arch: "folded" (single loop, default) or "hierarchical"
    (parent + per-platform subagents, the PMA's production choice).
    """

    def __init__(
        self,
        entry_point: str = "slack",
        model=None,
        routed: bool = False,
        skills_root: str | None = None,
        arch: str = "folded",
        tools_surface: str = "core",
        llm_selector: bool = False,
    ) -> None:
        if entry_point not in ENTRY_POINTS:
            raise ValueError(f"entry_point must be one of {ENTRY_POINTS}, got {entry_point!r}")
        if arch not in ("folded", "hierarchical"):
            raise ValueError(f"arch must be 'folded' or 'hierarchical', got {arch!r}")
        self.entry_point = entry_point
        self._model = model
        self.routed = routed
        self._skills_root = skills_root
        self.arch = arch
        self.tools_surface = tools_surface
        self.llm_selector = llm_selector
        self._middleware = None
        self._graph = None

    def _build(self):
        tools_override = _full50_if_requested(self.tools_surface)
        if self.llm_selector:
            from langchain.agents.middleware import LLMToolSelectorMiddleware

            self._middleware = LLMToolSelectorMiddleware(
                always_include=["propose_campaign_change"], max_tools=12
            )
            return create_agent(
                self.entry_point,
                model=self._model,
                middleware=[self._middleware],
                skills_root=self._skills_root,
                tools_override=tools_override,
            )
        if self.arch == "hierarchical":
            from .subagent_arch import create_hierarchical_agent

            return create_hierarchical_agent(
                self.entry_point, model=self._model, skills_root=self._skills_root
            )
        if self.routed:
            from .routing import tool_selection_middleware

            self._middleware = tool_selection_middleware()
            return create_agent(
                self.entry_point,
                model=self._model,
                middleware=[self._middleware],
                skills_root=self._skills_root,
                tools_override=tools_override,
            )
        return create_agent(
            self.entry_point,
            model=self._model,
            skills_root=self._skills_root,
            tools_override=tools_override,
        )

    @property
    def graph(self):
        if self._graph is None:
            self._graph = self._build()
        return self._graph

    def _selections(self) -> list[dict] | None:
        if not self.routed or self._middleware is None:
            return None
        return [
            {"task": task, "selected": list(sel.selected), "events": list(sel.events)}
            for task, sel in self._middleware.selector.events
        ]

    def run(self, scenario: Scenario) -> RunResult:
        started = time.perf_counter()
        result = self.graph.invoke(
            {"messages": [{"role": "user", "content": scenario.prompt}]},
            config={"configurable": {"thread_id": f"eval-{scenario.id}"}},
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        messages = result["messages"]
        usage = extract_usage(messages)
        return RunResult(
            text=extract_text(messages),
            tool_calls=extract_tool_calls(messages),
            tokens_in=usage["input_tokens"],
            tokens_out=usage["output_tokens"],
            cost_usd=estimate_cost_usd(usage["input_tokens"], usage["output_tokens"]),
            latency_ms=latency_ms,
            selections=self._selections(),
            trace=serialize_messages(messages),
        )
