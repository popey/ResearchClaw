"""ResearchClaw package initialization."""

from __future__ import annotations

import logging
import os
import time

from .utils.logging import setup_logger

# Fallback before importing env-backed constants.
LOG_LEVEL_ENV = "RESEARCHCLAW_LOG_LEVEL"

_bootstrap_err: Exception | None = None
try:
    from .envs import load_envs_into_environ

    load_envs_into_environ()
except Exception as exc:  # pragma: no cover - defensive bootstrap guard
    _bootstrap_err = exc

_t0 = time.perf_counter()
setup_logger(os.environ.get(LOG_LEVEL_ENV, "info"))
if _bootstrap_err is not None:
    logging.getLogger(__name__).warning(
        "researchclaw: failed to load persisted envs on init: %s",
        _bootstrap_err,
    )
logging.getLogger(__name__).debug(
    "%.3fs package init",
    time.perf_counter() - _t0,
)
