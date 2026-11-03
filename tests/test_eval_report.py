"""8.5 — fixture eval report covers all metrics; sample report checked in."""

from __future__ import annotations

from axiom_research.eval.comparison import run_three_way_comparison
from axiom_research.eval.gold import EVAL_METRICS
from axiom_research.eval.report import (
    REPORT_METRICS,
    build_eval_report,
    load_sample_report,
    report_to_markdown,
    sample_report_paths,
    write_sample_reports,
)


def test_report_metrics_match_readme_set() -> None:
    assert tuple(REPORT_METRICS) == (
        "citation_validity",
        "claim_to_source",
        "planted_error_detection",
        "verification_coverage",
        "handoff_usefulness",
        "redundant_tools",
        "latency",
        "token_cost",
        "failure_behavior",
    )
    assert set(REPORT_METRICS) == set(EVAL_METRICS)


def test_build_eval_report_includes_all_metrics_and_unbundling() -> None:
    report = build_eval_report(run_three_way_comparison())
    assert [row.metric for row in report.metrics] == list(REPORT_METRICS)
    assert report.source == "fixtures"
    assert report.llm_as_judge is False
    assert report.budgets_identical is True
    assert report.mode_suite_passed["swarm_gate"] is True
    assert len(report.gate_credits) >= 1
    assert len(report.swarm_credits) >= 1
    handoff = next(r for r in report.metrics if r.metric == "handoff_usefulness")
    assert handoff.by_mode["swarm_gate"].pending_human == 2
    assert handoff.by_mode["swarm_gate"].pass_count == 0


def test_checked_in_sample_report_present_and_valid() -> None:
    json_path, md_path = sample_report_paths()
    assert json_path.is_file(), f"missing {json_path}"
    assert md_path.is_file(), f"missing {md_path}"
    sample = load_sample_report()
    assert [row.metric for row in sample.metrics] == list(REPORT_METRICS)
    assert sample.llm_as_judge is False
    assert sample.generated_at == "2026-11-03T00:00:00+00:00"
    md = md_path.read_text(encoding="utf-8")
    for metric in REPORT_METRICS:
        assert f"`{metric}`" in md
    assert "LLM-as-judge: `False`" in md
    assert "gate_credits" in md.lower() or "Gate credits" in md


def test_sample_report_rebuild_is_stable(tmp_path) -> None:
    """Rebuilding with stable timestamp matches checked-in JSON structure."""
    report = build_eval_report(run_three_way_comparison())
    gold = tmp_path / "gold"
    gold.mkdir()
    write_sample_reports(report, root=gold)
    rebuilt = load_sample_report(root=gold)
    checked = load_sample_report()
    assert rebuilt.metrics == checked.metrics
    assert rebuilt.mode_suite_passed == checked.mode_suite_passed
    assert rebuilt.gate_credits == checked.gate_credits
    assert rebuilt.swarm_credits == checked.swarm_credits
    assert "citation_validity" in report_to_markdown(rebuilt)
