"""Model registry helpers."""

from __future__ import annotations


class ModelRegistry:
    """Returns built-in known model list."""

    def list_models(self) -> list[dict[str, str]]:
        return [
            {"name": "gpt-4o", "provider": "openai"},
            {"name": "gpt-4o-mini", "provider": "openai"},
            {"name": "o3", "provider": "openai"},
            {"name": "claude-sonnet-4-20250514", "provider": "anthropic"},
            {"name": "qwen-max", "provider": "dashscope"},
            {"name": "deepseek-chat", "provider": "deepseek"},
        ]
