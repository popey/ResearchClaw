"""Model factory – unified creation of LLM model instances and formatters.

Mirrors the CoPaw pattern: a single ``create_model_and_formatter()`` entry
point that returns ``(model, formatter)`` ready for the ScholarAgent.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from ..constant import DEFAULT_MODEL_NAME

logger = logging.getLogger(__name__)


class _OpenAIChatFallback:
    """Minimal OpenAI-compatible chat wrapper used when agentscope is not available.

    Provides the same interface expected by ScholarAgent._reasoning():
    ``response = model(messages)`` returns an object with ``.content`` and
    ``.tool_calls`` attributes.
    """

    def __init__(self, client: Any, model_name: str) -> None:
        self.client = client
        self.model_name = model_name

    def __call__(self, messages: list[dict], **kwargs: Any) -> Any:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            **kwargs,
        )
        return response.choices[0].message

    def stream(self, messages: list[dict], **kwargs: Any) -> Any:
        """Return a streaming iterator of chat completion chunks.

        Yields ``dict`` events with one of these shapes:
        - ``{"type": "thinking", "content": "..."}``
        - ``{"type": "content", "content": "..."}``
        - ``{"type": "tool_call", "index": int, "id": str,
               "name": str, "arguments": str}``
        - ``{"type": "done"}``
        """
        import json as _json

        kwargs.pop("stream", None)
        stream = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=True,
            **kwargs,
        )

        # Accumulate partial tool calls
        tool_call_bufs: dict[int, dict] = {}

        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta is None:
                continue

            finish_reason = chunk.choices[0].finish_reason

            # ── Reasoning / thinking tokens ──
            reasoning = getattr(delta, "reasoning_content", None) or getattr(
                delta,
                "reasoning",
                None,
            )
            if reasoning:
                yield {"type": "thinking", "content": reasoning}

            # ── Regular content tokens ──
            if delta.content:
                yield {"type": "content", "content": delta.content}

            # ── Tool calls (streamed incrementally) ──
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_call_bufs:
                        tool_call_bufs[idx] = {
                            "id": tc.id or "",
                            "name": (tc.function.name if tc.function else "")
                            or "",
                            "arguments": "",
                        }
                    buf = tool_call_bufs[idx]
                    if tc.id:
                        buf["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            buf["name"] = tc.function.name
                        if tc.function.arguments:
                            buf["arguments"] += tc.function.arguments

            # When the model finishes a tool-call turn, flush buffers
            if finish_reason == "tool_calls":
                for idx in sorted(tool_call_bufs):
                    buf = tool_call_bufs[idx]
                    yield {
                        "type": "tool_call",
                        "index": idx,
                        "id": buf["id"],
                        "name": buf["name"],
                        "arguments": buf["arguments"],
                    }
                tool_call_bufs.clear()

            if finish_reason == "stop":
                break

        yield {"type": "done"}


def create_model_and_formatter(
    llm_cfg: Optional[dict[str, Any]] = None,
) -> tuple[Any, Any]:
    """Create an LLM model wrapper and its formatter.

    Parameters
    ----------
    llm_cfg:
        Optional model configuration dict. If *None*, the active LLM config
        is loaded from ``config.json``.

    Returns
    -------
    tuple[model, formatter]
        Ready-to-use model and formatter instances.
    """
    if llm_cfg is None:
        llm_cfg = _get_active_llm_config()

    model_type = llm_cfg.get("model_type", "openai_chat")

    # Local model shortcut
    if model_type in ("local", "llamacpp", "mlx", "ollama"):
        return _create_local_model(llm_cfg)

    return _create_remote_model(llm_cfg)


def _get_active_llm_config() -> dict[str, Any]:
    """Load the currently active LLM configuration."""
    try:
        from ..config.config import load_config

        config = load_config()
        providers = config.get("providers", {})
        active = providers.get("active")
        if active and active in providers.get("configs", {}):
            return providers["configs"][active]
    except Exception:
        logger.debug("Could not load active LLM config, using defaults")

    return {
        "model_type": "openai_chat",
        "model_name": DEFAULT_MODEL_NAME,
        "api_key": "",
    }


def _create_remote_model(llm_cfg: dict[str, Any]) -> tuple[Any, Any]:
    """Instantiate a remote (API-based) model and formatter."""
    model_name = llm_cfg.get("model_name", DEFAULT_MODEL_NAME)
    api_key = llm_cfg.get("api_key", "")
    api_url = llm_cfg.get("api_url", None)

    # Try agentscope first
    try:
        from agentscope.models import OpenAIChatWrapper

        config = {
            "config_name": f"researchclaw_{model_name}",
            "model_type": "openai_chat",
            "model_name": model_name,
            "api_key": api_key,
        }
        if api_url:
            config["client_args"] = {"base_url": api_url}

        model = OpenAIChatWrapper(**config)
        formatter = _create_formatter(model)
        return model, formatter

    except (ImportError, Exception) as e:
        logger.debug(
            "agentscope model wrapper not available (%s), "
            "falling back to direct OpenAI SDK",
            e,
        )

    # Fallback: use openai SDK directly
    try:
        from openai import OpenAI

        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if api_url:
            client_kwargs["base_url"] = api_url

        model = _OpenAIChatFallback(
            client=OpenAI(**client_kwargs),
            model_name=model_name,
        )
        formatter = _create_formatter(model)
        return model, formatter

    except ImportError:
        raise ImportError(
            "Neither agentscope nor openai SDK is available. "
            "Install one with: pip install agentscope  or  pip install openai",
        )


def _create_local_model(llm_cfg: dict[str, Any]) -> tuple[Any, Any]:
    """Instantiate a local model (Ollama, llama.cpp, etc.)."""
    model_type = llm_cfg.get("model_type", "ollama")

    if model_type == "ollama":
        model_name = llm_cfg.get("model_name", "llama3")
        try:
            from agentscope.models import OllamaChatWrapper

            config = {
                "config_name": f"researchclaw_ollama_{model_name}",
                "model_type": "ollama_chat",
                "model_name": model_name,
            }
            if "api_url" in llm_cfg:
                config["client_args"] = {"base_url": llm_cfg["api_url"]}

            model = OllamaChatWrapper(**config)
            formatter = _create_formatter(model)
            return model, formatter

        except (ImportError, Exception) as e:
            logger.debug(
                "agentscope Ollama wrapper not available (%s), "
                "falling back to direct OpenAI-compatible SDK",
                e,
            )

        # Fallback: Ollama exposes an OpenAI-compatible endpoint
        try:
            from openai import OpenAI

            base_url = llm_cfg.get("api_url", "http://localhost:11434/v1")
            client = OpenAI(base_url=base_url, api_key="ollama")
            model = _OpenAIChatFallback(client=client, model_name=model_name)
            formatter = _create_formatter(model)
            return model, formatter
        except ImportError:
            raise ImportError(
                "Neither agentscope nor openai SDK is available for Ollama fallback.",
            )

    # Fallback: treat as OpenAI-compatible
    return _create_remote_model(llm_cfg)


def _create_formatter(model: Any) -> Any:
    """Create a message formatter that supports FileBlock in tool results.

    Wraps the model's default formatter to properly handle file blocks
    returned by research tools (PDFs, figures, etc.).
    """
    try:
        from agentscope.formatters import OpenAIFormatter

        class ResearchFormatter(OpenAIFormatter):
            """Extended formatter with research file block support."""

            def convert_tool_result_to_string(self, result: Any) -> str:
                """Handle FileBlock and PaperInfo results gracefully."""
                if isinstance(result, dict):
                    block_type = result.get("type")
                    if block_type == "file":
                        filename = result.get("filename", "file")
                        return f"[File: {filename}]"
                    if "title" in result and "authors" in result:
                        # PaperInfo-like dict
                        title = result["title"]
                        authors = ", ".join(result.get("authors", [])[:3])
                        year = result.get("year", "")
                        return f"📄 {title} ({authors}, {year})"

                if isinstance(result, list):
                    parts = [
                        self.convert_tool_result_to_string(r) for r in result
                    ]
                    return "\n".join(parts)

                return str(result)

        return ResearchFormatter()

    except ImportError:
        logger.debug(
            "Using default formatter (agentscope formatters not available)",
        )
        return None
