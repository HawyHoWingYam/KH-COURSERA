#!/usr/bin/env python3
"""
Database audit for HYA-OCR alignment status.

Reports counts for:
- company_document_configs prompt/schema path styles (ID vs legacy)
- files table path styles (upload/ vs uploads/, companies/, prompts/, schemas/)

Usage
  python db_audit.py
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def load_env():
    here = os.path.abspath(os.path.dirname(__file__))
    backend_env = os.path.join(os.path.dirname(here), "backend", "backend.env")
    if os.path.exists(backend_env):
        load_dotenv(backend_env, override=True)


def main():
    load_env()
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not set (backend/backend.env)")
    engine = create_engine(db_url)

    with engine.connect() as conn:
        print("== company_document_configs ==")
        q1 = text(
            """
            SELECT
              COUNT(*)                              AS total,
              COUNT(*) FILTER (WHERE prompt_path LIKE 's3://%/companies/%') AS prompt_id,
              COUNT(*) FILTER (WHERE schema_path LIKE 's3://%/companies/%') AS schema_id,
              COUNT(*) FILTER (WHERE prompt_path LIKE 's3://%/prompts/%')   AS prompt_legacy,
              COUNT(*) FILTER (WHERE schema_path LIKE 's3://%/schemas/%')   AS schema_legacy,
              COUNT(*) FILTER (WHERE prompt_path LIKE 's3://%/companies/%/temp_%') AS prompt_temp,
              COUNT(*) FILTER (WHERE schema_path LIKE 's3://%/companies/%/temp_%') AS schema_temp
            FROM company_document_configs
            """
        )
        print(conn.execute(q1).mappings().first())

        print("\n== files ==")
        q2 = text(
            """
            SELECT
              COUNT(*)                                    AS total,
              COUNT(*) FILTER (WHERE file_path LIKE 's3://%/upload/%')  AS upload_norm,
              COUNT(*) FILTER (WHERE file_path LIKE 's3://%/uploads/%') AS uploads_legacy,
              COUNT(*) FILTER (WHERE file_path LIKE 's3://%/companies/%') AS companies_based
            FROM files
            """
        )
        print(conn.execute(q2).mappings().first())


if __name__ == "__main__":
    main()

