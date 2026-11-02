"""In-process Evidence Ledger store (durable Postgres adapter comes with api tools).

Revision bumps invalidate verification bound to an older claim fingerprint.
Snapshot freeze copies current revisions immutably for gate / Finalizer.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from axiom_research.ledger import (
    CalculationRecord,
    ClaimRecord,
    EvidenceRecord,
    HypothesisRecord,
    LedgerSnapshot,
    SourceRecord,
    VerificationRecord,
    VerificationStatus,
)


def _fingerprint_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass
class SessionLedger:
    session_id: str
    sources: dict[str, SourceRecord] = field(default_factory=dict)
    evidence: dict[str, EvidenceRecord] = field(default_factory=dict)
    claims: dict[str, ClaimRecord] = field(default_factory=dict)
    calculations: dict[str, CalculationRecord] = field(default_factory=dict)
    hypotheses: dict[str, HypothesisRecord] = field(default_factory=dict)
    verifications: dict[str, VerificationRecord] = field(default_factory=dict)
    snapshots: dict[str, LedgerSnapshot] = field(default_factory=dict)


class InMemoryLedgerStore:
    """Session-scoped ledger with freeze + stale-verification rules."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionLedger] = {}

    def _session(self, session_id: str) -> SessionLedger:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionLedger(session_id=session_id)
        return self._sessions[session_id]

    def upsert_source(self, session_id: str, record: SourceRecord) -> SourceRecord:
        session = self._session(session_id)
        existing = session.sources.get(record.source_id)
        stored = record.model_copy(deep=True)
        if existing is not None and existing.fingerprint != stored.fingerprint:
            stored = stored.model_copy(update={"revision": existing.revision + 1})
        session.sources[stored.source_id] = stored
        return stored.model_copy(deep=True)

    def upsert_evidence(self, session_id: str, record: EvidenceRecord) -> EvidenceRecord:
        session = self._session(session_id)
        existing = session.evidence.get(record.evidence_id)
        stored = record.model_copy(deep=True)
        if existing is not None and existing.fingerprint != stored.fingerprint:
            stored = stored.model_copy(update={"revision": existing.revision + 1})
        session.evidence[stored.evidence_id] = stored
        return stored.model_copy(deep=True)

    def upsert_claim(self, session_id: str, record: ClaimRecord) -> ClaimRecord:
        session = self._session(session_id)
        existing = session.claims.get(record.claim_id)
        stored = record.model_copy(deep=True)
        if existing is not None and existing.fingerprint != stored.fingerprint:
            stored = stored.model_copy(
                update={
                    "revision": existing.revision + 1,
                    "verification_status": VerificationStatus.PENDING,
                    "verified_revision": None,
                }
            )
            self._drop_stale_verifications(
                session,
                claim_id=stored.claim_id,
                claim_fingerprint=stored.fingerprint,
            )
        session.claims[stored.claim_id] = stored
        return stored.model_copy(deep=True)

    def upsert_calculation(
        self, session_id: str, record: CalculationRecord
    ) -> CalculationRecord:
        session = self._session(session_id)
        existing = session.calculations.get(record.calculation_id)
        stored = record.model_copy(deep=True)
        if existing is not None and existing.fingerprint != stored.fingerprint:
            stored = stored.model_copy(update={"revision": existing.revision + 1})
        session.calculations[stored.calculation_id] = stored
        return stored.model_copy(deep=True)

    def upsert_hypothesis(
        self, session_id: str, record: HypothesisRecord
    ) -> HypothesisRecord:
        session = self._session(session_id)
        existing = session.hypotheses.get(record.hypothesis_id)
        stored = record.model_copy(deep=True)
        if existing is not None and existing.fingerprint != stored.fingerprint:
            stored = stored.model_copy(update={"revision": existing.revision + 1})
        session.hypotheses[stored.hypothesis_id] = stored
        return stored.model_copy(deep=True)

    def upsert_verification(
        self, session_id: str, record: VerificationRecord
    ) -> VerificationRecord:
        session = self._session(session_id)
        claim = session.claims.get(record.claim_id)
        if claim is None:
            raise KeyError(f"claim not found: {record.claim_id}")
        if (
            record.claim_fingerprint != claim.fingerprint
            or record.claim_revision != claim.revision
        ):
            raise ValueError(
                "verification bound to stale claim fingerprint/revision"
            )
        stored = record.model_copy(deep=True)
        session.verifications[stored.verification_id] = stored
        session.claims[claim.claim_id] = claim.model_copy(
            update={
                "verification_status": VerificationStatus(stored.status.value),
                "verified_revision": stored.verified_revision,
            }
        )
        return stored.model_copy(deep=True)

    def get_claim(self, session_id: str, claim_id: str) -> ClaimRecord | None:
        session = self._session(session_id)
        claim = session.claims.get(claim_id)
        return None if claim is None else claim.model_copy(deep=True)

    def get_hypothesis(self, session_id: str, hypothesis_id: str) -> HypothesisRecord | None:
        session = self._session(session_id)
        hyp = session.hypotheses.get(hypothesis_id)
        return None if hyp is None else hyp.model_copy(deep=True)

    def current_verification_for_claim(
        self, session_id: str, claim_id: str
    ) -> VerificationRecord | None:
        session = self._session(session_id)
        claim = session.claims.get(claim_id)
        if claim is None:
            return None
        for ver in session.verifications.values():
            if (
                ver.claim_id == claim_id
                and ver.claim_fingerprint == claim.fingerprint
                and ver.claim_revision == claim.revision
            ):
                return ver.model_copy(deep=True)
        return None

    def freeze_snapshot(
        self,
        *,
        snapshot_id: str,
        session_id: str,
        run_id: str,
        frozen_at: datetime | None = None,
    ) -> LedgerSnapshot:
        session = self._session(session_id)
        when = frozen_at or datetime.now(tz=UTC)
        sources = [copy.deepcopy(r) for r in session.sources.values()]
        evidence = [copy.deepcopy(r) for r in session.evidence.values()]
        claims = [copy.deepcopy(r) for r in session.claims.values()]
        calculations = [copy.deepcopy(r) for r in session.calculations.values()]
        hypotheses = [copy.deepcopy(r) for r in session.hypotheses.values()]
        verifications = [copy.deepcopy(r) for r in session.verifications.values()]
        payload = {
            "sources": [r.model_dump(mode="json") for r in sources],
            "evidence": [r.model_dump(mode="json") for r in evidence],
            "claims": [r.model_dump(mode="json") for r in claims],
            "calculations": [r.model_dump(mode="json") for r in calculations],
            "hypotheses": [r.model_dump(mode="json") for r in hypotheses],
            "verifications": [r.model_dump(mode="json") for r in verifications],
        }
        snapshot = LedgerSnapshot(
            snapshot_id=snapshot_id,
            session_id=session_id,
            run_id=run_id,
            frozen_at=when,
            sources=sources,
            evidence=evidence,
            claims=claims,
            calculations=calculations,
            hypotheses=hypotheses,
            verifications=verifications,
            fingerprint=_fingerprint_payload(payload),
        )
        # Store an independent deep copy so later ledger edits cannot mutate freeze.
        session.snapshots[snapshot_id] = snapshot.model_copy(deep=True)
        return snapshot.model_copy(deep=True)

    def get_snapshot(self, session_id: str, snapshot_id: str) -> LedgerSnapshot | None:
        session = self._session(session_id)
        snap = session.snapshots.get(snapshot_id)
        return None if snap is None else snap.model_copy(deep=True)

    def _drop_stale_verifications(
        self,
        session: SessionLedger,
        *,
        claim_id: str,
        claim_fingerprint: str,
    ) -> None:
        stale = [
            vid
            for vid, ver in session.verifications.items()
            if ver.claim_id == claim_id and ver.claim_fingerprint != claim_fingerprint
        ]
        for vid in stale:
            del session.verifications[vid]
