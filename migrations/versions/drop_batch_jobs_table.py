"""Drop batch_jobs table - migrate to Orders pipeline

Revision ID: drop_batch_jobs_001
Revises: awb_onedrive_001
Create Date: 2025-10-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'drop_batch_jobs_001'
down_revision: Union[str, None] = 'awb_onedrive_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Drop the batch_jobs table and related indexes.

    This migration is part of the consolidation from batch_jobs to Orders pipeline.
    All batch processing is now handled through:
    - OcrOrder (for order management)
    - OcrOrderItem (for individual items)
    - OrderItemFile (for file attachments)
    - ProcessingJob (for individual job tracking)

    Before running this migration, ensure:
    1. All batch_jobs have been migrated or archived
    2. No active batch processing is running
    3. Database backups are in place
    """

    # Drop foreign key constraints first
    op.execute("""
        DO $$
        BEGIN
            -- Drop foreign keys that reference batch_jobs
            IF EXISTS (
                SELECT constraint_name FROM information_schema.referential_constraints
                WHERE table_name='batch_jobs'
            ) THEN
                -- Get all foreign keys referencing batch_jobs and drop them
                FOR rec IN
                    SELECT constraint_name FROM information_schema.table_constraints
                    WHERE table_name='batch_jobs' AND constraint_type='FOREIGN KEY'
                LOOP
                    EXECUTE 'ALTER TABLE batch_jobs DROP CONSTRAINT IF EXISTS ' || rec.constraint_name;
                END LOOP;
            END IF;
        END $$;
    """)

    # Drop any indexes on batch_jobs table
    op.execute("""
        DO $$
        BEGIN
            -- Drop all indexes on batch_jobs table
            FOR idx_rec IN
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'batch_jobs'
                AND indexname NOT LIKE 'pg_toast%'
            LOOP
                EXECUTE 'DROP INDEX IF EXISTS ' || idx_rec.indexname;
            END LOOP;
        END $$;
    """)

    # Drop the batch_jobs table
    op.execute("""
        DROP TABLE IF EXISTS batch_jobs CASCADE;
    """)

    # Log migration completion
    op.execute("""
        INSERT INTO alembic_version (version_num)
        SELECT 'drop_batch_jobs_001'
        WHERE NOT EXISTS (SELECT 1 FROM alembic_version WHERE version_num = 'drop_batch_jobs_001');
    """)


def downgrade() -> None:
    """
    Recreate the batch_jobs table if needed (for reverting migration).

    Note: This recreates the schema but not the data.
    """

    # Recreate batch_jobs table with original schema
    op.create_table(
        'batch_jobs',
        sa.Column('batch_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('doc_type_id', sa.Integer(), nullable=False),
        sa.Column('upload_description', sa.String(length=255), nullable=True),
        sa.Column('s3_upload_path', sa.String(length=500), nullable=True),
        sa.Column('original_zipfile', sa.String(length=500), nullable=True),
        sa.Column('total_files', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('processed_files', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('json_output_path', sa.String(length=500), nullable=True),
        sa.Column('excel_output_path', sa.String(length=500), nullable=True),
        sa.Column('netsuite_csv_path', sa.String(length=500), nullable=True),
        sa.Column('matching_report_path', sa.String(length=500), nullable=True),
        sa.Column('summary_report_path', sa.String(length=500), nullable=True),
        sa.Column('uploader_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('batch_id'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.company_id'], ),
        sa.ForeignKeyConstraint(['doc_type_id'], ['document_types.doc_type_id'], ),
    )

    # Recreate indexes
    op.create_index('idx_batch_jobs_company', 'batch_jobs', ['company_id'])
    op.create_index('idx_batch_jobs_doc_type', 'batch_jobs', ['doc_type_id'])
    op.create_index('idx_batch_jobs_status', 'batch_jobs', ['status'])
    op.create_index('idx_batch_jobs_created_at', 'batch_jobs', ['created_at'])
