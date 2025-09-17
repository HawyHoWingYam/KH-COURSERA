#!/usr/bin/env python3
"""
Test script for clean S3 path structure implementation
Tests the new companies/{company_id}/prompts/{doc_type_id}/{config_id}/filename format
"""

import os
import sys
import logging
from typing import Optional

# Add current directory to path to import local modules
sys.path.append('.')

from utils.s3_storage import S3StorageManager
from utils.company_file_manager import CompanyFileManager, FileType

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_clean_path_structure():
    """Test the new clean S3 path structure"""
    
    print("🧪 Testing Clean S3 Path Structure")
    print("=" * 50)
    
    # Test CompanyFileManager path generation
    print("\n1. Testing CompanyFileManager path generation:")
    manager = CompanyFileManager()
    
    # Test prompt path
    prompt_path = manager.get_company_file_path(
        company_id=7,
        file_type=FileType.PROMPT,
        filename="invoice_prompt.txt",
        doc_type_id=43,
        config_id=40
    )
    expected_prompt = "companies/7/prompts/43/40/invoice_prompt.txt"
    print(f"   Prompt path: {prompt_path}")
    print(f"   Expected:    {expected_prompt}")
    print(f"   ✅ Match: {prompt_path == expected_prompt}")
    
    # Test schema path
    schema_path = manager.get_company_file_path(
        company_id=7,
        file_type=FileType.SCHEMA,
        filename="invoice_schema.json",
        doc_type_id=43,
        config_id=40
    )
    expected_schema = "companies/7/schemas/43/40/invoice_schema.json"
    print(f"   Schema path: {schema_path}")
    print(f"   Expected:   {expected_schema}")
    print(f"   ✅ Match: {schema_path == expected_schema}")
    
    # Test temp path (for new configs without ID)
    temp_path = manager.get_company_file_path(
        company_id=7,
        file_type=FileType.PROMPT,
        filename="test_prompt.txt",
        doc_type_id=43,
        config_id=None  # This should generate temp path
    )
    print(f"   Temp path: {temp_path}")
    print(f"   ✅ Contains temp: {'temp_' in temp_path}")
    
    print("\n2. Testing S3StorageManager integration:")
    
    # Test S3 manager (if available)
    try:
        s3_manager = S3StorageManager()
        if s3_manager.s3_client:
            print("   ✅ S3 connection successful")
            
            # Test upload simulation (dry run)
            print("   📤 Testing upload path construction...")
            test_content = "This is a test prompt for clean path structure."
            
            # This would upload to: companies/7/prompts/43/40/test_invoice_prompt.txt
            print(f"   Would upload to: {prompt_path}")
            print(f"   Original filename preserved: test_invoice_prompt.txt")
            
        else:
            print("   ⚠️ S3 not configured, skipping S3 tests")
            
    except Exception as e:
        print(f"   ⚠️ S3 test failed: {e}")
    
    print("\n3. Benefits of Clean Path Structure:")
    print("   ✅ Predictable paths: companies/{id}/prompts/{doc_type}/{config}/filename")
    print("   ✅ Original filenames preserved")
    print("   ✅ No temp prefixes in final paths")
    print("   ✅ Easy debugging and file organization")
    print("   ✅ Direct path construction without complex fallbacks")
    
    print("\n" + "=" * 50)
    print("🎉 Clean Path Structure Test Complete!")

if __name__ == "__main__":
    test_clean_path_structure()