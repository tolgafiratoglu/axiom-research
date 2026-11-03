"""Compose ``answer.final`` from a policy-approved snapshot (no tools, no Swarm)."""

from __future__ import annotations

from datetime import UTC, datetime

from api.finalizer.policy import ApprovedSnapshot, COMMERCIAL_READINESS_GUARDRAIL
from axiom_research.events import AnswerFinal


def compose_answer_final(
    approved: ApprovedSnapshot,
    *,
    session_id: str,
    run_id: str,
    ts: datetime | None = None,
) -> AnswerFinal:
    """Deterministic assessment text — rejected/insufficient never appear as facts."""
    when = ts or datetime.now(tz=UTC)
    if approved.established:
        conclusions = "\n".join(
            f"- {c.statement}" for c in approved.established
        )
    else:
        conclusions = (
            "Insufficient independently verified evidence for a confident assessment."
        )

    disputed = [
        f"[{item.label}] {item.claim.statement}" for item in approved.disputed
    ]

    notes = list(approved.uncertainty_notes)
    if COMMERCIAL_READINESS_GUARDRAIL not in notes:
        # Always surface the product guardrail when any claim existed.
        if approved.snapshot.claims:
            notes.append(COMMERCIAL_READINESS_GUARDRAIL)
    uncertainty = " ".join(notes) if notes else None

    return AnswerFinal(
        event_id="",
        ts=when,
        session_id=session_id,
        run_id=run_id,
        conclusions=conclusions,
        citations=list(approved.citations),
        disputed=disputed,
        uncertainty=uncertainty,
    )
