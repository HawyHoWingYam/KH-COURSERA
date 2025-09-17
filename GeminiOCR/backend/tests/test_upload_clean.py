#!/usr/bin/env python3
"""
Test script for clean S3 path structure upload
Tests the new upload endpoint with clean path structure
"""

import os
import sys
import logging
import requests
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_upload_with_clean_paths():
    """Test uploading files with clean path structure"""
    
    print("🧪 Testing Clean Path Upload")
    print("=" * 40)
    
    # API base URL
    base_url = "http://localhost:8000"
    
    # Test configuration data
    company_id = 7
    doc_type_id = 43
    config_id = 40  # Use existing config
    
    # Test files
    prompt_file = "test_invoice_prompt.txt"
    schema_file = "test_invoice_schema.json"
    
    print(f"Testing upload for config_id: {config_id}")
    print(f"Company ID: {company_id}, Doc Type ID: {doc_type_id}")
    
    # Test 1: Upload prompt file
    print(f"\n1. Testing prompt upload:")
    print(f"   File: {prompt_file}")
    
    # Construct the path according to new format
    # Path format: document_type/{doc_type_id}/{company_id}/prompt/{filename}
    prompt_path = f"document_type/{doc_type_id}/{company_id}/prompt/config_{config_id}_prompt.txt"
    print(f"   Upload path: {prompt_path}")
    
    try:
        with open(prompt_file, 'rb') as f:
            files = {'file': (prompt_file, f, 'text/plain')}
            data = {'path': prompt_path}
            
            # Make upload request
            response = requests.post(f"{base_url}/upload", files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ Upload successful!")
                print(f"   📁 S3 Path: {result.get('file_path', 'N/A')}")
                
                # Check if path follows clean structure
                expected_clean_path = f"companies/{company_id}/prompts/{doc_type_id}/{config_id}/{prompt_file}"
                if expected_clean_path in result.get('file_path', ''):
                    print(f"   ✅ Clean path structure confirmed!")
                else:
                    print(f"   ⚠️ Path structure may not be clean")
                    print(f"   Expected clean path component: {expected_clean_path}")
                    
            else:
                print(f"   ❌ Upload failed: {response.status_code} - {response.text}")
                
    except FileNotFoundError:
        print(f"   ⚠️ Test file {prompt_file} not found, skipping upload test")
    except requests.exceptions.ConnectionError:
        print(f"   ⚠️ Cannot connect to {base_url}, make sure backend is running")
    except Exception as e:
        print(f"   ❌ Upload error: {e}")
    
    # Test 2: Upload schema file
    print(f"\n2. Testing schema upload:")
    print(f"   File: {schema_file}")
    
    schema_path = f"document_type/{doc_type_id}/{company_id}/schema/config_{config_id}_schema.json"
    print(f"   Upload path: {schema_path}")
    
    try:
        with open(schema_file, 'rb') as f:
            files = {'file': (schema_file, f, 'application/json')}
            data = {'path': schema_path}
            
            response = requests.post(f"{base_url}/upload", files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ Upload successful!")
                print(f"   📁 S3 Path: {result.get('file_path', 'N/A')}")
                
                # Check if path follows clean structure
                expected_clean_path = f"companies/{company_id}/schemas/{doc_type_id}/{config_id}/{schema_file}"
                if expected_clean_path in result.get('file_path', ''):
                    print(f"   ✅ Clean path structure confirmed!")
                else:
                    print(f"   ⚠️ Path structure may not be clean")
                    print(f"   Expected clean path component: {expected_clean_path}")
                    
            else:
                print(f"   ❌ Upload failed: {response.status_code} - {response.text}")
                
    except FileNotFoundError:
        print(f"   ⚠️ Test file {schema_file} not found, skipping upload test")
    except requests.exceptions.ConnectionError:
        print(f"   ⚠️ Cannot connect to {base_url}, make sure backend is running")
    except Exception as e:
        print(f"   ❌ Upload error: {e}")
    
    print(f"\n" + "=" * 40)
    print("🎯 Test Summary:")
    print("   If uploads succeeded and show clean path structure,")
    print("   the new implementation is working correctly!")
    print("   Expected format: companies/{id}/prompts|schemas/{doc_type}/{config}/filename")

if __name__ == "__main__":
    test_upload_with_clean_paths()