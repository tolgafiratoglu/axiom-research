"""Postgres-backed Evidence Ledger store (JSONB payloads + indexed keys)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

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
from axiom_research.ledger_store import _fingerprint_payload, claim_body_fingerprint


def _dump(record: Any) -> dict[str, Any]:
    return record.model_dump(mode="json")


class PostgresLedgerStore:
    """Durable store using the 001_initial schema. Sessions/runs are ensured on write."""

    def __init__(self, database_url: str) -> None:
        self._url = database_url

    def _connect(self):
        return psycopg.connect(self._url, row_factory=dict_row)

    def ensure_session(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id)
                VALUES (%s)
                ON CONFLICT (session_id) DO UPDATE
                SET updated_at = now()
                """,
                (session_id,),
            )
            conn.commit()

    def ensure_run(self, session_id: str, run_id: str, *, question: str = "") -> None:
        self.ensure_session(session_id)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, session_id, question, status)
                VALUES (%s, %s, %s, 'running')
                ON CONFLICT (run_id) DO NOTHING
                """,
                (run_id, session_id, question),
            )
            conn.commit()

    def upsert_source(self, session_id: str, record: SourceRecord) -> SourceRecord:
        self.ensure_session(session_id)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT fingerprint, revision FROM sources WHERE source_id = %s",
                (record.source_id,),
            ).fetchone()
            stored = record.model_copy(deep=True)
            if existing and existing["fingerprint"] != stored.fingerprint:
                stored = stored.model_copy(update={"revision": existing["revision"] + 1})
            conn.execute(
                """
                INSERT INTO sources (
                    source_id, session_id, identifier, fingerprint, revision, payload
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_id) DO UPDATE SET
                    identifier = EXCLUDED.identifier,
                    fingerprint = EXCLUDED.fingerprint,
                    revision = EXCLUDED.revision,
                    payload = EXCLUDED.payload,
                    updated_at = now()
                """,
                (
                    stored.source_id,
                    session_id,
                    stored.identifier,
                    stored.fingerprint,
                    stored.revision,
                    Jsonb(_dump(stored)),
                ),
            )
            conn.commit()
            return stored.model_copy(deep=True)

    def upsert_evidence(self, session_id: str, record: EvidenceRecord) -> EvidenceRecord:
        self.ensure_session(session_id)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT fingerprint, revision FROM evidence WHERE evidence_id = %s",
                (record.evidence_id,),
            ).fetchone()
            stored = record.model_copy(deep=True)
            if existing and existing["fingerprint"] != stored.fingerprint:
                stored = stored.model_copy(update={"revision": existing["revision"] + 1})
            conn.execute(
                """
                INSERT INTO evidence (
                    evidence_id, session_id, source_id, kind, fingerprint, revision, payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (evidence_id) DO UPDATE SET
                    source_id = EXCLUDED.source_id,
                    kind = EXCLUDED.kind,
                    fingerprint = EXCLUDED.fingerprint,
                    revision = EXCLUDED.revision,
                    payload = EXCLUDED.payload,
                    updated_at = now()
                """,
                (
                    stored.evidence_id,
                    session_id,
                    stored.source_id,
                    stored.kind.value,
                    stored.fingerprint,
                    stored.revision,
                    Jsonb(_dump(stored)),
                ),
            )
            conn.commit()
            return stored.model_copy(deep=True)

    def upsert_claim(self, session_id: str, record: ClaimRecord) -> ClaimRecord:
        self.ensure_session(session_id)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT fingerprint, revision FROM claims WHERE claim_id = %s",
                (record.claim_id,),
            ).fetchone()
            stored = record.model_copy(deep=True)
            if existing and existing["fingerprint"] != stored.fingerprint:
                stored = stored.model_copy(
                    update={
                        "revision": existing["revision"] + 1,
                        "verification_status": VerificationStatus.PENDING,
                        "verified_revision": None,
                    }
                )
                conn.execute(
                    """
                    DELETE FROM verifications
                    WHERE claim_id = %s AND claim_fingerprint <> %s
                    """,
                    (stored.claim_id, stored.fingerprint),
                )
            conn.execute(
                """
                INSERT INTO claims (
                    claim_id, session_id, revision, fingerprint,
                    verification_status, verified_revision, payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (claim_id) DO UPDATE SET
                    revision = EXCLUDED.revision,
                    fingerprint = EXCLUDED.fingerprint,
                    verification_status = EXCLUDED.verification_status,
                    verified_revision = EXCLUDED.verified_revision,
                    payload = EXCLUDED.payload,
                    updated_at = now()
                """,
                (
                    stored.claim_id,
                    session_id,
                    stored.revision,
                    stored.fingerprint,
                    stored.verification_status.value,
                    stored.verified_revision,
                    Jsonb(_dump(stored)),
                ),
            )
            conn.execute(
                "DELETE FROM claim_evidence WHERE claim_id = %s",
                (stored.claim_id,),
            )
            for evidence_id in stored.evidence_ids:
                conn.execute(
                    """
                    INSERT INTO claim_evidence (claim_id, evidence_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (stored.claim_id, evidence_id),
                )
            conn.commit()
            return stored.model_copy(deep=True)

    def upsert_calculation(
        self, session_id: str, record: CalculationRecord
    ) -> CalculationRecord:
        self.ensure_session(session_id)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT fingerprint, revision FROM calculations WHERE calculation_id = %s",
                (record.calculation_id,),
            ).fetchone()
            stored = record.model_copy(deep=True)
            if existing and existing["fingerprint"] != stored.fingerprint:
                stored = stored.model_copy(update={"revision": existing["revision"] + 1})
            conn.execute(
                """
                INSERT INTO calculations (
                    calculation_id, session_id, fingerprint, revision, payload
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (calculation_id) DO UPDATE SET
                    fingerprint = EXCLUDED.fingerprint,
                    revision = EXCLUDED.revision,
                    payload = EXCLUDED.payload,
                    updated_at = now()
                """,
                (
                    stored.calculation_id,
                    session_id,
                    stored.fingerprint,
                    stored.revision,
                    Jsonb(_dump(stored)),
                ),
            )
            conn.commit()
            return stored.model_copy(deep=True)

    def upsert_hypothesis(
        self, session_id: str, record: HypothesisRecord
    ) -> HypothesisRecord:
        self.ensure_session(session_id)
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT fingerprint, revision FROM hypotheses WHERE hypothesis_id = %s",
                (record.hypothesis_id,),
            ).fetchone()
            stored = record.model_copy(deep=True)
            if existing and existing["fingerprint"] != stored.fingerprint:
                stored = stored.model_copy(update={"revision": existing["revision"] + 1})
            conn.execute(
                """
                INSERT INTO hypotheses (
                    hypothesis_id, session_id, fingerprint, revision, payload
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (hypothesis_id) DO UPDATE SET
                    fingerprint = EXCLUDED.fingerprint,
                    revision = EXCLUDED.revision,
                    payload = EXCLUDED.payload,
                    updated_at = now()
                """,
                (
                    stored.hypothesis_id,
                    session_id,
                    stored.fingerprint,
                    stored.revision,
                    Jsonb(_dump(stored)),
                ),
            )
            conn.commit()
            return stored.model_copy(deep=True)

    def upsert_verification(
        self, session_id: str, record: VerificationRecord
    ) -> VerificationRecord:
        claim = self.get_claim(session_id, record.claim_id)
        if claim is None:
            raise KeyError(f"claim not found: {record.claim_id}")
        if (
            record.claim_fingerprint != claim.fingerprint
            or record.claim_revision != claim.revision
        ):
            raise ValueError("verification bound to stale claim fingerprint/revision")
        stored = record.model_copy(deep=True)
        updated_claim = claim.model_copy(
            update={
                "verification_status": VerificationStatus(stored.status.value),
                "verified_revision": stored.verified_revision,
            }
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO verifications (
                    verification_id, session_id, claim_id, claim_revision,
                    claim_fingerprint, status, fingerprint, revision, payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (verification_id) DO UPDATE SET
                    claim_revision = EXCLUDED.claim_revision,
                    claim_fingerprint = EXCLUDED.claim_fingerprint,
                    status = EXCLUDED.status,
                    fingerprint = EXCLUDED.fingerprint,
                    revision = EXCLUDED.revision,
                    payload = EXCLUDED.payload,
                    updated_at = now()
                """,
                (
                    stored.verification_id,
                    session_id,
                    stored.claim_id,
                    stored.claim_revision,
                    stored.claim_fingerprint,
                    stored.status.value,
                    stored.fingerprint,
                    stored.revision,
                    Jsonb(_dump(stored)),
                ),
            )
            conn.execute(
                """
                UPDATE claims
                SET verification_status = %s,
                    verified_revision = %s,
                    payload = %s,
                    updated_at = now()
                WHERE claim_id = %s
                """,
                (
                    updated_claim.verification_status.value,
                    updated_claim.verified_revision,
                    Jsonb(_dump(updated_claim)),
                    updated_claim.claim_id,
                ),
            )
            conn.commit()
        return stored.model_copy(deep=True)

    def get_claim(self, session_id: str, claim_id: str) -> ClaimRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM claims WHERE claim_id = %s AND session_id = %s",
                (claim_id, session_id),
            ).fetchone()
        if row is None:
            return None
        return ClaimRecord.model_validate(row["payload"])

    def list_claims(self, session_id: str) -> list[ClaimRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM claims WHERE session_id = %s ORDER BY claim_id",
                (session_id,),
            ).fetchall()
        return [ClaimRecord.model_validate(r["payload"]) for r in rows]

    def get_hypothesis(
        self, session_id: str, hypothesis_id: str
    ) -> HypothesisRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM hypotheses WHERE hypothesis_id = %s AND session_id = %s",
                (hypothesis_id, session_id),
            ).fetchone()
        if row is None:
            return None
        return HypothesisRecord.model_validate(row["payload"])

    def get_evidence(
        self, session_id: str, evidence_id: str
    ) -> EvidenceRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM evidence WHERE evidence_id = %s AND session_id = %s",
                (evidence_id, session_id),
            ).fetchone()
        if row is None:
            return None
        return EvidenceRecord.model_validate(row["payload"])

    def current_verification_for_claim(
        self, session_id: str, claim_id: str
    ) -> VerificationRecord | None:
        claim = self.get_claim(session_id, claim_id)
        if claim is None:
            return None
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload FROM verifications
                WHERE session_id = %s
                  AND claim_id = %s
                  AND claim_fingerprint = %s
                  AND claim_revision = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (session_id, claim_id, claim.fingerprint, claim.revision),
            ).fetchone()
        if row is None:
            return None
        return VerificationRecord.model_validate(row["payload"])

    def attach_evidence(
        self, session_id: str, *, claim_id: str, evidence_id: str
    ) -> ClaimRecord:
        claim = self.get_claim(session_id, claim_id)
        if claim is None:
            raise KeyError(f"claim not found: {claim_id}")
        if self.get_evidence(session_id, evidence_id) is None:
            raise KeyError(f"evidence not found: {evidence_id}")
        evidence_ids = list(claim.evidence_ids)
        if evidence_id not in evidence_ids:
            evidence_ids.append(evidence_id)
        updated = claim.model_copy(
            update={
                "evidence_ids": evidence_ids,
                "fingerprint": claim_body_fingerprint(
                    claim.model_copy(update={"evidence_ids": evidence_ids})
                ),
            }
        )
        return self.upsert_claim(session_id, updated)

    def freeze_snapshot(
        self,
        *,
        snapshot_id: str,
        session_id: str,
        run_id: str,
        frozen_at: datetime | None = None,
    ) -> LedgerSnapshot:
        self.ensure_run(session_id, run_id)
        when = frozen_at or datetime.now(tz=UTC)
        with self._connect() as conn:
            sources = [
                SourceRecord.model_validate(r["payload"])
                for r in conn.execute(
                    "SELECT payload FROM sources WHERE session_id = %s",
                    (session_id,),
                ).fetchall()
            ]
            evidence = [
                EvidenceRecord.model_validate(r["payload"])
                for r in conn.execute(
                    "SELECT payload FROM evidence WHERE session_id = %s",
                    (session_id,),
                ).fetchall()
            ]
            claims = [
                ClaimRecord.model_validate(r["payload"])
                for r in conn.execute(
                    "SELECT payload FROM claims WHERE session_id = %s",
                    (session_id,),
                ).fetchall()
            ]
            calculations = [
                CalculationRecord.model_validate(r["payload"])
                for r in conn.execute(
                    "SELECT payload FROM calculations WHERE session_id = %s",
                    (session_id,),
                ).fetchall()
            ]
            hypotheses = [
                HypothesisRecord.model_validate(r["payload"])
                for r in conn.execute(
                    "SELECT payload FROM hypotheses WHERE session_id = %s",
                    (session_id,),
                ).fetchall()
            ]
            verifications = [
                VerificationRecord.model_validate(r["payload"])
                for r in conn.execute(
                    "SELECT payload FROM verifications WHERE session_id = %s",
                    (session_id,),
                ).fetchall()
            ]
            payload = {
                "sources": [_dump(r) for r in sources],
                "evidence": [_dump(r) for r in evidence],
                "claims": [_dump(r) for r in claims],
                "calculations": [_dump(r) for r in calculations],
                "hypotheses": [_dump(r) for r in hypotheses],
                "verifications": [_dump(r) for r in verifications],
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
            conn.execute(
                """
                INSERT INTO ledger_snapshots (
                    snapshot_id, session_id, run_id, frozen_at, fingerprint, payload
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (snapshot_id) DO UPDATE SET
                    fingerprint = EXCLUDED.fingerprint,
                    payload = EXCLUDED.payload,
                    frozen_at = EXCLUDED.frozen_at
                """,
                (
                    snapshot.snapshot_id,
                    session_id,
                    run_id,
                    when,
                    snapshot.fingerprint,
                    Jsonb(_dump(snapshot)),
                ),
            )
            conn.commit()
            return snapshot.model_copy(deep=True)

    def get_snapshot(
        self, session_id: str, snapshot_id: str
    ) -> LedgerSnapshot | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT payload FROM ledger_snapshots
                WHERE snapshot_id = %s AND session_id = %s
                """,
                (snapshot_id, session_id),
            ).fetchone()
        if row is None:
            return None
        return LedgerSnapshot.model_validate(row["payload"])

    def current_snapshot(
        self, session_id: str, *, run_id: str | None = None
    ) -> LedgerSnapshot | None:
        with self._connect() as conn:
            if run_id is None:
                row = conn.execute(
                    """
                    SELECT payload FROM ledger_snapshots
                    WHERE session_id = %s
                    ORDER BY frozen_at DESC, created_at DESC
                    LIMIT 1
                    """,
                    (session_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT payload FROM ledger_snapshots
                    WHERE session_id = %s AND run_id = %s
                    ORDER BY frozen_at DESC, created_at DESC
                    LIMIT 1
                    """,
                    (session_id, run_id),
                ).fetchone()
        if row is None:
            return None
        return LedgerSnapshot.model_validate(row["payload"])
