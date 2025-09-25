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

    async def _apply_order_mapping(self, order_id: int, results: List[Dict[str, Any]]):
        """Apply mapping rules to consolidated order results"""
        # TODO: Implement mapping logic similar to batch processing
        # This would use the mapping file and keys from the order
        # to enrich the consolidated results with business data
        logger.info(f"Mapping application for order {order_id} - TODO: Implement")
        pass

# Global order processor instance
order_processor = OrderProcessor()

async def start_order_processing(order_id: int):
    """Start processing an order in the background"""
    await order_processor.process_order(order_id)