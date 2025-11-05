"""
Report generator for cost allocation system.
Generates Excel reports for matching details and cost summaries.
"""

import pandas as pd
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import io

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates various Excel reports for cost allocation analysis."""
    
    def __init__(self):
        self.reports = {}
    
    def generate_matching_details_report(self, enriched_data: List[Dict[str, Any]], 
                                       mapping_stats: Dict[str, Any]) -> bytes:
        """
        Generate detailed matching report with Matched and Unmatched sheets.
        
        Args:
            enriched_data: List of enriched OCR records
            mapping_stats: Statistics from mapping process
            
        Returns:
            Excel file content as bytes
        """
        try:
            # Separate matched and unmatched records
            matched_records = [r for r in enriched_data if r.get('Matched', False)]
            unmatched_records = [r for r in enriched_data if not r.get('Matched', False)]
            
            # Create Excel writer
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                
                # Sheet 1: Matched Records
                if matched_records:
                    matched_df = self._prepare_matched_dataframe(matched_records)
                    matched_df.to_excel(writer, sheet_name='Matched', index=False)
                    
                    # Auto-adjust column widths
                    worksheet = writer.sheets['Matched']
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 50)
                        worksheet.column_dimensions[column_letter].width = adjusted_width
                
                # Sheet 2: Unmatched Records
                if unmatched_records:
                    unmatched_df = self._prepare_unmatched_dataframe(unmatched_records)
                    unmatched_df.to_excel(writer, sheet_name='Unmatched', index=False)
                    
                    # Auto-adjust column widths
                    worksheet = writer.sheets['Unmatched']
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 50)
                        worksheet.column_dimensions[column_letter].width = adjusted_width
                
                # Sheet 3: Summary Statistics
                summary_df = self._prepare_summary_dataframe(enriched_data, mapping_stats)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            output.seek(0)
            content = output.getvalue()
            
            logger.info(f"Generated matching details report with {len(matched_records)} matched and {len(unmatched_records)} unmatched records")
            return content
            
        except Exception as e:
            logger.error(f"Error generating matching details report: {e}")
            return b""
    
    def _prepare_matched_dataframe(self, matched_records: List[Dict[str, Any]]) -> pd.DataFrame:
        """Prepare DataFrame for matched records."""
        data = []
        
        for record in matched_records:
            row = {
                'Service Number': record.get('mobile_number', record.get('service_number', '')),
                'Account Number': record.get('account_number', ''),
                'Description': record.get('description', ''),
                'Amount': record.get('amount', 0),
                'Period': record.get('period', record.get('item_date_or_period', '')),
                'Shop Code': record.get('ShopCode', ''),
                'Department': record.get('Department', ''),
                'Service Type': record.get('ServiceType', ''),
                'Matched By': record.get('MatchedBy', ''),
                'Match Source': record.get('MatchSource', ''),
                'Company Name': record.get('company_name', ''),
                'Bill Date': record.get('bill_date', '')
            }
            data.append(row)
        
        return pd.DataFrame(data)
    
    def _prepare_unmatched_dataframe(self, unmatched_records: List[Dict[str, Any]]) -> pd.DataFrame:
        """Prepare DataFrame for unmatched records."""
        data = []
        
        for record in unmatched_records:
            identifiers = record.get('ExtractedIdentifiers', {})
            
            row = {
                'Service Number': record.get('mobile_number', record.get('service_number', '')),
                'Account Number': record.get('account_number', ''),
                'Customer Reference': record.get('customer_reference', ''),
                'Description': record.get('description', ''),
                'Amount': record.get('amount', 0),
                'Period': record.get('period', record.get('item_date_or_period', '')),
                'Company Name': record.get('company_name', ''),
                'Bill Date': record.get('bill_date', ''),
                'Extracted Identifiers': str(identifiers),
                'Reason': 'No matching entry found in mapping file'
            }
            data.append(row)
        
        return pd.DataFrame(data)
    
    def _prepare_summary_dataframe(self, enriched_data: List[Dict[str, Any]], 
                                  mapping_stats: Dict[str, Any]) -> pd.DataFrame:
        """Prepare DataFrame for summary statistics."""
        total_records = len(enriched_data)
        matched_records = len([r for r in enriched_data if r.get('Matched', False)])
        unmatched_records = total_records - matched_records
        
        match_rate = (matched_records / total_records * 100) if total_records > 0 else 0
        
        total_amount = sum(float(r.get('amount', 0)) for r in enriched_data)
        matched_amount = sum(float(r.get('amount', 0)) for r in enriched_data if r.get('Matched', False))
        unmatched_amount = total_amount - matched_amount
        
        data = [
            {'Metric': 'Total Records', 'Value': total_records},
            {'Metric': 'Matched Records', 'Value': matched_records},
            {'Metric': 'Unmatched Records', 'Value': unmatched_records},
            {'Metric': 'Match Rate (%)', 'Value': f"{match_rate:.2f}%"},
            {'Metric': 'Total Amount (HKD)', 'Value': f"{total_amount:.2f}"},
            {'Metric': 'Matched Amount (HKD)', 'Value': f"{matched_amount:.2f}"},
            {'Metric': 'Unmatched Amount (HKD)', 'Value': f"{unmatched_amount:.2f}"},
            {'Metric': 'Processing Date', 'Value': datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            {'Metric': 'Mapping Entries Used', 'Value': mapping_stats.get('total_mappings', 0)}
        ]
        
        return pd.DataFrame(data)
    
    def generate_cost_summary_report(self, enriched_data: List[Dict[str, Any]]) -> bytes:
        """
        Generate cost summary report grouped by department and shop.
        
        Args:
            enriched_data: List of enriched OCR records
            
        Returns:
            Excel file content as bytes
        """
        try:
            # Create Excel writer
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                
                # Sheet 1: Summary by Department
                dept_summary = self._generate_department_summary(enriched_data)
                dept_summary.to_excel(writer, sheet_name='By Department', index=False)
                
                # Sheet 2: Summary by Shop
                shop_summary = self._generate_shop_summary(enriched_data)
                shop_summary.to_excel(writer, sheet_name='By Shop', index=False)
                
                # Sheet 3: Detailed Breakdown
                detailed_breakdown = self._generate_detailed_breakdown(enriched_data)
                detailed_breakdown.to_excel(writer, sheet_name='Detailed Breakdown', index=False)
                
                # Auto-adjust column widths for all sheets
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 30)
                        worksheet.column_dimensions[column_letter].width = adjusted_width
            
            output.seek(0)
            content = output.getvalue()
            
            logger.info("Generated cost summary report")
            return content
            
        except Exception as e:
            logger.error(f"Error generating cost summary report: {e}")
            return b""
    
    def _generate_department_summary(self, enriched_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """Generate summary grouped by department."""
        dept_summary = {}
        
        for record in enriched_data:
            department = record.get('Department', 'Unknown')
            amount = float(record.get('amount', 0))
            
            if department not in dept_summary:
                dept_summary[department] = {
                    'Department': department,
                    'Total Amount (HKD)': 0,
                    'Record Count': 0,
                    'Matched Records': 0,
                    'Unmatched Records': 0
                }
            
            dept_summary[department]['Total Amount (HKD)'] += amount
            dept_summary[department]['Record Count'] += 1
            
            if record.get('Matched', False):
                dept_summary[department]['Matched Records'] += 1
            else:
                dept_summary[department]['Unmatched Records'] += 1
        
        # Convert to DataFrame and sort by amount descending
        df = pd.DataFrame(list(dept_summary.values()))
        df = df.sort_values('Total Amount (HKD)', ascending=False)
        
        # Format amounts
        df['Total Amount (HKD)'] = df['Total Amount (HKD)'].round(2)
        
        return df
    
    def _generate_shop_summary(self, enriched_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """Generate summary grouped by shop."""
        shop_summary = {}
        
        for record in enriched_data:
            shop_code = record.get('ShopCode', 'Unknown')
            department = record.get('Department', 'Unknown')
            amount = float(record.get('amount', 0))
            
            key = f"{shop_code}|{department}"
            
            if key not in shop_summary:
                shop_summary[key] = {
                    'Shop Code': shop_code,
                    'Department': department,
                    'Total Amount (HKD)': 0,
                    'Record Count': 0,
                    'Service Types': set()
                }
            
            shop_summary[key]['Total Amount (HKD)'] += amount
            shop_summary[key]['Record Count'] += 1
            shop_summary[key]['Service Types'].add(record.get('ServiceType', 'Unknown'))
        
        # Convert to DataFrame
        data = []
        for summary in shop_summary.values():
            data.append({
                'Shop Code': summary['Shop Code'],
                'Department': summary['Department'],
                'Total Amount (HKD)': round(summary['Total Amount (HKD)'], 2),
                'Record Count': summary['Record Count'],
                'Service Types': ', '.join(sorted(summary['Service Types']))
            })
        
        df = pd.DataFrame(data)
        df = df.sort_values('Total Amount (HKD)', ascending=False)
        
        return df
    
    def _generate_detailed_breakdown(self, enriched_data: List[Dict[str, Any]]) -> pd.DataFrame:
        """Generate detailed breakdown of all records."""
        data = []
        
        for record in enriched_data:
            row = {
                'Shop Code': record.get('ShopCode', ''),
                'Department': record.get('Department', ''),
                'Service Type': record.get('ServiceType', ''),
                'Service Number': record.get('mobile_number', record.get('service_number', '')),
                'Description': record.get('description', ''),
                'Amount (HKD)': round(float(record.get('amount', 0)), 2),
                'Period': record.get('period', record.get('item_date_or_period', '')),
                'Matched': 'Yes' if record.get('Matched', False) else 'No',
                'Match Source': record.get('MatchSource', ''),
                'Company': record.get('company_name', '')
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        return df.sort_values(['Department', 'Shop Code', 'Amount (HKD)'], ascending=[True, True, False])


def generate_matching_report(enriched_data: List[Dict[str, Any]], 
                           mapping_stats: Dict[str, Any]) -> bytes:
    """
    Convenience function to generate matching details report.
    
    Args:
        enriched_data: List of enriched OCR records
        mapping_stats: Statistics from mapping process
        
    Returns:
        Excel file content as bytes
    """
    generator = ReportGenerator()
    return generator.generate_matching_details_report(enriched_data, mapping_stats)


def generate_summary_report(enriched_data: List[Dict[str, Any]]) -> bytes:
    """
    Convenience function to generate cost summary report.
    
    Args:
        enriched_data: List of enriched OCR records
        
    Returns:
        Excel file content as bytes
    """
    generator = ReportGenerator()
    return generator.generate_cost_summary_report(enriched_data)