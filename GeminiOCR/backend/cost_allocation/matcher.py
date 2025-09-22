"""
Smart matching algorithm for OCR results and mapping data.
Implements priority-based matching with multiple identifier types.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class SmartMatcher:
    """Implements smart matching logic for OCR data and mapping information."""
    
    def __init__(self, unified_map: Dict[str, Any]):
        self.unified_map = unified_map
        self.match_statistics = {
            "total_records": 0,
            "matched_records": 0,
            "unmatched_records": 0,
            "match_by_priority": {
                "mobile_number": 0,
                "service_number": 0,
                "account_number": 0,
                "customer_reference": 0
            }
        }
    
    def normalize_identifier(self, identifier: str) -> str:
        """Normalize identifier for consistent matching."""
        if not identifier:
            return ""
        
        # Convert to string and remove spaces, special characters
        normalized = str(identifier).strip()
        normalized = re.sub(r'[^\w]', '', normalized)
        return normalized.upper()
    
    def extract_identifiers(self, ocr_record: Dict[str, Any]) -> Dict[str, str]:
        """Extract and normalize all possible identifiers from OCR record."""
        identifiers = {}
        
        # Priority 1: Mobile/Service numbers
        for field in ['mobile_number', 'service_number', 'phone_number']:
            if field in ocr_record and ocr_record[field]:
                # Handle multiple numbers (e.g., "53156812/14714300536")
                value = str(ocr_record[field])
                if '/' in value:
                    # Take the first number for primary matching
                    numbers = value.split('/')
                    identifiers['mobile_number'] = self.normalize_identifier(numbers[0])
                    # Store the full string for reference
                    identifiers['mobile_number_full'] = self.normalize_identifier(value.replace('/', ''))
                else:
                    identifiers['mobile_number'] = self.normalize_identifier(value)
                break
        
        # Priority 2: Account numbers
        for field in ['account_number', 'customer_number', 'customer_no']:
            if field in ocr_record and ocr_record[field]:
                identifiers['account_number'] = self.normalize_identifier(str(ocr_record[field]))
                break
        
        # Priority 3: Customer references
        for field in ['customer_reference', 'reference', 'ref_number']:
            if field in ocr_record and ocr_record[field]:
                identifiers['customer_reference'] = self.normalize_identifier(str(ocr_record[field]))
                break
        
        return identifiers
    
    def find_match(self, identifiers: Dict[str, str]) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Find matching entry in unified_map based on priority order.
        
        Returns:
            Tuple of (match_data, match_type) where match_type indicates which identifier was used
        """
        # Priority 1: Mobile/Service number
        if 'mobile_number' in identifiers:
            normalized_id = identifiers['mobile_number']
            if normalized_id in self.unified_map:
                return self.unified_map[normalized_id], 'mobile_number'
            
            # Try full mobile number if available
            if 'mobile_number_full' in identifiers:
                full_id = identifiers['mobile_number_full']
                if full_id in self.unified_map:
                    return self.unified_map[full_id], 'mobile_number'
        
        # Priority 2: Account number
        if 'account_number' in identifiers:
            normalized_id = identifiers['account_number']
            if normalized_id in self.unified_map:
                return self.unified_map[normalized_id], 'account_number'
        
        # Priority 3: Customer reference
        if 'customer_reference' in identifiers:
            normalized_id = identifiers['customer_reference']
            if normalized_id in self.unified_map:
                return self.unified_map[normalized_id], 'customer_reference'
        
        return None, 'unmatched'
    
    def enrich_ocr_record(self, ocr_record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich a single OCR record with mapping information.
        
        Args:
            ocr_record: Original OCR extracted data
            
        Returns:
            Enriched record with Department, ShopCode, and matching metadata
        """
        self.match_statistics["total_records"] += 1
        
        # Extract identifiers
        identifiers = self.extract_identifiers(ocr_record)
        
        # Find match
        match_data, match_type = self.find_match(identifiers)
        
        # Create enriched record
        enriched_record = ocr_record.copy()
        
        if match_data:
            # Add matching information
            enriched_record['Department'] = match_data.get('Department', 'Retail')
            enriched_record['ShopCode'] = match_data.get('ShopCode', '')
            enriched_record['ServiceType'] = match_data.get('ServiceType', 'Unknown')
            enriched_record['MatchedBy'] = match_type
            enriched_record['MatchSource'] = match_data.get('Source', '')
            enriched_record['Matched'] = True
            
            # Update statistics
            self.match_statistics["matched_records"] += 1
            self.match_statistics["match_by_priority"][match_type] += 1
            
            logger.debug(f"Matched record using {match_type} to shop {match_data.get('ShopCode', 'Unknown')}")
            
        else:
            # Mark as unmatched
            enriched_record['Department'] = 'Unallocated'
            enriched_record['ShopCode'] = 'UNMATCHED'
            enriched_record['ServiceType'] = 'Unknown'
            enriched_record['MatchedBy'] = 'unmatched'
            enriched_record['MatchSource'] = ''
            enriched_record['Matched'] = False
            
            # Update statistics
            self.match_statistics["unmatched_records"] += 1
            
            logger.warning(f"No match found for record with identifiers: {identifiers}")
        
        # Store original identifiers for debugging
        enriched_record['ExtractedIdentifiers'] = identifiers
        
        return enriched_record
    
    def enrich_ocr_batch(self, ocr_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Enrich a batch of OCR records with mapping information.
        
        Args:
            ocr_results: List of OCR extracted records
            
        Returns:
            Dict containing enriched records and processing statistics
        """
        logger.info(f"Starting enrichment process for {len(ocr_results)} OCR records")
        
        enriched_records = []
        
        for record in ocr_results:
            try:
                enriched_record = self.enrich_ocr_record(record)
                enriched_records.append(enriched_record)
            except Exception as e:
                logger.error(f"Error enriching record: {e}")
                # Add record with error flag
                error_record = record.copy()
                error_record['Department'] = 'Error'
                error_record['ShopCode'] = 'ERROR'
                error_record['Matched'] = False
                error_record['Error'] = str(e)
                enriched_records.append(error_record)
        
        # Calculate match rate
        match_rate = 0
        if self.match_statistics["total_records"] > 0:
            match_rate = (self.match_statistics["matched_records"] / self.match_statistics["total_records"]) * 100
        
        result = {
            "enriched_records": enriched_records,
            "total_records": self.match_statistics["total_records"],
            "matched_records": self.match_statistics["matched_records"],
            "unmatched_records": self.match_statistics["unmatched_records"],
            "match_rate_percent": round(match_rate, 2),
            "match_breakdown": self.match_statistics["match_by_priority"],
            "success": True
        }
        
        logger.info(f"Enrichment completed: {self.match_statistics['matched_records']}/{self.match_statistics['total_records']} records matched ({match_rate:.1f}%)")
        
        return result


def enrich_ocr_data(ocr_results: List[Dict[str, Any]], unified_map: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to enrich OCR data with mapping information.
    
    Args:
        ocr_results: List of OCR extracted records
        unified_map: Unified mapping dictionary from mapping processor
        
    Returns:
        Dict containing enriched records and processing statistics
    """
    matcher = SmartMatcher(unified_map)
    return matcher.enrich_ocr_batch(ocr_results)