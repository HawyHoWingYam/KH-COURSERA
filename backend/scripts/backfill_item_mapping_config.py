"""Backfill order-level mapping keys into per-item mapping_config (draft script).

Usage:
  python -m scripts.backfill_item_mapping_config --dry-run
  python -m scripts.backfill_item_mapping_config --execute

Notes:
  - This script copies OcrOrder.mapping_keys into each OcrOrderItem.mapping_config as
    'external_join_keys' and sets item_type='single_source' when mapping_config is empty.
  - It DOES NOT populate 'master_csv_path' because the new workflow expects OneDrive
    references. Operators should later complete the configs via the UI or defaults.
  - Safe to run multiple times; items with existing mapping_config are skipped by default.
"""
from __future__ import annotations

import argparse
from typing import Any, Dict

from sqlalchemy.orm import Session

from db.database import SessionLocal
from db.models import OcrOrder, OcrOrderItem, OrderItemType


def backfill(dry_run: bool = True) -> Dict[str, Any]:
    stats = {
        "orders_scanned": 0,
        "orders_with_keys": 0,
        "items_updated": 0,
        "items_skipped_existing_config": 0,
    }

    db: Session = SessionLocal()
    try:
        orders = db.query(OcrOrder).filter(OcrOrder.mapping_keys.isnot(None)).all()
        stats["orders_scanned"] = len(orders)
        for order in orders:
            if not order.mapping_keys:
                continue
            stats["orders_with_keys"] += 1
            items = db.query(OcrOrderItem).filter(OcrOrderItem.order_id == order.order_id).all()
            for item in items:
                if item.mapping_config:
                    stats["items_skipped_existing_config"] += 1
                    continue
                # Prepare minimal mapping_config; master_csv_path intentionally left empty
                item.item_type = OrderItemType.SINGLE_SOURCE
                item.mapping_config = {
                    "item_type": OrderItemType.SINGLE_SOURCE.value,
                    "external_join_keys": list(order.mapping_keys or []),
                }
                stats["items_updated"] += 1
            if not dry_run:
                db.commit()
        return stats
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Backfill order-level mapping keys into item mapping_config")
    parser.add_argument("--execute", action="store_true", help="Apply changes (otherwise dry-run)")
    args = parser.parse_args()

    result = backfill(dry_run=not args.execute)
    mode = "EXECUTE" if args.execute else "DRY-RUN"
    print(f"[{mode}] Backfill summary: {result}")


if __name__ == "__main__":
    main()

