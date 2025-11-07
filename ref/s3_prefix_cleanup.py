#!/usr/bin/env python3
"""
Cleanup legacy S3 prefixes and unify to standard ones.

Actions (when --apply)
- uploads/ -> upload/
- upload/upload/ -> upload/
- backup/ -> backups/

Dry-run by default (prints planned copy/delete operations).

Usage
  python s3_prefix_cleanup.py --bucket <name> [--region ap-southeast-1] [--apply]
"""

import argparse
import os
import sys
from typing import List, Tuple

import boto3
from botocore.exceptions import ClientError


def get_s3(region: str):
    return boto3.client("s3", region_name=region)


def list_keys(s3, bucket: str, prefix: str) -> List[str]:
    keys: List[str] = []
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/") and obj["Size"] == 0:
                # folder marker
                continue
            keys.append(key)
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return keys


def plan_move(prefix_src: str, prefix_dst: str, keys: List[str]) -> List[Tuple[str, str]]:
    plan = []
    for k in keys:
        remainder = k[len(prefix_src) :]
        dst = prefix_dst + remainder
        plan.append((k, dst))
    return plan


def copy_object(s3, bucket: str, src: str, dst: str, apply: bool):
    if not apply:
        print(f"[DRY] COPY s3://{bucket}/{src} -> s3://{bucket}/{dst}")
        return
    s3.copy_object(Bucket=bucket, Key=dst, CopySource={"Bucket": bucket, "Key": src})


def delete_object(s3, bucket: str, key: str, apply: bool):
    if not apply:
        print(f"[DRY] DELETE s3://{bucket}/{key}")
        return
    try:
        s3.delete_object(Bucket=bucket, Key=key)
    except ClientError as e:
        print(f"[WARN] delete {key} failed: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Unify S3 prefixes")
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET_NAME"))
    parser.add_argument("--region", default=os.getenv("AWS_DEFAULT_REGION", "ap-southeast-1"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not args.bucket:
        raise SystemExit("S3 bucket not specified")

    s3 = get_s3(args.region)

    # uploads/ -> upload/
    uploads_keys = list_keys(s3, args.bucket, "uploads/")
    if uploads_keys:
        print(f"Found {len(uploads_keys)} keys under uploads/")
        for src, dst in plan_move("uploads/", "upload/", uploads_keys):
            copy_object(s3, args.bucket, src, dst, args.apply)
        for k in uploads_keys:
            delete_object(s3, args.bucket, k, args.apply)
    else:
        print("No keys under uploads/")

    # upload/upload/ -> upload/
    upup_keys = list_keys(s3, args.bucket, "upload/upload/")
    if upup_keys:
        print(f"Found {len(upup_keys)} keys under upload/upload/")
        for src, dst in plan_move("upload/upload/", "upload/", upup_keys):
            copy_object(s3, args.bucket, src, dst, args.apply)
        for k in upup_keys:
            delete_object(s3, args.bucket, k, args.apply)
    else:
        print("No keys under upload/upload/")

    # backup/ -> backups/
    backup_keys = list_keys(s3, args.bucket, "backup/")
    if backup_keys:
        print(f"Found {len(backup_keys)} keys under backup/")
        for src, dst in plan_move("backup/", "backups/", backup_keys):
            copy_object(s3, args.bucket, src, dst, args.apply)
        for k in backup_keys:
            delete_object(s3, args.bucket, k, args.apply)
    else:
        print("No keys under backup/")

    print("Done.")


if __name__ == "__main__":
    main()

