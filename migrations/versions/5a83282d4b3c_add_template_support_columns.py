"""Add template support columns to document types and orders

Revision ID: 5a83282d4b3c
Revises: 1f82dd526512
Create Date: 2025-10-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "5a83282d4b3c"
down_revision: Union[str, None] = "1f82dd526512"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply schema changes for template support."""

    # Add template_json_path column to document_types if missing
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_types'
                  AND column_name = 'template_json_path'
            ) THEN
                ALTER TABLE document_types
                ADD COLUMN template_json_path VARCHAR(500);
                COMMENT ON COLUMN document_types.template_json_path IS 'S3 key or URL for uploaded template JSON file';
            END IF;
        END $$;
        """
    )

    # Add primary_doc_type_id column to ocr_orders if missing
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ocr_orders'
                  AND column_name = 'primary_doc_type_id'
            ) THEN
                ALTER TABLE ocr_orders
                ADD COLUMN primary_doc_type_id INTEGER;
            END IF;
        END $$;
        """
    )

    # Create foreign key constraint for primary_doc_type_id if missing
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints tc
                WHERE tc.table_name = 'ocr_orders'
                  AND tc.constraint_name = 'fk_ocr_orders_primary_doc_type'
            ) THEN
                ALTER TABLE ocr_orders
                ADD CONSTRAINT fk_ocr_orders_primary_doc_type
                FOREIGN KEY (primary_doc_type_id)
                REFERENCES document_types (doc_type_id)
                ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """Revert schema changes for template support."""

    # Drop foreign key constraint if it exists
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints tc
                WHERE tc.table_name = 'ocr_orders'
                  AND tc.constraint_name = 'fk_ocr_orders_primary_doc_type'
            ) THEN
                ALTER TABLE ocr_orders
                DROP CONSTRAINT fk_ocr_orders_primary_doc_type;
            END IF;
        END $$;
        """
    )

    # Drop primary_doc_type_id column if it exists
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'ocr_orders'
                  AND column_name = 'primary_doc_type_id'
            ) THEN
                ALTER TABLE ocr_orders
                DROP COLUMN primary_doc_type_id;
            END IF;
        END $$;
        """
    )

    # Drop template_json_path column if it exists
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_types'
                  AND column_name = 'template_json_path'
            ) THEN
                ALTER TABLE document_types
                DROP COLUMN template_json_path;
            END IF;
        END $$;
        """
    )
