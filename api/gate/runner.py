"""Deterministic verification gate — application code after Swarm stop."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Callable

from api.gate.validate import GateValidationError, validate_verification_result
from api.gate.verifier_client import VerifierClient, VerifierUnreachableError
from axiom_research.events import (
    A2AVerification,
    RunFailed,
    ServerMessage,
    VerificationGate,
)
from axiom_research.ledger import (
    ClaimRecord,
    LedgerSnapshot,
    VerificationRecord,
    VerificationStatus,
)
from axiom_research.ledger_store import LedgerStore
from axiom_research.verification import VerificationRequest, VerificationResult


def default_criteria(claim: ClaimRecord) -> str:
    kind = claim.evidence_kind.value
    return (
        f"Independently re-check claim against cited sources; "
        f"confirm identifiers resolve and units/values match "
        f"(evidence_kind={kind})."
    )


def _verification_fingerprint(result: VerificationResult) -> str:
    raw = json.dumps(result.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _needs_verification(store: LedgerStore, session_id: str, claim: ClaimRecord) -> bool:
    if claim.verification_status == VerificationStatus.PENDING:
        return True
    current = store.current_verification_for_claim(session_id, claim.claim_id)
    return current is None


def claim_to_request(
    claim: ClaimRecord,
    *,
    criteria: str,
) -> VerificationRequest:
    return VerificationRequest(
        claim_id=claim.claim_id,
        claim_revision=claim.revision,
        claim_fingerprint=claim.fingerprint,
        statement=claim.statement,
        source_refs=list(claim.source_refs),
        evidence_kind=claim.evidence_kind,
        criteria=criteria,
        unit=claim.unit,
        value=claim.value,
    )


@dataclass
class GateOutcome:
    """Gate result for Finalizer handoff. ``allow_finalizer`` is False on hard fail."""

    passed: bool
    allow_finalizer: bool
    snapshot: LedgerSnapshot
    events: list[ServerMessage] = field(default_factory=list)
    reason: str | None = None
    results: list[VerificationResult] = field(default_factory=list)


async def run_verification_gate(
    store: LedgerStore,
    *,
    session_id: str,
    run_id: str,
    client: VerifierClient,
    snapshot_id: str | None = None,
    criteria_fn: Callable[[ClaimRecord], str] | None = None,
    frozen_at: datetime | None = None,
) -> GateOutcome:
    """Freeze ledger, A2A-verify current unverified claims, emit gate events.

    Call after Swarm stop (success or budget). Never a Swarm node.
    """
    now = frozen_at or datetime.now(tz=UTC)
    snap_id = snapshot_id or f"snap-{uuid.uuid4().hex[:12]}"
    snapshot = store.freeze_snapshot(
        snapshot_id=snap_id,
        session_id=session_id,
        run_id=run_id,
        frozen_at=now,
    )
    events: list[ServerMessage] = []
    results: list[VerificationResult] = []
    criteria = criteria_fn or default_criteria

    pending = [c for c in snapshot.claims if _needs_verification(store, session_id, c)]

    for claim in pending:
        if not claim.source_refs:
            reason = f"incomplete assessment: claim {claim.claim_id} has no source_refs"
            events.append(
                VerificationGate(
                    event_id="",
                    ts=now,
                    session_id=session_id,
                    run_id=run_id,
                    passed=False,
                    detail=reason,
                )
            )
            return GateOutcome(
                passed=False,
                allow_finalizer=False,
                snapshot=snapshot,
                events=events,
                reason=reason,
                results=results,
            )

        request = claim_to_request(claim, criteria=criteria(claim))
        try:
            result = await client.verify(request)
        except VerifierUnreachableError as exc:
            reason = f"verifier unreachable: {exc}"
            events.append(
                RunFailed(
                    event_id="",
                    ts=now,
                    session_id=session_id,
                    run_id=run_id,
                    reason=reason,
                )
            )
            return GateOutcome(
                passed=False,
                allow_finalizer=False,
                snapshot=snapshot,
                events=events,
                reason=reason,
                results=results,
            )
        except (ValueError, TypeError) as exc:
            reason = f"schema-invalid verifier result: {exc}"
            events.append(
                VerificationGate(
                    event_id="",
                    ts=now,
                    session_id=session_id,
                    run_id=run_id,
                    passed=False,
                    detail=reason,
                )
            )
            return GateOutcome(
                passed=False,
                allow_finalizer=False,
                snapshot=snapshot,
                events=events,
                reason=reason,
                results=results,
            )

        try:
            validate_verification_result(request, result)
        except GateValidationError as exc:
            reason = str(exc)
            events.append(
                VerificationGate(
                    event_id="",
                    ts=now,
                    session_id=session_id,
                    run_id=run_id,
                    passed=False,
                    detail=reason,
                )
            )
            return GateOutcome(
                passed=False,
                allow_finalizer=False,
                snapshot=snapshot,
                events=events,
                reason=reason,
                results=results,
            )

        ver_id = f"ver-{claim.claim_id}-r{claim.revision}"
        store.upsert_verification(
            session_id,
            VerificationRecord(
                verification_id=ver_id,
                claim_id=claim.claim_id,
                claim_revision=claim.revision,
                claim_fingerprint=claim.fingerprint,
                status=result.status,
                source_refs=list(result.source_refs),
                verified_revision=result.verified_revision,
                fingerprint=_verification_fingerprint(result),
            ),
        )
        results.append(result)
        events.append(
            A2AVerification(
                event_id="",
                ts=now,
                session_id=session_id,
                run_id=run_id,
                verification_id=ver_id,
                claim_id=claim.claim_id,
                status=result.status,
                verified_revision=result.verified_revision,
            )
        )

    # Re-freeze so Finalizer snapshot includes written verifications.
    snapshot = store.freeze_snapshot(
        snapshot_id=f"{snap_id}-gated",
        session_id=session_id,
        run_id=run_id,
        frozen_at=now,
    )
    events.append(
        VerificationGate(
            event_id="",
            ts=now,
            session_id=session_id,
            run_id=run_id,
            passed=True,
            detail=None if pending else "no pending claims",
        )
    )
    return GateOutcome(
        passed=True,
        allow_finalizer=True,
        snapshot=snapshot,
        events=events,
        reason=None,
        results=results,
    )
