"""
Order Processing Pipeline
Handles the complete OCR Order workflow from submission to completion
"""

import asyncio
import json
import os
import tempfile
import zipfile
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Tuple, TYPE_CHECKING
from enum import Enum
from dataclasses import dataclass, field
import logging
import pandas as pd
from difflib import SequenceMatcher
from io import BytesIO, StringIO

from sqlalchemy.orm import Session, sessionmaker, joinedload

from db.database import engine
from db.models import (
    OcrOrder,
    OcrOrderItem,
    OrderItemFile,
    OrderStatus,
    OrderItemStatus,
    OrderItemType,
    Company,
    DocumentType,
    CompanyDocumentConfig,
    File,
    ApiUsage,
)
from main import extract_text_from_image, extract_text_from_pdf
from utils.s3_storage import get_s3_manager
from utils.special_csv_generator import SpecialCsvGenerator
from utils.template_service import sanitize_template_version
from utils.prompt_schema_manager import get_prompt_schema_manager
from utils.excel_converter import json_to_excel, json_to_csv
# Lazy import OneDrive client to avoid hard dependency at module import time
if TYPE_CHECKING:
    from utils.onedrive_client import OneDriveClient  # pragma: no cover - typing only
from utils.mapping_config import MappingItemType
from utils.mapping_config_resolver import MappingConfigResolver
from config_loader import config_loader

logger = logging.getLogger(__name__)


def escape_excel_formulas(value: Any) -> Any:
    """
    Escape values that Excel might interpret as formulas.

    This function prevents Excel from treating values starting with
    formula characters (-, +, =, @) as formulas, which would cause
    "#NAME?" errors in spreadsheet applications.

    Args:
        value: The value to check and potentially escape

    Returns:
        The original value with tab prefix if it starts with formula characters,
        otherwise the original value unchanged
    """
    if isinstance(value, str) and value:
        # Characters that Excel interprets as formula starters
        if value.startswith(('-', '+', '=', '@')):
            logger.debug(f"🔧 Escaping Excel formula-like value: {value}")
            return f"\t{value}"  # Prefix with tab to prevent formula interpretation
    return value


class MatchingStrategy(Enum):
    """Matching strategy options for intelligent field matching"""
    EXACT = "exact"          # Exact match only
    CONTAINS = "contains"    # One field contains the other
    SPLIT = "split"          # Split compound fields and match parts
    FUZZY = "fuzzy"          # Fuzzy matching with similarity threshold
    REGEX = "regex"          # Regular expression matching
    SMART = "smart"          # Intelligent combination of strategies


@dataclass
class MatchingConfig:
    """Configuration for intelligent matching behavior"""
    strategies: List[MatchingStrategy] = field(default_factory=lambda: [MatchingStrategy.EXACT])
    separators: List[str] = field(default_factory=lambda: ["/", ",", ";", "|", "-", "_", ":", ".", " "])
    fuzzy_threshold: float = 0.8  # Similarity threshold for fuzzy matching (0.0-1.0)
    min_match_length: int = 3     # Minimum length for partial matches
    case_sensitive: bool = False  # Case sensitivity for matching
    regex_patterns: Dict[str, str] = field(default_factory=dict)  # Custom regex patterns per field
    priority_order: List[MatchingStrategy] = field(default_factory=lambda: [
        MatchingStrategy.EXACT,
        MatchingStrategy.CONTAINS,
        MatchingStrategy.SPLIT,
        MatchingStrategy.FUZZY
    ])


@dataclass
class MatchResult:
    """Result of a matching operation"""
    success: bool
    strategy: MatchingStrategy
    ocr_value: str
    mapping_value: str
    similarity_score: float = 0.0
    extracted_parts: List[str] = field(default_factory=list)
    match_reason: str = ""


class MatchingEngine:
    """
    Universal intelligent matching engine for flexible field mapping.
    Supports multiple matching strategies for various business scenarios.
    """

    def __init__(self, config: MatchingConfig = None):
        self.config = config or MatchingConfig()
        self.logger = logging.getLogger(f"{__name__}.MatchingEngine")

    def extract_identifiers(self, value: str) -> List[str]:
        """
        Extract all possible identifiers from a compound field.

        Args:
            value: Input string that may contain multiple identifiers

        Returns:
            List of extracted identifier candidates
        """
        if not value or pd.isna(value):
            return []

        value_str = str(value).strip()
        if not value_str:
            return []

        # Start with the original value
        identifiers = [value_str]

        # Split by configured separators
        for separator in self.config.separators:
            new_parts = []
            for identifier in identifiers:
                parts = [part.strip() for part in identifier.split(separator) if part.strip()]
                if len(parts) > 1:  # Only split if it produces multiple parts
                    new_parts.extend(parts)
                else:
                    new_parts.append(identifier)
            identifiers = new_parts

        # Remove duplicates while preserving order
        unique_identifiers = []
        seen = set()
        for identifier in identifiers:
            if identifier not in seen and len(identifier) >= self.config.min_match_length:
                unique_identifiers.append(identifier)
                seen.add(identifier)

        # Add normalized versions
        normalized_identifiers = []
        for identifier in unique_identifiers:
            # Original form
            normalized_identifiers.append(identifier)

            # Remove all non-alphanumeric characters
            alphanumeric_only = re.sub(r'[^a-zA-Z0-9]', '', identifier)
            if alphanumeric_only and alphanumeric_only != identifier:
                normalized_identifiers.append(alphanumeric_only)

            # Digits only
            digits_only = re.sub(r'[^0-9]', '', identifier)
            if digits_only and len(digits_only) >= self.config.min_match_length:
                normalized_identifiers.append(digits_only)

        # Remove duplicates again
        final_identifiers = []
        seen = set()
        for identifier in normalized_identifiers:
            if identifier not in seen and len(identifier) >= self.config.min_match_length:
                final_identifiers.append(identifier)
                seen.add(identifier)

        self.logger.debug(f"Extracted identifiers from '{value_str}': {final_identifiers}")
        return final_identifiers

    def exact_match(self, ocr_value: str, mapping_value: str) -> MatchResult:
        """Perform exact string matching"""
        ocr_norm = str(ocr_value).strip()
        mapping_norm = str(mapping_value).strip()

        if not self.config.case_sensitive:
            ocr_norm = ocr_norm.lower()
            mapping_norm = mapping_norm.lower()

        success = ocr_norm == mapping_norm

        return MatchResult(
            success=success,
            strategy=MatchingStrategy.EXACT,
            ocr_value=ocr_value,
            mapping_value=mapping_value,
            similarity_score=1.0 if success else 0.0,
            match_reason=f"Exact match: '{ocr_norm}' == '{mapping_norm}'" if success else "No exact match"
        )

    def contains_match(self, ocr_value: str, mapping_value: str) -> MatchResult:
        """Perform contains-based matching (one field contains the other)"""
        ocr_norm = str(ocr_value).strip()
        mapping_norm = str(mapping_value).strip()

        if not self.config.case_sensitive:
            ocr_norm = ocr_norm.lower()
            mapping_norm = mapping_norm.lower()

        # Check minimum length requirements
        if len(ocr_norm) < self.config.min_match_length or len(mapping_norm) < self.config.min_match_length:
            return MatchResult(
                success=False,
                strategy=MatchingStrategy.CONTAINS,
                ocr_value=ocr_value,
                mapping_value=mapping_value,
                match_reason=f"Values too short for contains matching (min_length={self.config.min_match_length})"
            )

        # Check if one contains the other
        ocr_contains_mapping = mapping_norm in ocr_norm
        mapping_contains_ocr = ocr_norm in mapping_norm

        if ocr_contains_mapping or mapping_contains_ocr:
            # Calculate similarity based on length ratio
            shorter_len = min(len(ocr_norm), len(mapping_norm))
            longer_len = max(len(ocr_norm), len(mapping_norm))
            similarity = shorter_len / longer_len if longer_len > 0 else 0.0

            direction = "OCR contains mapping" if ocr_contains_mapping else "Mapping contains OCR"

            return MatchResult(
                success=True,
                strategy=MatchingStrategy.CONTAINS,
                ocr_value=ocr_value,
                mapping_value=mapping_value,
                similarity_score=similarity,
                match_reason=f"Contains match: {direction} ('{ocr_norm}' vs '{mapping_norm}')"
            )

        return MatchResult(
            success=False,
            strategy=MatchingStrategy.CONTAINS,
            ocr_value=ocr_value,
            mapping_value=mapping_value,
            match_reason=f"No contains relationship: '{ocr_norm}' vs '{mapping_norm}'"
        )

    def split_match(self, ocr_value: str, mapping_value: str) -> MatchResult:
        """Perform split-based matching (extract parts and match)"""
        ocr_identifiers = self.extract_identifiers(ocr_value)
        mapping_identifiers = self.extract_identifiers(mapping_value)

        # Normalize for comparison if needed
        if not self.config.case_sensitive:
            ocr_identifiers = [id.lower() for id in ocr_identifiers]
            mapping_identifiers = [id.lower() for id in mapping_identifiers]

        # Find intersections
        ocr_set = set(ocr_identifiers)
        mapping_set = set(mapping_identifiers)
        common_identifiers = ocr_set.intersection(mapping_set)

        if common_identifiers:
            # Calculate similarity based on overlap
            total_unique = len(ocr_set.union(mapping_set))
            similarity = len(common_identifiers) / total_unique if total_unique > 0 else 0.0

            return MatchResult(
                success=True,
                strategy=MatchingStrategy.SPLIT,
                ocr_value=ocr_value,
                mapping_value=mapping_value,
                similarity_score=similarity,
                extracted_parts=list(common_identifiers),
                match_reason=f"Split match found common identifiers: {sorted(common_identifiers)}"
            )

        return MatchResult(
            success=False,
            strategy=MatchingStrategy.SPLIT,
            ocr_value=ocr_value,
            mapping_value=mapping_value,
            extracted_parts=[],
            match_reason=f"No common identifiers: OCR={ocr_identifiers} vs Mapping={mapping_identifiers}"
        )

    def fuzzy_match(self, ocr_value: str, mapping_value: str) -> MatchResult:
        """Perform fuzzy string matching using similarity ratio"""
        ocr_norm = str(ocr_value).strip()
        mapping_norm = str(mapping_value).strip()

        if not self.config.case_sensitive:
            ocr_norm = ocr_norm.lower()
            mapping_norm = mapping_norm.lower()

        # Calculate similarity using SequenceMatcher
        similarity = SequenceMatcher(None, ocr_norm, mapping_norm).ratio()

        success = similarity >= self.config.fuzzy_threshold

        return MatchResult(
            success=success,
            strategy=MatchingStrategy.FUZZY,
            ocr_value=ocr_value,
            mapping_value=mapping_value,
            similarity_score=similarity,
            match_reason=f"Fuzzy match: similarity={similarity:.3f} (threshold={self.config.fuzzy_threshold})"
        )

    def regex_match(self, ocr_value: str, mapping_value: str, pattern: str = None) -> MatchResult:
        """Perform regex-based matching"""
        if not pattern:
            return MatchResult(
                success=False,
                strategy=MatchingStrategy.REGEX,
                ocr_value=ocr_value,
                mapping_value=mapping_value,
                match_reason="No regex pattern provided"
            )

        try:
            # Try to match both values against the pattern
            ocr_match = re.search(pattern, str(ocr_value))
            mapping_match = re.search(pattern, str(mapping_value))

            if ocr_match and mapping_match:
                # Extract matched groups
                ocr_groups = ocr_match.groups() if ocr_match.groups() else [ocr_match.group()]
                mapping_groups = mapping_match.groups() if mapping_match.groups() else [mapping_match.group()]

                # Check if extracted groups match
                success = ocr_groups == mapping_groups
                similarity = 1.0 if success else 0.0

                return MatchResult(
                    success=success,
                    strategy=MatchingStrategy.REGEX,
                    ocr_value=ocr_value,
                    mapping_value=mapping_value,
                    similarity_score=similarity,
                    extracted_parts=list(ocr_groups) if success else [],
                    match_reason=f"Regex match: OCR groups={ocr_groups}, Mapping groups={mapping_groups}"
                )

            return MatchResult(
                success=False,
                strategy=MatchingStrategy.REGEX,
                ocr_value=ocr_value,
                mapping_value=mapping_value,
                match_reason=f"Regex pattern '{pattern}' did not match both values"
            )

        except re.error as e:
            return MatchResult(
                success=False,
                strategy=MatchingStrategy.REGEX,
                ocr_value=ocr_value,
                mapping_value=mapping_value,
                match_reason=f"Invalid regex pattern '{pattern}': {str(e)}"
            )

    def smart_match(self, ocr_value: str, mapping_value: str, field_name: str = None) -> MatchResult:
        """
        Intelligent matching that tries multiple strategies in priority order.
        Returns the best match found.
        """
        best_result = MatchResult(
            success=False,
            strategy=MatchingStrategy.SMART,
            ocr_value=ocr_value,
            mapping_value=mapping_value,
            match_reason="No successful strategy found"
        )

        # Try strategies in priority order
        for strategy in self.config.priority_order:
            if strategy not in self.config.strategies:
                continue  # Skip strategies not enabled in config

            result = None

            if strategy == MatchingStrategy.EXACT:
                result = self.exact_match(ocr_value, mapping_value)
            elif strategy == MatchingStrategy.CONTAINS:
                result = self.contains_match(ocr_value, mapping_value)
            elif strategy == MatchingStrategy.SPLIT:
                result = self.split_match(ocr_value, mapping_value)
            elif strategy == MatchingStrategy.FUZZY:
                result = self.fuzzy_match(ocr_value, mapping_value)
            elif strategy == MatchingStrategy.REGEX and field_name in self.config.regex_patterns:
                pattern = self.config.regex_patterns[field_name]
                result = self.regex_match(ocr_value, mapping_value, pattern)

            if result and result.success:
                # Found a successful match, update strategy to show which one worked
                result.strategy = MatchingStrategy.SMART
                result.match_reason = f"SMART strategy succeeded with {strategy.value}: {result.match_reason}"
                return result
            elif result and result.similarity_score > best_result.similarity_score:
                # Keep track of the best unsuccessful match
                best_result = result
                best_result.strategy = MatchingStrategy.SMART
                best_result.match_reason = f"SMART strategy best attempt with {strategy.value}: {result.match_reason}"

        return best_result

    def match(self, ocr_value: str, mapping_value: str, strategy: MatchingStrategy = None, field_name: str = None) -> MatchResult:
        """
        Perform matching using the specified strategy or the default configured strategy.

        Args:
            ocr_value: Value from OCR data
            mapping_value: Value from mapping file
            strategy: Specific strategy to use (if None, uses first strategy in config)
            field_name: Field name for regex pattern lookup

        Returns:
            MatchResult with success status and details
        """
        if strategy is None:
            strategy = self.config.strategies[0] if self.config.strategies else MatchingStrategy.EXACT

        self.logger.debug(f"Matching '{ocr_value}' vs '{mapping_value}' using {strategy.value}")

        if strategy == MatchingStrategy.EXACT:
            return self.exact_match(ocr_value, mapping_value)
        elif strategy == MatchingStrategy.CONTAINS:
            return self.contains_match(ocr_value, mapping_value)
        elif strategy == MatchingStrategy.SPLIT:
            return self.split_match(ocr_value, mapping_value)
        elif strategy == MatchingStrategy.FUZZY:
            return self.fuzzy_match(ocr_value, mapping_value)
        elif strategy == MatchingStrategy.REGEX:
            pattern = self.config.regex_patterns.get(field_name, "")
            return self.regex_match(ocr_value, mapping_value, pattern)
        elif strategy == MatchingStrategy.SMART:
            return self.smart_match(ocr_value, mapping_value, field_name)
        else:
            return MatchResult(
                success=False,
                strategy=strategy,
                ocr_value=ocr_value,
                mapping_value=mapping_value,
                match_reason=f"Unknown strategy: {strategy}"
            )


class OrderProcessor:
    """Main coordinator for OCR Order processing"""

    def __init__(self):
        self.s3_manager = get_s3_manager()
        self.prompt_schema_manager = get_prompt_schema_manager()
        self.app_config = config_loader.get_app_config()
        self.special_csv_generator = SpecialCsvGenerator()
        self.onedrive_client: Optional['OneDriveClient'] = None
        self._master_csv_cache: Dict[str, pd.DataFrame] = {}

        # Initialize intelligent matching engine with default configuration
        default_config = MatchingConfig(
            strategies=[MatchingStrategy.EXACT, MatchingStrategy.SPLIT, MatchingStrategy.CONTAINS, MatchingStrategy.FUZZY],
            priority_order=[MatchingStrategy.EXACT, MatchingStrategy.SPLIT, MatchingStrategy.CONTAINS, MatchingStrategy.FUZZY],
            fuzzy_threshold=0.8,
            min_match_length=3,
            case_sensitive=False
        )
        self.matching_engine = MatchingEngine(default_config)

    # ------------------------------------------------------------------
    # Mapping helpers
    # ------------------------------------------------------------------

    def _ensure_onedrive_client(self) -> 'OneDriveClient':
        if self.onedrive_client:
            return self.onedrive_client

        onedrive_cfg = (self.app_config or {}).get("onedrive", {}) if isinstance(self.app_config, dict) else {}

        client_id = os.getenv("ONEDRIVE_CLIENT_ID") or onedrive_cfg.get("client_id")
        client_secret = os.getenv("ONEDRIVE_CLIENT_SECRET") or onedrive_cfg.get("client_secret")
        tenant_id = os.getenv("ONEDRIVE_TENANT_ID") or onedrive_cfg.get("tenant_id")
        target_user = os.getenv("ONEDRIVE_TARGET_USER_UPN") or onedrive_cfg.get("target_user_upn")

        if not (client_id and client_secret and tenant_id):
            raise RuntimeError("OneDrive credentials are not fully configured")

        try:
            from utils.onedrive_client import OneDriveClient  # local import; may raise if O365 missing
        except Exception as exc:
            raise RuntimeError("OneDrive client dependencies are not installed. Please install 'O365' and related packages.") from exc

        client = OneDriveClient(
            client_id=client_id,
            client_secret=client_secret,
            tenant_id=tenant_id,
            target_user_upn=target_user,
        )

        if not client.connect():
            raise RuntimeError("Failed to connect to OneDrive with provided credentials")

        self.onedrive_client = client
        return client

    def _apply_output_metadata(self, df: pd.DataFrame, context: Dict[str, Any], mapping_spec: Optional[Dict[str, Any]] = None) -> None:
        """Augment output DataFrame with metadata columns per configuration.

        Configure via mapping_config.output_meta (preferred) or env var MAPPING_OUTPUT_META_MAP, e.g.:
        - "order=ctx:order_id,item=col:__item_id,company=ctx:company_name"

        Each pair is dest=src where src is one of:
        - ctx:<key>   -> value from provided context dict (broadcast to all rows)
        - col:<name>  -> copy from existing DataFrame column if present
        Existing columns are not overwritten. If spec is missing or invalid, no-op.
        """
        try:
            # Prefer mapping_spec (from mapping_config.output_meta)
            spec_map: Dict[str, str] = {}
            if isinstance(mapping_spec, dict) and mapping_spec:
                spec_map = {str(k): str(v) for k, v in mapping_spec.items()}
            else:
                spec = os.getenv("MAPPING_OUTPUT_META_MAP", "").strip()
                if spec:
                    pairs = [p.strip() for p in spec.split(',') if p.strip()]
                    for token in pairs:
                        if '=' not in token:
                            continue
                        dest, src = token.split('=', 1)
                        spec_map[dest.strip()] = src.strip()

            if not spec_map:
                return

            for dest, src in spec_map.items():
                if not dest or dest in df.columns or not isinstance(src, str):
                    continue
                if src.startswith('ctx:'):
                    key = src[4:]
                    if key in context:
                        df[dest] = context[key]
                elif src.startswith('col:'):
                    col = src[4:]
                    if col in df.columns:
                        df[dest] = df[col]
        except Exception as e:
            logger.warning(f"Failed to apply output metadata mapping: {e}")

    def _get_master_csv_dataframe(self, path: str) -> pd.DataFrame:
        cached = self._master_csv_cache.get(path)
        if cached is not None:
            return cached.copy()

        client = self._ensure_onedrive_client()
        content = client.download_file_content(path)
        if not content:
            raise RuntimeError(f"Master CSV not found at OneDrive path: {path}")

        extension = os.path.splitext(path)[1].lower()
        try:
            if extension in {".xlsx", ".xls"}:
                df = pd.read_excel(BytesIO(content))
            else:
                df = pd.read_csv(BytesIO(content))
        except Exception as exc:
            raise RuntimeError(f"Failed to parse master CSV '{path}': {exc}") from exc

        df.columns = [col.strip() if isinstance(col, str) else col for col in df.columns]
        self._master_csv_cache[path] = df
        return df.copy()

    def _download_content_from_uri(self, uri: str) -> Optional[bytes]:
        if not uri:
            return None

        if uri.startswith("s3://"):
            key = uri.replace(f"s3://{self.s3_manager.bucket_name}/", "")
            if key.startswith(self.s3_manager.upload_prefix):
                key = key[len(self.s3_manager.upload_prefix):]
            return self.s3_manager.download_file(key)

        if os.path.exists(uri):
            with open(uri, "rb") as file_obj:
                return file_obj.read()

        # Fallback to file storage helper (handles s3:// formatted paths stored elsewhere)
        return self.s3_manager.download_file_by_stored_path(uri)

    def _load_item_records(self, item: OcrOrderItem) -> List[Dict[str, Any]]:
        if not item.ocr_result_json_path:
            raise RuntimeError("OCR result JSON path missing for item")

        content = self._download_content_from_uri(item.ocr_result_json_path)
        if not content:
            raise RuntimeError(f"Unable to load OCR result JSON for item {item.item_id}")

        try:
            loaded = json.loads(content.decode("utf-8"))
            # Normalise to a list of dicts so downstream code can iterate rows safely
            if isinstance(loaded, dict):
                records = [loaded]
            elif isinstance(loaded, list):
                records = loaded
            else:
                raise ValueError("Unexpected OCR JSON structure; must be object or array")

            # Defensive: keep only dict rows
            dict_rows: List[Dict[str, Any]] = [r for r in records if isinstance(r, dict)]
            if not dict_rows:
                raise ValueError("No valid row objects in OCR JSON")
            return dict_rows
        except Exception as exc:
            raise RuntimeError(f"Invalid OCR result JSON for item {item.item_id}: {exc}") from exc

    @staticmethod
    def _strip_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in record.items() if not k.startswith("__")}

    @staticmethod
    def _sanitise_prefix(value: Optional[str], fallback: str) -> str:
        if value:
            prefix = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
            if prefix:
                return prefix
        return fallback

    def _build_single_source_dataframe(
        self,
        item: OcrOrderItem,
        records: List[Dict[str, Any]],
    ) -> pd.DataFrame:
        """Build primary dataframe for single-source mapping.

        Notes:
        - Normalises OCR JSON by deep-flattening nested objects/arrays so that
          external join keys like 'service_number' are available as columns.
        - Strips internal metadata keys (prefix '__') before flattening.
        """
        primary_rows = [self._strip_metadata(row) for row in records if isinstance(row, dict) and row.get("__is_primary")]

        if not primary_rows:
            primary_rows = [self._strip_metadata(row) for row in records if isinstance(row, dict)]

        if not primary_rows:
            raise RuntimeError("No OCR data available for mapping")

        # Deep-flatten each row to expose nested fields as columns
        try:
            from utils.excel_converter import deep_flatten_json_universal
            flattened: List[Dict[str, Any]] = []
            for row in primary_rows:
                # deep_flatten_json_universal returns a list of row dicts
                flat_rows = deep_flatten_json_universal(row)
                for fr in flat_rows:
                    if isinstance(fr, dict):
                        # Ensure internal meta keys are not present post-flatten
                        cleaned = {k: v for k, v in fr.items() if not k.startswith("__")}
                        flattened.append(cleaned)

            if not flattened:
                # Fallback to non-flattened rows if flattening produced nothing
                flattened = primary_rows

            df = pd.DataFrame(flattened)
        except Exception:
            # On any flattening error, fall back to original behaviour
            df = pd.DataFrame(primary_rows)

        # Do not hardcode metadata columns; caller may choose to augment via mapping
        return df

    def _build_multi_source_dataframe(
        self,
        item: OcrOrderItem,
        records: List[Dict[str, Any]],
        default_internal_join_key: Optional[str],
    ) -> pd.DataFrame:
        """Merge primary + attachment records, supporting per-attachment join keys.

        - If 'default_internal_join_key' is provided, use it when a record doesn't match
          any attachment source override.
        - If mapping_config.attachment_sources contains 'join_key' and an optional
          'filename_contains', attachments are partitioned by join key and merged sequentially.
        - Always left-join to keep primary rows even if no attachments match.
        """
        primary_rows = [self._strip_metadata(row) for row in records if isinstance(row, dict) and row.get("__is_primary")]
        if not primary_rows:
            raise RuntimeError("Multi-source mapping requires at least one primary record")

        # Deep-flatten primary to expose nested fields for join keys
        try:
            from utils.excel_converter import deep_flatten_json_universal
            flattened: List[Dict[str, Any]] = []
            for row in primary_rows:
                flat_rows = deep_flatten_json_universal(row)
                for fr in flat_rows:
                    if isinstance(fr, dict):
                        cleaned = {k: v for k, v in fr.items() if not k.startswith("__")}
                        flattened.append(cleaned)
            if not flattened:
                flattened = primary_rows
            primary_df = pd.DataFrame(flattened)
        except Exception:
            primary_df = pd.DataFrame(primary_rows)

        # Build matcher rules from mapping_config
        cfg = item.mapping_config or {}
        srcs = cfg.get("attachment_sources", []) if isinstance(cfg, dict) else []
        # Normalise to a list of dicts with keys: join_key, filename_contains
        rules: List[Dict[str, Optional[str]]] = []
        for src in srcs:
            if not isinstance(src, dict):
                continue
            rules.append(
                {
                    "join_key": src.get("join_key"),
                    "filename_contains": (src.get("filename_contains") or "") or None,
                }
            )

        # Partition attachment records by applicable join key
        attachment_rows = [row for row in records if not row.get("__is_primary")]
        grouped: Dict[str, List[Dict[str, Any]]] = {}

        mapping_debug = os.getenv("MAPPING_DEBUG", "false").lower() in ("1", "true", "yes")

        def _pick_join_key(filename: Optional[str]) -> Optional[str]:
            fname = (filename or "").lower()
            for rule in rules:
                pat = (rule.get("filename_contains") or "").lower()
                if rule.get("join_key") and pat and pat in fname:
                    return rule["join_key"]
            # If no filename rule matched, fall back to any per-source rule without filename pattern
            for rule in rules:
                if rule.get("join_key") and not rule.get("filename_contains"):
                    return rule["join_key"]
            return default_internal_join_key

        for record in attachment_rows:
            clean_record = self._strip_metadata(record)
            join_key = _pick_join_key(record.get("__filename"))
            if not join_key:
                if mapping_debug:
                    logger.warning(
                        "[MAPPING_DEBUG] Item %s attachment '%s': no join_key resolved (rules=%s, default=%s)",
                        item.item_id,
                        record.get("__filename"),
                        rules,
                        default_internal_join_key,
                    )
                continue  # Nothing to join on; skip this attachment safely
            if join_key not in primary_df.columns:
                if mapping_debug:
                    logger.warning(
                        "[MAPPING_DEBUG] Item %s missing internal join key '%s' in primary columns: %s",
                        item.item_id,
                        join_key,
                        list(primary_df.columns),
                    )
                raise RuntimeError(f"Primary data missing internal join key '{join_key}'")

            grouped.setdefault(join_key, []).append(record)

        # Sequentially merge each group of attachments using its own join key
        merged_df = primary_df
        for join_key, recs in grouped.items():
            aggregated: Dict[Any, Dict[str, Any]] = {}
            prefix_counters: Dict[str, int] = {}
            for index, record in enumerate(recs):
                # Deep‑flatten each attachment record so nested fields are available for joining
                try:
                    from utils.excel_converter import deep_flatten_json_universal
                    flat_rows = deep_flatten_json_universal(self._strip_metadata(record))
                    # Ensure at least one row exists
                    if not flat_rows:
                        flat_rows = [self._strip_metadata(record)]
                except Exception:
                    flat_rows = [self._strip_metadata(record)]

                for sub_idx, clean_record in enumerate(flat_rows):
                    if not isinstance(clean_record, dict):
                        continue

                    # Obtain join value; fallback to keys whose last segment matches join_key
                    join_value = clean_record.get(join_key)
                    if join_value is None:
                        alt_key = next((k for k in clean_record.keys() if isinstance(k, str) and k.split(".")[-1] == join_key), None)
                        if alt_key is not None:
                            join_value = clean_record.get(alt_key)
                    if join_value is None:
                        continue

                    prefix_base = self._sanitise_prefix(record.get("__filename"), f"attachment_{index + 1}")
                    prefix_count = prefix_counters.get(prefix_base, 0)
                    prefix_counters[prefix_base] = prefix_count + 1
                    prefix = prefix_base if prefix_count == 0 else f"{prefix_base}_{prefix_count + 1}"

                    entry = aggregated.setdefault(join_value, {})
                    for key, value in clean_record.items():
                        # Skip the exact join_key column and the alt dotted key variant
                        if key == join_key or (isinstance(key, str) and key.split(".")[-1] == join_key):
                            continue
                        column_name = f"{prefix}__{key}"
                        if column_name not in entry:
                            entry[column_name] = value

            if aggregated:
                rows = []
                for join_value, data in aggregated.items():
                    row = {join_key: join_value}
                    row.update(data)
                    rows.append(row)
                attachments_df = pd.DataFrame(rows)
                merged_df = merged_df.merge(attachments_df, on=join_key, how="left")

        # Do not hardcode metadata columns; caller may choose to augment via mapping
        return merged_df

    def _join_with_master_csv(
        self,
        item_df: pd.DataFrame,
        master_df: pd.DataFrame,
        external_join_keys: List[str],
        column_aliases: Optional[Dict[str, str]] = None,
        join_normalize: Optional[Dict[str, Any]] = None,
    ) -> pd.DataFrame:
        if not external_join_keys:
            return item_df

        column_aliases = column_aliases or {}

        left_on: List[str] = []
        right_on: List[str] = []
        for key in external_join_keys:
            left_on.append(key)
            right_on.append(column_aliases.get(key, key))

        missing_left = [key for key in left_on if key not in item_df.columns]
        if missing_left:
            raise RuntimeError(f"Item data missing required join columns: {missing_left}")

        missing_right = [key for key in right_on if key not in master_df.columns]
        if missing_right:
            raise RuntimeError(f"Master CSV missing required join columns: {missing_right}")

        # Coerce join columns to strings on both sides to avoid dtype mismatch
        def _normalize_text(s: str, opts: Optional[Dict[str, Any]], key_name: Optional[str] = None) -> str:
            if opts is None:
                return s
            out = s
            try:
                if isinstance(out, str):
                    if opts.get('strip_non_digits'):
                        import re
                        out = re.sub(r"\D+", "", out)
                    # zfill: int or per-key map
                    zfill = opts.get('zfill')
                    if isinstance(zfill, int) and zfill > 0:
                        out = out.zfill(zfill)
                    elif isinstance(zfill, dict) and key_name and key_name in zfill:
                        length = int(zfill[key_name])
                        if length > 0:
                            out = out.zfill(length)
            except Exception:
                return s
            return out

        def _as_str_series(series: pd.Series, key_name: Optional[str]) -> pd.Series:
            try:
                s = series.astype(str).replace({"nan": "", "None": ""}).str.strip()
                if join_normalize:
                    return s.apply(lambda v: _normalize_text(v, join_normalize, key_name))
                return s
            except Exception:
                s = series.astype("string").fillna("").str.strip()
                if join_normalize:
                    return s.apply(lambda v: _normalize_text(v, join_normalize, key_name))
                return s

        left_tmp_cols: List[str] = []
        right_tmp_cols: List[str] = []
        for i, (lcol, rcol, key_name) in enumerate(zip(left_on, right_on, external_join_keys)):
            ltmp = f"__join_left_{i}__"
            rtmp = f"__join_right_{i}__"
            item_df[ltmp] = _as_str_series(item_df[lcol], key_name)
            master_df[rtmp] = _as_str_series(master_df[rcol], key_name)
            left_tmp_cols.append(ltmp)
            right_tmp_cols.append(rtmp)

        merged_df = item_df.merge(
            master_df,
            left_on=left_tmp_cols,
            right_on=right_tmp_cols,
            how="left",
            suffixes=("", (item.mapping_config.get("merge_suffix") if isinstance(getattr(item, 'mapping_config', None), dict) and item.mapping_config.get("merge_suffix") else "_master")),
        )

        # Drop temp join columns
        merged_df = merged_df.drop(columns=left_tmp_cols + right_tmp_cols, errors="ignore")

        return merged_df

    def _persist_item_mapping_result(
        self,
        order_id: int,
        item: OcrOrderItem,
        mapped_df: pd.DataFrame,
    ) -> str:
        s3_base = f"results/orders/{order_id // 1000}/items/{item.item_id}"
        csv_key = f"{s3_base}/item_{item.item_id}_mapped_final.csv"

        csv_bytes = mapped_df.to_csv(index=False).encode("utf-8")
        upload_success = self.s3_manager.upload_file(csv_bytes, csv_key)
        if not upload_success:
            raise RuntimeError("Failed to upload mapped CSV to storage")

        return f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{csv_key}"

    async def process_order(self, order_id: int):
        """Process an entire OCR order"""
        with Session(engine) as db:
            try:
                # Get order
                order = db.query(OcrOrder).filter(OcrOrder.order_id == order_id).first()
                if not order:
                    logger.error(f"Order {order_id} not found")
                    return

                if order.status != OrderStatus.PROCESSING:
                    logger.warning(f"Order {order_id} is not in PROCESSING status")
                    return

                # Get order items
                items = db.query(OcrOrderItem).filter(
                    OcrOrderItem.order_id == order_id,
                    OcrOrderItem.status == OrderItemStatus.PENDING
                ).all()

                if not items:
                    logger.warning(f"No pending items found for order {order_id}")
                    order.status = OrderStatus.FAILED
                    order.error_message = "No items to process"
                    db.commit()
                    return

                logger.info(f"Processing order {order_id} with {len(items)} items")

                # Process all items in parallel
                tasks = []
                for item in items:
                    task = asyncio.create_task(self._process_order_item(item.item_id))
                    tasks.append(task)

                # Wait for all items to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Check results and update order status
                completed_count = 0
                failed_count = 0

                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Item processing failed: {result}")
                        failed_count += 1
                    elif result:
                        completed_count += 1
                    else:
                        failed_count += 1

                # Update order counts
                order.completed_items = completed_count
                order.failed_items = failed_count

                if failed_count == len(items):
                    # All items failed
                    order.status = OrderStatus.FAILED
                    order.error_message = "All items failed to process"
                elif completed_count > 0:
                    # At least some items succeeded - proceed to consolidation
                    order.status = OrderStatus.MAPPING
                    logger.info(f"Order {order_id} moving to consolidation phase")

                    # Trigger consolidation
                    asyncio.create_task(self._consolidate_order_results(order_id))

                db.commit()
                logger.info(f"Order {order_id} processing completed: {completed_count} succeeded, {failed_count} failed")

            except Exception as e:
                logger.error(f"Error processing order {order_id}: {str(e)}")
                order.status = OrderStatus.FAILED
                order.error_message = str(e)
                db.commit()

    async def process_order_ocr_only(self, order_id: int):
        """Process an OCR order without mapping (OCR-only mode)"""
        with Session(engine) as db:
            try:
                # Get order
                order = db.query(OcrOrder).filter(OcrOrder.order_id == order_id).first()
                if not order:
                    logger.error(f"Order {order_id} not found")
                    return

                # Check if order is locked
                if order.status == OrderStatus.LOCKED:
                    logger.error(f"Order {order_id} is locked and cannot be processed for OCR")
                    return

                if order.status != OrderStatus.PROCESSING:
                    logger.warning(f"Order {order_id} is not in PROCESSING status")
                    return

                # Get order items
                items = db.query(OcrOrderItem).filter(
                    OcrOrderItem.order_id == order_id,
                    OcrOrderItem.status == OrderItemStatus.PENDING
                ).all()

                if not items:
                    logger.warning(f"No pending items found for order {order_id}")
                    order.status = OrderStatus.FAILED
                    order.error_message = "No items to process"
                    db.commit()
                    return

                logger.info(f"Processing order {order_id} (OCR-only) with {len(items)} items")

                # Process all items in parallel
                tasks = []
                for item in items:
                    task = asyncio.create_task(self._process_order_item(item.item_id))
                    tasks.append(task)

                # Wait for all items to complete
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Check results and update order status
                completed_count = 0
                failed_count = 0

                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Item processing failed: {result}")
                        failed_count += 1
                    elif result:
                        completed_count += 1
                    else:
                        failed_count += 1

                # Update order counts
                order.completed_items = completed_count
                order.failed_items = failed_count

                if failed_count == len(items):
                    # All items failed
                    order.status = OrderStatus.FAILED
                    order.error_message = "All items failed to process"
                elif completed_count > 0:
                    # At least some items succeeded - mark as OCR completed
                    order.status = OrderStatus.OCR_COMPLETED
                    logger.info(f"Order {order_id} OCR processing completed - ready for mapping configuration")

                db.commit()
                logger.info(f"Order {order_id} OCR-only processing completed: {completed_count} succeeded, {failed_count} failed")

            except Exception as e:
                logger.error(f"Error processing order OCR-only {order_id}: {str(e)}")
                order.status = OrderStatus.FAILED
                order.error_message = str(e)
                db.commit()

    def _get_ordered_file_links(self, item: OcrOrderItem) -> Tuple[Optional[Dict], List[Dict]]:
        """Get file links ordered with primary file first.

        Returns:
            Tuple of (primary_file_data, attachment_files_data)
        """
        from sqlalchemy.orm import Session
        with Session(engine) as db:
            file_links = db.query(OrderItemFile).filter(OrderItemFile.item_id == item.item_id).all()

            primary_file_data = None
            attachment_files = []

            for link in file_links:
                file_record = link.file
                file_data = {
                    'file_record': file_record,
                    'file_link': link,
                    'is_primary': item.primary_file_id and file_record.file_id == item.primary_file_id
                }

                if file_data['is_primary']:
                    primary_file_data = file_data
                else:
                    attachment_files.append(file_data)

            return primary_file_data, attachment_files

    async def _generate_item_csv_quick(self, item_id: int,
                                       primary_result: Optional[Dict],
                                       attachment_results: List[Dict]) -> Optional[str]:
        """Generate a quick CSV snapshot per item (OCR-only stage), without default_mapping_keys.

        - If primary row exists, include it as the first row.
        - Each attachment will be appended as its own row.
        - All internal fields starting with '__' are stripped.
        This CSV is only a convenience artifact before full mapping joins are run later.
        """
        try:
            from sqlalchemy.orm import Session
            with Session(engine) as db:
                item = db.query(OcrOrderItem).filter(OcrOrderItem.item_id == item_id).first()
                if not item:
                    logger.error(f"Item {item_id} not found for CSV generation")
                    return None

                # Prepare data for CSV
                csv_rows = []

                # Add primary file result as base row
                primary_row = {}
                if primary_result:
                    primary_row = {k: v for k, v in primary_result.items() if not k.startswith('__')}
                    csv_rows.append(primary_row)

                # Append each attachment as its own row
                for attach_result in attachment_results:
                    row = {k: v for k, v in attach_result.items() if not k.startswith('__')}
                    csv_rows.append(row)

                if not csv_rows:
                    logger.warning(f"No data for CSV generation for item {item_id}")
                    return None

                # Generate CSV
                s3_base = f"results/orders/{item_id // 1000}/items/{item_id}"
                with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as temp_csv:
                    temp_csv_path = temp_csv.name

                try:
                    # Convert to DataFrame and save
                    df = pd.DataFrame(csv_rows)
                    df.to_csv(temp_csv_path, index=False, encoding='utf-8')

                    # Upload to S3
                    with open(temp_csv_path, 'rb') as csv_file:
                        csv_content = csv_file.read()
                        csv_s3_key = f"{s3_base}/item_{item_id}_mapped.csv"
                        csv_upload_success = self.s3_manager.upload_file(csv_content, csv_s3_key)

                        if csv_upload_success:
                            csv_path = f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{csv_s3_key}"
                            logger.info(f"Generated mapped CSV for item {item_id}: {csv_s3_key}")
                            return csv_path
                        else:
                            logger.error(f"Failed to upload mapped CSV for item {item_id}")
                            return None
                finally:
                    try:
                        os.unlink(temp_csv_path)
                    except:
                        pass

        except Exception as e:
            logger.error(f"Error generating mapped CSV for item {item_id}: {str(e)}")
            return None

    async def _process_order_item(self, item_id: int) -> bool:
        """Process a single order item"""
        with Session(engine) as db:
            try:
                # Get item with relationships
                item = db.query(OcrOrderItem).filter(OcrOrderItem.item_id == item_id).first()
                if not item:
                    logger.error(f"Order item {item_id} not found")
                    return False

                # Update item status
                item.status = OrderItemStatus.PROCESSING
                item.processing_started_at = datetime.utcnow()
                db.commit()

                # Get company and document type codes
                company = db.query(Company).filter(Company.company_id == item.company_id).first()
                doc_type = db.query(DocumentType).filter(DocumentType.doc_type_id == item.doc_type_id).first()

                if not company or not doc_type:
                    raise Exception("Company or document type not found")

                # Load prompt and schema for this company/doc type. These are required for OCR.
                prompt = await self.prompt_schema_manager.get_prompt(company.company_code, doc_type.type_code)
                schema = await self.prompt_schema_manager.get_schema(company.company_code, doc_type.type_code)

                # Provide a clearer error so the UI can surface an actionable message
                if not prompt or not schema:
                    raise Exception(
                        f"Prompt or schema not found for {company.company_code}/{doc_type.type_code}. "
                        f"Please create and activate a configuration in Admin > Configs."
                    )

                # Get files for this item (use helper to prioritize primary file)
                primary_file_data, attachment_files = self._get_ordered_file_links(item)
                all_files = []
                if primary_file_data:
                    # `primary_file_data` is a dict with keys: file_record, file_link, is_primary
                    # Use the DB file record, not a non-existent 'file' key
                    all_files.append((primary_file_data['file_record'], True))  # Mark as primary
                for attachment_data in attachment_files:
                    all_files.append((attachment_data['file_record'], False))  # Mark as attachment

                if not all_files:
                    raise Exception("No files found for item")

                # Process all files for this item
                all_results = []
                temp_files_to_cleanup = []
                is_awb = doc_type.type_code == "AIRWAY_BILL"  # Check if this is an AWB item

                for file_record, is_primary_file in all_files:
                    try:
                        # Download file from S3 to temporary location
                        file_content = self.s3_manager.download_file_by_stored_path(file_record.file_path)
                        if not file_content:
                            logger.error(f"Failed to download file: {file_record.file_path}")
                            continue

                        # Create temporary file
                        file_ext = os.path.splitext(file_record.file_name)[1].lower()
                        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
                            temp_file.write(file_content)
                            temp_file_path = temp_file.name
                            temp_files_to_cleanup.append(temp_file_path)

                        # Process the file
                        if file_ext == '.pdf':
                            result = await extract_text_from_pdf(temp_file_path, prompt, schema)
                        else:
                            result = await extract_text_from_image(temp_file_path, prompt, schema)

                        # Clean result data - only keep business data
                        if isinstance(result, dict):
                            text_content = result.get("text", "")
                            if text_content:
                                try:
                                    business_data = json.loads(text_content)
                                    business_data["__filename"] = file_record.file_name
                                    business_data["__is_primary"] = is_primary_file  # Mark if primary file
                                    # Add file-level metadata for AWB items
                                    if is_awb:
                                        business_data["__file_id"] = file_record.file_id
                                        business_data["__source_path"] = file_record.file_path
                                    all_results.append(business_data)
                                except json.JSONDecodeError:
                                    error_result = {
                                        "text": text_content,
                                        "__filename": file_record.file_name,
                                        "__is_primary": is_primary_file
                                    }
                                    if is_awb:
                                        error_result["__file_id"] = file_record.file_id
                                        error_result["__source_path"] = file_record.file_path
                                    all_results.append(error_result)
                            else:
                                no_content_result = {
                                    "__filename": file_record.file_name,
                                    "__error": "No text content in result",
                                    "__is_primary": is_primary_file
                                }
                                if is_awb:
                                    no_content_result["__file_id"] = file_record.file_id
                                    no_content_result["__source_path"] = file_record.file_path
                                all_results.append(no_content_result)

                    except Exception as e:
                        logger.error(f"Error processing file {file_record.file_name}: {str(e)}")
                        error_result = {
                            "__filename": file_record.file_name,
                            "__error": f"Processing failed: {str(e)}",
                            "__is_primary": is_primary_file
                        }
                        if is_awb:
                            error_result["__file_id"] = file_record.file_id
                            error_result["__source_path"] = file_record.file_path
                        all_results.append(error_result)

                # Clean up temporary files
                for temp_file in temp_files_to_cleanup:
                    try:
                        os.unlink(temp_file)
                    except:
                        pass

                if not all_results:
                    raise Exception("No results generated")

                # Save item results to S3
                await self._save_item_results(item_id, company.company_code, doc_type.type_code, all_results)

                # Update item status
                item.status = OrderItemStatus.COMPLETED
                item.processing_completed_at = datetime.utcnow()

                if item.processing_started_at:
                    processing_time = (item.processing_completed_at - item.processing_started_at).total_seconds()
                    item.processing_time_seconds = processing_time

                db.commit()
                logger.info(f"Order item {item_id} processed successfully with {len(all_results)} results")
                return True

            except Exception as e:
                logger.error(f"Error processing order item {item_id}: {str(e)}")
                item.status = OrderItemStatus.FAILED
                item.error_message = str(e)
                item.processing_completed_at = datetime.utcnow()

                if item.processing_started_at:
                    processing_time = (item.processing_completed_at - item.processing_started_at).total_seconds()
                    item.processing_time_seconds = processing_time

                db.commit()
                return False

    async def _save_file_result(self, item_id: int, file_id: int, file_name: str, result_data: Dict[str, Any]) -> Optional[str]:
        """Save individual file-level OCR result to S3 (for AWB items only)

        Args:
            item_id: Item ID
            file_id: File ID
            file_name: File name
            result_data: OCR result data for this file

        Returns:
            S3 path to the saved file result, or None if failed
        """
        try:
            # Generate S3 path for file-level result
            s3_base = f"results/orders/{item_id // 1000}/items/{item_id}"
            file_result_key = f"{s3_base}/files/file_{file_id}_result.json"

            # Save file-level JSON result
            json_content = json.dumps(result_data, indent=2, ensure_ascii=False)
            json_upload_success = self.s3_manager.upload_file(json_content.encode('utf-8'), file_result_key)

            if json_upload_success:
                file_result_path = f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{file_result_key}"
                logger.info(f"✅ Saved file-level result for item {item_id}, file {file_id}: {file_result_key}")
                return file_result_path
            else:
                logger.error(f"Failed to upload file-level result for item {item_id}, file {file_id}")
                return None

        except Exception as e:
            logger.error(f"Error saving file-level result for item {item_id}, file {file_id}: {str(e)}")
            return None

    async def _generate_file_results_manifest(self, item_id: int, file_results_map: Dict[int, str]) -> Optional[str]:
        """Generate manifest of file-level results for AWB items

        Args:
            item_id: Item ID
            file_results_map: Dict mapping file_id to result_json_path

        Returns:
            S3 path to the manifest file, or None if failed
        """
        try:
            # Build manifest structure
            manifest = [
                {
                    "file_id": file_id,
                    "result_json_path": result_path
                }
                for file_id, result_path in file_results_map.items()
            ]

            # Generate S3 path for manifest
            s3_base = f"results/orders/{item_id // 1000}/items/{item_id}"
            manifest_key = f"{s3_base}/item_{item_id}_file_results.json"

            # Save manifest
            json_content = json.dumps(manifest, indent=2, ensure_ascii=False)
            manifest_upload_success = self.s3_manager.upload_file(json_content.encode('utf-8'), manifest_key)

            if manifest_upload_success:
                manifest_path = f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{manifest_key}"
                logger.info(f"✅ Generated file results manifest for item {item_id} with {len(manifest)} files")
                return manifest_path
            else:
                logger.error(f"Failed to upload manifest for item {item_id}")
                return None

        except Exception as e:
            logger.error(f"Error generating file results manifest for item {item_id}: {str(e)}")
            return None

    async def _save_item_results(self, item_id: int, company_code: str, doc_type_code: str, results: List[Dict[str, Any]]):
        """Save individual item results to S3, with file-level results for AWB items and CSV mapping"""
        try:
            # Generate S3 paths for item results
            s3_base = f"results/orders/{item_id // 1000}/items/{item_id}"
            is_awb = doc_type_code == "AIRWAY_BILL"

            # Separate primary file result from attachments
            primary_result = None
            attachment_results = []
            for result in results:
                if result.get("__is_primary", False):
                    primary_result = result
                else:
                    attachment_results.append(result)

            # For AWB items, save file-level results
            file_results_map = {}
            if is_awb:
                for result in results:
                    if "__file_id" in result:
                        file_id = result["__file_id"]
                        file_name = result.get("__filename", "unknown")
                        # Save file-level result
                        file_result_path = await self._save_file_result(item_id, file_id, file_name, result)
                        if file_result_path:
                            file_results_map[file_id] = file_result_path

                # Generate manifest for file results
                if file_results_map:
                    await self._generate_file_results_manifest(item_id, file_results_map)

            # Save JSON results (save primary file result separately if available)
            json_path = None
            if primary_result:
                # Save primary file result
                json_content = json.dumps(primary_result, indent=2, ensure_ascii=False)
                json_s3_key = f"{s3_base}/item_{item_id}_primary.json"
                json_upload_success = self.s3_manager.upload_file(json_content.encode('utf-8'), json_s3_key)

                if json_upload_success:
                    json_path = f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{json_s3_key}"
            else:
                # No primary file, save aggregated results for backward compatibility
                json_content = json.dumps(attachment_results if attachment_results else results, indent=2, ensure_ascii=False)
                json_s3_key = f"{s3_base}/item_{item_id}_results.json"
                json_upload_success = self.s3_manager.upload_file(json_content.encode('utf-8'), json_s3_key)

                if json_upload_success:
                    json_path = f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{json_s3_key}"

            # Generate CSV results using new mapping function
            csv_path = await self._generate_item_csv_quick(item_id, primary_result, attachment_results)

            # Update item with result paths
            with Session(engine) as db:
                item = db.query(OcrOrderItem).filter(OcrOrderItem.item_id == item_id).first()
                if item:
                    item.ocr_result_json_path = json_path
                    item.ocr_result_csv_path = csv_path
                    db.commit()

            logger.info(f"Item {item_id} results saved to S3" + (f" with {len(file_results_map)} file-level results" if is_awb and file_results_map else ""))

        except Exception as e:
            logger.error(f"Error saving item {item_id} results: {str(e)}")
            raise

    async def _consolidate_order_results(self, order_id: int):
        """Consolidate results from all order items and generate final reports"""
        with Session(engine) as db:
            try:
                logger.info(f"Starting consolidation for order {order_id}")

                order = db.query(OcrOrder).filter(OcrOrder.order_id == order_id).first()
                if not order:
                    logger.error(f"Order {order_id} not found")
                    return

                # Get completed items
                completed_items = db.query(OcrOrderItem).filter(
                    OcrOrderItem.order_id == order_id,
                    OcrOrderItem.status == OrderItemStatus.COMPLETED,
                    OcrOrderItem.ocr_result_json_path.isnot(None)
                ).all()

                if not completed_items:
                    order.status = OrderStatus.FAILED
                    order.error_message = "No completed items found for consolidation"
                    db.commit()
                    return

                # Download and aggregate all item results
                all_consolidated_results = []

                for item in completed_items:
                    try:
                        # Download item results from S3
                        if item.ocr_result_json_path.startswith('s3://'):
                            s3_key = item.ocr_result_json_path.replace(f"s3://{self.s3_manager.bucket_name}/", "")
                            if s3_key.startswith(self.s3_manager.upload_prefix):
                                s3_key = s3_key[len(self.s3_manager.upload_prefix):]

                            item_results_content = self.s3_manager.download_file(s3_key)
                            if item_results_content:
                                loaded = json.loads(item_results_content.decode('utf-8'))

                                # Normalise to a list of dicts
                                if isinstance(loaded, dict):
                                    item_results = [loaded]
                                elif isinstance(loaded, list):
                                    item_results = loaded
                                else:
                                    raise ValueError("Unexpected results JSON structure (must be object or array)")

                                # Add item metadata to each result (defensive: only dicts)
                                annotated = []
                                for result in item_results:
                                    if not isinstance(result, dict):
                                        continue
                                    result['__item_id'] = item.item_id
                                    result['__item_name'] = item.item_name
                                    result['__company'] = item.company.company_name if item.company else None
                                    result['__doc_type'] = item.document_type.type_name if item.document_type else None
                                    annotated.append(result)

                                all_consolidated_results.extend(annotated)

                    except Exception as e:
                        logger.error(f"Error loading results for item {item.item_id}: {str(e)}")

                if not all_consolidated_results:
                    order.status = OrderStatus.FAILED
                    order.error_message = "No results found for consolidation"
                    db.commit()
                    return

                # Generate consolidated reports
                await self._generate_consolidated_reports(order_id, all_consolidated_results)

                # Mark order as completed
                order.status = OrderStatus.COMPLETED
                order.updated_at = datetime.utcnow()
                db.commit()

                logger.info(f"Order {order_id} consolidation completed successfully")

            except Exception as e:
                logger.error(f"Error consolidating order {order_id}: {str(e)}")
                order.status = OrderStatus.FAILED
                order.error_message = f"Consolidation failed: {str(e)}"
                db.commit()

    async def _generate_consolidated_reports(self, order_id: int, results: List[Dict[str, Any]]):
        """Generate consolidated reports for the entire order"""
        try:
            s3_base = f"results/orders/{order_id // 1000}/consolidated"

            # Save consolidated JSON
            json_content = json.dumps(results, indent=2, ensure_ascii=False)
            json_s3_key = f"{s3_base}/order_{order_id}_consolidated.json"
            json_upload_success = self.s3_manager.upload_file(json_content.encode('utf-8'), json_s3_key)

            # Save consolidated Excel
            excel_path = None
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_excel:
                temp_excel_path = temp_excel.name

            try:
                json_to_excel(results, temp_excel_path)

                with open(temp_excel_path, 'rb') as excel_file:
                    excel_content = excel_file.read()
                    excel_s3_key = f"{s3_base}/order_{order_id}_consolidated.xlsx"
                    excel_upload_success = self.s3_manager.upload_file(excel_content, excel_s3_key)

                    if excel_upload_success:
                        excel_path = f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{excel_s3_key}"

            finally:
                os.unlink(temp_excel_path)

            # Save consolidated CSV
            csv_path = None
            with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as temp_csv:
                temp_csv_path = temp_csv.name

            try:
                json_to_csv(results, temp_csv_path)

                with open(temp_csv_path, 'rb') as csv_file:
                    csv_content = csv_file.read()
                    csv_s3_key = f"{s3_base}/order_{order_id}_consolidated.csv"
                    csv_upload_success = self.s3_manager.upload_file(csv_content, csv_s3_key)

                    if csv_upload_success:
                        csv_path = f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{csv_s3_key}"

            finally:
                os.unlink(temp_csv_path)

            # Update order with consolidated report paths
            with Session(engine) as db:
                order = db.query(OcrOrder).filter(OcrOrder.order_id == order_id).first()
                if order:
                    logger.info(f"🔍 CONSOLIDATION - BEFORE update - Order {order_id} final_report_paths: {order.final_report_paths}")

                    # Preserve existing final_report_paths and update consolidation results
                    current_paths = order.final_report_paths or {}
                    consolidation_paths = {
                        'consolidated_json': f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{json_s3_key}" if json_upload_success else None,
                        'consolidated_excel': excel_path,
                        'consolidated_csv': csv_path
                    }

                    logger.info(f"🔍 CONSOLIDATION - Adding paths: {consolidation_paths}")
                    logger.info(f"🔍 CONSOLIDATION - Current existing paths: {current_paths}")

                    # Update consolidation paths while preserving mapping paths
                    current_paths.update(consolidation_paths)
                    order.final_report_paths = current_paths

                    # Force SQLAlchemy to detect JSONB field changes
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(order, 'final_report_paths')

                    logger.info(f"🔍 CONSOLIDATION - AFTER update - final_report_paths: {current_paths}")

                    try:
                        db.commit()
                        logger.info(f"✅ CONSOLIDATION - Successfully committed for order {order_id}")

                        # Verify the commit worked by re-querying
                        db.refresh(order)
                        logger.info(f"🔍 CONSOLIDATION - POST-COMMIT verification - final_report_paths: {order.final_report_paths}")

                    except Exception as commit_error:
                        logger.error(f"❌ CONSOLIDATION - Failed to commit for order {order_id}: {str(commit_error)}")
                        db.rollback()
                        raise

            logger.info(f"Consolidated reports generated for order {order_id}")

        except Exception as e:
            logger.error(f"Error generating consolidated reports for order {order_id}: {str(e)}")
            raise


    async def process_order_mapping_only(self, order_id: int):
        """Process mapping for an order using per-item configurations."""
        with Session(engine) as db:
            order = db.query(OcrOrder).filter(OcrOrder.order_id == order_id).first()
            if not order:
                logger.error(f"Order {order_id} not found")
                return

            if order.status == OrderStatus.LOCKED:
                logger.error(f"Order {order_id} is locked and cannot be processed for mapping")
                return

            if order.status not in {OrderStatus.OCR_COMPLETED, OrderStatus.MAPPING}:
                logger.warning(
                    f"Order {order_id} must be in OCR_COMPLETED or MAPPING status (current: {order.status})"
                )
                return

            order.status = OrderStatus.MAPPING
            order.completed_items = db.query(OcrOrderItem).filter(
                OcrOrderItem.order_id == order_id,
                OcrOrderItem.status == OrderItemStatus.COMPLETED,
            ).count()
            order.failed_items = db.query(OcrOrderItem).filter(
                OcrOrderItem.order_id == order_id,
                OcrOrderItem.status == OrderItemStatus.FAILED,
            ).count()

            order.updated_at = datetime.utcnow()
            db.commit()

        aggregated_frames: List[pd.DataFrame] = []
        item_failures: Dict[int, str] = {}

        with Session(engine) as db:
            resolver = MappingConfigResolver(db)
            items = db.query(OcrOrderItem).filter(
                OcrOrderItem.order_id == order_id,
                OcrOrderItem.status == OrderItemStatus.COMPLETED,
            ).all()

            if not items:
                logger.warning(f"Order {order_id} has no completed items to map")
                order = db.query(OcrOrder).filter(OcrOrder.order_id == order_id).first()
                if order:
                    order.status = OrderStatus.FAILED
                    order.error_message = "No completed items available for mapping"
                    order.updated_at = datetime.utcnow()
                    db.commit()
                return

            for item in items:
                try:
                    resolved = resolver.resolve_for_item(
                        company_id=item.company_id,
                        doc_type_id=item.doc_type_id,
                        item_type=item.item_type,
                        current_config=item.mapping_config,
                    )

                    if resolved:
                        item.mapping_config = resolved.config
                        item.applied_template_id = resolved.template_id
                        resolved_type = resolved.config.get("item_type")
                        if resolved_type:
                            item.item_type = OrderItemType(resolved_type)

                    if not item.mapping_config:
                        raise RuntimeError("Mapping configuration not defined for item")

                    mapping_item_type = MappingItemType(
                        item.mapping_config.get("item_type", item.item_type.value)
                    )

                    logger.info(
                        "Processing mapping for order %s item %s (type=%s)",
                        order_id,
                        item.item_id,
                        mapping_item_type.value,
                    )

                    records = self._load_item_records(item)

                    if mapping_item_type == MappingItemType.SINGLE_SOURCE:
                        item_df = self._build_single_source_dataframe(item, records)
                    else:
                        internal_key = item.mapping_config.get("internal_join_key") if isinstance(item.mapping_config, dict) else None
                        # Support per-attachment join keys; 'internal_key' acts as default if provided
                        item_df = self._build_multi_source_dataframe(item, records, internal_key)

                    master_path = item.mapping_config.get("master_csv_path")
                    if not master_path:
                        raise RuntimeError("master_csv_path missing from mapping configuration")

                    master_df = self._get_master_csv_dataframe(master_path)

                    merged_df = self._join_with_master_csv(
                        item_df,
                        master_df,
                        item.mapping_config.get("external_join_keys", []),
                        item.mapping_config.get("column_aliases"),
                        item.mapping_config.get("join_normalize") or item.mapping_config.get("join_value_normalization"),
                    )

                    mapped_path = self._persist_item_mapping_result(order_id, item, merged_df)
                    item.ocr_result_csv_path = mapped_path
                    item.updated_at = datetime.utcnow()
                    item.status = OrderItemStatus.COMPLETED
                    item.error_message = None

                    annotated_df = merged_df.copy()
                    # Optional: augment with metadata columns based on mapping spec defined in mapping_config.output_meta
                    mapping_spec = None
                    try:
                        if isinstance(item.mapping_config, dict):
                            mapping_spec = item.mapping_config.get("output_meta")
                    except Exception:
                        mapping_spec = None
                    self._apply_output_metadata(
                        annotated_df,
                        {
                            "order_id": order_id,
                            "item_id": item.item_id,
                            "item_name": item.item_name or "",
                            "company_id": item.company_id,
                            "doc_type_id": item.doc_type_id,
                        },
                        mapping_spec,
                    )
                    aggregated_frames.append(annotated_df)

                except Exception as exc:
                    logger.error(
                        "Failed to map order %s item %s: %s",
                        order_id,
                        item.item_id,
                        exc,
                    )
                    item.status = OrderItemStatus.FAILED
                    item.error_message = str(exc)
                    item.updated_at = datetime.utcnow()
                    item_failures[item.item_id] = str(exc)

            db.commit()

        with Session(engine) as db:
            order = db.query(OcrOrder).filter(OcrOrder.order_id == order_id).first()
            if not order:
                logger.error(f"Order {order_id} not found after mapping")
                return

            from sqlalchemy.orm.attributes import flag_modified

            if aggregated_frames:
                combined_df = pd.concat(aggregated_frames, ignore_index=True)
                s3_base = f"results/orders/{order_id // 1000}/consolidated"
                csv_key = f"{s3_base}/order_{order_id}_mapped.csv"
                csv_bytes = combined_df.to_csv(index=False).encode("utf-8")
                upload_success = self.s3_manager.upload_file(csv_bytes, csv_key)

                mapped_path = (
                    f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{csv_key}"
                    if upload_success
                    else None
                )

                current_paths = order.final_report_paths or {}
                if mapped_path:
                    current_paths['mapped_csv'] = mapped_path
                order.final_report_paths = current_paths
                flag_modified(order, 'final_report_paths')

                if item_failures:
                    order.status = OrderStatus.FAILED
                    order.error_message = ", ".join(
                        f"item {item_id}: {error}" for item_id, error in item_failures.items()
                    )
                else:
                    order.status = OrderStatus.COMPLETED
                    order.error_message = None
            else:
                order.status = OrderStatus.FAILED
                order.error_message = (
                    ", ".join(
                        f"item {item_id}: {error}" for item_id, error in item_failures.items()
                    )
                    if item_failures
                    else "No mapping outputs generated"
                )

            order.updated_at = datetime.utcnow()
            db.commit()
    async def _load_expanded_ocr_results(self, order_id: int) -> List[Dict[str, Any]]:
        """Load OCR results in expanded format (individual rows per phone service)"""
        with Session(engine) as db:
            # Get completed order items
            items = db.query(OcrOrderItem).filter(
                OcrOrderItem.order_id == order_id,
                OcrOrderItem.status == OrderItemStatus.COMPLETED
            ).all()

            all_expanded_results = []

            for item in items:
                try:
                    # Download item's CSV results (expanded format)
                    if not item.ocr_result_csv_path or not item.ocr_result_csv_path.startswith('s3://'):
                        logger.error(f"Invalid CSV path for item {item.item_id}")
                        continue

                    s3_key = item.ocr_result_csv_path.replace(f"s3://{self.s3_manager.bucket_name}/", "")
                    if s3_key.startswith(self.s3_manager.upload_prefix):
                        s3_key = s3_key[len(self.s3_manager.upload_prefix):]

                    csv_content = self.s3_manager.download_file(s3_key)
                    if not csv_content:
                        logger.error(f"Failed to download CSV for item {item.item_id}")
                        continue

                    # Parse CSV data
                    import pandas as pd
                    from io import StringIO

                    df = pd.read_csv(StringIO(csv_content.decode('utf-8')))
                    item_records = df.to_dict('records')

                    # Add item metadata to each record
                    for record in item_records:
                        record['__item_id'] = item.item_id
                        record['__item_name'] = item.item_name
                        record['__company'] = item.company.company_name if item.company else None
                        record['__doc_type'] = item.document_type.type_name if item.document_type else None

                    all_expanded_results.extend(item_records)
                    logger.info(f"Loaded {len(item_records)} expanded records from item {item.item_id}")

                except Exception as e:
                    logger.error(f"Error loading expanded results for item {item.item_id}: {str(e)}")
                    continue

            return all_expanded_results


# ------------------------------------------------------------------
# Backward-compatible wrappers expected by app.py background tasks
# ------------------------------------------------------------------
async def start_order_processing(order_id: int) -> None:
    """Compatibility wrapper: process full order pipeline."""
    processor = OrderProcessor()
    await processor.process_order(order_id)


async def start_order_ocr_only_processing(order_id: int) -> None:
    """Compatibility wrapper: run OCR only for a given order."""
    processor = OrderProcessor()
    await processor.process_order_ocr_only(order_id)


async def start_order_mapping_only_processing(order_id: int) -> None:
    """Compatibility wrapper: run mapping-only stage for a given order."""
    processor = OrderProcessor()
    await processor.process_order_mapping_only(order_id)
