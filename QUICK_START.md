# 🚀 B1 OneDrive Integration - Quick Start

## ⚠️ STEP 1: Rotate Client Secret (5 min) - DO THIS FIRST!

```bash
# 1. Go to Azure Portal: https://portal.azure.com
# 2. Azure Active Directory → App Registrations
# 3. Find: 7f3aeda8-6218-44c7-a564-3c7cb3084bf3
# 4. Certificates & secrets → Delete old secret
# 5. Create new secret → Copy value
# 6. Update file:
# Edit: /home/ubuntu/KH-COURSERA/env/.env
# Lines 123, 127: ONEDRIVE_CLIENT_SECRET=<NEW_VALUE>
```

---

## ✅ STEP 2: Run Verification (5 min)

```bash
cd /home/ubuntu/KH-COURSERA/GeminiOCR/backend
conda activate gemini-sandbox
python scripts/verify_onedrive_access.py
```

**Expected result:** ✅ All checks passed!

---

## 🧪 STEP 3: Test Local Backend (10 min)

```bash
# Terminal 1: Start backend
cd /home/ubuntu/KH-COURSERA/GeminiOCR/backend
conda activate gemini-sandbox
export AWS_ACCESS_KEY_ID=<YOUR_AWS_ACCESS_KEY>
export AWS_SECRET_ACCESS_KEY=<YOUR_AWS_SECRET_KEY>
export AWS_DEFAULT_REGION=ap-southeast-1
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Test endpoints
curl -X POST http://localhost:8000/api/awb/trigger-sync
curl http://localhost:8000/api/awb/sync-status
aws s3 ls s3://hya-ocr-sandbox/upload/onedrive/airway-bills/ --recursive
```

---

## 🐳 STEP 4: Test Docker (5 min)

```bash
cd /home/ubuntu/KH-COURSERA
docker build -f docker/backend.Dockerfile -t geminiocr-backend:latest .
docker compose -f GeminiOCR/docker-compose.simple.yml up -d
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/awb/trigger-sync
```

---

## 📝 Implementation Summary

**What was done:**
- ✅ Created `GeminiOCR/backend/scripts/verify_onedrive_access.py`
- ✅ Modified `GeminiOCR/backend/utils/onedrive_client.py` (lines 19, 34, 61-68)
- ✅ Modified `GeminiOCR/backend/scripts/onedrive_ingest.py` (lines 27, 56)
- ✅ Updated `env/.env.development` (line 133)
- ✅ Created complete documentation

**How it works:**
1. App-only authentication (Client Credentials)
2. Access target user's OneDrive: `hawy_ho@hyakunousha.com`
3. Read files from: `Documents/HYA-OCR`
4. Upload to S3: `upload/onedrive/airway-bills/`
5. Move files to: `已处理` (processed folder)

**Key files:**
- `IMPLEMENTATION_GUIDE.md` - Complete testing guide
- `ONEDRIVE_IMPLEMENTATION_SUMMARY.md` - Detailed summary
- `QUICK_START.md` - This file

---

## 🔑 Environment Variables

```bash
# In /home/ubuntu/KH-COURSERA/env/.env or env/.env.development
ONEDRIVE_SYNC_ENABLED=true
ONEDRIVE_CLIENT_ID=7f3aeda8-6218-44c7-a564-3c7cb3084bf3
ONEDRIVE_CLIENT_SECRET=<ROTATE_THIS>            # ⚠️ UPDATE NOW
ONEDRIVE_TENANT_ID=3f2232b2-1a12-45aa-8631-4fcd3945c768
ONEDRIVE_TARGET_USER_UPN=hawy_ho@hyakunousha.com
ONEDRIVE_SHARED_FOLDER_PATH=Documents/HYA-OCR
ONEDRIVE_PROCESSED_FOLDER=已处理
AWB_S3_PREFIX=upload/onedrive/airway-bills
```

---

## 🎯 Success Indicators

Look for these in logs:
```
✅ APScheduler started - OneDrive sync scheduled for 2:00 AM daily
✅ Connected to OneDrive (app-only mode for user: hawy_ho@hyakunousha.com)
✅ Successfully obtained drive object
✅ Found folder: Documents/HYA-OCR
✅ OneDrive sync completed: N processed, 0 failed
```

---

## ❌ Common Issues

| Issue | Fix |
|-------|-----|
| 403 Forbidden | Ask admin to enable App-only access in SharePoint |
| 404 Not Found | Check folder path with verification script |
| Secret invalid | Rotate in Azure Portal |
| O365 import error | `pip install -r requirements.txt` |

---

## 📞 Get Help

- Full guide: `IMPLEMENTATION_GUIDE.md`
- Detailed summary: `ONEDRIVE_IMPLEMENTATION_SUMMARY.md`
- Verification script: `GeminiOCR/backend/scripts/verify_onedrive_access.py`

---

**Estimated total time: 30 minutes** ⏱️

Start with Step 1! 🎬
