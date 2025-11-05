"""Export legacy auto-mapping default_mapping_keys into Mapping Defaults records.

Run this BEFORE dropping legacy columns via Alembic migration.

Usage:
  python -m scripts.export_auto_mapping_to_defaults --execute
  (dry-run by default)
"""
from __future__ import annotations

import argparse
from typing import Any, Dict

from sqlalchemy.orm import Session

from db.database import SessionLocal
from db.models import CompanyDocumentConfig, CompanyDocMappingDefault, OrderItemType


def export(dry_run: bool = True) -> Dict[str, Any]:
    stats = {"configs_scanned": 0, "defaults_created": 0, "defaults_updated": 0, "skipped": 0}
    db: Session = SessionLocal()
    try:
        configs = db.query(CompanyDocumentConfig).all()
        stats["configs_scanned"] = len(configs)
        for cfg in configs:
            keys = getattr(cfg, 'default_mapping_keys', None)
            if not keys:
                stats["skipped"] += 1
                continue
            # Write to defaults for BOTH modes as conservative export (single_source typical)
            for mode in (OrderItemType.SINGLE_SOURCE, OrderItemType.MULTI_SOURCE):
                existing = (
                    db.query(CompanyDocMappingDefault)
                    .filter(
                        CompanyDocMappingDefault.company_id == cfg.company_id,
                        CompanyDocMappingDefault.doc_type_id == cfg.doc_type_id,
                        CompanyDocMappingDefault.item_type == mode,
                    )
                    .first()
                )
                override = {"item_type": mode.value, "external_join_keys": list(keys)}
                if existing:
                    existing.config_override = override
                    stats["defaults_updated"] += 1
                else:
                    record = CompanyDocMappingDefault(
                        company_id=cfg.company_id,
                        doc_type_id=cfg.doc_type_id,
                        item_type=mode,
                        template_id=None,
                        config_override=override,
                    )
                    db.add(record)
                    stats["defaults_created"] += 1
        if not dry_run:
            db.commit()
        return stats
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Export default_mapping_keys to mapping defaults")
    parser.add_argument("--execute", action="store_true", help="Persist changes (default dry-run)")
    args = parser.parse_args()
    result = export(dry_run=not args.execute)
    print(("EXECUTE" if args.execute else "DRY-RUN"), result)


if __name__ == "__main__":
    main()

