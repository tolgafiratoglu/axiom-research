"""Checked-in run snapshots for the CI fixture runner (8.3 / 8.4).

Layout: ``eval/snapshots/{mode}/{case_id}.json``
Snapshots record structured observations — never live API payloads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from axiom_research.eval.gold import gold_root
from axiom_research.eval.modes import EvalMode


class SnapshotObservations(BaseModel):
    """Deterministic facts derived from a frozen fixture run (or authored for CI)."""

    model_config = ConfigDict(extra="forbid")

    citation_valid: bool | None = None
    claim_supported: bool | None = None
    claim_qualified: bool | None = None
    planted_error_detected: bool | None = None
    planted_error_kind: str | None = None
    verification_outcome: str | None = None
    failure_outcome: str | None = None
    false_final_emitted: bool = False
    fabricated_sources_present: bool = False
    latency_bounded: bool | None = None
    token_cost_recorded: bool | None = None
    redundant_tools_excess: bool | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    notes: str | None = None


class RunSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    mode: EvalMode
    observations: SnapshotObservations
    event_types: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


def snapshots_root(explicit: Path | None = None) -> Path:
    return gold_root(explicit).parent / "snapshots"


def mode_snapshots_dir(mode: EvalMode, root: Path | None = None) -> Path:
    return snapshots_root(root) / mode.value


def load_run_snapshot(
    case_id: str,
    root: Path | None = None,
    *,
    mode: EvalMode = EvalMode.SWARM_GATE,
) -> RunSnapshot:
    path = mode_snapshots_dir(mode, root) / f"{case_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    snap = RunSnapshot.model_validate(data)
    if snap.case_id != case_id:
        raise ValueError(f"snapshot case_id mismatch: {case_id!r} vs {snap.case_id!r}")
    if snap.mode != mode:
        raise ValueError(
            f"snapshot mode mismatch: path {mode.value!r} vs payload {snap.mode.value!r}"
        )
    return snap


def load_run_snapshots(
    case_ids: list[str],
    root: Path | None = None,
    *,
    mode: EvalMode = EvalMode.SWARM_GATE,
) -> dict[str, RunSnapshot]:
    return {cid: load_run_snapshot(cid, root, mode=mode) for cid in case_ids}
