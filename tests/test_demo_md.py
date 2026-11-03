"""9.2 — DEMO.md walkthrough covers compose, ask, handoff / MCP / A2A / sticky."""

from __future__ import annotations

from pathlib import Path

from axiom_research.demo.pins import CANONICAL_QUESTION

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "DEMO.md"


def test_demo_md_exists_and_names_canonical_question() -> None:
    assert DEMO.is_file()
    text = DEMO.read_text(encoding="utf-8")
    assert CANONICAL_QUESTION in text


def test_demo_md_covers_compose_ask_and_four_signals() -> None:
    text = DEMO.read_text(encoding="utf-8")
    assert "docker compose up -d --build" in text
    assert "AXIOM_LIVE_BOOTSTRAP" in text
    assert '"type": "ask"' in text or '"type":"ask"' in text
    # Four interview signals
    assert "agent.handoff" in text
    assert "tool.summary" in text or "evidence.updated" in text
    assert "a2a.verification" in text
    assert "answer.final" in text
    assert "sticky" in text.lower()
    # Pins + layout-only path
    assert "canonical_pins.json" in text
    assert "demo=layout" in text
    assert "ws://127.0.0.1:8200/ws/session" in text or "8200/ws/session" in text
