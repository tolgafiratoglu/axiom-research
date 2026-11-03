"""9.4 — scientific guardrail visible on every Final Assessment (answer.final)."""

from __future__ import annotations

from datetime import UTC, datetime

from api.finalizer import (
    SCIENTIFIC_GUARDRAIL,
    approve_for_finalizer,
    ensure_scientific_guardrail,
    run_finalizer,
)
from api.finalizer.compose import compose_answer_final
from api.gate import GateOutcome
from axiom_research.identities import AgentId
from axiom_research.ledger import (
    ClaimRecord,
    EvidenceKind,
    LedgerSnapshot,
    VerificationRecord,
    VerificationStatus,
    VerificationVerdict,
)

NOW = datetime(2026, 11, 3, tzinfo=UTC)
README_GUARDRAIL_PHRASE = (
    "not proof of manufacturing feasibility, operational safety, "
    "cost competitiveness or market adoption"
)


def _snap(*, with_claim: bool = True, verified: bool = True) -> LedgerSnapshot:
    claims = []
    verifications = []
    if with_claim:
        claim = ClaimRecord(
            claim_id="claim-g",
            revision=1,
            statement="Computed band gap is in range.",
            author_agent=AgentId.DATA_ANALYST,
            evidence_ids=["ev-1"],
            source_refs=["materials-project:mp-19017"],
            evidence_kind=EvidenceKind.COMPUTED_PROPERTY,
            value=3.5,
            unit="eV",
            verification_status=VerificationStatus.PENDING,
            fingerprint="fp-g1",
        )
        claims.append(claim)
        if verified:
            verifications.append(
                VerificationRecord(
                    verification_id="ver-g",
                    claim_id="claim-g",
                    claim_revision=1,
                    claim_fingerprint="fp-g1",
                    status=VerificationVerdict.VERIFIED,
                    source_refs=["materials-project:mp-19017"],
                    verified_revision=1,
                    fingerprint="fp-verg",
                )
            )
    return LedgerSnapshot(
        snapshot_id="snap-g",
        session_id="ses-g",
        run_id="run-g",
        frozen_at=NOW,
        sources=[],
        evidence=[],
        claims=claims,
        calculations=[],
        hypotheses=[],
        verifications=verifications,
        fingerprint="fp-snap-g",
    )


def test_scientific_guardrail_matches_readme_wording() -> None:
    assert "Scientific guardrail:" in SCIENTIFIC_GUARDRAIL
    assert README_GUARDRAIL_PHRASE in SCIENTIFIC_GUARDRAIL


def test_answer_final_always_includes_guardrail_in_uncertainty() -> None:
    approved = approve_for_finalizer(_snap(verified=True))
    answer = compose_answer_final(
        approved, session_id="ses-g", run_id="run-g", ts=NOW
    )
    assert answer.uncertainty is not None
    assert SCIENTIFIC_GUARDRAIL in answer.uncertainty
    assert README_GUARDRAIL_PHRASE in answer.uncertainty


def test_guardrail_present_even_when_no_established_claims() -> None:
    approved = approve_for_finalizer(_snap(verified=False))
    answer = compose_answer_final(
        approved, session_id="ses-g", run_id="run-g", ts=NOW
    )
    assert SCIENTIFIC_GUARDRAIL in (answer.uncertainty or "")


def test_guardrail_present_on_empty_snapshot_final() -> None:
    approved = approve_for_finalizer(_snap(with_claim=False))
    answer = compose_answer_final(
        approved, session_id="ses-g", run_id="run-g", ts=NOW
    )
    # Compose always ensures visibility even if policy notes were empty.
    assert SCIENTIFIC_GUARDRAIL in (answer.uncertainty or "")
    assert ensure_scientific_guardrail(None) == SCIENTIFIC_GUARDRAIL


def test_run_finalizer_surfaces_guardrail_on_sticky_event() -> None:
    gate = GateOutcome(
        passed=True,
        allow_finalizer=True,
        snapshot=_snap(verified=True),
    )
    outcome = run_finalizer(gate, session_id="ses-g", run_id="run-g", ts=NOW)
    assert outcome.answer is not None
    assert SCIENTIFIC_GUARDRAIL in (outcome.answer.uncertainty or "")
