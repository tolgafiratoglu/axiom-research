from datetime import UTC, datetime

from axiom_research import (
    SERVER_EVENT_TYPES,
    AgentId,
    AuditEvent,
    CalculationRecord,
    ClaimRecord,
    EvidenceKind,
    EvidenceRecord,
    HypothesisRecord,
    SourceRecord,
    VerificationRecord,
    VerificationStatus,
    VerificationVerdict,
    parse_client,
    parse_server,
)

README_CLAIM = {
    "claim_id": "claim-042",
    "revision": 3,
    "statement": "The cited calculation reports a material property in a specified range.",
    "author_agent": "data_analyst",
    "evidence_ids": ["ev-101", "ev-102"],
    "source_refs": ["materials-project:<record-id>", "doi:<identifier>"],
    "evidence_kind": "computed_property",
    "method": "As recorded by original source",
    "value": None,
    "unit": None,
    "verification_status": "pending",
    "verified_revision": None,
    "limitations": ["A calculation is not experimental or commercial validation"],
    "fingerprint": "fp-claim-042-r3",
}


def test_agent_identities() -> None:
    assert {member.value for member in AgentId} == {
        "planner",
        "investigator",
        "data_analyst",
        "challenger",
        "verifier",
        "finalizer",
    }


def test_client_envelopes() -> None:
    ask = parse_client({"type": "ask", "question": "Can solid-state batteries replace Li-ion?"})
    assert ask.type == "ask"
    cancel = parse_client({"type": "cancel", "run_id": "run-1"})
    assert cancel.type == "cancel"
    beat = parse_client({"type": "heartbeat", "last_event_id": "evt-9"})
    assert beat.last_event_id == "evt-9"


def test_server_event_types_match_readme() -> None:
    assert SERVER_EVENT_TYPES == (
        "agent.started",
        "agent.handoff",
        "tool.summary",
        "evidence.updated",
        "hypothesis.created",
        "a2a.verification",
        "verification.gate",
        "answer.final",
        "run.failed",
    )


def test_server_envelopes_import() -> None:
    base = {
        "event_id": "evt-1",
        "ts": datetime(2026, 11, 2, tzinfo=UTC),
        "session_id": "ses-1",
        "run_id": "run-1",
    }
    started = parse_server({**base, "type": "agent.started", "agent_id": "planner"})
    assert started.agent_id is AgentId.PLANNER
    handoff = parse_server(
        {
            **base,
            "type": "agent.handoff",
            "from_agent": "planner",
            "to_agent": "investigator",
        }
    )
    assert handoff.to_agent is AgentId.INVESTIGATOR
    parse_server(
        {
            **base,
            "type": "tool.summary",
            "agent_id": "investigator",
            "tool_name": "openalex.search_works",
            "summary": "4 works",
            "ok": True,
        }
    )
    parse_server({**base, "type": "evidence.updated", "claim_id": "claim-042", "revision": 3})
    parse_server(
        {
            **base,
            "type": "hypothesis.created",
            "hypothesis_id": "hyp-1",
            "author_agent": "challenger",
        }
    )
    parse_server(
        {
            **base,
            "type": "a2a.verification",
            "verification_id": "ver-1",
            "claim_id": "claim-042",
            "status": "verified",
            "verified_revision": 3,
        }
    )
    parse_server({**base, "type": "verification.gate", "passed": True})
    final = parse_server(
        {
            **base,
            "type": "answer.final",
            "conclusions": "Insufficient evidence for commercial replacement.",
            "citations": ["doi:10.example/1"],
            "disputed": [],
            "uncertainty": "Computed properties are not manufacturing proof.",
        }
    )
    assert final.type == "answer.final"
    parse_server({**base, "type": "run.failed", "reason": "verifier unreachable"})
    parse_server({**base, "type": "heartbeat", "last_event_id": "evt-1"})


def test_ledger_records_import() -> None:
    now = datetime(2026, 11, 2, tzinfo=UTC)
    SourceRecord(
        source_id="src-1",
        identifier="doi:10.example/1",
        url="https://doi.org/10.example/1",
        version="1",
        retrieved_at=now,
        license="CC-BY-4.0",
        provider="crossref",
        fingerprint="fp-src-1",
    )
    EvidenceRecord(
        evidence_id="ev-101",
        source_id="src-1",
        kind=EvidenceKind.COMPUTED_PROPERTY,
        statement="Reported band gap in the cited calculation.",
        method="DFT as recorded by source",
        unit="eV",
        retrieved_at=now,
        author_agent=AgentId.INVESTIGATOR,
        fingerprint="fp-ev-101",
    )
    claim = ClaimRecord.model_validate(README_CLAIM)
    assert claim.author_agent is AgentId.DATA_ANALYST
    assert claim.verification_status is VerificationStatus.PENDING
    CalculationRecord(
        calculation_id="calc-1",
        inputs={"a": 1.0, "b": 2.0},
        formula="a / b",
        normalization=None,
        unit="1",
        output=0.5,
        author_agent=AgentId.DATA_ANALYST,
        fingerprint="fp-calc-1",
    )
    HypothesisRecord(
        hypothesis_id="hyp-1",
        statement="A single lab result does not establish commercial readiness.",
        author_agent=AgentId.CHALLENGER,
        related_claim_ids=["claim-042"],
        fingerprint="fp-hyp-1",
    )
    VerificationRecord(
        verification_id="ver-1",
        claim_id="claim-042",
        claim_revision=3,
        claim_fingerprint="fp-claim-042-r3",
        status=VerificationVerdict.VERIFIED,
        source_refs=["doi:10.example/1"],
        verified_revision=3,
        fingerprint="fp-ver-1",
    )
    AuditEvent(
        audit_id="aud-1",
        ts=now,
        session_id="ses-1",
        run_id="run-1",
        action="snapshot.freeze",
        agent_id=None,
        fingerprint="fp-aud-1",
    )
