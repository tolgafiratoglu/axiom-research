"""9.3 — Verifier DataCite vs Investigator Zenodo for the same dataset PID."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from strands import tool

from api.ledger.tools import LedgerTools
from api.swarm.agents import build_investigator
from api.swarm.policy import agent_tool_names
from axiom_research.demo.pins import load_canonical_pins
from axiom_research.ledger_store import InMemoryLedgerStore
from axiom_research.mcp.dual_path import (
    assert_dual_path_tool_split,
    dual_path_dataset_doi,
    filter_mcp_tools_for_role,
    is_datacite_tool,
    is_zenodo_tool,
    tool_name,
)
from verifier.agent import VERIFIER_PROMPT, build_verifier_agent


@tool(name="zenodo_get_record", description="stub zenodo")
def _zenodo_get(record_id: str) -> str:
    return record_id


@tool(name="zenodo_search_records", description="stub zenodo search")
def _zenodo_search(query: str) -> str:
    return query


@tool(name="datacite_resolve_doi", description="stub datacite")
def _datacite(doi: str) -> str:
    return doi


@tool(name="openalex_get_work", description="stub lit")
def _openalex(work_id: str) -> str:
    return work_id


MCP_BOTH = [_openalex, _zenodo_get, _zenodo_search, _datacite]


def test_pinned_doi_is_shared_across_zenodo_and_datacite() -> None:
    pins = load_canonical_pins()
    assert pins.zenodo.doi == pins.datacite.doi
    assert dual_path_dataset_doi() == pins.zenodo.doi
    assert pins.zenodo.doi == "10.5281/zenodo.3233912"
    assert "zenodo_get_record" in pins.zenodo.tools
    assert "datacite_resolve_doi" in pins.datacite.tools


def test_filter_splits_zenodo_and_datacite() -> None:
    inv = {tool_name(t) for t in filter_mcp_tools_for_role(MCP_BOTH, "investigator")}
    ver = {tool_name(t) for t in filter_mcp_tools_for_role(MCP_BOTH, "verifier")}
    assert "zenodo_get_record" in inv
    assert "zenodo_search_records" in inv
    assert "datacite_resolve_doi" not in inv
    assert "datacite_resolve_doi" in ver
    assert "zenodo_get_record" not in ver
    assert "openalex_get_work" in inv and "openalex_get_work" in ver
    assert_dual_path_tool_split(inv, ver)


def test_investigator_agent_drops_datacite_tools() -> None:
    ledger = LedgerTools(InMemoryLedgerStore(), session_id="ses-9.3", run_id="run-9.3")
    agent = build_investigator(model=MagicMock(), ledger=ledger, mcp_tools=MCP_BOTH)
    names = agent_tool_names(agent)
    assert "zenodo_get_record" in names
    assert not any(is_datacite_tool(n) for n in names)


def test_verifier_agent_drops_zenodo_tools() -> None:
    agent = build_verifier_agent("ctx-9.3", mcp_tools=MCP_BOTH, model=MagicMock())
    names = set(agent.tool_names)
    assert "datacite_resolve_doi" in names
    assert not any(is_zenodo_tool(n) for n in names)
    assert "DataCite" in VERIFIER_PROMPT or "datacite_resolve_doi" in VERIFIER_PROMPT


def test_assert_dual_path_rejects_overlap() -> None:
    with pytest.raises(RuntimeError, match="datacite"):
        assert_dual_path_tool_split(
            {"zenodo_get_record", "datacite_resolve_doi"},
            {"datacite_resolve_doi"},
        )
    with pytest.raises(RuntimeError, match="zenodo"):
        assert_dual_path_tool_split(
            {"zenodo_get_record"},
            {"datacite_resolve_doi", "zenodo_get_record"},
        )
