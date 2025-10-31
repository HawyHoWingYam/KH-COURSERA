"""
Utility script to restore mapping-related columns on the ocr_orders table.

The live Postgres database no longer has these columns, causing ORM queries
that reference them to fail. Run this script once to add the columns back
without relying on Alembic migrations.

Usage:
    DATABASE_URL=postgresql://... python -m scripts.restore_order_mapping_columns
"""
import logging
import os
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

COLUMNS = {
    "mapping_file_path": {
        "type_sql": "VARCHAR(500)",
        "comment": "S3 path to uploaded mapping file (Excel/CSV)",
    },
    "mapping_keys": {
        "type_sql": "JSONB",
        "comment": "Array of 1-3 mapping keys selected by user [key1, key2, key3]",
    },
}


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    return database_url


@contextmanager
def db_connection():
    engine = create_engine(get_database_url())
    try:
        with engine.begin() as connection:
            yield connection
    finally:
        engine.dispose()


def column_exists(connection: Connection, table_name: str, column_name: str) -> bool:
    result = connection.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = :table_name
              AND column_name = :column_name
              AND table_schema = current_schema()
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    ).first()
    return result is not None


def ensure_column(connection: Connection, table_name: str, column_name: str, definition: dict) -> None:
    if column_exists(connection, table_name, column_name):
        logger.info("Column %s.%s already exists; skipping.", table_name, column_name)
        return

    logger.info("Adding column %s.%s ...", table_name, column_name)
    connection.execute(
        text(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {definition['type_sql']} NULL"
        )
    )
    connection.execute(
        text(
            "COMMENT ON COLUMN "
            f"{table_name}.{column_name} IS :comment"
        ),
        {"comment": definition["comment"]},
    )
    logger.info("Added column %s.%s.", table_name, column_name)


def main():
    with db_connection() as connection:
        for column_name, definition in COLUMNS.items():
            ensure_column(connection, "ocr_orders", column_name, definition)
    logger.info("Column restoration complete.")


if __name__ == "__main__":
    main()
