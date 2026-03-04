"""Logging setup for ResearchClaw."""

from __future__ import annotations

import logging
import sys


def setup_logger(level_name: str = "info") -> None:
    """Configure the root ``researchclaw`` logger.

    Parameters
    ----------
    level_name:
        One of ``debug``, ``info``, ``warning``, ``error``, ``critical``.
    """
    level = getattr(logging, level_name.upper(), logging.INFO)
    logger = logging.getLogger("researchclaw")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        fmt = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s – %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(fmt)
        logger.addHandler(handler)
