"""Model registry helpers."""

from __future__ import annotations


class ModelRegistry:
    """Returns built-in known model list."""

    def list_models(self) -> list[dict[str, str]]:
        return [
            {"name": "gpt-5", "provider": "openai"},
            {"name": "gpt-5-mini", "provider": "openai"},
            {"name": "gpt-5-nano", "provider": "openai"},
            {"name": "gpt-4.1", "provider": "openai"},
            {"name": "o4-mini", "provider": "openai"},
            {"name": "claude-opus-4-1-20250805", "provider": "anthropic"},
            {"name": "claude-sonnet-4-20250514", "provider": "anthropic"},
            {"name": "claude-3-5-haiku-latest", "provider": "anthropic"},
            {"name": "qwen-max", "provider": "dashscope"},
            {"name": "qwen-plus", "provider": "dashscope"},
            {"name": "qwen-turbo", "provider": "dashscope"},
            {"name": "qwq-plus", "provider": "dashscope"},
            {"name": "deepseek-chat", "provider": "deepseek"},
            {"name": "deepseek-reasoner", "provider": "deepseek"},
            {"name": "llama3.2", "provider": "ollama"},
            {"name": "qwen2.5", "provider": "ollama"},
            {"name": "deepseek-r1", "provider": "ollama"},
        ]
