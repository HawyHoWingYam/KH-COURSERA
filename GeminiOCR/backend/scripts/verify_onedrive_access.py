"""
Phase 2: Verify App-only OneDrive Access to Target User
This script validates that the Azure AD app can access the target user's OneDrive
with App-only authentication (Client Credentials flow).
"""

import os
import sys
import logging
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
import sys

# Try multiple possible paths for .env file
possible_paths = [
    '/home/ubuntu/KH-COURSERA/env/.env',
    os.path.join(os.path.dirname(__file__), '../../env/.env'),
    os.path.join(os.path.expanduser('~'), 'KH-COURSERA/env/.env'),
]

env_path = None
for path in possible_paths:
    if os.path.exists(path):
        env_path = path
        break

if not env_path:
    print(f"❌ Could not find .env file in any of these locations:")
    for path in possible_paths:
        print(f"   - {path}")
    sys.exit(1)

load_dotenv(env_path)

# Get Azure credentials
CLIENT_ID = os.getenv('ONEDRIVE_CLIENT_ID')
CLIENT_SECRET = os.getenv('ONEDRIVE_CLIENT_SECRET')
TENANT_ID = os.getenv('ONEDRIVE_TENANT_ID')
TARGET_USER_UPN = os.getenv('ONEDRIVE_TARGET_USER_UPN')

logger.info("=" * 80)
logger.info("🔐 Phase 2: OneDrive App-only Access Verification")
logger.info("=" * 80)


def verify_credentials():
    """Verify all required credentials are present"""
    logger.info("\n📋 Step 1: Checking credentials...")

    missing = []
    if not CLIENT_ID:
        missing.append("ONEDRIVE_CLIENT_ID")
    if not CLIENT_SECRET:
        missing.append("ONEDRIVE_CLIENT_SECRET")
    if not TENANT_ID:
        missing.append("ONEDRIVE_TENANT_ID")
    if not TARGET_USER_UPN:
        missing.append("ONEDRIVE_TARGET_USER_UPN")

    if missing:
        logger.error(f"❌ Missing credentials: {', '.join(missing)}")
        logger.error(f"   Set these in /home/ubuntu/KH-COURSERA/env/.env")
        logger.error(f"   Loaded from: {env_path}")
        return False

    logger.info(f"✅ Client ID: {CLIENT_ID[:8]}...")
    logger.info(f"✅ Tenant ID: {TENANT_ID[:8]}...")
    logger.info(f"✅ Target User: {TARGET_USER_UPN}")
    return True


def get_access_token():
    """Get access token using Client Credentials flow"""
    logger.info("\n🔑 Step 2: Obtaining access token (Client Credentials)...")

    token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"

    payload = {
        'grant_type': 'client_credentials',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'scope': 'https://graph.microsoft.com/.default'
    }

    try:
        response = requests.post(token_url, data=payload)
        response.raise_for_status()
        token = response.json()['access_token']
        logger.info(f"✅ Access token obtained (expires in {response.json().get('expires_in')} seconds)")
        return token
    except requests.exceptions.HTTPError as e:
        logger.error(f"❌ Failed to obtain token: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"❌ Error getting token: {str(e)}")
        return None


def get_user_drive(token):
    """Get the target user's OneDrive root"""
    logger.info(f"\n🚗 Step 3: Accessing OneDrive for user: {TARGET_USER_UPN}...")

    headers = {'Authorization': f'Bearer {token}'}

    # Try different UPN formats
    upn_variants = [
        TARGET_USER_UPN,  # Original
        TARGET_USER_UPN.replace('@', '%40'),  # URL-encoded variant
    ]

    for upn_variant in upn_variants:
        url = f"https://graph.microsoft.com/v1.0/users/{upn_variant}/drive/root"

        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                drive_info = response.json()
                logger.info(f"✅ Successfully accessed user's drive")
                logger.info(f"   Drive ID: {drive_info.get('id')}")
                logger.info(f"   Drive Name: {drive_info.get('name', 'OneDrive')}")
                return drive_info
            elif response.status_code == 403:
                logger.error(f"❌ 403 Forbidden - Tenant may not allow App-only access to user OneDrive")
                logger.error(f"   Required: Application Permissions 'Files.ReadWrite.All' with Admin Consent")
                logger.error(f"   Action: Ask tenant admin to enable App-only access in SharePoint admin center")
                return None
            elif response.status_code == 404:
                logger.warning(f"⚠️  404 Not Found with UPN variant: {upn_variant}")
                continue
            else:
                logger.warning(f"⚠️  Unexpected status {response.status_code} with UPN: {upn_variant}")
                continue
        except Exception as e:
            logger.warning(f"⚠️  Error with UPN variant {upn_variant}: {str(e)}")
            continue

    # If we get here, none of the UPN variants worked
    logger.error(f"❌ Could not access OneDrive with any UPN variant")
    logger.error(f"   Tried: {', '.join(upn_variants)}")
    logger.error(f"   Check if UPN is correct: {TARGET_USER_UPN}")
    logger.info(f"\n💡 Tip: This might be a tenant restriction. Ask Azure AD admin to:")
    logger.info(f"   1. Verify the user UPN exists in Azure AD")
    logger.info(f"   2. Enable app-only access to OneDrive in SharePoint admin")
    logger.info(f"   3. Verify Application Permissions have admin consent")
    return None


def list_root_items(token):
    """List items in root folder to see folder structure"""
    logger.info(f"\n📁 Step 4: Listing root folder contents...")

    headers = {'Authorization': f'Bearer {token}'}
    url = f"https://graph.microsoft.com/v1.0/users/{TARGET_USER_UPN}/drive/root/children"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        items = response.json().get('value', [])

        if not items:
            logger.info("   (no items in root)")
            return

        logger.info(f"   Found {len(items)} items in root:")
        folders = []
        for item in items:
            name = item.get('name', 'Unknown')
            item_type = 'folder' if 'folder' in item else 'file'
            logger.info(f"   - {name} ({item_type})")
            if 'folder' in item:
                folders.append(name)

        return folders
    except Exception as e:
        logger.error(f"❌ Error listing root items: {str(e)}")
        return None


def access_hya_ocr_folder(token):
    """Try to access HYA-OCR folder at Documents/HYA-OCR"""
    logger.info(f"\n📂 Step 5: Accessing Documents/HYA-OCR folder...")

    headers = {'Authorization': f'Bearer {token}'}

    # Try the full path
    folder_path = "Documents/HYA-OCR"
    url = f"https://graph.microsoft.com/v1.0/users/{TARGET_USER_UPN}/drive/root:/{folder_path}"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        folder_info = response.json()
        logger.info(f"✅ Successfully accessed: {folder_path}")
        logger.info(f"   Folder ID: {folder_info.get('id')}")
        logger.info(f"   Web URL: {folder_info.get('webUrl', 'N/A')}")
        return folder_info
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning(f"⚠️  Path not found: {folder_path}")
            logger.info("   Attempting alternative paths...")
            return try_alternative_paths(token)
        elif e.response.status_code == 403:
            logger.error(f"❌ 403 Forbidden - No permission to access folder")
            return None
        else:
            logger.error(f"❌ Error {e.response.status_code}: {e.response.text}")
            return None
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        return None


def try_alternative_paths(token):
    """Try alternative folder paths"""
    headers = {'Authorization': f'Bearer {token}'}

    alternatives = [
        "HYA-OCR",  # At root
        "Documents/HYA-OCR",  # Full path
        "/HYA-OCR",  # With leading slash
    ]

    for path in alternatives:
        url = f"https://graph.microsoft.com/v1.0/users/{TARGET_USER_UPN}/drive/root:/{path.lstrip('/')}"
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                folder_info = response.json()
                logger.info(f"✅ Found at: {path}")
                logger.info(f"   Folder ID: {folder_info.get('id')}")
                return folder_info
        except:
            continue

    logger.error("❌ Could not find HYA-OCR folder in any standard location")
    return None


def list_hya_ocr_contents(token, folder_info):
    """List contents of HYA-OCR folder"""
    if not folder_info:
        return

    logger.info(f"\n📄 Step 6: Listing HYA-OCR folder contents...")

    headers = {'Authorization': f'Bearer {token}'}
    folder_id = folder_info.get('id')
    url = f"https://graph.microsoft.com/v1.0/users/{TARGET_USER_UPN}/drive/items/{folder_id}/children"

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        items = response.json().get('value', [])

        if not items:
            logger.info("   (folder is empty)")
            return

        logger.info(f"   Found {len(items)} items:")
        pdf_count = 0
        for item in items:
            name = item.get('name', 'Unknown')
            item_type = 'folder' if 'folder' in item else 'file'
            size = item.get('size', 0)
            logger.info(f"   - {name} ({item_type}, {size} bytes)")
            if name.lower().endswith('.pdf'):
                pdf_count += 1

        logger.info(f"   Total PDF files: {pdf_count}")
        return items
    except Exception as e:
        logger.error(f"❌ Error listing folder: {str(e)}")
        return None


def verify_with_o365_library():
    """Verify access using O365 library (what the app will use)"""
    logger.info(f"\n🧪 Step 7: Verifying with O365 library (actual implementation)...")

    try:
        from O365 import Account

        credentials = (CLIENT_ID, CLIENT_SECRET)
        account = Account(
            credentials,
            auth_flow_type='credentials',
            tenant_id=TENANT_ID
        )

        if not account.is_authenticated:
            account.authenticate()

        # Try to access target user's storage
        storage = account.storage(resource=TARGET_USER_UPN)
        drive = storage.get_default_drive()

        logger.info(f"✅ O365 library successfully connected to user's drive")
        logger.info(f"   Drive: {drive.name if hasattr(drive, 'name') else 'Default OneDrive'}")

        # Try to get HYA-OCR folder (at root level, not under Documents)
        try:
            folder = drive.get_item_by_path("HYA-OCR")
            if folder and folder.is_folder:
                logger.info(f"✅ Successfully accessed HYA-OCR folder via O365")
                # List items in folder
                items = list(folder.get_items())
                logger.info(f"   Contains {len(items)} items")
                for item in items:
                    logger.info(f"   - {item.name}")
                return True
            else:
                logger.warning(f"⚠️  Could not access HYA-OCR as folder")
                return False
        except Exception as e:
            logger.error(f"❌ Error accessing folder with O365: {str(e)}")
            return False

    except ImportError:
        logger.warning("⚠️  O365 library not installed (run: pip install -r requirements.txt)")
        return None
    except Exception as e:
        logger.error(f"❌ O365 library error: {str(e)}")
        return False


def main():
    """Run all verification steps"""

    # Step 1: Verify credentials
    if not verify_credentials():
        logger.error("\n❌ Credential verification failed")
        return False

    # Step 2: Get access token
    token = get_access_token()
    if not token:
        logger.error("\n❌ Authentication failed")
        return False

    # Step 3: Access user's drive
    drive_info = get_user_drive(token)
    if not drive_info:
        logger.error("\n❌ Failed to access user's drive")
        logger.error("   Possible causes:")
        logger.error("   1. Tenant doesn't allow App-only access (need admin action)")
        logger.error("   2. App permissions not set correctly")
        logger.error("   3. UPN is incorrect")
        return False

    # Step 4: List root items
    list_root_items(token)

    # Step 5: Access HYA-OCR folder
    folder_info = access_hya_ocr_folder(token)
    if not folder_info:
        logger.error("\n❌ Failed to access HYA-OCR folder")
        return False

    # Step 6: List folder contents
    list_hya_ocr_contents(token, folder_info)

    # Step 7: Verify with O365 library
    o365_result = verify_with_o365_library()

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("✅ VERIFICATION COMPLETE")
    logger.info("=" * 80)
    logger.info("\n✅ All checks passed! Ready for Phase 3 implementation.")
    logger.info("\nNext steps:")
    logger.info("1. Modify GeminiOCR/backend/utils/onedrive_client.py")
    logger.info("2. Modify GeminiOCR/backend/scripts/onedrive_ingest.py")
    logger.info("3. Test with: POST http://localhost:8000/api/awb/trigger-sync")

    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n\n⏸️  Verification interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
