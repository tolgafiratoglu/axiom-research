"""8.2 — human rubrics for qualitative metrics; no LLM-as-judge as ground truth."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from axiom_research.eval.gold import ExpectedCheck
from axiom_research.eval.rubrics import (
    FORBIDDEN_GROUND_TRUTH,
    QUALITATIVE_METRICS,
    HumanRubric,
    assert_check_judge_policy,
    load_human_rubric,
    validate_gold_rubric_policy,
)


def test_qualitative_metric_is_handoff_usefulness_only() -> None:
    assert QUALITATIVE_METRICS == frozenset({"handoff_usefulness"})


def test_human_rubric_loads_and_rejects_llm_judge_fields() -> None:
    rubric = load_human_rubric("handoff_usefulness_v1")
    assert rubric.ground_truth == "human"
    assert rubric.metric == "handoff_usefulness"
    assert len(rubric.criteria) >= 2
    with pytest.raises(ValidationError, match="LLM-as-judge|forbidden"):
        HumanRubric.model_validate(
            {
                "rubric_id": "bad",
                "metric": "handoff_usefulness",
                "title": "bad",
                "ground_truth": "human",
                "criteria": [{"id": "x", "pass_when": "y"}],
                "aggregate": "n/a",
                "llm_as_judge": True,
            }
        )


def test_deterministic_metric_cannot_use_human_rubric() -> None:
    check = ExpectedCheck(
        metric="citation_validity",
        expect="reject",
        judge="deterministic",
    )
    assert_check_judge_policy(check)
    misuse = ExpectedCheck(
        metric="citation_validity",
        expect="reject",
        judge="human_rubric",
        rubric_id="handoff_usefulness_v1",
    )
    with pytest.raises(ValueError, match="deterministic"):
        assert_check_judge_policy(misuse)


def test_qualitative_check_requires_human_rubric_id() -> None:
    with pytest.raises(ValidationError):
        ExpectedCheck(
            metric="handoff_usefulness",
            expect="pass",
            judge="human_rubric",
        )
    ok = ExpectedCheck(
        metric="handoff_usefulness",
        expect="challenger_engaged",
        judge="human_rubric",
        rubric_id="handoff_usefulness_v1",
    )
    assert_check_judge_policy(ok)


def test_gold_set_satisfies_rubric_policy() -> None:
    cases = validate_gold_rubric_policy()
    human_checks = [
        c
        for case in cases
        for c in case.expected_checks
        if c.metric in QUALITATIVE_METRICS
    ]
    assert human_checks
    assert all(c.judge == "human_rubric" and c.rubric_id for c in human_checks)
    for case in cases:
        blob = case.model_dump_json()
        for forbidden in FORBIDDEN_GROUND_TRUTH:
            assert forbidden not in blob
