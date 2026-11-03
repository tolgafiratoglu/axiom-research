"""Per-agent-turn token/cost accounting for Strands model calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from axiom_research.settings import Settings, settings


@dataclass(frozen=True)
class TurnUsage:
    agent_id: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float


@dataclass
class TokenCostAccounting:
    """Hook that records usage after each model call (one Swarm agent turn slice)."""

    input_usd_per_mtok: float = field(default_factory=lambda: settings.gemini_input_usd_per_mtok)
    output_usd_per_mtok: float = field(
        default_factory=lambda: settings.gemini_output_usd_per_mtok
    )
    turns: list[TurnUsage] = field(default_factory=list)
    max_tokens: int | None = None
    max_cost_usd: float | None = None
    exceeded_reason: str | None = None

    @classmethod
    def from_settings(cls, cfg: Settings | None = None) -> TokenCostAccounting:
        ready = cfg or settings
        return cls(
            input_usd_per_mtok=ready.gemini_input_usd_per_mtok,
            output_usd_per_mtok=ready.gemini_output_usd_per_mtok,
            max_tokens=ready.swarm_max_tokens_per_run,
            max_cost_usd=ready.swarm_max_cost_usd_per_run,
        )

    @property
    def total_tokens(self) -> int:
        return sum(t.total_tokens for t in self.turns)

    @property
    def total_cost_usd(self) -> float:
        return sum(t.cost_usd for t in self.turns)

    def estimate_cost_usd(self, *, input_tokens: int, output_tokens: int) -> float:
        return (
            (input_tokens / 1_000_000) * self.input_usd_per_mtok
            + (output_tokens / 1_000_000) * self.output_usd_per_mtok
        )

    def record_turn(
        self,
        *,
        agent_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> TurnUsage:
        total = input_tokens + output_tokens
        turn = TurnUsage(
            agent_id=agent_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total,
            cost_usd=self.estimate_cost_usd(
                input_tokens=input_tokens, output_tokens=output_tokens
            ),
        )
        self.turns.append(turn)
        return turn

    def attach(self, agent: Any) -> None:
        """Register on a Strands ``Agent`` (or any object with ``add_hook``)."""
        try:
            from strands.hooks import AfterModelCallEvent, BeforeModelCallEvent
        except ImportError:  # pragma: no cover
            from strands.hooks.events import (  # type: ignore[no-redef]
                AfterModelCallEvent,
                BeforeModelCallEvent,
            )

        agent.add_hook(self.before_model_call, BeforeModelCallEvent)
        agent.add_hook(self.after_model_call, AfterModelCallEvent)

    def ceiling_reason(self) -> str | None:
        if self.max_tokens is not None and self.total_tokens >= self.max_tokens:
            return "run.failed: token ceiling exceeded"
        if self.max_cost_usd is not None and self.total_cost_usd >= self.max_cost_usd:
            return "run.failed: cost ceiling exceeded"
        return None

    def before_model_call(self, event: Any) -> None:
        reason = self.exceeded_reason or self.ceiling_reason()
        if reason:
            self.exceeded_reason = reason
            event.cancel = reason

    def after_model_call(self, event: Any) -> None:
        usage = usage_from_model_event(event)
        if usage is None:
            return
        agent = getattr(event, "agent", None)
        agent_id = str(getattr(agent, "name", None) or "agent")
        self.record_turn(
            agent_id=agent_id,
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
        )
        reason = self.ceiling_reason()
        if reason:
            self.exceeded_reason = reason



def usage_from_model_event(event: Any) -> dict[str, int] | None:
    """Pull token counts from AfterModelCallEvent stop_response / message metadata."""
    stop = getattr(event, "stop_response", None)
    if stop is None:
        return None
    message = getattr(stop, "message", None)
    meta: Any = None
    if isinstance(message, dict):
        meta = message.get("metadata")
    elif message is not None:
        meta = getattr(message, "metadata", None)
    if meta is None:
        meta = getattr(stop, "metadata", None)
    if not isinstance(meta, dict):
        return None
    usage = meta.get("usage")
    if not isinstance(usage, dict):
        return None
    input_tokens = int(usage.get("inputTokens") or usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("outputTokens") or usage.get("output_tokens") or 0)
    if input_tokens == 0 and output_tokens == 0:
        return None
    return {"input_tokens": input_tokens, "output_tokens": output_tokens}
