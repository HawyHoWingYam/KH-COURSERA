"""
Initial schema for GeminiOCR.

Revision ID: 0001_initial
Revises: 
Create Date: 2025-09-15
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # departments
    op.create_table(
        "departments",
        sa.Column("department_id", sa.Integer(), primary_key=True),
        sa.Column("department_name", sa.String(length=255), nullable=False, unique=True),
    )

    # users
    op.create_table(
        "users",
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("cognito_sub", sa.String(length=36), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("role", sa.String(length=50), nullable=False, server_default=sa.text("'user'")),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.department_id", ondelete="SET NULL"), nullable=True),
    )

    # document_types
    op.create_table(
        "document_types",
        sa.Column("doc_type_id", sa.Integer(), primary_key=True),
        sa.Column("type_name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("type_code", sa.String(length=50), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # companies
    op.create_table(
        "companies",
        sa.Column("company_id", sa.Integer(), primary_key=True),
        sa.Column("company_name", sa.String(length=100), nullable=False, unique=True),
        sa.Column("company_code", sa.String(length=50), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # batch_jobs (create before processing_jobs to satisfy FK)
    op.create_table(
        "batch_jobs",
        sa.Column("batch_id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.company_id"), nullable=False),
        sa.Column("doc_type_id", sa.Integer(), sa.ForeignKey("document_types.doc_type_id"), nullable=False),
        sa.Column("uploader_user_id", sa.Integer(), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("zip_filename", sa.String(length=255), nullable=True),
        sa.Column("s3_zipfile_path", sa.String(length=255), nullable=True),
        sa.Column("original_zipfile", sa.String(length=255), nullable=True),
        sa.Column("total_files", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("processed_files", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("json_output_path", sa.String(length=255), nullable=True),
        sa.Column("excel_output_path", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # processing_jobs
    op.create_table(
        "processing_jobs",
        sa.Column("job_id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.company_id"), nullable=False),
        sa.Column("doc_type_id", sa.Integer(), sa.ForeignKey("document_types.doc_type_id"), nullable=False),
        sa.Column("s3_pdf_path", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("processing_started_at", sa.DateTime(), nullable=True),
        sa.Column("processing_completed_at", sa.DateTime(), nullable=True),
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("batch_jobs.batch_id"), nullable=True),
    )

    # files
    op.create_table(
        "files",
        sa.Column("file_id", sa.Integer(), primary_key=True),
        sa.Column("file_path", sa.String(length=255), nullable=False, unique=True),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("file_type", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # document_files
    op.create_table(
        "document_files",
        sa.Column("document_file_id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("processing_jobs.job_id"), nullable=False),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("files.file_id"), nullable=False),
        sa.Column("file_category", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("job_id", "file_category", name="uq_document_files_job_category"),
    )

    # api_usage
    op.create_table(
        "api_usage",
        sa.Column("usage_id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("processing_jobs.job_id"), nullable=False),
        sa.Column("input_token_count", sa.Integer(), nullable=False),
        sa.Column("output_token_count", sa.Integer(), nullable=False),
        sa.Column("api_call_timestamp", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
    )

    # company_document_configs
    op.create_table(
        "company_document_configs",
        sa.Column("config_id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.company_id"), nullable=False),
        sa.Column("doc_type_id", sa.Integer(), sa.ForeignKey("document_types.doc_type_id"), nullable=False),
        sa.Column("prompt_path", sa.String(length=255), nullable=False),
        sa.Column("schema_path", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("company_id", "doc_type_id", name="uq_company_doc_type"),
    )

    # department_doc_type_access (association)
    op.create_table(
        "department_doc_type_access",
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.department_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("doc_type_id", sa.Integer(), sa.ForeignKey("document_types.doc_type_id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("department_doc_type_access")
    op.drop_table("company_document_configs")
    op.drop_table("api_usage")
    op.drop_table("document_files")
    op.drop_table("files")
    op.drop_table("processing_jobs")
    op.drop_table("batch_jobs")
    op.drop_table("companies")
    op.drop_table("document_types")
    op.drop_table("users")
    op.drop_table("departments")

