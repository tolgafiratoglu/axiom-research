"""Eval run modes for three-way comparison (8.4).

Same tools and budgets across modes so Swarm is not credited for the Verifier.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from axiom_research.settings import Settings, settings


class EvalMode(StrEnum):
    """Unbundled comparison arms (ReadMe evaluation section)."""

    ONE_AGENT_NO_GATE = "one_agent_no_gate"
    ONE_AGENT_GATE = "one_agent_gate"
    SWARM_GATE = "swarm_gate"


# Fixed order for reports / CI.
COMPARISON_MODES: tuple[EvalMode, ...] = (
    EvalMode.ONE_AGENT_NO_GATE,
    EvalMode.ONE_AGENT_GATE,
    EvalMode.SWARM_GATE,
)


class SharedBudgets(BaseModel):
    """Identical cost/time ceilings for every comparison arm."""

    model_config = ConfigDict(extra="forbid")

    max_handoffs: int
    max_iterations: int
    execution_timeout_seconds: float
    node_timeout_seconds: float
    max_tokens_per_run: int
    max_cost_usd_per_run: float
    # Declared tool surface — same MCP servers for all arms.
    mcp_servers: tuple[str, ...] = Field(
        default=("mcp-literature", "mcp-materials", "mcp-research-data")
    )

    @classmethod
    def from_settings(cls, cfg: Settings | None = None) -> SharedBudgets:
        ready = cfg or settings
        return cls(
            max_handoffs=ready.swarm_max_handoffs,
            max_iterations=ready.swarm_max_iterations,
            execution_timeout_seconds=ready.swarm_execution_timeout_seconds,
            node_timeout_seconds=ready.swarm_node_timeout_seconds,
            max_tokens_per_run=ready.swarm_max_tokens_per_run,
            max_cost_usd_per_run=ready.swarm_max_cost_usd_per_run,
        )


def mode_label(mode: EvalMode) -> str:
    return {
        EvalMode.ONE_AGENT_NO_GATE: "one agent + same MCP, no gate",
        EvalMode.ONE_AGENT_GATE: "one agent + same MCP + A2A gate",
        EvalMode.SWARM_GATE: "Swarm + A2A gate",
    }[mode]
