"""Ollama model management via the Ollama Python SDK."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

_OLLAMA_TIMEOUT_SECONDS = 10


class OllamaModelInfo(BaseModel):
    """Metadata for one Ollama model."""

    name: str = Field(..., description="Model name, e.g. 'llama3:8b'")
    size: int = Field(0, description="Model size in bytes")
    digest: Optional[str] = Field(default=None, description="Model digest")
    modified_at: Optional[str] = Field(default=None, description="Modified time")

    @field_validator("modified_at", mode="before")
    @classmethod
    def convert_datetime_to_str(
        cls,
        value: Union[str, datetime, None],
    ) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)


def _ensure_ollama():
    try:
        import ollama  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "The 'ollama' Python package is required. "
            "Install with: pip install 'researchclaw[ollama]'",
        ) from exc
    return ollama


class OllamaModelManager:
    """High-level model lifecycle wrapper for Ollama."""

    @staticmethod
    def _make_client(host: Optional[str] = None):
        ollama = _ensure_ollama()
        kwargs: dict = {"timeout": _OLLAMA_TIMEOUT_SECONDS}
        if host:
            kwargs["host"] = host
        return ollama.Client(**kwargs)

    @staticmethod
    def list_models(host: Optional[str] = None) -> List[OllamaModelInfo]:
        raw = OllamaModelManager._make_client(host).list()
        out: List[OllamaModelInfo] = []
        for item in raw.get("models", []):
            out.append(
                OllamaModelInfo(
                    name=item.get("model", ""),
                    size=item.get("size", 0) or 0,
                    digest=item.get("digest"),
                    modified_at=item.get("modified_at"),
                ),
            )
        return out

    @staticmethod
    def pull_model(name: str, host: Optional[str] = None) -> OllamaModelInfo:
        logger.info("Pulling Ollama model: %s", name)
        OllamaModelManager._make_client(host).pull(name)
        logger.info("Pull completed: %s", name)

        for model in OllamaModelManager.list_models(host=host):
            if model.name == name:
                return model
        raise ValueError(f"Ollama model '{name}' not found after pull.")

    @staticmethod
    def delete_model(name: str, host: Optional[str] = None) -> None:
        logger.info("Deleting Ollama model: %s", name)
        OllamaModelManager._make_client(host).delete(name)
        logger.info("Ollama model deleted: %s", name)
