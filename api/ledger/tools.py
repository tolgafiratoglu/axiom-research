"""Local ledger tools for Swarm agents — writes go through policy + store."""

from __future__ import annotations

from datetime import datetime

from axiom_research.calculations import assert_replayable
from axiom_research.ledger import (
    CalculationRecord,
    ClaimRecord,
    EvidenceRecord,
    HypothesisRecord,
    LedgerSnapshot,
    SourceRecord,
    VerificationRecord,
)
from axiom_research.ledger_policy import assert_claim_units
from axiom_research.ledger_store import LedgerStore


class LedgerTools:
    """Session/run-scoped facade used by api agents (and unit tests)."""

    def __init__(
        self,
        store: LedgerStore,
        *,
        session_id: str,
        run_id: str,
    ) -> None:
        self._store = store
        self.session_id = session_id
        self.run_id = run_id

    def upsert_source(self, record: SourceRecord) -> SourceRecord:
        return self._store.upsert_source(self.session_id, record)

    def upsert_evidence(self, record: EvidenceRecord) -> EvidenceRecord:
        return self._store.upsert_evidence(self.session_id, record)

    def upsert_claim(self, record: ClaimRecord) -> ClaimRecord:
        assert_claim_units(record)
        return self._store.upsert_claim(self.session_id, record)

    def upsert_calculation(self, record: CalculationRecord) -> CalculationRecord:
        assert_replayable(record)
        return self._store.upsert_calculation(self.session_id, record)

    def upsert_hypothesis(self, record: HypothesisRecord) -> HypothesisRecord:
        return self._store.upsert_hypothesis(self.session_id, record)

    def upsert_verification(self, record: VerificationRecord) -> VerificationRecord:
        return self._store.upsert_verification(self.session_id, record)

    def attach_evidence_to_claim(self, *, claim_id: str, evidence_id: str) -> ClaimRecord:
        return self._store.attach_evidence(
            self.session_id, claim_id=claim_id, evidence_id=evidence_id
        )

    def freeze_snapshot(
        self, snapshot_id: str, *, frozen_at: datetime | None = None
    ) -> LedgerSnapshot:
        return self._store.freeze_snapshot(
            snapshot_id=snapshot_id,
            session_id=self.session_id,
            run_id=self.run_id,
            frozen_at=frozen_at,
        )

    def read_current_snapshot(self) -> LedgerSnapshot | None:
        return self._store.current_snapshot(self.session_id, run_id=self.run_id)

    def get_claim(self, claim_id: str) -> ClaimRecord | None:
        """Claims only — never returns a hypothesis row."""
        return self._store.get_claim(self.session_id, claim_id)

    def get_hypothesis(self, hypothesis_id: str) -> HypothesisRecord | None:
        return self._store.get_hypothesis(self.session_id, hypothesis_id)

    def current_verification_for_claim(
        self, claim_id: str
    ) -> VerificationRecord | None:
        return self._store.current_verification_for_claim(self.session_id, claim_id)
