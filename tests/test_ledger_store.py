"""2.2 / 2.3 — snapshot freeze and stale verification invalidation (in-memory)."""

from datetime import UTC, datetime

from axiom_research.identities import AgentId
from axiom_research.ledger import (
    ClaimRecord,
    EvidenceKind,
    EvidenceRecord,
    HypothesisRecord,
    SourceRecord,
    VerificationRecord,
    VerificationStatus,
    VerificationVerdict,
)
from axiom_research.ledger_store import InMemoryLedgerStore

NOW = datetime(2026, 11, 2, tzinfo=UTC)
SESSION = "ses-1"


def _source() -> SourceRecord:
    return SourceRecord(
        source_id="src-1",
        identifier="doi:10.example/1",
        url="https://doi.org/10.example/1",
        retrieved_at=NOW,
        provider="crossref",
        fingerprint="fp-src-1",
    )


def _evidence() -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="ev-1",
        source_id="src-1",
        kind=EvidenceKind.COMPUTED_PROPERTY,
        statement="Reported band gap.",
        unit="eV",
        retrieved_at=NOW,
        author_agent=AgentId.INVESTIGATOR,
        fingerprint="fp-ev-1",
    )


def _claim(*, revision: int = 1, fingerprint: str = "fp-claim-1") -> ClaimRecord:
    return ClaimRecord(
        claim_id="claim-1",
        revision=revision,
        statement="Material property is in a stated range.",
        author_agent=AgentId.DATA_ANALYST,
        evidence_ids=["ev-1"],
        source_refs=["doi:10.example/1"],
        evidence_kind=EvidenceKind.COMPUTED_PROPERTY,
        unit="eV",
        verification_status=VerificationStatus.PENDING,
        fingerprint=fingerprint,
    )


def test_freeze_snapshot_is_immutable_copy() -> None:
    store = InMemoryLedgerStore()
    store.upsert_source(SESSION, _source())
    store.upsert_evidence(SESSION, _evidence())
    store.upsert_claim(SESSION, _claim())

    snap = store.freeze_snapshot(
        snapshot_id="snap-1",
        session_id=SESSION,
        run_id="run-1",
        frozen_at=NOW,
    )
    assert snap.fingerprint
    assert len(snap.claims) == 1
    assert snap.claims[0].revision == 1

    store.upsert_claim(
        SESSION,
        _claim(revision=1, fingerprint="fp-claim-1-edited"),
    )
    frozen = store.get_snapshot(SESSION, "snap-1")
    assert frozen is not None
    assert frozen.claims[0].fingerprint == "fp-claim-1"
    assert frozen.claims[0].revision == 1
    assert store.get_claim(SESSION, "claim-1").fingerprint == "fp-claim-1-edited"


def test_revision_increment_invalidates_verification() -> None:
    store = InMemoryLedgerStore()
    store.upsert_source(SESSION, _source())
    store.upsert_evidence(SESSION, _evidence())
    store.upsert_claim(SESSION, _claim())
    store.upsert_verification(
        SESSION,
        VerificationRecord(
            verification_id="ver-1",
            claim_id="claim-1",
            claim_revision=1,
            claim_fingerprint="fp-claim-1",
            status=VerificationVerdict.VERIFIED,
            source_refs=["doi:10.example/1"],
            verified_revision=1,
            fingerprint="fp-ver-1",
        ),
    )
    assert store.current_verification_for_claim(SESSION, "claim-1") is not None
    claim = store.get_claim(SESSION, "claim-1")
    assert claim is not None
    assert claim.verification_status is VerificationStatus.VERIFIED

    updated = store.upsert_claim(
        SESSION,
        _claim(revision=1, fingerprint="fp-claim-2"),
    )
    assert updated.revision == 2
    assert updated.verification_status is VerificationStatus.PENDING
    assert updated.verified_revision is None
    assert store.current_verification_for_claim(SESSION, "claim-1") is None


def test_hypothesis_is_not_a_claim() -> None:
    store = InMemoryLedgerStore()
    store.upsert_hypothesis(
        SESSION,
        HypothesisRecord(
            hypothesis_id="hyp-1",
            statement="Single-lab result is not commercial readiness.",
            author_agent=AgentId.CHALLENGER,
            fingerprint="fp-hyp-1",
        ),
    )
    assert store.get_hypothesis(SESSION, "hyp-1") is not None
    assert store.get_claim(SESSION, "hyp-1") is None
