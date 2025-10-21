"""Add primary_file_id column to ocr_order_items table

Revision ID: 001_add_primary_file_id
Revises:
Create Date: 2025-10-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_add_primary_file_id'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add primary_file_id column to ocr_order_items
    op.add_column('ocr_order_items',
        sa.Column('primary_file_id', sa.Integer(), nullable=True,
                 comment='Primary uploaded file for this item')
    )

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_ocr_order_items_primary_file_id',
        'ocr_order_items', 'files',
        ['primary_file_id'], ['file_id'],
        ondelete='SET NULL'
    )

    # Update file_count comment to reflect that it now counts only attachments
    # Note: SQLAlchemy/Alembic doesn't directly support modifying column comments,
    # so this is handled via raw SQL for PostgreSQL
    with op.get_context().connection.begin():
        op.execute("COMMENT ON COLUMN ocr_order_items.file_count IS 'Number of attachment files in this item (excludes primary file)'")
        op.execute("COMMENT ON COLUMN ocr_order_items.ocr_result_json_path IS 'S3 path to primary file OCR result JSON'")
        op.execute("COMMENT ON COLUMN ocr_order_items.ocr_result_csv_path IS 'S3 path to mapped CSV result (primary + attachments)'")


def downgrade() -> None:
    # Remove foreign key constraint
    op.drop_constraint('fk_ocr_order_items_primary_file_id',
                      'ocr_order_items', type_='foreignkey')

    # Remove primary_file_id column
    op.drop_column('ocr_order_items', 'primary_file_id')

    # Restore original comments
    with op.get_context().connection.begin():
        op.execute("COMMENT ON COLUMN ocr_order_items.file_count IS 'Number of files in this item'")
        op.execute("COMMENT ON COLUMN ocr_order_items.ocr_result_json_path IS 'S3 path to OCR result JSON file'")
        op.execute("COMMENT ON COLUMN ocr_order_items.ocr_result_csv_path IS 'S3 path to OCR result CSV file'")
