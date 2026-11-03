"""3.C — Swarm runtime: handoff, budgets, tool visibility (mocked Gemini/MCP)."""

from __future__ import annotations

import logging

import pytest
from strands import tool

from api.swarm.policy import (
    CALC_TOOL_NAME,
    agent_tool_names,
    is_mcp_tool_name,
)
from api.swarm.runtime import build_research_swarm, run_research_swarm
from api.swarm.scripted_model import ScriptedModel, handoff_turn, text_turn, tool_turn
from axiom_research.identities import AgentId
from axiom_research.ledger_store import InMemoryLedgerStore
from axiom_research.settings import Settings

logging.disable(logging.CRITICAL)


@tool(name="openalex_search_works", description="stub MCP")
def _openalex(query: str) -> str:
    return query


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
        "swarm_repetitive_handoff_detection_window": 4,
        "swarm_repetitive_handoff_min_unique_agents": 3,
        "swarm_max_tokens_per_run": 100_000,
        "swarm_max_cost_usd_per_run": 1.0,
    }
    data.update(overrides)
    return Settings.model_validate(data)


def test_tool_visibility_planner_without_mcp_analyst_does_not_search() -> None:
    from api.ledger.tools import LedgerTools

    ledger = LedgerTools(InMemoryLedgerStore(), session_id="ses-vis", run_id="run-vis")
    _swarm, agents, _acc = build_research_swarm(
        ledger=ledger,
        mcp_tools=[_openalex],
        model=ScriptedModel([text_turn()]),
        cfg=_cfg(),
    )
    planner_tools = agent_tool_names(agents[AgentId.PLANNER])
    assert not any(is_mcp_tool_name(n) for n in planner_tools)
    assert planner_tools <= {"handoff_to_agent"}  # Swarm injects handoff only
    inv = agent_tool_names(agents[AgentId.INVESTIGATOR])
    assert "openalex_search_works" in inv
    assert "upsert_source" in inv
    analyst = agent_tool_names(agents[AgentId.DATA_ANALYST])
    assert not any(is_mcp_tool_name(n) for n in analyst)
    assert CALC_TOOL_NAME in analyst
    assert agents[AgentId.PLANNER].name == "planner"


def test_handoff_entry_point_planner_writes_ledger_rows() -> None:
    models = {
        AgentId.PLANNER: ScriptedModel(
            [handoff_turn("investigator", "Fetch DOI metadata"), text_turn()]
        ),
        AgentId.INVESTIGATOR: ScriptedModel(
            [
                tool_turn(
                    "upsert_source",
                    {
                        "payload": {
                            "source_id": "src-1",
                            "identifier": "doi:10.example/1",
                            "retrieved_at": "2026-11-02T00:00:00Z",
                            "provider": "crossref",
                            "fingerprint": "fp-src-1",
                        }
                    },
                    tool_use_id="src-1",
                ),
                text_turn("recorded"),
            ]
        ),
        AgentId.DATA_ANALYST: ScriptedModel([text_turn()]),
        AgentId.CHALLENGER: ScriptedModel([text_turn()]),
    }
    result = run_research_swarm(
        "What is known about solid-state electrolytes?",
        models=models,
        mcp_tools=[_openalex],
        cfg=_cfg(),
        session_id="ses-handoff",
        run_id="run-handoff",
    )
    assert result.status == "completed"
    assert result.node_history[0] == "planner"
    assert "investigator" in result.node_history
    assert result.ledger_summary["sources"] >= 1


def test_repetitive_handoff_stops() -> None:
    ping = ScriptedModel(
        [
            handoff_turn("investigator", "ping"),
            text_turn(),
            handoff_turn("investigator", "ping2"),
            text_turn(),
            handoff_turn("investigator", "ping3"),
            text_turn(),
        ]
    )
    pong = ScriptedModel(
        [
            handoff_turn("planner", "pong"),
            text_turn(),
            handoff_turn("planner", "pong2"),
            text_turn(),
            handoff_turn("planner", "pong3"),
            text_turn(),
        ]
    )
    models = {
        AgentId.PLANNER: ping,
        AgentId.INVESTIGATOR: pong,
        AgentId.DATA_ANALYST: ScriptedModel([text_turn()]),
        AgentId.CHALLENGER: ScriptedModel([text_turn()]),
    }
    result = run_research_swarm(
        "ping pong",
        models=models,
        mcp_tools=[],
        cfg=_cfg(
            swarm_repetitive_handoff_detection_window=4,
            swarm_repetitive_handoff_min_unique_agents=3,
            swarm_max_handoffs=8,
            swarm_max_iterations=8,
        ),
    )
    assert result.status == "failed"
    assert result.reason is not None
    assert "run.failed" in result.reason or result.raw.status.value == "failed"


def test_token_ceiling_stop_run_failed_semantics() -> None:
    models = {
        AgentId.PLANNER: ScriptedModel(
            [
                handoff_turn(
                    "investigator",
                    "go",
                    input_tokens=80,
                    output_tokens=20,
                ),
                text_turn(input_tokens=1, output_tokens=1),
            ]
        ),
        AgentId.INVESTIGATOR: ScriptedModel(
            [text_turn(input_tokens=50, output_tokens=50)]
        ),
        AgentId.DATA_ANALYST: ScriptedModel([text_turn()]),
        AgentId.CHALLENGER: ScriptedModel([text_turn()]),
    }
    result = run_research_swarm(
        "budget",
        models=models,
        mcp_tools=[],
        cfg=_cfg(swarm_max_tokens_per_run=100, swarm_max_cost_usd_per_run=10.0),
    )
    assert result.status == "failed"
    assert result.reason == "run.failed: token ceiling exceeded"
    assert result.accounting.total_tokens >= 100
