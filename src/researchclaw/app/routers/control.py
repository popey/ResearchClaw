"""Control-plane routes for 24x7 standby status and runtime management."""

from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from researchclaw.config import load_config, save_config
from researchclaw.constant import CUSTOM_CHANNELS_DIR, WORKING_DIR
from researchclaw.app.gateway.health import (
    build_control_status_payload,
    empty_usage_stats,
    get_automation_runtime_stats,
    get_channel_runtime_stats,
    get_control_cron_jobs,
    get_cron_runtime_stats,
    get_heartbeat_runtime_stats,
    get_runner_runtime_stats,
    get_skills_runtime_stats,
)

router = APIRouter()

CUSTOM_CHANNEL_TEMPLATE = '''# -*- coding: utf-8 -*-
"""Custom channel: {key}. Edit and implement required methods."""
from __future__ import annotations

from typing import Any

from researchclaw.app.channels.base import BaseChannel
from researchclaw.app.channels.schema import ChannelType


class CustomChannel(BaseChannel):
    channel: ChannelType = "{key}"

    def __init__(self, process, enabled=True, bot_prefix="", on_reply_sent=None, show_tool_details=True, **kwargs):
        super().__init__(process, on_reply_sent=on_reply_sent, show_tool_details=show_tool_details)
        self.enabled = enabled
        self.bot_prefix = bot_prefix or ""

    @classmethod
    def from_config(cls, process, config, on_reply_sent=None, show_tool_details=True):
        return cls(
            process=process,
            enabled=getattr(config, "enabled", True),
            bot_prefix=getattr(config, "bot_prefix", ""),
            on_reply_sent=on_reply_sent,
            show_tool_details=show_tool_details,
        )

    @classmethod
    def from_env(cls, process, on_reply_sent=None):
        return cls(process=process, on_reply_sent=on_reply_sent)

    def build_agent_request_from_native(self, native_payload: Any):
        payload = native_payload if isinstance(native_payload, dict) else {{}}
        channel_id = payload.get("channel_id") or self.channel
        sender_id = payload.get("sender_id") or ""
        meta = payload.get("meta") or {{}}
        session_id = self.resolve_session_id(sender_id, meta)
        text = payload.get("text", "")
        from agentscope_runtime.engine.schemas.agent_schemas import TextContent, ContentType
        content_parts = [TextContent(type=ContentType.TEXT, text=text)]
        request = self.build_agent_request_from_user_content(
            channel_id=channel_id, sender_id=sender_id, session_id=session_id,
            content_parts=content_parts, channel_meta=meta,
        )
        request.channel_meta = meta
        return request

    async def start(self):
        pass

    async def stop(self):
        pass

    async def send(self, to_handle: str, text: str, meta=None):
        pass
'''


class ConfigApplyRequest(BaseModel):
    """Config apply payload."""

    patch: dict[str, Any] = Field(default_factory=dict)
    replace: bool = False


class BindingsUpdateRequest(BaseModel):
    bindings: list[dict[str, Any]] = Field(default_factory=list)


class ChannelAccountsUpdateRequest(BaseModel):
    channel_accounts: dict[str, dict[str, dict[str, Any]]] = Field(
        default_factory=dict,
    )


class ChannelAccountUpsertRequest(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)


class ChannelInstallRequest(BaseModel):
    key: str
    path: str | None = None
    url: str | None = None
    overwrite: bool = False


class SessionDeleteTarget(BaseModel):
    session_id: str
    agent_id: str | None = None


class SessionBatchDeleteRequest(BaseModel):
    sessions: list[SessionDeleteTarget] = Field(default_factory=list)


def _load_mutable_config() -> dict[str, Any]:
    cfg = load_config()
    return cfg if isinstance(cfg, dict) else {}


def _empty_usage_stats() -> dict[str, Any]:
    return empty_usage_stats()


def _tail_log_file(path: Path, lines: int = 200) -> str:
    path = Path(path)
    if not path.exists() or not path.is_file():
        return ""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            content = f.readlines()
        return "".join(content[-max(1, min(lines, 2000)) :])
    except Exception:
        return ""


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in patch.items():
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(value, dict)
        ):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _resolve_agent_id(agent_id: str | None) -> str:
    return (agent_id or "main").strip() or "main"


def _get_session_record(
    runner: Any,
    *,
    session_id: str,
    agent_id: str,
) -> Any:
    if hasattr(runner, "get_session"):
        return runner.get_session(agent_id=agent_id, session_id=session_id)
    if hasattr(runner, "session_manager"):
        return runner.session_manager.get_session(session_id)
    return None


def _delete_session_with_runner(
    runner: Any,
    *,
    session_id: str,
    agent_id: str,
) -> dict[str, Any]:
    session = _get_session_record(
        runner,
        session_id=session_id,
        agent_id=agent_id,
    )
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found in agent '{agent_id}'",
        )

    if hasattr(runner, "delete_session"):
        runner.delete_session(agent_id=agent_id, session_id=session_id)
    else:
        runner.session_manager.delete_session(session_id)

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
        "agent_id": agent_id,
        "memory_messages_deleted": memory_deleted,
    }


async def _refresh_runtime(req: Request) -> None:
    cfg_watcher = getattr(req.app.state, "config_watcher", None)
    if cfg_watcher is not None and hasattr(cfg_watcher, "apply_now"):
        await cfg_watcher.apply_now()

    runner = getattr(req.app.state, "runner", None)
    if runner is not None and hasattr(runner, "reload_from_config"):
        await runner.reload_from_config()


def _list_custom_channel_entries() -> list[dict[str, Any]]:
    custom_dir = Path(CUSTOM_CHANNELS_DIR)
    if not custom_dir.exists():
        return []
    out: list[dict[str, Any]] = []
    for item in sorted(custom_dir.iterdir()):
        if item.is_file() and item.suffix == ".py" and item.stem != "__init__":
            out.append(
                {
                    "key": item.stem,
                    "kind": "file",
                    "path": str(item),
                },
            )
            continue
        if item.is_dir() and (item / "__init__.py").exists():
            out.append(
                {
                    "key": item.name,
                    "kind": "package",
                    "path": str(item),
                },
            )
    return out


def _sanitize_channel_key(raw: str) -> str:
    key = str(raw or "").strip()
    if not key or not key.isidentifier():
        raise HTTPException(
            status_code=400,
            detail=f"Invalid channel key: '{raw}'. Use a valid Python identifier.",
        )
    return key


def _save_and_update_channel_catalog(
    config: dict[str, Any],
    *,
    key: str,
    remove: bool = False,
) -> None:
    channels = config.get("channels")
    if not isinstance(channels, dict):
        channels = {}
        config["channels"] = channels

    available = channels.get("available")
    if not isinstance(available, list):
        available = [
            k
            for k, v in channels.items()
            if k != "available" and isinstance(v, dict) and v.get("enabled")
        ]

    if remove:
        channels.pop(key, None)
        available = [str(v) for v in available if str(v) != key]
    else:
        channels.setdefault(key, {"enabled": True, "bot_prefix": "[BOT] "})
        if key not in available:
            available.append(key)

    channels["available"] = available


async def _get_control_cron_jobs(cron: Any) -> list[Any]:
    return await get_control_cron_jobs(cron)


async def _get_cron_runtime_stats(cron: Any) -> dict[str, Any]:
    return await get_cron_runtime_stats(cron)


def _get_runner_runtime_stats(runner: Any) -> dict[str, Any]:
    return get_runner_runtime_stats(runner)


def _get_skills_runtime_stats() -> dict[str, Any]:
    return get_skills_runtime_stats()


def _get_heartbeat_runtime_stats() -> dict[str, Any]:
    return get_heartbeat_runtime_stats()


def _get_channel_runtime_stats(channels: Any) -> dict[str, Any]:
    return get_channel_runtime_stats(channels)


async def _get_automation_stats(req: Request) -> dict[str, Any]:
    store = getattr(req.app.state, "automation_store", None)
    return await get_automation_runtime_stats(store)


@router.get("/status")
async def runtime_status(req: Request):
    return await build_control_status_payload(req.app)


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


@router.get("/usage")
async def usage_stats(req: Request, agent_id: str | None = None):
    """Model usage + fallback observability."""
    runner = getattr(req.app.state, "runner", None)
    if runner is None:
        return _empty_usage_stats()
    if hasattr(runner, "list_usage_stats"):
        return runner.list_usage_stats(agent_id=agent_id)
    if hasattr(runner, "get_usage_stats"):
        return runner.get_usage_stats()
    return _empty_usage_stats()


@router.get("/channels/catalog")
async def channels_catalog():
    """List builtin/custom channel catalog entries."""
    from researchclaw.app.channels.registry import BUILTIN_CHANNEL_KEYS

    custom = _list_custom_channel_entries()
    custom_keys = {item["key"] for item in custom}
    out: list[dict[str, Any]] = []
    for key in sorted(BUILTIN_CHANNEL_KEYS):
        out.append(
            {
                "key": key,
                "builtin": True,
                "installed": True,
                "kind": "builtin",
                "path": "",
            },
        )
    for item in custom:
        out.append(
            {
                "key": item["key"],
                "builtin": False,
                "installed": True,
                "kind": item.get("kind", "file"),
                "path": item.get("path", ""),
            },
        )
    return {
        "channels": out,
        "custom_keys": sorted(custom_keys),
    }


@router.get("/channels/custom")
async def list_custom_channels():
    """List custom channel plugins from custom_channels/."""
    return {"channels": _list_custom_channel_entries()}


@router.post("/channels/custom/install")
async def install_custom_channel(req: Request, payload: ChannelInstallRequest):
    """Install a custom channel plugin from path/url or template."""
    from researchclaw.app.channels.registry import BUILTIN_CHANNEL_KEYS

    key = _sanitize_channel_key(payload.key)
    if key in BUILTIN_CHANNEL_KEYS:
        raise HTTPException(
            status_code=409,
            detail=f"'{key}' is a built-in channel and cannot be installed as custom.",
        )

    custom_dir = Path(CUSTOM_CHANNELS_DIR)
    custom_dir.mkdir(parents=True, exist_ok=True)
    dest_file = custom_dir / f"{key}.py"
    dest_dir = custom_dir / key
    exists = dest_file.exists() or dest_dir.exists()
    if exists and not payload.overwrite:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Custom channel '{key}' already exists. "
                "Set overwrite=true to replace it."
            ),
        )

    if payload.path and payload.url:
        raise HTTPException(
            status_code=400,
            detail="Specify either path or url, not both.",
        )

    if payload.path:
        src = Path(payload.path).expanduser().resolve()
        if not src.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Path not found: {src}",
            )
        if dest_file.exists():
            dest_file.unlink()
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        if src.is_file():
            shutil.copy2(src, dest_file)
        elif src.is_dir():
            shutil.copytree(src, dest_dir)
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported source path type",
            )
    elif payload.url:
        try:
            with urllib.request.urlopen(
                payload.url,
                timeout=15,
            ) as resp:  # nosec B310
                body = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to download custom channel: {e}",
            ) from e
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_file.write_text(body, encoding="utf-8")
    else:
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        dest_file.write_text(
            CUSTOM_CHANNEL_TEMPLATE.format(key=key),
            encoding="utf-8",
        )

    config = _load_mutable_config()
    _save_and_update_channel_catalog(config, key=key, remove=False)
    save_config(config)
    await _refresh_runtime(req)

    return {
        "installed": True,
        "key": key,
        "path": str(dest_dir if dest_dir.exists() else dest_file),
    }


@router.delete("/channels/custom/{key}")
async def remove_custom_channel(req: Request, key: str):
    """Remove a custom channel plugin and config references."""
    from researchclaw.app.channels.registry import BUILTIN_CHANNEL_KEYS

    normalized = _sanitize_channel_key(key)
    if normalized in BUILTIN_CHANNEL_KEYS:
        raise HTTPException(
            status_code=409,
            detail=f"'{normalized}' is a built-in channel and cannot be removed.",
        )

    custom_dir = Path(CUSTOM_CHANNELS_DIR)
    dest_file = custom_dir / f"{normalized}.py"
    dest_dir = custom_dir / normalized
    if not dest_file.exists() and not dest_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Custom channel '{normalized}' not found.",
        )

    if dest_file.exists():
        dest_file.unlink()
    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    config = _load_mutable_config()
    _save_and_update_channel_catalog(config, key=normalized, remove=True)
    extra = config.get("extra_channels")
    if isinstance(extra, dict):
        extra.pop(normalized, None)
    accounts = config.get("channel_accounts")
    if isinstance(accounts, dict):
        accounts.pop(normalized, None)
    save_config(config)
    await _refresh_runtime(req)
    return {"removed": True, "key": normalized}


@router.get("/channels/accounts")
async def get_channel_accounts():
    """Get channel account mapping configuration."""
    cfg = _load_mutable_config()
    accounts = cfg.get("channel_accounts")
    if not isinstance(accounts, dict):
        return {"channel_accounts": {}}
    return {"channel_accounts": accounts}


@router.put("/channels/accounts")
async def update_channel_accounts(
    req: Request,
    payload: ChannelAccountsUpdateRequest,
):
    """Replace all channel account mappings."""
    cfg = _load_mutable_config()
    cfg["channel_accounts"] = payload.channel_accounts
    save_config(cfg)
    await _refresh_runtime(req)
    return {"updated": True, "channel_accounts": payload.channel_accounts}


@router.post("/channels/accounts/{channel}/{account_id}")
async def upsert_channel_account(
    channel: str,
    account_id: str,
    req: Request,
    payload: ChannelAccountUpsertRequest,
):
    """Upsert one channel account config."""
    channel_key = _sanitize_channel_key(channel)
    account_key = str(account_id or "").strip()
    if not account_key:
        raise HTTPException(
            status_code=400,
            detail="account_id must be non-empty",
        )

    cfg = load_config()
    if not isinstance(cfg, dict):
        cfg = {}
    accounts = cfg.get("channel_accounts")
    if not isinstance(accounts, dict):
        accounts = {}
        cfg["channel_accounts"] = accounts
    per_channel = accounts.get(channel_key)
    if not isinstance(per_channel, dict):
        per_channel = {}
        accounts[channel_key] = per_channel
    per_channel[account_key] = dict(payload.config or {})
    save_config(cfg)
    await _refresh_runtime(req)
    return {
        "updated": True,
        "channel": channel_key,
        "account_id": account_key,
        "config": per_channel[account_key],
    }


@router.delete("/channels/accounts/{channel}/{account_id}")
async def remove_channel_account(channel: str, account_id: str, req: Request):
    """Remove one channel account config."""
    channel_key = _sanitize_channel_key(channel)
    account_key = str(account_id or "").strip()
    if not account_key:
        raise HTTPException(
            status_code=400,
            detail="account_id must be non-empty",
        )

    cfg = load_config()
    if not isinstance(cfg, dict):
        cfg = {}
    accounts = cfg.get("channel_accounts")
    if not isinstance(accounts, dict):
        raise HTTPException(
            status_code=404,
            detail="No channel account config found",
        )
    per_channel = accounts.get(channel_key)
    if not isinstance(per_channel, dict) or account_key not in per_channel:
        raise HTTPException(
            status_code=404,
            detail=f"Account '{account_key}' not found for channel '{channel_key}'",
        )
    del per_channel[account_key]
    if not per_channel:
        accounts.pop(channel_key, None)
    save_config(cfg)
    await _refresh_runtime(req)
    return {
        "removed": True,
        "channel": channel_key,
        "account_id": account_key,
    }


@router.get("/bindings")
async def get_bindings():
    """List routing bindings used by multi-agent dispatch."""
    cfg = load_config()
    if not isinstance(cfg, dict):
        return {"bindings": []}
    bindings = cfg.get("bindings")
    if not isinstance(bindings, list):
        bindings = cfg.get("agents", {}).get("bindings")
    if not isinstance(bindings, list):
        bindings = []
    return {"bindings": bindings}


@router.put("/bindings")
async def update_bindings(req: Request, payload: BindingsUpdateRequest):
    """Replace routing bindings."""
    cfg = load_config()
    if not isinstance(cfg, dict):
        cfg = {}
    cfg["bindings"] = payload.bindings
    agents = cfg.get("agents")
    if isinstance(agents, dict):
        agents["bindings"] = payload.bindings
    save_config(cfg)
    await _refresh_runtime(req)
    return {"updated": True, "bindings": payload.bindings}


@router.get("/agents")
async def list_agents(req: Request):
    runner = getattr(req.app.state, "runner", None)
    if not runner or not hasattr(runner, "list_agents"):
        return [
            {
                "id": "main",
                "enabled": True,
                "running": bool(getattr(runner, "is_running", False))
                if runner
                else False,
                "default": True,
            },
        ]
    return runner.list_agents()


@router.get("/sessions")
async def list_sessions(req: Request, agent_id: str | None = None):
    runner = getattr(req.app.state, "runner", None)
    if not runner:
        return []
    if hasattr(runner, "list_sessions"):
        return runner.list_sessions(agent_id=agent_id)
    if hasattr(runner, "session_manager"):
        rows = runner.session_manager.list_sessions()
        return [dict(item, agent_id="main") for item in rows]
    return []


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    req: Request,
    agent_id: str | None = None,
):
    runner = getattr(req.app.state, "runner", None)
    if not runner:
        raise HTTPException(
            status_code=404,
            detail="Session manager not available",
        )

    aid = _resolve_agent_id(agent_id)
    session = _get_session_record(runner, session_id=session_id, agent_id=aid)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found in agent '{aid}'",
        )
    data = session.to_dict()
    data["agent_id"] = aid
    return data


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    req: Request,
    agent_id: str | None = None,
):
    runner = getattr(req.app.state, "runner", None)
    if not runner:
        raise HTTPException(
            status_code=404,
            detail="Session manager not available",
        )

    aid = _resolve_agent_id(agent_id)
    return _delete_session_with_runner(
        runner,
        session_id=session_id,
        agent_id=aid,
    )


@router.post("/sessions/batch-delete")
async def batch_delete_sessions(
    request: SessionBatchDeleteRequest,
    req: Request,
):
    runner = getattr(req.app.state, "runner", None)
    if not runner:
        raise HTTPException(
            status_code=404,
            detail="Session manager not available",
        )

    deleted: list[dict[str, Any]] = []
    not_found: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for item in request.sessions:
        session_id = str(item.session_id or "").strip()
        if not session_id:
            continue
        aid = _resolve_agent_id(item.agent_id)
        key = (aid, session_id)
        if key in seen:
            continue
        seen.add(key)
        try:
            deleted.append(
                _delete_session_with_runner(
                    runner,
                    session_id=session_id,
                    agent_id=aid,
                ),
            )
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            not_found.append(
                {
                    "session_id": session_id,
                    "agent_id": aid,
                    "detail": exc.detail,
                },
            )

    return {
        "deleted": deleted,
        "deleted_count": len(deleted),
        "not_found": not_found,
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
    return _get_heartbeat_runtime_stats()


@router.get("/automation/runs")
async def automation_runs(req: Request, limit: int = 50):
    """Recent automation trigger runs."""
    store = getattr(req.app.state, "automation_store", None)
    if store is None or not hasattr(store, "list"):
        return {"runs": []}
    return {"runs": await store.list(limit=limit)}


@router.get("/logs")
async def control_logs(lines: int = 200):
    """Tail service logs for operations UI."""
    path = Path(WORKING_DIR) / "researchclaw.log"
    return {
        "path": str(path),
        "lines": max(1, min(int(lines), 2000)),
        "content": _tail_log_file(path, lines=lines),
    }


@router.post("/reload")
async def reload_runtime(req: Request):
    """Reload runtime components from current config."""
    await _refresh_runtime(req)
    runner = getattr(req.app.state, "runner", None)

    return {
        "reloaded": True,
        "agents": runner.list_agents()
        if runner is not None and hasattr(runner, "list_agents")
        else [],
    }


@router.post("/config/apply")
async def apply_config(req: Request, payload: ConfigApplyRequest):
    """Persist config patch and apply to runtime immediately."""
    current = load_config()
    if not isinstance(current, dict):
        current = {}
    patch = payload.patch or {}
    if not isinstance(patch, dict):
        raise HTTPException(status_code=400, detail="patch must be an object")

    next_cfg = dict(patch) if payload.replace else _deep_merge(current, patch)
    save_config(next_cfg)

    await _refresh_runtime(req)
    runner = getattr(req.app.state, "runner", None)

    return {
        "applied": True,
        "config": next_cfg,
        "agents": runner.list_agents()
        if runner is not None and hasattr(runner, "list_agents")
        else [],
    }
