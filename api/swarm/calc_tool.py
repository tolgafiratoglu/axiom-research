"""Deterministic local calculation tool (Data Analyst only; no MCP)."""

from __future__ import annotations

from typing import Any

from strands import tool

from api.swarm.policy import CALC_TOOL_NAME
from axiom_research.calculations import CalculationError, replay_formula


def build_replay_calculate_tool() -> Any:
    @tool(
        name=CALC_TOOL_NAME,
        description=(
            "Deterministic arithmetic over named numeric inputs. "
            "Returns inputs, formula, unit, and output. Does not call MCP."
        ),
    )
    def replay_calculate(
        inputs: dict[str, float],
        formula: str,
        unit: str,
    ) -> dict[str, Any]:
        if not (unit or "").strip():
            raise CalculationError("calculations require a unit")
        output = replay_formula(inputs, formula)
        return {
            "inputs": inputs,
            "formula": formula,
            "unit": unit,
            "output": output,
        }

    return replay_calculate
