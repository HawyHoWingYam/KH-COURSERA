HYA-OCR Backend S3/DB Alignment Runbook

Overview
- Goal: unifying storage paths and DB references to the ID-based scheme
- Mandatory env: use backend/backend.env (S3 + DB + region)

Key Standards
- Prompts/Schemas: companies/{company_id}/{prompts|schemas}/{doc_type_id}/{config_id}/{filename}
- Order Uploads:   upload/orders/{order_id}/items/{item_id}/{timestamp}_{uuid}_{filename}
- Results:         results/orders/{...}
- AWB Monthly:     upload/onedrive/airway-bills/YYYY/MM/{filename}.pdf
- Backups:         backups/

Scripts (run from ref/ directory)
- Audit:   python s3_audit.py --bucket $S3_BUCKET_NAME --region $AWS_DEFAULT_REGION
- Migrate: python migrate_prompts_schemas_to_id.py --bucket $S3_BUCKET_NAME --apply
- Cleanup: python s3_prefix_cleanup.py --bucket $S3_BUCKET_NAME --apply

Recommended Steps
1) Audit
   - Verify the bucket region and enumerate top-level prefixes
   - Confirm legacy prefixes presence (prompts/, schemas/, uploads/, backup/)

2) Dry-run Migration
   - Run migrate_prompts_schemas_to_id.py without --apply to see plan
   - Validate target paths map to correct company_id/doc_type_id/config_id + filenames

3) Apply Migration
   - Re-run with --apply (copies objects, deletes temp_ and updates DB prompt_path/schema_path)

4) Cleanup Old Prefixes
   - s3_prefix_cleanup.py --apply
     * uploads/ -> upload/
     * upload/upload/ -> upload/
     * backup/ -> backups/

5) Toggle Read Compatibility (optional)
   - In code, disable name-based/wildcard fallbacks after migrations are completed

Validation
- /health should report S3 healthy
- GET /configs/{config_id}/download/{prompt|schema} should resolve files directly via companies/ paths
- Orders: upload primary file and generate pre-signed URL; check object exists under upload/orders/...

