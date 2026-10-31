import pytest


def test_chat_model_wiring():
    from langchain_openai import ChatOpenAI

    from pmf_agent.fw import FIREWORKS_BASE_URL, MODEL_ID, chat_model

    assert MODEL_ID == "accounts/fireworks/models/glm-5p3-flash"
    assert FIREWORKS_BASE_URL == "https://api.fireworks.ai/inference/v1"
    m = chat_model()
    assert isinstance(m, ChatOpenAI)
    assert m.model_name == MODEL_ID
    assert m.openai_api_base == FIREWORKS_BASE_URL


def test_missing_key_raises_clear_error(monkeypatch):
    from pmf_agent import fw

    monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FIREWORKS_API_KEY"):
        fw.chat_model()


def test_placeholder_prices_present():
    from pmf_agent.fw import PRICE_PER_M_INPUT, PRICE_PER_M_OUTPUT

    assert PRICE_PER_M_INPUT > 0 and PRICE_PER_M_OUTPUT > 0
