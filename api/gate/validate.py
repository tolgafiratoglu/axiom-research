"""Deterministic checks on Verifier results — transport success ≠ science."""

from __future__ import annotations

from axiom_research.ledger import VerificationVerdict
from axiom_research.verification import VerificationRequest, VerificationResult


class GateValidationError(ValueError):
    """Stale binding, schema gap, or transport-success-without-science."""


def assert_result_binds_to_request(
    request: VerificationRequest,
    result: VerificationResult,
) -> None:
    if result.claim_id != request.claim_id:
        raise GateValidationError(
            f"stale verification: claim_id mismatch "
            f"(got {result.claim_id!r}, expected {request.claim_id!r})"
        )
    if result.claim_fingerprint != request.claim_fingerprint:
        raise GateValidationError(
            "stale verification: claim_fingerprint does not match current revision"
        )
    if result.claim_revision != request.claim_revision:
        raise GateValidationError(
            "stale verification: claim_revision does not match current revision"
        )
    if result.verified_revision != request.claim_revision:
        raise GateValidationError(
            "stale verification: verified_revision is not the current claim revision"
        )


def assert_scientific_result(
    request: VerificationRequest,
    result: VerificationResult,
) -> None:
    """Reject A2A transport acks that are not a scientific verdict payload."""
    if not isinstance(result.status, VerificationVerdict):
        raise GateValidationError(
            "transport-success-without-science: status is not a VerificationVerdict"
        )
    if result.status not in VerificationVerdict:
        raise GateValidationError(
            "transport-success-without-science: unknown verdict"
        )
    refs = [r.strip() for r in result.source_refs if (r or "").strip()]
    if not refs:
        raise GateValidationError(
            "transport-success-without-science: empty source_refs"
        )
    # Verifier must ground the verdict in at least one claim source identifier.
    claimed = {r.strip() for r in request.source_refs if (r or "").strip()}
    if claimed.isdisjoint(set(refs)):
        raise GateValidationError(
            "transport-success-without-science: source_refs do not cite claim sources"
        )


def validate_verification_result(
    request: VerificationRequest,
    result: VerificationResult,
) -> None:
    assert_result_binds_to_request(request, result)
    assert_scientific_result(request, result)
