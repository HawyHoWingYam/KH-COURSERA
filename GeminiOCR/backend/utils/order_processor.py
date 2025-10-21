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
from typing import List, Dict, Any, Optional, Union, Tuple
from enum import Enum
from dataclasses import dataclass, field
import logging
import pandas as pd
from difflib import SequenceMatcher

from sqlalchemy.orm import Session, sessionmaker, joinedload

from db.database import engine
from db.models import (
    OcrOrder, OcrOrderItem, OrderItemFile, OrderStatus, OrderItemStatus,
    Company, DocumentType, CompanyDocumentConfig, File, ApiUsage
)
from main import extract_text_from_image, extract_text_from_pdf
from utils.s3_storage import get_s3_manager
from utils.file_storage import get_file_storage
from utils.special_csv_generator import SpecialCsvGenerator
from utils.template_service import sanitize_template_version
from utils.prompt_schema_manager import get_prompt_schema_manager
from utils.excel_converter import json_to_excel, json_to_csv
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

        # Initialize intelligent matching engine with default configuration
        default_config = MatchingConfig(
            strategies=[MatchingStrategy.EXACT, MatchingStrategy.SPLIT, MatchingStrategy.CONTAINS, MatchingStrategy.FUZZY],
            priority_order=[MatchingStrategy.EXACT, MatchingStrategy.SPLIT, MatchingStrategy.CONTAINS, MatchingStrategy.FUZZY],
            fuzzy_threshold=0.8,
            min_match_length=3,
            case_sensitive=False
        )
        self.matching_engine = MatchingEngine(default_config)

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

                # Load prompt and schema
                prompt = await self.prompt_schema_manager.get_prompt(company.company_code, doc_type.type_code)
                schema = await self.prompt_schema_manager.get_schema(company.company_code, doc_type.type_code)

                if not prompt or not schema:
                    raise Exception("Prompt or schema not found")

                # Get files for this item
                file_links = db.query(OrderItemFile).filter(OrderItemFile.item_id == item_id).all()
                if not file_links:
                    raise Exception("No files found for item")

                # Process all files for this item
                all_results = []
                temp_files_to_cleanup = []
                is_awb = doc_type.type_code == "AIRWAY_BILL"  # Check if this is an AWB item

                for file_link in file_links:
                    file_record = file_link.file
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
                                    # Add file-level metadata for AWB items
                                    if is_awb:
                                        business_data["__file_id"] = file_record.file_id
                                        business_data["__source_path"] = file_record.file_path
                                    all_results.append(business_data)
                                except json.JSONDecodeError:
                                    error_result = {
                                        "text": text_content,
                                        "__filename": file_record.file_name
                                    }
                                    if is_awb:
                                        error_result["__file_id"] = file_record.file_id
                                        error_result["__source_path"] = file_record.file_path
                                    all_results.append(error_result)
                            else:
                                no_content_result = {
                                    "__filename": file_record.file_name,
                                    "__error": "No text content in result"
                                }
                                if is_awb:
                                    no_content_result["__file_id"] = file_record.file_id
                                    no_content_result["__source_path"] = file_record.file_path
                                all_results.append(no_content_result)

                    except Exception as e:
                        logger.error(f"Error processing file {file_record.file_name}: {str(e)}")
                        error_result = {
                            "__filename": file_record.file_name,
                            "__error": f"Processing failed: {str(e)}"
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
        """Save individual item results to S3, with file-level results for AWB items"""
        try:
            # Generate S3 paths for item results
            s3_base = f"results/orders/{item_id // 1000}/items/{item_id}"
            is_awb = doc_type_code == "AIRWAY_BILL"

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

            # Save JSON results (item-level aggregated results)
            json_content = json.dumps(results, indent=2, ensure_ascii=False)
            json_s3_key = f"{s3_base}/item_{item_id}_results.json"
            json_upload_success = self.s3_manager.upload_file(json_content.encode('utf-8'), json_s3_key)

            json_path = None
            if json_upload_success:
                json_path = f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{json_s3_key}"

            # Save CSV results
            csv_path = None
            with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as temp_csv:
                temp_csv_path = temp_csv.name

            try:
                json_to_csv(results, temp_csv_path)

                with open(temp_csv_path, 'rb') as csv_file:
                    csv_content = csv_file.read()
                    csv_s3_key = f"{s3_base}/item_{item_id}_results.csv"
                    csv_upload_success = self.s3_manager.upload_file(csv_content, csv_s3_key)

                    if csv_upload_success:
                        csv_path = f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{csv_s3_key}"

            finally:
                os.unlink(temp_csv_path)

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
                                item_results = json.loads(item_results_content.decode('utf-8'))

                                # Add item metadata to each result
                                for result in item_results:
                                    result['__item_id'] = item.item_id
                                    result['__item_name'] = item.item_name
                                    result['__company'] = item.company.company_name if item.company else None
                                    result['__doc_type'] = item.document_type.type_name if item.document_type else None

                                all_consolidated_results.extend(item_results)

                    except Exception as e:
                        logger.error(f"Error loading results for item {item.item_id}: {str(e)}")

                if not all_consolidated_results:
                    order.status = OrderStatus.FAILED
                    order.error_message = "No results found for consolidation"
                    db.commit()
                    return

                # Generate consolidated reports
                await self._generate_consolidated_reports(order_id, all_consolidated_results)

                # Apply mapping if mapping file and keys are provided
                if order.mapping_file_path and order.mapping_keys:
                    await self._apply_order_mapping(order_id, all_consolidated_results)

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
        """Process mapping for an order that already has OCR results (MAPPING status)"""
        with Session(engine) as db:
            try:
                # Get order
                order = db.query(OcrOrder).filter(OcrOrder.order_id == order_id).first()
                if not order:
                    logger.error(f"Order {order_id} not found")
                    return

                # Check if order is locked
                if order.status == OrderStatus.LOCKED:
                    logger.error(f"Order {order_id} is locked and cannot be processed for mapping")
                    return

                if order.status != OrderStatus.MAPPING:
                    logger.warning(f"Order {order_id} is not in MAPPING status")
                    return

                # Get order details for logging
                total_items = db.query(OcrOrderItem).filter(OcrOrderItem.order_id == order_id).count()
                completed_items = db.query(OcrOrderItem).filter(
                    OcrOrderItem.order_id == order_id,
                    OcrOrderItem.status == OrderItemStatus.COMPLETED
                ).count()

                logger.info(f"🚀 Starting dynamic mapping processing for order {order_id}")
                logger.info(f"📊 Order overview: {completed_items}/{total_items} items completed")
                logger.info(f"📁 Mapping file: {order.mapping_file_path}")
                logger.info(f"🔑 Mapping keys: {order.mapping_keys}")
                logger.info(f"📈 Status: {order.status}")

                # Load existing OCR results - get the expanded CSV format
                all_ocr_results = await self._load_expanded_ocr_results(order_id)
                if not all_ocr_results:
                    logger.error(f"No OCR results found for order {order_id}")
                    return

                logger.info(f"Loaded {len(all_ocr_results)} OCR result records")

                # Load and parse mapping file using dynamic processor
                if not order.mapping_file_path:
                    logger.error(f"No mapping file found for order {order_id}")
                    return

                mapping_content = self.s3_manager.download_file_by_stored_path(order.mapping_file_path)
                if not mapping_content:
                    logger.error(f"Could not read mapping file for order {order_id}")
                    return

                # Use dynamic mapping processor
                from cost_allocation.dynamic_mapping_processor import process_dynamic_mapping_file
                mapping_result = process_dynamic_mapping_file(mapping_content, order.mapping_file_path)

                if not mapping_result['success']:
                    logger.error(f"Failed to process mapping file: {mapping_result.get('error', 'Unknown error')}")
                    return

                mapping_data = mapping_result['mapping_data']
                mapping_columns = mapping_result['columns']
                logger.info(f"Loaded {len(mapping_data)} mapping records with columns: {mapping_columns}")

                # Get user-selected mapping keys or auto-apply from document configuration
                user_mapping_keys = order.mapping_keys or []

                # AUTO-MAPPING: Check if no user mapping keys are configured and auto-mapping is enabled
                if not user_mapping_keys:
                    logger.info(f"No user mapping keys found for order {order_id}, checking for auto-mapping configuration...")

                    # Get distinct company/document type pairs from order items
                    order_items = db.query(OcrOrderItem).filter(
                        OcrOrderItem.order_id == order_id,
                        OcrOrderItem.status == OrderItemStatus.COMPLETED
                    ).all()

                    auto_mapping_keys = []
                    for item in order_items:
                        # Check if auto-mapping is enabled for this company/document type
                        config = db.query(CompanyDocumentConfig).filter(
                            CompanyDocumentConfig.company_id == item.company_id,
                            CompanyDocumentConfig.doc_type_id == item.doc_type_id,
                            CompanyDocumentConfig.auto_mapping_enabled == True,
                            CompanyDocumentConfig.active == True
                        ).first()

                        if config and config.default_mapping_keys:
                            logger.info(f"Found auto-mapping config for company {item.company_id}, doc_type {item.doc_type_id}: {config.default_mapping_keys}")
                            # Use default mapping keys from configuration
                            auto_mapping_keys.extend(config.default_mapping_keys)
                            break  # Use first found configuration

                    if auto_mapping_keys:
                        # Remove duplicates while preserving order
                        user_mapping_keys = list(dict.fromkeys(auto_mapping_keys))
                        logger.info(f"Applied auto-mapping keys: {user_mapping_keys}")

                        # Update order with auto-applied mapping keys for record keeping
                        order.mapping_keys = user_mapping_keys
                        db.commit()
                    else:
                        logger.error(f"No mapping keys configured for order {order_id} and no auto-mapping configuration found")
                        return

                logger.info(f"Using user-selected mapping keys: {user_mapping_keys}")

                # Perform dynamic JOIN operation
                joined_results = await self._perform_dynamic_join(
                    all_ocr_results, mapping_data, mapping_columns, user_mapping_keys, order_id
                )

                logger.info(f"JOIN completed: {len(joined_results)} records processed")

                # Generate final CSV with proper format
                if joined_results:
                    template_details = self._get_template_details_from_order(order, db)
                    csv_content, standard_df = self._generate_mapped_csv(joined_results, mapping_columns)

                    # DataFrame logging for debugging (show first 5 rows after mapping completion)
                    # logger.info(f"🔍 DataFrame Debug - Order {order_id} after mapping completion:")
                    # logger.info(f"   DataFrame shape: {standard_df.shape}")
                    # logger.info(f"   DataFrame columns: {list(standard_df.columns)}")
                    # logger.info(f"   First 5 rows sample:")
                    # logger.info(f"{standard_df.head().to_dict('records')}")

                    # Save final results to S3 - using consistent path format
                    s3_base = f"results/orders/{order_id // 1000}/mapped"
                    final_key = f"{s3_base}/order_{order_id}_mapped.csv"
                    success = self.s3_manager.upload_file(csv_content.encode('utf-8'), final_key)

                    if success:
                        # logger.info(f"Final mapped results saved to S3: {final_key}")

                        # Update order status to COMPLETED and set final_report_paths
                        order.status = OrderStatus.COMPLETED
                        order.updated_at = datetime.utcnow()

                        # Update final_report_paths with the CSV path
                        csv_path = f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{final_key}"
                        current_paths = order.final_report_paths or {}
                        current_paths['mapped_csv'] = csv_path

                        special_csv_path = None
                        if template_details:
                            logger.info(f"🎯 Starting Special CSV generation for order {order.order_id}")
                            logger.info(f"   Using template: {template_details.get('template_path', 'N/A')}")
                            logger.info(f"   Input DataFrame shape: {standard_df.shape}")
                            logger.info(f"   Input DataFrame columns: {list(standard_df.columns)}")

                            special_csv_path = self._generate_special_csv_from_template(
                                order.order_id,
                                standard_df,
                                template_details["template_path"],
                                template_details.get("doc_type_name", ""),
                                s3_base,
                            )

                            if special_csv_path:
                                logger.info(f"✅ Special CSV generated successfully: {special_csv_path}")
                            else:
                                logger.error(f"❌ Special CSV generation failed for order {order.order_id}")
                        else:
                            logger.warning(
                                "⚠️  Order %s does not have a primary document template configured; skipping special CSV",
                                order.order_id,
                            )

                        if special_csv_path:
                            current_paths['special_csv'] = special_csv_path

                        order.final_report_paths = current_paths

                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(order, 'final_report_paths')

                        db.commit()

                        # Count matching statistics
                        matched_records = sum(1 for row in joined_results if row.get('Matched', False))
                        unmatched_records = len(joined_results) - matched_records
                        match_rate = (matched_records / len(joined_results) * 100) if joined_results else 0

                        logger.info(f"✅ Order {order_id} mapping processing completed successfully")
                        logger.info(f"📊 Final statistics:")
                        logger.info(f"   - Total records processed: {len(joined_results)}")
                        logger.info(f"   - Successfully matched: {matched_records}")
                        logger.info(f"   - Unmatched records: {unmatched_records}")
                        logger.info(f"   - Match rate: {match_rate:.1f}%")
                        logger.info(f"📁 Results saved to: {csv_path}")
                    else:
                        logger.error(f"Failed to save final results for order {order_id}")
                else:
                    logger.error(f"No results to save for order {order_id}")

            except Exception as e:
                logger.error(f"Error in mapping-only processing for order {order_id}: {str(e)}")
                db.rollback()
                # Update order status to FAILED
                try:
                    order = db.query(OcrOrder).filter(OcrOrder.order_id == order_id).first()
                    if order:
                        order.status = OrderStatus.FAILED
                        order.updated_at = datetime.utcnow()
                        db.commit()
                except:
                    pass
                raise

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

    async def _perform_dynamic_join(self, ocr_results: List[Dict], mapping_data: List[Dict],
                                   mapping_columns: List[str], user_mapping_keys: List[str],
                                   order_id: int = None) -> List[Dict]:
        """Perform dynamic JOIN based on user-selected mapping keys"""

        # Get OCR columns to understand available fields
        ocr_columns = set()
        if ocr_results:
            ocr_columns = set(ocr_results[0].keys())

        logger.info(f"🔍 MAPPING ANALYSIS START - Order {order_id}")
        logger.info(f"   Available OCR columns: {sorted(ocr_columns)}")
        logger.info(f"   Available mapping columns: {mapping_columns}")
        logger.info(f"   User selected mapping keys: {user_mapping_keys}")

        # Simplified field mapping using only default mapping keys
        ocr_fields = []
        mapping_fields = []

        logger.info(f"🚀 Starting field analysis for mapping keys...")

        # AUTO-MAPPING: Use default mapping keys to determine OCR and mapping fields
        if order_id:
            logger.info("🤖 Using default mapping keys from document configuration")
            # We'll use the user_mapping_keys directly for both OCR and mapping field detection
            # This simplified approach relies on the user's selected mapping keys

        for key in user_mapping_keys:
            # Check for direct field matches
            direct_ocr_match = key in ocr_columns
            direct_mapping_match = key in mapping_columns

            if direct_ocr_match:
                ocr_fields.append(key)
                logger.info(f"'{key}' identified as OCR field")

            if direct_mapping_match:
                mapping_fields.append(key)
                logger.info(f"'{key}' identified as mapping field")

            # If key not found in either column set, try semantic matching
            if not direct_ocr_match and not direct_mapping_match:
                logger.warning(f"'{key}' not found in either OCR or mapping columns, trying semantic matching...")

                key_lower = key.lower()

                # Find semantically equivalent OCR fields
                for ocr_col in ocr_columns:
                    ocr_col_lower = ocr_col.lower()
                    if self._are_semantically_equivalent(key_lower, ocr_col_lower):
                        ocr_fields.append(ocr_col)
                        logger.info(f"'{ocr_col}' identified as similar OCR field for '{key}'")
                        break

                # Find semantically equivalent mapping fields
                for map_col in mapping_columns:
                    map_col_lower = map_col.lower()
                    if self._are_semantically_equivalent(key_lower, map_col_lower):
                        mapping_fields.append(map_col)
                        logger.info(f"'{map_col}' identified as similar mapping field for '{key}'")
                        break

                # If still not found, add as fallback
                if not any(key.lower() == field.lower() for field in ocr_fields + mapping_fields):
                    ocr_fields.append(key)
                    mapping_fields.append(key)
                    logger.info(f"'{key}' added to both OCR and mapping fields as fallback")

        logger.info(f"Final OCR fields: {ocr_fields}")
        logger.info(f"Final mapping fields: {mapping_fields}")

        # Create lookup dictionary from mapping data using mapping fields
        mapping_lookup = {}

        for mapping_row in mapping_data:
            # Create lookup keys from mapping fields
            lookup_keys = []

            # Use mapping fields (from mapping file) to create lookup keys
            for mapping_field in mapping_fields:
                if mapping_field in mapping_row and pd.notna(mapping_row[mapping_field]):
                    # Normalize the lookup key
                    normalized_key = self._normalize_identifier(str(mapping_row[mapping_field]))
                    if normalized_key:
                        lookup_keys.append(normalized_key)
                        # Store the mapping record for each lookup key
                        mapping_lookup[normalized_key] = mapping_row.copy()

            # If no direct mapping fields identified, try all user-selected keys in mapping data
            if not mapping_fields:
                for user_key in user_mapping_keys:
                    if user_key in mapping_row and pd.notna(mapping_row[user_key]):
                        normalized_key = self._normalize_identifier(str(mapping_row[user_key]))
                        if normalized_key:
                            lookup_keys.append(normalized_key)
                            mapping_lookup[normalized_key] = mapping_row.copy()
                            logger.info(f"Added user-key lookup: mapping[{user_key}]='{mapping_row[user_key]}' -> key='{normalized_key}'")

        logger.info(f"Created mapping lookup with {len(mapping_lookup)} entries from mapping fields: {mapping_fields}")

        # Perform JOIN operation with improved multi-key matching
        joined_results = []
        matched_count = 0
        debug_info = []

        for i, ocr_row in enumerate(ocr_results):
            # Try to find matching record using multiple strategies
            mapping_match = None
            match_info = {"row_index": i, "attempts": [], "matched": False}

            # Strategy 1: Try matching using OCR fields
            for ocr_field in ocr_fields:
                if ocr_field in ocr_row and pd.notna(ocr_row[ocr_field]):
                    lookup_value = self._normalize_identifier(str(ocr_row[ocr_field]))
                    match_info["attempts"].append({
                        "strategy": "ocr_field",
                        "field": ocr_field,
                        "original_value": str(ocr_row[ocr_field]),
                        "normalized_value": lookup_value
                    })

                    mapping_match = mapping_lookup.get(lookup_value)
                    if mapping_match:
                        matched_count += 1
                        match_info["matched"] = True
                        match_info["matched_strategy"] = f"ocr_field:{ocr_field}"
                        match_info["matched_value"] = lookup_value
                        logger.info(f"✓ Row {i}: Matched OCR field '{ocr_field}' value '{lookup_value}'")
                        break

            
            # Strategy 2: If no match found with OCR fields, try all user keys directly
            if not mapping_match:
                for user_key in user_mapping_keys:
                    if user_key in ocr_row and pd.notna(ocr_row[user_key]):
                        lookup_value = self._normalize_identifier(str(ocr_row[user_key]))
                        match_info["attempts"].append({
                            "strategy": "user_key",
                            "field": user_key,
                            "original_value": str(ocr_row[user_key]),
                            "normalized_value": lookup_value
                        })

                        mapping_match = mapping_lookup.get(lookup_value)
                        if mapping_match:
                            matched_count += 1
                            match_info["matched"] = True
                            match_info["matched_strategy"] = f"user_key:{user_key}"
                            match_info["matched_value"] = lookup_value
                            logger.info(f"✓ Row {i}: Matched user key '{user_key}' value '{lookup_value}'")
                            break

            # Strategy 3: Intelligent matching using MatchingEngine for unmatched records
            if not mapping_match:
                # Try intelligent matching for each mapping key against each OCR field
                best_match_result = None
                best_mapping_record = None

                for user_key in user_mapping_keys:
                    # Get all possible OCR field values to try matching against
                    ocr_values_to_try = []

                    # Add values from all OCR fields
                    for ocr_field, ocr_value in ocr_row.items():
                        if ocr_value and not pd.isna(ocr_value) and not ocr_field.startswith('__'):
                            ocr_values_to_try.append((ocr_field, str(ocr_value)))

                    # Try matching against all mapping records
                    for mapping_record in mapping_data:
                        if user_key in mapping_record and pd.notna(mapping_record[user_key]):
                            mapping_value = str(mapping_record[user_key])

                            # Try intelligent matching with each OCR field value
                            for ocr_field, ocr_value in ocr_values_to_try:
                                match_result = self.matching_engine.match(
                                    ocr_value=ocr_value,
                                    mapping_value=mapping_value,
                                    strategy=MatchingStrategy.SMART,
                                    field_name=user_key
                                )

                                if match_result.success:
                                    # Found a successful intelligent match
                                    if (best_match_result is None or
                                        match_result.similarity_score > best_match_result.similarity_score):
                                        best_match_result = match_result
                                        best_mapping_record = mapping_record

                                        # Log detailed match information
                                        # logger.info(f"🎯 Row {i}: Intelligent match found!")
                                        # logger.info(f"   Strategy: {match_result.strategy.value}")
                                        # logger.info(f"   OCR field '{ocr_field}': '{ocr_value}'")
                                        # logger.info(f"   Mapping field '{user_key}': '{mapping_value}'")
                                        # logger.info(f"   Similarity: {match_result.similarity_score:.3f}")
                                        # logger.info(f"   Reason: {match_result.match_reason}")
                                        # if match_result.extracted_parts:
                                        #     logger.info(f"   Extracted parts: {match_result.extracted_parts}")

                if best_match_result and best_mapping_record:
                    # Use the best intelligent match found
                    mapping_match = best_mapping_record
                    matched_count += 1
                    match_info["matched"] = True
                    match_info["matched_strategy"] = f"intelligent:{best_match_result.strategy.value}"
                    match_info["matched_value"] = best_match_result.mapping_value
                    match_info["similarity_score"] = best_match_result.similarity_score
                    match_info["match_reason"] = best_match_result.match_reason

                    # logger.info(f"✓ Row {i}: Intelligent match success - {best_match_result.match_reason}")
                else:
                    # No intelligent match found either
                    match_info["unmatched_reason"] = "No match found using exact or intelligent strategies"
                    # logger.warning(f"✗ Row {i}: No match found for OCR record with item_id={ocr_row.get('__item_id', 'unknown')}")

            debug_info.append(match_info)

            # Create joined record
            joined_row = {}

            # Add mapping columns first (empty if no match)
            for col in mapping_columns:
                if mapping_match and col in mapping_match:
                    joined_row[col] = mapping_match[col]
                else:
                    joined_row[col] = ''

            # Add all OCR columns
            for col, value in ocr_row.items():
                joined_row[col] = value

            # Add match status (CRITICAL for Special CSV generation)
            joined_row['Matched'] = match_info.get('matched', False)

            # Log the match status for debugging
            if i < 3:  # Log first 3 rows to avoid spam
                logger.info(f"📝 Row {i}: Matched status = {joined_row['Matched']}, item_id = {ocr_row.get('__item_id', 'unknown')}")

            joined_results.append(joined_row)

        # Enhanced validation and debug logging
        unmatched_count = len(ocr_results) - matched_count
        match_rate = (matched_count / len(ocr_results) * 100) if ocr_results else 0

        # Log Matched column preservation verification
        matched_columns_in_output = sum(1 for row in joined_results if row.get('Matched', False))
        logger.info(f"🎯 CRITICAL VERIFICATION: Matched column preservation in joined_results:")
        logger.info(f"   Rows with Matched=True: {matched_columns_in_output}")
        logger.info(f"   Rows with Matched=False: {len(joined_results) - matched_columns_in_output}")
        logger.info(f"   Total rows in joined_results: {len(joined_results)}")
        logger.info(f"   Expected matches: {matched_count}")

        logger.info(f"🎯 JOIN OPERATION SUMMARY:")
        logger.info(f"   Total OCR records processed: {len(ocr_results)}")
        logger.info(f"   Successful matches: {matched_count}")
        logger.info(f"   Unmatched records: {unmatched_count}")
        logger.info(f"   Match rate: {match_rate:.1f}%")
        logger.info(f"   Mapping lookup table size: {len(mapping_lookup)}")

        # Log details about unmatched records for debugging
        unmatched_items = set()
        for info in debug_info:
            if not info["matched"]:
                item_id = ocr_results[info["row_index"]].get('__item_id', 'unknown')
                unmatched_items.add(item_id)

        if unmatched_items:
            logger.warning(f"⚠️  Unmatched records found in items: {sorted(unmatched_items)}")
            logger.info(f"💡 Debug tip: Check if mapping keys '{user_mapping_keys}' exist in both OCR and mapping data")

        # Validate that mapping columns are properly populated in results
        if joined_results and mapping_columns:
            populated_mapping_cols = 0
            for col in mapping_columns:
                if any(row.get(col, '') != '' for row in joined_results):
                    populated_mapping_cols += 1

            logger.info(f"📊 Mapping columns validation: {populated_mapping_cols}/{len(mapping_columns)} columns have data")

        return joined_results

    def _are_semantically_equivalent(self, field1: str, field2: str) -> bool:
        """Check if two field names are semantically equivalent"""
        # Define semantic equivalence mappings (case-insensitive)
        equivalences = {
            'phone': ['service_number', 'servicenumber', 'number', 'mobile', 'tel', 'telephone', 'contact'],
            'service_number': ['phone', 'servicenumber', 'number', 'mobile', 'service_no', 'svc_num'],
            'account': ['account_no', 'accountno', 'acc_no', 'account_number', 'acct'],
            'vendor': ['provider', 'carrier', 'operator', 'company'],
            'staff': ['employee', 'person', 'name', 'user'],
            'department': ['dept', 'division', 'section', 'shop'],
            'account_no': ['account', 'accountno', 'acc_no', 'account_number', 'acct']
        }

        # Normalize field names: lowercase, remove underscores, dashes, spaces
        field1_normalized = field1.lower().replace('_', '').replace('-', '').replace(' ', '')
        field2_normalized = field2.lower().replace('_', '').replace('-', '').replace(' ', '')

        # Direct match after normalization
        if field1_normalized == field2_normalized:
            return True

        # Check equivalences in both directions
        for key, synonyms in equivalences.items():
            key_normalized = key.lower().replace('_', '').replace('-', '').replace(' ', '')
            synonyms_normalized = [s.lower().replace('_', '').replace('-', '').replace(' ', '') for s in synonyms]

            # Check if field1 matches key or synonyms, and field2 matches key or synonyms
            if (field1_normalized == key_normalized or field1_normalized in synonyms_normalized):
                if (field2_normalized == key_normalized or field2_normalized in synonyms_normalized):
                    return True

        return False

    def _normalize_identifier(self, identifier: str) -> str:
        """Normalize identifier for consistent matching"""
        import re
        import pandas as pd

        if not identifier or pd.isna(identifier):
            return ""

        # Convert to string and remove spaces, special characters
        normalized = str(identifier).strip()
        normalized = re.sub(r'[^\w]', '', normalized)
        return normalized.upper()

    def _generate_mapped_csv(
        self, joined_results: List[Dict], mapping_columns: List[str]
    ) -> Tuple[str, pd.DataFrame]:
        """Generate CSV content and DataFrame with proper column ordering."""
        if not joined_results:
            return "", pd.DataFrame()

        # Get all unique columns
        all_columns = set()
        for row in joined_results:
            all_columns.update(row.keys())

        # Check if Matched column exists and log it
        has_matched_column = 'Matched' in all_columns
        if has_matched_column:
            logger.info(f"✓ Found Matched column in joined_results, will preserve in output DataFrame")
            matched_count = sum(1 for row in joined_results if row.get('Matched', False))
            logger.info(f"📊 Matched statistics in joined_results: {matched_count} matched, {len(joined_results) - matched_count} unmatched")
        else:
            logger.warning(f"✗ Matched column not found in joined_results - this will affect Special CSV generation")

        # Order columns: mapping columns first, then OCR columns, then metadata (Matched)
        ocr_columns = [col for col in all_columns if col not in mapping_columns and not col.startswith('__') and col != 'Matched']
        metadata_columns = ['Matched'] if has_matched_column else []
        ordered_columns = mapping_columns + ocr_columns + metadata_columns

        logger.info(f"📋 Column ordering: {len(mapping_columns)} mapping, {len(ocr_columns)} OCR, {len(metadata_columns)} metadata columns")
        if has_matched_column:
            logger.info(f"🔍 Matched column will be at position {len(ordered_columns) - 1} in output DataFrame")

        # Generate CSV
        import pandas as pd
        import io

        # Ensure all rows have all columns
        normalized_results = []
        for row in joined_results:
            normalized_row = {}
            for col in ordered_columns:
                normalized_row[col] = row.get(col, '')
            normalized_results.append(normalized_row)

        df = pd.DataFrame(normalized_results, columns=ordered_columns)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        return csv_buffer.getvalue(), df

    def _get_template_details_from_order(
        self, order: OcrOrder, db: Session
    ) -> Optional[Dict[str, str]]:
        """Resolve template path and metadata for an order within an active session."""

        if not order or not order.primary_doc_type_id:
            return None

        doc_type = order.primary_doc_type
        if not doc_type and order.primary_doc_type_id:
            doc_type = (
                db.query(DocumentType)
                .filter(DocumentType.doc_type_id == order.primary_doc_type_id)
                .first()
            )

        if doc_type and doc_type.template_json_path:
            return {
                "template_path": doc_type.template_json_path,
                "doc_type_name": doc_type.type_name or "",
            }

        return None

    def _get_order_template_details(self, order_id: int) -> Optional[Dict[str, str]]:
        """Fetch template details for an order using a dedicated session."""

        with Session(engine) as db:
            order = (
                db.query(OcrOrder)
                .options(joinedload(OcrOrder.primary_doc_type))
                .filter(OcrOrder.order_id == order_id)
                .first()
            )
            if not order:
                return None
            return self._get_template_details_from_order(order, db)

    def _generate_special_csv_from_template(
        self,
        order_id: int,
        standard_df: pd.DataFrame,
        template_path: str,
        doc_type_name: str,
        s3_base: str,
    ) -> Optional[str]:
        """Generate and upload special CSV using the provided template."""

        if standard_df is None or standard_df.empty:
            logger.warning(
                "Skipping special CSV generation for order %s because standard DataFrame is empty",
                order_id,
            )
            return None

        try:
            # Step 1: Load and validate template
            logger.info(f"Loading template for order {order_id} from: {template_path}")
            template_config = self.special_csv_generator.load_template_from_s3(template_path)

            # Step 2: Validate template structure
            logger.info(f"Validating template structure for order {order_id}")
            self.special_csv_generator.validate_template(template_config)
            template_version = sanitize_template_version(template_config.get("version", "latest"))

            # Step 3: Sort DataFrame by match status and generate special CSV with detailed logging
            logger.info(f"Generating special CSV for order {order_id} using template version {template_version}")
            logger.info(f"Input DataFrame shape: {standard_df.shape}, columns: {list(standard_df.columns)}")

            # Sort DataFrame by match status: matched records first, unmatched records last
            if 'Matched' in standard_df.columns:
                matched_count = standard_df['Matched'].sum()
                unmatched_count = len(standard_df) - matched_count
                logger.info(f"📊 Special CSV sorting: {matched_count} matched, {unmatched_count} unmatched")

                # Validate Matched column data
                logger.info(f"🔍 Matched column analysis:")
                matched_count = (standard_df['Matched'] == True).sum()
                unmatched_count = (standard_df['Matched'] == False).sum()
                logger.info(f"  - Matched rows: {matched_count}, Unmatched rows: {unmatched_count}")

                # Show sample data before sorting
                if matched_count > 0:
                    sample_matched_row = standard_df[standard_df['Matched'] == True].iloc[0]
                    logger.info(f"📋 Sample matched row: Department='{sample_matched_row.get('Department', 'N/A')}', Location_1='{sample_matched_row.get('Location_1', 'N/A')}', Mobile no.='{sample_matched_row.get('Mobile no.', 'N/A')}'")

                if unmatched_count > 0:
                    sample_unmatched_row = standard_df[standard_df['Matched'] == False].iloc[0]
                    logger.info(f"📋 Sample unmatched row: Department='{sample_unmatched_row.get('Department', 'N/A')}', Location_1='{sample_unmatched_row.get('Location_1', 'N/A')}', Mobile no.='{sample_unmatched_row.get('Mobile no.', 'N/A')}'")

                # Sort: matched records (True) first, unmatched (False) last
                logger.info("🔄 Performing sort: matched records first, unmatched records last")
                standard_df = standard_df.sort_values('Matched', ascending=False)
                logger.info("✅ DataFrame sorting completed successfully")

                # Verify sorting worked correctly
                first_rows = standard_df.head(3)['Matched'].tolist()
                last_rows = standard_df.tail(3)['Matched'].tolist()
                logger.info(f"🔍 Sorting verification: First 3 rows Matched status = {first_rows}, Last 3 rows Matched status = {last_rows}")
            else:
                logger.warning("⚠️ No 'Matched' column found in DataFrame - all computed columns will use standard computation")
                logger.info(f"🔍 Available columns for diagnosis: {list(standard_df.columns)}")

            special_df = self.special_csv_generator.generate_special_csv(standard_df, template_config)

            logger.info(f"Special CSV generated successfully - Output shape: {special_df.shape}, columns: {list(special_df.columns)}")

            # Step 4: Apply Excel formula escaping and prepare file
            escaped_df = special_df.copy()
            for column in escaped_df.columns:
                escaped_df[column] = escaped_df[column].apply(escape_excel_formulas)

            special_key = f"{s3_base}/order_{order_id}_special_v{template_version}.csv"
            special_csv_content = escaped_df.to_csv(index=False)

            logger.info(f"Uploading special CSV to S3: {special_key}")
            upload_success = self.s3_manager.upload_file(
                special_csv_content.encode("utf-8"), special_key
            )

            if upload_success:
                special_path = (
                    f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{special_key}"
                )
                logger.info(
                    "✅ Special CSV generated successfully for order %s using template '%s' (version %s)",
                    order_id,
                    doc_type_name or "unknown",
                    template_version,
                )
                logger.info(f"📁 Special CSV path: {special_path}")
                return special_path
            else:
                logger.error(
                    "❌ Failed to upload special CSV for order %s using template '%s' - S3 upload failed",
                    order_id,
                    doc_type_name or "unknown",
                )

        except FileNotFoundError as exc:
            logger.error(
                "❌ Template file not found for order %s using template '%s': %s",
                order_id,
                doc_type_name or "unknown",
                template_path,
            )
        except ValueError as exc:
            logger.error(
                "❌ Template validation failed for order %s using template '%s': %s",
                order_id,
                doc_type_name or "unknown",
                exc,
            )
        except Exception as exc:
            logger.error(
                "❌ Special CSV generation failed for order %s using template '%s': %s",
                order_id,
                doc_type_name or "unknown",
                exc,
            )
            logger.error(f"Error type: {type(exc).__name__}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")

        return None

    async def _apply_order_mapping(self, order_id: int, results: List[Dict[str, Any]]):
        """Apply mapping rules to consolidated order results"""
        with Session(engine) as db:
            try:
                logger.info(f"Starting mapping application for order {order_id}")

                # Get order with mapping configuration
                order = db.query(OcrOrder).filter(OcrOrder.order_id == order_id).first()
                if not order or not order.mapping_file_path:
                    logger.warning(f"No mapping file found for order {order_id}")
                    return

                # Download and process mapping file
                file_storage = get_file_storage()
                mapping_file_content = file_storage.download_file(order.mapping_file_path)
                if not mapping_file_content:
                    logger.error(f"Failed to download mapping file for order {order_id}")
                    return

                # Import cost allocation modules
                from cost_allocation.dynamic_mapping_processor import process_dynamic_mapping_file
                from cost_allocation.matcher import SmartMatcher

                # Process the mapping file to create unified lookup
                mapping_result = process_dynamic_mapping_file(mapping_file_content, order.mapping_file_path)
                if not mapping_result['success']:
                    logger.error(f"Failed to process mapping file: {mapping_result.get('error', 'Unknown error')}")
                    return

                # Create proper lookup map using user-selected mapping keys
                logger.info(f"🔧 Creating unified lookup map...")
                logger.info(f"🔧 Raw mapping_data type: {type(mapping_result.get('mapping_data', 'NOT_FOUND'))}")
                logger.info(f"🔧 Raw mapping_data length: {len(mapping_result.get('mapping_data', []))}")
                logger.info(f"🔧 Order mapping_keys: {order.mapping_keys}")

                from cost_allocation.dynamic_mapping_processor import DynamicMappingProcessor
                processor = DynamicMappingProcessor()
                unified_map = processor.create_lookup_map(mapping_result['mapping_data'], order.mapping_keys or [])

                logger.info(f"🔧 Created unified_map type: {type(unified_map)}")
                logger.info(f"Processed mapping file with {len(unified_map)} entries")

                # Debug unified_map content
                logger.info(f"🔍 DEBUG: unified_map keys (first 10): {list(unified_map.keys())[:10]}")
                logger.info(f"🔍 DEBUG: unified_map sample entries:")
                for i, (key, value) in enumerate(list(unified_map.items())[:5]):
                    logger.info(f"    [{i+1}] key='{key}' -> {value}")

                # Check specifically for service_numbers we expect
                expected_service_numbers = ['52857834', '90171042', '57410267', '57410268']
                for service_number in expected_service_numbers:
                    if service_number in unified_map:
                        logger.info(f"✅ Found expected service_number '{service_number}' in unified_map")
                    else:
                        logger.warning(f"❌ Expected service_number '{service_number}' NOT found in unified_map")

                # Get completed order items with their individual mapping keys
                completed_items = db.query(OcrOrderItem).filter(
                    OcrOrderItem.order_id == order_id,
                    OcrOrderItem.status == OrderItemStatus.COMPLETED,
                    OcrOrderItem.ocr_result_csv_path.isnot(None)
                ).all()

                # Process each item's results with its individual mapping keys
                all_enriched_results = []

                for item in completed_items:
                    try:
                        # Download item's CSV results
                        if not item.ocr_result_csv_path.startswith('s3://'):
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

                        # Add item metadata to all records
                        df['__item_id'] = item.item_id
                        df['__item_name'] = item.item_name
                        df['__company'] = item.company.company_name if item.company else None
                        df['__doc_type'] = item.document_type.type_name if item.document_type else None

                        # Use unified mapping logic (same as re-mapping pipeline)
                        item_mapping_keys = item.mapping_keys or order.mapping_keys or []
                        logger.info(f"🔄 Using _perform_dynamic_join for item {item.item_id} with {len(df)} records")

                        # Convert DataFrame to records format for _perform_dynamic_join
                        ocr_results = df.to_dict('records')

                        # Convert unified_map back to mapping_data format
                        mapping_data = list(unified_map.values())

                        # Get mapping columns from mapping data
                        mapping_columns = mapping_result['columns']

                        joined_results = await self._perform_dynamic_join(
                            ocr_results, mapping_data, mapping_columns, item_mapping_keys, order_id
                        )

                        if joined_results and len(joined_results) > 0:
                            # Convert results back to DataFrame for consistency
                            enriched_df = pd.DataFrame(joined_results)
                            item_records = joined_results  # Already in dict format
                            all_enriched_results.extend(item_records)
                            logger.info(f"✅ Processed {len(item_records)} records from item {item.item_id} using unified pipeline")
                        else:
                            logger.warning(f"⚠️ No enriched results from _perform_dynamic_join for item {item.item_id}")
                            continue

                    except Exception as e:
                        logger.error(f"Error processing item {item.item_id}: {str(e)}")
                        continue

                if not all_enriched_results:
                    logger.error(f"No enriched results generated for order {order_id}")
                    return

                # 🔍 UNIFIED PIPELINE CHECK: Verify unified pipeline results
                logger.info(f"🔍 UNIFIED PIPELINE CHECK: all_enriched_results has {len(all_enriched_results)} records")
                if all_enriched_results:
                    # Collect all mapping keys from order and items
                    all_mapping_keys = set(order.mapping_keys or [])
                    for item in order.items:
                        if item.mapping_keys:
                            all_mapping_keys.update(item.mapping_keys)

                    # Count matched vs unmatched records to verify Matched column preservation
                    matched_count = sum(1 for record in all_enriched_results if record.get('Matched', False))
                    unmatched_count = len(all_enriched_results) - matched_count
                    logger.info(f"🔍 UNIFIED PIPELINE: Matched={matched_count}, Unmatched={unmatched_count}")

                    # Verify Matched column is preserved from _perform_dynamic_join
                    has_matched_column = any('Matched' in record for record in all_enriched_results)
                    logger.info(f"🔍 UNIFIED PIPELINE: Matched column preserved: {has_matched_column}")

                    if has_matched_column:
                        logger.info(f"🔍 ✅ Unified pipeline working - Special CSV will have Matched data for sorting")
                    else:
                        logger.error(f"🔍 ❌ Unified pipeline issue - Matched column missing")

                # Generate final mapped reports using same logic as re-mapping pipeline
                await self._generate_mapped_reports(order_id, all_enriched_results)

                logger.info(f"Successfully completed mapping for order {order_id} with {len(all_enriched_results)} records")

            except Exception as e:
                logger.error(f"Error applying order mapping {order_id}: {str(e)}")
                raise

    def _apply_priority_mapping(self, record: Dict[str, Any], unified_map: Dict[str, Any], mapping_keys: List[str], order_id: int = None, item_id: int = None) -> Dict[str, Any]:
        """Apply priority-based mapping to a single record with auto-derivation support"""
        enriched_record = record.copy()

        # Default values for unmatched records - keep empty for consistency with _perform_dynamic_join
        enriched_record['Department'] = ''
        enriched_record['ShopCode'] = ''
        enriched_record['ServiceType'] = ''
        enriched_record['MatchedBy'] = ''
        enriched_record['MatchSource'] = ''
        enriched_record['Matched'] = False

        # Get document config for auto-derivation
        auto_mapping_enabled = False
        default_mapping_keys = []
        if item_id:
            try:
                with Session(engine) as db:
                    logger.info(f"🔍 Looking up document config for item_id={item_id}")

                    # Get the order item with company and document type info
                    item = db.query(OcrOrderItem).filter(OcrOrderItem.item_id == item_id).first()
                    if not item:
                        logger.error(f"❌ Item {item_id} not found in database")
                        return enriched_record

                    logger.info(f"📋 Item {item_id}: company_id={item.company_id}, doc_type_id={item.doc_type_id}")

                    # Find the CompanyDocumentConfig using company_id and doc_type_id
                    from db.models import CompanyDocumentConfig
                    config = db.query(CompanyDocumentConfig).filter(
                        CompanyDocumentConfig.company_id == item.company_id,
                        CompanyDocumentConfig.doc_type_id == item.doc_type_id,
                        CompanyDocumentConfig.active == True
                    ).first()

                    if config:
                        auto_mapping_enabled = config.auto_mapping_enabled or False
                        default_mapping_keys = config.default_mapping_keys or []
                        logger.info(f"✅ Found document config: auto_mapping_enabled={auto_mapping_enabled}, default_keys={default_mapping_keys}")
                    else:
                        logger.warning(f"⚠️ No active CompanyDocumentConfig found for company_id={item.company_id}, doc_type_id={item.doc_type_id}")

            except Exception as e:
                logger.error(f"❌ Failed to get document config for item {item_id}: {e}")
                import traceback
                logger.error(f"❌ Traceback: {traceback.format_exc()}")
        else:
            logger.warning("⚠️ No item_id provided for document config lookup")

        # Log available OCR fields for debugging
        ocr_fields = list(record.keys())
        logger.info(f"🔍 Available OCR fields: {ocr_fields}")
        logger.info(f"🎯 User mapping keys: {mapping_keys}")
        logger.info(f"🤖 Auto mapping enabled: {auto_mapping_enabled}")
        logger.info(f"📝 Default mapping keys: {default_mapping_keys}")

        # Try matching with priority order (Key 1, Key 2, Key 3)
        for i, mapping_key in enumerate(mapping_keys):
            if not mapping_key:
                logger.warning(f"⚠️ Empty mapping key at position {i+1}")
                continue

            logger.info(f"🔄 Processing mapping key {i+1}: '{mapping_key}'")

            # Auto-derivation logic: user selects mapping_key (PHONE), system uses default_key (service_number)
            key_value = None
            actual_field_used = None

            if auto_mapping_enabled and default_mapping_keys:
                # Auto mapping mode: use default keys to find value, but match against user key
                logger.info(f"🤖 Auto mapping mode: looking for default keys in OCR record")
                for default_key in default_mapping_keys:
                    logger.info(f"    🔍 Checking if '{default_key}' exists in OCR record...")
                    if default_key in record:
                        key_value = record[default_key]
                        actual_field_used = default_key
                        logger.info(f"    ✅ Found! Using OCR[{default_key}]={key_value} for user key '{mapping_key}'")
                        break
                    else:
                        logger.info(f"    ❌ '{default_key}' not found in OCR record")

                if key_value is None:
                    logger.warning(f"⚠️ Auto mapping failed: none of the default keys {default_mapping_keys} found in OCR record")
            else:
                # Manual mapping mode: use mapping key directly
                logger.info(f"👤 Manual mapping mode: looking for user key '{mapping_key}' directly in OCR record")
                if mapping_key in record:
                    key_value = record[mapping_key]
                    actual_field_used = mapping_key
                    logger.info(f"    ✅ Found! Direct mapping: {mapping_key}={key_value}")
                else:
                    logger.info(f"    ❌ '{mapping_key}' not found in OCR record")

            if key_value is None:
                logger.warning(f"⚠️ No value found for mapping key '{mapping_key}' - skipping")
                continue

            if not key_value:
                logger.warning(f"⚠️ Empty value for {actual_field_used}")
                continue

            # Enhanced identifier matching with intelligent extraction
            import re
            logger.info(f"🔍 ENHANCED MATCHING: Starting intelligent identifier extraction for value='{key_value}'")

            # Use MatchingEngine for intelligent identifier extraction
            extracted_identifiers = self.matching_engine.extract_identifiers(str(key_value))
            logger.info(f"🔍 ENHANCED MATCHING: MatchingEngine extracted {len(extracted_identifiers)} identifiers: {extracted_identifiers}")

            # Also keep the legacy normalization for backward compatibility
            legacy_normalized_key = str(key_value).strip()
            legacy_normalized_key = re.sub(r'[^\w]', '', legacy_normalized_key).upper()
            logger.info(f"🔍 ENHANCED MATCHING: Legacy normalized key: '{legacy_normalized_key}'")

            # Try matching in priority order: extracted identifiers first, then legacy
            all_candidates = extracted_identifiers + [legacy_normalized_key]
            logger.info(f"🔍 ENHANCED MATCHING: All matching candidates: {all_candidates}")

            match_data = None
            matched_identifier = None

            for i, candidate in enumerate(all_candidates):
                logger.info(f"🔍 ENHANCED MATCHING: Trying candidate {i+1}/{len(all_candidates)}: '{candidate}'")
                if candidate in unified_map:
                    match_data = unified_map[candidate]
                    matched_identifier = candidate
                    if i < len(extracted_identifiers):
                        logger.info(f"✅ ENHANCED MATCHING: SUCCESS! Matched on extracted identifier '{candidate}' (intelligent extraction)")
                    else:
                        logger.info(f"✅ ENHANCED MATCHING: SUCCESS! Matched on legacy normalized key '{candidate}' (backward compatibility)")
                    break
                else:
                    logger.info(f"❌ ENHANCED MATCHING: Candidate '{candidate}' not found in unified_map")

            if match_data:

                # Apply the matched data - copy ALL mapping file data (not just debug fields)
                logger.info(f"🔄 Copying mapping data to enriched_record: {match_data}")

                # Copy all mapping file data to enriched record
                mapping_fields_copied = []
                for mapping_field, mapping_value in match_data.items():
                    if mapping_field not in ['Source']:  # Skip internal fields
                        enriched_record[mapping_field] = mapping_value
                        mapping_fields_copied.append(f"{mapping_field}={mapping_value}")
                        logger.info(f"   📋 Copied: {mapping_field} = {mapping_value}")

                logger.info(f"🎯 MAPPING COPY COMPLETE: Copied {len(mapping_fields_copied)} fields")
                logger.info(f"🎯 MAPPING FIELDS: {mapping_fields_copied}")

                # Add debug/tracking fields
                enriched_record['Department'] = match_data.get('Department', 'Retail')
                enriched_record['ShopCode'] = match_data.get('ShopCode', '')
                enriched_record['ServiceType'] = match_data.get('ServiceType', 'Unknown')
                enriched_record['MatchedBy'] = f'key_{i+1}_{mapping_key}'
                enriched_record['MatchSource'] = match_data.get('Source', '')
                enriched_record['Matched'] = True
                enriched_record['MatchedValue'] = key_value
                enriched_record['MatchedKey'] = mapping_key
                enriched_record['ActualFieldUsed'] = actual_field_used

                # Log final enriched_record state
                mapping_keys_in_record = [k for k in enriched_record.keys() if k in mapping_keys]
                logger.info(f"🏁 ENRICHED RECORD STATE: total_fields={len(enriched_record)}")
                logger.info(f"🏁 MAPPING KEYS IN RECORD: {mapping_keys_in_record}")
                logger.info(f"🏁 ALL KEYS: {list(enriched_record.keys())[:20]}...")  # Show first 20 keys

                if auto_mapping_enabled and actual_field_used != mapping_key:
                    logger.info(f"✅ ENHANCED MATCHING: Auto mapping success: OCR[{actual_field_used}]={key_value} ↔ User[{mapping_key}] matched on '{matched_identifier}' -> shop {match_data.get('ShopCode', 'Unknown')}")
                else:
                    logger.info(f"✅ ENHANCED MATCHING: Manual mapping success: {mapping_key}={key_value} matched on '{matched_identifier}' -> shop {match_data.get('ShopCode', 'Unknown')}")
                break  # Stop at first successful match (priority order)
            else:
                logger.warning(f"❌ ENHANCED MATCHING: No match found for value '{key_value}' with {len(all_candidates)} candidates: {all_candidates}")

        return enriched_record

    async def _generate_mapped_reports(self, order_id: int, enriched_results: List[Dict[str, Any]]):
        """Generate final mapped reports for the order"""
        try:
            # Get order information to access mapping keys
            with Session(engine) as db:
                order = db.query(OcrOrder).filter(OcrOrder.order_id == order_id).first()

                # Collect all mapping keys from order and items
                all_mapping_keys = set(order.mapping_keys or [])
                for item in order.items:
                    if item.mapping_keys:
                        all_mapping_keys.update(item.mapping_keys)

            s3_base = f"results/orders/{order_id // 1000}/mapped"

            # Generate mapped CSV with business-friendly format (dynamic column detection)
            import pandas as pd

            # Get all available columns from ALL records (critical fix for mapping columns)
            if enriched_results:
                all_columns = set()
                # IMPORTANT: Check ALL records, not just first one, as mapping columns may only exist in some records
                for record in enriched_results:
                    all_columns.update(record.keys())

                # Internal columns to exclude (only filter fields that start with __)
                internal_columns = {col for col in all_columns if col.startswith('__')}

                # Also exclude explicit internal tracking fields (not business data)
                # NOTE: Keep 'Matched' column so Special CSV generator can use it for sorting and computed column logic
                explicit_internal_fields = {
                    'MatchedBy', 'MatchSource', 'MatchedValue', 'MatchedKey', 'ActualFieldUsed'
                }

                # Combined internal columns to exclude
                debug_columns = internal_columns.union(explicit_internal_fields)

                # Check for mapping columns specifically
                mapping_cols_found = [col for col in all_columns if col in all_mapping_keys]

                # Filter out debug columns to get business columns
                business_columns = [col for col in all_columns if col not in debug_columns]

                # CRITICAL FIX: Ensure mapping columns are ALWAYS included even if they appear in few records
                for mapping_col in all_mapping_keys:
                    if mapping_col in all_columns and mapping_col not in business_columns:
                        business_columns.append(mapping_col)
                        logger.info(f"📊 FORCE-ADDED missing mapping column: {mapping_col}")

                business_columns.sort()  # Sort for consistent order

                logger.info(f"📊 REPORT GENERATION DEBUG:")
                logger.info(f"📊 Total enriched_results records: {len(enriched_results)}")
                logger.info(f"📊 All columns in enriched_results: {sorted(all_columns)}")
                logger.info(f"📊 All mapping keys: {sorted(all_mapping_keys)}")
                logger.info(f"📊 Mapping columns found: {mapping_cols_found}")
                logger.info(f"📊 Filtered internal columns (dynamic detection): {sorted(debug_columns & all_columns)}")
                logger.info(f"📊 Business columns (FIXED - no hardcoded assumptions): {business_columns}")
                logger.info(f"📊 Business columns include Department, ShopCode, ServiceType: {[col for col in ['Department', 'ShopCode', 'ServiceType'] if col in business_columns]}")
                logger.info(f"📊 GUARANTEED MAPPING COLUMNS IN CSV: {[col for col in business_columns if col in all_mapping_keys]}")

                # 🔍 NEW: Check if Matched column is preserved for Special CSV generator
                has_matched_column = 'Matched' in business_columns
                logger.info(f"🔍 MATCHED COLUMN TRACKING:")
                logger.info(f"🔍 'Matched' column in all_columns: {'Matched' in all_columns}")
                logger.info(f"🔍 'Matched' column in business_columns: {has_matched_column}")
                logger.info(f"🔍 'Matched' column excluded from internal fields: {'Matched' not in explicit_internal_fields}")

                if has_matched_column:
                    # Count matched vs unmatched records for verification
                    matched_count = sum(1 for record in enriched_results if record.get('Matched', False))
                    unmatched_count = len(enriched_results) - matched_count
                    logger.info(f"🔍 Matched records: {matched_count}, Unmatched records: {unmatched_count}")
                    logger.info(f"🔍 ✅ Matched column preserved - Special CSV generator can sort and compute columns correctly")
                else:
                    logger.warning(f"🔍 ❌ Matched column NOT preserved - Special CSV generator will not have Matched data for sorting")

                # Sample records to check mapping data (check first, middle, last)
                sample_indices = [0, len(enriched_results)//2, -1] if len(enriched_results) > 1 else [0]
                for idx in sample_indices:
                    if idx < len(enriched_results):
                        record = enriched_results[idx]
                        mapping_sample = {k:v for k,v in record.items() if k in all_mapping_keys}
                        position = "FIRST" if idx == 0 else "MIDDLE" if idx == len(enriched_results)//2 else "LAST"
                        logger.info(f"📊 {position} record ({idx}) mapping fields: {mapping_sample}")

                # Count enriched_results records with mapping data
                report_records_with_mapping = sum(1 for record in enriched_results
                                                if any(k in record for k in all_mapping_keys))
                logger.info(f"📊 REPORT LEVEL: {report_records_with_mapping} out of {len(enriched_results)} records have mapping fields")
            else:
                # Initialize empty variables when no enriched_results
                all_columns = set()
                internal_columns = set()
                debug_columns = set()
                business_columns = []
                mapping_cols_found = []
                logger.warning("📊 No enriched_results to extract columns from")

            # Create business-friendly records with only business columns
            business_results = []
            for record in enriched_results:
                business_record = {}
                for col in business_columns:
                    business_record[col] = record.get(col, '')
                business_results.append(business_record)

            logger.info(f"📊 Generating business CSV with {len(business_results)} records")
            logger.info(f"📊 Final column count: {len(business_columns)}")

            df = pd.DataFrame(business_results)
            template_details = self._get_order_template_details(order_id)
            special_csv_path = None

            if template_details:
                try:
                    logger.info(f"🎯 Starting Special CSV generation for order {order_id}")
                    logger.info(f"   Template: {template_details.get('template_path', 'N/A')}")
                    logger.info(f"   DataFrame shape: {df.shape}")
                    logger.info(f"   DataFrame columns: {list(df.columns)}")

                    special_csv_path = self._generate_special_csv_from_template(
                        order_id,
                        df,
                        template_details["template_path"],
                        template_details.get("doc_type_name", ""),
                        s3_base,
                    )

                    if special_csv_path:
                        logger.info(f"✅ Successfully generated Special CSV for order {order_id}: {special_csv_path}")
                    else:
                        logger.warning(f"⚠️ Special CSV generation returned None for order {order_id}")

                except Exception as special_csv_error:
                    logger.error(f"❌ Error generating Special CSV for order {order_id}: {str(special_csv_error)}")
                    special_csv_path = None
            else:
                logger.info(
                    "📋 Order %s has no template configured; skipping special CSV",
                    order_id,
                )

            # Create CSV content with Excel formula escaping
            try:
                # Apply formula escaping to prevent Excel #NAME? errors
                escaped_df = df.copy()
                for column in escaped_df.columns:
                    escaped_df[column] = escaped_df[column].apply(escape_excel_formulas)

                csv_content = escaped_df.to_csv(index=False)
                csv_s3_key = f"{s3_base}/order_{order_id}_mapped.csv"
                csv_upload_success = self.s3_manager.upload_file(csv_content.encode('utf-8'), csv_s3_key)

                if csv_upload_success:
                    logger.info(f"✅ Successfully uploaded mapped CSV for order {order_id} to {csv_s3_key}")
                else:
                    logger.error(f"❌ Failed to upload mapped CSV for order {order_id} to {csv_s3_key}")

            except Exception as csv_error:
                logger.error(f"❌ Error generating/uploading CSV for order {order_id}: {str(csv_error)}")
                csv_upload_success = False
                csv_s3_key = None

            # Excel generation skipped - only CSV and Special CSV needed
            excel_path = None
            logger.info(f"📋 Excel generation skipped for order {order_id} - only CSV and Special CSV required")

            # Update order with mapped report paths
            with Session(engine) as db:
                order = db.query(OcrOrder).filter(OcrOrder.order_id == order_id).first()
                if order:
                    logger.info(f"🔍 BEFORE mapping update - Order {order_id} final_report_paths: {order.final_report_paths}")

                    current_paths = order.final_report_paths or {}
                    # Fix path construction - csv_s3_key already contains the correct path
                    csv_full_path = f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{csv_s3_key}" if csv_upload_success else None

                    logger.info(f"🔍 S3 Path Construction Debug:")
                    logger.info(f"   bucket_name: {self.s3_manager.bucket_name}")
                    logger.info(f"   upload_prefix: {self.s3_manager.upload_prefix}")
                    logger.info(f"   csv_s3_key: {csv_s3_key}")
                    logger.info(f"   final csv_full_path: {csv_full_path}")
                    logger.info(f"   special_csv_path: {special_csv_path}")

                    path_updates = {
                        'mapped_csv': csv_full_path
                    }
                    if special_csv_path:
                        path_updates['special_csv'] = special_csv_path

                    current_paths.update(path_updates)
                    order.final_report_paths = current_paths

                    # Force SQLAlchemy to detect JSONB field changes
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(order, 'final_report_paths')

                    logger.info(f"🔍 AFTER mapping update - final_report_paths: {current_paths}")

                    try:
                        db.commit()
                        logger.info(f"✅ Successfully committed mapping paths for order {order_id}")

                        # Verify the commit worked by re-querying
                        db.refresh(order)
                        logger.info(f"🔍 POST-COMMIT verification - final_report_paths: {order.final_report_paths}")

                    except Exception as commit_error:
                        logger.error(f"❌ Failed to commit database changes for order {order_id}: {str(commit_error)}")
                        db.rollback()
                        raise
                else:
                    logger.error(f"❌ Order {order_id} not found in database for final_report_paths update")

            logger.info(f"Generated mapped reports for order {order_id}")

        except Exception as e:
            logger.error(f"Error generating mapped reports for order {order_id}: {str(e)}")
            raise

# Global order processor instance
order_processor = OrderProcessor()

async def start_order_processing(order_id: int):
    """Start processing an order in the background"""
    await order_processor.process_order(order_id)

async def start_order_ocr_only_processing(order_id: int):
    """Start OCR-only processing (no mapping) for an order in the background"""
    await order_processor.process_order_ocr_only(order_id)

async def start_order_mapping_only_processing(order_id: int):
    """Start mapping-only processing for an order that already has OCR results"""
    await order_processor.process_order_mapping_only(order_id)
