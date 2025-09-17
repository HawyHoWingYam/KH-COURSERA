#!/usr/bin/env python3
"""
Test script for clean S3 path structure download
Tests the new download endpoint with clean path structure
"""

import os
import sys
import logging
import requests
import json

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_download_with_clean_paths():
    """Test downloading files with clean path structure"""
    
    print("🧪 Testing Clean Path Download")
    print("=" * 40)
    
    # API base URL
    base_url = "http://localhost:8000"
    
    # Test configuration data
    config_id = 40  # Use config that we just uploaded to
    
    print(f"Testing download for config_id: {config_id}")
    
    # Test 1: Download prompt file
    print(f"\n1. Testing prompt download:")
    
    try:
        response = requests.get(f"{base_url}/configs/{config_id}/download/prompt")
        
        if response.status_code == 200:
            print(f"   ✅ Download successful!")
            
            # Check Content-Disposition header for filename
            content_disp = response.headers.get('content-disposition', '')
            print(f"   📁 Content-Disposition: {content_disp}")
            
            # Check if original filename is preserved
            if 'test_invoice_prompt.txt' in content_disp:
                print(f"   ✅ Original filename preserved in download!")
            else:
                print(f"   ⚠️ Original filename may not be preserved")
            
            # Check content
            content = response.text
            print(f"   📄 Content length: {len(content)} chars")
            if "OCR专家" in content:
                print(f"   ✅ Content appears correct (contains expected text)")
            else:
                print(f"   ⚠️ Content may be incorrect")
                
            # Save downloaded file for verification
            with open("downloaded_prompt.txt", "w", encoding="utf-8") as f:
                f.write(content)
            print(f"   💾 Saved as: downloaded_prompt.txt")
                
        else:
            print(f"   ❌ Download failed: {response.status_code} - {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"   ⚠️ Cannot connect to {base_url}, make sure backend is running")
    except Exception as e:
        print(f"   ❌ Download error: {e}")
    
    # Test 2: Download schema file
    print(f"\n2. Testing schema download:")
    
    try:
        response = requests.get(f"{base_url}/configs/{config_id}/download/schema")
        
        if response.status_code == 200:
            print(f"   ✅ Download successful!")
            
            # Check Content-Disposition header for filename
            content_disp = response.headers.get('content-disposition', '')
            print(f"   📁 Content-Disposition: {content_disp}")
            
            # Check if original filename is preserved
            if 'test_invoice_schema.json' in content_disp:
                print(f"   ✅ Original filename preserved in download!")
            else:
                print(f"   ⚠️ Original filename may not be preserved")
            
            # Check content
            content = response.text
            print(f"   📄 Content length: {len(content)} chars")
            
            # Try to parse as JSON
            try:
                schema_data = json.loads(content)
                if "invoice_info" in schema_data.get("properties", {}):
                    print(f"   ✅ Content appears correct (valid JSON schema)")
                else:
                    print(f"   ⚠️ Content may be incorrect (missing expected properties)")
            except json.JSONDecodeError:
                print(f"   ⚠️ Content is not valid JSON")
                
            # Save downloaded file for verification
            with open("downloaded_schema.json", "w", encoding="utf-8") as f:
                f.write(content)
            print(f"   💾 Saved as: downloaded_schema.json")
                
        else:
            print(f"   ❌ Download failed: {response.status_code} - {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"   ⚠️ Cannot connect to {base_url}, make sure backend is running")
    except Exception as e:
        print(f"   ❌ Download error: {e}")
    
    print(f"\n" + "=" * 40)
    print("🎯 Test Summary:")
    print("   ✅ If downloads succeeded with original filenames,")
    print("      the clean path structure is working perfectly!")
    print("   ✅ Expected: Files downloaded with original names")
    print("      - test_invoice_prompt.txt")
    print("      - test_invoice_schema.json")
    print("   ✅ No more temp prefixes or config prefixes!")

if __name__ == "__main__":
    test_download_with_clean_paths()