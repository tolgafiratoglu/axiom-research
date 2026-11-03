"""5.B — deterministic gate: freeze, A2A verify, stale/schema/unreachable (mocked)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from api.gate import GateOutcome, MockVerifierClient, run_verification_gate
from axiom_research.identities import AgentId
from axiom_research.ledger import (
    ClaimRecord,
    EvidenceKind,
    EvidenceRecord,
    SourceRecord,
    VerificationRecord,
    VerificationStatus,
    VerificationVerdict,
)
from axiom_research.ledger_store import InMemoryLedgerStore
from axiom_research.verification import VerificationRequest, VerificationResult

NOW = datetime(2026, 11, 2, tzinfo=UTC)
SESSION = "ses-gate-1"
RUN = "run-gate-1"


def _seed(store: InMemoryLedgerStore) -> ClaimRecord:
    store.upsert_source(
        SESSION,
        SourceRecord(
            source_id="src-1",
            identifier="doi:10.example/1",
            retrieved_at=NOW,
            provider="crossref",
            fingerprint="fp-src-1",
        ),
    )
    store.upsert_evidence(
        SESSION,
        EvidenceRecord(
            evidence_id="ev-1",
            source_id="src-1",
            kind=EvidenceKind.COMPUTED_PROPERTY,
            statement="Reported band gap.",
            unit="eV",
            retrieved_at=NOW,
            author_agent=AgentId.INVESTIGATOR,
            fingerprint="fp-ev-1",
        ),
    )
    claim = ClaimRecord(
        claim_id="claim-1",
        revision=1,
        statement="Material property is in a stated range.",
        author_agent=AgentId.DATA_ANALYST,
        evidence_ids=["ev-1"],
        source_refs=["doi:10.example/1"],
        evidence_kind=EvidenceKind.COMPUTED_PROPERTY,
        value=1.2,
        unit="eV",
        verification_status=VerificationStatus.PENDING,
        fingerprint="fp-claim-1",
    )
    return store.upsert_claim(SESSION, claim)


def _ok_result(request: VerificationRequest) -> VerificationResult:
    return VerificationResult(
        claim_id=request.claim_id,
        claim_fingerprint=request.claim_fingerprint,
        claim_revision=request.claim_revision,
        status=VerificationVerdict.VERIFIED,
        source_refs=list(request.source_refs),
        verified_revision=request.claim_revision,
    )


@pytest.mark.asyncio
async def test_gate_freezes_and_verifies_pending_claim() -> None:
    store = InMemoryLedgerStore()
    _seed(store)
    client = MockVerifierClient(handler=lambda req: _ok_result(req))

    outcome = await run_verification_gate(
        store,
        session_id=SESSION,
        run_id=RUN,
        client=client,
        snapshot_id="snap-ok",
        frozen_at=NOW,
    )

    assert isinstance(outcome, GateOutcome)
    assert outcome.passed is True
    assert outcome.allow_finalizer is True
    assert len(client.calls) == 1
    assert client.calls[0].claim_id == "claim-1"
    assert "swarm_transcript" not in client.calls[0].model_dump()
    types = [e.type for e in outcome.events]
    assert types == ["a2a.verification", "verification.gate"]
    assert outcome.events[-1].passed is True
    assert store.current_verification_for_claim(SESSION, "claim-1") is not None
    assert store.get_claim(SESSION, "claim-1").verification_status == VerificationStatus.VERIFIED


@pytest.mark.asyncio
async def test_gate_skips_already_verified_current_revision() -> None:
    store = InMemoryLedgerStore()
    claim = _seed(store)
    store.upsert_verification(
        SESSION,
        VerificationRecord(
            verification_id="ver-existing",
            claim_id=claim.claim_id,
            claim_revision=claim.revision,
            claim_fingerprint=claim.fingerprint,
            status=VerificationVerdict.VERIFIED,
            source_refs=list(claim.source_refs),
            verified_revision=claim.revision,
            fingerprint="fp-ver-existing",
        ),
    )
    client = MockVerifierClient()

    outcome = await run_verification_gate(
        store,
        session_id=SESSION,
        run_id=RUN,
        client=client,
        snapshot_id="snap-skip",
        frozen_at=NOW,
    )

    assert outcome.passed is True
    assert client.calls == []
    assert [e.type for e in outcome.events] == ["verification.gate"]


@pytest.mark.asyncio
async def test_gate_rejects_stale_verification_fingerprint() -> None:
    store = InMemoryLedgerStore()
    _seed(store)

    async def stale(req: VerificationRequest) -> VerificationResult:
        return VerificationResult(
            claim_id=req.claim_id,
            claim_fingerprint="fp-old-stale",
            claim_revision=req.claim_revision,
            status=VerificationVerdict.VERIFIED,
            source_refs=list(req.source_refs),
            verified_revision=req.claim_revision,
        )

    client = MockVerifierClient(handler=stale)
    outcome = await run_verification_gate(
        store,
        session_id=SESSION,
        run_id=RUN,
        client=client,
        frozen_at=NOW,
    )

    assert outcome.passed is False
    assert outcome.allow_finalizer is False
    assert "stale verification" in (outcome.reason or "")
    assert outcome.events[-1].type == "verification.gate"
    assert outcome.events[-1].passed is False


@pytest.mark.asyncio
async def test_gate_rejects_schema_invalid_result() -> None:
    store = InMemoryLedgerStore()
    _seed(store)

    async def bad(_req: VerificationRequest) -> VerificationResult:
        raise ValueError("verifier JSON was not an object")

    client = MockVerifierClient(handler=bad)
    outcome = await run_verification_gate(
        store,
        session_id=SESSION,
        run_id=RUN,
        client=client,
        frozen_at=NOW,
    )

    assert outcome.passed is False
    assert outcome.allow_finalizer is False
    assert "schema-invalid" in (outcome.reason or "")
    assert outcome.events[-1].type == "verification.gate"
    assert outcome.events[-1].passed is False


@pytest.mark.asyncio
async def test_gate_rejects_transport_success_without_science() -> None:
    store = InMemoryLedgerStore()
    _seed(store)

    async def ungrounded(req: VerificationRequest) -> VerificationResult:
        # Transport OK + enum verdict, but cites none of the claim sources.
        return VerificationResult(
            claim_id=req.claim_id,
            claim_fingerprint=req.claim_fingerprint,
            claim_revision=req.claim_revision,
            status=VerificationVerdict.VERIFIED,
            source_refs=["doi:10.unrelated/999"],
            verified_revision=req.claim_revision,
        )

    client = MockVerifierClient(handler=ungrounded)
    outcome = await run_verification_gate(
        store,
        session_id=SESSION,
        run_id=RUN,
        client=client,
        frozen_at=NOW,
    )

    assert outcome.passed is False
    assert outcome.allow_finalizer is False
    assert "transport-success-without-science" in (outcome.reason or "")
    assert outcome.events[-1].type == "verification.gate"
    assert outcome.events[-1].passed is False


@pytest.mark.asyncio
async def test_gate_unreachable_verifier_emits_run_failed() -> None:
    store = InMemoryLedgerStore()
    _seed(store)
    client = MockVerifierClient(unreachable=True)

    outcome = await run_verification_gate(
        store,
        session_id=SESSION,
        run_id=RUN,
        client=client,
        frozen_at=NOW,
    )

    assert outcome.passed is False
    assert outcome.allow_finalizer is False
    assert "unreachable" in (outcome.reason or "").lower()
    assert outcome.events[-1].type == "run.failed"
