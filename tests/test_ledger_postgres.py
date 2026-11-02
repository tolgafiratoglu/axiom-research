"""Phase 2 exit — Postgres round-trip (operator: compose up postgres + migrate).

Skipped unless AXIOM_LEDGER_PG_TEST=1. Agent unit path is tests/test_ledger_tools.py.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import pytest

from api.ledger.tools import LedgerTools
from axiom_research.db.migrate import apply_migrations
from axiom_research.db.postgres_store import PostgresLedgerStore
from axiom_research.identities import AgentId
from axiom_research.ledger import (
    CalculationRecord,
    ClaimRecord,
    EvidenceKind,
    EvidenceRecord,
    SourceRecord,
    VerificationStatus,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("AXIOM_LEDGER_PG_TEST") != "1",
    reason="Set AXIOM_LEDGER_PG_TEST=1 with migrated Compose Postgres",
)

NOW = datetime(2026, 11, 2, tzinfo=UTC)


def test_ledger_tools_roundtrip_postgres() -> None:
    url = (
        os.environ.get("DATABASE_URL")
        or "postgresql://axiom:axiom@127.0.0.1:5434/axiom_research"
    ).strip()
    apply_migrations(url)
    store = PostgresLedgerStore(url)
    session_id = f"ses-{uuid.uuid4().hex[:10]}"
    run_id = f"run-{uuid.uuid4().hex[:10]}"
    tools = LedgerTools(store, session_id=session_id, run_id=run_id)

    tools.upsert_source(
        SourceRecord(
            source_id=f"src-{session_id}",
            identifier="doi:10.example/pg",
            retrieved_at=NOW,
            provider="crossref",
            fingerprint="fp-src-pg",
        )
    )
    evidence_id = f"ev-{session_id}"
    tools.upsert_evidence(
        EvidenceRecord(
            evidence_id=evidence_id,
            source_id=f"src-{session_id}",
            kind=EvidenceKind.COMPUTED_PROPERTY,
            statement="PG round-trip band gap.",
            unit="eV",
            retrieved_at=NOW,
            author_agent=AgentId.INVESTIGATOR,
            fingerprint="fp-ev-pg",
        )
    )
    tools.upsert_claim(
        ClaimRecord(
            claim_id=f"claim-{session_id}",
            revision=1,
            statement="Property in stated range.",
            author_agent=AgentId.DATA_ANALYST,
            evidence_ids=[evidence_id],
            source_refs=["doi:10.example/pg"],
            evidence_kind=EvidenceKind.COMPUTED_PROPERTY,
            value=1.5,
            unit="eV",
            verification_status=VerificationStatus.PENDING,
            fingerprint="fp-claim-pg",
        )
    )
    tools.upsert_calculation(
        CalculationRecord(
            calculation_id=f"calc-{session_id}",
            inputs={"a": 3.0, "b": 2.0},
            formula="a / b",
            unit="1",
            output=1.5,
            author_agent=AgentId.DATA_ANALYST,
            fingerprint="fp-calc-pg",
        )
    )
    snap = tools.freeze_snapshot(f"snap-{session_id}", frozen_at=NOW)
    current = tools.read_current_snapshot()
    assert current is not None
    assert current.snapshot_id == snap.snapshot_id
    assert tools.get_claim(f"claim-{session_id}") is not None
