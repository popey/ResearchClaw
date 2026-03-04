"""Abstract base class for local-model backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generator

from ..schema import LocalModelInfo


class LocalBackend(ABC):
    """Common interface every backend must implement."""

    def __init__(self, model_info: LocalModelInfo) -> None:
        self.model_info = model_info

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str:
        """Run a blocking chat completion and return the full text."""

    @abstractmethod
    def chat_completion_stream(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> Generator[str, None, None]:
        """Yield tokens as they are generated."""

    @abstractmethod
    def unload(self) -> None:
        """Release all resources held by the backend."""

    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """Return ``True`` when the model is ready for inference."""
