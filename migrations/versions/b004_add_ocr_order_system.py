"""Add OCR Order system tables

Revision ID: b004_add_ocr_order_system
Revises: b003_unified_batch_system
Create Date: 2025-09-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = 'b004_add_ocr_order_system'
down_revision = 'b003_unified_batch_system'
branch_labels = None
depends_on = None


def upgrade():
    """Add OCR Order system tables for enhanced workflow"""

    # Create order status enum
    order_status_enum = sa.Enum(
        'DRAFT', 'PROCESSING', 'MAPPING', 'COMPLETED', 'FAILED',
        name='order_status_enum'
    )
    order_status_enum.create(op.get_bind())

    # Create order item status enum
    order_item_status_enum = sa.Enum(
        'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED',
        name='order_item_status_enum'
    )
    order_item_status_enum.create(op.get_bind())

    # Create ocr_orders table
    op.create_table('ocr_orders',
        sa.Column('order_id', sa.Integer(), primary_key=True),
        sa.Column('order_name', sa.String(255), nullable=True, comment='User-friendly name for the order'),
        sa.Column('status', order_status_enum, nullable=False, server_default='DRAFT', comment='Current status of the order'),
        sa.Column('mapping_file_path', sa.String(500), nullable=True, comment='S3 path to uploaded mapping file (Excel/CSV)'),
        sa.Column('mapping_keys', JSON, nullable=True, comment='Array of 1-3 mapping keys selected by user [key1, key2, key3]'),
        sa.Column('final_report_paths', JSON, nullable=True, comment='Paths to final consolidated reports (NetSuite CSV, Excel reports)'),
        sa.Column('total_items', sa.Integer(), nullable=False, server_default='0', comment='Total number of order items'),
        sa.Column('completed_items', sa.Integer(), nullable=False, server_default='0', comment='Number of completed order items'),
        sa.Column('failed_items', sa.Integer(), nullable=False, server_default='0', comment='Number of failed order items'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Error message if order processing fails'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        comment='Main OCR order container - holds multiple processing items'
    )

    # Create ocr_order_items table
    op.create_table('ocr_order_items',
        sa.Column('item_id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('ocr_orders.order_id', ondelete='CASCADE'), nullable=False),
        sa.Column('company_id', sa.Integer(), sa.ForeignKey('companies.company_id'), nullable=False),
        sa.Column('doc_type_id', sa.Integer(), sa.ForeignKey('document_types.doc_type_id'), nullable=False),
        sa.Column('item_name', sa.String(255), nullable=True, comment='User-friendly name for this item'),
        sa.Column('status', order_item_status_enum, nullable=False, server_default='PENDING'),
        sa.Column('file_count', sa.Integer(), nullable=False, server_default='0', comment='Number of files in this item'),
        sa.Column('ocr_result_json_path', sa.String(500), nullable=True, comment='S3 path to OCR result JSON file'),
        sa.Column('ocr_result_csv_path', sa.String(500), nullable=True, comment='S3 path to OCR result CSV file'),
        sa.Column('processing_started_at', sa.DateTime(), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(), nullable=True),
        sa.Column('processing_time_seconds', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        comment='Individual processing items within an OCR order'
    )

    # Create order_item_files junction table
    op.create_table('order_item_files',
        sa.Column('item_id', sa.Integer(), sa.ForeignKey('ocr_order_items.item_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('file_id', sa.Integer(), sa.ForeignKey('files.file_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('upload_order', sa.Integer(), nullable=True, comment='Order in which file was uploaded to this item'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        comment='Many-to-many relationship between order items and files'
    )

    # Create indexes for better query performance
    op.create_index('idx_ocr_orders_status', 'ocr_orders', ['status'])
    op.create_index('idx_ocr_orders_created_at', 'ocr_orders', ['created_at'])
    op.create_index('idx_ocr_order_items_order_id', 'ocr_order_items', ['order_id'])
    op.create_index('idx_ocr_order_items_status', 'ocr_order_items', ['status'])
    op.create_index('idx_ocr_order_items_company_doc_type', 'ocr_order_items', ['company_id', 'doc_type_id'])
    op.create_index('idx_order_item_files_item_id', 'order_item_files', ['item_id'])


def downgrade():
    """Remove OCR Order system tables"""

    # Drop indexes
    op.drop_index('idx_order_item_files_item_id')
    op.drop_index('idx_ocr_order_items_company_doc_type')
    op.drop_index('idx_ocr_order_items_status')
    op.drop_index('idx_ocr_order_items_order_id')
    op.drop_index('idx_ocr_orders_created_at')
    op.drop_index('idx_ocr_orders_status')

    # Drop tables
    op.drop_table('order_item_files')
    op.drop_table('ocr_order_items')
    op.drop_table('ocr_orders')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS order_item_status_enum")
    op.execute("DROP TYPE IF EXISTS order_status_enum")