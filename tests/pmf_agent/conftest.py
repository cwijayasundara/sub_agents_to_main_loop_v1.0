import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage


class ToolCallingFakeChatModel(GenericFakeChatModel):
    """GenericFakeChatModel that tolerates bind_tools (langgraph agents always bind)."""

    def bind_tools(self, tools, **kwargs):  # noqa: D102 - ignore, return self
        return self


@pytest.fixture
def fake_model():
    return ToolCallingFakeChatModel(messages=iter([AIMessage("ok")]))


def make_fake_model(text: str = "ok"):
    return ToolCallingFakeChatModel(messages=iter([AIMessage(text)]))
