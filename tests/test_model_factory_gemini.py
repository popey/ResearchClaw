from types import SimpleNamespace

from researchclaw.agents.model_factory import (
    _OpenAIChatFallback,
    _create_remote_model,
)


def test_create_remote_model_defaults_gemini_openai_compatible_base_url(
    monkeypatch,
):
    calls = []

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            calls.append(kwargs)

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
            "provider": "gemini",
            "model_type": "gemini",
            "model_name": "gemini-2.5-flash",
            "api_key": "AIza-demo",
        }
    )

    assert isinstance(model, _OpenAIChatFallback)
    assert calls[0]["api_key"] == "AIza-demo"
    assert (
        calls[0]["base_url"]
        == "https://generativelanguage.googleapis.com/v1beta/openai/"
    )
