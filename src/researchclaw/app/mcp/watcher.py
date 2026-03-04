"""MCP config watcher."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class MCPWatcher:
    """Polling watcher placeholder for MCP config file changes."""

    def __init__(self, interval_seconds: int = 5):
        self.interval_seconds = interval_seconds
        self._task: asyncio.Task | None = None

    async def start(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        while True:
            await asyncio.sleep(self.interval_seconds)
            logger.debug("MCP watcher heartbeat")
