"""Local model management and inference for ResearchClaw.

Supports downloading, managing, and running local LLM models via
llama.cpp (GGUF) and MLX (Apple Silicon) backends.
"""

from .schema import (
    BackendType,
    DownloadSource,
    LocalModelInfo,
    DownloadProgress,
)
from .manager import (
    LocalModelManager,
    list_local_models,
    get_local_model,
    delete_local_model,
)
from .factory import (
    create_local_chat_model,
    unload_active_model,
    get_active_local_model,
)

__all__ = [
    "BackendType",
    "DownloadSource",
    "LocalModelInfo",
    "DownloadProgress",
    "LocalModelManager",
    "list_local_models",
    "get_local_model",
    "delete_local_model",
    "create_local_chat_model",
    "unload_active_model",
    "get_active_local_model",
]
