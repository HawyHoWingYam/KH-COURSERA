"""Make cognito_sub nullable

Revision ID: alter_cognito_sub
Revises: [previous_revision_id]
Create Date: [current_date]
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Make cognito_sub nullable
    op.alter_column('users', 'cognito_sub', 
                    existing_type=sa.String(), 
                    nullable=True)

def downgrade():
    # Make cognito_sub NOT NULL again
    op.alter_column('users', 'cognito_sub', 
                    existing_type=sa.String(), 
                    nullable=False) 