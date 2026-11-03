"""8.4 — three-way comparison with shared budgets; unbundle Swarm vs Verifier."""

from __future__ import annotations

from axiom_research.eval.comparison import (
    run_three_way_comparison,
    write_comparison_json,
)
from axiom_research.eval.fixture_runner import run_fixture_suite
from axiom_research.eval.gold import REQUIRED_CASE_IDS, load_gold_set
from axiom_research.eval.modes import (
    COMPARISON_MODES,
    EvalMode,
    SharedBudgets,
)
from axiom_research.eval.snapshot import load_run_snapshot, mode_snapshots_dir


def test_shared_budgets_match_settings_defaults() -> None:
    budgets = SharedBudgets.from_settings()
    assert budgets.max_handoffs == 8
    assert budgets.max_iterations == 8
    assert budgets.execution_timeout_seconds == 180.0
    assert budgets.node_timeout_seconds == 45.0
    assert budgets.max_tokens_per_run == 100_000
    assert budgets.max_cost_usd_per_run == 1.0
    assert budgets.mcp_servers == (
        "mcp-literature",
        "mcp-materials",
        "mcp-research-data",
    )


def test_each_mode_has_all_gold_snapshots() -> None:
    cases = load_gold_set()
    assert [c.case_id for c in cases] == list(REQUIRED_CASE_IDS)
    for mode in COMPARISON_MODES:
        for case_id in REQUIRED_CASE_IDS:
            path = mode_snapshots_dir(mode) / f"{case_id}.json"
            assert path.is_file(), path
            snap = load_run_snapshot(case_id, mode=mode)
            assert snap.mode is mode


def test_three_way_comparison_unbundles_gate_and_swarm() -> None:
    result = run_three_way_comparison()
    assert result.budgets_identical is True
    assert set(result.modes) == {m.value for m in COMPARISON_MODES}

    # Full system must still pass gold expects.
    assert result.modes[EvalMode.SWARM_GATE.value].passed is True
    # Weaker arms fail some gold expects by design.
    assert result.modes[EvalMode.ONE_AGENT_NO_GATE.value].passed is False
    assert result.modes[EvalMode.ONE_AGENT_GATE.value].passed is False

    assert len(result.gate_credits) >= 1
    assert all(
        d.weaker_mode is EvalMode.ONE_AGENT_NO_GATE
        and d.stronger_mode is EvalMode.ONE_AGENT_GATE
        for d in result.gate_credits
    )
    assert len(result.swarm_credits) >= 1
    assert all(
        d.weaker_mode is EvalMode.ONE_AGENT_GATE and d.stronger_mode is EvalMode.SWARM_GATE
        for d in result.swarm_credits
    )
    # At least one swarm credit is Challenger plant detection (not verifier).
    assert any(
        d.case_id == "planted_challenger_alternative"
        and d.metric == "planted_error_detection"
        for d in result.swarm_credits
    )


def test_comparison_json_roundtrip(tmp_path) -> None:
    result = run_three_way_comparison()
    out = tmp_path / "three_way.json"
    write_comparison_json(result, out)
    text = out.read_text(encoding="utf-8")
    assert "one_agent_no_gate" in text
    assert "one_agent_gate" in text
    assert "swarm_gate" in text
    assert "gate_credits" in text
    assert "swarm_credits" in text
    assert '"budgets_identical": true' in text


def test_default_fixture_suite_is_swarm_gate() -> None:
    suite = run_fixture_suite()
    assert suite.mode == EvalMode.SWARM_GATE.value
    assert suite.passed is True
