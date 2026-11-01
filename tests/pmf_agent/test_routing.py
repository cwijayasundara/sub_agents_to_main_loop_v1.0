import pytest

from decision_harness.errors import SelectorUnavailable
from decision_harness.middleware.tool_selection import ToolSelectionMiddleware
from decision_harness.types import ToolSelection

from pmf_agent.routing import RecordingToolSelector, tool_selection_middleware


class FakeClient:
    """Stands in for DecisionsClient: returns probability 1.0 for the first tool."""

    zero_data_retention = True

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def post(self, payload):
        self.calls.append(payload)
        if self.fail:
            raise RuntimeError("wire down")
        return {"answers": [{"probability": 1.0}, {"probability": 0.0}, {"probability": 0.0}, {"probability": 0.0}]}

    def _parse_tools(self, data, tool_names):
        answers = data.get("answers", [])
        return {name: (ans["probability"] if i < len(answers) else 0.0) for i, (name, ans) in enumerate(zip(tool_names, answers))}


def test_middleware_is_tool_selection_middleware_with_recording_selector():
    mw = tool_selection_middleware(client=FakeClient())
    assert isinstance(mw, ToolSelectionMiddleware)
    assert isinstance(mw.selector, RecordingToolSelector)


def test_recording_selector_captures_selections():
    selector = RecordingToolSelector(client=FakeClient())
    selection = selector.select(
        "how did google spend move",
        [("check_platform_performance", "d"), ("compare_platform_windows", "d")],
    )
    assert selection.selected == ["check_platform_performance"]  # first tool had p=1.0
    assert len(selector.events) == 1
    task_text, recorded = selector.events[0]
    assert "google" in task_text
    assert recorded.selected == ["check_platform_performance"]


def test_degraded_selection_still_recorded():
    selector = RecordingToolSelector(client=FakeClient(fail=True))
    with pytest.raises(SelectorUnavailable):
        selector.select("task", [("a", "d")])
    assert len(selector.events) == 1
    task_text, recorded = selector.events[0]
    assert recorded.selected == []  # degraded marker


def test_conservative_defaults():
    mw = tool_selection_middleware(client=FakeClient())
    assert mw.always_include == ["list_platforms"]
    assert mw.on_none == "all"
