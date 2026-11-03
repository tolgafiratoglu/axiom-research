"""4.B — Strands multiagent_* → UI mapping; WS stream + replay/cancel fixture."""

from __future__ import annotations

import logging
import time

from fastapi.testclient import TestClient

from api.main import create_app
from api.swarm.scripted_model import ScriptedModel, handoff_turn, text_turn, tool_turn
from api.ws.hub import SessionHub, default_swarm_run_factory
from api.ws.normalize import MAPPING_TABLE, normalize_multiagent_event
from axiom_research.events import SERVER_EVENT_TYPES
from axiom_research.identities import AgentId
from axiom_research.settings import Settings

logging.disable(logging.CRITICAL)


def _cfg(**overrides: object) -> Settings:
    data: dict[str, object] = {
        "llm_provider": "gemini",
        "gemini_model": "gemini-3.6-flash",
        "secrets_env_path": "/nonexistent/axiom-test-secrets.env",
        "swarm_max_handoffs": 8,
        "swarm_max_iterations": 8,
        "swarm_execution_timeout_seconds": 30.0,
        "swarm_node_timeout_seconds": 15.0,
        "swarm_repetitive_handoff_detection": True,
        "swarm_repetitive_handoff_detection_window": 8,
        "swarm_repetitive_handoff_min_unique_agents": 3,
        "swarm_max_tokens_per_run": 100_000,
        "swarm_max_cost_usd_per_run": 1.0,
    }
    data.update(overrides)
    return Settings.model_validate(data)


def _wait_until(predicate, *, timeout: float = 8.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def _scripted_models() -> dict[AgentId, ScriptedModel]:
    return {
        AgentId.PLANNER: ScriptedModel(
            [handoff_turn("investigator", "Fetch evidence"), text_turn()]
        ),
        AgentId.INVESTIGATOR: ScriptedModel(
            [
                tool_turn(
                    "upsert_evidence",
                    {
                        "payload": {
                            "evidence_id": "ev-ws-1",
                            "source_id": "src-1",
                            "kind": "computed_property",
                            "statement": "reported property",
                            "retrieved_at": "2026-11-02T00:00:00Z",
                            "author_agent": "investigator",
                            "fingerprint": "fp-ev-ws",
                            "unit": "eV",
                        }
                    },
                    tool_use_id="ev-tool",
                ),
                text_turn("done"),
            ]
        ),
        AgentId.DATA_ANALYST: ScriptedModel([text_turn()]),
        AgentId.CHALLENGER: ScriptedModel([text_turn()]),
    }


def test_mapping_table_covers_stable_ui_targets() -> None:
    targets = {ui for _sdk, ui in MAPPING_TABLE}
    assert "agent.started" in targets
    assert "agent.handoff" in targets
    assert "evidence.updated" in targets
    assert "hypothesis.created" in targets
    assert "tool.summary" in targets
    assert "run.failed" in targets
    assert targets <= set(SERVER_EVENT_TYPES)


def test_normalize_node_start_handoff_and_drops_raw_sdk_keys() -> None:
    names: dict[str, str] = {}
    started = normalize_multiagent_event(
        {"type": "multiagent_node_start", "node_id": "planner", "node_type": "agent"},
        session_id="ses-1",
        run_id="run-1",
        tool_names_by_id=names,
    )
    assert len(started) == 1
    assert started[0].type == "agent.started"
    dumped = started[0].model_dump(mode="json")
    assert "node_id" not in dumped
    assert "node_type" not in dumped

    handoff = normalize_multiagent_event(
        {
            "type": "multiagent_handoff",
            "from_node_ids": ["planner"],
            "to_node_ids": ["investigator"],
            "message": "retrieve sources",
        },
        session_id="ses-1",
        run_id="run-1",
        tool_names_by_id=names,
    )
    assert handoff[0].type == "agent.handoff"
    assert handoff[0].from_agent is AgentId.PLANNER
    assert handoff[0].to_agent is AgentId.INVESTIGATOR

    noise = normalize_multiagent_event(
        {
            "type": "multiagent_node_stream",
            "node_id": "planner",
            "event": {"init_event_loop": True},
        },
        session_id="ses-1",
        run_id="run-1",
        tool_names_by_id=names,
    )
    assert noise == []


def test_normalize_ledger_tool_results_to_evidence_and_hypothesis() -> None:
    names: dict[str, str] = {}
    normalize_multiagent_event(
        {
            "type": "multiagent_node_stream",
            "node_id": "investigator",
            "event": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "e1",
                                "name": "upsert_evidence",
                                "input": {},
                            }
                        }
                    ],
                }
            },
        },
        session_id="ses-1",
        run_id="run-1",
        tool_names_by_id=names,
    )
    assert names["e1"] == "upsert_evidence"

    evidence_events = normalize_multiagent_event(
        {
            "type": "multiagent_node_stream",
            "node_id": "investigator",
            "event": {
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "toolResult": {
                                "toolUseId": "e1",
                                "status": "success",
                                "content": [
                                    {
                                        "text": (
                                            '{"evidence_id":"ev-1","claim_id":null,'
                                            '"revision":1,"statement":"band gap"}'
                                        )
                                    }
                                ],
                            }
                        }
                    ],
                }
            },
        },
        session_id="ses-1",
        run_id="run-1",
        tool_names_by_id=names,
    )
    assert evidence_events[0].type == "evidence.updated"
    assert evidence_events[0].evidence_id == "ev-1"

    names["h1"] = "upsert_hypothesis"
    hyp = normalize_multiagent_event(
        {
            "type": "multiagent_node_stream",
            "node_id": "challenger",
            "event": {
                "message": {
                    "role": "user",
                    "content": [
                        {
                            "toolResult": {
                                "toolUseId": "h1",
                                "status": "success",
                                "content": [
                                    {
                                        "text": (
                                            '{"hypothesis_id":"hyp-1",'
                                            '"statement":"not commercial readiness"}'
                                        )
                                    }
                                ],
                            }
                        }
                    ],
                }
            },
        },
        session_id="ses-1",
        run_id="run-1",
        tool_names_by_id=names,
    )
    assert hyp[0].type == "hypothesis.created"
    assert hyp[0].hypothesis_id == "hyp-1"


def test_ws_mocked_swarm_streams_stable_events_replay_and_cancel() -> None:
    hub = SessionHub(run_factory=default_swarm_run_factory)
    app = create_app(hub=hub)
    client = TestClient(app)

    with client.websocket_connect("/ws/session") as ws:
        hello = ws.receive_json()
        session_id = hello["session_id"]
        session = hub.get_or_create(session_id)
        session.models = _scripted_models()
        session.cfg = _cfg()

        ws.send_json({"type": "ask", "question": "solid-state electrolytes?"})
        assert _wait_until(
            lambda: any(e["type"] == "agent.started" for e in session.events._events)  # noqa: SLF001
        )
        assert _wait_until(lambda: not session.is_live, timeout=10.0)

        types = [e["type"] for e in session.events._events]  # noqa: SLF001
        for t in types:
            assert not t.startswith("multiagent_")
        assert "agent.started" in types
        assert "agent.handoff" in types
        assert "evidence.updated" in types
        # Drain socket so the pump does not back up (exact count unknown).
        # Events are already asserted via the session log above.

    # Reconnect + replay (does not restart a live run).
    with client.websocket_connect(f"/ws/session?session_id={session_id}") as ws2:
        hello2 = ws2.receive_json()
        assert hello2["session_id"] == session_id
        first_id = session.events._events[0]["event_id"]  # noqa: SLF001
        ws2.send_json({"type": "heartbeat", "last_event_id": first_id})
        replayed = hub.replay(session, first_id)
        replay_types = [e["type"] for e in replayed]
        assert "agent.handoff" in replay_types or "evidence.updated" in replay_types
        # One more heartbeat is appended by the handler; ignore wire drain.
        assert session.is_live is False

    # Cancel path (4.6): start a run then cancel before it finishes.
    async def _slow(ctx):
        from datetime import UTC, datetime

        from axiom_research.events import AgentStarted, RunFailed

        yield AgentStarted(
            event_id="",
            ts=datetime.now(tz=UTC),
            session_id=ctx.session_id,
            run_id=ctx.run_id,
            agent_id=AgentId.PLANNER,
        )
        for _ in range(100):
            if ctx.cancel.is_set():
                yield RunFailed(
                    event_id="",
                    ts=datetime.now(tz=UTC),
                    session_id=ctx.session_id,
                    run_id=ctx.run_id,
                    reason="cancelled",
                )
                return
            import asyncio

            await asyncio.sleep(0.01)

    cancel_hub = SessionHub(run_factory=_slow)
    cancel_app = create_app(hub=cancel_hub)
    cancel_client = TestClient(cancel_app)
    with cancel_client.websocket_connect("/ws/session") as ws:
        ws.receive_json()
        ws.send_json({"type": "ask", "question": "cancel me"})
        run_id = None
        for _ in range(20):
            msg = ws.receive_json()
            if msg["type"] == "agent.started":
                run_id = msg["run_id"]
                break
        assert run_id
        ws.send_json({"type": "cancel", "run_id": run_id})
        for _ in range(40):
            msg = ws.receive_json()
            if msg.get("type") == "run.failed" and msg.get("reason") == "cancelled":
                break
        else:
            raise AssertionError("expected cancelled run.failed")
