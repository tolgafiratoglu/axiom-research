"""Strands @tool wrappers over api.ledger.LedgerTools, filtered by allowlist."""

from __future__ import annotations

from typing import Any

from strands import tool

from api.ledger.tools import LedgerTools
from axiom_research.ledger import (
    CalculationRecord,
    ClaimRecord,
    EvidenceRecord,
    HypothesisRecord,
    SourceRecord,
)


def build_ledger_agent_tools(
    ledger: LedgerTools, allowed: frozenset[str]
) -> list[Any]:
    tools: list[Any] = []

    if "upsert_source" in allowed:

        @tool(name="upsert_source", description="Upsert a source record into the ledger.")
        def upsert_source(payload: dict[str, Any]) -> dict[str, Any]:
            return ledger.upsert_source(SourceRecord.model_validate(payload)).model_dump(
                mode="json"
            )

        tools.append(upsert_source)

    if "upsert_evidence" in allowed:

        @tool(
            name="upsert_evidence",
            description="Upsert an evidence record linked to a source.",
        )
        def upsert_evidence(payload: dict[str, Any]) -> dict[str, Any]:
            return ledger.upsert_evidence(
                EvidenceRecord.model_validate(payload)
            ).model_dump(mode="json")

        tools.append(upsert_evidence)

    if "upsert_claim" in allowed:

        @tool(
            name="upsert_claim",
            description="Upsert a claim. Numeric values require an explicit unit.",
        )
        def upsert_claim(payload: dict[str, Any]) -> dict[str, Any]:
            return ledger.upsert_claim(ClaimRecord.model_validate(payload)).model_dump(
                mode="json"
            )

        tools.append(upsert_claim)

    if "upsert_calculation" in allowed:

        @tool(
            name="upsert_calculation",
            description="Store a replayable calculation (inputs, formula, unit, output).",
        )
        def upsert_calculation(payload: dict[str, Any]) -> dict[str, Any]:
            return ledger.upsert_calculation(
                CalculationRecord.model_validate(payload)
            ).model_dump(mode="json")

        tools.append(upsert_calculation)

    if "upsert_hypothesis" in allowed:

        @tool(
            name="upsert_hypothesis",
            description="Write a hypothesis (never a claim).",
        )
        def upsert_hypothesis(payload: dict[str, Any]) -> dict[str, Any]:
            return ledger.upsert_hypothesis(
                HypothesisRecord.model_validate(payload)
            ).model_dump(mode="json")

        tools.append(upsert_hypothesis)

    if "attach_evidence_to_claim" in allowed:

        @tool(
            name="attach_evidence_to_claim",
            description="Attach an evidence_id to a claim_id (bumps claim revision).",
        )
        def attach_evidence_to_claim(claim_id: str, evidence_id: str) -> dict[str, Any]:
            return ledger.attach_evidence_to_claim(
                claim_id=claim_id, evidence_id=evidence_id
            ).model_dump(mode="json")

        tools.append(attach_evidence_to_claim)

    if "get_claim" in allowed:

        @tool(name="get_claim", description="Read a claim by id (never a hypothesis).")
        def get_claim(claim_id: str) -> dict[str, Any] | None:
            claim = ledger.get_claim(claim_id)
            return None if claim is None else claim.model_dump(mode="json")

        tools.append(get_claim)

    if "get_hypothesis" in allowed:

        @tool(name="get_hypothesis", description="Read a hypothesis by id.")
        def get_hypothesis(hypothesis_id: str) -> dict[str, Any] | None:
            hyp = ledger.get_hypothesis(hypothesis_id)
            return None if hyp is None else hyp.model_dump(mode="json")

        tools.append(get_hypothesis)

    if "read_current_snapshot" in allowed:

        @tool(
            name="read_current_snapshot",
            description="Read the latest frozen ledger snapshot for this run.",
        )
        def read_current_snapshot() -> dict[str, Any] | None:
            snap = ledger.read_current_snapshot()
            return None if snap is None else snap.model_dump(mode="json")

        tools.append(read_current_snapshot)

    return tools
