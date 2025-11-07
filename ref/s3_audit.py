#!/usr/bin/env python3
"""
S3 bucket audit tool for HYA-OCR

Features
- Verify bucket region
- List top-level prefixes and counts
- Inspect legacy vs new layout (companies/, prompts/, schemas/, upload/, uploads/, results/, exports/, backup/, backups/)
- Print sample keys to help migration planning

Usage
  python s3_audit.py --bucket <name> [--region ap-southeast-1] [--max-samples 10]

Environment
  Falls back to S3_BUCKET_NAME and AWS_DEFAULT_REGION when args omitted.
"""

import argparse
import os
from typing import List, Dict

import boto3


def get_s3(region: str):
    return boto3.client("s3", region_name=region)


def list_common_prefixes(s3, bucket: str, prefix: str = "", delimiter: str = "/") -> List[str]:
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, Delimiter=delimiter)
    cps = [cp["Prefix"] for cp in resp.get("CommonPrefixes", [])]
    return cps


def list_objects(s3, bucket: str, prefix: str, max_keys: int = 1000) -> List[Dict]:
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=max_keys)
    return resp.get("Contents", [])


def print_header(title: str):
    print("\n== " + title + " ==")


def main():
    parser = argparse.ArgumentParser(description="Audit S3 bucket layout")
    parser.add_argument("--bucket", default=os.getenv("S3_BUCKET_NAME"))
    parser.add_argument("--region", default=os.getenv("AWS_DEFAULT_REGION", "ap-southeast-1"))
    parser.add_argument("--max-samples", type=int, default=5)
    args = parser.parse_args()

    if not args.bucket:
        raise SystemExit("S3 bucket not specified (use --bucket or set S3_BUCKET_NAME)")

    s3 = get_s3(args.region)

    # Region check
    loc = s3.get_bucket_location(Bucket=args.bucket)
    bucket_region = loc.get("LocationConstraint") or "us-east-1"
    print_header("Bucket")
    print(f"bucket={args.bucket}, region={bucket_region}")

    # Top-level prefixes
    top = list_common_prefixes(s3, args.bucket)
    print_header("Top-level prefixes")
    for p in top:
        print("-", p)

    interesting = [
        "companies/",
        "prompts/",
        "schemas/",
        "upload/",
        "uploads/",
        "results/",
        "exports/",
        "backup/",
        "backups/",
    ]

    for p in interesting:
        print_header(p)
        cps = list_common_prefixes(s3, args.bucket, p)
        objs = list_objects(s3, args.bucket, p)
        print(f"sub-prefixes={len(cps)}, objects={len(objs)}")
        if cps:
            print("sub-prefix samples:")
            for sample in cps[: args.max_samples]:
                print("  -", sample)
        if objs:
            print("object samples:")
            for o in objs[: args.max_samples]:
                print(f"  - {o['Key']} ({o['Size']} bytes)")

    # Anomaly hints
    print_header("Anomalies/Hints")
    hints = [
        ("uploads/ present?", "uploads/" in top),
        ("upload/upload/ present?", any(cp.startswith("upload/upload/") for cp in list_common_prefixes(s3, args.bucket, "upload/"))),
        ("backup/ present?", "backup/" in top),
        ("legacy prompts/ present?", "prompts/" in top),
        ("legacy schemas/ present?", "schemas/" in top),
    ]
    for name, val in hints:
        print(f"- {name} {val}")


if __name__ == "__main__":
    main()

