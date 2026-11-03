"""4.A — WS /ws/session: ask, cancel, heartbeat replay, follow-up memory (mocked run)."""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from api.main import create_app
from api.ws.hub import RunContext, SessionHub, compose_follow_up_question
from axiom_research.events import AgentStarted, RunFailed
from axiom_research.identities import AgentId


async def _slow_mock_run(ctx: RunContext):
    yield AgentStarted(
        event_id="",
        ts=datetime.now(tz=UTC),
        session_id=ctx.session_id,
        run_id=ctx.run_id,
        agent_id=AgentId.PLANNER,
    )
    for _ in range(50):
        if ctx.cancel.is_set():
            yield RunFailed(
                event_id="",
                ts=datetime.now(tz=UTC),
                session_id=ctx.session_id,
                run_id=ctx.run_id,
                reason="cancelled",
            )
            return
        await asyncio.sleep(0.01)
    yield AgentStarted(
        event_id="",
        ts=datetime.now(tz=UTC),
        session_id=ctx.session_id,
        run_id=ctx.run_id,
        agent_id=AgentId.INVESTIGATOR,
    )


def _wait_until(predicate, *, timeout: float = 2.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_ask_cancel_and_heartbeat_replay() -> None:
    hub = SessionHub(run_factory=_slow_mock_run)
    app = create_app(hub=hub)
    client = TestClient(app)

    with client.websocket_connect("/ws/session") as ws:
        hello = ws.receive_json()
        assert hello["type"] == "heartbeat"
        session_id = hello["session_id"]

        ws.send_json({"type": "ask", "question": "solid-state electrolytes?"})
        started = None
        for _ in range(20):
            msg = ws.receive_json()
            if msg["type"] == "agent.started":
                started = msg
                break
        assert started is not None
        assert started["agent_id"] == "planner"
        run_id = started["run_id"]
        last_id = started["event_id"]

        ws.send_json({"type": "cancel", "run_id": run_id})
        cancelled = None
        for _ in range(40):
            msg = ws.receive_json()
            if msg.get("type") == "run.failed" and msg.get("reason") == "cancelled":
                cancelled = msg
                break
        assert cancelled is not None
        assert _wait_until(lambda: not hub.get_or_create(session_id).is_live)

    with client.websocket_connect(f"/ws/session?session_id={session_id}") as ws2:
        hello2 = ws2.receive_json()
        assert hello2["session_id"] == session_id
        ws2.send_json({"type": "heartbeat", "last_event_id": last_id})
        replayed: list[dict] = []
        for _ in range(15):
            msg = ws2.receive_json()
            replayed.append(msg)
            if msg["type"] == "heartbeat" and msg["event_id"] != hello2["event_id"]:
                break
        types = [m["type"] for m in replayed]
        assert "run.failed" in types
        assert hub.get_or_create(session_id).is_live is False


def test_follow_up_ask_uses_memory_and_same_ledger() -> None:
    seen: list[str] = []

    async def _fast_mock_run(ctx: RunContext):
        seen.append(compose_follow_up_question(ctx.memory, ctx.question))
        yield AgentStarted(
            event_id="",
            ts=datetime.now(tz=UTC),
            session_id=ctx.session_id,
            run_id=ctx.run_id,
            agent_id=AgentId.PLANNER,
        )

    hub = SessionHub(run_factory=_fast_mock_run)
    app = create_app(hub=hub)
    client = TestClient(app)

    with client.websocket_connect("/ws/session") as ws:
        hello = ws.receive_json()
        session_id = hello["session_id"]
        session = hub.get_or_create(session_id)

        ws.send_json({"type": "ask", "question": "sodium-ion vs lithium-ion?"})
        for _ in range(20):
            msg = ws.receive_json()
            if msg["type"] == "agent.started":
                break
        assert _wait_until(lambda: not session.is_live)

        ws.send_json({"type": "ask", "question": "What about solid-state?"})
        for _ in range(20):
            msg = ws.receive_json()
            if msg["type"] == "agent.started":
                break
        assert _wait_until(lambda: not session.is_live)

        assert len(seen) >= 2
        assert "sodium-ion vs lithium-ion?" in seen[-1]
        assert "Current question: What about solid-state?" in seen[-1]
        assert len([m for m in session.memory if m["role"] == "user"]) == 2
        assert session.store is hub.get_or_create(session_id).store


def test_ask_during_live_run_does_not_restart() -> None:
    hub = SessionHub(run_factory=_slow_mock_run)
    app = create_app(hub=hub)
    client = TestClient(app)

    with client.websocket_connect("/ws/session") as ws:
        ws.receive_json()
        ws.send_json({"type": "ask", "question": "first"})
        first_run = None
        for _ in range(20):
            msg = ws.receive_json()
            if msg["type"] == "agent.started":
                first_run = msg["run_id"]
                break
        assert first_run
        ws.send_json({"type": "ask", "question": "second should not restart"})
        saw_second_start = False
        for _ in range(8):
            msg = ws.receive_json()
            if msg["type"] == "agent.started" and msg["run_id"] != first_run:
                saw_second_start = True
                break
            if msg["type"] == "heartbeat":
                break
        assert saw_second_start is False
        ws.send_json({"type": "cancel", "run_id": first_run})
        for _ in range(40):
            msg = ws.receive_json()
            if msg.get("type") == "run.failed":
                break
