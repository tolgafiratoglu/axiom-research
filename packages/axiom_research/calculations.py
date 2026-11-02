"""Deterministic calculation replay for Evidence Ledger records."""

from __future__ import annotations

import ast
import operator
from typing import Any

from axiom_research.ledger import CalculationRecord

_BIN_OPS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}

_UNARY_OPS: dict[type[ast.unaryop], Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class CalculationError(ValueError):
    """Formula cannot be replayed or output does not match."""


def replay_formula(inputs: dict[str, Any], formula: str) -> float | int:
    """Evaluate a restricted arithmetic formula against ``inputs``."""
    try:
        tree = ast.parse(formula.strip(), mode="eval")
    except SyntaxError as exc:
        raise CalculationError(f"invalid formula: {formula!r}") from exc
    return _eval_node(tree.body, inputs)


def _eval_node(node: ast.AST, inputs: dict[str, Any]) -> float | int:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in inputs:
            raise CalculationError(f"unknown input: {node.id}")
        value = inputs[node.id]
        if not isinstance(value, (int, float)):
            raise CalculationError(f"input {node.id!r} must be numeric")
        return value
    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise CalculationError("unsupported operator")
        return op(_eval_node(node.left, inputs), _eval_node(node.right, inputs))
    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise CalculationError("unsupported unary operator")
        return op(_eval_node(node.operand, inputs))
    raise CalculationError("unsupported formula expression")


def assert_replayable(record: CalculationRecord) -> None:
    if not (record.unit or "").strip():
        raise CalculationError("calculations require a unit")
    if not record.formula.strip():
        raise CalculationError("calculations require a formula")
    if not record.inputs:
        raise CalculationError("calculations require inputs")
    replayed = replay_formula(record.inputs, record.formula)
    if isinstance(record.output, (int, float)):
        if abs(float(replayed) - float(record.output)) > 1e-9:
            raise CalculationError(
                f"output {record.output!r} does not match replay {replayed!r}"
            )
    elif str(record.output) != str(replayed):
        raise CalculationError(
            f"output {record.output!r} does not match replay {replayed!r}"
        )
