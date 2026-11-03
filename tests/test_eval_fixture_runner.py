"""8.3 — fixture/snapshot runner (CI); live runner stays operator-gated."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from axiom_research.eval.fixture_runner import (
    run_fixture_suite,
    score_check,
    write_suite_json,
)
from axiom_research.eval.gold import ExpectedCheck, load_gold_set
from axiom_research.eval.live_runner import main as live_main
from axiom_research.eval.modes import EvalMode
from axiom_research.eval.snapshot import load_run_snapshot, mode_snapshots_dir


def test_all_gold_cases_have_fixture_snapshots() -> None:
    cases = load_gold_set()
    for case in cases:
        path = mode_snapshots_dir(EvalMode.SWARM_GATE) / f"{case.case_id}.json"
        assert path.is_file(), f"missing snapshot {path}"
        snap = load_run_snapshot(case.case_id, mode=EvalMode.SWARM_GATE)
        assert snap.mode is EvalMode.SWARM_GATE
        assert snap.case_id == case.case_id


def test_fixture_suite_passes_deterministic_checks() -> None:
    result = run_fixture_suite(mode=EvalMode.SWARM_GATE)
    assert result.passed is True
    assert result.mode == EvalMode.SWARM_GATE.value
    assert result.deterministic_check_count >= 20
    assert result.pending_human_count == 2  # handoff_usefulness × 2 cases
    for case in result.cases:
        assert case.deterministic_passed, case.case_id
        for check in case.checks:
            if check.judge == "human_rubric":
                assert check.status == "pending_human"
            else:
                assert check.status == "pass", (case.case_id, check)


def test_human_rubric_never_auto_scored_as_llm() -> None:
    check = ExpectedCheck(
        metric="handoff_usefulness",
        expect="challenger_engaged",
        judge="human_rubric",
        rubric_id="handoff_usefulness_v1",
    )
    snap = load_run_snapshot(
        "planted_challenger_alternative", mode=EvalMode.SWARM_GATE
    )
    scored = score_check(check, snap.observations)
    assert scored.status == "pending_human"
    assert "LLM" in (scored.detail or "") or "human" in (scored.detail or "").lower()


def test_write_suite_json_roundtrip(tmp_path: Path) -> None:
    result = run_fixture_suite(mode=EvalMode.SWARM_GATE)
    out = tmp_path / "fixture_suite.json"
    write_suite_json(result, out)
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert '"mode": "swarm_gate"' in text
    assert '"passed": true' in text


def test_live_runner_refuses_without_eval_live_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EVAL_LIVE", raising=False)
    with pytest.raises(SystemExit) as exc:
        live_main([])
    assert exc.value.code != 0
    assert os.environ.get("EVAL_LIVE") != "1"
