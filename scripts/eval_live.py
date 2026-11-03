#!/usr/bin/env python3
"""Operator entry: live eval probe (not CI).

Usage:
  docker compose up -d --build mcp-literature mcp-materials mcp-research-data
  EVAL_LIVE=1 .venv/bin/python scripts/eval_live.py

CI fixture paths (no network):
  .venv/bin/python -m axiom_research.eval.fixture_runner   # swarm_gate only
  .venv/bin/python -m axiom_research.eval.comparison       # three-way
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from axiom_research.eval.live_runner import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
