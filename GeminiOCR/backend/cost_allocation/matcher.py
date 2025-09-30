"""
Smart matching algorithm for OCR results and mapping data.
Implements priority-based matching with multiple identifier types.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple

# Import enhanced matching engine for intelligent identifier extraction
from utils.order_processor import MatchingEngine, MatchingConfig, MatchingStrategy

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

        # Initialize enhanced matching engine for intelligent identifier extraction
        logger.info("🔧 SmartMatcher: Initializing enhanced MatchingEngine for identifier extraction")
        matching_config = MatchingConfig(
            separators=["/", ",", ";", "|", "-", "_", ":", ".", " "],  # Support multiple separators
            min_match_length=3,
            case_sensitive=False
        )
        self.matching_engine = MatchingEngine(matching_config)
        logger.info(f"🔧 SmartMatcher: MatchingEngine initialized with separators: {matching_config.separators}")
    
    def normalize_identifier(self, identifier: str) -> str:
        """Normalize identifier for consistent matching."""
        if not identifier:
            return ""
        
        # Convert to string and remove spaces, special characters
        normalized = str(identifier).strip()
        normalized = re.sub(r'[^\w]', '', normalized)
        return normalized.upper()
    
    def extract_identifiers(self, ocr_record: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract and normalize all possible identifiers from OCR record.
        Enhanced with intelligent multi-separator extraction.
        """
        identifiers = {}

        # Priority 1: Mobile/Service numbers - Enhanced extraction
        for field in ['mobile_number', 'service_number', 'phone_number']:
            if field in ocr_record and ocr_record[field]:
                value = str(ocr_record[field])
                logger.info(f"🔍 SmartMatcher: Extracting identifiers from {field}='{value}'")

                # Use enhanced MatchingEngine for intelligent extraction
                extracted_parts = self.matching_engine.extract_identifiers(value)
                logger.info(f"🔍 SmartMatcher: MatchingEngine extracted parts: {extracted_parts}")

                if extracted_parts:
                    # Store primary identifier (first part for backward compatibility)
                    identifiers['mobile_number'] = extracted_parts[0]
                    logger.info(f"🔍 SmartMatcher: Primary mobile_number='{extracted_parts[0]}'")

                    # Store all individual parts for comprehensive matching
                    for i, part in enumerate(extracted_parts):
                        identifiers[f'mobile_number_part_{i}'] = part
                        logger.info(f"🔍 SmartMatcher: Added mobile_number_part_{i}='{part}'")

                    # Also store using legacy naming for compatibility if multiple parts
                    if len(extracted_parts) > 1:
                        # Store second part explicitly (this will fix CMHK 19519057870 issue)
                        identifiers['mobile_number_alt'] = extracted_parts[1]
                        logger.info(f"🔍 SmartMatcher: Added mobile_number_alt='{extracted_parts[1]}' (second part)")

                        # Store concatenated version for legacy compatibility
                        identifiers['mobile_number_full'] = ''.join(extracted_parts)
                        logger.info(f"🔍 SmartMatcher: Added mobile_number_full='{identifiers['mobile_number_full']}' (concatenated)")
                else:
                    # Fallback to simple normalization if no extraction possible
                    identifiers['mobile_number'] = self.normalize_identifier(value)
                    logger.warning(f"🔍 SmartMatcher: Fallback normalization for {field}='{value}' -> '{identifiers['mobile_number']}'")

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
        Enhanced to try all extracted identifier parts.

        Returns:
            Tuple of (match_data, match_type) where match_type indicates which identifier was used
        """
        logger.info(f"🔍 SmartMatcher.find_match: Trying to match with identifiers: {list(identifiers.keys())}")

        # Priority 1: Mobile/Service number - Try primary identifier first
        if 'mobile_number' in identifiers:
            normalized_id = identifiers['mobile_number']
            logger.info(f"🔍 SmartMatcher.find_match: Trying primary mobile_number='{normalized_id}'")
            if normalized_id in self.unified_map:
                logger.info(f"✅ SmartMatcher.find_match: MATCHED on primary mobile_number='{normalized_id}'")
                return self.unified_map[normalized_id], 'mobile_number'

        # Priority 1.1: Try alternative mobile number (second part) - NEW: This fixes CMHK issue!
        if 'mobile_number_alt' in identifiers:
            alt_id = identifiers['mobile_number_alt']
            logger.info(f"🔍 SmartMatcher.find_match: Trying mobile_number_alt='{alt_id}' (second part)")
            if alt_id in self.unified_map:
                logger.info(f"✅ SmartMatcher.find_match: MATCHED on mobile_number_alt='{alt_id}' (second part)")
                return self.unified_map[alt_id], 'mobile_number_alt'

        # Priority 1.2: Try all individual parts
        for key, value in identifiers.items():
            if key.startswith('mobile_number_part_'):
                logger.info(f"🔍 SmartMatcher.find_match: Trying {key}='{value}'")
                if value in self.unified_map:
                    logger.info(f"✅ SmartMatcher.find_match: MATCHED on {key}='{value}'")
                    return self.unified_map[value], key

        # Priority 1.3: Try legacy full mobile number
        if 'mobile_number_full' in identifiers:
            full_id = identifiers['mobile_number_full']
            logger.info(f"🔍 SmartMatcher.find_match: Trying legacy mobile_number_full='{full_id}'")
            if full_id in self.unified_map:
                logger.info(f"✅ SmartMatcher.find_match: MATCHED on mobile_number_full='{full_id}'")
                return self.unified_map[full_id], 'mobile_number_full'

        # Priority 2: Account number
        if 'account_number' in identifiers:
            normalized_id = identifiers['account_number']
            logger.info(f"🔍 SmartMatcher.find_match: Trying account_number='{normalized_id}'")
            if normalized_id in self.unified_map:
                logger.info(f"✅ SmartMatcher.find_match: MATCHED on account_number='{normalized_id}'")
                return self.unified_map[normalized_id], 'account_number'

        # Priority 3: Customer reference
        if 'customer_reference' in identifiers:
            normalized_id = identifiers['customer_reference']
            logger.info(f"🔍 SmartMatcher.find_match: Trying customer_reference='{normalized_id}'")
            if normalized_id in self.unified_map:
                logger.info(f"✅ SmartMatcher.find_match: MATCHED on customer_reference='{normalized_id}'")
                return self.unified_map[normalized_id], 'customer_reference'

        logger.warning("❌ SmartMatcher.find_match: No match found for any identifier")
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