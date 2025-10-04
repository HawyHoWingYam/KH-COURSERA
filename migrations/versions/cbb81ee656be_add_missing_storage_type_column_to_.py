"""Add missing storage_type column to company_document_configs

Revision ID: cbb81ee656be
Revises: 1d1b940188ef
Create Date: 2025-10-04 14:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cbb81ee656be'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add storage_type column if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'company_document_configs'
                AND column_name = 'storage_type'
            ) THEN
                ALTER TABLE company_document_configs
                ADD COLUMN storage_type VARCHAR(10) DEFAULT 'local';
            END IF;
        END $$;
    """)

    # Add storage_metadata column if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'company_document_configs'
                AND column_name = 'storage_metadata'
            ) THEN
                ALTER TABLE company_document_configs
                ADD COLUMN storage_metadata JSONB;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Only drop if exists
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'company_document_configs'
                AND column_name = 'storage_metadata'
            ) THEN
                ALTER TABLE company_document_configs
                DROP COLUMN storage_metadata;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'company_document_configs'
                AND column_name = 'storage_type'
            ) THEN
                ALTER TABLE company_document_configs
                DROP COLUMN storage_type;
            END IF;
        END $$;
    """)
