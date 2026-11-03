"""Session hub: one conversation, event log + ledger + memory."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from api.telemetry import build_run_metrics, new_trace_id, stamp_telemetry
from api.ws.events_log import EventLog
from api.ws.normalize import normalize_multiagent_event
from axiom_research.events import RunFailed, ServerHeartbeat, ServerMessage
from axiom_research.identities import AgentId
from axiom_research.ledger_store import InMemoryLedgerStore
from axiom_research.settings import Settings


@dataclass
class RunContext:
    session_id: str
    run_id: str
    question: str
    memory: list[dict[str, str]]
    store: InMemoryLedgerStore
    cancel: asyncio.Event
    models: dict[AgentId, Any] | None = None
    mcp_tools: list[Any] = field(default_factory=list)
    cfg: Settings | None = None
    # Injected Verifier client (mock in tests; live A2A in operator runs).
    verifier_client: Any | None = None
    trace_id: str = ""


RunFactory = Callable[[RunContext], AsyncIterator[ServerMessage]]


def compose_follow_up_question(memory: list[dict[str, str]], question: str) -> str:
    """Prior user turns + current question (same ledger session, not a blank Swarm)."""
    prior = [m for m in memory if m.get("role") == "user"]
    prior = prior[:-1] if prior else []
    if not prior:
        return question
    lines = ["Prior questions in this conversation:"]
    for item in prior:
        lines.append(f"- {item['content']}")
    lines.append("")
    lines.append(f"Current question: {question}")
    return "\n".join(lines)


async def default_swarm_run_factory(ctx: RunContext) -> AsyncIterator[ServerMessage]:
    """Stream Swarm via ``stream_async`` and normalize to stable UI events."""
    from api.ledger.tools import LedgerTools
    from api.swarm.runtime import build_research_swarm

    trace_id = ctx.trace_id or new_trace_id()
    started = time.perf_counter()

    if ctx.cancel.is_set():
        yield stamp_telemetry(
            RunFailed(
                event_id="",
                ts=datetime.now(tz=UTC),
                session_id=ctx.session_id,
                run_id=ctx.run_id,
                reason="cancelled",
            ),
            trace_id=trace_id,
        )
        return

    question = compose_follow_up_question(ctx.memory, ctx.question)
    ledger = LedgerTools(ctx.store, session_id=ctx.session_id, run_id=ctx.run_id)
    swarm, _agents, tracker = build_research_swarm(
        ledger=ledger,
        mcp_tools=ctx.mcp_tools,
        models=ctx.models,
        cfg=ctx.cfg,
    )
    tool_names_by_id: dict[str, str] = {}
    async for raw in swarm.stream_async(question):
        if ctx.cancel.is_set():
            yield stamp_telemetry(
                RunFailed(
                    event_id="",
                    ts=datetime.now(tz=UTC),
                    session_id=ctx.session_id,
                    run_id=ctx.run_id,
                    reason="cancelled",
                ),
                trace_id=trace_id,
            )
            return
        if not isinstance(raw, dict):
            continue
        for event in normalize_multiagent_event(
            raw,
            session_id=ctx.session_id,
            run_id=ctx.run_id,
            tool_names_by_id=tool_names_by_id,
            trace_id=trace_id,
        ):
            yield event

    latency_ms = max(0, int((time.perf_counter() - started) * 1000))
    yield build_run_metrics(
        tracker,
        session_id=ctx.session_id,
        run_id=ctx.run_id,
        trace_id=trace_id,
        latency_ms=latency_ms,
    )

    if tracker.exceeded_reason:
        yield stamp_telemetry(
            RunFailed(
                event_id="",
                ts=datetime.now(tz=UTC),
                session_id=ctx.session_id,
                run_id=ctx.run_id,
                reason=tracker.exceeded_reason,
            ),
            trace_id=trace_id,
        )
        # Still attempt gate on budget stop when a Verifier client is wired.
        # (No confident Finalizer if gate fails.)

    if ctx.verifier_client is not None:
        from api.finalizer import run_finalizer
        from api.gate import run_verification_gate

        gate = await run_verification_gate(
            ctx.store,
            session_id=ctx.session_id,
            run_id=ctx.run_id,
            client=ctx.verifier_client,
        )
        for event in gate.events:
            yield stamp_telemetry(event, trace_id=trace_id)
            if event.type == "run.failed":
                return
        final = run_finalizer(
            gate,
            session_id=ctx.session_id,
            run_id=ctx.run_id,
        )
        for event in final.events:
            yield stamp_telemetry(event, trace_id=trace_id)


@dataclass
class SessionState:
    session_id: str
    store: InMemoryLedgerStore = field(default_factory=InMemoryLedgerStore)
    memory: list[dict[str, str]] = field(default_factory=list)
    events: EventLog = field(init=False)
    live_run_id: str | None = None
    live_task: asyncio.Task[None] | None = None
    cancel: asyncio.Event = field(default_factory=asyncio.Event)
    models: dict[AgentId, Any] | None = None
    mcp_tools: list[Any] = field(default_factory=list)
    cfg: Settings | None = None
    verifier_client: Any | None = None

    def __post_init__(self) -> None:
        self.events = EventLog(self.session_id)

    @property
    def is_live(self) -> bool:
        return self.live_task is not None and not self.live_task.done()


class SessionHub:
    """Process-local session registry (Compose api is single process)."""

    def __init__(self, run_factory: RunFactory | None = None) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._run_factory: RunFactory = run_factory or default_swarm_run_factory
        self._subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}

    def get_or_create(self, session_id: str | None = None) -> SessionState:
        sid = session_id or f"ses-{uuid.uuid4().hex[:12]}"
        if sid not in self._sessions:
            self._sessions[sid] = SessionState(session_id=sid)
        return self._sessions[sid]

    def subscribe(self, session_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers.setdefault(session_id, []).append(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        subs = self._subscribers.get(session_id) or []
        if queue in subs:
            subs.remove(queue)

    def _publish(self, session: SessionState, payload: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(session.session_id, [])):
            queue.put_nowait(payload)

    def append_event(self, session: SessionState, event: ServerMessage) -> dict[str, Any]:
        stored = session.events.append(event)
        self._publish(session, stored)
        return stored

    def replay(self, session: SessionState, last_event_id: str | None) -> list[dict[str, Any]]:
        return session.events.events_after(last_event_id)

    async def start_ask(self, session: SessionState, question: str) -> str | None:
        """Start a run. Returns None if a live run already exists (do not restart)."""
        if session.is_live:
            return None
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        session.live_run_id = run_id
        session.cancel = asyncio.Event()
        session.memory.append({"role": "user", "content": question})
        session.live_task = asyncio.create_task(
            self._run(session, question, run_id),
            name=f"axiom-run-{run_id}",
        )
        return run_id

    async def cancel(self, session: SessionState, run_id: str | None = None) -> bool:
        if not session.is_live:
            return False
        if run_id and session.live_run_id and run_id != session.live_run_id:
            return False
        session.cancel.set()
        task = session.live_task
        if task is not None:
            await task
        return True

    async def _run(self, session: SessionState, question: str, run_id: str) -> None:
        trace_id = new_trace_id()
        ctx = RunContext(
            session_id=session.session_id,
            run_id=run_id,
            question=question,
            memory=list(session.memory),
            store=session.store,
            cancel=session.cancel,
            models=session.models,
            mcp_tools=list(session.mcp_tools),
            cfg=session.cfg,
            verifier_client=session.verifier_client,
            trace_id=trace_id,
        )
        try:
            async for event in self._run_factory(ctx):
                updates: dict[str, Any] = {
                    "session_id": session.session_id,
                    "run_id": run_id,
                    "ts": getattr(event, "ts", None) or datetime.now(tz=UTC),
                }
                if not getattr(event, "trace_id", None):
                    updates["trace_id"] = trace_id
                data = event.model_copy(update=updates)
                stored = self.append_event(session, data)
                if stored.get("type") == "run.failed":
                    break
            session.memory.append(
                {"role": "assistant", "content": f"run:{run_id}:done"}
            )
        finally:
            if session.live_run_id == run_id:
                session.live_task = None
                session.live_run_id = None


def heartbeat_event(session: SessionState) -> ServerHeartbeat:
    return ServerHeartbeat(
        event_id="",
        ts=datetime.now(tz=UTC),
        session_id=session.session_id,
        run_id=session.live_run_id or "session",
        last_event_id=session.events.last_event_id,
    )
