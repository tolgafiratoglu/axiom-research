"""Eval report over fixture three-way results (8.5).

Covers the ReadMe metrics: citation validity, claim-to-source, planted-error
detection, verification coverage, handoff usefulness, redundant tools, latency,
token cost, failure behavior. Human-rubric rows stay pending — never LLM-judged.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from axiom_research.eval.comparison import ThreeWayComparison, run_three_way_comparison
from axiom_research.eval.gold import EVAL_METRICS, gold_root
from axiom_research.eval.modes import COMPARISON_MODES, EvalMode, SharedBudgets

# Stable report order (RoadMap 8.5 / ReadMe).
REPORT_METRICS: tuple[str, ...] = (
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

StatusCountKey = Literal["pass", "fail", "pending_human", "skip", "absent"]


class MetricModeCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pass_count: int = 0
    fail_count: int = 0
    pending_human: int = 0
    skip_count: int = 0
    # Gold cases that do not declare this metric for scoring.
    absent_count: int = 0


class MetricReportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    by_mode: dict[str, MetricModeCounts]
    notes: str | None = None


class CaseMetricCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    metric: str
    by_mode: dict[str, str]  # status or "absent"


class EvalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = "AxiomResearch fixture evaluation report"
    source: Literal["fixtures"] = "fixtures"
    generated_at: str
    budgets: SharedBudgets
    budgets_identical: bool
    mode_labels: dict[str, str]
    mode_suite_passed: dict[str, bool]
    metrics: list[MetricReportRow]
    case_metric_matrix: list[CaseMetricCell]
    gate_credits: list[dict[str, Any]] = Field(default_factory=list)
    swarm_credits: list[dict[str, Any]] = Field(default_factory=list)
    summary: str
    llm_as_judge: Literal[False] = False


def _empty_counts() -> MetricModeCounts:
    return MetricModeCounts()


def build_eval_report(comparison: ThreeWayComparison | None = None) -> EvalReport:
    """Aggregate three-way fixture scores into the 8.5 metric report."""
    cmp = comparison or run_three_way_comparison()
    case_ids = [
        c.case_id for c in cmp.modes[EvalMode.SWARM_GATE.value].cases
    ]

    # metric -> mode -> counts
    tallies: dict[str, dict[str, MetricModeCounts]] = {
        metric: {mode.value: _empty_counts() for mode in COMPARISON_MODES}
        for metric in REPORT_METRICS
    }
    matrix: list[CaseMetricCell] = []

    for case_id in case_ids:
        for metric in REPORT_METRICS:
            by_mode: dict[str, str] = {}
            for mode in COMPARISON_MODES:
                suite = cmp.modes[mode.value]
                case = next(c for c in suite.cases if c.case_id == case_id)
                checks = [c for c in case.checks if c.metric == metric]
                counts = tallies[metric][mode.value]
                if not checks:
                    counts.absent_count += 1
                    by_mode[mode.value] = "absent"
                    continue
                # One primary status per case/metric (gold has at most one check/metric).
                status = checks[0].status
                by_mode[mode.value] = status
                if status == "pass":
                    counts.pass_count += 1
                elif status == "fail":
                    counts.fail_count += 1
                elif status == "pending_human":
                    counts.pending_human += 1
                else:
                    counts.skip_count += 1
            matrix.append(
                CaseMetricCell(case_id=case_id, metric=metric, by_mode=by_mode)
            )

    metric_notes = {
        "handoff_usefulness": "Qualitative — human rubric only; never LLM-as-judge.",
        "token_cost": (
            "Declared in the metric set; gold cases may omit checks until live runs "
            "record accounting (fixture cells show absent)."
        ),
        "latency": "Scored where gold expects bounded failure (e.g. delayed_a2a).",
    }

    rows = [
        MetricReportRow(
            metric=metric,
            by_mode=tallies[metric],
            notes=metric_notes.get(metric),
        )
        for metric in REPORT_METRICS
    ]

    swarm_ok = cmp.modes[EvalMode.SWARM_GATE.value].passed
    summary = (
        f"Fixture three-way report: swarm_gate passed={swarm_ok}; "
        f"gate_credits={len(cmp.gate_credits)}; swarm_credits={len(cmp.swarm_credits)}. "
        "Do not credit Swarm for Verifier gains (see gate_credits)."
    )

    return EvalReport(
        generated_at=datetime.now(tz=UTC).replace(microsecond=0).isoformat(),
        budgets=cmp.budgets,
        budgets_identical=cmp.budgets_identical,
        mode_labels=dict(cmp.labels),
        mode_suite_passed={m: cmp.modes[m].passed for m in cmp.modes},
        metrics=rows,
        case_metric_matrix=matrix,
        gate_credits=[d.model_dump(mode="json") for d in cmp.gate_credits],
        swarm_credits=[d.model_dump(mode="json") for d in cmp.swarm_credits],
        summary=summary,
        llm_as_judge=False,
    )


def report_to_markdown(report: EvalReport) -> str:
    lines = [
        f"# {report.title}",
        "",
        f"- Source: `{report.source}` (no live APIs)",
        f"- Generated: `{report.generated_at}`",
        f"- LLM-as-judge: `{report.llm_as_judge}`",
        f"- Budgets identical across modes: `{report.budgets_identical}`",
        "",
        "## Shared budgets",
        "",
        "```json",
        report.budgets.model_dump_json(indent=2),
        "```",
        "",
        "## Mode suite pass/fail",
        "",
    ]
    for mode, passed in report.mode_suite_passed.items():
        label = report.mode_labels.get(mode, mode)
        lines.append(f"- **{mode}** ({label}): passed=`{passed}`")
    lines.extend(["", "## Metrics", ""])
    lines.append(
        "| Metric | one_agent_no_gate (P/F/H/A) | one_agent_gate (P/F/H/A) | swarm_gate (P/F/H/A) |"
    )
    lines.append("| --- | --- | --- | --- |")
    for row in report.metrics:
        cells = []
        for mode in COMPARISON_MODES:
            c = row.by_mode[mode.value]
            cells.append(
                f"{c.pass_count}/{c.fail_count}/{c.pending_human}/{c.absent_count}"
            )
        note = f" — {row.notes}" if row.notes else ""
        lines.append(
            f"| `{row.metric}` | " + " | ".join(cells) + f" |{note}"
        )
    lines.extend(
        [
            "",
            "P=pass F=fail H=pending_human A=absent (no gold check for that metric).",
            "",
            "## Unbundling",
            "",
            f"- Gate credits (Verifier, not Swarm): **{len(report.gate_credits)}**",
            f"- Swarm credits (collaboration, not Verifier): **{len(report.swarm_credits)}**",
            "",
            report.summary,
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def sample_report_paths(root: Path | None = None) -> tuple[Path, Path]:
    base = gold_root(root).parent / "reports"
    return base / "sample_fixture_report.json", base / "sample_fixture_report.md"


def write_sample_reports(
    report: EvalReport | None = None,
    root: Path | None = None,
) -> tuple[Path, Path]:
    """Write the checked-in sample report pair under ``eval/reports/``."""
    built = report or build_eval_report()
    # Stable timestamp for the checked-in sample (reproducible diffs).
    stable = built.model_copy(
        update={"generated_at": "2026-11-03T00:00:00+00:00"}
    )
    json_path, md_path = sample_report_paths(root)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(stable.model_dump_json(indent=2) + "\n", encoding="utf-8")
    md_path.write_text(report_to_markdown(stable), encoding="utf-8")
    return json_path, md_path


def load_sample_report(root: Path | None = None) -> EvalReport:
    path, _ = sample_report_paths(root)
    return EvalReport.model_validate_json(path.read_text(encoding="utf-8"))


def main() -> int:
    """``python -m axiom_research.eval.report`` — rebuild sample fixture report."""
    comparison = run_three_way_comparison()
    report = build_eval_report(comparison)
    json_path, md_path = write_sample_reports(report)
    print(f"sample report json: {json_path}")
    print(f"sample report md:   {md_path}")
    print(report.summary)
    return 0 if comparison.modes[EvalMode.SWARM_GATE.value].passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
