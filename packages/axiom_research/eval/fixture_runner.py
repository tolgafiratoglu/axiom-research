"""CI fixture/snapshot runner — scores gold cases against checked-in snapshots.

No outbound network. Human-rubric checks are ``pending_human``, never LLM-judged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from axiom_research.eval.gold import ExpectedCheck, GoldCase, gold_root, load_gold_set
from axiom_research.eval.modes import EvalMode
from axiom_research.eval.rubrics import validate_gold_rubric_policy
from axiom_research.eval.snapshot import (
    RunSnapshot,
    SnapshotObservations,
    load_run_snapshot,
)

CheckStatus = Literal["pass", "fail", "pending_human", "skip"]


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metric: str
    expect: str
    judge: str
    status: CheckStatus
    detail: str | None = None
    rubric_id: str | None = None


class CaseRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    mode: str = EvalMode.SWARM_GATE.value
    checks: list[CheckResult]
    deterministic_passed: bool
    pending_human: int = 0


class FixtureSuiteResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = EvalMode.SWARM_GATE.value
    cases: list[CaseRunResult]
    passed: bool
    deterministic_check_count: int
    pending_human_count: int


def score_check(check: ExpectedCheck, obs: SnapshotObservations) -> CheckResult:
    if check.judge == "human_rubric":
        return CheckResult(
            metric=check.metric,
            expect=check.expect,
            judge=check.judge,
            status="pending_human",
            detail="qualitative — human rubric only (not LLM-as-judge)",
            rubric_id=check.rubric_id,
        )

    ok = False
    detail = check.detail

    if check.metric == "citation_validity":
        if check.expect == "reject":
            ok = obs.citation_valid is False
            detail = detail or "citation_valid must be false"
        elif check.expect == "flag_status":
            ok = obs.citation_valid is False or obs.planted_error_detected is True
        elif check.expect == "no_fabricated_sources":
            ok = obs.fabricated_sources_present is False
        else:
            return CheckResult(
                metric=check.metric,
                expect=check.expect,
                judge=check.judge,
                status="fail",
                detail=f"unmapped expect for citation_validity: {check.expect}",
            )

    elif check.metric == "claim_to_source":
        if check.expect == "fail":
            ok = obs.claim_supported is False
        elif check.expect == "fail_or_qualify":
            ok = obs.claim_supported is False or obs.claim_qualified is True
        else:
            return CheckResult(
                metric=check.metric,
                expect=check.expect,
                judge=check.judge,
                status="fail",
                detail=f"unmapped expect for claim_to_source: {check.expect}",
            )

    elif check.metric == "planted_error_detection":
        if check.expect in {"detect", "surface_alternative"}:
            ok = obs.planted_error_detected is True
        elif check.expect == "n/a_outage":
            ok = True  # outage cases do not require a scientific plant detect
            detail = detail or "outage path — planted_error N/A"
        else:
            return CheckResult(
                metric=check.metric,
                expect=check.expect,
                judge=check.judge,
                status="fail",
                detail=f"unmapped expect for planted_error_detection: {check.expect}",
            )

    elif check.metric == "verification_coverage":
        ok = obs.verification_outcome == check.expect

    elif check.metric == "failure_behavior":
        if check.expect == "no_false_final":
            ok = obs.false_final_emitted is False and (
                obs.failure_outcome in {None, "no_false_final", "run_or_gate_failed", "tool_summary_failure"}
                or obs.verification_outcome == "stale_reject"
            )
            # Prefer explicit failure_outcome when set.
            if obs.failure_outcome == "no_false_final":
                ok = obs.false_final_emitted is False
        else:
            ok = obs.failure_outcome == check.expect and obs.false_final_emitted is False

    elif check.metric == "latency":
        if check.expect == "bounded_fail":
            ok = obs.latency_bounded is True and obs.false_final_emitted is False
        else:
            return CheckResult(
                metric=check.metric,
                expect=check.expect,
                judge=check.judge,
                status="fail",
                detail=f"unmapped expect for latency: {check.expect}",
            )

    elif check.metric == "token_cost":
        ok = obs.token_cost_recorded is True

    elif check.metric == "redundant_tools":
        if check.expect == "no_requirement":
            ok = obs.redundant_tools_excess is not True
        else:
            ok = obs.redundant_tools_excess is False

    else:
        return CheckResult(
            metric=check.metric,
            expect=check.expect,
            judge=check.judge,
            status="fail",
            detail=f"no scorer for metric {check.metric}",
        )

    return CheckResult(
        metric=check.metric,
        expect=check.expect,
        judge=check.judge,
        status="pass" if ok else "fail",
        detail=detail,
        rubric_id=check.rubric_id,
    )


def run_case(case: GoldCase, snapshot: RunSnapshot) -> CaseRunResult:
    if snapshot.case_id != case.case_id:
        raise ValueError(
            f"case/snapshot id mismatch: {case.case_id!r} vs {snapshot.case_id!r}"
        )
    results = [score_check(check, snapshot.observations) for check in case.expected_checks]
    deterministic = [r for r in results if r.status != "pending_human"]
    pending = sum(1 for r in results if r.status == "pending_human")
    return CaseRunResult(
        case_id=case.case_id,
        mode=snapshot.mode,
        checks=results,
        deterministic_passed=all(r.status == "pass" for r in deterministic),
        pending_human=pending,
    )


def run_fixture_suite(
    root: Path | None = None,
    *,
    mode: EvalMode = EvalMode.SWARM_GATE,
) -> FixtureSuiteResult:
    """Load gold + mode snapshots; score every case. Default mode = Swarm+gate."""
    validate_gold_rubric_policy(root)
    cases = load_gold_set(root)
    case_results: list[CaseRunResult] = []
    for case in cases:
        snap = load_run_snapshot(case.case_id, root, mode=mode)
        case_results.append(run_case(case, snap))
    det_checks = [
        c for result in case_results for c in result.checks if c.status != "pending_human"
    ]
    pending = sum(r.pending_human for r in case_results)
    return FixtureSuiteResult(
        mode=mode.value,
        cases=case_results,
        passed=all(r.deterministic_passed for r in case_results),
        deterministic_check_count=len(det_checks),
        pending_human_count=pending,
    )


def write_suite_json(result: FixtureSuiteResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        result.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    """``python -m axiom_research.eval.fixture_runner`` — Swarm+gate CI, no network."""
    result = run_fixture_suite(mode=EvalMode.SWARM_GATE)
    out = gold_root().parent / "reports" / "fixture_suite_latest.json"
    write_suite_json(result, out)
    print(
        f"fixture suite mode={result.mode}: passed={result.passed} "
        f"deterministic={result.deterministic_check_count} "
        f"pending_human={result.pending_human_count} "
        f"report={out}"
    )
    for case in result.cases:
        failed = [c for c in case.checks if c.status == "fail"]
        if failed:
            print(f"  FAIL {case.case_id}: {[c.metric for c in failed]}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
