"""Agent API routes – chat with ScholarAgent."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from researchclaw.constant import (
    DEFAULT_MAX_INPUT_TOKENS,
    DEFAULT_MAX_ITERS,
    WORKING_DIR,
)

logger = logging.getLogger(__name__)

router = APIRouter()
STREAM_HEARTBEAT_INTERVAL_SECONDS = 10.0


class ChatRequest(BaseModel):
    """Chat message request body."""

    message: str
    session_id: str | None = None
    agent_id: str | None = None
    stream: bool = False


class ChatResponse(BaseModel):
    """Chat message response."""

    response: str
    session_id: str


class AgentsRunningConfig(BaseModel):
    """Runtime agent limits shown in console settings."""

    max_iters: int = DEFAULT_MAX_ITERS
    max_input_length: int = DEFAULT_MAX_INPUT_TOKENS


def _agent_config_path() -> Path:
    return Path(WORKING_DIR) / "config.json"


def _load_agent_config_payload() -> dict[str, Any]:
    config_path = _agent_config_path()
    if not config_path.exists():
        return {}
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_agent_config_payload(payload: dict[str, Any]) -> None:
    config_path = _agent_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _load_running_config() -> AgentsRunningConfig:
    data = _load_agent_config_payload()
    if not data:
        return AgentsRunningConfig()

    return AgentsRunningConfig(
        max_iters=int(data.get("max_iters", DEFAULT_MAX_ITERS)),
        max_input_length=int(
            data.get("max_input_length", DEFAULT_MAX_INPUT_TOKENS),
        ),
    )


def _save_running_config(config: AgentsRunningConfig) -> AgentsRunningConfig:
    payload = _load_agent_config_payload()
    payload.update(config.model_dump())
    _save_agent_config_payload(payload)
    return config


def _get_runner_snapshot(runner: Any) -> dict[str, Any] | None:
    if not runner or not hasattr(runner, "get_status_snapshot"):
        return None
    try:
        snapshot = runner.get_status_snapshot()
    except Exception:
        logger.debug("Failed to load runner status snapshot", exc_info=True)
        return None
    return snapshot if isinstance(snapshot, dict) else None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    """Send a message to ScholarAgent and get a response."""
    runner = getattr(req.app.state, "runner", None)
    if not runner:
        return ChatResponse(
            response="Agent is not running. Please check the server logs.",
            session_id=request.session_id or str(uuid.uuid4()),
        )

    session_id = request.session_id or str(uuid.uuid4())

    try:
        response = await runner.chat(
            message=request.message,
            session_id=session_id,
            agent_id=request.agent_id,
        )
        return ChatResponse(response=response, session_id=session_id)
    except Exception as e:
        logger.exception("Chat error")
        return ChatResponse(
            response=f"Error: {e}",
            session_id=session_id,
        )


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, req: Request):
    """Stream a response from ScholarAgent via SSE.

    Sends events of these types:
    - ``thinking`` — reasoning/thinking tokens (from thinking models)
    - ``content`` — regular content tokens
    - ``skill_call`` — the agent selected a skill for this turn
    - ``tool_call`` — the agent is calling a tool
    - ``tool_result`` — tool execution result
    - ``done`` — final complete response
    - ``error`` — an error occurred
    """
    runner = getattr(req.app.state, "runner", None)
    session_id = request.session_id or str(uuid.uuid4())

    def _sse(payload: dict[str, Any]) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    async def generate():
        if not runner:
            yield _sse({"type": "error", "content": "Agent not running"})
            return

        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        async def forward_events() -> None:
            try:
                async for event in runner.chat_stream(
                    message=request.message,
                    session_id=session_id,
                    agent_id=request.agent_id,
                ):
                    await queue.put(event)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                await queue.put(
                    {
                        "type": "error",
                        "content": str(e),
                        "session_id": session_id,
                    },
                )
            finally:
                await queue.put(None)

        producer = asyncio.create_task(forward_events())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(),
                        timeout=STREAM_HEARTBEAT_INTERVAL_SECONDS,
                    )
                except asyncio.TimeoutError:
                    heartbeat = {
                        "type": "heartbeat",
                        "session_id": session_id,
                    }
                    if request.agent_id:
                        heartbeat["agent_id"] = request.agent_id
                    yield _sse(heartbeat)
                    continue

                if event is None:
                    break

                event["session_id"] = session_id
                if request.agent_id:
                    event["agent_id"] = request.agent_id
                yield _sse(event)
        finally:
            producer.cancel()
            with suppress(asyncio.CancelledError):
                await producer

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/tools")
async def list_tools(req: Request):
    """List available agent tools."""
    runner = getattr(req.app.state, "runner", None)
    if not runner:
        return {"tools": []}
    snapshot = _get_runner_snapshot(runner)
    if snapshot is not None:
        return {"tools": list(snapshot.get("tool_names", []) or [])}
    if not runner.agent:
        return {"tools": []}
    return {"tools": runner.agent.tool_names}


@router.get("/status")
async def agent_status(req: Request):
    """Get agent status."""
    runner = getattr(req.app.state, "runner", None)
    snapshot = _get_runner_snapshot(runner)
    if snapshot is not None:
        return snapshot

    agents = []
    if runner and hasattr(runner, "list_agents"):
        try:
            agents = runner.list_agents()
        except Exception:
            agents = []
    return {
        "running": runner is not None and runner.is_running,
        "agent_name": "Scholar",
        "tool_count": len(runner.agent.tool_names)
        if runner and runner.agent
        else 0,
        "tool_names": list(runner.agent.tool_names)
        if runner and runner.agent
        else [],
        "agents": agents,
    }


@router.get("/running-config", response_model=AgentsRunningConfig)
async def get_running_config():
    """Get persisted runtime configuration for agent limits."""
    return _load_running_config()


@router.put("/running-config", response_model=AgentsRunningConfig)
async def update_running_config(config: AgentsRunningConfig):
    """Persist runtime configuration for agent limits."""
    return _save_running_config(config)
