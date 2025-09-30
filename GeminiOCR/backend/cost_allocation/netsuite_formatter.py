"""
NetSuite CSV formatter for generating journal entries from enriched OCR data.
Generates CSV files compatible with NetSuite import format.
"""

import pandas as pd
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class NetSuiteFormatter:
    """Formats enriched OCR data into NetSuite-compatible CSV journal entries."""
    
    def __init__(self):
        self.netsuite_records = []
        self.external_id_counter = 1
    
    def generate_external_id(self, prefix: str = "DC") -> str:
        """Generate unique external ID for NetSuite entries."""
        today = datetime.now().strftime("%y%m%d")
        external_id = f"{prefix}{today}-{self.external_id_counter:02d}"
        self.external_id_counter += 1
        return external_id
    
    def format_date(self, date_str: str) -> str:
        """Format date for NetSuite (DD/MM/YYYY)."""
        try:
            # Try to parse various date formats
            for fmt in ["%Y-%m-%d", "%d-%b-%Y", "%d/%m/%Y", "%d/%m/%y"]:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    return date_obj.strftime("%d/%m/%Y")
                except ValueError:
                    continue
            
            # If parsing fails, use current date
            logger.warning(f"Could not parse date '{date_str}', using current date")
            return datetime.now().strftime("%d/%m/%Y")
            
        except Exception as e:
            logger.error(f"Error formatting date '{date_str}': {e}")
            return datetime.now().strftime("%d/%m/%Y")
    
    def get_vendor_name(self, service_type: str, company_name: str = "") -> str:
        """Determine vendor name based on service type and company."""
        vendor_mapping = {
            "Phone": "3HK / CMHK / CSL / Smartone",
            "Broadband": "PCCW",
            "Gas": "CLP",
            "Water": "WSD",
            "Electricity": "HKELE"
        }
        
        # Try to get specific vendor from company name
        if company_name:
            company_lower = company_name.lower()
            if "cmhk" in company_lower or "china mobile" in company_lower:
                return "CMHK"
            elif "3hk" in company_lower or "three" in company_lower:
                return "3HK"
            elif "csl" in company_lower:
                return "CSL"
            elif "smartone" in company_lower:
                return "Smartone"
            elif "pccw" in company_lower:
                return "PCCW"
            elif "clp" in company_lower:
                return "CLP"
            elif "wsd" in company_lower or "water" in company_lower:
                return "WSD"
            elif "hkele" in company_lower or "electricity" in company_lower:
                return "HKELE"
        
        return vendor_mapping.get(service_type, "Other Payable")
    
    def create_credit_entry(self, external_id: str, date: str, memo: str, 
                           total_amount: float, vendor_name: str) -> Dict[str, Any]:
        """Create credit entry for total bill amount (payables)."""
        return {
            "External ID": external_id,
            "Date": date,
            "Currency": "HKD",
            "Exchange Rate": "1.0000",
            "Memo (Main)": memo,
            "AR/AP Type": "",
            "Account": "3011300",  # Other Payable account
            "Debit": "0.00",
            "Credit": f"{total_amount:.2f}",
            "short name": vendor_name,
            "netsuite name": "Other Payable",
            "Name": f"1000000213 {vendor_name}",
            "Department": "Finance",
            "Location": "",
            "Memo (Line)": memo,
            "Reference no.": memo
        }
    
    def create_debit_entry(self, external_id: str, date: str, memo: str,
                          amount: float, shop_code: str, department: str) -> Dict[str, Any]:
        """Create debit entry for cost allocation to specific shop/department."""
        line_memo = f"{memo} - {shop_code}" if shop_code != "UNMATCHED" else f"{memo} - UNALLOCATED"
        
        return {
            "External ID": external_id,
            "Date": date,
            "Currency": "HKD",
            "Exchange Rate": "1.0000",
            "Memo (Main)": memo,
            "AR/AP Type": "",
            "Account": "7081108",  # Telephone & Internet expense account
            "Debit": f"{amount:.2f}",
            "Credit": "0.00",
            "short name": "Telephone & Internet",
            "netsuite name": "Telephone & Internet",
            "Name": f"1000000213 {self.get_vendor_name('Phone')}",  # Default vendor
            "Department": department,
            "Location": shop_code if shop_code != "UNMATCHED" else "",
            "Memo (Line)": line_memo,
            "Reference no.": ""
        }
    
    def process_invoice_group(self, invoice_data: Dict[str, Any], 
                             enriched_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a single invoice and its associated records into NetSuite entries."""
        entries = []
        
        # Extract invoice information
        company_name = invoice_data.get('company_name', '')
        bill_date = invoice_data.get('bill_date', datetime.now().strftime("%d/%m/%Y"))
        account_number = invoice_data.get('account_number', '')
        total_amount = invoice_data.get('total_amount_due', 0)
        
        # Format date
        formatted_date = self.format_date(bill_date)
        
        # Generate external ID and memo
        external_id = self.generate_external_id()
        memo = f"{formatted_date} Bill ({account_number})" if account_number else f"{formatted_date} Telecom Bill"
        
        # Determine vendor
        vendor_name = self.get_vendor_name("Phone", company_name)
        
        # Create credit entry (total bill amount)
        credit_entry = self.create_credit_entry(
            external_id, formatted_date, memo, total_amount, vendor_name
        )
        entries.append(credit_entry)
        
        # Create debit entries for each line item
        for record in enriched_records:
            try:
                amount = float(record.get('amount', 0))
                if amount <= 0:
                    continue
                
                shop_code = record.get('ShopCode', 'UNMATCHED')
                department = record.get('Department', 'Retail')
                
                debit_entry = self.create_debit_entry(
                    external_id, formatted_date, memo, amount, shop_code, department
                )
                entries.append(debit_entry)
                
            except (ValueError, TypeError) as e:
                logger.error(f"Error processing record amount: {e}")
                continue
        
        return entries
    
    def format_to_netsuite_csv(self, enriched_data: List[Dict[str, Any]], 
                              invoice_metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Convert enriched OCR data to NetSuite CSV format.
        
        Args:
            enriched_data: List of enriched OCR records
            invoice_metadata: Optional metadata about the invoice
            
        Returns:
            CSV string in NetSuite format
        """
        try:
            # Group records by invoice if possible, otherwise treat as single group
            if invoice_metadata:
                # Process with invoice metadata
                entries = self.process_invoice_group(invoice_metadata, enriched_data)
            else:
                # Create generic invoice data
                total_amount = sum(float(record.get('amount', 0)) for record in enriched_data if record.get('amount'))
                generic_invoice = {
                    'company_name': 'Telecom Provider',
                    'bill_date': datetime.now().strftime("%d/%m/%Y"),
                    'account_number': 'BATCH',
                    'total_amount_due': total_amount
                }
                entries = self.process_invoice_group(generic_invoice, enriched_data)
            
            # Convert to DataFrame and then CSV
            if entries:
                df = pd.DataFrame(entries)
                
                # Ensure column order matches NetSuite requirements
                column_order = [
                    "External ID", "Date", "Currency", "Exchange Rate", "Memo (Main)",
                    "AR/AP Type", "Account", "Debit", "Credit", "short name",
                    "netsuite name", "Name", "Department", "Location", 
                    "Memo (Line)", "Reference no."
                ]
                
                # Reorder columns
                df = df.reindex(columns=column_order)
                
                # Convert to CSV
                csv_content = df.to_csv(index=False, encoding='utf-8-sig')
                
                logger.info(f"Generated NetSuite CSV with {len(entries)} entries")
                return csv_content
            else:
                logger.warning("No entries generated for NetSuite CSV")
                return ""
                
        except Exception as e:
            logger.error(f"Error generating NetSuite CSV: {e}")
            return ""
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get formatting statistics."""
        total_entries = len(self.netsuite_records)
        credit_entries = len([r for r in self.netsuite_records if float(r.get('Credit', 0)) > 0])
        debit_entries = len([r for r in self.netsuite_records if float(r.get('Debit', 0)) > 0])
        
        return {
            "total_entries": total_entries,
            "credit_entries": credit_entries,
            "debit_entries": debit_entries,
            "invoices_processed": self.external_id_counter - 1
        }


def generate_netsuite_csv(enriched_data: List[Dict[str, Any]], 
                         invoice_metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Convenience function to generate NetSuite CSV from enriched data.
    
    Args:
        enriched_data: List of enriched OCR records
        invoice_metadata: Optional metadata about the invoice
        
    Returns:
        CSV string in NetSuite format
    """
    formatter = NetSuiteFormatter()
    return formatter.format_to_netsuite_csv(enriched_data, invoice_metadata)