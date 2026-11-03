"""Tool-less Finalizer agent — outside Swarm; snapshot-only prompt context."""

from __future__ import annotations

from typing import Any

from strands import Agent

from axiom_research.identities import AgentId
from axiom_research.untrusted import UNTRUSTED_DATA_NOTICE

FINALIZER_PROMPT = f"""\
You are the Finalizer for AxiomResearch. You have no tools and no MCP access.
You read only the policy-approved Evidence Ledger snapshot provided in the
user message. Do not invent sources, peer review, or commercial readiness.
State only verified claims as established facts. Label rejected, insufficient,
conflicting, or stale items explicitly — never as facts.
Scientific guardrail: A calculated material property is not proof of
manufacturing feasibility, operational safety, cost competitiveness or
market adoption. Never equate computed properties with experimental proof
or commercial readiness.
{UNTRUSTED_DATA_NOTICE}
"""

FINALIZER_DESCRIPTION = (
    "Tool-less final assessment from a policy-approved ledger snapshot only."
)


def build_finalizer_agent(*, model: Any) -> Agent:
    """Strictly tool-less Strands agent (live path). Unit tests use compose()."""
    return Agent(
        name=AgentId.FINALIZER.value,
        description=FINALIZER_DESCRIPTION,
        model=model,
        system_prompt=FINALIZER_PROMPT,
        tools=[],
    )


def assert_finalizer_tool_less(agent: Agent) -> None:
    names = set(getattr(agent, "tool_names", []) or [])
    if names:
        raise RuntimeError(f"Finalizer must be tool-less; got tools: {sorted(names)}")
