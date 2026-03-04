"""Bootstrap hook – runs on first message to guide the user through setup."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..react_agent import ScholarAgent

logger = logging.getLogger(__name__)


class BootstrapHook:
    """First-run hook that guides the user through research profile setup.

    On the very first message, if no PROFILE.md exists, this hook prepends
    bootstrap guidance to help the user configure their research areas and
    preferences.
    """

    def __init__(self, agent: ScholarAgent) -> None:
        self.agent = agent
        self._bootstrapped = False

    def pre_reply(self, message: str) -> str:
        """Check if bootstrap is needed and inject guidance."""
        if self._bootstrapped:
            return message

        profile_path = Path(self.agent.working_dir) / "PROFILE.md"
        if profile_path.exists():
            self._bootstrapped = True
            return message

        # First run — mark as bootstrapped and let agent guide the user
        self._bootstrapped = True
        logger.info("First run detected — bootstrap guidance will be shown")
        return message

    def should_show_guidance(self) -> bool:
        """Check if we should show first-run guidance."""
        profile_path = Path(self.agent.working_dir) / "PROFILE.md"
        return not profile_path.exists()
