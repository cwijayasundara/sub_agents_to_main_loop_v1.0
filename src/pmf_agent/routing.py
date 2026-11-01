"""Intent routing for the single loop, via decision_harness ToolSelectionMiddleware.

The RecordingToolSelector wraps the Decisions-backed ToolSelector and captures
every selection (or degradation) so the eval harness can measure routing
accuracy — the metric that replaces subagent-routing accuracy after a fold.
"""

from __future__ import annotations

from decision_harness.decisions import DecisionsClient
from decision_harness.errors import SelectorUnavailable
from decision_harness.middleware.tool_selection import ToolSelectionMiddleware
from decision_harness.tools import ToolSelector
from decision_harness.types import ToolSelection

ALWAYS_INCLUDE = ["list_platforms"]  # discovery is never hidden from the model


class RecordingToolSelector:
    """Same select/aselect surface as ToolSelector, plus an event log."""

    def __init__(self, client: DecisionsClient | None = None) -> None:
        self._inner = ToolSelector(client=client)
        self.events: list[tuple[str, ToolSelection]] = []

    def select(self, task, tools, **kwargs) -> ToolSelection:
        try:
            selection = self._inner.select(task, tools, **kwargs)
        except SelectorUnavailable:
            self.events.append((task, ToolSelection(selected=[], probabilities={}, events=["unavailable -> keep all tools"], latency_ms=0)))
            raise
        self.events.append((task, selection))
        return selection

    async def aselect(self, task, tools, **kwargs) -> ToolSelection:
        try:
            selection = await self._inner.aselect(task, tools, **kwargs)
        except SelectorUnavailable:
            self.events.append((task, ToolSelection(selected=[], probabilities={}, events=["unavailable -> keep all tools"], latency_ms=0)))
            raise
        self.events.append((task, selection))
        return selection


def tool_selection_middleware(client: DecisionsClient | None = None) -> ToolSelectionMiddleware:
    """Middleware that filters the tool surface per intent, with conservative fallbacks."""
    return ToolSelectionMiddleware(
        selector=RecordingToolSelector(client=client),
        always_include=ALWAYS_INCLUDE,
        on_none="all",
    )
