"""A2A Independent Verifier request/result contracts.

Payload must not carry Swarm transcript or other agents' opinions.
Verifier returns a verdict enum only — never mutates ledger claims.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from axiom_research.ledger import EvidenceKind, VerificationVerdict

_FORBIDDEN_REQUEST_KEYS = frozenset(
    {
        "swarm_transcript",
        "transcript",
        "agent_opinions",
        "opinions",
        "prior_verdicts",
        "prior_verdict",
        "rationale_from_swarm",
        "swarm_context",
        "node_history",
    }
)


class VerificationRequest(BaseModel):
    """Claim check sent to the remote Verifier (application → A2A)."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_revision: int
    claim_fingerprint: str
    statement: str
    source_refs: list[str] = Field(min_length=1)
    evidence_kind: EvidenceKind
    criteria: str
    unit: str | None = None
    value: float | str | None = None

    @field_validator("statement", "criteria")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not (value or "").strip():
            raise ValueError("must be non-empty")
        return value.strip()


class VerificationResult(BaseModel):
    """Verifier response — only verdict + provenance + revision binding."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    claim_fingerprint: str
    claim_revision: int
    status: VerificationVerdict
    source_refs: list[str] = Field(min_length=1)
    verified_revision: int


def assert_no_swarm_opinions(payload: dict) -> None:
    """Reject A2A payloads that smuggle Swarm dialogue or peer conclusions."""
    bad = sorted(k for k in payload if k in _FORBIDDEN_REQUEST_KEYS)
    if bad:
        raise ValueError(
            "verification payload must not include Swarm opinions/transcript: "
            + ", ".join(bad)
        )


def parse_verification_request(data: object) -> VerificationRequest:
    if isinstance(data, dict):
        assert_no_swarm_opinions(data)
    return VerificationRequest.model_validate(data)


def parse_verification_result(data: object) -> VerificationResult:
    return VerificationResult.model_validate(data)
