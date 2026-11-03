"""Three-way comparison: one agent / one+gate / Swarm+gate (8.4).

Budgets and MCP tool surface are identical. Swarm must not be credited for the
Verifier — gate gains show up in ``one_agent_gate`` vs ``one_agent_no_gate``;
collaboration gains show up in ``swarm_gate`` vs ``one_agent_gate``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from axiom_research.eval.fixture_runner import (
    CaseRunResult,
    FixtureSuiteResult,
    run_fixture_suite,
    write_suite_json,
)
from axiom_research.eval.gold import gold_root
from axiom_research.eval.modes import (
    COMPARISON_MODES,
    EvalMode,
    SharedBudgets,
    mode_label,
)


class ModeMetricDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    metric: str
    weaker_mode: EvalMode
    stronger_mode: EvalMode
    detail: str


class ThreeWayComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    budgets: SharedBudgets
    modes: dict[str, FixtureSuiteResult]
    # Gate credit (Verifier), not Swarm.
    gate_credits: list[ModeMetricDelta] = Field(default_factory=list)
    # Collaboration credit (Swarm handoffs / Challenger), not Verifier.
    swarm_credits: list[ModeMetricDelta] = Field(default_factory=list)
    budgets_identical: bool = True
    labels: dict[str, str] = Field(default_factory=dict)


def _check_status_map(case: CaseRunResult) -> dict[str, str]:
    return {c.metric: c.status for c in case.checks}


def _find_case(suite: FixtureSuiteResult, case_id: str) -> CaseRunResult:
    for case in suite.cases:
        if case.case_id == case_id:
            return case
    raise KeyError(case_id)


def derive_unbundling_deltas(
    suites: dict[EvalMode, FixtureSuiteResult],
) -> tuple[list[ModeMetricDelta], list[ModeMetricDelta]]:
    """Highlight gate-only vs swarm-only improvements on known gold cases."""
    no_gate = suites[EvalMode.ONE_AGENT_NO_GATE]
    with_gate = suites[EvalMode.ONE_AGENT_GATE]
    swarm = suites[EvalMode.SWARM_GATE]

    gate_credits: list[ModeMetricDelta] = []
    swarm_credits: list[ModeMetricDelta] = []

    # Gate catches citation / stale verification; no-gate does not.
    for case_id, metric in (
        ("fabricated_doi", "citation_validity"),
        ("fabricated_doi", "planted_error_detection"),
        ("stale_verification", "verification_coverage"),
        ("stale_verification", "failure_behavior"),
        ("computed_as_experimental", "verification_coverage"),
    ):
        weak = _check_status_map(_find_case(no_gate, case_id)).get(metric)
        strong = _check_status_map(_find_case(with_gate, case_id)).get(metric)
        if weak == "fail" and strong == "pass":
            gate_credits.append(
                ModeMetricDelta(
                    case_id=case_id,
                    metric=metric,
                    weaker_mode=EvalMode.ONE_AGENT_NO_GATE,
                    stronger_mode=EvalMode.ONE_AGENT_GATE,
                    detail="A2A/gate improvement — do not attribute to Swarm",
                )
            )

    # Swarm Challenger / collaboration — gate alone does not surface alternative.
    for case_id, metric in (
        ("planted_challenger_alternative", "planted_error_detection"),
        ("single_lab_as_commercial", "planted_error_detection"),
    ):
        weak = _check_status_map(_find_case(with_gate, case_id)).get(metric)
        strong = _check_status_map(_find_case(swarm, case_id)).get(metric)
        if weak == "fail" and strong == "pass":
            swarm_credits.append(
                ModeMetricDelta(
                    case_id=case_id,
                    metric=metric,
                    weaker_mode=EvalMode.ONE_AGENT_GATE,
                    stronger_mode=EvalMode.SWARM_GATE,
                    detail="Swarm/Challenger collaboration — not Verifier credit",
                )
            )

    return gate_credits, swarm_credits


def run_three_way_comparison(root: Path | None = None) -> ThreeWayComparison:
    budgets = SharedBudgets.from_settings()
    suites: dict[EvalMode, FixtureSuiteResult] = {}
    for mode in COMPARISON_MODES:
        suites[mode] = run_fixture_suite(root, mode=mode)

    # Budgets are stamped from one Settings source — identical by construction.
    gate_credits, swarm_credits = derive_unbundling_deltas(suites)
    return ThreeWayComparison(
        budgets=budgets,
        modes={mode.value: suite for mode, suite in suites.items()},
        gate_credits=gate_credits,
        swarm_credits=swarm_credits,
        budgets_identical=True,
        labels={mode.value: mode_label(mode) for mode in COMPARISON_MODES},
    )


def write_comparison_json(result: ThreeWayComparison, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")


def main() -> int:
    """``python -m axiom_research.eval.comparison`` — CI three-way, no network."""
    result = run_three_way_comparison()
    out = gold_root().parent / "reports" / "three_way_latest.json"
    write_comparison_json(result, out)
    # Also keep the swarm_gate suite report for the default CI path.
    swarm = result.modes[EvalMode.SWARM_GATE.value]
    write_suite_json(swarm, gold_root().parent / "reports" / "fixture_suite_latest.json")

    print(f"three-way comparison → {out}")
    print(f"shared budgets: {result.budgets.model_dump()}")
    for mode in COMPARISON_MODES:
        suite = result.modes[mode.value]
        print(
            f"  {mode.value}: passed={suite.passed} "
            f"det={suite.deterministic_check_count} "
            f"pending_human={suite.pending_human_count}"
        )
    print(f"gate_credits={len(result.gate_credits)} swarm_credits={len(result.swarm_credits)}")
    # CI: swarm_gate must pass; comparison must show both unbundling signals.
    ok = (
        swarm.passed
        and result.budgets_identical
        and len(result.gate_credits) >= 1
        and len(result.swarm_credits) >= 1
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
