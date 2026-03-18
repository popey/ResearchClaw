from types import SimpleNamespace

from researchclaw.agents.model_factory import (
    _OpenAIChatFallback,
    _create_remote_model,
)


class _FakeCompletions:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class _FakeChat:
    def __init__(self, response):
        self.completions = _FakeCompletions(response)


class _FakeClient:
    def __init__(self, response):
        self.chat = _FakeChat(response)


def test_openai_fallback_promotes_minimax_reasoning_details():
    message = SimpleNamespace(
        content="final answer",
        tool_calls=[],
        reasoning_details=[{"text": "step one"}, {"text": "step two"}],
    )
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
    client = _FakeClient(response)
    model = _OpenAIChatFallback(
        client=client,
        model_name="MiniMax-M2.7",
        default_extra_body={"reasoning_split": True},
    )

    result = model([{"role": "user", "content": "hi"}])

    assert result.content == "final answer"
    assert result.reasoning_content == "step one\nstep two"
    assert (
        client.chat.completions.calls[0]["extra_body"]["reasoning_split"]
        is True
    )


def test_openai_fallback_merges_extra_body_without_losing_defaults():
    message = SimpleNamespace(content="ok", tool_calls=[], reasoning_details=[])
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
    client = _FakeClient(response)
    model = _OpenAIChatFallback(
        client=client,
        model_name="MiniMax-M2.5",
        default_extra_body={"reasoning_split": True},
    )

    model(
        [{"role": "user", "content": "hi"}],
        extra_body={"custom_flag": 1},
    )

    assert client.chat.completions.calls[0]["extra_body"] == {
        "reasoning_split": True,
        "custom_flag": 1,
    }


def test_create_remote_model_keeps_openai_transport_for_coding_plan_v1(
    monkeypatch,
):
    calls = []

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            calls.append(kwargs)
            self.kwargs = kwargs

        @property
        def chat(self):
            raise AssertionError("not used in this test")

    monkeypatch.setitem(
        __import__("sys").modules,
        "openai",
        SimpleNamespace(OpenAI=_FakeOpenAI),
    )

    model, _ = _create_remote_model(
        {
            "provider": "minimax",
            "model_type": "minimax",
            "model_name": "MiniMax-M2.7",
            "api_key": "sk-cp-demo",
            "api_url": "https://api.minimax.io/v1",
        }
    )

    assert isinstance(model, _OpenAIChatFallback)
    assert calls[0]["api_key"] == "sk-cp-demo"
    assert calls[0]["base_url"] == "https://api.minimax.io/v1"


def test_openai_fallback_can_collapse_multiple_system_messages():
    message = SimpleNamespace(content="ok", tool_calls=[], reasoning_details=[])
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
    client = _FakeClient(response)
    model = _OpenAIChatFallback(
        client=client,
        model_name="MiniMax-M2.7",
        collapse_system_messages=True,
    )

    model(
        [
            {"role": "system", "content": "sys1"},
            {"role": "system", "content": "sys2"},
            {"role": "user", "content": "hi"},
        ]
    )

    sent_messages = client.chat.completions.calls[0]["messages"]
    assert sent_messages == [
        {"role": "system", "content": "sys1\n\nsys2"},
        {"role": "user", "content": "hi"},
    ]
