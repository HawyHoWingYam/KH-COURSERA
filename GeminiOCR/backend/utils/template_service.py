"""Utility helpers for managing document type templates."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple


logger = logging.getLogger(__name__)

_REQUIRED_TOP_LEVEL_KEYS: Tuple[str, ...] = (
    "template_name",
    "version",
    "column_order",
    "column_definitions",
)


def sanitize_template_version(version: str) -> str:
    """Sanitize template version for safe filesystem/S3 usage."""

    if not isinstance(version, str):
        return "latest"

    cleaned = version.strip() or "latest"
    # Allow alphanumerics, dots, dashes, and underscores. Replace others with underscore.
    return re.sub(r"[^0-9A-Za-z._-]", "_", cleaned)


def build_template_object_name(doc_type_id: int, version: str) -> str:
    """Return S3 object key (without upload prefix) for a template."""

    safe_version = sanitize_template_version(version)
    return f"templates/document_types/{doc_type_id}/template_v{safe_version}.json"


def validate_template_payload(template_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate core structure of uploaded template JSON.

    Raises:
        ValueError: if the payload fails basic structural validation.
    """

    if not isinstance(template_data, dict):
        raise ValueError("Template payload must be a JSON object")

    missing = [key for key in _REQUIRED_TOP_LEVEL_KEYS if key not in template_data]
    if missing:
        raise ValueError(f"Missing required template fields: {', '.join(missing)}")

    column_order = template_data["column_order"]
    column_definitions = template_data["column_definitions"]

    if not isinstance(column_order, list) or not column_order:
        raise ValueError("column_order must be a non-empty array of column names")

    if not all(isinstance(name, str) and name.strip() for name in column_order):
        raise ValueError("column_order entries must be non-empty strings")

    if not isinstance(column_definitions, dict) or not column_definitions:
        raise ValueError("column_definitions must be a non-empty mapping")

    for column in column_order:
        if column not in column_definitions:
            raise ValueError(
                f"Column '{column}' listed in column_order is missing from column_definitions"
            )

    _validate_column_definitions(column_definitions)

    source_data = template_data.get("source_data")
    if source_data and source_data.lower() != "mapped_csv":
        raise ValueError("source_data must be 'mapped_csv' when provided")

    return template_data


def _validate_column_definitions(column_definitions: Dict[str, Any]) -> None:
    """Validate individual column definitions."""

    allowed_types = {"source", "computed", "constant"}

    for column_name, definition in column_definitions.items():
        if not isinstance(definition, dict):
            raise ValueError(f"Column '{column_name}' definition must be an object")

        column_type = definition.get("type")
        if column_type not in allowed_types:
            raise ValueError(
                f"Column '{column_name}' has unsupported type '{column_type}'."
                " Allowed types: source, computed, constant"
            )

        if column_type == "source" and not definition.get("source_column"):
            raise ValueError(f"Column '{column_name}' missing source_column for source type")

        if column_type == "computed" and not definition.get("expression"):
            raise ValueError(f"Column '{column_name}' missing expression for computed type")

        if column_type == "constant" and "value" not in definition:
            raise ValueError(f"Column '{column_name}' missing value for constant type")


def collect_computed_expressions(column_definitions: Dict[str, Any]) -> Dict[str, str]:
    """Return mapping of column name to expression for computed columns."""

    expressions: Dict[str, str] = {}
    for column_name, definition in column_definitions.items():
        if definition.get("type") == "computed" and isinstance(definition.get("expression"), str):
            expressions[column_name] = definition["expression"]
    return expressions


def pretty_print_template(template_data: Dict[str, Any]) -> str:
    """Return compact JSON representation for logging."""

    try:
        return json.dumps(template_data, ensure_ascii=False)
    except Exception:
        return str(template_data)


_EXPRESSION_VAR_PATTERN = re.compile(r"\{([^{}]+)\}")
_TEMPLATE_VERSION_PATTERN = re.compile(r"template_v([^/]+?)\.json$")


def extract_expression_variables(expression: str) -> List[str]:
    """Extract placeholder variables from a computed column expression."""

    if not isinstance(expression, str):
        return []
    return [match.strip() for match in _EXPRESSION_VAR_PATTERN.findall(expression) if match.strip()]


def extract_template_version_from_path(template_path: Optional[str]) -> Optional[str]:
    """Attempt to extract the version segment from a template storage path."""

    if not template_path:
        return None

    match = _TEMPLATE_VERSION_PATTERN.search(template_path)
    if not match:
        return None

    return match.group(1)
