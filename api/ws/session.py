"""``WS /ws/session`` — ask / cancel / heartbeat + replay."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.ws.hub import SessionHub, heartbeat_event
from axiom_research.events import parse_client

logger = logging.getLogger(__name__)

router = APIRouter()


async def _send(ws: WebSocket, payload: dict[str, Any]) -> None:
    await ws.send_json(payload)


async def _pump_subscriber(
    ws: WebSocket,
    queue: asyncio.Queue[dict[str, Any]],
) -> None:
    while True:
        payload = await queue.get()
        await _send(ws, payload)


@router.websocket("/ws/session")
async def ws_session(websocket: WebSocket, session_id: str | None = None) -> None:
    """One socket per conversation. Query ``session_id`` reconnects the same hub session."""
    await websocket.accept()
    hub: SessionHub = websocket.app.state.hub
    session = hub.get_or_create(session_id)
    queue = hub.subscribe(session.session_id)
    pump = asyncio.create_task(_pump_subscriber(websocket, queue))

    # Announce session id via heartbeat so clients can reconnect.
    await _send(websocket, hub.append_event(session, heartbeat_event(session)))

    try:
        while True:
            raw = await websocket.receive_json()
            try:
                message = parse_client(raw)
            except Exception as exc:
                await _send(
                    websocket,
                    {
                        "type": "run.failed",
                        "event_id": "evt-invalid",
                        "ts": heartbeat_event(session).ts.isoformat(),
                        "session_id": session.session_id,
                        "run_id": session.live_run_id or "session",
                        "reason": f"invalid client message: {exc}",
                    },
                )
                continue

            if message.type == "heartbeat":
                for missed in hub.replay(session, message.last_event_id):
                    await _send(websocket, missed)
                await _send(
                    websocket, hub.append_event(session, heartbeat_event(session))
                )
                continue

            if message.type == "cancel":
                await hub.cancel(session, message.run_id)
                continue

            # ask
            for missed in hub.replay(session, message.last_event_id):
                await _send(websocket, missed)
            if session.is_live:
                # Reconnect / duplicate ask must not restart a live run.
                await _send(
                    websocket, hub.append_event(session, heartbeat_event(session))
                )
                continue
            await hub.start_ask(session, message.question)
    except WebSocketDisconnect:
        logger.debug("ws disconnected session=%s", session.session_id)
    finally:
        pump.cancel()
        try:
            await pump
        except asyncio.CancelledError:
            pass
        hub.unsubscribe(session.session_id, queue)
