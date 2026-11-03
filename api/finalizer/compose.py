"""Compose ``answer.final`` from a policy-approved snapshot (no tools, no Swarm)."""

from __future__ import annotations

from datetime import UTC, datetime

from api.finalizer.policy import ApprovedSnapshot, SCIENTIFIC_GUARDRAIL
from axiom_research.events import AnswerFinal


def ensure_scientific_guardrail(text: str | None) -> str:
    """Guarantee the ReadMe scientific guardrail is present in Final Assessment text."""
    body = (text or "").strip()
    if SCIENTIFIC_GUARDRAIL in body:
        return body
    if body:
        return f"{body} {SCIENTIFIC_GUARDRAIL}"
    return SCIENTIFIC_GUARDRAIL


def compose_answer_final(
    approved: ApprovedSnapshot,
    *,
    session_id: str,
    run_id: str,
    ts: datetime | None = None,
) -> AnswerFinal:
    """Deterministic assessment text — rejected/insufficient never appear as facts.

    The scientific guardrail is always visible on ``answer.final`` (sticky panel).
    """
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

    uncertainty = ensure_scientific_guardrail(" ".join(approved.uncertainty_notes))

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
