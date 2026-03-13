"""Ingress-side helpers shared across gateway entry points."""

from __future__ import annotations

import uuid


def default_session_id(*, prefix: str, provided: str | None = None) -> str:
    """Return a provided session id or generate one with a stable prefix."""
    value = str(provided or "").strip()
    if value:
        return value
    normalized_prefix = (prefix or "gateway").strip() or "gateway"
    return f"{normalized_prefix}:{uuid.uuid4().hex[:12]}"
