"""Update prompt and schema paths to support S3 URIs

Revision ID: 57b129edcc85
Revises: 0001_initial
Create Date: 2025-09-16 07:55:41.795400

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '57b129edcc85'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """升级数据库schema"""
    # Increase length of path columns to support longer S3 URLs
    # S3 URLs can be quite long, especially with complex folder structures
    op.alter_column('company_document_configs', 'prompt_path',
                    existing_type=sa.String(255),
                    type_=sa.String(500),
                    existing_nullable=False,
                    comment='Path to prompt file (supports local paths and S3 URIs like s3://bucket/prompts/...)')
    
    op.alter_column('company_document_configs', 'schema_path',
                    existing_type=sa.String(255),
                    type_=sa.String(500),
                    existing_nullable=False,
                    comment='Path to schema file (supports local paths and S3 URIs like s3://bucket/schemas/...)')
    
    # Add storage type enum to help distinguish between local and S3 storage
    # First create the enum type explicitly
    storage_type_enum = sa.Enum('local', 's3', name='storage_type', create_type=False)
    storage_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Add the column as nullable first
    op.add_column('company_document_configs', 
                  sa.Column('storage_type', storage_type_enum, 
                           nullable=True,
                           comment='Storage backend type for prompts and schemas'))
    
    # Update all existing rows to have 'local' as default
    op.execute("UPDATE company_document_configs SET storage_type = 'local' WHERE storage_type IS NULL")
    
    # Now make the column NOT NULL with default
    op.alter_column('company_document_configs', 'storage_type',
                    nullable=False,
                    server_default='local')
    
    # Add metadata column for S3-specific information (JSON field)
    op.add_column('company_document_configs',
                  sa.Column('storage_metadata', sa.JSON,
                           nullable=True,
                           comment='Additional metadata for storage backend (e.g., S3 bucket info, cache settings)'))
    
    # Add index on storage_type for better query performance
    op.create_index('idx_storage_type', 'company_document_configs', ['storage_type'])


def downgrade() -> None:
    """降级数据库schema"""
    # Remove the added index
    op.drop_index('idx_storage_type', table_name='company_document_configs')
    
    # Remove the added columns
    op.drop_column('company_document_configs', 'storage_metadata')
    op.drop_column('company_document_configs', 'storage_type')
    
    # Drop the enum type
    sa.Enum(name='storage_type').drop(op.get_bind(), checkfirst=True)
    
    # Revert path column lengths
    op.alter_column('company_document_configs', 'prompt_path',
                    existing_type=sa.String(500),
                    type_=sa.String(255),
                    existing_nullable=False)
    
    op.alter_column('company_document_configs', 'schema_path',
                    existing_type=sa.String(500),
                    type_=sa.String(255),
                    existing_nullable=False)