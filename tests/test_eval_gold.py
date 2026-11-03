"""8.1 — curated gold-set fixtures load with explicit expected checks (no live APIs)."""

from __future__ import annotations

from axiom_research.eval.gold import (
    EVAL_METRICS,
    REQUIRED_CASE_IDS,
    GoldFault,
    load_gold_case,
    load_gold_manifest,
    load_gold_set,
)


def test_manifest_lists_all_required_cases() -> None:
    manifest = load_gold_manifest()
    assert manifest.version == 1
    assert tuple(manifest.case_ids) == REQUIRED_CASE_IDS
    assert set(manifest.case_ids) == {f.value for f in GoldFault}


def test_gold_set_loads_nine_cases_with_checks() -> None:
    cases = load_gold_set()
    assert len(cases) == 9
    by_id = {c.case_id: c for c in cases}
    assert set(by_id) == set(REQUIRED_CASE_IDS)

    for case_id in REQUIRED_CASE_IDS:
        case = by_id[case_id]
        assert case.fault.value == case_id
        assert case.question.strip()
        assert case.planted
        assert case.expected_checks
        for check in case.expected_checks:
            assert check.metric in EVAL_METRICS
            assert check.expect.strip()
            assert check.judge in {"deterministic", "human_rubric"}


def test_qualitative_handoff_uses_human_rubric_not_llm_judge() -> None:
    """8.1 seeds; 8.2 expands rubrics — no LLM-as-judge field on gold cases."""
    challenger = load_gold_case("planted_challenger_alternative")
    handoff_checks = [c for c in challenger.expected_checks if c.metric == "handoff_usefulness"]
    assert handoff_checks
    assert all(c.judge == "human_rubric" for c in handoff_checks)
    for case in load_gold_set():
        dumped = case.model_dump()
        assert "llm_judge" not in dumped
        assert "llm_as_judge" not in dumped
