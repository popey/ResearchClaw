from types import SimpleNamespace
import sys

from researchclaw.agents.model_factory import (
    _AnthropicChatFallback,
    _create_remote_model,
    _looks_like_minimax_coding_plan,
    _uses_minimax_anthropic_transport,
)


class _FakeAnthropicMessages:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class _FakeAnthropicClient:
    def __init__(self, response):
        self.messages = _FakeAnthropicMessages(response)


def test_detect_minimax_coding_plan_from_key_prefix():
    assert _looks_like_minimax_coding_plan(
        "minimax",
        "sk-cp-demo",
        "https://api.minimax.io/v1",
    )


def test_detect_anthropic_transport_from_minimax_base_url():
    assert _uses_minimax_anthropic_transport(
        "minimax",
        "https://api.minimax.io/anthropic",
    )


def test_anthropic_fallback_normalizes_tool_use_response():
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking="analyze first"),
            SimpleNamespace(type="text", text="I'll use a tool."),
            SimpleNamespace(
                type="tool_use",
                id="toolu_1",
                name="search_notes",
                input={"query": "rag"},
            ),
        ],
    )
    client = _FakeAnthropicClient(response)
    model = _AnthropicChatFallback(client=client, model_name="MiniMax-M2.7")

    result = model(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "find notes"},
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "search_notes",
                    "description": "Search saved notes",
                    "parameters": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                },
            },
        ],
    )

    assert result.content == "I'll use a tool."
    assert result.reasoning_content == "analyze first"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].id == "toolu_1"
    assert result.tool_calls[0].function.name == "search_notes"
    assert result.tool_calls[0].function.arguments == '{"query": "rag"}'

    call = client.messages.calls[0]
    assert call["system"] == "You are helpful."
    assert call["messages"] == [{"role": "user", "content": "find notes"}]
    assert call["tools"][0]["name"] == "search_notes"


def test_anthropic_fallback_converts_tool_result_history():
    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="done")],
    )
    client = _FakeAnthropicClient(response)
    model = _AnthropicChatFallback(client=client, model_name="MiniMax-M2.7")

    model(
        [
            {"role": "user", "content": "start"},
            {
                "role": "assistant",
                "content": "calling tool",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "search_notes",
                            "arguments": '{"query":"rag"}',
                        },
                    },
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "content": "result body",
            },
        ],
    )

    call = client.messages.calls[0]
    assert call["messages"][1]["role"] == "assistant"
    assert call["messages"][1]["content"][1]["type"] == "tool_use"
    assert call["messages"][2]["role"] == "user"
    assert call["messages"][2]["content"][0]["type"] == "tool_result"
    assert call["messages"][2]["content"][0]["tool_use_id"] == "call_1"


def test_create_remote_model_uses_auth_token_for_minimax_anthropic_transport(
    monkeypatch,
):
    calls = []

    class _FakeAnthropic:
        def __init__(self, **kwargs):
            calls.append(kwargs)
            self.kwargs = kwargs

    monkeypatch.setitem(
        sys.modules,
        "anthropic",
        SimpleNamespace(Anthropic=_FakeAnthropic),
    )

    model, _ = _create_remote_model(
        {
            "provider": "minimax",
            "model_type": "minimax",
            "model_name": "MiniMax-M2.7",
            "api_key": "sk-cp-demo",
            "api_url": "https://api.minimax.io/anthropic",
        },
    )

    assert isinstance(model, _AnthropicChatFallback)
    assert calls[0]["auth_token"] == "sk-cp-demo"
    assert "api_key" not in calls[0]
    assert calls[0]["base_url"] == "https://api.minimax.io/anthropic"
