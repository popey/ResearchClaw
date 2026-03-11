"""Automation trigger API routes."""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..automation import AutomationRunStore
from ...config import load_config

router = APIRouter()


class TriggerDispatch(BaseModel):
    """A channel dispatch target for automation output."""

    channel: str
    user_id: str = "main"
    session_id: str = "main"


class AgentTriggerRequest(BaseModel):
    """Payload for triggering an automated agent run."""

    message: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    user_id: str = "automation"
    deliver: bool = True
    dispatches: List[TriggerDispatch] = Field(default_factory=list)
    fanout_channels: List[str] = Field(default_factory=list)
    run_async: bool = True


def _get_or_create_store(req: Request) -> AutomationRunStore:
    store = getattr(req.app.state, "automation_store", None)
    if store is None:
        store = AutomationRunStore()
        req.app.state.automation_store = store
    return store


def _resolve_token_from_config() -> str:
    cfg = load_config()
    if not isinstance(cfg, dict):
        return ""
    automation_cfg = cfg.get("automation")
    if isinstance(automation_cfg, dict):
        token = str(automation_cfg.get("token", "") or "").strip()
        if token:
            return token
    hooks_cfg = cfg.get("hooks")
    if isinstance(hooks_cfg, dict):
        token = str(hooks_cfg.get("token", "") or "").strip()
        if token:
            return token
    return ""


def _configured_automation_token() -> str:
    env_token = str(
        os.environ.get("RESEARCHCLAW_AUTOMATION_TOKEN", "") or "",
    ).strip()
    if env_token:
        return env_token
    return _resolve_token_from_config()


def _extract_request_token(req: Request) -> str:
    auth = str(req.headers.get("authorization", "") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    alt = str(
        req.headers.get("x-researchclaw-token")
        or req.headers.get("x-researchclaw-automation-token")
        or "",
    ).strip()
    return alt


def _verify_trigger_auth(req: Request) -> None:
    configured = _configured_automation_token()
    if not configured:
        raise HTTPException(
            status_code=503,
            detail=(
                "Automation token is not configured. Set "
                "RESEARCHCLAW_AUTOMATION_TOKEN or config.automation.token."
            ),
        )
    got = _extract_request_token(req)
    if got != configured:
        raise HTTPException(status_code=401, detail="Invalid automation token")


def _normalize_channel_name(name: str) -> str:
    return (name or "").strip().lower()


def _dedupe_dispatches(
    dispatches: List[Dict[str, str]],
) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in dispatches:
        channel = _normalize_channel_name(str(item.get("channel", "")))
        user_id = str(item.get("user_id", "") or "").strip() or "main"
        session_id = str(item.get("session_id", "") or "").strip() or "main"
        if not channel:
            continue
        key = (channel, user_id, session_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {"channel": channel, "user_id": user_id, "session_id": session_id},
        )
    return out


def _expand_dispatches(
    *,
    payload: AgentTriggerRequest,
    req: Request,
    default_session_id: str,
) -> List[Dict[str, str]]:
    dispatches = [
        {
            "channel": d.channel,
            "user_id": d.user_id,
            "session_id": d.session_id,
        }
        for d in payload.dispatches
    ]

    if payload.deliver and payload.fanout_channels:
        channels = [_normalize_channel_name(v) for v in payload.fanout_channels]
        channels = [v for v in channels if v]
        if "*" in channels:
            mgr = getattr(req.app.state, "channel_manager", None)
            available = []
            if mgr is not None and hasattr(mgr, "list_channels"):
                available = [
                    str(item.get("name", "")).strip().lower()
                    for item in mgr.list_channels()
                    if isinstance(item, dict)
                ]
            channels = sorted({v for v in available if v})

        for channel in channels:
            dispatches.append(
                {
                    "channel": channel,
                    "user_id": payload.user_id or "main",
                    "session_id": default_session_id,
                },
            )

    if payload.deliver and not dispatches:
        last = {}
        cfg = load_config()
        if isinstance(cfg, dict):
            last = cfg.get("last_dispatch") or {}
        channel = _normalize_channel_name(str(last.get("channel", "")))
        user_id = str(last.get("user_id", "") or "").strip()
        session_id = str(last.get("session_id", "") or "").strip()
        dispatches.append(
            {
                "channel": channel or "console",
                "user_id": user_id or "main",
                "session_id": session_id or default_session_id,
            },
        )

    return _dedupe_dispatches(dispatches)


async def _run_agent_trigger(
    *,
    req: Request,
    run_id: str,
    payload: AgentTriggerRequest,
    session_id: str,
    dispatches: List[Dict[str, str]],
) -> Dict[str, Any]:
    store = _get_or_create_store(req)
    await store.mark_running(run_id)

    runner = getattr(req.app.state, "runner", None)
    if runner is None:
        await store.mark_failed(
            run_id,
            error="Agent runner is not initialized",
        )
        raise RuntimeError("Agent runner is not initialized")

    response_text = await runner.chat(payload.message, session_id=session_id)

    delivery_results: List[Dict[str, Any]] = []
    if payload.deliver:
        channel_manager = getattr(req.app.state, "channel_manager", None)
        if channel_manager is None:
            delivery_results.append(
                {
                    "ok": False,
                    "error": "Channel manager is not initialized",
                },
            )
        else:
            for target in dispatches:
                result = dict(target)
                try:
                    await channel_manager.send_text(
                        channel=target["channel"],
                        user_id=target["user_id"],
                        session_id=target["session_id"],
                        text=response_text,
                        meta={"source": "automation"},
                    )
                    result["ok"] = True
                except Exception as e:  # channel errors should not abort the run
                    result["ok"] = False
                    result["error"] = str(e)
                delivery_results.append(result)

    return (
        await store.mark_success(
            run_id,
            response=response_text,
            delivery_results=delivery_results,
        )
        or {}
    )


@router.post("/triggers/agent")
async def trigger_agent(payload: AgentTriggerRequest, req: Request):
    """Trigger an agent run from external automation systems."""
    _verify_trigger_auth(req)
    store = _get_or_create_store(req)

    run_id = str(uuid.uuid4())
    session_id = (payload.session_id or f"automation:{run_id}").strip()
    dispatches = _expand_dispatches(
        payload=payload,
        req=req,
        default_session_id=session_id,
    )

    await store.create(
        run_id=run_id,
        message=payload.message,
        session_id=session_id,
        deliver=payload.deliver,
        dispatches=dispatches,
    )

    async def _task() -> None:
        try:
            await _run_agent_trigger(
                req=req,
                run_id=run_id,
                payload=payload,
                session_id=session_id,
                dispatches=dispatches,
            )
        except Exception as e:
            await store.mark_failed(run_id, error=str(e))

    if payload.run_async:
        asyncio.create_task(_task())
        return {
            "id": run_id,
            "status": "queued",
            "session_id": session_id,
            "dispatches": dispatches,
        }

    try:
        run = await _run_agent_trigger(
            req=req,
            run_id=run_id,
            payload=payload,
            session_id=session_id,
            dispatches=dispatches,
        )
        return run
    except Exception as e:
        await store.mark_failed(run_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/triggers/runs")
async def list_trigger_runs(req: Request, limit: int = 50):
    """List recent automation trigger runs."""
    store = _get_or_create_store(req)
    return {"runs": await store.list(limit=limit)}


@router.get("/triggers/runs/{run_id}")
async def get_trigger_run(req: Request, run_id: str):
    """Get one automation trigger run by id."""
    store = _get_or_create_store(req)
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
