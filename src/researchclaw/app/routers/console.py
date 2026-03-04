"""Console SSE streaming routes."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/events")
async def console_events(req: Request):
    """SSE endpoint for real-time console events."""
    push_store = getattr(req.app.state, "push_store", None)

    async def event_stream():
        queue: asyncio.Queue = asyncio.Queue()
        client_id = id(queue)

        if push_store:
            push_store.add_client(client_id, queue)

        try:
            # Send initial heartbeat
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                except asyncio.CancelledError:
                    break
        finally:
            if push_store:
                push_store.remove_client(client_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/push")
async def push_event(event: dict, req: Request):
    """Push an event to all connected console clients."""
    push_store = getattr(req.app.state, "push_store", None)
    if push_store:
        await push_store.broadcast(event)
    return {"status": "ok"}
