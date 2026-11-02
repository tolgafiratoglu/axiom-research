"""Per-agent tool allowlists — enforced in code, not only in prompts."""

from __future__ import annotations

from axiom_research.identities import AgentId

# Local ledger tool names exposed as Strands @tool wrappers.
PLANNER_LEDGER_TOOLS: frozenset[str] = frozenset()

INVESTIGATOR_LEDGER_TOOLS: frozenset[str] = frozenset(
    {
        "upsert_source",
        "upsert_evidence",
        "upsert_claim",
        "attach_evidence_to_claim",
        "get_claim",
        "read_current_snapshot",
    }
)

DATA_ANALYST_LEDGER_TOOLS: frozenset[str] = frozenset(
    {
        "get_claim",
        "get_hypothesis",
        "read_current_snapshot",
        "upsert_calculation",
        "upsert_claim",
        "attach_evidence_to_claim",
    }
)

CHALLENGER_LEDGER_TOOLS: frozenset[str] = frozenset(
    {
        "get_claim",
        "get_hypothesis",
        "read_current_snapshot",
        "upsert_hypothesis",
    }
)

# Deterministic local calc tool (Data Analyst only).
CALC_TOOL_NAME = "replay_calculate"

# Substrings that mark scientific MCP tools (Investigator only).
MCP_TOOL_MARKERS: tuple[str, ...] = (
    "openalex_",
    "crossref_",
    "arxiv_",
    "materials_project_",
    "pubchem_",
    "zenodo_",
    "datacite_",
    "server_info",
)

LEDGER_TOOLS_BY_AGENT: dict[AgentId, frozenset[str]] = {
    AgentId.PLANNER: PLANNER_LEDGER_TOOLS,
    AgentId.INVESTIGATOR: INVESTIGATOR_LEDGER_TOOLS,
    AgentId.DATA_ANALYST: DATA_ANALYST_LEDGER_TOOLS,
    AgentId.CHALLENGER: CHALLENGER_LEDGER_TOOLS,
}


def is_mcp_tool_name(name: str) -> bool:
    return any(marker in name for marker in MCP_TOOL_MARKERS)


def agent_tool_names(agent: object) -> set[str]:
    names = getattr(agent, "tool_names", None)
    if names is None:
        return set()
    return set(names)
