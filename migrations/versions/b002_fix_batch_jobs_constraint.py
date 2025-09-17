"""Fix batch_jobs doc_type_id foreign key constraint to RESTRICT

Revision ID: fix_batch_jobs_constraint
Revises: make_paths_nullable
Create Date: 2025-09-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b002_fix_batch_jobs_constraint'
down_revision = 'b001_make_paths_nullable'
branch_labels = None
depends_on = None


def upgrade():
    """Change batch_jobs foreign key constraint from NO ACTION to RESTRICT"""
    # Drop the existing foreign key constraint
    op.drop_constraint('batch_jobs_doc_type_id_fkey', 'batch_jobs', type_='foreignkey')
    
    # Add the new foreign key constraint with RESTRICT on delete
    op.create_foreign_key(
        'batch_jobs_doc_type_id_fkey', 
        'batch_jobs', 
        'document_types',
        ['doc_type_id'], 
        ['doc_type_id'], 
        ondelete='RESTRICT'
    )


def downgrade():
    """Revert batch_jobs foreign key constraint back to NO ACTION"""
    # Drop the RESTRICT constraint
    op.drop_constraint('batch_jobs_doc_type_id_fkey', 'batch_jobs', type_='foreignkey')
    
    # Add back the NO ACTION constraint
    op.create_foreign_key(
        'batch_jobs_doc_type_id_fkey', 
        'batch_jobs', 
        'document_types',
        ['doc_type_id'], 
        ['doc_type_id']
        # NO ACTION is the default, so no ondelete parameter needed
    )