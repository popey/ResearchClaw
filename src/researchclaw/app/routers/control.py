"""Control-plane routes for 24x7 standby status and runtime management."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from researchclaw.constant import WORKING_DIR

router = APIRouter()


async def _get_control_cron_jobs(cron: Any) -> list[Any]:
    """Return cron jobs for control page (prefer registered/simple jobs)."""
    if cron is None:
        return []

    # Prefer persistent cron jobs.
    if hasattr(cron, "list_jobs"):
        try:
            return await cron.list_jobs()
        except Exception:
            pass

    # Backward-compatible path for built-in interval jobs.
    if hasattr(cron, "list_registered_jobs"):
        try:
            return cron.list_registered_jobs()
        except Exception:
            pass

    return []


async def _get_cron_runtime_stats(cron: Any) -> dict[str, Any]:
    """Best-effort cron runtime stats for observability."""
    if cron is None:
        return {
            "started": False,
            "scheduler_active": False,
            "registered_jobs_total": 0,
            "registered_jobs_enabled": 0,
            "persistent_jobs_total": 0,
            "persistent_jobs_enabled": 0,
            "states_tracked": 0,
            "running_jobs": 0,
            "errored_jobs": 0,
        }
    if hasattr(cron, "get_runtime_stats"):
        try:
            stats = await cron.get_runtime_stats()
            if isinstance(stats, dict):
                return stats
        except Exception:
            pass

    jobs = await _get_control_cron_jobs(cron)
    total = len(jobs)
    enabled = sum(
        1 for job in jobs if isinstance(job, dict) and job.get("enabled", True)
    )
    return {
        "started": True,
        "scheduler_active": False,
        "registered_jobs_total": total,
        "registered_jobs_enabled": enabled,
        "persistent_jobs_total": total,
        "persistent_jobs_enabled": enabled,
        "states_tracked": 0,
        "running_jobs": 0,
        "errored_jobs": 0,
    }


def _get_runner_runtime_stats(runner: Any) -> dict[str, Any]:
    """Best-effort runner/session observability snapshot."""
    if runner is None:
        return {
            "running": False,
            "session_count": 0,
            "model_provider": "",
            "model_name": "",
        }
    session_count = 0
    try:
        if hasattr(runner, "session_manager"):
            session_count = len(runner.session_manager.list_sessions())
    except Exception:
        session_count = 0

    model_cfg = {}
    try:
        runner_impl = getattr(runner, "runner", None)
        if runner_impl is not None:
            model_cfg = getattr(runner_impl, "_last_model_config", {}) or {}
    except Exception:
        model_cfg = {}

    return {
        "running": bool(getattr(runner, "is_running", False)),
        "session_count": session_count,
        "model_provider": str(model_cfg.get("provider", "") or ""),
        "model_name": str(model_cfg.get("model_name", "") or ""),
    }


def _get_channel_runtime_stats(channels: Any) -> dict[str, Any]:
    """Best-effort channel runtime stats."""
    if channels is None:
        return {
            "registered_channels": 0,
            "queued_messages": 0,
            "pending_messages": 0,
            "in_progress_keys": 0,
            "consumer_workers": {"total": 0, "alive": 0},
            "channels": [],
        }
    if hasattr(channels, "get_runtime_stats"):
        try:
            stats = channels.get_runtime_stats()
            if isinstance(stats, dict):
                return stats
        except Exception:
            pass
    listed = []
    try:
        listed = channels.list_channels()
    except Exception:
        listed = []
    return {
        "registered_channels": len(listed),
        "queued_messages": 0,
        "pending_messages": 0,
        "in_progress_keys": 0,
        "consumer_workers": {"total": 0, "alive": 0},
        "channels": listed,
    }


async def _get_automation_stats(req: Request) -> dict[str, Any]:
    store = getattr(req.app.state, "automation_store", None)
    if store is None or not hasattr(store, "stats"):
        return {"total": 0, "queued": 0, "running": 0, "succeeded": 0, "failed": 0}
    try:
        stats = await store.stats()
        if isinstance(stats, dict):
            return stats
    except Exception:
        pass
    return {"total": 0, "queued": 0, "running": 0, "succeeded": 0, "failed": 0}


@router.get("/status")
async def runtime_status(req: Request):
    started_at = getattr(req.app.state, "started_at", None)
    uptime_seconds = int(time.time() - started_at) if started_at else 0

    runner = getattr(req.app.state, "runner", None)
    cron = getattr(req.app.state, "cron", None)
    channels = getattr(req.app.state, "channel_manager", None)
    mcp = getattr(req.app.state, "mcp_manager", None)
    cron_jobs = await _get_control_cron_jobs(cron)
    cron_stats = await _get_cron_runtime_stats(cron)
    channel_stats = _get_channel_runtime_stats(channels)
    runner_stats = _get_runner_runtime_stats(runner)
    automation_stats = await _get_automation_stats(req)

    return {
        "service": "ResearchClaw",
        "mode": "24x7-standby",
        "uptime_seconds": uptime_seconds,
        "runner_running": runner_stats["running"],
        "cron_jobs": cron_jobs,
        "channels": channel_stats.get("channels", []),
        "mcp_clients": mcp.list_clients() if mcp else [],
        "runtime": {
            "runner": runner_stats,
            "channels": channel_stats,
            "cron": cron_stats,
            "automation": automation_stats,
        },
    }


@router.get("/cron-jobs")
async def list_cron_jobs(req: Request):
    cron = getattr(req.app.state, "cron", None)
    return await _get_control_cron_jobs(cron)


@router.get("/channels")
async def list_channels(req: Request):
    channels = getattr(req.app.state, "channel_manager", None)
    if not channels:
        return []
    return channels.list_channels()


@router.get("/channels/runtime")
async def channels_runtime(req: Request):
    """Detailed runtime stats for channel workers and queues."""
    channels = getattr(req.app.state, "channel_manager", None)
    return _get_channel_runtime_stats(channels)


@router.get("/sessions")
async def list_sessions(req: Request):
    runner = getattr(req.app.state, "runner", None)
    if not runner or not hasattr(runner, "session_manager"):
        return []
    return runner.session_manager.list_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, req: Request):
    runner = getattr(req.app.state, "runner", None)
    if not runner or not hasattr(runner, "session_manager"):
        raise HTTPException(
            status_code=404,
            detail="Session manager not available",
        )

    session = runner.session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found",
        )
    return session.to_dict()


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, req: Request):
    runner = getattr(req.app.state, "runner", None)
    if not runner or not hasattr(runner, "session_manager"):
        raise HTTPException(
            status_code=404,
            detail="Session manager not available",
        )

    session = runner.session_manager.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found",
        )

    runner.session_manager.delete_session(session_id)

    # Also clean up associated memory messages
    memory_deleted = 0
    if hasattr(runner, "runner") and runner.runner.agent is not None:
        agent = runner.runner.agent
        if hasattr(agent, "memory") and hasattr(
            agent.memory,
            "delete_session_messages",
        ):
            memory_deleted = agent.memory.delete_session_messages(session_id)

    return {
        "deleted": True,
        "session_id": session_id,
        "memory_messages_deleted": memory_deleted,
    }


@router.post("/cron-jobs/{job_name}/enable")
async def enable_cron_job(job_name: str, req: Request):
    cron = getattr(req.app.state, "cron", None)
    if not cron:
        raise HTTPException(
            status_code=500,
            detail="Cron manager not available",
        )
    if hasattr(cron, "enable_job_by_name"):
        cron.enable_job_by_name(job_name)
    elif hasattr(cron, "enable_job"):
        cron.enable_job(job_name)
    else:
        raise HTTPException(
            status_code=500,
            detail="Cron manager does not support enable operation",
        )
    return {"enabled": True, "job": job_name}


@router.post("/cron-jobs/{job_name}/disable")
async def disable_cron_job(job_name: str, req: Request):
    cron = getattr(req.app.state, "cron", None)
    if not cron:
        raise HTTPException(
            status_code=500,
            detail="Cron manager not available",
        )
    if hasattr(cron, "disable_job_by_name"):
        cron.disable_job_by_name(job_name)
    elif hasattr(cron, "disable_job"):
        cron.disable_job(job_name)
    else:
        raise HTTPException(
            status_code=500,
            detail="Cron manager does not support disable operation",
        )
    return {"enabled": False, "job": job_name}


@router.get("/heartbeat")
async def heartbeat_status():
    hb_file = Path(WORKING_DIR) / "heartbeat.json"
    if not hb_file.exists():
        return {"enabled": True, "last_heartbeat": None, "healthy": False}

    try:
        data = json.loads(hb_file.read_text(encoding="utf-8"))
    except Exception:
        return {"enabled": True, "last_heartbeat": None, "healthy": False}

    ts = float(data.get("timestamp", 0))
    age = int(time.time() - ts) if ts else None
    return {
        "enabled": True,
        "last_heartbeat": ts,
        "age_seconds": age,
        "healthy": age is not None and age <= 2 * 3600,
    }


@router.get("/automation/runs")
async def automation_runs(req: Request, limit: int = 50):
    """Recent automation trigger runs."""
    store = getattr(req.app.state, "automation_store", None)
    if store is None or not hasattr(store, "list"):
        return {"runs": []}
    return {"runs": await store.list(limit=limit)}
