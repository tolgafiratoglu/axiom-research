"""Evaluation gold set and (later) runners — fixture path only, no live APIs."""

from axiom_research.eval.gold import (
    REQUIRED_CASE_IDS,
    ExpectedCheck,
    GoldCase,
    GoldFault,
    gold_root,
    load_gold_case,
    load_gold_manifest,
    load_gold_set,
)
from axiom_research.eval.comparison import ThreeWayComparison, run_three_way_comparison
from axiom_research.eval.fixture_runner import (
    CaseRunResult,
    CheckResult,
    FixtureSuiteResult,
    run_fixture_suite,
)
from axiom_research.eval.modes import COMPARISON_MODES, EvalMode, SharedBudgets
from axiom_research.eval.report import (
    REPORT_METRICS,
    EvalReport,
    build_eval_report,
    load_sample_report,
)
from axiom_research.eval.rubrics import (
    FORBIDDEN_GROUND_TRUTH,
    QUALITATIVE_METRICS,
    HumanRubric,
    load_human_rubric,
    load_human_rubrics,
    validate_gold_rubric_policy,
)
from axiom_research.eval.snapshot import RunSnapshot, load_run_snapshot

__all__ = [
    "COMPARISON_MODES",
    "FORBIDDEN_GROUND_TRUTH",
    "QUALITATIVE_METRICS",
    "REPORT_METRICS",
    "REQUIRED_CASE_IDS",
    "CaseRunResult",
    "CheckResult",
    "EvalMode",
    "EvalReport",
    "ExpectedCheck",
    "FixtureSuiteResult",
    "GoldCase",
    "GoldFault",
    "HumanRubric",
    "RunSnapshot",
    "SharedBudgets",
    "ThreeWayComparison",
    "build_eval_report",
    "gold_root",
    "load_gold_case",
    "load_gold_manifest",
    "load_gold_set",
    "load_human_rubric",
    "load_human_rubrics",
    "load_run_snapshot",
    "load_sample_report",
    "run_fixture_suite",
    "run_three_way_comparison",
    "validate_gold_rubric_policy",
]
