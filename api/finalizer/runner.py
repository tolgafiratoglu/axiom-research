"""Run Finalizer only after a passed verification gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from api.finalizer.compose import compose_answer_final
from api.finalizer.policy import approve_for_finalizer
from api.gate.runner import GateOutcome
from axiom_research.events import AnswerFinal, ServerMessage


@dataclass
class FinalizerOutcome:
    answer: AnswerFinal | None
    events: list[ServerMessage] = field(default_factory=list)
    reason: str | None = None

    @property
    def emitted_final(self) -> bool:
        return self.answer is not None


def run_finalizer(
    gate: GateOutcome,
    *,
    session_id: str,
    run_id: str,
    ts: datetime | None = None,
) -> FinalizerOutcome:
    """Compose ``answer.final`` from the gated snapshot. Gate fail → no answer."""
    when = ts or datetime.now(tz=UTC)
    if not gate.allow_finalizer:
        return FinalizerOutcome(
            answer=None,
            events=[],
            reason=gate.reason or "gate did not allow Finalizer",
        )

    approved = approve_for_finalizer(gate.snapshot)
    answer = compose_answer_final(
        approved,
        session_id=session_id,
        run_id=run_id,
        ts=when,
    )
    return FinalizerOutcome(answer=answer, events=[answer], reason=None)
