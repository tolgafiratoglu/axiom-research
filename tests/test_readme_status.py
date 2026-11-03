"""9.5 — README status reflects completed 0–9 demo path (not pre-implementation)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "ReadMe.md"
ROADMAP = ROOT / "RoadMap.md"


def test_readme_status_is_no_longer_pre_implementation() -> None:
    text = README.read_text(encoding="utf-8")
    assert "**Status:**" in text
    status_line = next(
        line for line in text.splitlines() if line.startswith("**Status:**")
    )
    assert "pre-implementation" not in status_line.lower()
    assert "interview-ready" in status_line.lower()
    assert "DEMO.md" in status_line


def test_roadmap_phase_9_demo_path_checkboxes_complete() -> None:
    text = ROADMAP.read_text(encoding="utf-8")
    # All numbered 9.x items marked done.
    for item in ("9.1", "9.2", "9.3", "9.4", "9.5"):
        assert f"- [x] **{item}**" in text
    assert "- [ ] **9." not in text
