"""5.C — Finalizer: policy snapshot, no fake answer on gate fail (mocked)."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from api.finalizer import (
    COMMERCIAL_READINESS_GUARDRAIL,
    approve_for_finalizer,
    assert_finalizer_tool_less,
    build_finalizer_agent,
    run_finalizer,
)
from api.gate import GateOutcome, MockVerifierClient, run_verification_gate
from axiom_research.identities import AgentId
from axiom_research.ledger import (
    ClaimRecord,
    EvidenceKind,
    EvidenceRecord,
    LedgerSnapshot,
    SourceRecord,
    VerificationRecord,
    VerificationStatus,
    VerificationVerdict,
)
from axiom_research.ledger_store import InMemoryLedgerStore
from axiom_research.verification import VerificationRequest, VerificationResult

NOW = datetime(2026, 11, 2, tzinfo=UTC)
SESSION = "ses-fin-1"
RUN = "run-fin-1"


def _seed(
    store: InMemoryLedgerStore,
    *,
    session_id: str = SESSION,
    claim_id: str = "claim-1",
    statement: str = "Material property is in a stated range.",
    fingerprint: str = "fp-claim-1",
    status: VerificationStatus = VerificationStatus.PENDING,
) -> ClaimRecord:
    store.upsert_source(
        session_id,
        SourceRecord(
            source_id="src-1",
            identifier="doi:10.example/1",
            retrieved_at=NOW,
            provider="crossref",
            fingerprint="fp-src-1",
        ),
    )
    store.upsert_evidence(
        session_id,
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
    return store.upsert_claim(
        session_id,
        ClaimRecord(
            claim_id=claim_id,
            revision=1,
            statement=statement,
            author_agent=AgentId.DATA_ANALYST,
            evidence_ids=["ev-1"],
            source_refs=["doi:10.example/1"],
            evidence_kind=EvidenceKind.COMPUTED_PROPERTY,
            value=1.2,
            unit="eV",
            verification_status=status,
            fingerprint=fingerprint,
        ),
    )


def _ok(req: VerificationRequest) -> VerificationResult:
    return VerificationResult(
        claim_id=req.claim_id,
        claim_fingerprint=req.claim_fingerprint,
        claim_revision=req.claim_revision,
        status=VerificationVerdict.VERIFIED,
        source_refs=list(req.source_refs),
        verified_revision=req.claim_revision,
    )


def test_finalizer_agent_is_tool_less() -> None:
    agent = build_finalizer_agent(model=MagicMock(name="model"))
    assert agent.name == AgentId.FINALIZER.value
    assert_finalizer_tool_less(agent)
    assert set(agent.tool_names) == set()


@pytest.mark.asyncio
async def test_gate_pass_emits_answer_final_with_commercial_guardrail() -> None:
    store = InMemoryLedgerStore()
    _seed(store)
    gate = await run_verification_gate(
        store,
        session_id=SESSION,
        run_id=RUN,
        client=MockVerifierClient(handler=_ok),
        frozen_at=NOW,
    )
    assert gate.allow_finalizer is True

    outcome = run_finalizer(gate, session_id=SESSION, run_id=RUN, ts=NOW)
    assert outcome.emitted_final is True
    assert outcome.answer is not None
    assert outcome.answer.type == "answer.final"
    assert "Material property is in a stated range." in outcome.answer.conclusions
    assert "doi:10.example/1" in outcome.answer.citations
    assert COMMERCIAL_READINESS_GUARDRAIL in (outcome.answer.uncertainty or "")


@pytest.mark.asyncio
async def test_rejected_claims_cannot_appear_as_facts() -> None:
    store = InMemoryLedgerStore()
    rejected_text = "This claim must not be stated as established fact."
    _seed(store, statement=rejected_text)

    async def reject(req: VerificationRequest) -> VerificationResult:
        return VerificationResult(
            claim_id=req.claim_id,
            claim_fingerprint=req.claim_fingerprint,
            claim_revision=req.claim_revision,
            status=VerificationVerdict.REJECTED,
            source_refs=list(req.source_refs),
            verified_revision=req.claim_revision,
        )

    gate = await run_verification_gate(
        store,
        session_id=SESSION,
        run_id=RUN,
        client=MockVerifierClient(handler=reject),
        frozen_at=NOW,
    )
    outcome = run_finalizer(gate, session_id=SESSION, run_id=RUN, ts=NOW)
    assert outcome.answer is not None
    # Not listed as an established bullet fact.
    assert outcome.answer.conclusions.startswith("Insufficient")
    assert rejected_text not in outcome.answer.conclusions
    assert any(
        rejected_text in d and d.startswith("[rejected]")
        for d in outcome.answer.disputed
    )


def test_stale_verification_regression_not_treated_as_fact() -> None:
    """Verification bound to an older fingerprint must not establish the claim."""
    claim = ClaimRecord(
        claim_id="claim-stale",
        revision=2,
        statement="Updated claim text after edit.",
        author_agent=AgentId.DATA_ANALYST,
        evidence_ids=["ev-1"],
        source_refs=["doi:10.example/1"],
        evidence_kind=EvidenceKind.COMPUTED_PROPERTY,
        value=1.5,
        unit="eV",
        verification_status=VerificationStatus.PENDING,
        fingerprint="fp-claim-r2",
    )
    stale_ver = VerificationRecord(
        verification_id="ver-old",
        claim_id="claim-stale",
        claim_revision=1,
        claim_fingerprint="fp-claim-r1",
        status=VerificationVerdict.VERIFIED,
        source_refs=["doi:10.example/1"],
        verified_revision=1,
        fingerprint="fp-ver-old",
    )
    snap = LedgerSnapshot(
        snapshot_id="snap-stale",
        session_id=SESSION,
        run_id=RUN,
        frozen_at=NOW,
        sources=[],
        evidence=[],
        claims=[claim],
        calculations=[],
        hypotheses=[],
        verifications=[stale_ver],
        fingerprint="fp-snap-stale",
    )
    approved = approve_for_finalizer(snap)
    assert approved.established == []
    assert len(approved.disputed) == 1
    assert approved.disputed[0].label == "stale_or_unverified"

    gate = GateOutcome(
        passed=True,
        allow_finalizer=True,
        snapshot=snap,
    )
    outcome = run_finalizer(gate, session_id=SESSION, run_id=RUN, ts=NOW)
    assert outcome.answer is not None
    assert "Updated claim text after edit." not in outcome.answer.conclusions
    assert any("stale_or_unverified" in d for d in outcome.answer.disputed)


@pytest.mark.asyncio
async def test_gate_fail_does_not_produce_fake_answer() -> None:
    store = InMemoryLedgerStore()
    _seed(store)
    gate = await run_verification_gate(
        store,
        session_id=SESSION,
        run_id=RUN,
        client=MockVerifierClient(unreachable=True),
        frozen_at=NOW,
    )
    assert gate.allow_finalizer is False
    assert any(e.type == "run.failed" for e in gate.events)

    outcome = run_finalizer(gate, session_id=SESSION, run_id=RUN, ts=NOW)
    assert outcome.emitted_final is False
    assert outcome.answer is None
    assert outcome.events == []
    assert "gate" in (outcome.reason or "").lower() or "unreachable" in (
        outcome.reason or ""
    ).lower()


def test_ws_ask_gate_finalizer_mocked_e2e() -> None:
    """Phase 5 exit: mocked ask → gate → answer.final over WS (no live APIs)."""
    from collections.abc import AsyncIterator

    from fastapi.testclient import TestClient

    from api.main import create_app
    from api.ws.hub import RunContext, SessionHub
    from axiom_research.events import AgentStarted, ServerMessage

    async def factory(ctx: RunContext) -> AsyncIterator[ServerMessage]:
        yield AgentStarted(
            event_id="",
            ts=NOW,
            session_id=ctx.session_id,
            run_id=ctx.run_id,
            agent_id=AgentId.PLANNER,
        )
        assert ctx.verifier_client is not None
        gate = await run_verification_gate(
            ctx.store,
            session_id=ctx.session_id,
            run_id=ctx.run_id,
            client=ctx.verifier_client,
            frozen_at=NOW,
        )
        for event in gate.events:
            yield event
        for event in run_finalizer(
            gate, session_id=ctx.session_id, run_id=ctx.run_id, ts=NOW
        ).events:
            yield event

    hub = SessionHub(run_factory=factory)
    app = create_app(hub=hub)
    client = TestClient(app)

    with client.websocket_connect("/ws/session") as ws:
        hello = ws.receive_json()
        session_id = hello["session_id"]
        session = hub.get_or_create(session_id)
        _seed(session.store, session_id=session_id)
        session.verifier_client = MockVerifierClient(handler=_ok)
        ws.send_json({"type": "ask", "question": "What do sources support?"})

        types: list[str] = []
        for _ in range(20):
            msg = ws.receive_json()
            if msg.get("type") == "heartbeat":
                continue
            types.append(msg["type"])
            if msg["type"] == "answer.final":
                assert "Material property" in msg["conclusions"]
                assert COMMERCIAL_READINESS_GUARDRAIL in (msg.get("uncertainty") or "")
                break
        assert "a2a.verification" in types
        assert "verification.gate" in types
        assert "answer.final" in types
