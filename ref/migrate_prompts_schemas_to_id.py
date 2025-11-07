#!/usr/bin/env python3
"""
Migrate legacy prompts/schemas to unified ID-based paths and update DB.

Target structure
  companies/{company_id}/prompts/{doc_type_id}/{config_id}/{filename}
  companies/{company_id}/schemas/{doc_type_id}/{config_id}/{filename}

What it does
  - Reads DB (company_document_configs + companies + document_types)
  - For each config, computes target keys for prompt/schema
  - If current path is companies/.../temp_*: copy -> final path, delete temp (when --apply)
  - Else, try to locate legacy source under prompts/{company_code}/{doc_type_code}/ and schemas/...
  - Copy to target and update DB (when --apply). Otherwise prints plan (dry-run default).

Usage
  python migrate_prompts_schemas_to_id.py --bucket <name> [--region ap-southeast-1] [--apply]

Notes
  - Expects backend/backend.env to exist so DATABASE_URL is available.
  - Run inside project root or anywhere with access to backend/backend.env.
"""

import argparse
import os
import re
from typing import Dict, Optional, Tuple

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def load_env():
    here = os.path.abspath(os.path.dirname(__file__))
    backend_env = os.path.join(os.path.dirname(here), "backend", "backend.env")
    if os.path.exists(backend_env):
        load_dotenv(backend_env, override=True)


def get_s3(region: str):
    return boto3.client("s3", region_name=region)


def s3_head(s3, bucket: str, key: str) -> Optional[dict]:
    try:
        return s3.head_object(Bucket=bucket, Key=key)
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
            return None
        raise


def s3_exists(s3, bucket: str, key: str) -> bool:
    return s3_head(s3, bucket, key) is not None


def s3_copy(s3, bucket: str, src_key: str, dst_key: str, metadata: Optional[dict] = None, apply: bool = False):
    if not apply:
        print(f"[DRY] COPY s3://{bucket}/{src_key} -> s3://{bucket}/{dst_key}")
        return
    copy_source = {"Bucket": bucket, "Key": src_key}
    extra = {}
    if metadata:
        # To set new metadata, you must specify MetadataDirective='REPLACE'
        extra["MetadataDirective"] = "REPLACE"
        extra["Metadata"] = metadata
    s3.copy_object(Bucket=bucket, Key=dst_key, CopySource=copy_source, **extra)


def s3_delete(s3, bucket: str, key: str, apply: bool = False):
    if not apply:
        print(f"[DRY] DELETE s3://{bucket}/{key}")
        return
    s3.delete_object(Bucket=bucket, Key=key)


def main():
    load_env()

    parser = argparse.ArgumentParser(description="Migrate prompts/schemas to ID-based paths")
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET_NAME"))
    parser.add_argument("--region", default=os.getenv("AWS_DEFAULT_REGION", "ap-southeast-1"))
    parser.add_argument("--apply", action="store_true", help="apply changes (copy/delete + DB update)")
    args = parser.parse_args()

    if not args.bucket:
        raise SystemExit("S3 bucket not specified (use --bucket or set S3_BUCKET_NAME)")

    s3 = get_s3(args.region)

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not found in environment (backend/backend.env)")
    engine = create_engine(db_url)

    # Build code->id maps
    with engine.connect() as conn:
        companies = {r.company_code: r.company_id for r in conn.execute(text("SELECT company_id, company_code FROM companies"))}
        doctypes = {r.type_code: r.doc_type_id for r in conn.execute(text("SELECT doc_type_id, type_code FROM document_types"))}

        configs = list(conn.execute(text(
            """
            SELECT config_id, company_id, doc_type_id,
                   prompt_path, schema_path,
                   original_prompt_filename, original_schema_filename
            FROM company_document_configs
            ORDER BY config_id
            """
        )))

    def compute_target(company_id: int, doc_type_id: int, config_id: int,
                       prompt_name: Optional[str], schema_name: Optional[str]) -> Tuple[str, str]:
        p_name = (prompt_name or "prompt.txt").strip()
        s_name = (schema_name or "schema.json").strip()
        p_key = f"companies/{company_id}/prompts/{doc_type_id}/{config_id}/{p_name}"
        s_key = f"companies/{company_id}/schemas/{doc_type_id}/{config_id}/{s_name}"
        return p_key, s_key

    updates = []
    for row in configs:
        cfg_id = row.config_id
        cid = row.company_id
        did = row.doc_type_id
        p_stored = (row.prompt_path or "").replace(f"s3://{args.bucket}/", "")
        s_stored = (row.schema_path or "").replace(f"s3://{args.bucket}/", "")
        p_target, s_target = compute_target(cid, did, cfg_id, row.original_prompt_filename, row.original_schema_filename)

        actions = {"config_id": cfg_id, "prompt": [], "schema": []}

        # PROMPT
        if p_stored:
            if p_stored.startswith(f"companies/{cid}/prompts/{did}/temp_"):
                # move temp -> final
                actions["prompt"].append(("copy", p_stored, p_target))
                actions["prompt"].append(("delete", p_stored, None))
            elif p_stored == p_target:
                pass  # already in place
            else:
                # ensure it exists at target; copy if missing
                actions["prompt"].append(("ensure_copy", p_stored, p_target))
        else:
            # try legacy prompts/{code}/{type_code}/...
            # find company_code and type_code for this ID
            # we will try a set of candidate filenames
            actions["prompt"].append(("discover_legacy", None, p_target))

        # SCHEMA
        if s_stored:
            if s_stored.startswith(f"companies/{cid}/schemas/{did}/temp_"):
                actions["schema"].append(("copy", s_stored, s_target))
                actions["schema"].append(("delete", s_stored, None))
            elif s_stored == s_target:
                pass
            else:
                actions["schema"].append(("ensure_copy", s_stored, s_target))
        else:
            actions["schema"].append(("discover_legacy", None, s_target))

        updates.append((row, actions))

    def find_legacy(s3, bucket: str, company_id: int, doc_type_id: int, kind: str) -> Optional[str]:
        # Resolve codes by querying DB once (outer scope)
        # We need company_code and type_code from DB
        # For speed, do a quick map by ID
        nonlocal_companies_by_id = getattr(find_legacy, "companies_by_id", None)
        nonlocal_doctypes_by_id = getattr(find_legacy, "doctypes_by_id", None)
        if nonlocal_companies_by_id is None or nonlocal_doctypes_by_id is None:
            with engine.connect() as conn:
                find_legacy.companies_by_id = {r.company_id: r.company_code for r in conn.execute(text("SELECT company_id, company_code FROM companies"))}
                find_legacy.doctypes_by_id = {r.doc_type_id: r.type_code for r in conn.execute(text("SELECT doc_type_id, type_code FROM document_types"))}
        company_code = find_legacy.companies_by_id.get(company_id)
        type_code = find_legacy.doctypes_by_id.get(doc_type_id)
        if not company_code or not type_code:
            return None
        base = f"{('prompts' if kind=='prompt' else 'schemas')}/{company_code}/{type_code}/"
        # list prefix and pick first reasonable candidate
        resp = s3.list_objects_v2(Bucket=bucket, Prefix=base)
        items = resp.get("Contents", [])
        if not items:
            return None
        # Prefer .txt for prompt, .json for schema
        preferred_ext = ".txt" if kind == "prompt" else ".json"
        for obj in items:
            key = obj["Key"]
            if key.lower().endswith(preferred_ext):
                return key
        # fallback first
        return items[0]["Key"]

    # Execute actions
    for row, actions in updates:
        cid = row.company_id
        did = row.doc_type_id
        cfg_id = row.config_id
        p_target, s_target = compute_target(cid, did, cfg_id, row.original_prompt_filename, row.original_schema_filename)

        # PROMPT
        for action, src, dst in actions["prompt"]:
            if action == "copy":
                meta = {}
                filename = os.path.basename(dst)
                meta["original_filename"] = filename
                s3_copy(s3, args.bucket, src, dst, metadata=meta, apply=args.apply)
            elif action == "delete":
                s3_delete(s3, args.bucket, src, apply=args.apply)
            elif action == "ensure_copy":
                if not s3_exists(s3, args.bucket, dst):
                    meta = {"original_filename": os.path.basename(dst)}
                    s3_copy(s3, args.bucket, src, dst, metadata=meta, apply=args.apply)
            elif action == "discover_legacy":
                legacy = find_legacy(s3, args.bucket, cid, did, "prompt")
                if legacy:
                    meta = {"original_filename": os.path.basename(dst)}
                    s3_copy(s3, args.bucket, legacy, dst, metadata=meta, apply=args.apply)
        # SCHEMA
        for action, src, dst in actions["schema"]:
            if action == "copy":
                meta = {"original_filename": os.path.basename(dst)}
                s3_copy(s3, args.bucket, src, dst, metadata=meta, apply=args.apply)
            elif action == "delete":
                s3_delete(s3, args.bucket, src, apply=args.apply)
            elif action == "ensure_copy":
                if not s3_exists(s3, args.bucket, dst):
                    meta = {"original_filename": os.path.basename(dst)}
                    s3_copy(s3, args.bucket, src, dst, metadata=meta, apply=args.apply)
            elif action == "discover_legacy":
                legacy = find_legacy(s3, args.bucket, cid, did, "schema")
                if legacy:
                    meta = {"original_filename": os.path.basename(dst)}
                    s3_copy(s3, args.bucket, legacy, dst, metadata=meta, apply=args.apply)

        # DB update
        if args.apply:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE company_document_configs
                        SET prompt_path = :ppath,
                            schema_path = :spath,
                            original_prompt_filename = COALESCE(original_prompt_filename, :pname),
                            original_schema_filename = COALESCE(original_schema_filename, :sname),
                            updated_at = NOW()
                        WHERE config_id = :cid
                        """
                    ),
                    {
                        "ppath": f"s3://{args.bucket}/{p_target}",
                        "spath": f"s3://{args.bucket}/{s_target}",
                        "pname": os.path.basename(p_target),
                        "sname": os.path.basename(s_target),
                        "cid": cfg_id,
                    },
                )
                print(f"[APPLY] DB updated for config {cfg_id}")
        else:
            print(f"[DRY] Would update DB for config {cfg_id} -> {p_target}, {s_target}")


if __name__ == "__main__":
    main()

