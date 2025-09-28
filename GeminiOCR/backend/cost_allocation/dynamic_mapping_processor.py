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

    def detect_file_format(self, file_content: bytes) -> str:
        """Detect if file is CSV or Excel format."""
        try:
            # Try to detect Excel file
            pd.read_excel(BytesIO(file_content), nrows=1)
            return 'excel'
        except:
            try:
                # Try to detect CSV file
                pd.read_csv(StringIO(file_content.decode('utf-8')), nrows=1)
                return 'csv'
            except:
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
                "file_format": "csv"
            }

            logger.info(f"Successfully processed CSV with {len(self.mapping_data)} valid rows and columns: {self.columns}")
            return result

        except Exception as e:
            logger.error(f"Error processing CSV file: {e}")
            return {
                "success": False,
                "error": str(e),
                "mapping_data": [],
                "columns": []
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
                "sheet_name": sheet_name
            }

            logger.info(f"Successfully processed Excel with {len(self.mapping_data)} valid rows and columns: {self.columns}")
            return result

        except Exception as e:
            logger.error(f"Error processing Excel file: {e}")
            return {
                "success": False,
                "error": str(e),
                "mapping_data": [],
                "columns": []
            }

    def process_mapping_file(self, file_content: bytes) -> Dict[str, Any]:
        """
        Process mapping file (auto-detect CSV or Excel format).

        Args:
            file_content: Raw bytes content of mapping file

        Returns:
            Dict containing mapping data and metadata
        """
        file_format = self.detect_file_format(file_content)

        if file_format == 'csv':
            return self.process_csv_file(file_content)
        elif file_format == 'excel':
            return self.process_excel_file(file_content)
        else:
            return {
                "success": False,
                "error": "Unsupported file format. Please use CSV or Excel files.",
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


def process_dynamic_mapping_file(file_content: bytes) -> Dict[str, Any]:
    """
    Convenience function to process mapping file with dynamic column detection.

    Args:
        file_content: Raw bytes content of mapping file

    Returns:
        Dict containing mapping data and metadata
    """
    processor = DynamicMappingProcessor()
    return processor.process_mapping_file(file_content)