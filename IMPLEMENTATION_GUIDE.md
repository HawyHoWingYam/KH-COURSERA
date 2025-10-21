# B1 App-only OneDrive Integration - Implementation Complete

## ✅ What Has Been Implemented

### 1. **Verification Script Created**
- **File:** `GeminiOCR/backend/scripts/verify_onedrive_access.py`
- **Purpose:** Tests app-only authentication and OneDrive folder access
- **Tests:**
  - ✅ Azure AD credentials validation
  - ✅ Client Credentials flow (app-only token)
  - ✅ Access to target user's OneDrive (hawy_ho@hyakunousha.com)
  - ✅ Folder structure discovery
  - ✅ Documents/HYA-OCR folder access
  - ✅ O365 library integration test

### 2. **OneDrive Client Modified**
- **File:** `GeminiOCR/backend/utils/onedrive_client.py`
- **Changes:**
  - ✅ Added `target_user_upn` parameter to `__init__()` (line 19)
  - ✅ Updated `connect()` method to use `account.storage(resource=upn)` for app-only access (line 61-68)
  - ✅ Maintains backward compatibility (optional parameter)

### 3. **Sync Script Updated**
- **File:** `GeminiOCR/backend/scripts/onedrive_ingest.py`
- **Changes:**
  - ✅ Added `ONEDRIVE_TARGET_USER_UPN` environment variable reading (line 27)
  - ✅ Pass `target_user_upn` to OneDriveClient (line 56)

### 4. **Environment Configuration**
- **File:** `env/.env.development`
- **Status:** ✅ Configured with:
  - ✅ Client ID: `7f3aeda8-6218-44c7-a564-3c7cb3084bf3`
  - ✅ Tenant ID: `3f2232b2-1a12-45aa-8631-4fcd3945c768`
  - ✅ Target User: `hawy_ho@hyakunousha.com`
  - ✅ Folder Path: `Documents/HYA-OCR`
  - ⚠️  **IMPORTANT:** Client secret needs to be updated (see Security Section)

---

## 🚨 SECURITY - IMMEDIATE ACTION REQUIRED

**The original client secret has been exposed and MUST be rotated:**

### Step 1: Rotate Client Secret in Azure
1. Open [Azure Portal](https://portal.azure.com)
2. Go to Azure Active Directory → App Registrations
3. Find app: `7f3aeda8-6218-44c7-a564-3c7cb3084bf3`
4. Click "Certificates & secrets"
5. Under "Client secrets", delete the old secret (the exposed one)
6. Click "+ New client secret"
7. Set expiration (e.g., 12 months)
8. Copy the new secret value

### Step 2: Update Environment
```bash
# Edit /home/ubuntu/KH-COURSERA/env/.env
# Find lines 123 and 127
ONEDRIVE_CLIENT_SECRET=<NEW_SECRET_VALUE>
ONEDRIVE_SECRET_VALUE=<NEW_SECRET_VALUE>
```

### Step 3: Verify
```bash
# Never commit secrets to git
git status  # Ensure .env is not staged
```

---

## 🧪 Phase 2: Verification Testing

### Prerequisites
- ✅ Azure AD app has Application Permissions:
  - `Files.ReadWrite.All` (with Admin Consent)
  - `Sites.ReadWrite.All` (recommended, with Admin Consent)
- ✅ Tenant allows App-only access to user OneDrive
- ✅ Rotated client secret in Azure
- ✅ Updated `.env` with new secret

### Run Verification Script

**Local Testing:**
```bash
cd /home/ubuntu/KH-COURSERA/GeminiOCR/backend

# Activate conda environment
conda activate gemini-sandbox

# Run verification
python scripts/verify_onedrive_access.py
```

**Expected Output:**
```
🔐 Phase 2: OneDrive App-only Access Verification
================================================================================

📋 Step 1: Checking credentials...
✅ Client ID: 7f3aeda8...
✅ Tenant ID: 3f2232b2...
✅ Target User: hawy_ho@hyakunousha.com

🔑 Step 2: Obtaining access token (Client Credentials)...
✅ Access token obtained (expires in 3599 seconds)

🚗 Step 3: Accessing OneDrive for user: hawy_ho@hyakunousha.com...
✅ Successfully accessed user's drive

📁 Step 4: Listing root folder contents...
   Found 2 items in root:
   - Documents (folder)
   - OneDrive (folder)

📂 Step 5: Accessing Documents/HYA-OCR folder...
✅ Successfully accessed: Documents/HYA-OCR
   Folder ID: xxxxxxxxxxxxx
   Web URL: https://...

📄 Step 6: Listing HYA-OCR folder contents...
   Found N items:
   - file1.pdf (file, 1234567 bytes)
   - file2.pdf (file, 2345678 bytes)

🧪 Step 7: Verifying with O365 library (actual implementation)...
✅ O365 library successfully connected to user's drive
✅ Successfully accessed Documents/HYA-OCR folder via O365

✅ VERIFICATION COMPLETE
================================================================================
✅ All checks passed! Ready for Phase 3 implementation.
```

### Troubleshooting

**403 Forbidden Error**
```
❌ 403 Forbidden - Tenant may not allow App-only access to user OneDrive
   Required: Application Permissions 'Files.ReadWrite.All' with Admin Consent
```
**Solution:** Ask tenant admin to enable App-only access in SharePoint admin center

**404 Not Found Error**
```
❌ 404 Not Found - User OneDrive not found
   Check if UPN is correct: hawy_ho@hyakunousha.com
```
**Solution:** Verify UPN is correct in Azure AD Users

**Authentication Failed**
```
❌ Failed to obtain token: 401 - unauthorized_client
```
**Solution:** Verify client secret was rotated correctly in Azure Portal

---

## 🚀 Phase 3: Local Backend Testing

### Start Backend with OneDrive Sync

```bash
cd /home/ubuntu/KH-COURSERA/GeminiOCR/backend

# Activate environment
conda activate gemini-sandbox

# Set AWS credentials
export AWS_ACCESS_KEY_ID=<YOUR_AWS_ACCESS_KEY>
export AWS_SECRET_ACCESS_KEY=<YOUR_AWS_SECRET_KEY>
export AWS_DEFAULT_REGION=ap-southeast-1

# Start backend
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### Check APScheduler Startup

**Look for logs:**
```
✅ APScheduler started - OneDrive sync scheduled for 2:00 AM daily
✅ Connected to OneDrive (app-only mode for user: hawy_ho@hyakunousha.com)
```

### Test Manual Sync Trigger

```bash
# Trigger sync
curl -X POST http://localhost:8000/api/awb/trigger-sync

# Expected response:
{
  "success": true,
  "message": "OneDrive sync triggered in background"
}
```

### Check Sync Status

```bash
# Get sync history
curl http://localhost:8000/api/awb/sync-status

# Expected response:
{
  "success": true,
  "syncs": [
    {
      "sync_id": 1,
      "last_sync_time": "2025-10-21T12:34:56.789123",
      "sync_status": "success",
      "files_processed": 5,
      "files_failed": 0,
      "error_message": null,
      "created_at": "2025-10-21T12:34:56.789123",
      "metadata": {
        "s3_prefix": "upload/onedrive/airway-bills",
        "onedrive_folder": "Documents/HYA-OCR"
      }
    }
  ]
}
```

### Verify S3 Upload

```bash
# Check S3 for uploaded files
aws s3 ls s3://hya-ocr-sandbox/upload/onedrive/airway-bills/ --recursive

# Expected:
2025-10-21 12:35:00       1234567 upload/onedrive/airway-bills/2025/10/21/file1.pdf
2025-10-21 12:35:01       2345678 upload/onedrive/airway-bills/2025/10/21/file2.pdf
```

### Verify Database

```bash
# Check OneDriveSync table
# Connect to database and run:
SELECT * FROM onedrive_sync ORDER BY created_at DESC LIMIT 5;

# Expected columns:
# sync_id | last_sync_time | sync_status | files_processed | files_failed | error_message | sync_metadata
```

---

## 🐳 Phase 4: Docker Deployment

### Build Docker Image

```bash
cd /home/ubuntu/KH-COURSERA

# Build backend image
docker build -f docker/backend.Dockerfile -t geminiocr-backend:latest .

# Verify build
docker images | grep geminiocr-backend
```

### Deploy with Docker Compose

```bash
# Start services
docker compose -f GeminiOCR/docker-compose.simple.yml up -d

# Check status
docker compose -f GeminiOCR/docker-compose.simple.yml ps

# View logs
docker compose -f GeminiOCR/docker-compose.simple.yml logs -f backend
```

### Test Docker Deployment

```bash
# Health check
curl http://localhost:8000/health

# Trigger sync
curl -X POST http://localhost:8000/api/awb/trigger-sync

# Check status
curl http://localhost:8000/api/awb/sync-status
```

---

## ✅ Acceptance Criteria Checklist

- [ ] Verification script runs successfully (Phase 2)
- [ ] Can list Documents/HYA-OCR folder contents
- [ ] No 403 Forbidden or 404 Not Found errors
- [ ] Backend starts with "APScheduler started" message
- [ ] Manual sync trigger works: `POST /api/awb/trigger-sync`
- [ ] Sync status shows files processed: `GET /api/awb/sync-status`
- [ ] Files uploaded to S3: `s3://hya-ocr-sandbox/upload/onedrive/airway-bills/`
- [ ] OneDriveSync table records created
- [ ] Files not duplicated on repeated syncs (source_path deduplication)
- [ ] Scheduled sync registered for 2:00 AM daily
- [ ] Docker deployment produces same results as local

---

## 📝 Code Changes Summary

### Modified Files

1. **`GeminiOCR/backend/utils/onedrive_client.py`**
   - Added `target_user_upn` parameter (line 19)
   - Updated `connect()` to use `account.storage(resource=upn)` (line 61-68)

2. **`GeminiOCR/backend/scripts/onedrive_ingest.py`**
   - Added `ONEDRIVE_TARGET_USER_UPN` environment reading (line 27)
   - Pass `target_user_upn` to client (line 56)

3. **`env/.env.development`**
   - Updated `ONEDRIVE_SHARED_FOLDER_PATH` to `Documents/HYA-OCR` (line 133)

### New Files

1. **`GeminiOCR/backend/scripts/verify_onedrive_access.py`**
   - Phase 2 verification script with 7 verification steps

---

## 🔄 Next Steps

1. **Rotate Client Secret** (SECURITY)
   - Update Azure AD App registration
   - Update `.env` with new secret

2. **Run Verification**
   - Execute `python scripts/verify_onedrive_access.py`
   - Confirm all 7 steps pass

3. **Test Locally**
   - Start backend
   - Trigger manual sync
   - Verify S3 upload and DB records

4. **Test Docker**
   - Build image
   - Deploy with docker-compose
   - Verify end-to-end

5. **Monitor Production**
   - Scheduled sync runs at 2:00 AM daily
   - Monitor CloudWatch logs for errors
   - Check OneDriveSync table for sync history

---

## 📚 Architecture Reference

**App-only Authentication Flow:**
```
Azure AD App (7f3aeda8...)
    ↓
Client Credentials (client_id + client_secret)
    ↓
Access Token (scope: https://graph.microsoft.com/.default)
    ↓
O365 Library: account.storage(resource="hawy_ho@hyakunousha.com")
    ↓
Target User's OneDrive Drive
    ↓
Documents/HYA-OCR Folder
    ↓
List PDF files → Download → S3 Upload → Move to 已处理
```

**Key Insight:** O365 library already supports app-only access to specific user's OneDrive via the `resource` parameter. No need for direct Microsoft Graph API calls.

---

## 📞 Support

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| 403 Forbidden | Tenant blocks app-only access | Ask admin to enable in SharePoint admin |
| 404 Not Found | Folder path incorrect | Run verification script to find path |
| Auth fails | Invalid secret | Rotate secret in Azure Portal |
| Import error | O365 not installed | `pip install -r requirements.txt` |
| No APScheduler | Not installed | `pip install APScheduler==3.10.4` |

### Verification Logs

Check backend logs for success indicators:
```bash
# Look for these messages:
✅ APScheduler started
✅ Connected to OneDrive (app-only mode for user: hawy_ho@hyakunousha.com)
✅ Successfully obtained drive object
✅ Found folder: Documents/HYA-OCR
✅ Uploaded to S3
✅ Moved to processed folder
```

---

Generated: 2025-10-21
Status: ✅ Implementation Complete - Ready for Phase 2 Verification
