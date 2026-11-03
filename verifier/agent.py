"""Independent Verifier agent — MCP read tools only; no ledger / claim writes."""

from __future__ import annotations

from typing import Any

from strands import Agent

from axiom_research.identities import AgentId
from axiom_research.llm.strands_gemini import build_gemini_model
from axiom_research.settings import Settings, settings

VERIFIER_FORBIDDEN_TOOLS: frozenset[str] = frozenset(
    {
        "upsert_source",
        "upsert_evidence",
        "upsert_claim",
        "upsert_calculation",
        "upsert_hypothesis",
        "attach_evidence_to_claim",
        "freeze_snapshot",
        "read_current_snapshot",
        # Local Swarm coordination must never appear on the Verifier.
        "handoff_to_agent",
    }
)

VERIFIER_PROMPT = """\
You are the Independent Verifier for AxiomResearch.
You re-check claim support using your own MCP tools only.
You never receive the Swarm transcript or other agents' conclusions as authority.
You cannot write to the Evidence Ledger or mutate research claims.

Return ONLY a JSON object with keys:
  claim_id, claim_fingerprint, claim_revision, status, source_refs, verified_revision
where status is one of:
  verified | rejected | insufficient_evidence | conflicting_evidence
source_refs must be concrete identifiers you checked (DOI, arXiv, MP id, dataset PID).
verified_revision must equal the claim_revision you were asked to check.
Do not invent peer-review or commercial readiness from a computation alone.
"""


def assert_verifier_tools_safe(tools: list[Any]) -> None:
    """Hard fail if any claim-mutating / Swarm tool sneaks into the Verifier."""
    names: set[str] = set()
    for tool in tools:
        for attr in ("tool_name", "name", "__name__"):
            value = getattr(tool, attr, None)
            if isinstance(value, str) and value:
                names.add(value)
                break
        else:
            spec = getattr(tool, "tool_spec", None) or getattr(tool, "spec", None)
            if isinstance(spec, dict) and spec.get("name"):
                names.add(str(spec["name"]))
    banned = names & VERIFIER_FORBIDDEN_TOOLS
    if banned:
        raise RuntimeError(
            "Verifier must not receive claim-mutating or Swarm tools: "
            + ", ".join(sorted(banned))
        )


def build_verifier_agent(
    context_id: str,
    *,
    mcp_tools: list[Any],
    model: Any | None = None,
    cfg: Settings | None = None,
) -> Agent:
    """Fresh agent per A2A context. ``context_id`` isolates callers."""
    del context_id  # reserved for future per-context session wiring
    assert_verifier_tools_safe(mcp_tools)
    return Agent(
        name=AgentId.VERIFIER.value,
        description=(
            "Independent scientific claim verifier. Re-fetches sources via MCP; "
            "returns verified|rejected|insufficient_evidence|conflicting_evidence."
        ),
        model=model if model is not None else build_gemini_model(cfg or settings),
        system_prompt=VERIFIER_PROMPT,
        tools=list(mcp_tools),
    )
