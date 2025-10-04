"""Add remaining missing columns to company_document_configs

Revision ID: 1f82dd526512
Revises: cbb81ee656be
Create Date: 2025-10-04 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '1f82dd526512'
down_revision: Union[str, None] = 'cbb81ee656be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add original_prompt_filename column if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'company_document_configs'
                AND column_name = 'original_prompt_filename'
            ) THEN
                ALTER TABLE company_document_configs
                ADD COLUMN original_prompt_filename VARCHAR(255);
                COMMENT ON COLUMN company_document_configs.original_prompt_filename IS 'Original filename of uploaded prompt file (e.g., invoice_prompt.txt)';
            END IF;
        END $$;
    """)

    # Add original_schema_filename column if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'company_document_configs'
                AND column_name = 'original_schema_filename'
            ) THEN
                ALTER TABLE company_document_configs
                ADD COLUMN original_schema_filename VARCHAR(255);
                COMMENT ON COLUMN company_document_configs.original_schema_filename IS 'Original filename of uploaded schema file (e.g., invoice_schema.json)';
            END IF;
        END $$;
    """)

    # Add default_mapping_keys column if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'company_document_configs'
                AND column_name = 'default_mapping_keys'
            ) THEN
                ALTER TABLE company_document_configs
                ADD COLUMN default_mapping_keys JSONB DEFAULT '[]'::jsonb;
                COMMENT ON COLUMN company_document_configs.default_mapping_keys IS 'Default mapping keys for auto-mapping [key1, key2, key3]';
            END IF;
        END $$;
    """)

    # Add auto_mapping_enabled column if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'company_document_configs'
                AND column_name = 'auto_mapping_enabled'
            ) THEN
                ALTER TABLE company_document_configs
                ADD COLUMN auto_mapping_enabled BOOLEAN DEFAULT FALSE;
                COMMENT ON COLUMN company_document_configs.auto_mapping_enabled IS 'Whether to enable auto-mapping for this document type';
            END IF;
        END $$;
    """)

    # Add cross_field_mappings column if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'company_document_configs'
                AND column_name = 'cross_field_mappings'
            ) THEN
                ALTER TABLE company_document_configs
                ADD COLUMN cross_field_mappings JSONB DEFAULT '{}'::jsonb;
                COMMENT ON COLUMN company_document_configs.cross_field_mappings IS 'Cross-field mappings for semantic field mapping {"ocr_field": "mapping_field"}';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Drop columns only if they exist
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'company_document_configs'
                AND column_name = 'cross_field_mappings'
            ) THEN
                ALTER TABLE company_document_configs DROP COLUMN cross_field_mappings;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'company_document_configs'
                AND column_name = 'auto_mapping_enabled'
            ) THEN
                ALTER TABLE company_document_configs DROP COLUMN auto_mapping_enabled;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'company_document_configs'
                AND column_name = 'default_mapping_keys'
            ) THEN
                ALTER TABLE company_document_configs DROP COLUMN default_mapping_keys;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'company_document_configs'
                AND column_name = 'original_schema_filename'
            ) THEN
                ALTER TABLE company_document_configs DROP COLUMN original_schema_filename;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'company_document_configs'
                AND column_name = 'original_prompt_filename'
            ) THEN
                ALTER TABLE company_document_configs DROP COLUMN original_prompt_filename;
            END IF;
        END $$;
    """)
