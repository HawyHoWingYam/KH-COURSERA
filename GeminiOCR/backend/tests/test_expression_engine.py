"""Unit tests for the ExpressionEngine helper."""

from __future__ import annotations

import math

import pytest

from utils.expression_engine import ExpressionEngine


@pytest.fixture()
def engine() -> ExpressionEngine:
    return ExpressionEngine()


def test_parse_expression_captures_variables(engine: ExpressionEngine) -> None:
    parsed = engine.parse_expression("concat({FIRST}, '-', {SECOND}, '-', {FIRST})")

    assert parsed.variables == ["FIRST", "SECOND", "FIRST"]
    assert "__get__('FIRST')" in parsed.expression
    assert parsed.original == "concat({FIRST}, '-', {SECOND}, '-', {FIRST})"


def test_parse_expression_rejects_empty_values(engine: ExpressionEngine) -> None:
    with pytest.raises(ValueError):
        engine.parse_expression("")


def test_parse_expression_respects_length_limit() -> None:
    engine = ExpressionEngine(max_expression_length=5)
    with pytest.raises(ValueError):
        engine.parse_expression("a" * 6)


def test_evaluate_expression_with_builtin_functions(engine: ExpressionEngine) -> None:
    parsed = engine.parse_expression(
        "concat(upper({name}), '-', substring(replace({code}, ' ', ''), 0, 4))"
    )

    result = engine.evaluate(parsed, {"name": "telecom", "code": " 1234 5678 "})

    assert result == "TELECOM-1234"


def test_evaluate_expression_handles_missing_values_with_default(engine: ExpressionEngine) -> None:
    parsed = engine.parse_expression("{missing} or {present}")

    result = engine.evaluate(parsed, {"present": "value"}, default_value="fallback")

    assert result == "fallback"


def test_evaluate_expression_supports_if_and_math(engine: ExpressionEngine) -> None:
    parsed = engine.parse_expression("if({total} > 0, {total} * 1.2, 0)")

    result = engine.evaluate(parsed, {"total": 100})

    assert math.isclose(result, 120.0)


def test_evaluate_expression_raises_on_invalid_syntax(engine: ExpressionEngine) -> None:
    with pytest.raises(Exception):
        engine.evaluate("concat({a}", {"a": "value"})
