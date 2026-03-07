"""Built-in tools for ResearchClaw.

Includes all core tools (file I/O, shell, browser, search) plus
research-specific tools (ArXiv, Semantic Scholar, BibTeX, etc.).
"""

from .file_io import (
    read_file,
    write_file,
    edit_file,
    append_file,
)
from .file_search import (
    grep_search,
    glob_search,
)
from .shell import run_shell
from .send_file import send_file
from .browser_control import browse_url, browser_use
from .browser_snapshot import build_role_snapshot_from_aria
from .desktop_screenshot import desktop_screenshot
from .memory_search import memory_search
from .get_current_time import get_current_time
from .skill_tools import skills_list, skills_read_file
from .copaw_compat import execute_shell_command, send_file_to_user

__all__ = [
    # File I/O
    "read_file",
    "write_file",
    "edit_file",
    "append_file",
    # File search
    "grep_search",
    "glob_search",
    # Shell
    "run_shell",
    "execute_shell_command",
    # Browser
    "browse_url",
    "browser_use",
    "build_role_snapshot_from_aria",
    "desktop_screenshot",
    # Memory
    "memory_search",
    # Utilities
    "send_file",
    "send_file_to_user",
    "get_current_time",
    # Skills
    "skills_list",
    "skills_read_file",
]
