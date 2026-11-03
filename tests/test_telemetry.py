"""7.5 — run/trace IDs, latency, token cost on events; no private CoT."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from api.swarm.accounting import TokenCostAccounting
from api.telemetry import (
    PRIVATE_COT_KEYS,
    assert_no_private_cot,
    build_run_metrics,
    new_trace_id,
    scrub_private_cot,
    stamp_telemetry,
)
from api.ws.events_log import EventLog
from api.ws.normalize import normalize_multiagent_event
from axiom_research.events import AgentStarted, parse_server
from axiom_research.identities import AgentId


def test_new_trace_id_format() -> None:
    tid = new_trace_id()
    assert tid.startswith("tr-")
    assert len(tid) > 6


def test_scrub_and_assert_reject_private_cot() -> None:
    dirty = {
        "type": "tool.summary",
        "summary": "ok",
        "chain_of_thought": "secret reasoning",
        "nested": {"thinking": "nope", "claim_id": "c1"},
    }
    clean = scrub_private_cot(dirty)
    assert isinstance(clean, dict)
    assert "chain_of_thought" not in clean
    assert "thinking" not in clean["nested"]
    assert clean["nested"]["claim_id"] == "c1"
    assert_no_private_cot(clean)
    with pytest.raises(ValueError, match="chain-of-thought"):
        assert_no_private_cot({"reasoning": "x"})


def test_event_log_strips_private_cot_keys() -> None:
    log = EventLog("ses-tel")
    stored = log.append(
        {
            "type": "agent.started",
            "event_id": "",
            "ts": datetime(2026, 11, 3, tzinfo=UTC),
            "session_id": "ses-tel",
            "run_id": "run-tel",
            "agent_id": "planner",
            "trace_id": "tr-abc",
            "chain_of_thought": "must not persist",
        }
    )
    assert stored["trace_id"] == "tr-abc"
    assert "chain_of_thought" not in stored
    for key in PRIVATE_COT_KEYS:
        assert key not in stored


def test_normalize_stamps_trace_id_and_drops_reasoning_stream() -> None:
    events = normalize_multiagent_event(
        {
            "type": "multiagent_node_start",
            "node_id": "planner",
        },
        session_id="ses-1",
        run_id="run-1",
        trace_id="tr-norm",
    )
    assert len(events) == 1
    assert events[0].trace_id == "tr-norm"
    assert events[0].run_id == "run-1"

    dropped = normalize_multiagent_event(
        {
            "type": "multiagent_node_stream",
            "node_id": "planner",
            "event": {"type": "thinking", "text": "private cot"},
        },
        session_id="ses-1",
        run_id="run-1",
        trace_id="tr-norm",
    )
    assert dropped == []


def test_run_metrics_from_accounting() -> None:
    accounting = TokenCostAccounting(
        input_usd_per_mtok=1.0,
        output_usd_per_mtok=2.0,
    )
    accounting.record_turn(agent_id="planner", input_tokens=1000, output_tokens=500)
    metrics = build_run_metrics(
        accounting,
        session_id="ses-1",
        run_id="run-1",
        trace_id="tr-m",
        latency_ms=123,
        ts=datetime(2026, 11, 3, tzinfo=UTC),
    )
    assert metrics.type == "run.metrics"
    assert metrics.trace_id == "tr-m"
    assert metrics.latency_ms == 123
    assert metrics.input_tokens == 1000
    assert metrics.output_tokens == 500
    assert metrics.total_tokens == 1500
    assert metrics.turn_count == 1
    assert metrics.cost_usd == pytest.approx(0.002)
    # Round-trip through contract.
    parsed = parse_server(metrics.model_dump(mode="json"))
    assert parsed.type == "run.metrics"


def test_stamp_telemetry_preserves_agent_event() -> None:
    started = AgentStarted(
        event_id="",
        ts=datetime(2026, 11, 3, tzinfo=UTC),
        session_id="ses-1",
        run_id="run-1",
        agent_id=AgentId.PLANNER,
    )
    stamped = stamp_telemetry(started, trace_id="tr-1", latency_ms=9)
    assert stamped.trace_id == "tr-1"
    assert stamped.latency_ms == 9
    assert stamped.agent_id is AgentId.PLANNER
