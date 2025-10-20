"""AWB (Air Waybill) Monthly Processing - OCR + 3-layer matching"""
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from io import BytesIO

import pandas as pd
from difflib import SequenceMatcher

from utils.s3_storage import S3StorageManager
from utils.excel_converter import json_to_excel, json_to_csv
from main import extract_text_from_pdf
from db.models import File, BatchJob, Company
from config_loader import config_loader

logger = logging.getLogger(__name__)


class AWBProcessor:
    """Process AWB files with 3-layer matching (cost, person, department)"""

    def __init__(self):
        self.s3_manager = S3StorageManager()
        self.fuzzy_threshold = 0.85  # Similarity threshold for fuzzy matching

    def process_monthly_awb(
        self,
        company_id: int,
        month: str,  # YYYY-MM format
        summary_pdf_path: str,  # S3 path
        employees_csv_path: str,  # S3 path
        db_session
    ) -> Tuple[bool, Optional[Dict], str]:
        """Process monthly AWB files

        Args:
            company_id: Company ID
            month: Month in YYYY-MM format
            summary_pdf_path: S3 path to summary PDF
            employees_csv_path: S3 path to employees CSV
            db_session: Database session

        Returns:
            Tuple of (success, output_data, error_message)
        """
        try:
            logger.info(f"🔄 Starting AWB monthly processing for {month}")

            # Parse month
            try:
                year, month_num = month.split('-')
                year = int(year)
                month_num = int(month_num)
            except (ValueError, IndexError):
                return False, None, f"Invalid month format. Use YYYY-MM"

            # Download and OCR summary PDF
            logger.info("📄 OCRing summary PDF...")
            summary_results = self._ocr_file(summary_pdf_path, 'AWB_SUMMARY')
            if not summary_results:
                return False, None, "Failed to OCR summary PDF"

            # Download employees CSV
            logger.info("👥 Loading employee mapping...")
            employee_map = self._load_employee_csv(employees_csv_path)
            if employee_map is None:
                return False, None, "Failed to load employee CSV"

            # List AWB PDFs from S3 by month
            logger.info(f"📂 Listing AWB files for {year}/{month_num:02d}...")
            awb_files = self._list_awb_files(year, month_num)
            if not awb_files:
                return False, None, f"No AWB files found for {month}"

            logger.info(f"✅ Found {len(awb_files)} AWB files")

            # OCR all AWB detail files
            logger.info("🔍 OCRing AWB detail files...")
            detail_results = []
            for file_path in awb_files:
                result = self._ocr_file(file_path, 'AWB_DETAIL')
                if result:
                    detail_results.extend(result)

            # Three-layer matching
            logger.info("🔗 Running 3-layer matching...")
            enriched_records = self._three_layer_matching(
                summary_results,
                detail_results,
                employee_map,
                awb_files
            )

            if not enriched_records:
                return False, None, "No records after matching"

            # Generate outputs
            logger.info("📊 Generating outputs...")
            output_data = {
                'records': enriched_records,
                'matched_count': sum(1 for r in enriched_records if r.get('department_matched')),
                'unmatched_count': sum(1 for r in enriched_records if not r.get('department_matched')),
                'total_count': len(enriched_records),
            }

            logger.info(f"✅ AWB processing completed: {output_data['matched_count']} matched, {output_data['unmatched_count']} unmatched")
            return True, output_data, None

        except Exception as e:
            logger.error(f"❌ AWB processing failed: {str(e)}")
            return False, None, str(e)

    def _ocr_file(self, s3_path: str, doc_type: str) -> Optional[List[Dict]]:
        """OCR a file and extract structured data

        Args:
            s3_path: S3 path to file
            doc_type: Document type (AWB_SUMMARY or AWB_DETAIL)

        Returns:
            List of extracted records or None on error
        """
        try:
            # Download file from S3
            file_obj = self.s3_manager.get_file_as_bytes(s3_path)
            if not file_obj:
                logger.warning(f"⚠️  Could not download {s3_path}")
                return None

            # Extract text
            if s3_path.lower().endswith('.pdf'):
                # For demonstration - in production, would call actual OCR
                text = self._extract_pdf_text(file_obj)
            else:
                logger.warning(f"⚠️  Unsupported file format: {s3_path}")
                return None

            # Parse extracted text (simplified - in production use prompt/schema)
            if doc_type == 'AWB_SUMMARY':
                return self._parse_awb_summary(text)
            elif doc_type == 'AWB_DETAIL':
                return self._parse_awb_detail(text)

        except Exception as e:
            logger.error(f"❌ Error OCRing {s3_path}: {str(e)}")
            return None

    def _extract_pdf_text(self, file_obj: BytesIO) -> str:
        """Extract text from PDF"""
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(file_obj)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            return text
        except Exception as e:
            logger.error(f"❌ PDF extraction failed: {str(e)}")
            return ""

    def _parse_awb_summary(self, text: str) -> List[Dict]:
        """Parse AWB summary text to extract order_number and charge

        Returns list of: [{"order_number": str, "charge": float}]
        """
        # Simplified parsing - in production use Gemini API with prompt/schema
        records = []
        logger.info("📋 Parsing AWB summary...")
        return records

    def _parse_awb_detail(self, text: str) -> List[Dict]:
        """Parse AWB detail text to extract order_number and colleague_name

        Returns list of: [{"order_number": str, "colleague_name": str}]
        """
        # Simplified parsing - in production use Gemini API with prompt/schema
        records = []
        logger.info("📋 Parsing AWB detail...")
        return records

    def _load_employee_csv(self, s3_path: str) -> Optional[Dict[str, str]]:
        """Load employee CSV and return {name: department} mapping"""
        try:
            # Download and read CSV
            file_obj = self.s3_manager.get_file_as_bytes(s3_path)
            if not file_obj:
                return None

            df = pd.read_csv(file_obj)

            # Expected columns: 'name', 'department'
            if 'name' not in df.columns or 'department' not in df.columns:
                logger.warning(f"⚠️  CSV missing required columns (name, department)")
                return None

            # Build mapping
            employee_map = dict(zip(df['name'], df['department']))
            logger.info(f"✅ Loaded {len(employee_map)} employees")
            return employee_map

        except Exception as e:
            logger.error(f"❌ Error loading employee CSV: {str(e)}")
            return None

    def _list_awb_files(self, year: int, month: int) -> List[str]:
        """List AWB PDF files from S3 for given month"""
        try:
            prefix = f"upload/onedrive/airway-bills/{year:04d}/{month:02d}/"
            files = self.s3_manager.list_files(prefix=prefix, extension='.pdf')
            return files

        except Exception as e:
            logger.error(f"❌ Error listing files: {str(e)}")
            return []

    def _three_layer_matching(
        self,
        summary_results: List[Dict],
        detail_results: List[Dict],
        employee_map: Dict[str, str],
        awb_file_paths: List[str]
    ) -> List[Dict]:
        """Perform 3-layer matching: cost, person, department

        Layer 1: Join by order_number (summary ↔ detail)
        Layer 2: Extract colleague name from detail
        Layer 3: Match department from CSV (exact, then fuzzy)
        """
        enriched_records = []

        try:
            # Create summary lookup
            summary_map = {item.get('order_number'): item.get('charge') for item in summary_results}

            for detail in detail_results:
                order_num = detail.get('order_number')
                colleague = detail.get('colleague_name', '')

                # Layer 1: Cost matching
                cost_matched = order_num in summary_map
                cost = summary_map.get(order_num)

                # Layer 2: Person extraction (already done)
                # Layer 3: Department matching
                department, dept_matched, confidence, matched_name = self._match_department(
                    colleague,
                    employee_map
                )

                enriched_record = {
                    'order_number': order_num,
                    'cost': cost,
                    'cost_matched': cost_matched,
                    'colleague': colleague,
                    'department': department,
                    'department_matched': dept_matched,
                    'match_confidence': confidence,
                    'matched_employee_name': matched_name if matched_name != colleague else None,
                }

                enriched_records.append(enriched_record)

            return enriched_records

        except Exception as e:
            logger.error(f"❌ Error in 3-layer matching: {str(e)}")
            return []

    def _match_department(
        self,
        colleague_name: str,
        employee_map: Dict[str, str]
    ) -> Tuple[Optional[str], bool, float, Optional[str]]:
        """Match colleague name to department

        Returns: (department, matched, confidence_score, matched_name)
        """
        if not colleague_name or not employee_map:
            return None, False, 0.0, None

        # Exact match
        if colleague_name in employee_map:
            return employee_map[colleague_name], True, 1.0, colleague_name

        # Fuzzy match
        best_match = None
        best_score = 0.0

        for emp_name in employee_map.keys():
            similarity = SequenceMatcher(None, colleague_name.lower(), emp_name.lower()).ratio()

            if similarity > best_score:
                best_score = similarity
                best_match = emp_name

        if best_score >= self.fuzzy_threshold and best_match:
            return employee_map[best_match], True, best_score, best_match

        # No match
        return None, False, 0.0, None

    def generate_outputs(
        self,
        enriched_records: List[Dict],
        month: str
    ) -> Dict[str, str]:
        """Generate JSON, Excel, CSV outputs

        Returns: {"json_path": ..., "excel_path": ..., "csv_path": ...}
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            prefix = f"results/awb/monthly/{month}"

            outputs = {}

            # JSON
            json_key = f"{prefix}/enriched_{timestamp}.json"
            import json
            json_data = json.dumps(enriched_records, indent=2)
            self.s3_manager.put_object(json_key, json_data)
            outputs['json_path'] = json_key
            logger.info(f"✅ JSON output: {json_key}")

            # Excel
            excel_key = f"{prefix}/enriched_{timestamp}.xlsx"
            excel_bytes = json_to_excel(enriched_records)
            self.s3_manager.put_object(excel_key, excel_bytes, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            outputs['excel_path'] = excel_key
            logger.info(f"✅ Excel output: {excel_key}")

            # CSV
            csv_key = f"{prefix}/enriched_{timestamp}.csv"
            csv_bytes = json_to_csv(enriched_records)
            self.s3_manager.put_object(csv_key, csv_bytes, content_type='text/csv')
            outputs['csv_path'] = csv_key
            logger.info(f"✅ CSV output: {csv_key}")

            return outputs

        except Exception as e:
            logger.error(f"❌ Error generating outputs: {str(e)}")
            return {}
