"""Generate special CSV outputs based on template.json definitions."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence

import pandas as pd

from .expression_engine import ExpressionEngine, ParsedExpression
from .file_storage import get_file_storage
from .template_service import (
    collect_computed_expressions,
    extract_expression_variables,
    validate_template_payload,
)


logger = logging.getLogger(__name__)


class SpecialCsvGenerator:
    """Create special CSV DataFrames from mapped DataFrames and templates."""

    def __init__(self, expression_engine: Optional[ExpressionEngine] = None) -> None:
        self.expression_engine = expression_engine or ExpressionEngine()
        self._file_storage = get_file_storage()

    # ------------------------------------------------------------------
    # Template loading / validation
    # ------------------------------------------------------------------
    def load_template_from_s3(self, template_path: str) -> Dict[str, Any]:
        """Load and parse template JSON from S3 or local storage."""

        raw_content = self._file_storage.download_file(template_path)
        if not raw_content:
            raise FileNotFoundError(f"Template file not found: {template_path}")

        try:
            template_json = json.loads(raw_content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid template JSON at {template_path}: {exc}") from exc

        validate_template_payload(template_json)
        return template_json

    def validate_template(self, template_json: Dict[str, Any]) -> None:
        """Validate template structure and log computed column information."""

        validate_template_payload(template_json)
        computed_columns = collect_computed_expressions(template_json["column_definitions"])
        if computed_columns:
            logger.info(
                "Template includes computed columns: %s",
                ", ".join(computed_columns.keys()),
            )

    # ------------------------------------------------------------------
    # Generation API
    # ------------------------------------------------------------------
    def generate_special_csv(
        self,
        standard_df: pd.DataFrame,
        template_config: Dict[str, Any],
    ) -> pd.DataFrame:
        """Generate the special CSV DataFrame based on the template definition."""

        if standard_df is None or standard_df.empty:
            raise ValueError("Standard DataFrame must not be empty for special CSV generation")

        validate_template_payload(template_config)

        column_order: List[str] = template_config["column_order"]
        column_definitions: Dict[str, Any] = template_config["column_definitions"]

        self._validate_columns_exist(standard_df, self._required_source_columns(column_definitions))

        result_df = pd.DataFrame(index=standard_df.index)

        for column_name in column_order:
            definition = column_definitions[column_name]
            column_type = definition.get("type")
            default_value = definition.get("default_value", "")

            if column_type == "source":
                source_column = definition.get("source_column")
                result_df[column_name] = standard_df[source_column]

            elif column_type == "computed":
                expression = definition.get("expression")
                parsed_expression = self.expression_engine.parse_expression(expression)
                result_df[column_name] = self._evaluate_computed_column(
                    standard_df,
                    parsed_expression,
                    default_value,
                    column_name,
                )

            elif column_type == "constant":
                result_df[column_name] = definition.get("value", default_value)

            else:
                raise ValueError(f"Unsupported column type '{column_type}' for column '{column_name}'")

            if default_value is not None:
                result_df[column_name] = result_df[column_name].fillna(default_value)

        # Ensure column order aligns with template definition
        result_df = result_df[column_order]

        return result_df

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _evaluate_computed_column(
        self,
        standard_df: pd.DataFrame,
        parsed_expression: ParsedExpression,
        default_value: Optional[Any],
        target_column: str,
    ) -> pd.Series:
        """Evaluate a computed column across the DataFrame."""

        def _compute(row: pd.Series) -> Any:
            context = row.to_dict()
            try:
                value = self.expression_engine.evaluate(parsed_expression, context, default_value)
            except Exception as exc:
                raise ValueError(
                    f"Failed to evaluate expression for column '{target_column}': {exc}"
                ) from exc
            return value

        series = standard_df.apply(_compute, axis=1)

        if default_value is not None:
            return series.fillna(default_value)
        return series

    @staticmethod
    def _required_source_columns(column_definitions: Dict[str, Any]) -> List[str]:
        required: List[str] = []
        for definition in column_definitions.values():
            if definition.get("type") == "source" and definition.get("source_column"):
                required.append(definition["source_column"])
            elif definition.get("type") == "computed":
                required.extend(extract_expression_variables(definition.get("expression")))
        return list(dict.fromkeys(required))

    @staticmethod
    def _validate_columns_exist(df: pd.DataFrame, columns: Sequence[str]) -> None:
        missing = [column for column in columns if column and column not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns in standard DataFrame: {missing}")
