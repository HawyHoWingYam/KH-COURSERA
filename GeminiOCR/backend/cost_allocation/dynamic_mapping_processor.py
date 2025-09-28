"""
Dynamic CSV mapping file processor for flexible column mapping.
Supports any CSV structure based on user-selected mapping keys.
"""

import pandas as pd
import logging
from typing import Dict, Optional, Union, Any, List
from io import BytesIO, StringIO
import re

logger = logging.getLogger(__name__)


class DynamicMappingProcessor:
    """Processes CSV mapping files with dynamic column detection and user-defined mapping keys."""

    def __init__(self):
        self.mapping_data = []
        self.columns = []
        self.ocr_to_mapping_field_map = {
            # Default mappings - can be extended
            'number': 'PHONE',
            'account_number': 'ACCOUNT_NO',
            'customer_reference': 'REFERENCE',
            'account_no': 'ACCOUNT_NO'
        }

    def detect_file_format(self, file_content: bytes, file_path: Optional[str] = None) -> str:
        """
        Detect if file is CSV or Excel format.

        Args:
            file_content: Raw bytes content of the file
            file_path: Optional file path for extension-based detection

        Returns:
            'csv', 'excel', or 'unknown'
        """
        # First, try to determine format from file extension if available
        if file_path:
            file_extension = file_path.lower().split('.')[-1] if '.' in file_path else ''
            logger.info(f"File extension detected: '{file_extension}' from path: {file_path}")

            if file_extension == 'csv':
                # Verify it's actually a valid CSV
                try:
                    pd.read_csv(StringIO(file_content.decode('utf-8')), nrows=1)
                    logger.info("File extension and content both indicate CSV format")
                    return 'csv'
                except Exception as e:
                    logger.warning(f"File has .csv extension but CSV parsing failed: {e}")
                    # Continue to content-based detection
            elif file_extension in ['xlsx', 'xls']:
                # Verify it's actually a valid Excel file
                try:
                    pd.read_excel(BytesIO(file_content), nrows=1)
                    logger.info("File extension and content both indicate Excel format")
                    return 'excel'
                except Exception as e:
                    logger.warning(f"File has Excel extension but Excel parsing failed: {e}")
                    # Continue to content-based detection

        # Fallback to content-based detection
        logger.info("Performing content-based format detection...")

        # Try CSV first (more reliable detection)
        try:
            pd.read_csv(StringIO(file_content.decode('utf-8')), nrows=1)
            logger.info("Content-based detection indicates CSV format")
            return 'csv'
        except Exception as csv_error:
            logger.debug(f"CSV detection failed: {csv_error}")

            # Try Excel as fallback
            try:
                pd.read_excel(BytesIO(file_content), nrows=1)
                logger.info("Content-based detection indicates Excel format")
                return 'excel'
            except Exception as excel_error:
                logger.error(f"Both CSV and Excel detection failed. CSV error: {csv_error}, Excel error: {excel_error}")
                return 'unknown'

    def process_csv_file(self, file_content: bytes) -> Dict[str, Any]:
        """
        Process CSV file content and return mapping data with all columns.

        Args:
            file_content: Raw bytes content of CSV file

        Returns:
            Dict containing mapping data and metadata
        """
        try:
            # Read CSV file
            csv_string = file_content.decode('utf-8')
            df = pd.read_csv(StringIO(csv_string))

            if df.empty:
                return {
                    "success": False,
                    "error": "CSV file is empty"
                }

            # Store column information
            self.columns = list(df.columns)
            logger.info(f"Detected CSV columns: {self.columns}")

            # Convert to list of dictionaries, preserving all columns
            self.mapping_data = df.to_dict('records')

            # Clean the data - remove rows where all values are NaN
            cleaned_data = []
            for row in self.mapping_data:
                if any(pd.notna(value) and str(value).strip() for value in row.values()):
                    cleaned_data.append(row)

            self.mapping_data = cleaned_data

            result = {
                "success": True,
                "mapping_data": self.mapping_data,
                "columns": self.columns,
                "total_rows": len(self.mapping_data),
                "original_rows": len(df),
                "file_format": "csv",
                # Backward compatibility fields
                "unified_map": self.mapping_data,
                "total_mappings": len(self.mapping_data)
            }

            logger.info(f"Successfully processed CSV with {len(self.mapping_data)} valid rows and columns: {self.columns}")
            return result

        except Exception as e:
            logger.error(f"Error processing CSV file: {e}")
            return {
                "success": False,
                "error": str(e),
                "mapping_data": [],
                "columns": [],
                # Backward compatibility fields
                "unified_map": [],
                "total_mappings": 0
            }

    def process_excel_file(self, file_content: bytes) -> Dict[str, Any]:
        """
        Process Excel file content (fallback to existing processor for Excel files).

        Args:
            file_content: Raw bytes content of Excel file

        Returns:
            Dict containing mapping data and metadata
        """
        try:
            # For Excel files, we'll use the first sheet and treat it like a CSV
            excel_file = pd.ExcelFile(BytesIO(file_content))
            sheet_name = excel_file.sheet_names[0]  # Use first sheet

            df = pd.read_excel(excel_file, sheet_name=sheet_name)

            if df.empty:
                return {
                    "success": False,
                    "error": "Excel sheet is empty"
                }

            # Store column information
            self.columns = list(df.columns)
            logger.info(f"Detected Excel columns: {self.columns}")

            # Convert to list of dictionaries
            self.mapping_data = df.to_dict('records')

            # Clean the data
            cleaned_data = []
            for row in self.mapping_data:
                if any(pd.notna(value) and str(value).strip() for value in row.values()):
                    cleaned_data.append(row)

            self.mapping_data = cleaned_data

            result = {
                "success": True,
                "mapping_data": self.mapping_data,
                "columns": self.columns,
                "total_rows": len(self.mapping_data),
                "original_rows": len(df),
                "file_format": "excel",
                "sheet_name": sheet_name,
                # Backward compatibility fields
                "unified_map": self.mapping_data,
                "total_mappings": len(self.mapping_data)
            }

            logger.info(f"Successfully processed Excel with {len(self.mapping_data)} valid rows and columns: {self.columns}")
            return result

        except Exception as e:
            logger.error(f"Error processing Excel file: {e}")
            return {
                "success": False,
                "error": str(e),
                "mapping_data": [],
                "columns": [],
                # Backward compatibility fields
                "unified_map": [],
                "total_mappings": 0
            }

    def process_mapping_file(self, file_content: bytes, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Process mapping file (auto-detect CSV or Excel format).

        Args:
            file_content: Raw bytes content of mapping file
            file_path: Optional file path for extension-based format detection

        Returns:
            Dict containing mapping data and metadata
        """
        logger.info(f"Processing mapping file{f' from path: {file_path}' if file_path else ''}")

        file_format = self.detect_file_format(file_content, file_path)
        logger.info(f"Detected file format: {file_format}")

        if file_format == 'csv':
            logger.info("Processing as CSV file")
            return self.process_csv_file(file_content)
        elif file_format == 'excel':
            logger.info("Processing as Excel file")
            return self.process_excel_file(file_content)
        else:
            error_msg = f"Unsupported file format: {file_format}. Please use CSV or Excel files."
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "mapping_data": [],
                "columns": []
            }

    def create_lookup_map(self, mapping_data: List[Dict], user_mapping_keys: List[str]) -> Dict[str, Dict]:
        """
        Create a lookup map based on user-selected mapping keys.

        Args:
            mapping_data: List of mapping file records
            user_mapping_keys: User-selected keys for mapping (e.g., ['PHONE', 'ACCOUNT_NO'])

        Returns:
            Dictionary with lookup keys mapped to full record data
        """
        lookup_map = {}

        for record in mapping_data:
            # Create lookup keys based on user selection
            lookup_keys = []

            for mapping_key in user_mapping_keys:
                if mapping_key in record and pd.notna(record[mapping_key]):
                    # Normalize the lookup key
                    normalized_key = self.normalize_identifier(str(record[mapping_key]))
                    if normalized_key:
                        lookup_keys.append(normalized_key)

            # Store the full record for each lookup key
            for lookup_key in lookup_keys:
                if lookup_key not in lookup_map:
                    lookup_map[lookup_key] = record.copy()
                else:
                    # Handle duplicates - keep first occurrence, log warning
                    logger.warning(f"Duplicate lookup key found: {lookup_key}")

        logger.info(f"Created lookup map with {len(lookup_map)} entries from {len(user_mapping_keys)} mapping keys")
        return lookup_map

    def normalize_identifier(self, identifier: str) -> str:
        """Normalize identifier for consistent matching."""
        if not identifier or pd.isna(identifier):
            return ""

        # Convert to string and remove spaces, special characters
        normalized = str(identifier).strip()
        normalized = re.sub(r'[^\w]', '', normalized)
        return normalized.upper()

    def get_ocr_field_for_mapping_key(self, mapping_key: str) -> str:
        """
        Get the corresponding OCR field for a mapping key.

        Args:
            mapping_key: Key from mapping file (e.g., 'PHONE')

        Returns:
            Corresponding OCR field name (e.g., 'number')
        """
        # Reverse lookup in the mapping
        for ocr_field, map_field in self.ocr_to_mapping_field_map.items():
            if map_field == mapping_key:
                return ocr_field

        # If no mapping found, try direct match (lowercase)
        return mapping_key.lower()


def process_dynamic_mapping_file(file_content: bytes, file_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to process mapping file with dynamic column detection.

    Args:
        file_content: Raw bytes content of mapping file
        file_path: Optional file path for extension-based format detection

    Returns:
        Dict containing mapping data and metadata
    """
    processor = DynamicMappingProcessor()
    return processor.process_mapping_file(file_content, file_path)