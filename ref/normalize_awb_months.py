#!/usr/bin/env python3
"""
Normalize AWB monthly folders from YYYYMM to YYYY/MM under upload/onedrive/airway-bills/.

Default is dry-run. Use --apply to perform copy+delete.

Usage
  python normalize_awb_months.py --bucket <name> [--region ap-southeast-1] [--apply]
"""

import argparse
import os
import re
from typing import List

import boto3


def get_s3(region: str):
    return boto3.client("s3", region_name=region)


def list_all(s3, bucket: str, prefix: str) -> List[str]:
    keys: List[str] = []
    token = None
    while True:
        kwargs = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
        if token:
            kwargs["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            k = obj["Key"]
            if k.endswith('/') and obj['Size'] == 0:
                continue
            keys.append(k)
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return keys


def main():
    parser = argparse.ArgumentParser(description="Normalize AWB month paths")
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET_NAME"))
    parser.add_argument("--region", default=os.getenv("AWS_DEFAULT_REGION", "ap-southeast-1"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    if not args.bucket:
        raise SystemExit("S3 bucket not specified")

    s3 = get_s3(args.region)
    base = "upload/onedrive/airway-bills/"
    keys = list_all(s3, args.bucket, base)
    print(f"Found {len(keys)} objects under {base}")

    moved = 0
    pat = re.compile(r"^" + re.escape(base) + r"(\d{6})/(.+)$")
    for k in keys:
        m = pat.match(k)
        if not m:
            continue
        yyyymm, rest = m.group(1), m.group(2)
        yyyy, mm = yyyymm[:4], yyyymm[4:]
        dst = f"{base}{yyyy}/{mm}/{rest}"
        if not args.apply:
            print(f"[DRY] COPY s3://{args.bucket}/{k} -> s3://{args.bucket}/{dst}")
        else:
            s3.copy_object(Bucket=args.bucket, Key=dst, CopySource={"Bucket": args.bucket, "Key": k})
            s3.delete_object(Bucket=args.bucket, Key=k)
        moved += 1

    print(f"Done. moved={moved}")


if __name__ == "__main__":
    main()

