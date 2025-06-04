"""Create system settings table

Revision ID: create_system_settings
Revises: [previous_revision_id]
Create Date: [current_date]

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers
revision = 'create_system_settings'
down_revision = '[previous_revision_id]'  # Replace with your previous migration ID
branch_labels = None
depends_on = None

def upgrade():
    # Create settings table
    op.create_table(
        'system_settings',
        sa.Column('setting_id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(255), nullable=False, unique=True),
        sa.Column('value', sa.String(1000), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('updated_at', sa.DateTime(), default=datetime.now)
    )
    
    # Insert default settings
    op.execute("""
    INSERT INTO system_settings (key, value, description) VALUES
    ('gemini_api_key', '', 'API key for Google Gemini'),
    ('default_model', 'gemini-1.5-pro', 'Default Gemini model to use'),
    ('max_context_length', '16000', 'Maximum context length for API calls'),
    ('temperature', '0.3', 'Temperature for generation (0.0-1.0)'),
    ('top_p', '0.95', 'Top-p sampling parameter'),
    ('top_k', '40', 'Top-k sampling parameter')
    """)

def downgrade():
    op.drop_table('system_settings') 