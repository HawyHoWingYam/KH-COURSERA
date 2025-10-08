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

        # === COMPREHENSIVE DIAGNOSTIC LOGGING ===
        logger.info(f"=== SPECIAL CSV GENERATION DIAGNOSTICS ===")
        logger.info(f"Input DataFrame shape: {standard_df.shape}")
        logger.info(f"Input DataFrame columns: {list(standard_df.columns)}")

        if 'Matched' in standard_df.columns:
            logger.info(f"✓ Matched column EXISTS in DataFrame")
            try:
                matched_values = standard_df['Matched'].value_counts().to_dict()
                logger.info(f"  - Matched value counts: {matched_values}")
            except Exception as e:
                logger.error(f"  - Error analyzing Matched column: {e}")
                logger.info(f"  - Matched column sample: {standard_df['Matched'].head().tolist()}")

            # Additional validation for Matched column
            try:
                matched_mask = standard_df['Matched'].astype(bool)
                matched_count = matched_mask.sum()
                total_count = len(matched_mask)
                logger.info(f"  - Matched rows after bool conversion: {matched_count}/{total_count}")

                if matched_count == 0:
                    logger.warning(f"  ⚠️  ALL ROWS ARE UNMATCHED! This suggests a problem with Matched detection")
                elif matched_count == total_count:
                    logger.info(f"  ✓ All rows are matched")
                else:
                    logger.info(f"  ✓ Mixed match status: {matched_count} matched, {total_count - matched_count} unmatched")

            except Exception as e:
                logger.error(f"  ✗ Failed to convert Matched column to bool: {e}")
        else:
            logger.warning(f"✗ Matched column NOT FOUND in DataFrame")
            logger.info(f"  Available columns: {list(standard_df.columns)}")

        column_order: List[str] = template_config["column_order"]
        column_definitions: Dict[str, Any] = template_config["column_definitions"]

        # Log computed columns details
        computed_columns = []
        source_columns = []
        constant_columns = []

        for column_name in column_order:
            definition = column_definitions[column_name]
            column_type = definition.get("type")
            if column_type == "computed":
                expression = definition.get("expression")
                computed_columns.append(f"{column_name}='{expression}'")
            elif column_type == "source":
                source_col = definition.get("source_column")
                source_columns.append(f"{column_name}←{source_col}")
            elif column_type == "constant":
                const_val = definition.get("value", "")
                constant_columns.append(f"{column_name}='{const_val}'")

        logger.info(f"Template analysis:")
        logger.info(f"  - Computed columns ({len(computed_columns)}): {computed_columns}")
        logger.info(f"  - Source columns ({len(source_columns)}): {source_columns}")
        logger.info(f"  - Constant columns ({len(constant_columns)}): {constant_columns}")
        logger.info(f"=== END DIAGNOSTICS ===")
        # === END DIAGNOSTIC LOGGING ===

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

                logger.info(f"Processing computed column '{column_name}' with expression: '{expression}'")

                # Decide whether to use Matched-based logic with robust validation
                use_matched_logic = False
                matched_mask = None

                if 'Matched' in standard_df.columns:
                    try:
                        # Validate Matched column and create boolean mask
                        matched_mask = standard_df['Matched'].astype(bool)
                        matched_count = matched_mask.sum()
                        total_count = len(matched_mask)

                        logger.info(f"Matched analysis for '{column_name}': {matched_count}/{total_count} rows matched")

                        # Only use Matched logic if we have both matched and unmatched rows
                        # AND there's at least some matched rows
                        if 0 < matched_count < total_count:
                            use_matched_logic = True
                            logger.info(f"Using Matched-based logic for '{column_name}': {matched_count} matched, {total_count - matched_count} unmatched")
                        elif matched_count == 0:
                            logger.warning(f"ALL rows unmatched for '{column_name}'. This suggests a Matched detection issue - using fallback logic")
                        elif matched_count == total_count:
                            logger.info(f"All rows matched for '{column_name}'. Using standard computation for all rows")

                    except Exception as e:
                        logger.error(f"Failed to process Matched column for '{column_name}': {e}. Using fallback logic")
                else:
                    logger.info(f"No Matched column found for '{column_name}'. Using standard computation for all rows")

                # Apply the appropriate logic
                if use_matched_logic:
                    # Use Matched-based logic (mixed match status)
                    computed_values = pd.Series(index=standard_df.index, data=default_value)

                    # Merge standard_df with result_df for calculation context
                    merged_df = pd.concat([standard_df, result_df], axis=1)

                    # Calculate only for matched rows
                    matched_results = self._evaluate_computed_column(
                        merged_df[matched_mask],
                        parsed_expression,
                        default_value,
                        column_name,
                    )
                    computed_values[matched_mask] = matched_results

                    # Log statistics
                    unmatched_count = (~matched_mask).sum()
                    if unmatched_count > 0:
                        logger.info(f"Computed column '{column_name}': {matched_count} calculated, {unmatched_count} used default value")

                    result_df[column_name] = computed_values

                else:
                    # Use original logic (no Matched column, or all matched/unmatched)
                    logger.info(f"Computed column '{column_name}': using standard computation for all rows")
                    merged_df = pd.concat([standard_df, result_df], axis=1)
                    result_df[column_name] = self._evaluate_computed_column(
                        merged_df,
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
        """Extract columns that must exist in the INPUT DataFrame (not template-created columns)."""
        required: List[str] = []
        for definition in column_definitions.values():
            # Only "source" type columns require input columns
            if definition.get("type") == "source" and definition.get("source_column"):
                required.append(definition["source_column"])
            # Note: Computed columns can reference template-created columns,
            # so we don't validate their variables against input DataFrame
        return list(dict.fromkeys(required))

    @staticmethod
    def _validate_columns_exist(df: pd.DataFrame, columns: Sequence[str]) -> None:
        missing = [column for column in columns if column and column not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns in standard DataFrame: {missing}")
