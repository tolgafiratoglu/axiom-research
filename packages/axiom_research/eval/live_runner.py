"""Manual live-API eval runner (operator only — not CI).

Requires ``EVAL_LIVE=1``. Does not run during pytest. Hits Compose health and
records a probe report. Fixture three-way compare (no network) is:

  python -m axiom_research.eval.comparison
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx2

from axiom_research.eval.gold import gold_root, load_gold_set
from axiom_research.eval.rubrics import validate_gold_rubric_policy

DEFAULT_HEALTH = (
    "http://127.0.0.1:8210/health",
    "http://127.0.0.1:8211/health",
    "http://127.0.0.1:8212/health",
)


def _require_live_flag() -> None:
    if os.environ.get("EVAL_LIVE", "").strip() != "1":
        raise SystemExit(
            "Refusing live eval: set EVAL_LIVE=1 (operator-only). "
            "CI must use: python -m axiom_research.eval.fixture_runner"
        )


async def probe_mcp_health(urls: tuple[str, ...] = DEFAULT_HEALTH) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    async with httpx2.AsyncClient(timeout=10.0) as http:
        for url in urls:
            try:
                response = await http.get(url)
                results.append(
                    {
                        "url": url,
                        "ok": response.status_code == 200,
                        "status_code": response.status_code,
                    }
                )
            except Exception as exc:  # noqa: BLE001 — operator probe
                results.append({"url": url, "ok": False, "error": str(exc)})
    return results


def write_live_probe_report(
    *,
    health: list[dict[str, object]],
    case_ids: list[str],
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "mode": "live",
        "ts": datetime.now(tz=UTC).isoformat(),
        "note": (
            "Live MCP health probe (operator). CI ground truth is the fixture "
            "three-way comparison: python -m axiom_research.eval.comparison "
            "(modes: one_agent_no_gate, one_agent_gate, swarm_gate; shared budgets)."
        ),
        "comparison_modes": [
            "one_agent_no_gate",
            "one_agent_gate",
            "swarm_gate",
        ],
        "gold_case_ids": case_ids,
        "mcp_health": health,
        "all_mcp_healthy": all(bool(row.get("ok")) for row in health),
    }
    path.write_text(
        __import__("json").dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


async def run_live_probe(report_path: Path | None = None) -> int:
    _require_live_flag()
    validate_gold_rubric_policy()
    cases = load_gold_set()
    health = await probe_mcp_health()
    out = report_path or (gold_root().parent / "reports" / "live_probe_latest.json")
    write_live_probe_report(
        health=health,
        case_ids=[c.case_id for c in cases],
        path=out,
    )
    print(f"live probe report: {out}")
    for row in health:
        print(f"  {row}")
    return 0 if all(bool(r.get("ok")) for r in health) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AxiomResearch live eval probe (EVAL_LIVE=1 required)."
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write probe JSON here (default eval/reports/live_probe_latest.json)",
    )
    args = parser.parse_args(argv)
    return asyncio.run(run_live_probe(report_path=args.report))


if __name__ == "__main__":
    raise SystemExit(main())
