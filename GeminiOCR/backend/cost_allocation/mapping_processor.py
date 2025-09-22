"""
Excel mapping file processor for cost allocation system.
Handles reading multi-sheet Excel files and building unified mapping dictionaries.
"""

import pandas as pd
import logging
from typing import Dict, Optional, Union, Any
from io import BytesIO
import re

logger = logging.getLogger(__name__)


class MappingProcessor:
    """Processes Excel mapping files to create unified lookup dictionaries."""
    
    def __init__(self):
        self.unified_map = {}
        self.sheet_configs = {
            'Phone': {
                'id_columns': ['Phone number', 'Phone', 'Mobile Number', 'mobile_number'],
                'shop_columns': ['Shop', 'Shop Code', 'Location', 'store_code', 'cost_center'],
                'department_columns': ['Department', 'Dept', 'department']
            },
            'Broadband': {
                'id_columns': ['Account Number', 'Account', 'account_number', 'Account No'],
                'shop_columns': ['Shop', 'Shop Code', 'Location', 'store_code'],
                'department_columns': ['Department', 'Dept', 'department']
            },
            'CLP': {
                'id_columns': ['Customer reference', 'Customer Reference', 'account_number', 'Reference'],
                'shop_columns': ['Shop', 'Shop Code', 'Location', 'store_code'],
                'department_columns': ['Department', 'Dept', 'department']
            },
            'Water': {
                'id_columns': ['Account no.', 'Account Number', 'Account', 'account_number'],
                'shop_columns': ['Shop Code', 'Shop', 'Location', 'store_code'],
                'department_columns': ['Department', 'Dept', 'department']
            },
            'HKELE': {
                'id_columns': ['Account Number', 'Account', 'account_number', 'Customer Account'],
                'shop_columns': ['Shop Code', 'Shop', 'Location', 'store_code'],
                'department_columns': ['Department', 'Dept', 'department']
            }
        }
    
    def normalize_identifier(self, identifier: str) -> str:
        """Normalize identifier for consistent matching."""
        if not identifier or pd.isna(identifier):
            return ""
        
        # Convert to string and remove spaces, special characters
        normalized = str(identifier).strip()
        normalized = re.sub(r'[^\w]', '', normalized)
        return normalized.upper()
    
    def find_column(self, df: pd.DataFrame, possible_names: list) -> Optional[str]:
        """Find the actual column name from a list of possible names."""
        df_columns = [col.strip() for col in df.columns]
        
        for possible_name in possible_names:
            # Exact match
            if possible_name in df_columns:
                return possible_name
            
            # Case insensitive match
            for col in df_columns:
                if col.lower() == possible_name.lower():
                    return col
        
        return None
    
    def process_sheet(self, df: pd.DataFrame, sheet_name: str, service_type: str) -> int:
        """Process a single sheet and add mappings to unified_map."""
        if sheet_name not in self.sheet_configs:
            logger.warning(f"Unknown sheet type: {sheet_name}, skipping")
            return 0
        
        config = self.sheet_configs[sheet_name]
        
        # Find the actual column names
        id_col = self.find_column(df, config['id_columns'])
        shop_col = self.find_column(df, config['shop_columns'])
        dept_col = self.find_column(df, config['department_columns'])
        
        if not id_col:
            logger.error(f"Could not find identifier column in {sheet_name} sheet. Expected one of: {config['id_columns']}")
            return 0
        
        if not shop_col:
            logger.warning(f"Could not find shop column in {sheet_name} sheet. Expected one of: {config['shop_columns']}")
        
        processed_count = 0
        
        for index, row in df.iterrows():
            try:
                identifier = row[id_col]
                if pd.isna(identifier) or not str(identifier).strip():
                    continue
                
                normalized_id = self.normalize_identifier(str(identifier))
                if not normalized_id:
                    continue
                
                # Extract shop and department info
                shop_code = ""
                department = "Retail"  # Default department
                
                if shop_col and not pd.isna(row[shop_col]):
                    shop_code = str(row[shop_col]).strip()
                
                if dept_col and not pd.isna(row[dept_col]):
                    department = str(row[dept_col]).strip()
                
                # Store in unified map
                self.unified_map[normalized_id] = {
                    "ShopCode": shop_code,
                    "Department": department,
                    "ServiceType": service_type,
                    "OriginalId": str(identifier),
                    "Source": sheet_name
                }
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing row {index} in {sheet_name}: {e}")
                continue
        
        logger.info(f"Processed {processed_count} records from {sheet_name} sheet")
        return processed_count
    
    def process_excel_file(self, file_content: bytes) -> Dict[str, Any]:
        """
        Process Excel file content and return unified mapping dictionary.
        
        Args:
            file_content: Raw bytes content of Excel file
            
        Returns:
            Dict containing unified mapping and processing statistics
        """
        try:
            # Read Excel file with all sheets
            excel_file = pd.ExcelFile(BytesIO(file_content))
            sheet_names = excel_file.sheet_names
            
            logger.info(f"Found sheets in Excel file: {sheet_names}")
            
            total_processed = 0
            sheet_stats = {}
            
            # Process each sheet
            for sheet_name in sheet_names:
                try:
                    df = pd.read_excel(excel_file, sheet_name=sheet_name)
                    
                    # Skip empty sheets
                    if df.empty:
                        logger.warning(f"Sheet {sheet_name} is empty, skipping")
                        continue
                    
                    # Determine service type based on sheet name
                    service_type = sheet_name
                    if sheet_name.lower() in ['phone', 'mobile']:
                        service_type = "Phone"
                    elif sheet_name.lower() in ['broadband', 'internet']:
                        service_type = "Broadband"
                    elif sheet_name.lower() in ['clp', 'gas']:
                        service_type = "Gas"
                    elif sheet_name.lower() in ['water']:
                        service_type = "Water"
                    elif sheet_name.lower() in ['hkele', 'electricity']:
                        service_type = "Electricity"
                    
                    processed = self.process_sheet(df, sheet_name, service_type)
                    sheet_stats[sheet_name] = {
                        "rows_processed": processed,
                        "total_rows": len(df),
                        "service_type": service_type
                    }
                    total_processed += processed
                    
                except Exception as e:
                    logger.error(f"Error processing sheet {sheet_name}: {e}")
                    sheet_stats[sheet_name] = {
                        "error": str(e),
                        "rows_processed": 0
                    }
            
            # Prepare result
            result = {
                "unified_map": self.unified_map,
                "total_mappings": len(self.unified_map),
                "total_processed": total_processed,
                "sheet_statistics": sheet_stats,
                "success": True
            }
            
            logger.info(f"Successfully created unified mapping with {len(self.unified_map)} entries")
            return result
            
        except Exception as e:
            logger.error(f"Error processing Excel file: {e}")
            return {
                "unified_map": {},
                "total_mappings": 0,
                "total_processed": 0,
                "error": str(e),
                "success": False
            }


def process_mapping_file(file_content: bytes) -> Dict[str, Any]:
    """
    Convenience function to process mapping file.
    
    Args:
        file_content: Raw bytes content of Excel file
        
    Returns:
        Dict containing unified mapping and processing statistics
    """
    processor = MappingProcessor()
    return processor.process_excel_file(file_content)