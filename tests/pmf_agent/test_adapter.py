from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from pmf_evals.runner import AgentUnderTest
from pmf_evals.scenarios import Scenario
from pmf_agent.adapter import FireworksAgentUnderTest, extract_text, extract_tool_calls, extract_usage


def _msgs():
    return [
        HumanMessage("how did google spend move?"),
        AIMessage(
            "",
            tool_calls=[{"name": "compare_platform_windows", "args": {}, "id": "c1"}],
            usage_metadata={"input_tokens": 100, "output_tokens": 10, "total_tokens": 110},
        ),
        ToolMessage("{}", tool_call_id="c1"),
        AIMessage(
            "google spend was up.",
            usage_metadata={"input_tokens": 200, "output_tokens": 30, "total_tokens": 230},
        ),
    ]


def test_extract_text_takes_last_ai_text():
    assert extract_text(_msgs()) == "google spend was up."


def test_extract_tool_calls_across_turns_deduped_in_order():
    calls = extract_tool_calls(_msgs())
    assert calls == ["compare_platform_windows"]


def test_usage_sums_across_model_turns():
    usage = extract_usage(_msgs())
    assert usage["input_tokens"] == 300  # 100 + 200
    assert usage["output_tokens"] == 40  # 10 + 30


def test_adapter_satisfies_protocol():
    adapter = FireworksAgentUnderTest(entry_point="slack", model="stub")
    assert isinstance(adapter, AgentUnderTest)


def test_adapter_run_maps_to_run_result(monkeypatch):
    from pmf_agent import adapter as ad

    captured = {}

    class StubGraph:
        def invoke(self, state, config):
            captured.update(config)
            return {"messages": _msgs()}

    monkeypatch.setattr(ad.FireworksAgentUnderTest, "_build", lambda self: StubGraph())
    adapter = ad.FireworksAgentUnderTest(entry_point="slack", model="stub")
    scenario = Scenario(id="q01_x", entry_point="slack", category="q_and_a", prompt="p")
    result = adapter.run(scenario)
    assert result.text == "google spend was up."
    assert result.tool_calls == ["compare_platform_windows"]
    assert result.tokens_in == 300
    assert result.tokens_out == 40
    assert result.cost_usd > 0
    assert result.latency_ms >= 0
    assert captured["configurable"]["thread_id"]  # per-scenario thread


def test_entry_point_validated():
    import pytest

    with pytest.raises(ValueError, match="entry_point"):
        FireworksAgentUnderTest(entry_point="email", model="stub")
