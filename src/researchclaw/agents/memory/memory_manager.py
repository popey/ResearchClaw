"""Memory manager with advanced search capabilities."""

from __future__ import annotations

import logging
from typing import Any

from .research_memory import ResearchMemory

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages memory lifecycle including compaction, search, and notes.

    This is a higher-level wrapper around :class:`ResearchMemory` that
    provides the ``memory_search`` tool and coordinates memory compaction.
    """

    def __init__(self, memory: ResearchMemory) -> None:
        self.memory = memory

    def search(self, query: str, **kwargs: Any) -> list[dict[str, Any]]:
        """Search across all memory stores."""
        return self.memory.search(query, **kwargs)

    def add_research_note(
        self,
        content: str,
        tags: list[str] | None = None,
        title: str = "",
    ) -> str:
        """Add a research note and return confirmation."""
        self.memory.add_note(content, tags=tags, title=title)
        return f"Research note saved: {title or content[:50]}..."

    def track_paper(self, paper_info: dict[str, Any]) -> None:
        """Track a paper mentioned in conversation."""
        self.memory.add_discussed_paper(paper_info)
