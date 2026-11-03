"""3.B — agent tool boundaries (mocked model + MCP stubs; no live Gemini/API)."""

from __future__ import annotations

from strands import tool

from api.ledger.tools import LedgerTools
from api.swarm.agents import build_swarm_agents
from api.swarm.policy import (
    CALC_TOOL_NAME,
    CHALLENGER_LEDGER_TOOLS,
    DATA_ANALYST_LEDGER_TOOLS,
    INVESTIGATOR_LEDGER_TOOLS,
    agent_tool_names,
    is_mcp_tool_name,
)
from axiom_research.identities import AgentId
from axiom_research.ledger_store import InMemoryLedgerStore


@tool(name="openalex_search_works", description="stub")
def _openalex_search_works(query: str) -> str:
    return query


@tool(name="materials_project_get_material", description="stub")
def _mp_get(material_id: str) -> str:
    return material_id


@tool(name="zenodo_get_record", description="stub")
def _zenodo_get(record_id: str) -> str:
    return record_id


@tool(name="datacite_resolve_doi", description="stub — must be filtered from Investigator")
def _datacite_resolve(doi: str) -> str:
    return doi


MCP_STUBS = [_openalex_search_works, _mp_get, _zenodo_get, _datacite_resolve]


def _agents():
    ledger = LedgerTools(
        InMemoryLedgerStore(), session_id="ses-3b", run_id="run-3b"
    )
    return build_swarm_agents(model=None, ledger=ledger, mcp_tools=MCP_STUBS)


def test_planner_has_no_mcp_and_no_ledger_writes() -> None:
    agents = _agents()
    names = agent_tool_names(agents[AgentId.PLANNER])
    assert names == set()
    assert not any(is_mcp_tool_name(n) for n in names)


def test_investigator_has_mcp_and_provenance_writes() -> None:
    agents = _agents()
    names = agent_tool_names(agents[AgentId.INVESTIGATOR])
    assert "openalex_search_works" in names
    assert "materials_project_get_material" in names
    assert "zenodo_get_record" in names
    assert "datacite_resolve_doi" not in names  # 9.3 Verifier dual path
    assert INVESTIGATOR_LEDGER_TOOLS <= names
    assert "upsert_hypothesis" not in names
    assert CALC_TOOL_NAME not in names


def test_data_analyst_has_no_mcp_and_has_calc() -> None:
    agents = _agents()
    names = agent_tool_names(agents[AgentId.DATA_ANALYST])
    assert not any(is_mcp_tool_name(n) for n in names)
    assert CALC_TOOL_NAME in names
    assert DATA_ANALYST_LEDGER_TOOLS <= names
    assert "upsert_source" not in names
    assert "upsert_hypothesis" not in names


def test_challenger_is_ledger_only_hypotheses() -> None:
    agents = _agents()
    names = agent_tool_names(agents[AgentId.CHALLENGER])
    assert names == set(CHALLENGER_LEDGER_TOOLS)
    assert not any(is_mcp_tool_name(n) for n in names)
    assert "upsert_source" not in names
    assert "upsert_claim" not in names
    assert CALC_TOOL_NAME not in names
