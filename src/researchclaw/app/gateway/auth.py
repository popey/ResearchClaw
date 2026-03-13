"""Shared auth helpers for gateway-facing ingress routes."""

from __future__ import annotations

from collections.abc import Mapping


def extract_bearer_token(authorization: str | None) -> str:
    """Extract a bearer token from an Authorization header value."""
    auth = str(authorization or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def extract_header_token(
    headers: Mapping[str, str],
    *header_names: str,
) -> str:
    """Return the first non-empty token value from the provided headers."""
    bearer = extract_bearer_token(headers.get("authorization"))
    if bearer:
        return bearer
    for name in header_names:
        value = str(headers.get(name, "") or "").strip()
        if value:
            return value
    return ""
