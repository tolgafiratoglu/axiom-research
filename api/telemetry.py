"""Run/trace IDs, latency, token/cost on events — never private CoT."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from api.swarm.accounting import TokenCostAccounting
from axiom_research.events import RunMetrics, ServerMessage

# Keys that must never appear on persisted/streamed UI event payloads.
PRIVATE_COT_KEYS: frozenset[str] = frozenset(
    {
        "chain_of_thought",
        "private_cot",
        "cot",
        "reasoning",
        "reasoning_content",
        "thinking",
        "thought",
        "scratchpad",
        "internal_monologue",
        "model_reasoning",
        "hidden_prompt",
    }
)


def new_trace_id() -> str:
    return f"tr-{uuid.uuid4().hex[:16]}"


def scrub_private_cot(value: Any) -> Any:
    """Drop private-reasoning keys recursively from dict/list payloads."""
    if isinstance(value, dict):
        return {
            key: scrub_private_cot(item)
            for key, item in value.items()
            if key not in PRIVATE_COT_KEYS
        }
    if isinstance(value, list):
        return [scrub_private_cot(item) for item in value]
    return value


def assert_no_private_cot(payload: dict[str, Any]) -> None:
    bad = sorted(k for k in payload if k in PRIVATE_COT_KEYS)
    if bad:
        raise ValueError(
            "event payload must not include private chain-of-thought fields: "
            + ", ".join(bad)
        )
    for item in payload.values():
        if isinstance(item, dict):
            assert_no_private_cot(item)
        elif isinstance(item, list):
            for nested in item:
                if isinstance(nested, dict):
                    assert_no_private_cot(nested)


def stamp_telemetry(
    event: ServerMessage,
    *,
    trace_id: str | None,
    latency_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd: float | None = None,
) -> ServerMessage:
    updates: dict[str, Any] = {}
    if trace_id:
        updates["trace_id"] = trace_id
    if latency_ms is not None:
        updates["latency_ms"] = latency_ms
    if input_tokens is not None:
        updates["input_tokens"] = input_tokens
    if output_tokens is not None:
        updates["output_tokens"] = output_tokens
    if cost_usd is not None:
        updates["cost_usd"] = cost_usd
    return event.model_copy(update=updates) if updates else event


def build_run_metrics(
    accounting: TokenCostAccounting,
    *,
    session_id: str,
    run_id: str,
    trace_id: str,
    latency_ms: int,
    ts: datetime | None = None,
) -> RunMetrics:
    return RunMetrics(
        event_id="",
        ts=ts or datetime.now(tz=UTC),
        session_id=session_id,
        run_id=run_id,
        trace_id=trace_id,
        latency_ms=latency_ms,
        input_tokens=sum(t.input_tokens for t in accounting.turns),
        output_tokens=sum(t.output_tokens for t in accounting.turns),
        total_tokens=accounting.total_tokens,
        cost_usd=round(accounting.total_cost_usd, 8),
        turn_count=len(accounting.turns),
    )
