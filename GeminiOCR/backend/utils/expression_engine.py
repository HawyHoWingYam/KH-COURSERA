"""Expression evaluation utilities for computed template columns."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

from simpleeval import SimpleEval

from .template_service import extract_expression_variables


@dataclass
class ParsedExpression:
    """Represents a parsed computed-column expression."""

    original: str
    expression: str
    variables: List[str]


class ExpressionEngine:
    """Safe expression evaluator with template-specific helpers."""

    def __init__(self, max_expression_length: int = 1000) -> None:
        self._base_functions: Dict[str, Callable[..., Any]] = {
            "concat": self._fn_concat,
            "replace": self._fn_replace,
            "split": self._fn_split,
            "substring": self._fn_substring,
            "upper": self._fn_upper,
            "lower": self._fn_lower,
            "trim": self._fn_trim,
            "strip": self._fn_trim,
            "if": self._fn_if,
            "iif": self._fn_if,
        }
        self.max_expression_length = max_expression_length

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def parse_expression(self, expr_string: str) -> ParsedExpression:
        """Prepare expression for evaluation and capture referenced variables."""

        if not isinstance(expr_string, str) or not expr_string.strip():
            raise ValueError("Expression must be a non-empty string")

        if len(expr_string) > self.max_expression_length:
            raise ValueError(
                f"Expression exceeds maximum length of {self.max_expression_length} characters"
            )

        variables = extract_expression_variables(expr_string)
        processed = expr_string
        for column_name in set(variables):
            placeholder = f"{{{column_name}}}"
            processed = processed.replace(placeholder, f"__get__('{column_name}')")

        # Translate reserved keywords to safe identifiers for SimpleEval parsing
        processed = re.sub(r"(?<![A-Za-z0-9_])if\s*\(", "iif(", processed)

        return ParsedExpression(original=expr_string, expression=processed, variables=variables)

    def evaluate(
        self,
        expression: Union[str, ParsedExpression],
        context: Dict[str, Any],
        default_value: Optional[Any] = None,
    ) -> Any:
        """Evaluate an expression against the provided context."""

        parsed = self.parse_expression(expression) if isinstance(expression, str) else expression

        evaluator = SimpleEval()
        evaluator.names = {}
        evaluator.functions = {
            **self._base_functions,
            "__get__": lambda column_name: context.get(column_name, default_value),
        }

        return evaluator.eval(parsed.expression)

    def evaluate_with_context(  # pragma: no cover - convenience wrapper
        self, expression: str, context: Dict[str, Any], default_value: Optional[Any] = None
    ) -> Any:
        """Backward-compatible helper to evaluate raw expressions."""

        parsed = self.parse_expression(expression)
        return self.evaluate(parsed, context, default_value=default_value)

    # ------------------------------------------------------------------
    # Built-in functions
    # ------------------------------------------------------------------
    @staticmethod
    def _coalesce_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value)

    def _fn_concat(self, *args: Any) -> str:
        return "".join(self._coalesce_text(arg) for arg in args)

    @staticmethod
    def _fn_replace(value: Any, old: str, new: str) -> str:
        return ExpressionEngine._coalesce_text(value).replace(old, new)

    @staticmethod
    def _fn_split(value: Any, delimiter: str, maxsplit: int = -1) -> List[str]:
        return ExpressionEngine._coalesce_text(value).split(delimiter, maxsplit)

    @staticmethod
    def _fn_substring(value: Any, start: int, length: Optional[int] = None) -> str:
        text = ExpressionEngine._coalesce_text(value)
        if length is None:
            return text[start:]
        end = start + length
        return text[start:end]

    @staticmethod
    def _fn_upper(value: Any) -> str:
        return ExpressionEngine._coalesce_text(value).upper()

    @staticmethod
    def _fn_lower(value: Any) -> str:
        return ExpressionEngine._coalesce_text(value).lower()

    @staticmethod
    def _fn_trim(value: Any) -> str:
        return ExpressionEngine._coalesce_text(value).strip()

    @staticmethod
    def _fn_if(condition: Any, true_value: Any, false_value: Any) -> Any:
        return true_value if condition else false_value
