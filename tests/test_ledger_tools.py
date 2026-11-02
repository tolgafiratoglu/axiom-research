"""2.4–2.6 — ledger tools: policy, replayable calc, stale verification (mocked store)."""

from datetime import UTC, datetime

import pytest

from api.ledger.tools import LedgerTools
from axiom_research.calculations import CalculationError
from axiom_research.identities import AgentId
from axiom_research.ledger import (
    CalculationRecord,
    ClaimRecord,
    EvidenceKind,
    EvidenceRecord,
    HypothesisRecord,
    SourceRecord,
    VerificationRecord,
    VerificationStatus,
    VerificationVerdict,
)
from axiom_research.ledger_policy import LedgerPolicyError
from axiom_research.ledger_store import InMemoryLedgerStore

NOW = datetime(2026, 11, 2, tzinfo=UTC)
SESSION = "ses-tools-1"
RUN = "run-tools-1"


def _tools(store: InMemoryLedgerStore | None = None) -> LedgerTools:
    return LedgerTools(store or InMemoryLedgerStore(), session_id=SESSION, run_id=RUN)


def _seed(tools: LedgerTools) -> None:
    tools.upsert_source(
        SourceRecord(
            source_id="src-1",
            identifier="doi:10.example/1",
            retrieved_at=NOW,
            provider="crossref",
            fingerprint="fp-src-1",
        )
    )
    tools.upsert_evidence(
        EvidenceRecord(
            evidence_id="ev-1",
            source_id="src-1",
            kind=EvidenceKind.COMPUTED_PROPERTY,
            statement="Reported band gap.",
            unit="eV",
            retrieved_at=NOW,
            author_agent=AgentId.INVESTIGATOR,
            fingerprint="fp-ev-1",
        )
    )


def _claim(**overrides: object) -> ClaimRecord:
    data: dict[str, object] = {
        "claim_id": "claim-1",
        "revision": 1,
        "statement": "Material property is in a stated range.",
        "author_agent": AgentId.DATA_ANALYST,
        "evidence_ids": ["ev-1"],
        "source_refs": ["doi:10.example/1"],
        "evidence_kind": EvidenceKind.COMPUTED_PROPERTY,
        "value": 1.2,
        "unit": "eV",
        "verification_status": VerificationStatus.PENDING,
        "fingerprint": "fp-claim-1",
    }
    data.update(overrides)
    return ClaimRecord.model_validate(data)


def test_stale_verification_after_edit() -> None:
    tools = _tools()
    _seed(tools)
    tools.upsert_claim(_claim())
    tools.upsert_verification(
        VerificationRecord(
            verification_id="ver-1",
            claim_id="claim-1",
            claim_revision=1,
            claim_fingerprint="fp-claim-1",
            status=VerificationVerdict.VERIFIED,
            source_refs=["doi:10.example/1"],
            verified_revision=1,
            fingerprint="fp-ver-1",
        )
    )
    assert tools.current_verification_for_claim("claim-1") is not None

    tools.upsert_evidence(
        EvidenceRecord(
            evidence_id="ev-2",
            source_id="src-1",
            kind=EvidenceKind.COMPUTED_PROPERTY,
            statement="Alternate reported value.",
            unit="eV",
            retrieved_at=NOW,
            author_agent=AgentId.INVESTIGATOR,
            fingerprint="fp-ev-2",
        )
    )
    updated = tools.attach_evidence_to_claim(claim_id="claim-1", evidence_id="ev-2")
    assert updated.revision == 2
    assert updated.verification_status is VerificationStatus.PENDING
    assert tools.current_verification_for_claim("claim-1") is None


def test_hypothesis_cannot_be_read_as_claim() -> None:
    tools = _tools()
    tools.upsert_hypothesis(
        HypothesisRecord(
            hypothesis_id="hyp-1",
            statement="Single-lab result is not commercial readiness.",
            author_agent=AgentId.CHALLENGER,
            fingerprint="fp-hyp-1",
        )
    )
    assert tools.get_hypothesis("hyp-1") is not None
    assert tools.get_claim("hyp-1") is None


def test_missing_units_rejected_on_numeric_claims() -> None:
    tools = _tools()
    _seed(tools)
    with pytest.raises(LedgerPolicyError, match="unit"):
        tools.upsert_claim(_claim(unit=None))


def test_calculation_stores_replayable_inputs_formula_units_output() -> None:
    tools = _tools()
    stored = tools.upsert_calculation(
        CalculationRecord(
            calculation_id="calc-1",
            inputs={"a": 4.0, "b": 2.0},
            formula="a / b",
            unit="eV",
            output=2.0,
            author_agent=AgentId.DATA_ANALYST,
            fingerprint="fp-calc-1",
        )
    )
    assert stored.unit == "eV"
    assert stored.inputs == {"a": 4.0, "b": 2.0}

    with pytest.raises(CalculationError, match="does not match replay"):
        tools.upsert_calculation(
            CalculationRecord(
                calculation_id="calc-bad",
                inputs={"a": 4.0, "b": 2.0},
                formula="a / b",
                unit="eV",
                output=9.0,
                author_agent=AgentId.DATA_ANALYST,
                fingerprint="fp-calc-bad",
            )
        )


def test_freeze_and_read_current_snapshot() -> None:
    tools = _tools()
    _seed(tools)
    tools.upsert_claim(_claim())
    frozen = tools.freeze_snapshot("snap-1", frozen_at=NOW)
    current = tools.read_current_snapshot()
    assert current is not None
    assert current.snapshot_id == frozen.snapshot_id
    assert current.fingerprint == frozen.fingerprint
    assert len(current.claims) == 1
