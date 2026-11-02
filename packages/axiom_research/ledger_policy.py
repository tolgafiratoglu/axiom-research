"""Ledger write policy shared by api tools and stores."""

from __future__ import annotations

from axiom_research.ledger import ClaimRecord


class LedgerPolicyError(ValueError):
    """Claim/evidence policy violation."""


def assert_claim_units(record: ClaimRecord) -> None:
    """Numeric claims must carry an explicit unit (never inferred)."""
    if isinstance(record.value, (int, float)) and not (record.unit or "").strip():
        raise LedgerPolicyError("numeric claims require a unit")
