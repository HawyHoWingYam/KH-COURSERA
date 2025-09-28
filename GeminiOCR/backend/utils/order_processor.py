"""
Order Processing Pipeline
Handles the complete OCR Order workflow from submission to completion
"""

import asyncio
import json
import os
import tempfile
import zipfile
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
import pandas as pd

from sqlalchemy.orm import Session, sessionmaker

from db.database import engine
from db.models import (
    OcrOrder, OcrOrderItem, OrderItemFile, OrderStatus, OrderItemStatus,
    Company, DocumentType, CompanyDocumentConfig, File, ApiUsage
)
from main import extract_text_from_image, extract_text_from_pdf
from utils.s3_storage import get_s3_manager
from utils.prompt_schema_manager import get_prompt_schema_manager
from utils.excel_converter import json_to_excel, json_to_csv
from config_loader import config_loader

logger = logging.getLogger(__name__)

class OrderProcessor:
    """Main coordinator for OCR Order processing"""

    def __init__(self):
        self.s3_manager = get_s3_manager()
        self.prompt_schema_manager = get_prompt_schema_manager()
        self.app_config = config_loader.get_app_config()

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
                                    all_results.append(business_data)
                                except json.JSONDecodeError:
                                    all_results.append({
                                        "text": text_content,
                                        "__filename": file_record.file_name
                                    })
                            else:
                                all_results.append({
                                    "__filename": file_record.file_name,
                                    "__error": "No text content in result"
                                })

                    except Exception as e:
                        logger.error(f"Error processing file {file_record.file_name}: {str(e)}")
                        all_results.append({
                            "__filename": file_record.file_name,
                            "__error": f"Processing failed: {str(e)}"
                        })

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

    async def _save_item_results(self, item_id: int, company_code: str, doc_type_code: str, results: List[Dict[str, Any]]):
        """Save individual item results to S3"""
        try:
            # Generate S3 paths for item results
            s3_base = f"results/orders/{item_id // 1000}/items/{item_id}"

            # Save JSON results
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

            logger.info(f"Item {item_id} results saved to S3")

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
                    report_paths = {
                        'consolidated_json': f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{json_s3_key}" if json_upload_success else None,
                        'consolidated_excel': excel_path,
                        'consolidated_csv': csv_path
                    }
                    order.final_report_paths = report_paths
                    db.commit()

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

                if order.status != OrderStatus.MAPPING:
                    logger.warning(f"Order {order_id} is not in MAPPING status")
                    return

                logger.info(f"Starting dynamic mapping processing for order {order_id}")

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
                mapping_result = process_dynamic_mapping_file(mapping_content)

                if not mapping_result['success']:
                    logger.error(f"Failed to process mapping file: {mapping_result.get('error', 'Unknown error')}")
                    return

                mapping_data = mapping_result['mapping_data']
                mapping_columns = mapping_result['columns']
                logger.info(f"Loaded {len(mapping_data)} mapping records with columns: {mapping_columns}")

                # Get user-selected mapping keys
                user_mapping_keys = order.mapping_keys or []
                if not user_mapping_keys:
                    logger.error(f"No mapping keys configured for order {order_id}")
                    return

                logger.info(f"Using user-selected mapping keys: {user_mapping_keys}")

                # Perform dynamic JOIN operation
                joined_results = await self._perform_dynamic_join(
                    all_ocr_results, mapping_data, mapping_columns, user_mapping_keys
                )

                logger.info(f"JOIN completed: {len(joined_results)} records processed")

                # Generate final CSV with proper format
                if joined_results:
                    csv_content = self._generate_mapped_csv(joined_results, mapping_columns)

                    # Save final results to S3
                    final_key = f"upload/results/orders/{order_id}/final_mapped_results.csv"
                    success = self.s3_manager.upload_file(csv_content.encode('utf-8'), final_key)

                    if success:
                        logger.info(f"Final mapped results saved to S3: {final_key}")

                        # Update order status to COMPLETED and set final_report_paths
                        order.status = OrderStatus.COMPLETED
                        order.updated_at = datetime.utcnow()

                        # Update final_report_paths with the CSV path
                        csv_path = f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{final_key}"
                        current_paths = order.final_report_paths or {}
                        current_paths['mapped_csv'] = csv_path
                        order.final_report_paths = current_paths

                        db.commit()

                        logger.info(f"Order {order_id} mapping processing completed successfully with final_report_paths updated")
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
                                   mapping_columns: List[str], user_mapping_keys: List[str]) -> List[Dict]:
        """Perform dynamic JOIN based on user-selected mapping keys"""

        # Create OCR field to mapping field mapping
        ocr_to_mapping_map = {
            'number': 'PHONE',  # Default mapping
            'account_number': 'ACCOUNT_NO',
        }

        # Create lookup dictionary from mapping data
        mapping_lookup = {}

        for mapping_row in mapping_data:
            # Create composite lookup key using user-selected mapping keys
            lookup_keys = []

            for mapping_key in user_mapping_keys:
                if mapping_key in mapping_row and pd.notna(mapping_row[mapping_key]):
                    # Normalize the lookup key
                    normalized_key = self._normalize_identifier(str(mapping_row[mapping_key]))
                    if normalized_key:
                        lookup_keys.append(normalized_key)

            # Use first available key as primary lookup
            if lookup_keys:
                primary_key = lookup_keys[0]
                mapping_lookup[primary_key] = mapping_row.copy()

        logger.info(f"Created mapping lookup with {len(mapping_lookup)} entries")

        # Perform JOIN operation
        joined_results = []
        matched_count = 0

        for ocr_row in ocr_results:
            # Try to find matching record using user-selected mapping keys
            mapping_match = None

            for mapping_key in user_mapping_keys:
                # Find corresponding OCR field
                ocr_field = None
                for ocr_field_name, map_field_name in ocr_to_mapping_map.items():
                    if map_field_name == mapping_key:
                        ocr_field = ocr_field_name
                        break

                if not ocr_field:
                    # If no explicit mapping, try lowercase version
                    ocr_field = mapping_key.lower()

                # Get value from OCR record
                if ocr_field in ocr_row and pd.notna(ocr_row[ocr_field]):
                    lookup_value = self._normalize_identifier(str(ocr_row[ocr_field]))
                    mapping_match = mapping_lookup.get(lookup_value)
                    if mapping_match:
                        matched_count += 1
                        break

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

            joined_results.append(joined_row)

        logger.info(f"JOIN operation completed: {matched_count} matched out of {len(ocr_results)} total records")
        return joined_results

    def _normalize_identifier(self, identifier: str) -> str:
        """Normalize identifier for consistent matching"""
        import re

        if not identifier or pd.isna(identifier):
            return ""

        # Convert to string and remove spaces, special characters
        normalized = str(identifier).strip()
        normalized = re.sub(r'[^\w]', '', normalized)
        return normalized.upper()

    def _generate_mapped_csv(self, joined_results: List[Dict], mapping_columns: List[str]) -> str:
        """Generate CSV content with proper column ordering"""
        if not joined_results:
            return ""

        # Get all unique columns
        all_columns = set()
        for row in joined_results:
            all_columns.update(row.keys())

        # Order columns: mapping columns first, then OCR columns
        ocr_columns = [col for col in all_columns if col not in mapping_columns and not col.startswith('__')]
        ordered_columns = mapping_columns + ocr_columns

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
        return csv_buffer.getvalue()

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
                from cost_allocation.mapping_processor import process_mapping_file
                from cost_allocation.matcher import SmartMatcher

                # Process the mapping file to create unified lookup
                mapping_result = process_mapping_file(mapping_file_content)
                if not mapping_result['success']:
                    logger.error(f"Failed to process mapping file: {mapping_result.get('error', 'Unknown error')}")
                    return

                unified_map = mapping_result['unified_map']
                logger.info(f"Processed mapping file with {len(unified_map)} entries")

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
                        item_records = df.to_dict('records')

                        # Apply item-specific mapping with priority-based matching
                        item_mapping_keys = item.mapping_keys or order.mapping_keys or []

                        for record in item_records:
                            # Add item metadata
                            record['__item_id'] = item.item_id
                            record['__item_name'] = item.item_name
                            record['__company'] = item.company.company_name if item.company else None
                            record['__doc_type'] = item.document_type.type_name if item.document_type else None

                            # Apply mapping with priority order
                            enriched_record = self._apply_priority_mapping(
                                record, unified_map, item_mapping_keys
                            )
                            all_enriched_results.append(enriched_record)

                        logger.info(f"Processed {len(item_records)} records from item {item.item_id}")

                    except Exception as e:
                        logger.error(f"Error processing item {item.item_id}: {str(e)}")
                        continue

                if not all_enriched_results:
                    logger.error(f"No enriched results generated for order {order_id}")
                    return

                # Generate final mapped reports
                await self._generate_mapped_reports(order_id, all_enriched_results)

                logger.info(f"Successfully completed mapping for order {order_id} with {len(all_enriched_results)} records")

            except Exception as e:
                logger.error(f"Error applying order mapping {order_id}: {str(e)}")
                raise

    def _apply_priority_mapping(self, record: Dict[str, Any], unified_map: Dict[str, Any], mapping_keys: List[str]) -> Dict[str, Any]:
        """Apply priority-based mapping to a single record"""
        enriched_record = record.copy()

        # Default values for unmatched records
        enriched_record['Department'] = 'Unallocated'
        enriched_record['ShopCode'] = 'UNMATCHED'
        enriched_record['ServiceType'] = 'Unknown'
        enriched_record['MatchedBy'] = 'unmatched'
        enriched_record['MatchSource'] = ''
        enriched_record['Matched'] = False

        # Try matching with priority order (Key 1, Key 2, Key 3)
        for i, mapping_key in enumerate(mapping_keys):
            if not mapping_key or mapping_key not in record:
                continue

            # Get the value from the record for this mapping key
            key_value = record[mapping_key]
            if not key_value:
                continue

            # Normalize the identifier for matching
            import re
            normalized_key = str(key_value).strip()
            normalized_key = re.sub(r'[^\w]', '', normalized_key).upper()

            if normalized_key in unified_map:
                match_data = unified_map[normalized_key]

                # Apply the matched data
                enriched_record['Department'] = match_data.get('Department', 'Retail')
                enriched_record['ShopCode'] = match_data.get('ShopCode', '')
                enriched_record['ServiceType'] = match_data.get('ServiceType', 'Unknown')
                enriched_record['MatchedBy'] = f'key_{i+1}_{mapping_key}'
                enriched_record['MatchSource'] = match_data.get('Source', '')
                enriched_record['Matched'] = True
                enriched_record['MatchedValue'] = key_value
                enriched_record['MatchedKey'] = mapping_key

                logger.debug(f"Matched record using key {i+1} ({mapping_key}={key_value}) to shop {match_data.get('ShopCode', 'Unknown')}")
                break  # Stop at first successful match (priority order)

        return enriched_record

    async def _generate_mapped_reports(self, order_id: int, enriched_results: List[Dict[str, Any]]):
        """Generate final mapped reports for the order"""
        try:
            s3_base = f"results/orders/{order_id // 1000}/mapped"

            # Generate mapped CSV
            import pandas as pd
            df = pd.DataFrame(enriched_results)

            # Create CSV content
            csv_content = df.to_csv(index=False)
            csv_s3_key = f"{s3_base}/order_{order_id}_mapped.csv"
            csv_upload_success = self.s3_manager.upload_file(csv_content.encode('utf-8'), csv_s3_key)

            # Generate Excel report with multiple sheets
            excel_path = None
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_excel:
                temp_excel_path = temp_excel.name

            try:
                # Create Excel with multiple sheets
                with pd.ExcelWriter(temp_excel_path, engine='openpyxl') as writer:
                    # Main results sheet
                    df.to_excel(writer, sheet_name='Mapped Results', index=False)

                    # Matched vs Unmatched analysis
                    matched_df = df[df['Matched'] == True]
                    unmatched_df = df[df['Matched'] == False]

                    matched_df.to_excel(writer, sheet_name='Matched Records', index=False)
                    unmatched_df.to_excel(writer, sheet_name='Unmatched Records', index=False)

                    # Summary sheet
                    summary_data = {
                        'Total Records': len(enriched_results),
                        'Matched Records': len(matched_df),
                        'Unmatched Records': len(unmatched_df),
                        'Match Rate': f"{(len(matched_df) / len(enriched_results) * 100):.1f}%" if enriched_results else "0%"
                    }
                    summary_df = pd.DataFrame(list(summary_data.items()), columns=['Metric', 'Value'])
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)

                # Upload Excel file
                with open(temp_excel_path, 'rb') as excel_file:
                    excel_content = excel_file.read()
                    excel_s3_key = f"{s3_base}/order_{order_id}_mapped.xlsx"
                    excel_upload_success = self.s3_manager.upload_file(excel_content, excel_s3_key)

                    if excel_upload_success:
                        excel_path = f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{excel_s3_key}"

            finally:
                os.unlink(temp_excel_path)

            # Update order with mapped report paths
            with Session(engine) as db:
                order = db.query(OcrOrder).filter(OcrOrder.order_id == order_id).first()
                if order:
                    current_paths = order.final_report_paths or {}
                    current_paths.update({
                        'mapped_csv': f"s3://{self.s3_manager.bucket_name}/{self.s3_manager.upload_prefix}{csv_s3_key}" if csv_upload_success else None,
                        'mapped_excel': excel_path
                    })
                    order.final_report_paths = current_paths
                    db.commit()

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