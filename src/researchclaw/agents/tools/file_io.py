"""File I/O tools for reading, writing, editing, and appending files.

Improvements over CoPaw:
- ``append_file`` for incremental writing
- ``create_dirs`` option for automatic parent directory creation
- ``encoding`` parameter on all operations
- Line range with header showing (lines X-Y of N)
- Large file truncation (500 KB)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from ...constant import WORKING_DIR

logger = logging.getLogger(__name__)


def _resolve_file_path(file_path: str) -> str:
    """Resolve file path: absolute as-is, relative from WORKING_DIR."""
    path = Path(file_path)
    if path.is_absolute():
        return str(path)
    return str(Path(WORKING_DIR) / file_path)


def read_file(
    file_path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    encoding: str = "utf-8",
) -> str:
    """Read the contents of a file. Relative paths resolve from WORKING_DIR.

    Use ``start_line``/``end_line`` to read a specific line range (output
    includes line numbers). Omit both to read the full file.

    Parameters
    ----------
    file_path:
        Path to the file to read.
    start_line:
        First line to read (1-based, inclusive).
    end_line:
        Last line to read (1-based, inclusive).
    encoding:
        File encoding (default: utf-8).

    Returns
    -------
    str
        File contents (or the specified line range).
    """
    try:
        file_path = _resolve_file_path(file_path)
        path = Path(file_path)
        if not path.exists():
            return f"Error: File not found: {file_path}"
        if not path.is_file():
            return f"Error: Not a file: {file_path}"

        content = path.read_text(encoding=encoding, errors="replace")

        if start_line is not None or end_line is not None:
            lines = content.splitlines(keepends=True)
            total = len(lines)
            s = max(1, start_line if start_line is not None else 1)
            e = min(total, end_line if end_line is not None else total)

            if s > total:
                return (
                    f"Error: start_line {s} exceeds file length "
                    f"({total} lines) in {file_path}."
                )
            if s > e:
                return (
                    f"Error: start_line ({s}) is greater than "
                    f"end_line ({e}) in {file_path}."
                )

            selected = lines[s - 1 : e]
            content = "".join(selected)
            return f"{file_path}  (lines {s}-{e} of {total})\n{content}"

        # Truncate very large files
        if len(content) > 500_000:
            content = content[:500_000] + "\n... [truncated, file too large]"

        return content
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(
    file_path: str,
    content: str,
    create_dirs: bool = True,
    encoding: str = "utf-8",
) -> str:
    """Create or overwrite a file. Relative paths resolve from WORKING_DIR.

    Parameters
    ----------
    file_path:
        Path to the file to write.
    content:
        Content to write.
    create_dirs:
        Create parent directories if needed.
    encoding:
        File encoding.

    Returns
    -------
    str
        Success or error message.
    """
    if not file_path:
        return "Error: No file_path provided."

    try:
        file_path = _resolve_file_path(file_path)
        path = Path(file_path)
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(content, encoding=encoding)
        return f"Wrote {len(content)} bytes to {file_path}."
    except Exception as e:
        return f"Error writing file: {e}"


def edit_file(
    file_path: str,
    old_string: str,
    new_string: str,
    encoding: str = "utf-8",
) -> str:
    """Find-and-replace text in a file. All occurrences of ``old_string`` are
    replaced with ``new_string``. Relative paths resolve from WORKING_DIR.

    Parameters
    ----------
    file_path:
        Path to the file to edit.
    old_string:
        Exact text to find and replace.
    new_string:
        Replacement text.
    encoding:
        File encoding.

    Returns
    -------
    str
        Success or error message.
    """
    try:
        file_path = _resolve_file_path(file_path)
        path = Path(file_path)
        if not path.exists():
            return f"Error: File not found: {file_path}"

        content = path.read_text(encoding=encoding)

        if old_string not in content:
            return f"Error: The text to replace was not found in {file_path}."

        count = content.count(old_string)
        new_content = content.replace(old_string, new_string)
        path.write_text(new_content, encoding=encoding)

        return f"Successfully replaced text in {file_path} ({count} occurrence(s))."
    except Exception as e:
        return f"Error editing file: {e}"


def append_file(
    file_path: str,
    content: str,
    encoding: str = "utf-8",
) -> str:
    """Append content to the end of a file. Relative paths resolve from
    WORKING_DIR.

    Parameters
    ----------
    file_path:
        Path to the file.
    content:
        Content to append.
    encoding:
        File encoding.

    Returns
    -------
    str
        Success or error message.
    """
    if not file_path:
        return "Error: No file_path provided."

    try:
        file_path = _resolve_file_path(file_path)
        with open(file_path, "a", encoding=encoding) as f:
            f.write(content)
        return f"Appended {len(content)} bytes to {file_path}."
    except Exception as e:
        return f"Error appending to file: {e}"
