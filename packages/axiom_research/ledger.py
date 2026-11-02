from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from axiom_research.identities import AgentId


class LedgerRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceKind(StrEnum):
    PREPRINT = "preprint"
    PEER_REVIEWED = "peer_reviewed"
    COMPUTED_PROPERTY = "computed_property"
    MEASUREMENT = "measurement"
    DATASET = "dataset"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


class VerificationVerdict(StrEnum):
    VERIFIED = "verified"
    REJECTED = "rejected"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTING_EVIDENCE = "conflicting_evidence"


class SourceRecord(LedgerRecord):
    source_id: str
    identifier: str
    url: str | None = None
    version: str | None = None
    retrieved_at: datetime
    method: str | None = None
    license: str | None = None
    provider: str | None = None
    fingerprint: str
    revision: int = 1


class EvidenceRecord(LedgerRecord):
    evidence_id: str
    source_id: str
    kind: EvidenceKind
    statement: str
    method: str | None = None
    unit: str | None = None
    retrieved_at: datetime
    license: str | None = None
    author_agent: AgentId
    fingerprint: str
    revision: int = 1


class ClaimRecord(LedgerRecord):
    claim_id: str
    revision: int
    statement: str
    author_agent: AgentId
    evidence_ids: list[str]
    source_refs: list[str]
    evidence_kind: EvidenceKind
    method: str | None = None
    value: float | str | None = None
    unit: str | None = None
    verification_status: VerificationStatus = VerificationStatus.PENDING
    verified_revision: int | None = None
    limitations: list[str] = Field(default_factory=list)
    fingerprint: str


class CalculationRecord(LedgerRecord):
    calculation_id: str
    inputs: dict[str, Any]
    formula: str
    normalization: str | None = None
    unit: str
    output: float | str
    author_agent: AgentId
    fingerprint: str
    revision: int = 1


class HypothesisRecord(LedgerRecord):
    hypothesis_id: str
    statement: str
    author_agent: AgentId
    related_claim_ids: list[str] = Field(default_factory=list)
    fingerprint: str
    revision: int = 1


class VerificationRecord(LedgerRecord):
    verification_id: str
    claim_id: str
    claim_revision: int
    claim_fingerprint: str
    status: VerificationVerdict
    source_refs: list[str]
    verified_revision: int
    author_agent: AgentId = AgentId.VERIFIER
    fingerprint: str
    revision: int = 1


class AuditEvent(LedgerRecord):
    audit_id: str
    ts: datetime
    session_id: str
    run_id: str
    action: str
    agent_id: AgentId | None = None
    fingerprint: str
    revision: int = 1


class LedgerSnapshot(LedgerRecord):
    """Immutable freeze of claim/evidence/source revisions for a gate pass."""

    snapshot_id: str
    session_id: str
    run_id: str
    frozen_at: datetime
    sources: list[SourceRecord]
    evidence: list[EvidenceRecord]
    claims: list[ClaimRecord]
    calculations: list[CalculationRecord]
    hypotheses: list[HypothesisRecord]
    verifications: list[VerificationRecord]
    fingerprint: str
