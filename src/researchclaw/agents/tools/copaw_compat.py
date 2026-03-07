"""Compatibility aliases for CoPaw/OpenClaw tool names."""

from __future__ import annotations

from typing import Optional

from .send_file import send_file
from .shell import run_shell


def execute_shell_command(
    command: str,
    timeout: int = 60,
    cwd: Optional[str] = None,
) -> str:
    """CoPaw-compatible alias for shell execution."""
    result = run_shell(command=command, timeout=timeout, cwd=cwd)
    returncode = int(result.get("returncode", -1))
    stdout = str(result.get("stdout", "") or "")
    stderr = str(result.get("stderr", "") or "")

    if returncode == 0:
        return stdout or "Command executed successfully (no output)."

    parts = [f"Command failed with exit code {returncode}."]
    if stdout:
        parts.append(f"\n[stdout]\n{stdout}")
    if stderr:
        parts.append(f"\n[stderr]\n{stderr}")
    return "".join(parts)


def send_file_to_user(file_path: str):
    """CoPaw-compatible alias for sending files to the user."""
    return send_file(file_path=file_path)
