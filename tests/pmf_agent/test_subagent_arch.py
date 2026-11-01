import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


def _fake():
    return GenericFakeChatModel(messages=iter([AIMessage("ok")]))


def test_platform_read_tools_are_scoped():
    from pmf_agent.subagent_arch import platform_read_tools

    tools = platform_read_tools("google_ads")
    names = {t.name for t in tools}
    assert {"check_performance", "compare_windows", "read_context"} <= names
    result = tools[0].invoke({"window": "last_week"}) if False else next(
        t for t in tools if t.name == "check_performance"
    ).invoke({"window": "last_week"})
    assert result["platform"] == "google_ads"  # platform pre-bound
    assert result["window"] == "last_week"


def test_hierarchical_agent_builds_with_three_platform_subagents():
    from pmf_agent.subagent_arch import create_hierarchical_agent

    agent = create_hierarchical_agent("slack", model=_fake())
    assert set(agent.pmf_subagents) == {"google-ads-specialist", "meta-ads-specialist", "reddit-ads-specialist"}


def test_hierarchical_parent_has_no_direct_read_tools():
    """The parent delegates analysis; it does not hold the platform read tools."""
    from pmf_agent.subagent_arch import create_hierarchical_agent

    agent = create_hierarchical_agent("slack", model=_fake())
    parent_names = {t.name for t in agent.pmf_tools}
    assert "check_platform_performance" not in parent_names
    assert "propose_campaign_change" in parent_names  # writes stay at the parent


def test_hierarchical_scheduled_has_no_propose():
    from pmf_agent.subagent_arch import create_hierarchical_agent

    agent = create_hierarchical_agent("scheduled", model=_fake())
    parent_names = {t.name for t in agent.pmf_tools}
    assert "propose_campaign_change" not in parent_names


def test_unknown_platform_raises():
    from pmf_agent.subagent_arch import platform_read_tools

    with pytest.raises(ValueError, match="platform"):
        platform_read_tools("tiktok_ads")
