"""Map Strands ``multiagent_*`` stream dicts → stable UI events (0.5).

Browser never receives raw SDK keys.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from axiom_research.events import (
    AgentHandoff,
    AgentStarted,
    EvidenceUpdated,
    HypothesisCreated,
    RunFailed,
    ServerMessage,
    ToolSummary,
)
from api.telemetry import stamp_telemetry
from axiom_research.identities import AgentId
from axiom_research.mcp.failures import tool_failure_summary

# Ledger tool names that surface as evidence/hypothesis UI events (not raw JSON).
_EVIDENCE_TOOLS = frozenset(
    {
        "upsert_evidence",
        "upsert_claim",
        "attach_evidence_to_claim",
        "upsert_source",
    }
)
_HYPOTHESIS_TOOLS = frozenset({"upsert_hypothesis"})
_SKIP_TOOL_SUMMARY = frozenset({"handoff_to_agent"})

# Documented mapping for tests / operators (SDK type → UI type).
MAPPING_TABLE: tuple[tuple[str, str], ...] = (
    ("multiagent_node_start", "agent.started"),
    ("multiagent_handoff", "agent.handoff"),
    ("multiagent_node_stream.toolResult(ledger evidence)", "evidence.updated"),
    ("multiagent_node_stream.toolResult(upsert_hypothesis)", "hypothesis.created"),
    ("multiagent_node_stream.toolResult(other)", "tool.summary"),
    ("result(Status.FAILED)", "run.failed"),
)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _opt_str(body: dict[str, Any], key: str) -> str | None:
    val = body.get(key)
    if val is None:
        return None
    text = str(val).strip()
    return text or None


def _evidence_display_fields(body: dict[str, Any]) -> dict[str, Any]:
    """Safe claim/evidence fields for UI expand — never full tool dumps."""
    refs = body.get("source_refs") or body.get("identifier")
    source_refs: list[str] = []
    if isinstance(refs, list):
        source_refs = [str(r) for r in refs if str(r).strip()]
    elif isinstance(refs, str) and refs.strip():
        source_refs = [refs.strip()]
    retrieved = body.get("retrieved_at")
    retrieved_at = None
    if retrieved is not None:
        retrieved_at = retrieved if isinstance(retrieved, str) else str(retrieved)
    return {
        "statement": _opt_str(body, "statement"),
        "source_refs": source_refs,
        "unit": _opt_str(body, "unit"),
        "value": body.get("value"),
        "method": _opt_str(body, "method"),
        "license": _opt_str(body, "license"),
        "evidence_kind": _opt_str(body, "evidence_kind") or _opt_str(body, "kind"),
        "verification_status": _opt_str(body, "verification_status"),
        "retrieved_at": retrieved_at,
    }


def _agent_id(node_id: str) -> AgentId | None:
    try:
        return AgentId(node_id)
    except ValueError:
        return None


def _parse_jsonish(text: str) -> dict[str, Any] | None:
    import json

    raw = text.strip()
    if not raw.startswith("{"):
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def normalize_multiagent_event(
    raw: dict[str, Any],
    *,
    session_id: str,
    run_id: str,
    tool_names_by_id: dict[str, str] | None = None,
    trace_id: str | None = None,
) -> list[ServerMessage]:
    """Convert one SDK stream dict into zero or more stable ServerMessage values."""
    if not isinstance(raw, dict):
        return []

    sdk_type = raw.get("type")
    ts = _now()
    out: list[ServerMessage] = []
    names = tool_names_by_id if tool_names_by_id is not None else {}

    def _finish(events: list[ServerMessage]) -> list[ServerMessage]:
        if not trace_id:
            return events
        return [stamp_telemetry(event, trace_id=trace_id) for event in events]

    # Never surface raw SDK reasoning / private CoT blobs as UI events.
    if sdk_type == "multiagent_node_stream":
        inner = raw.get("event")
        if isinstance(inner, dict) and inner.get("type") in {
            "reasoning",
            "thinking",
            "chain_of_thought",
        }:
            return []

    # Track toolUse id → name for later toolResult blocks.
    if sdk_type == "multiagent_node_stream":
        inner = raw.get("event")
        if isinstance(inner, dict):
            msg = inner.get("message")
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                for block in msg.get("content") or []:
                    if isinstance(block, dict) and "toolUse" in block:
                        use = block["toolUse"]
                        if isinstance(use, dict) and use.get("toolUseId") and use.get("name"):
                            names[str(use["toolUseId"])] = str(use["name"])
            # tool_use_stream current_tool_use
            current = inner.get("current_tool_use")
            if isinstance(current, dict) and current.get("toolUseId") and current.get("name"):
                names[str(current["toolUseId"])] = str(current["name"])

    if sdk_type == "multiagent_node_start":
        agent = _agent_id(str(raw.get("node_id") or ""))
        if agent is None:
            return []
        out.append(
            AgentStarted(
                event_id="",
                ts=ts,
                session_id=session_id,
                run_id=run_id,
                agent_id=agent,
            )
        )
        return _finish(out)

    if sdk_type == "multiagent_handoff":
        from_ids = raw.get("from_node_ids") or []
        to_ids = raw.get("to_node_ids") or []
        if not from_ids or not to_ids:
            return []
        fr = _agent_id(str(from_ids[0]))
        to = _agent_id(str(to_ids[0]))
        if fr is None or to is None:
            return []
        reason = raw.get("message")
        out.append(
            AgentHandoff(
                event_id="",
                ts=ts,
                session_id=session_id,
                run_id=run_id,
                from_agent=fr,
                to_agent=to,
                reason=str(reason) if reason else None,
            )
        )
        return _finish(out)

    if sdk_type == "multiagent_node_stream":
        inner = raw.get("event")
        if not isinstance(inner, dict):
            return []
        agent = _agent_id(str(raw.get("node_id") or "")) or AgentId.PLANNER
        # Resolve tool result
        message = inner.get("message")
        if isinstance(message, dict):
            for block in message.get("content") or []:
                if not isinstance(block, dict) or "toolResult" not in block:
                    continue
                result = block["toolResult"]
                if not isinstance(result, dict):
                    continue
                tool_use_id = str(result.get("toolUseId") or "")
                name = names.get(tool_use_id) or str(result.get("name") or "")
                status = str(result.get("status") or "success")
                ok = status == "success"
                parts: list[str] = []
                for item in result.get("content") or []:
                    if isinstance(item, dict) and item.get("text"):
                        parts.append(str(item["text"]))
                summary = " ".join(parts).strip() or f"{name or 'tool'} {status}"
                if not name or name in _SKIP_TOOL_SUMMARY:
                    continue
                # 7.2: failed MCP/tool calls never become evidence/hypothesis rows
                # (no fabricated sources from error payloads).
                if not ok:
                    out.append(
                        ToolSummary(
                            event_id="",
                            ts=ts,
                            session_id=session_id,
                            run_id=run_id,
                            agent_id=agent,
                            tool_name=name,
                            summary=tool_failure_summary(name, summary)[:400],
                            ok=False,
                        )
                    )
                    continue
                if name in _HYPOTHESIS_TOOLS:
                    payload = _parse_jsonish(summary) or {}
                    # Tool wrappers return model_dump JSON as text sometimes nested.
                    hyp_id = str(
                        payload.get("hypothesis_id")
                        or (payload.get("payload") or {}).get("hypothesis_id")
                        or "hypothesis"
                    )
                    out.append(
                        HypothesisCreated(
                            event_id="",
                            ts=ts,
                            session_id=session_id,
                            run_id=run_id,
                            hypothesis_id=hyp_id,
                            author_agent=agent,
                        )
                    )
                elif name in _EVIDENCE_TOOLS:
                    payload = _parse_jsonish(summary) or {}
                    body = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
                    if not isinstance(body, dict):
                        body = {}
                    display = _evidence_display_fields(body)
                    out.append(
                        EvidenceUpdated(
                            event_id="",
                            ts=ts,
                            session_id=session_id,
                            run_id=run_id,
                            evidence_id=(
                                str(body["evidence_id"])
                                if body.get("evidence_id")
                                else None
                            ),
                            claim_id=(
                                str(body["claim_id"]) if body.get("claim_id") else None
                            ),
                            revision=(
                                int(body["revision"])
                                if isinstance(body.get("revision"), int)
                                else None
                            ),
                            **display,
                        )
                    )
                else:
                    out.append(
                        ToolSummary(
                            event_id="",
                            ts=ts,
                            session_id=session_id,
                            run_id=run_id,
                            agent_id=agent,
                            tool_name=name,
                            summary=summary[:400],
                            ok=ok,
                        )
                    )
        return _finish(out)

    if sdk_type == "result":
        result = raw.get("result")
        status = getattr(result, "status", None)
        value = getattr(status, "value", status)
        if value == "failed":
            out.append(
                RunFailed(
                    event_id="",
                    ts=ts,
                    session_id=session_id,
                    run_id=run_id,
                    reason="run.failed: swarm stopped",
                )
            )
        return _finish(out)

    # Drop raw SDK noise (node_stop, init_event_loop, token deltas, private CoT, …).
    return []
