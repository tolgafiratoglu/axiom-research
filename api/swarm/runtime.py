"""Build and run the local Research Swarm (no Verifier / Finalizer)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from strands.multiagent import Swarm

from api.ledger.tools import LedgerTools
from api.swarm.accounting import TokenCostAccounting
from api.swarm.agents import (
    build_challenger,
    build_data_analyst,
    build_investigator,
    build_planner,
)
from axiom_research.identities import AgentId
from axiom_research.ledger_store import InMemoryLedgerStore, LedgerStore
from axiom_research.llm.strands_gemini import build_gemini_model
from axiom_research.settings import Settings, settings


@dataclass
class SwarmRunResult:
    status: str
    reason: str | None
    question: str
    session_id: str
    run_id: str
    node_history: list[str]
    execution_count: int
    accounting: TokenCostAccounting
    ledger_summary: dict[str, Any]
    raw: Any = None


def _resolve_model(
    agent_id: AgentId,
    *,
    shared: Any | None,
    models: dict[AgentId, Any] | None,
) -> Any:
    if models and agent_id in models:
        return models[agent_id]
    if shared is not None:
        return shared
    raise RuntimeError(f"no model configured for {agent_id.value}")


def build_research_swarm(
    *,
    ledger: LedgerTools,
    mcp_tools: list[Any],
    model: Any | None = None,
    models: dict[AgentId, Any] | None = None,
    accounting: TokenCostAccounting | None = None,
    cfg: Settings | None = None,
) -> tuple[Swarm, dict[AgentId, Any], TokenCostAccounting]:
    """Wire Swarm with ``entry_point=planner`` and 0.A budgets."""
    ready = cfg or settings
    shared = model
    if models is None and shared is None:
        shared = build_gemini_model(ready)

    agents = {
        AgentId.PLANNER: build_planner(
            model=_resolve_model(AgentId.PLANNER, shared=shared, models=models),
            ledger=ledger,
        ),
        AgentId.INVESTIGATOR: build_investigator(
            model=_resolve_model(AgentId.INVESTIGATOR, shared=shared, models=models),
            ledger=ledger,
            mcp_tools=mcp_tools,
        ),
        AgentId.DATA_ANALYST: build_data_analyst(
            model=_resolve_model(AgentId.DATA_ANALYST, shared=shared, models=models),
            ledger=ledger,
        ),
        AgentId.CHALLENGER: build_challenger(
            model=_resolve_model(AgentId.CHALLENGER, shared=shared, models=models),
            ledger=ledger,
        ),
    }

    tracker = accounting or TokenCostAccounting.from_settings(ready)
    tracker.max_tokens = ready.swarm_max_tokens_per_run
    tracker.max_cost_usd = ready.swarm_max_cost_usd_per_run
    for agent in agents.values():
        tracker.attach(agent)

    window = (
        ready.swarm_repetitive_handoff_detection_window
        if ready.swarm_repetitive_handoff_detection
        else 0
    )
    min_unique = (
        ready.swarm_repetitive_handoff_min_unique_agents
        if ready.swarm_repetitive_handoff_detection
        else 0
    )
    swarm = Swarm(
        [
            agents[AgentId.PLANNER],
            agents[AgentId.INVESTIGATOR],
            agents[AgentId.DATA_ANALYST],
            agents[AgentId.CHALLENGER],
        ],
        entry_point=agents[AgentId.PLANNER],
        max_handoffs=ready.swarm_max_handoffs,
        max_iterations=ready.swarm_max_iterations,
        execution_timeout=ready.swarm_execution_timeout_seconds,
        node_timeout=ready.swarm_node_timeout_seconds,
        repetitive_handoff_detection_window=window,
        repetitive_handoff_min_unique_agents=min_unique,
    )
    return swarm, agents, tracker


def ledger_summary(store: LedgerStore, session_id: str) -> dict[str, Any]:
    session = getattr(store, "_sessions", {}).get(session_id)
    if session is None:
        return {
            "sources": 0,
            "evidence": 0,
            "claims": 0,
            "calculations": 0,
            "hypotheses": 0,
        }
    return {
        "sources": len(session.sources),
        "evidence": len(session.evidence),
        "claims": len(session.claims),
        "calculations": len(session.calculations),
        "hypotheses": len(session.hypotheses),
    }


def run_research_swarm(
    question: str,
    *,
    store: LedgerStore | None = None,
    mcp_tools: list[Any] | None = None,
    model: Any | None = None,
    models: dict[AgentId, Any] | None = None,
    session_id: str | None = None,
    run_id: str | None = None,
    cfg: Settings | None = None,
    accounting: TokenCostAccounting | None = None,
) -> SwarmRunResult:
    ready = cfg or settings
    sid = session_id or f"ses-{uuid.uuid4().hex[:10]}"
    rid = run_id or f"run-{uuid.uuid4().hex[:10]}"
    mem = store or InMemoryLedgerStore()
    ledger = LedgerTools(mem, session_id=sid, run_id=rid)
    swarm, _agents, tracker = build_research_swarm(
        ledger=ledger,
        mcp_tools=mcp_tools or [],
        model=model,
        models=models,
        accounting=accounting,
        cfg=ready,
    )
    raw = swarm(question)
    history = [node.node_id for node in raw.node_history]
    status = str(getattr(raw.status, "value", raw.status))
    reason = None
    if tracker.exceeded_reason:
        status = "failed"
        reason = tracker.exceeded_reason
    elif status == "failed":
        reason = "run.failed: swarm budget or repetitive handoff stop"
    return SwarmRunResult(
        status=status,
        reason=reason,
        question=question,
        session_id=sid,
        run_id=rid,
        node_history=history,
        execution_count=int(raw.execution_count),
        accounting=tracker,
        ledger_summary=ledger_summary(mem, sid),
        raw=raw,
    )
