"""Workspace routes for key file browsing/editing and relation summaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from researchclaw.config import get_heartbeat_config, get_heartbeat_query_path
from researchclaw.constant import (
    ACTIVE_SKILLS_DIR,
    CHATS_FILE,
    CONFIG_FILE,
    CUSTOMIZED_SKILLS_DIR,
    EXAMPLES_DIR,
    EXPERIMENTS_DIR,
    JOBS_FILE,
    MD_FILES_DIR,
    MEMORY_DIR,
    PAPERS_DIR,
    REFERENCES_DIR,
    WORKING_DIR,
)

router = APIRouter()

_MAX_EDITABLE_FILE_SIZE = 2 * 1024 * 1024  # 2 MB
_MAX_LISTED_FILES_PER_DIR = 300
_MAX_WALK_DEPTH = 6
_TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".py",
    ".sh",
    ".sql",
    ".xml",
    ".csv",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
}


class WorkspaceFileWriteRequest(BaseModel):
    path: str
    content: str


def _working_dir() -> Path:
    return Path(WORKING_DIR).resolve()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_resolve_relative(path_str: str) -> Path:
    rel = Path(path_str or "")
    if rel.is_absolute():
        raise HTTPException(status_code=400, detail="path must be relative")
    target = (_working_dir() / rel).resolve()
    if not str(target).startswith(str(_working_dir())):
        raise HTTPException(status_code=400, detail="path out of working dir")
    return target


def _to_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(_working_dir()).as_posix()
    except Exception:
        return path.name


def _is_likely_text(path: Path) -> bool:
    if path.suffix.lower() in _TEXT_SUFFIXES:
        return True
    if not path.exists() or not path.is_file():
        return False
    try:
        sample = path.read_bytes()[:1024]
    except Exception:
        return False
    return b"\x00" not in sample


def _make_file_item(
    *,
    rel_path: str,
    category: str,
    required: bool = False,
) -> dict[str, Any]:
    path = _safe_resolve_relative(rel_path)
    exists = path.exists()
    is_file = exists and path.is_file()
    size = path.stat().st_size if is_file else 0
    modified = (
        datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        if exists
        else None
    )
    return {
        "path": rel_path,
        "category": category,
        "required": required,
        "exists": exists,
        "editable": (not exists) or (is_file and _is_likely_text(path)),
        "size": size,
        "modified_at": modified,
    }


def _list_text_files_under_dir(base: Path, *, category: str) -> list[dict[str, Any]]:
    if not base.exists() or not base.is_dir():
        return []

    out: list[dict[str, Any]] = []
    count = 0
    for p in sorted(base.rglob("*")):
        if count >= _MAX_LISTED_FILES_PER_DIR:
            break
        if not p.is_file():
            continue
        try:
            rel_depth = len(p.relative_to(base).parts)
        except Exception:
            continue
        if rel_depth > _MAX_WALK_DEPTH:
            continue
        # Skills directories only expose SKILL.md content files.
        if category in {"active_skills", "customized_skills"} and p.name.lower() != "skill.md":
            continue
        rel = _to_rel(p)
        if not rel:
            continue
        if not _is_likely_text(p):
            continue
        out.append(
            _make_file_item(
                rel_path=rel,
                category=category,
                required=False,
            ),
        )
        count += 1
    return out


@router.get("")
async def workspace_info():
    wd = _working_dir()
    return {
        "working_dir": str(wd),
        "exists": wd.exists(),
        "directories": {
            "papers": str(Path(PAPERS_DIR)),
            "references": str(Path(REFERENCES_DIR)),
            "experiments": str(Path(EXPERIMENTS_DIR)),
            "md_files": str(Path(MD_FILES_DIR)),
            "examples": str(Path(EXAMPLES_DIR)),
            "active_skills": str(Path(ACTIVE_SKILLS_DIR)),
            "customized_skills": str(Path(CUSTOMIZED_SKILLS_DIR)),
            "memory": str(Path(MEMORY_DIR)),
        },
        "now": _now_iso(),
    }


@router.get("/profile")
async def profile_md():
    profile_path = _working_dir() / "PROFILE.md"
    if not profile_path.exists():
        return {"exists": False, "content": ""}
    return {
        "exists": True,
        "path": str(profile_path),
        "content": profile_path.read_text(encoding="utf-8"),
    }


@router.get("/files")
async def list_workspace_files():
    """List key editable files and selected directory files in WORKING_DIR."""
    core_rel_paths = [
        CONFIG_FILE,
        "HEARTBEAT.md",
        JOBS_FILE,
        CHATS_FILE,
        "SOUL.md",
        "AGENTS.md",
        "PROFILE.md",
    ]

    hb_query_rel = _to_rel(get_heartbeat_query_path())
    if hb_query_rel not in core_rel_paths:
        core_rel_paths.append(hb_query_rel)

    core_files = [
        _make_file_item(
            rel_path=p,
            category="core",
            required=p in {"SOUL.md", "AGENTS.md"},
        )
        for p in core_rel_paths
    ]

    working = _working_dir()
    dir_entries = [
        (working / "active_skills", "active_skills"),
        (working / "customized_skills", "customized_skills"),
        (working / "memory", "memory"),
    ]

    directory_files: list[dict[str, Any]] = []
    for base, category in dir_entries:
        directory_files.extend(_list_text_files_under_dir(base, category=category))

    all_files = sorted(
        core_files + directory_files,
        key=lambda x: (x.get("category", ""), x.get("path", "")),
    )
    return {
        "working_dir": str(working),
        "files": all_files,
        "count": len(all_files),
        "now": _now_iso(),
    }


@router.get("/file")
async def get_workspace_file(path: str = Query(..., description="Relative file path")):
    """Read one text file content from WORKING_DIR by relative path."""
    fp = _safe_resolve_relative(path)
    if not fp.exists():
        return {
            "exists": False,
            "path": path,
            "content": "",
            "editable": True,
        }
    if not fp.is_file():
        raise HTTPException(status_code=400, detail="path is not a file")
    if fp.stat().st_size > _MAX_EDITABLE_FILE_SIZE:
        raise HTTPException(status_code=413, detail="file too large to edit")
    if not _is_likely_text(fp):
        raise HTTPException(status_code=400, detail="binary file is not editable")
    try:
        content = fp.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = fp.read_text(encoding="utf-8", errors="replace")

    return {
        "exists": True,
        "path": path,
        "abs_path": str(fp),
        "editable": True,
        "size": fp.stat().st_size,
        "modified_at": datetime.fromtimestamp(
            fp.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat(),
        "content": content,
    }


@router.put("/file")
async def save_workspace_file(req: WorkspaceFileWriteRequest):
    """Create or overwrite one text file under WORKING_DIR."""
    fp = _safe_resolve_relative(req.path)
    if fp.exists() and fp.is_dir():
        raise HTTPException(status_code=400, detail="path is a directory")
    if fp.suffix.lower() not in _TEXT_SUFFIXES and fp.exists() and not _is_likely_text(fp):
        raise HTTPException(status_code=400, detail="binary file is not editable")
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(req.content, encoding="utf-8")
    return {
        "saved": True,
        "path": req.path,
        "size": fp.stat().st_size,
        "modified_at": datetime.fromtimestamp(
            fp.stat().st_mtime,
            tz=timezone.utc,
        ).isoformat(),
    }


@router.get("/relations")
async def get_workspace_relations(request: Request):
    """Summarize relationships among chat, skills, cron, and heartbeat."""
    working = _working_dir()
    config_path = working / CONFIG_FILE
    jobs_path = working / JOBS_FILE
    chats_path = working / CHATS_FILE

    config: dict[str, Any] = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            config = {}

    cron_total = 0
    cron_enabled = 0
    if jobs_path.exists():
        try:
            jobs_data = json.loads(jobs_path.read_text(encoding="utf-8"))
            jobs = jobs_data.get("jobs") if isinstance(jobs_data, dict) else []
            if isinstance(jobs, list):
                cron_total = len(jobs)
                cron_enabled = sum(1 for j in jobs if bool((j or {}).get("enabled", True)))
        except Exception:
            pass

    chats_total = 0
    if chats_path.exists():
        try:
            chats_data = json.loads(chats_path.read_text(encoding="utf-8"))
            if isinstance(chats_data, dict):
                if isinstance(chats_data.get("chats"), list):
                    chats_total = len(chats_data.get("chats"))
                elif isinstance(chats_data.get("items"), list):
                    chats_total = len(chats_data.get("items"))
            elif isinstance(chats_data, list):
                chats_total = len(chats_data)
        except Exception:
            pass

    session_total = 0
    runner = getattr(request.app.state, "runner", None)
    if runner and hasattr(runner, "session_manager"):
        try:
            session_total = len(runner.session_manager.list_sessions())
        except Exception:
            session_total = 0

    active_skills: list[str] = []
    try:
        from researchclaw.agents.skills_manager import SkillsManager

        active_skills = SkillsManager().list_active_skills()
    except Exception:
        active_skills = []

    hb = get_heartbeat_config()
    hb_query_rel = _to_rel(get_heartbeat_query_path())
    channels = config.get("channels", {}) if isinstance(config, dict) else {}
    available_channels = channels.get("available", []) if isinstance(channels, dict) else []
    if not isinstance(available_channels, list):
        available_channels = []

    return {
        "chat": {
            "session_total": session_total,
            "chats_file_total": chats_total,
        },
        "skills": {
            "active_count": len(active_skills),
            "active_skills": active_skills,
        },
        "cron": {
            "total": cron_total,
            "enabled": cron_enabled,
            "disabled": max(0, cron_total - cron_enabled),
        },
        "heartbeat": {
            "enabled": bool(getattr(hb, "enabled", False)),
            "every": str(getattr(hb, "every", "30m")),
            "target": str(getattr(hb, "target", "last")),
            "query_file": hb_query_rel,
        },
        "config": {
            "available_channels": [str(x) for x in available_channels],
            "last_dispatch": (config.get("last_dispatch") if isinstance(config, dict) else None),
            "language": config.get("language") if isinstance(config, dict) else None,
        },
        "links": [
            "Skills affect both chat and cron(task_type=agent) tool capabilities.",
            "Cron agent jobs run through the same runner as chat sessions.",
            "Heartbeat reads HEARTBEAT.md and can dispatch to last active channel.",
            "Channel auth/switch, heartbeat settings, and language are persisted in config.json.",
        ],
        "now": _now_iso(),
    }
