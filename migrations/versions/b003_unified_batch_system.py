"""Convert to unified batch-only system - update BatchJob schema

Revision ID: b003_unified_batch_system
Revises: b002_fix_batch_jobs_constraint
Create Date: 2025-09-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = 'b003_unified_batch_system'
down_revision = 'b002_fix_batch_jobs_constraint'
branch_labels = None
depends_on = None


def upgrade():
    """Convert BatchJob table for unified batch-only system"""
    
    # Rename existing columns to be more generic
    op.alter_column('batch_jobs', 'zip_filename', new_column_name='upload_description')
    op.alter_column('batch_jobs', 's3_zipfile_path', new_column_name='s3_upload_path')
    
    # Add new columns for unified batch system
    op.add_column('batch_jobs', sa.Column('upload_type', 
        sa.Enum('single_file', 'multiple_files', 'zip_file', 'mixed', name='upload_type_enum'), 
        nullable=False, server_default='single_file'))
    
    op.add_column('batch_jobs', sa.Column('original_file_names', JSON, nullable=True, 
        comment='Array of original uploaded filenames'))
    
    op.add_column('batch_jobs', sa.Column('file_count', sa.Integer, nullable=False, 
        server_default='0', comment='Total number of files in this batch'))
    
    # Update existing records to have proper values
    # Set upload_type based on existing data
    op.execute("""
        UPDATE batch_jobs 
        SET upload_type = 'zip_file' 
        WHERE upload_description LIKE '%.zip'
    """)
    
    op.execute("""
        UPDATE batch_jobs 
        SET upload_type = 'single_file' 
        WHERE upload_description NOT LIKE '%.zip'
    """)
    
    # Set file_count to total_files for existing records
    op.execute("""
        UPDATE batch_jobs 
        SET file_count = total_files 
        WHERE total_files > 0
    """)


def downgrade():
    """Revert BatchJob table changes"""
    
    # Remove new columns
    op.drop_column('batch_jobs', 'file_count')
    op.drop_column('batch_jobs', 'original_file_names')
    op.drop_column('batch_jobs', 'upload_type')
    
    # Rename columns back
    op.alter_column('batch_jobs', 'upload_description', new_column_name='zip_filename')
    op.alter_column('batch_jobs', 's3_upload_path', new_column_name='s3_zipfile_path')
    
    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS upload_type_enum")