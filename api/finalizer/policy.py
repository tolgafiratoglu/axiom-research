"""Policy-approve a gated ledger snapshot for the tool-less Finalizer."""

from __future__ import annotations

from dataclasses import dataclass, field

from axiom_research.ledger import (
    ClaimRecord,
    EvidenceKind,
    LedgerSnapshot,
    VerificationRecord,
    VerificationVerdict,
)

# ReadMe / DEMO scientific guardrail — must appear on every answer.final (9.4).
SCIENTIFIC_GUARDRAIL = (
    "Scientific guardrail: A calculated material property is not proof of "
    "manufacturing feasibility, operational safety, cost competitiveness or "
    "market adoption."
)
# Backward-compatible alias used by older tests and imports.
COMMERCIAL_READINESS_GUARDRAIL = SCIENTIFIC_GUARDRAIL


@dataclass(frozen=True)
class LabeledClaim:
    claim: ClaimRecord
    label: str


@dataclass
class ApprovedSnapshot:
    """Only ``established`` may be stated as facts in ``answer.final``."""

    snapshot: LedgerSnapshot
    established: list[ClaimRecord] = field(default_factory=list)
    disputed: list[LabeledClaim] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)


def _current_verification(
    snapshot: LedgerSnapshot, claim: ClaimRecord
) -> VerificationRecord | None:
    for ver in snapshot.verifications:
        if (
            ver.claim_id == claim.claim_id
            and ver.claim_fingerprint == claim.fingerprint
            and ver.claim_revision == claim.revision
            and ver.verified_revision == claim.revision
        ):
            return ver
    return None


def _label_for_verdict(status: VerificationVerdict) -> str:
    return {
        VerificationVerdict.REJECTED: "rejected",
        VerificationVerdict.INSUFFICIENT_EVIDENCE: "insufficient_evidence",
        VerificationVerdict.CONFLICTING_EVIDENCE: "conflicting_evidence",
        VerificationVerdict.VERIFIED: "verified",
    }[status]


def approve_for_finalizer(snapshot: LedgerSnapshot) -> ApprovedSnapshot:
    """Partition claims: verified facts vs labeled non-facts (never silent)."""
    established: list[ClaimRecord] = []
    disputed: list[LabeledClaim] = []
    citations: list[str] = []
    notes: list[str] = []

    for claim in snapshot.claims:
        ver = _current_verification(snapshot, claim)
        if ver is None:
            disputed.append(
                LabeledClaim(
                    claim=claim,
                    label="stale_or_unverified",
                )
            )
            continue
        if ver.status is VerificationVerdict.VERIFIED:
            established.append(claim)
            for ref in claim.source_refs:
                if ref not in citations:
                    citations.append(ref)
        else:
            disputed.append(
                LabeledClaim(claim=claim, label=_label_for_verdict(ver.status))
            )

    has_computed = any(
        c.evidence_kind is EvidenceKind.COMPUTED_PROPERTY for c in snapshot.claims
    ) or any(
        e.kind is EvidenceKind.COMPUTED_PROPERTY for e in snapshot.evidence
    )
    # Always attach the product scientific guardrail when any ledger claim exists.
    if snapshot.claims and SCIENTIFIC_GUARDRAIL not in notes:
        notes.append(SCIENTIFIC_GUARDRAIL)
    elif has_computed and SCIENTIFIC_GUARDRAIL not in notes:
        notes.append(SCIENTIFIC_GUARDRAIL)
    if not established and snapshot.claims:
        notes.append("No independently verified claims support a confident conclusion.")

    return ApprovedSnapshot(
        snapshot=snapshot,
        established=established,
        disputed=disputed,
        citations=citations,
        uncertainty_notes=notes,
    )
