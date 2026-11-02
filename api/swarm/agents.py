"""Local Swarm specialist agents with hard tool boundaries."""

from __future__ import annotations

from typing import Any

from strands import Agent

from api.ledger.tools import LedgerTools
from api.swarm.calc_tool import build_replay_calculate_tool
from api.swarm.ledger_agent_tools import build_ledger_agent_tools
from api.swarm.policy import (
    CHALLENGER_LEDGER_TOOLS,
    DATA_ANALYST_LEDGER_TOOLS,
    INVESTIGATOR_LEDGER_TOOLS,
    PLANNER_LEDGER_TOOLS,
)
from api.swarm.prompts import DESCRIPTIONS, PROMPTS
from axiom_research.identities import AgentId


def _agent(
    agent_id: AgentId,
    *,
    model: Any,
    tools: list[Any],
) -> Agent:
    return Agent(
        name=agent_id.value,
        description=DESCRIPTIONS[agent_id],
        model=model,
        system_prompt=PROMPTS[agent_id],
        tools=tools,
    )


def build_planner(*, model: Any, ledger: LedgerTools | None = None) -> Agent:
    """No MCP; no ledger writes (run scope only via Swarm context / handoff)."""
    tools = (
        build_ledger_agent_tools(ledger, PLANNER_LEDGER_TOOLS) if ledger is not None else []
    )
    return _agent(AgentId.PLANNER, model=model, tools=tools)


def build_investigator(
    *,
    model: Any,
    ledger: LedgerTools,
    mcp_tools: list[Any],
) -> Agent:
    """Literature + materials + research-data MCP; owns provenance ledger writes."""
    tools = [
        *mcp_tools,
        *build_ledger_agent_tools(ledger, INVESTIGATOR_LEDGER_TOOLS),
    ]
    return _agent(AgentId.INVESTIGATOR, model=model, tools=tools)


def build_data_analyst(*, model: Any, ledger: LedgerTools) -> Agent:
    """No MCP; ledger read + deterministic calculation + replayable calc upsert."""
    tools = [
        *build_ledger_agent_tools(ledger, DATA_ANALYST_LEDGER_TOOLS),
        build_replay_calculate_tool(),
    ]
    return _agent(AgentId.DATA_ANALYST, model=model, tools=tools)


def build_challenger(*, model: Any, ledger: LedgerTools) -> Agent:
    """Ledger only; hypotheses / contradictions; no domain expansion or MCP."""
    tools = build_ledger_agent_tools(ledger, CHALLENGER_LEDGER_TOOLS)
    return _agent(AgentId.CHALLENGER, model=model, tools=tools)


def build_swarm_agents(
    *,
    model: Any,
    ledger: LedgerTools,
    mcp_tools: list[Any],
) -> dict[AgentId, Agent]:
    """Construct the four local Swarm specialists with role tool sets."""
    return {
        AgentId.PLANNER: build_planner(model=model, ledger=ledger),
        AgentId.INVESTIGATOR: build_investigator(
            model=model, ledger=ledger, mcp_tools=mcp_tools
        ),
        AgentId.DATA_ANALYST: build_data_analyst(model=model, ledger=ledger),
        AgentId.CHALLENGER: build_challenger(model=model, ledger=ledger),
    }
