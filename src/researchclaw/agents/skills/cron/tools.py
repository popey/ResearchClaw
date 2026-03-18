"""Cron job management tools for in-chat scheduling."""

from __future__ import annotations

import os
from typing import Any

import httpx

from ....app.channels.schema import DEFAULT_CHANNEL
from ....constant import DEFAULT_HOST, DEFAULT_PORT


def _resolve_base_url(base_url: str) -> str:
    if base_url and base_url.strip():
        return base_url.rstrip("/")

    env_url = os.environ.get("RESEARCHCLAW_API_BASE_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")

    host = (
        os.environ.get("RESEARCHCLAW_HOST", DEFAULT_HOST).strip()
        or DEFAULT_HOST
    )
    if host in {"0.0.0.0", "::", "[::]"}:
        host = "127.0.0.1"
    port = str(
        os.environ.get("RESEARCHCLAW_PORT", DEFAULT_PORT),
    ).strip() or str(DEFAULT_PORT)
    return f"http://{host}:{port}"


def _http_request(
    method: str,
    path: str,
    *,
    base_url: str = "",
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url_base = _resolve_base_url(base_url)
    try:
        with httpx.Client(base_url=url_base, timeout=30.0) as cli:
            res = cli.request(method=method.upper(), url=path, json=payload)
    except Exception as e:
        return {"ok": False, "error": f"Request failed: {e}"}

    try:
        data = res.json()
    except Exception:
        data = {"raw": res.text}

    if res.status_code >= 400:
        detail = data.get("detail") if isinstance(data, dict) else str(data)
        return {
            "ok": False,
            "status_code": res.status_code,
            "error": f"HTTP {res.status_code}: {detail}",
            "data": data,
        }
    return {"ok": True, "status_code": res.status_code, "data": data}


def cron_list_jobs(base_url: str = "") -> dict[str, Any]:
    """List all scheduled cron jobs."""
    result = _http_request(
        "GET",
        "/api/crons/cron/jobs",
        base_url=base_url,
    )
    if not result.get("ok"):
        return result
    jobs = result.get("data")
    if not isinstance(jobs, list):
        jobs = []
    return {"ok": True, "count": len(jobs), "jobs": jobs}


def cron_get_job(job_id: str, base_url: str = "") -> dict[str, Any]:
    """Get one scheduled cron job by ID."""
    if not (job_id or "").strip():
        return {"ok": False, "error": "job_id is required"}
    return _http_request(
        "GET",
        f"/api/crons/cron/jobs/{job_id}",
        base_url=base_url,
    )


def cron_create_job(
    name: str,
    cron: str,
    task_type: str = "agent",
    prompt: str = "",
    text: str = "",
    channel: str = DEFAULT_CHANNEL,
    target_user_id: str = "main",
    target_session_id: str = "main",
    timezone: str = "UTC",
    mode: str = "final",
    enabled: bool = True,
    base_url: str = "",
) -> dict[str, Any]:
    """Create a scheduled cron job (agent or text task)."""
    n = (name or "").strip()
    c = (cron or "").strip()
    t = (task_type or "").strip().lower()
    if not n:
        return {"ok": False, "error": "name is required"}
    if not c:
        return {"ok": False, "error": "cron is required"}
    if t not in {"agent", "text"}:
        return {"ok": False, "error": "task_type must be 'agent' or 'text'"}
    if mode not in {"stream", "final"}:
        return {"ok": False, "error": "mode must be 'stream' or 'final'"}

    dispatch = {
        "type": "channel",
        "channel": (channel or DEFAULT_CHANNEL).strip() or DEFAULT_CHANNEL,
        "target": {
            "user_id": (target_user_id or "").strip() or "main",
            "session_id": (target_session_id or "").strip() or "main",
        },
        "mode": mode,
        "meta": {},
    }
    payload: dict[str, Any] = {
        "id": "",
        "name": n,
        "enabled": bool(enabled),
        "schedule": {
            "type": "cron",
            "cron": c,
            "timezone": (timezone or "UTC").strip() or "UTC",
        },
        "task_type": t,
        "dispatch": dispatch,
        "runtime": {
            "max_concurrency": 1,
            "timeout_seconds": 120,
            "misfire_grace_seconds": 60,
        },
        "meta": {},
    }

    if t == "text":
        body = (text or prompt or "").strip()
        if not body:
            return {"ok": False, "error": "text task requires text (or prompt)"}
        payload["text"] = body
    else:
        body = (prompt or text or "").strip()
        if not body:
            return {"ok": False, "error": "agent task requires prompt"}
        payload["request"] = {
            "input": [
                {
                    "role": "user",
                    "type": "message",
                    "content": [{"type": "text", "text": body}],
                },
            ],
            "session_id": dispatch["target"]["session_id"],
            "user_id": dispatch["target"]["user_id"],
            "channel": dispatch["channel"],
        }

    return _http_request(
        "POST",
        "/api/crons/cron/jobs",
        base_url=base_url,
        payload=payload,
    )


def cron_delete_job(job_id: str, base_url: str = "") -> dict[str, Any]:
    """Delete one scheduled cron job by ID."""
    if not (job_id or "").strip():
        return {"ok": False, "error": "job_id is required"}
    return _http_request(
        "DELETE",
        f"/api/crons/cron/jobs/{job_id}",
        base_url=base_url,
    )


def cron_pause_job(job_id: str, base_url: str = "") -> dict[str, Any]:
    """Pause one scheduled cron job by ID."""
    if not (job_id or "").strip():
        return {"ok": False, "error": "job_id is required"}
    return _http_request(
        "POST",
        f"/api/crons/cron/jobs/{job_id}/pause",
        base_url=base_url,
    )


def cron_resume_job(job_id: str, base_url: str = "") -> dict[str, Any]:
    """Resume one paused cron job by ID."""
    if not (job_id or "").strip():
        return {"ok": False, "error": "job_id is required"}
    return _http_request(
        "POST",
        f"/api/crons/cron/jobs/{job_id}/resume",
        base_url=base_url,
    )


def cron_run_job(job_id: str, base_url: str = "") -> dict[str, Any]:
    """Run one scheduled cron job immediately by ID."""
    if not (job_id or "").strip():
        return {"ok": False, "error": "job_id is required"}
    return _http_request(
        "POST",
        f"/api/crons/cron/jobs/{job_id}/run",
        base_url=base_url,
    )

__all__ = [
    "cron_list_jobs",
    "cron_get_job",
    "cron_create_job",
    "cron_delete_job",
    "cron_pause_job",
    "cron_resume_job",
    "cron_run_job",
]
