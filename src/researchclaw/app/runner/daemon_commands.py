"""Daemon command execution helpers.

Shared by in-chat slash commands and CLI `researchclaw daemon <sub>`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from ...__version__ import __version__
from ...config import load_config

logger = logging.getLogger(__name__)

RestartCallback = Callable[[], Awaitable[None]]


class RestartInProgressError(Exception):
    """Raised when restart is requested while another restart is running."""


DAEMON_SUBCOMMANDS = frozenset(
    {"status", "restart", "reload-config", "version", "logs"},
)
DAEMON_SHORT_ALIASES = {
    "restart": "restart",
    "status": "status",
    "reload-config": "reload-config",
    "reload_config": "reload-config",
    "version": "version",
    "logs": "logs",
}


@dataclass
class DaemonContext:
    """Context for daemon commands."""

    working_dir: Path
    load_config_fn: Callable[[], Any] = load_config
    memory_manager: Optional[Any] = None
    restart_callback: Optional[RestartCallback] = None


def _get_last_lines(path: Path, lines: int = 100, max_bytes: int = 512 * 1024) -> str:
    """Read tail lines from log file with bounded memory."""
    path = Path(path)
    if not path.exists() or not path.is_file():
        return f"(Log file not found: {path})"

    try:
        size = path.stat().st_size
        if size == 0:
            return "(empty)"

        with open(path, "rb") as fh:
            if size <= max_bytes:
                content = fh.read().decode("utf-8", errors="replace")
            else:
                fh.seek(size - max_bytes)
                content = fh.read().decode("utf-8", errors="replace")
                first_nl = content.find("\n")
                content = content[first_nl + 1 :] if first_nl != -1 else ""

        all_lines = content.splitlines()
        return "\n".join(all_lines[-lines:]) if all_lines else "(empty)"
    except OSError as exc:
        return f"(Error reading log: {exc})"


def run_daemon_status(context: DaemonContext) -> str:
    parts = ["**Daemon Status**", ""]
    try:
        cfg = context.load_config_fn()
        parts.append("- Config loaded: yes")
        lang = cfg.get("language") if isinstance(cfg, dict) else None
        if lang:
            parts.append(f"- Language: {lang}")
    except Exception as exc:
        parts.append(f"- Config loaded: no ({exc})")

    parts.append(f"- Working dir: {context.working_dir}")
    parts.append(
        "- Memory manager: running"
        if context.memory_manager is not None
        else "- Memory manager: not attached",
    )
    return "\n".join(parts)


async def run_daemon_restart(context: DaemonContext) -> str:
    if context.restart_callback is not None:
        try:
            await context.restart_callback()
            return (
                "**Restart completed**\n\n"
                "- Services were reloaded in-process."
            )
        except RestartInProgressError:
            return (
                "**Restart skipped**\n\n"
                "- A restart is already in progress."
            )
        except Exception as exc:
            return f"**Restart failed**\n\n- {exc}"

    return (
        "**Restart**\n\n"
        "- No restart callback is attached in this context. "
        "Use `researchclaw app` runtime control or restart the process manually."
    )


def run_daemon_reload_config(context: DaemonContext) -> str:
    try:
        context.load_config_fn()
        return "**Config reloaded**\n\n- load_config() re-invoked successfully."
    except Exception as exc:
        return f"**Reload failed**\n\n- {exc}"


def run_daemon_version(context: DaemonContext) -> str:
    return (
        "**Daemon version**\n\n"
        f"- Version: {__version__}\n"
        f"- Working dir: {context.working_dir}\n"
        f"- Log file: {context.working_dir / 'researchclaw.log'}"
    )


def run_daemon_logs(context: DaemonContext, lines: int = 100) -> str:
    content = _get_last_lines(context.working_dir / "researchclaw.log", lines=lines)
    return f"**Console log (last {lines} lines)**\n\n```\n{content}\n```"


def parse_daemon_query(query: str) -> Optional[tuple[str, list[str]]]:
    if not query or not isinstance(query, str):
        return None
    raw = query.strip()
    if not raw.startswith("/"):
        return None

    rest = raw.lstrip("/").strip()
    if not rest:
        return None

    parts = rest.split()
    first = parts[0].lower() if parts else ""

    if first == "daemon":
        if len(parts) < 2:
            return ("status", [])
        sub = parts[1].lower().replace("_", "-")
        if sub not in DAEMON_SUBCOMMANDS and "reload" in sub:
            sub = "reload-config"
        if sub not in DAEMON_SUBCOMMANDS:
            return None
        return (sub, parts[2:] if len(parts) > 2 else [])

    if first in DAEMON_SHORT_ALIASES:
        return (DAEMON_SHORT_ALIASES[first], parts[1:] if len(parts) > 1 else [])

    return None
