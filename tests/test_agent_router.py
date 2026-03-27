from __future__ import annotations

import asyncio
from types import SimpleNamespace

from researchclaw.app.routers import agent as agent_router


def test_agent_status_prefers_runner_snapshot() -> None:
    snapshot = {
        "running": True,
        "agent_name": "lab",
        "tool_count": 3,
        "tool_names": ["search", "read", "write"],
        "agents": [{"id": "lab", "running": True}],
    }
    runner = SimpleNamespace(get_status_snapshot=lambda: snapshot)
    req = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(runner=runner)),
    )

    result = asyncio.run(agent_router.agent_status(req))

    assert result == snapshot


def test_list_tools_prefers_runner_snapshot() -> None:
    runner = SimpleNamespace(
        get_status_snapshot=lambda: {"tool_names": ["search", "read"]},
        agent=None,
    )
    req = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(runner=runner)),
    )

    result = asyncio.run(agent_router.list_tools(req))

    assert result == {"tools": ["search", "read"]}


def test_chat_stream_emits_heartbeat_during_silence(monkeypatch) -> None:
    async def fake_stream(
        message: str,
        session_id: str | None = None,
        agent_id: str | None = None,
    ):
        await asyncio.sleep(0.03)
        yield {"type": "content", "content": "hello"}
        yield {"type": "done", "content": "hello"}

    async def run_stream() -> str:
        runner = SimpleNamespace(chat_stream=fake_stream)
        req = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(runner=runner)),
        )
        request = agent_router.ChatRequest(message="ping", session_id="s1")

        response = await agent_router.chat_stream(request, req)
        chunks: list[str] = []
        async for chunk in response.body_iterator:
            chunks.append(
                chunk.decode("utf-8")
                if isinstance(chunk, bytes)
                else str(chunk)
            )
        return "".join(chunks)

    monkeypatch.setattr(
        agent_router,
        "STREAM_HEARTBEAT_INTERVAL_SECONDS",
        0.01,
    )

    body = asyncio.run(run_stream())

    assert '"type": "heartbeat"' in body
    assert '"type": "content"' in body
    assert '"type": "done"' in body
