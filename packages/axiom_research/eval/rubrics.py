"""Human-reviewed rubrics for qualitative eval metrics (8.2).

LLM-as-judge is never ground truth. Deterministic metrics stay fixture-checked;
only metrics in ``QUALITATIVE_METRICS`` may use ``judge=human_rubric``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from axiom_research.eval.gold import (
    EVAL_METRICS,
    ExpectedCheck,
    GoldCase,
    gold_root,
    load_gold_set,
)

# Qualitative methodology-style scores — human rubric required.
QUALITATIVE_METRICS: frozenset[str] = frozenset(
    {
        "handoff_usefulness",
    }
)

FORBIDDEN_GROUND_TRUTH: frozenset[str] = frozenset(
    {
        "llm_as_judge",
        "llm_judge",
        "model_as_judge",
        "gemini_as_judge",
        "auto_llm_score",
    }
)


class RubricCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    pass_when: str
    weight: int = 1
    required: bool = True


class HumanRubric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubric_id: str
    metric: str
    version: int = 1
    title: str
    ground_truth: Literal["human"] = "human"
    scale: list[str] = Field(default_factory=lambda: ["fail", "partial", "pass"])
    criteria: list[RubricCriterion] = Field(min_length=1)
    aggregate: str
    notes: str | None = None

    @field_validator("metric")
    @classmethod
    def _qualitative_metric(cls, value: str) -> str:
        if value not in EVAL_METRICS:
            raise ValueError(f"unknown eval metric: {value}")
        if value not in QUALITATIVE_METRICS:
            raise ValueError(
                f"metric {value!r} is not qualitative; use deterministic checks, not a human rubric"
            )
        return value

    @field_validator("ground_truth")
    @classmethod
    def _human_only(cls, value: str) -> str:
        if value != "human":
            raise ValueError("rubric ground_truth must be 'human'")
        return value

    @model_validator(mode="before")
    @classmethod
    def _reject_llm_judge_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        bad = sorted(k for k in data if k in FORBIDDEN_GROUND_TRUTH)
        if bad:
            raise ValueError(
                "LLM-as-judge fields are forbidden as ground truth: " + ", ".join(bad)
            )
        return data


def rubrics_root(explicit: Path | None = None) -> Path:
    return gold_root(explicit) / "rubrics"


def load_human_rubric(rubric_id: str, root: Path | None = None) -> HumanRubric:
    path = rubrics_root(root) / f"{rubric_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    rubric = HumanRubric.model_validate(data)
    if rubric.rubric_id != rubric_id:
        raise ValueError(
            f"rubric_id mismatch: file {rubric_id!r} vs payload {rubric.rubric_id!r}"
        )
    return rubric


def load_human_rubrics(root: Path | None = None) -> list[HumanRubric]:
    base = rubrics_root(root)
    if not base.is_dir():
        raise FileNotFoundError(f"rubrics directory missing: {base}")
    rubrics: list[HumanRubric] = []
    for path in sorted(base.glob("*.json")):
        rubrics.append(load_human_rubric(path.stem, root))
    return rubrics


def assert_check_judge_policy(check: ExpectedCheck) -> None:
    """Qualitative → human_rubric + rubric_id; others → deterministic; never LLM judge."""
    if check.metric in QUALITATIVE_METRICS:
        if check.judge != "human_rubric":
            raise ValueError(
                f"qualitative metric {check.metric!r} requires judge=human_rubric"
            )
        if not check.rubric_id:
            raise ValueError(
                f"qualitative metric {check.metric!r} requires rubric_id"
            )
    elif check.judge == "human_rubric":
        raise ValueError(
            f"metric {check.metric!r} is deterministic; do not attach human_rubric"
        )
    elif check.rubric_id:
        raise ValueError(
            f"metric {check.metric!r} is deterministic; rubric_id must be omitted"
        )


def assert_case_rubric_policy(case: GoldCase, rubrics_by_id: dict[str, HumanRubric]) -> None:
    for check in case.expected_checks:
        assert_check_judge_policy(check)
        if check.judge == "human_rubric":
            assert check.rubric_id is not None
            rubric = rubrics_by_id.get(check.rubric_id)
            if rubric is None:
                raise ValueError(
                    f"case {case.case_id}: missing rubric file for {check.rubric_id!r}"
                )
            if rubric.metric != check.metric:
                raise ValueError(
                    f"case {case.case_id}: rubric {check.rubric_id!r} metric "
                    f"{rubric.metric!r} != check metric {check.metric!r}"
                )


def validate_gold_rubric_policy(root: Path | None = None) -> list[GoldCase]:
    """Load gold set + rubrics; enforce human-only qualitative ground truth."""
    rubrics = {r.rubric_id: r for r in load_human_rubrics(root)}
    cases = load_gold_set(root)
    for case in cases:
        dumped = case.model_dump()
        for key in FORBIDDEN_GROUND_TRUTH:
            if key in dumped:
                raise ValueError(f"case {case.case_id} contains forbidden field {key}")
        assert_case_rubric_policy(case, rubrics)
    # Every qualitative metric used in gold must have at least one rubric on disk.
    used = {
        c.rubric_id
        for case in cases
        for c in case.expected_checks
        if c.judge == "human_rubric" and c.rubric_id
    }
    missing_files = used - set(rubrics)
    if missing_files:
        raise ValueError(f"referenced rubrics missing on disk: {sorted(missing_files)}")
    return cases
