"""Agent runner – wraps ScholarAgent for async web usage."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from researchclaw.constant import WORKING_DIR

logger = logging.getLogger(__name__)


class AgentRunner:
    """Wraps a ScholarAgent instance for use in the web server context.

    Handles:
    - Agent initialisation with model config
    - Async chat dispatch (runs blocking agent reply in executor)
    - Session state tracking
    """

    def __init__(self):
        self.agent = None
        self._lock = asyncio.Lock()
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running and self.agent is not None

    async def start(self, model_config: dict[str, Any] | None = None):
        """Initialise the ScholarAgent."""
        async with self._lock:
            if self.agent is not None:
                logger.info("Agent already running, skipping start")
                return

            try:
                config = model_config or {}
                from researchclaw.agents import ScholarAgent

                llm_cfg = {
                    "model_type": config.get("provider", "openai_chat"),
                    "model_name": config.get("model_name", "gpt-4o"),
                    "api_key": config.get("api_key", ""),
                }
                if config.get("base_url"):
                    llm_cfg["api_url"] = config.get("base_url")

                self.agent = ScholarAgent(
                    llm_cfg=llm_cfg,
                    working_dir=config.get("working_dir") or WORKING_DIR,
                )
                self._is_running = True
                logger.info("ScholarAgent started successfully")
            except Exception:
                logger.exception("Failed to start ScholarAgent")
                raise

    async def stop(self):
        """Stop the agent."""
        async with self._lock:
            self.agent = None
            self._is_running = False
            logger.info("ScholarAgent stopped")

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
    ) -> str:
        """Send a message to the agent and get a response.

        The agent's ``reply`` method is blocking, so we run it in an executor.
        """
        if not self.agent:
            raise RuntimeError("Agent is not running")

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            self.agent.reply,
            message,
        )

        if hasattr(response, "content"):
            return response.content
        return str(response)

    async def restart(self, model_config: dict[str, Any] | None = None):
        """Restart the agent with a new configuration."""
        await self.stop()
        await self.start(model_config)
