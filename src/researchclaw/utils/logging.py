"""Logging setup for ResearchClaw."""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

_LOG_MAX_BYTES = 5 * 1024 * 1024
_LOG_BACKUP_COUNT = 3
_LOG_NAMESPACE = "researchclaw"

_LEVEL_MAP = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
    "trace": logging.DEBUG,
}


def setup_logger(level_name: str = "info") -> logging.Logger:
    """Configure the package logger and return it."""
    level = _LEVEL_MAP.get(str(level_name).lower(), logging.INFO)

    # Keep third-party logs quiet by default.
    root = logging.getLogger()
    root.setLevel(logging.WARNING)

    logger = logging.getLogger(_LOG_NAMESPACE)
    logger.setLevel(level)
    logger.propagate = False

    has_stream = any(
        isinstance(h, logging.StreamHandler)
        and not isinstance(h, logging.FileHandler)
        for h in logger.handlers
    )
    if not has_stream:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        handler.setFormatter(
            logging.Formatter(
                "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ),
        )
        logger.addHandler(handler)
    else:
        for h in logger.handlers:
            if isinstance(h, logging.StreamHandler):
                h.setLevel(level)

    return logger


def add_researchclaw_file_handler(log_path: Path) -> None:
    """Attach a rotating file handler to the researchclaw logger."""
    log_path = Path(log_path).expanduser().resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(_LOG_NAMESPACE)
    for handler in logger.handlers:
        base = getattr(handler, "baseFilename", None)
        if base is not None and Path(base).resolve() == log_path:
            return

    try:
        os.chmod(log_path.parent, 0o700)
    except OSError:
        pass

    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        encoding="utf-8",
        maxBytes=_LOG_MAX_BYTES,
        backupCount=_LOG_BACKUP_COUNT,
    )
    file_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ),
    )
    logger.addHandler(file_handler)

    try:
        os.chmod(log_path, 0o600)
    except OSError:
        pass
