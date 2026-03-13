"""Dispatch primitives for the internal gateway layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DispatchTarget:
    """Normalized outbound dispatch target."""

    channel: str
    user_id: str = "main"
    session_id: str = "main"


def normalize_channel_name(name: str) -> str:
    """Normalize a channel key for routing and dedupe."""
    return (name or "").strip().lower()


def coerce_dispatch_target(
    *,
    channel: str,
    user_id: str = "main",
    session_id: str = "main",
) -> DispatchTarget | None:
    """Build a normalized dispatch target or return None for empty channels."""
    normalized = normalize_channel_name(channel)
    if not normalized:
        return None
    return DispatchTarget(
        channel=normalized,
        user_id=(user_id or "").strip() or "main",
        session_id=(session_id or "").strip() or "main",
    )


def dedupe_dispatch_mappings(
    dispatches: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Normalize and dedupe dispatch mapping dictionaries."""
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in dispatches:
        target = coerce_dispatch_target(
            channel=str(item.get("channel", "")),
            user_id=str(item.get("user_id", "") or ""),
            session_id=str(item.get("session_id", "") or ""),
        )
        if target is None:
            continue
        key = (target.channel, target.user_id, target.session_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "channel": target.channel,
                "user_id": target.user_id,
                "session_id": target.session_id,
            },
        )
    return out
