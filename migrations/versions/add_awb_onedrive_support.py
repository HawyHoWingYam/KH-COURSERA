"""Add AWB and OneDrive support

Revision ID: awb_onedrive_001
Revises: 1f82dd526512
Create Date: 2025-10-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'awb_onedrive_001'
down_revision: Union[str, None] = '1f82dd526512'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to files table for OneDrive tracking
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'files'
                AND column_name = 'source_system'
            ) THEN
                ALTER TABLE files
                ADD COLUMN source_system VARCHAR(50) DEFAULT 'upload';
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'files'
                AND column_name = 'source_path'
            ) THEN
                ALTER TABLE files
                ADD COLUMN source_path VARCHAR(500);
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'files'
                AND column_name = 'source_metadata'
            ) THEN
                ALTER TABLE files
                ADD COLUMN source_metadata JSONB;
            END IF;
        END $$;
    """)

    # Create index for source_path (for deduplication)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_files_source_path
        ON files(source_path) WHERE source_path IS NOT NULL;
    """)

    # Extend upload_type enum to include awb_monthly
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_type WHERE typname = 'upload_type_enum'
            ) THEN
                ALTER TYPE upload_type_enum ADD VALUE IF NOT EXISTS 'awb_monthly';
            END IF;
        END $$;
    """)

    # Create onedrive_sync table for tracking sync history
    op.execute("""
        CREATE TABLE IF NOT EXISTS onedrive_sync (
            sync_id SERIAL PRIMARY KEY,
            last_sync_time TIMESTAMP WITH TIME ZONE NOT NULL,
            sync_status VARCHAR(50) NOT NULL,
            files_processed INTEGER DEFAULT 0,
            files_failed INTEGER DEFAULT 0,
            error_message TEXT,
            sync_metadata JSONB,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_onedrive_sync_status
        ON onedrive_sync(sync_status);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_onedrive_sync_created_at
        ON onedrive_sync(created_at);
    """)


def downgrade() -> None:
    # Drop onedrive_sync table
    op.execute("DROP TABLE IF EXISTS onedrive_sync CASCADE;")

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_files_source_path CASCADE;")

    # Drop columns from files table
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'files'
                AND column_name = 'source_metadata'
            ) THEN
                ALTER TABLE files DROP COLUMN source_metadata;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'files'
                AND column_name = 'source_path'
            ) THEN
                ALTER TABLE files DROP COLUMN source_path;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'files'
                AND column_name = 'source_system'
            ) THEN
                ALTER TABLE files DROP COLUMN source_system;
            END IF;
        END $$;
    """)
