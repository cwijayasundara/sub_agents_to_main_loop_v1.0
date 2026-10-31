import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


def _fake_model():
    return GenericFakeChatModel(messages=iter([AIMessage("ok")]))


def test_slack_profile_binds_all_tools():
    from pmf_agent.agent import create_agent

    agent = create_agent("slack", model=_fake_model())
    names = {t.name for t in agent.pmf_tools}
    from pmf_agent.tools import ALL_TOOL_NAMES

    assert names == set(ALL_TOOL_NAMES)


def test_scheduled_profile_is_read_only():
    from pmf_agent.agent import create_agent
    from pmf_agent.tools import READ_TOOL_NAMES

    agent = create_agent("scheduled", model=_fake_model())
    names = {t.name for t in agent.pmf_tools}
    assert names == set(READ_TOOL_NAMES)
    assert "propose_campaign_change" not in names


def test_invalid_entry_point_raises():
    from pmf_agent.agent import create_agent

    with pytest.raises(ValueError, match="entry_point"):
        create_agent("email", model="fake")


def test_prompt_is_thin_map():
    from pmf_agent.prompts import system_prompt

    text = system_prompt("slack")
    assert len(text) < 1200
    assert "google_ads" in text or "source" in text.lower()  # tells where numbers come from
    assert "approval" in text.lower()  # tells where writes go


def test_factory_injects_model():
    from langchain_openai import ChatOpenAI

    from pmf_agent.agent import create_agent

    m = ChatOpenAI(model="gpt-4o-mini", api_key="test")
    agent = create_agent("slack", model=m)
    assert agent is not None
