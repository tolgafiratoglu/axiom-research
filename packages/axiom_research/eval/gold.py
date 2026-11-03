"""Curated gold-set cases for fixture evaluation (8.1).

Cases are JSON under ``eval/gold/cases/``. Checks are explicit; qualitative
metrics are marked ``human_rubric`` (no LLM-as-judge as ground truth).
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Metrics named in ReadMe evaluation section.
EVAL_METRICS: frozenset[str] = frozenset(
    {
        "citation_validity",
        "claim_to_source",
        "planted_error_detection",
        "verification_coverage",
        "handoff_usefulness",
        "redundant_tools",
        "latency",
        "token_cost",
        "failure_behavior",
    }
)

REQUIRED_CASE_IDS: tuple[str, ...] = (
    "fabricated_doi",
    "preprint_as_peer_review",
    "unit_mismatch",
    "computed_as_experimental",
    "single_lab_as_commercial",
    "planted_challenger_alternative",
    "stale_verification",
    "mcp_outage",
    "delayed_a2a",
)


class GoldFault(StrEnum):
    FABRICATED_DOI = "fabricated_doi"
    PREPRINT_AS_PEER_REVIEW = "preprint_as_peer_review"
    UNIT_MISMATCH = "unit_mismatch"
    COMPUTED_AS_EXPERIMENTAL = "computed_as_experimental"
    SINGLE_LAB_AS_COMMERCIAL = "single_lab_as_commercial"
    PLANTED_CHALLENGER_ALTERNATIVE = "planted_challenger_alternative"
    STALE_VERIFICATION = "stale_verification"
    MCP_OUTAGE = "mcp_outage"
    DELAYED_A2A = "delayed_a2a"


class ExpectedCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    # Deterministic outcome label for the fixture runner (8.3), not an LLM score.
    expect: str
    detail: str | None = None
    judge: Literal["deterministic", "human_rubric"] = "deterministic"
    # Required when judge=human_rubric (see eval/gold/rubrics/).
    rubric_id: str | None = None

    @field_validator("metric")
    @classmethod
    def _known_metric(cls, value: str) -> str:
        if value not in EVAL_METRICS:
            raise ValueError(f"unknown eval metric: {value}")
        return value

    @model_validator(mode="after")
    def _rubric_id_with_human_judge(self) -> ExpectedCheck:
        if self.judge == "human_rubric" and not (self.rubric_id or "").strip():
            raise ValueError("judge=human_rubric requires rubric_id")
        if self.judge == "deterministic" and self.rubric_id:
            raise ValueError("deterministic checks must omit rubric_id")
        return self


class GoldCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    fault: GoldFault
    title: str
    question: str
    description: str
    # Scenario seed for later fixture/snapshot runners (no live network).
    planted: dict[str, Any] = Field(default_factory=dict)
    expected_checks: list[ExpectedCheck] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("case_id")
    @classmethod
    def _case_id_nonempty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("case_id must be non-empty")
        return text


class GoldManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    case_ids: list[str]


def gold_root(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    # packages/axiom_research/eval/gold.py → repo root
    return Path(__file__).resolve().parents[3] / "eval" / "gold"


def load_gold_manifest(root: Path | None = None) -> GoldManifest:
    path = gold_root(root) / "manifest.json"
    return GoldManifest.model_validate_json(path.read_text(encoding="utf-8"))


def load_gold_case(case_id: str, root: Path | None = None) -> GoldCase:
    path = gold_root(root) / "cases" / f"{case_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    case = GoldCase.model_validate(data)
    if case.case_id != case_id:
        raise ValueError(f"case_id mismatch: file {case_id!r} vs payload {case.case_id!r}")
    if case.fault.value != case.case_id:
        raise ValueError(
            f"fault {case.fault.value!r} must match case_id {case.case_id!r} for gold fixtures"
        )
    return case


def load_gold_set(root: Path | None = None) -> list[GoldCase]:
    base = gold_root(root)
    manifest = load_gold_manifest(base)
    cases = [load_gold_case(case_id, base) for case_id in manifest.case_ids]
    missing = [cid for cid in REQUIRED_CASE_IDS if cid not in manifest.case_ids]
    if missing:
        raise ValueError(f"gold manifest missing required cases: {missing}")
    return cases
