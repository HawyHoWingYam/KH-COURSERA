"""Expression evaluation utilities for computed template columns."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

from simpleeval import SimpleEval

from .template_service import extract_expression_variables

logger = logging.getLogger(__name__)


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
            # Aggregate functions
            "sum_matched": self._fn_sum_matched,
            "count_matched": self._fn_count_matched,
            "avg_matched": self._fn_avg_matched,
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
        dataframe_context: Optional[Any] = None,
    ) -> Any:
        """Evaluate an expression against the provided context."""

        parsed = self.parse_expression(expression) if isinstance(expression, str) else expression

        # Set DataFrame context for aggregate functions
        self._current_dataframe = dataframe_context

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

        # Handle pandas NaN values from DataFrame rows
        import math
        if isinstance(value, float) and math.isnan(value):
            logger.debug(f"🔧 Converting NaN value to empty string")
            return ""

        # Also handle string "nan" which can come from NaN conversion
        if isinstance(value, str) and value.lower() == "nan":
            logger.debug(f"🔧 Converting string 'nan' to empty string")
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

    def _fn_sum_matched(self, column_name: str) -> float:
        """Sum values from a column for all rows where Matched=True"""
        # Access DataFrame from the global context set during evaluation
        import sys
        dataframe_context = getattr(self, '_current_dataframe', None)
        logger.info(f"🔍 sum_matched: column={column_name}, DataFrame context available: {dataframe_context is not None}")

        if dataframe_context is None:
            logger.warning("⚠️ sum_matched: No DataFrame context available, returning 0.0")
            return 0.0

        try:
            logger.info(f"🔍 sum_matched: DataFrame shape={dataframe_context.shape}, Matched column exists={'Matched' in dataframe_context.columns}")
            if 'Matched' not in dataframe_context.columns:
                logger.warning("⚠️ sum_matched: Matched column not found in DataFrame")
                return 0.0

            matched_count = (dataframe_context['Matched'] == True).sum()
            logger.info(f"🔍 sum_matched: Found {matched_count} matched rows")

            if matched_count == 0:
                logger.warning("⚠️ sum_matched: No matched rows found, returning 0.0")
                return 0.0

            matched_rows = dataframe_context[dataframe_context['Matched'] == True]
            logger.info(f"🔍 sum_matched: Target column '{column_name}' exists={column_name in matched_rows.columns}")

            if column_name not in matched_rows.columns:
                logger.warning(f"⚠️ sum_matched: Column '{column_name}' not found in DataFrame")
                return 0.0

            logger.info(f"🔍 sum_matched: Raw column values sample: {matched_rows[column_name].head().tolist()}")
            column_values = matched_rows[column_name].astype(float)
            logger.info(f"🔍 sum_matched: After conversion to float, values: {column_values.head().tolist()}")

            result = column_values.sum()
            logger.info(f"✅ sum_matched: Final result = {result}")
            return result
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"❌ sum_matched: Error processing column '{column_name}': {e}")
            return 0.0

    def _fn_count_matched(self, column_name: str = None) -> int:
        """Count rows where Matched=True (or count non-null values in specific column for matched rows)"""
        dataframe_context = getattr(self, '_current_dataframe', None)
        if dataframe_context is None:
            return 0

        try:
            matched_rows = dataframe_context[dataframe_context['Matched'] == True]
            if column_name:
                return matched_rows[column_name].notna().sum()
            else:
                return len(matched_rows)
        except (KeyError, ValueError, TypeError):
            return 0

    def _fn_avg_matched(self, column_name: str) -> float:
        """Average values from a column for all rows where Matched=True"""
        dataframe_context = getattr(self, '_current_dataframe', None)
        if dataframe_context is None:
            return 0.0

        try:
            matched_rows = dataframe_context[dataframe_context['Matched'] == True]
            column_values = matched_rows[column_name].astype(float)
            return column_values.mean()
        except (KeyError, ValueError, TypeError):
            return 0.0
