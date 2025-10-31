"""Remove legacy auto-mapping columns from company_document_configs

Revision ID: 002_remove_auto_mapping
Revises: 001_add_primary_file_id_to_order_items
Create Date: 2025-10-31
"""
from alembic import op
import sqlalchemy as sa

revision = '002_remove_auto_mapping'
down_revision = '001_add_primary_file_id_to_order_items'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if 'company_document_configs' in inspector.get_table_names():
        cols = {c['name'] for c in inspector.get_columns('company_document_configs')}
        if 'default_mapping_keys' in cols:
            try:
                op.drop_column('company_document_configs', 'default_mapping_keys')
            except Exception:
                pass
        if 'auto_mapping_enabled' in cols:
            try:
                op.drop_column('company_document_configs', 'auto_mapping_enabled')
            except Exception:
                pass
        if 'cross_field_mappings' in cols:
            try:
                op.drop_column('company_document_configs', 'cross_field_mappings')
            except Exception:
                pass


def downgrade():
    # No-op (do not recreate legacy columns)
    pass

