# B1 App-only OneDrive Integration - Implementation Summary

**Status:** ✅ **COMPLETE - Ready for Phase 2 Testing**

**Date:** 2025-10-21
**Implementation Time:** Completed
**Target User:** hawy_ho@hyakunousha.com
**Folder:** Documents/HYA-OCR

---

## 📋 What Was Implemented

### 1️⃣ Created Verification Script
**File:** `GeminiOCR/backend/scripts/verify_onedrive_access.py` (NEW)

This script validates the complete setup before running the actual sync:
- Tests app-only authentication with Client Credentials flow
- Verifies access to target user's OneDrive
- Lists folder structure
- Tests Documents/HYA-OCR access
- Tests O365 library integration
- Provides detailed error messages for troubleshooting

### 2️⃣ Modified OneDrive Client
**File:** `GeminiOCR/backend/utils/onedrive_client.py`

**Changes:**
- ✅ Line 19: Added `target_user_upn` parameter to `__init__()`
- ✅ Line 34: Store `target_user_upn` as instance variable
- ✅ Lines 61-68: Updated `connect()` method to use:
  ```python
  if self.target_user_upn:
      self.storage = self.account.storage(resource=self.target_user_upn)
  else:
      self.storage = self.account.storage()
  ```

**Key Innovation:** Uses O365 library's built-in support for `account.storage(resource=upn)` - no direct Graph API needed!

### 3️⃣ Updated Sync Script
**File:** `GeminiOCR/backend/scripts/onedrive_ingest.py`

**Changes:**
- ✅ Line 27: Added `ONEDRIVE_TARGET_USER_UPN` environment variable reading
- ✅ Line 56: Pass `target_user_upn=ONEDRIVE_TARGET_USER_UPN` to OneDriveClient

### 4️⃣ Updated Environment
**File:** `env/.env.development`

**Changes:**
- ✅ Line 133: Updated folder path to `Documents/HYA-OCR` (was `Documents/AWB`)

**Current Configuration:**
```bash
ONEDRIVE_SYNC_ENABLED=true
ONEDRIVE_CLIENT_ID=7f3aeda8-6218-44c7-a564-3c7cb3084bf3
ONEDRIVE_CLIENT_SECRET=<ROTATED_SECRET_VALUE>  ⚠️ NEEDS ROTATION
ONEDRIVE_TENANT_ID=3f2232b2-1a12-45aa-8631-4fcd3945c768
ONEDRIVE_TARGET_USER_UPN=hawy_ho@hyakunousha.com
ONEDRIVE_SHARED_FOLDER_PATH=Documents/HYA-OCR
ONEDRIVE_PROCESSED_FOLDER=已处理
AWB_S3_PREFIX=upload/onedrive/airway-bills
```

---

## 🚨 CRITICAL: Secret Rotation Required

**⚠️ WARNING:** The client secret has been exposed in this conversation.

### Immediate Actions:
1. **In Azure Portal:**
   - Go to Azure AD → App Registrations
   - Find app `7f3aeda8-6218-44c7-a564-3c7cb3084bf3`
   - Delete the old secret
   - Create a new client secret
   - Copy the new value

2. **Update `.env` file:**
   ```bash
   # Edit /home/ubuntu/KH-COURSERA/env/.env (lines 123, 127)
   ONEDRIVE_CLIENT_SECRET=<NEW_SECRET_VALUE>
   ONEDRIVE_SECRET_VALUE=<NEW_SECRET_VALUE>
   ```

3. **Verify:**
   ```bash
   cd /home/ubuntu/KH-COURSERA
   git status  # Ensure .env is not staged
   ```

---

## ✅ Ready for Phase 2: Testing

### Step 1: Verify Credentials

```bash
cd /home/ubuntu/KH-COURSERA/GeminiOCR/backend
conda activate gemini-sandbox
python scripts/verify_onedrive_access.py
```

This will test:
1. ✅ Credentials are valid
2. ✅ Client Credentials flow works
3. ✅ Can access user's OneDrive
4. ✅ Can access Documents/HYA-OCR folder
5. ✅ O365 library integration works

**Expected Success:**
```
✅ All checks passed! Ready for Phase 3 implementation.
```

### Step 2: Start Backend

```bash
cd /home/ubuntu/KH-COURSERA/GeminiOCR/backend

# Activate conda
conda activate gemini-sandbox

# Set AWS credentials
export AWS_ACCESS_KEY_ID=<YOUR_AWS_ACCESS_KEY>
export AWS_SECRET_ACCESS_KEY=<YOUR_AWS_SECRET_KEY>
export AWS_DEFAULT_REGION=ap-southeast-1

# Start backend
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

**Look for in logs:**
```
✅ APScheduler started - OneDrive sync scheduled for 2:00 AM daily
✅ Connected to OneDrive (app-only mode for user: hawy_ho@hyakunousha.com)
```

### Step 3: Test Manual Sync

```bash
# In another terminal:
curl -X POST http://localhost:8000/api/awb/trigger-sync

# Response:
{
  "success": true,
  "message": "OneDrive sync triggered in background"
}
```

### Step 4: Check Sync Status

```bash
curl http://localhost:8000/api/awb/sync-status

# Response should show successful sync:
{
  "success": true,
  "syncs": [
    {
      "sync_status": "success",
      "files_processed": N,
      "files_failed": 0
    }
  ]
}
```

### Step 5: Verify S3 Upload

```bash
# Check files uploaded to S3
aws s3 ls s3://hya-ocr-sandbox/upload/onedrive/airway-bills/ --recursive

# Should see files organized by date:
2025-10-21 12:35:00       1234567 upload/onedrive/airway-bills/2025/10/21/file1.pdf
```

---

## 🐳 Docker Deployment

Once local testing passes:

```bash
cd /home/ubuntu/KH-COURSERA

# Build image
docker build -f docker/backend.Dockerfile -t geminiocr-backend:latest .

# Deploy
docker compose -f GeminiOCR/docker-compose.simple.yml up -d

# Test
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/awb/trigger-sync
```

---

## 📊 Success Metrics

✅ **Phase 2 (Verification):**
- [ ] Verification script runs without errors
- [ ] All 7 verification steps pass
- [ ] Can list Documents/HYA-OCR contents

✅ **Phase 3 (Local Testing):**
- [ ] Backend starts with APScheduler message
- [ ] Manual sync trigger works
- [ ] Files appear in S3
- [ ] OneDriveSync table has records
- [ ] No duplicate files on second sync

✅ **Phase 4 (Docker):**
- [ ] Docker image builds successfully
- [ ] Docker deployment passes all same tests
- [ ] End-to-end flow works

---

## 📚 Implementation Files

### Files Modified (3)
```
GeminiOCR/backend/utils/onedrive_client.py     ✅ Added target_user_upn parameter
GeminiOCR/backend/scripts/onedrive_ingest.py   ✅ Pass target_user_upn to client
env/.env.development                            ✅ Updated folder path
```

### Files Created (2)
```
GeminiOCR/backend/scripts/verify_onedrive_access.py  ✅ Verification script
IMPLEMENTATION_GUIDE.md                              ✅ Complete guide
```

### Files Not Modified
```
GeminiOCR/backend/app.py                    ✅ Already has scheduler & endpoints
GeminiOCR/backend/db/models.py              ✅ OneDriveSync model exists
GeminiOCR/backend/requirements.txt           ✅ O365 and APScheduler included
```

---

## 🔑 Key Technical Details

### Architecture
```
┌─────────────────────┐
│  OneDrive (User)    │
│  hawy_ho@...        │
│  /Documents/HYA-OCR │
└──────────┬──────────┘
           │
           │ App-only auth (Client Credentials)
           │
┌──────────▼──────────┐
│   O365 Library      │
│ account.storage()   │
│  (resource=upn)     │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  Backend API        │
│  /api/awb/          │
│  trigger-sync       │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  S3 Bucket          │
│  upload/onedrive/   │
│  airway-bills/      │
└─────────────────────┘
```

### Authentication Flow
1. **Client Credentials** (App-only): Uses client_id + client_secret
2. **No user interaction** needed - fully automated
3. **Tenant admin approval** required (Application Permissions)
4. **O365 library handles** Microsoft Graph API calls

### Deduplication
- Uses `source_path` field in File table
- Format: `onedrive://{drive_id}/{item_id}`
- Same file won't be processed twice

---

## 🚀 Next Immediate Actions

### 1. **PRIORITY: Rotate Secret** (5 min)
   - Go to Azure Portal
   - Create new client secret
   - Update `.env`

### 2. **Run Verification** (5 min)
   ```bash
   python GeminiOCR/backend/scripts/verify_onedrive_access.py
   ```

### 3. **Test Local** (10 min)
   - Start backend
   - Trigger sync
   - Check S3 and DB

### 4. **Test Docker** (5 min)
   - Build image
   - Deploy with compose
   - Verify results

---

## 📞 Troubleshooting

### 403 Forbidden
```
Error: 403 Forbidden - Tenant may not allow App-only access
```
**Solution:** Ask Azure AD admin to enable App-only access in SharePoint admin center

### 404 Not Found
```
Error: 404 Not Found - Could not find HYA-OCR folder
```
**Solution:** Verify folder path with verification script, check OneDrive web UI

### Import Error
```
Error: from O365 import Account - ModuleNotFoundError
```
**Solution:** `pip install -r GeminiOCR/backend/requirements.txt`

---

## 📖 Documentation

For complete details, see:
- **Main Guide:** `IMPLEMENTATION_GUIDE.md`
- **Code Changes:** See modified files listed above
- **Architecture:** Documented in this summary

---

## ✨ Summary

**What was done:**
- ✅ Created verification script for Phase 2 testing
- ✅ Modified client to support app-only + user access
- ✅ Updated sync script to use target user
- ✅ Configured environment with correct folder path
- ✅ Created comprehensive implementation guide

**What's next:**
1. Rotate client secret (CRITICAL)
2. Run verification script
3. Test locally
4. Test with Docker
5. Deploy to production

**Estimated time to completion:** ~30 minutes (including secret rotation)

---

Generated: 2025-10-21
Status: ✅ Implementation Complete
Next Phase: Phase 2 Verification
