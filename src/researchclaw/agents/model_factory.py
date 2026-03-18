"""Model factory – unified creation of LLM model instances and formatters.

Mirrors the CoPaw pattern: a single ``create_model_and_formatter()`` entry
point that returns ``(model, formatter)`` ready for the ScholarAgent.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Optional

from ..constant import DEFAULT_MODEL_NAME

logger = logging.getLogger(__name__)


@dataclass
class _ChatMessageFallback:
    """Normalized chat message shape used by the agent runtime."""

    content: str | None
    tool_calls: Any
    reasoning_content: str | None = None
    raw_message: Any = None


class _OpenAIChatFallback:
    """Minimal OpenAI-compatible chat wrapper used when agentscope is not available.

    Provides the same interface expected by ScholarAgent._reasoning():
    ``response = model(messages)`` returns an object with ``.content`` and
    ``.tool_calls`` attributes.
    """

    def __init__(
        self,
        client: Any,
        model_name: str,
        *,
        default_extra_body: dict[str, Any] | None = None,
        collapse_system_messages: bool = False,
    ) -> None:
        self.client = client
        self.model_name = model_name
        self.default_extra_body = dict(default_extra_body or {})
        self.collapse_system_messages = collapse_system_messages

    def _merge_kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        merged = dict(kwargs)
        extra_body = merged.get("extra_body")
        if self.default_extra_body:
            next_extra = dict(self.default_extra_body)
            if isinstance(extra_body, dict):
                next_extra.update(extra_body)
            merged["extra_body"] = next_extra
        return merged

    @staticmethod
    def _extract_reasoning_text(payload: Any) -> str | None:
        direct = getattr(payload, "reasoning_content", None) or getattr(
            payload,
            "reasoning",
            None,
        )
        if isinstance(direct, str) and direct.strip():
            return direct

        details = getattr(payload, "reasoning_details", None)
        if not details:
            return None

        parts: list[str] = []
        for item in details:
            if isinstance(item, dict):
                text = item.get("text")
            else:
                text = getattr(item, "text", None)
            if isinstance(text, str) and text:
                parts.append(text)
        return "\n".join(parts).strip() or None

    def _normalize_message(self, message: Any) -> _ChatMessageFallback:
        return _ChatMessageFallback(
            content=getattr(message, "content", None),
            tool_calls=getattr(message, "tool_calls", None),
            reasoning_content=self._extract_reasoning_text(message),
            raw_message=message,
        )

    @staticmethod
    def _collapse_system_messages(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        system_parts: list[str] = []
        others: list[dict[str, Any]] = []
        for msg in messages:
            if msg.get("role") == "system":
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    system_parts.append(content)
            else:
                others.append(msg)

        if not system_parts:
            return list(messages)

        return [
            {"role": "system", "content": "\n\n".join(system_parts)},
            *others,
        ]

    def __call__(self, messages: list[dict], **kwargs: Any) -> Any:
        if self.collapse_system_messages:
            messages = self._collapse_system_messages(messages)
        call_kwargs = self._merge_kwargs(kwargs)
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            **call_kwargs,
        )
        return self._normalize_message(response.choices[0].message)

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

        if self.collapse_system_messages:
            messages = self._collapse_system_messages(messages)
        kwargs.pop("stream", None)
        call_kwargs = self._merge_kwargs(kwargs)
        stream = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=True,
            **call_kwargs,
        )

        # Accumulate partial tool calls
        tool_call_bufs: dict[int, dict] = {}
        reasoning_buffer = ""

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

            reasoning_details = getattr(delta, "reasoning_details", None)
            if reasoning_details:
                text_parts: list[str] = []
                for item in reasoning_details:
                    if isinstance(item, dict):
                        text = item.get("text")
                    else:
                        text = getattr(item, "text", None)
                    if isinstance(text, str) and text:
                        text_parts.append(text)
                merged_reasoning = "".join(text_parts)
                if merged_reasoning:
                    new_reasoning = (
                        merged_reasoning[len(reasoning_buffer) :]
                        if merged_reasoning.startswith(reasoning_buffer)
                        else merged_reasoning
                    )
                    if new_reasoning:
                        yield {"type": "thinking", "content": new_reasoning}
                    reasoning_buffer = merged_reasoning

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


class _AnthropicChatFallback:
    """Anthropic-compatible chat wrapper normalized to OpenAI-style fields."""

    def __init__(
        self,
        client: Any,
        model_name: str,
        *,
        max_tokens: int = 4096,
    ) -> None:
        self.client = client
        self.model_name = model_name
        self.max_tokens = max_tokens

    @staticmethod
    def _combine_system_messages(messages: list[dict[str, Any]]) -> str | None:
        parts = [
            str(msg.get("content", "")).strip()
            for msg in messages
            if msg.get("role") == "system" and str(msg.get("content", "")).strip()
        ]
        return "\n\n".join(parts) if parts else None

    @staticmethod
    def _json_loads_best_effort(value: Any) -> Any:
        if isinstance(value, dict):
            return value
        if not isinstance(value, str):
            return {}
        try:
            parsed = json.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _to_anthropic_tools(tools: Any) -> list[dict[str, Any]] | None:
        if not isinstance(tools, list):
            return None

        out: list[dict[str, Any]] = []
        for item in tools:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "function":
                continue
            fn = item.get("function", {})
            if not isinstance(fn, dict):
                continue
            name = str(fn.get("name", "")).strip()
            if not name:
                continue
            out.append(
                {
                    "name": name,
                    "description": str(fn.get("description", "") or ""),
                    "input_schema": fn.get("parameters", {"type": "object"}),
                }
            )
        return out or None

    @classmethod
    def _to_anthropic_messages(
        cls,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []

        for msg in messages:
            role = str(msg.get("role", "") or "").strip()
            if role == "system":
                continue

            if role == "user":
                out.append({"role": "user", "content": str(msg.get("content", ""))})
                continue

            if role == "assistant":
                content_blocks: list[dict[str, Any]] = []
                text = msg.get("content")
                if isinstance(text, str) and text:
                    content_blocks.append({"type": "text", "text": text})
                for tc in msg.get("tool_calls", []) or []:
                    if not isinstance(tc, dict):
                        continue
                    fn = tc.get("function", {})
                    if not isinstance(fn, dict):
                        continue
                    name = str(fn.get("name", "") or "").strip()
                    if not name:
                        continue
                    content_blocks.append(
                        {
                            "type": "tool_use",
                            "id": str(tc.get("id", "") or ""),
                            "name": name,
                            "input": cls._json_loads_best_effort(
                                fn.get("arguments", "{}")
                            ),
                        }
                    )
                if content_blocks:
                    out.append({"role": "assistant", "content": content_blocks})
                continue

            if role == "tool":
                tool_use_id = str(msg.get("tool_call_id", "") or "").strip()
                if not tool_use_id:
                    continue
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": str(msg.get("content", "")),
                            }
                        ],
                    }
                )

        return out

    @staticmethod
    def _merge_adjacent_messages(
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for msg in messages:
            if not merged or merged[-1]["role"] != msg["role"]:
                merged.append(msg)
                continue

            prev = merged[-1]
            prev_content = prev.get("content")
            next_content = msg.get("content")

            if isinstance(prev_content, str) and isinstance(next_content, str):
                prev["content"] = f"{prev_content}\n\n{next_content}".strip()
            else:
                prev_blocks = (
                    list(prev_content) if isinstance(prev_content, list) else []
                )
                next_blocks = (
                    list(next_content) if isinstance(next_content, list) else []
                )
                prev["content"] = [*prev_blocks, *next_blocks]

        return merged

    @classmethod
    def _prepare_request(
        cls,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
        *,
        model_name: str,
        max_tokens: int,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": model_name,
            "max_tokens": int(kwargs.get("max_tokens") or max_tokens),
            "messages": cls._merge_adjacent_messages(
                cls._to_anthropic_messages(messages)
            ),
        }
        system = cls._combine_system_messages(messages)
        if system:
            params["system"] = system

        tools = cls._to_anthropic_tools(kwargs.get("tools"))
        if tools:
            params["tools"] = tools

        if "temperature" in kwargs:
            params["temperature"] = kwargs["temperature"]

        return params

    @staticmethod
    def _normalize_response(response: Any) -> _ChatMessageFallback:
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_calls: list[Any] = []

        for block in getattr(response, "content", []) or []:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text = getattr(block, "text", None)
                if isinstance(text, str) and text:
                    text_parts.append(text)
            elif block_type == "thinking":
                thinking = getattr(block, "thinking", None)
                if isinstance(thinking, str) and thinking:
                    thinking_parts.append(thinking)
            elif block_type == "tool_use":
                tool_calls.append(
                    SimpleNamespace(
                        id=getattr(block, "id", ""),
                        function=SimpleNamespace(
                            name=getattr(block, "name", ""),
                            arguments=json.dumps(
                                getattr(block, "input", {}) or {},
                                ensure_ascii=False,
                            ),
                        ),
                    )
                )

        content = "\n".join(part for part in text_parts if part).strip() or None
        reasoning = (
            "\n".join(part for part in thinking_parts if part).strip() or None
        )
        return _ChatMessageFallback(
            content=content,
            tool_calls=tool_calls,
            reasoning_content=reasoning,
            raw_message=response,
        )

    def __call__(self, messages: list[dict], **kwargs: Any) -> Any:
        params = self._prepare_request(
            messages,
            kwargs,
            model_name=self.model_name,
            max_tokens=self.max_tokens,
        )
        response = self.client.messages.create(**params)
        return self._normalize_response(response)

    def stream(self, messages: list[dict], **kwargs: Any) -> Any:
        params = self._prepare_request(
            messages,
            kwargs,
            model_name=self.model_name,
            max_tokens=self.max_tokens,
        )
        params["stream"] = True
        stream = self.client.messages.create(**params)

        tool_buffers: dict[int, dict[str, str]] = {}

        for event in stream:
            event_type = getattr(event, "type", "")

            if event_type == "content_block_start":
                block = getattr(event, "content_block", None)
                index = int(getattr(event, "index", 0))
                block_type = getattr(block, "type", "")

                if block_type == "thinking":
                    text = getattr(block, "thinking", "")
                    if text:
                        yield {"type": "thinking", "content": text}
                elif block_type == "text":
                    text = getattr(block, "text", "")
                    if text:
                        yield {"type": "content", "content": text}
                elif block_type == "tool_use":
                    tool_buffers[index] = {
                        "id": str(getattr(block, "id", "") or ""),
                        "name": str(getattr(block, "name", "") or ""),
                        "arguments": "",
                    }
                    block_input = getattr(block, "input", None)
                    if isinstance(block_input, dict) and block_input:
                        tool_buffers[index]["arguments"] = json.dumps(
                            block_input,
                            ensure_ascii=False,
                        )

            elif event_type == "content_block_delta":
                delta = getattr(event, "delta", None)
                index = int(getattr(event, "index", 0))
                delta_type = getattr(delta, "type", "")

                if delta_type == "text_delta":
                    text = getattr(delta, "text", "")
                    if text:
                        yield {"type": "content", "content": text}
                elif delta_type == "thinking_delta":
                    text = getattr(delta, "thinking", "")
                    if text:
                        yield {"type": "thinking", "content": text}
                elif delta_type == "input_json_delta":
                    partial_json = getattr(delta, "partial_json", "")
                    if index not in tool_buffers:
                        tool_buffers[index] = {
                            "id": "",
                            "name": "",
                            "arguments": "",
                        }
                    tool_buffers[index]["arguments"] += partial_json

            elif event_type == "content_block_stop":
                index = int(getattr(event, "index", 0))
                if index in tool_buffers:
                    buf = tool_buffers.pop(index)
                    yield {
                        "type": "tool_call",
                        "index": index,
                        "id": buf["id"],
                        "name": buf["name"],
                        "arguments": buf["arguments"] or "{}",
                    }

            elif event_type == "message_stop":
                break

        yield {"type": "done"}


def _looks_like_minimax_coding_plan(
    provider: str,
    api_key: str,
    api_url: str | None,
) -> bool:
    del provider
    del api_url
    api_key = (api_key or "").strip()
    return api_key.startswith("sk-cp-")


def _uses_minimax_anthropic_transport(
    provider: str,
    api_url: str | None,
) -> bool:
    provider = (provider or "").strip().lower()
    value = (api_url or "").strip().lower()
    return provider == "anthropic" or (
        provider == "minimax" and "/anthropic" in value
    )


def _default_minimax_base_url(api_url: str | None, suffix: str) -> str:
    value = (api_url or "").strip().lower()
    host = "https://api.minimax.io"
    if "minimaxi.com" in value:
        host = "https://api.minimaxi.com"
    return f"{host}{suffix}"


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
    provider = str(
        llm_cfg.get("provider")
        or llm_cfg.get("provider_type")
        or llm_cfg.get("model_type", "openai_chat"),
    ).strip().lower()
    is_minimax = provider == "minimax"
    is_minimax_coding_plan = _looks_like_minimax_coding_plan(
        provider,
        api_key,
        api_url,
    )
    uses_anthropic_transport = _uses_minimax_anthropic_transport(
        provider,
        api_url,
    )

    if is_minimax_coding_plan and (
        not model_name
        or model_name == DEFAULT_MODEL_NAME
        or model_name == "MiniMax-M2.5"
    ):
        model_name = "MiniMax-M2.7"

    if uses_anthropic_transport and is_minimax and not api_url:
        api_url = _default_minimax_base_url(api_url, "/anthropic")
    elif is_minimax and not api_url:
        api_url = _default_minimax_base_url(api_url, "/v1")

    default_extra_body = {"reasoning_split": True} if is_minimax else None

    if uses_anthropic_transport:
        try:
            from anthropic import Anthropic

            client_kwargs: dict[str, Any] = {}
            if is_minimax and "/anthropic" in str(api_url or "").lower():
                client_kwargs["auth_token"] = api_key
            else:
                client_kwargs["api_key"] = api_key
            if api_url:
                client_kwargs["base_url"] = api_url

            model = _AnthropicChatFallback(
                client=Anthropic(**client_kwargs),
                model_name=model_name,
            )
            formatter = _create_formatter(model)
            return model, formatter
        except ImportError:
            raise ImportError(
                "Anthropic SDK is required for Anthropic-compatible providers. "
                "Install with: pip install anthropic",
            )

    # MiniMax's OpenAI-compatible format exposes reasoning via
    # reasoning_details. Use the direct OpenAI SDK path so we can preserve
    # those fields consistently for both sync and streaming tool use.
    if is_minimax:
        try:
            from openai import OpenAI

            client_kwargs: dict[str, Any] = {"api_key": api_key}
            if api_url:
                client_kwargs["base_url"] = api_url

            model = _OpenAIChatFallback(
                client=OpenAI(**client_kwargs),
                model_name=model_name,
                default_extra_body=default_extra_body,
                collapse_system_messages=is_minimax,
            )
            formatter = _create_formatter(model)
            return model, formatter
        except ImportError:
            raise ImportError(
                "OpenAI SDK is required for MiniMax compatibility mode. "
                "Install with: pip install openai",
            )

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
            default_extra_body=default_extra_body,
            collapse_system_messages=is_minimax,
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
