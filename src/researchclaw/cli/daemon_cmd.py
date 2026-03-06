"""CLI daemon subcommands: status, restart, reload-config, version, logs."""

from __future__ import annotations

import asyncio
from pathlib import Path

import click

from ..app.runner.daemon_commands import (
    DaemonContext,
    run_daemon_logs,
    run_daemon_reload_config,
    run_daemon_restart,
    run_daemon_status,
    run_daemon_version,
)
from ..constant import WORKING_DIR


def _context() -> DaemonContext:
    return DaemonContext(
        working_dir=Path(WORKING_DIR),
        memory_manager=None,
        restart_callback=None,
    )


@click.group("daemon")
def daemon_group() -> None:
    """Daemon commands: status, restart, reload-config, version, logs."""


@daemon_group.command("status")
def status_cmd() -> None:
    """Show daemon status."""
    click.echo(run_daemon_status(_context()))


@daemon_group.command("restart")
def restart_cmd() -> None:
    """Print restart instructions (CLI has no running app callback)."""
    click.echo(asyncio.run(run_daemon_restart(_context())))


@daemon_group.command("reload-config")
def reload_config_cmd() -> None:
    """Reload configuration from disk."""
    click.echo(run_daemon_reload_config(_context()))


@daemon_group.command("version")
def version_cmd() -> None:
    """Show version and runtime paths."""
    click.echo(run_daemon_version(_context()))


@daemon_group.command("logs")
@click.option(
    "-n",
    "--lines",
    default=100,
    type=int,
    help="Number of last lines to show (default 100).",
)
def logs_cmd(lines: int) -> None:
    """Tail log file from WORKING_DIR."""
    click.echo(run_daemon_logs(_context(), lines=max(1, min(lines, 2000))))
