"""Memory compaction hook – auto-compresses context when it gets too long."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ...constant import MEMORY_COMPACT_RATIO

if TYPE_CHECKING:
    from ..react_agent import ScholarAgent

logger = logging.getLogger(__name__)


class MemoryCompactionHook:
    """Automatically compacts memory when context usage exceeds threshold.

    After each reply, checks whether the conversation length (in messages)
    has exceeded ``MEMORY_COMPACT_RATIO`` × ``max_input_tokens``. If so,
    triggers automatic compaction.
    """

    def __init__(self, agent: ScholarAgent) -> None:
        self.agent = agent

    def post_reply(self, user_message: str, response: str) -> None:
        """Check context usage and compact if needed."""
        message_count = len(self.agent.memory._messages)

        # Simple heuristic: compact when message count is high
        # Each message is roughly 100-500 tokens on average
        estimated_tokens = message_count * 300
        threshold = int(self.agent.max_input_tokens * MEMORY_COMPACT_RATIO)

        if estimated_tokens > threshold:
            logger.info(
                "Auto-compacting memory: ~%d tokens (threshold: %d)",
                estimated_tokens,
                threshold,
            )
            self.agent.memory.compact()
