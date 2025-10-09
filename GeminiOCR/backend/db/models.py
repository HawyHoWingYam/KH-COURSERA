from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    DateTime,
    UniqueConstraint,
    Float,
)
from sqlalchemy.orm import relationship
import enum
from sqlalchemy.dialects.postgresql import JSON
from .database import Base
from datetime import datetime


class FileCategory(enum.Enum):
    original_upload = "original_upload"
    processed_image = "processed_image"
    json_output = "json_output"
    excel_output = "excel_output"


class StorageType(enum.Enum):
    local = "local"
    s3 = "s3"


class Department(Base):
    __tablename__ = "departments"

    department_id = Column(Integer, primary_key=True)
    department_name = Column(String(255), unique=True, nullable=False)

    users = relationship("User", back_populates="department")
    document_types = relationship(
        "DocumentType",
        secondary="department_doc_type_access",
        back_populates="departments",
    )


class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True)
    cognito_sub = Column(String(36), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(String(50), nullable=False, default="user")
    department_id = Column(
        Integer,
        ForeignKey("departments.department_id", ondelete="SET NULL"),
        nullable=True,
    )

    department = relationship("Department", back_populates="users")


class DocumentType(Base):
    __tablename__ = "document_types"

    doc_type_id = Column(Integer, primary_key=True)
    type_name = Column(String(100), nullable=False, unique=True)
    type_code = Column(String(50), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    template_json_path = Column(
        String(500),
        nullable=True,
        comment="S3 key or URL for uploaded template JSON file",
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    departments = relationship(
        "Department",
        secondary="department_doc_type_access",
        back_populates="document_types",
    )
    configs = relationship("CompanyDocumentConfig", back_populates="document_type")
    jobs = relationship("ProcessingJob", back_populates="document_type")
    batch_jobs = relationship("BatchJob", back_populates="document_type")
    primary_orders = relationship(
        "OcrOrder",
        back_populates="primary_doc_type",
        foreign_keys="OcrOrder.primary_doc_type_id",
    )


class DepartmentDocTypeAccess(Base):
    __tablename__ = "department_doc_type_access"

    department_id = Column(
        Integer,
        ForeignKey("departments.department_id", ondelete="CASCADE"),
        primary_key=True,
    )
    doc_type_id = Column(
        Integer,
        ForeignKey("document_types.doc_type_id", ondelete="CASCADE"),
        primary_key=True,
    )


class Company(Base):
    __tablename__ = "companies"

    company_id = Column(Integer, primary_key=True)
    company_name = Column(String(100), nullable=False, unique=True)
    company_code = Column(String(50), nullable=False, unique=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    configs = relationship("CompanyDocumentConfig", back_populates="company")
    jobs = relationship("ProcessingJob", back_populates="company")
    batch_jobs = relationship("BatchJob", back_populates="company")


class CompanyDocumentConfig(Base):
    __tablename__ = "company_document_configs"

    config_id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    doc_type_id = Column(
        Integer, ForeignKey("document_types.doc_type_id"), nullable=False
    )
    prompt_path = Column(String(500), nullable=True, comment='Path to prompt file (supports local paths and S3 URIs like s3://bucket/prompts/...)')
    schema_path = Column(String(500), nullable=True, comment='Path to schema file (supports local paths and S3 URIs like s3://bucket/schemas/...)')
    storage_type = Column(Enum(StorageType), nullable=False, default=StorageType.local, comment='Storage backend type for prompts and schemas')
    storage_metadata = Column(JSON, nullable=True, comment='Additional metadata for storage backend (e.g., S3 bucket info, cache settings)')
    original_prompt_filename = Column(String(255), nullable=True, comment='Original filename of uploaded prompt file (e.g., invoice_prompt.txt)')
    original_schema_filename = Column(String(255), nullable=True, comment='Original filename of uploaded schema file (e.g., invoice_schema.json)')
    default_mapping_keys = Column(JSON, nullable=True, default=list, comment='Default mapping keys for auto-mapping [key1, key2, key3]')
    auto_mapping_enabled = Column(Boolean, default=False, comment='Whether to enable auto-mapping for this document type')
    cross_field_mappings = Column(JSON, nullable=True, default=dict, comment='Cross-field mappings for semantic field mapping {"ocr_field": "mapping_field"}')
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="configs")
    document_type = relationship("DocumentType", back_populates="configs")

    __table_args__ = (UniqueConstraint("company_id", "doc_type_id"),)


class File(Base):
    __tablename__ = "files"

    file_id = Column(Integer, primary_key=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(255), nullable=False, unique=True)
    file_type = Column(String(255), nullable=False)
    file_size = Column(BigInteger, nullable=True)
    mime_type = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    s3_bucket = Column(String(255), nullable=True)
    s3_key = Column(String(255), nullable=True)

    document_files = relationship("DocumentFile", back_populates="file")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    job_id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    doc_type_id = Column(
        Integer, ForeignKey("document_types.doc_type_id"), nullable=False
    )
    s3_pdf_path = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    original_filename = Column(String(255), nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Add timing fields
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)

    company = relationship("Company", back_populates="jobs")
    document_type = relationship("DocumentType", back_populates="jobs")
    files = relationship("DocumentFile", back_populates="job")
    api_usages = relationship("ApiUsage", back_populates="job")
    batch_id = Column(Integer, ForeignKey("batch_jobs.batch_id"), nullable=True)
    batch_job = relationship("BatchJob", back_populates="jobs")


class DocumentFile(Base):
    __tablename__ = "document_files"

    document_file_id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("processing_jobs.job_id"), nullable=False)
    file_id = Column(Integer, ForeignKey("files.file_id"), nullable=False)
    file_category = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("ProcessingJob", back_populates="files")
    file = relationship("File", back_populates="document_files")

    __table_args__ = (UniqueConstraint("job_id", "file_category"),)


class ApiUsage(Base):
    __tablename__ = "api_usage"

    usage_id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("processing_jobs.job_id"), nullable=False)
    input_token_count = Column(Integer, nullable=False)
    output_token_count = Column(Integer, nullable=False)
    api_call_timestamp = Column(DateTime, default=datetime.now, nullable=False)
    model = Column(String(255), nullable=False)

    # Add new fields for timing
    processing_time_seconds = Column(Float, nullable=True)
    status = Column(
        String(50), nullable=True
    )  # success, error, success_with_fallback, etc.

    # Existing relationships
    job = relationship("ProcessingJob", back_populates="api_usages")


class UploadType(enum.Enum):
    single_file = "single_file"
    multiple_files = "multiple_files"
    zip_file = "zip_file"
    mixed = "mixed"


class BatchJob(Base):
    __tablename__ = "batch_jobs"

    batch_id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    doc_type_id = Column(
        Integer, ForeignKey("document_types.doc_type_id"), nullable=False
    )
    uploader_user_id = Column(Integer, ForeignKey("users.user_id"), nullable=True)
    
    # Updated for unified batch system
    upload_description = Column(String(255), nullable=True, comment='Description of uploaded files (filename or summary)')
    s3_upload_path = Column(String(255), nullable=True, comment='S3 path to uploaded files')
    upload_type = Column(Enum(UploadType), nullable=False, default=UploadType.single_file, comment='Type of upload batch')
    original_file_names = Column(JSON, nullable=True, comment='Array of original uploaded filenames')
    file_count = Column(Integer, nullable=False, default=0, comment='Total number of files in this batch')
    
    # Keep legacy column for backward compatibility during transition
    original_zipfile = Column(String(255), nullable=True)
    
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    status = Column(String(20), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    json_output_path = Column(String(255), nullable=True)
    excel_output_path = Column(String(255), nullable=True)
    csv_output_path = Column(String(255), nullable=True)
    
    # Cost allocation output files
    netsuite_csv_path = Column(String(255), nullable=True, comment='Path to NetSuite-ready CSV file')
    matching_report_path = Column(String(255), nullable=True, comment='Path to matching details report (Excel)')
    summary_report_path = Column(String(255), nullable=True, comment='Path to cost summary report (Excel)')
    unmatched_count = Column(Integer, nullable=True, default=0, comment='Number of unmatched records in cost allocation')
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    company = relationship("Company", back_populates="batch_jobs")
    document_type = relationship("DocumentType", back_populates="batch_jobs")
    jobs = relationship("ProcessingJob", back_populates="batch_job")
    uploader = relationship("User", backref="batch_jobs")


# OCR Order System Models

class OrderStatus(enum.Enum):
    DRAFT = "DRAFT"
    PROCESSING = "PROCESSING"
    OCR_COMPLETED = "OCR_COMPLETED"  # NEW: OCR finished, ready for mapping configuration
    MAPPING = "MAPPING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    LOCKED = "LOCKED"  # NEW: Order is locked, no modifications allowed


class OrderItemStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class OcrOrder(Base):
    __tablename__ = "ocr_orders"

    order_id = Column(Integer, primary_key=True)
    order_name = Column(String(255), nullable=True, comment='User-friendly name for the order')
    status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.DRAFT, comment='Current status of the order')
    mapping_file_path = Column(String(500), nullable=True, comment='S3 path to uploaded mapping file (Excel/CSV)')
    mapping_keys = Column(JSON, nullable=True, comment='Array of 1-3 mapping keys selected by user [key1, key2, key3]')
    final_report_paths = Column(JSON, nullable=True, comment='Paths to final consolidated reports (NetSuite CSV, Excel reports)')
    total_items = Column(Integer, nullable=False, default=0, comment='Total number of order items')
    completed_items = Column(Integer, nullable=False, default=0, comment='Number of completed order items')
    failed_items = Column(Integer, nullable=False, default=0, comment='Number of failed order items')
    error_message = Column(Text, nullable=True, comment='Error message if order processing fails')
    primary_doc_type_id = Column(
        Integer,
        ForeignKey("document_types.doc_type_id", ondelete="SET NULL"),
        nullable=True,
        comment='Primary document type driving template-based special CSV generation',
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    items = relationship("OcrOrderItem", back_populates="order", cascade="all, delete-orphan")
    primary_doc_type = relationship(
        "DocumentType",
        back_populates="primary_orders",
        foreign_keys=[primary_doc_type_id],
    )


class OcrOrderItem(Base):
    __tablename__ = "ocr_order_items"

    item_id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("ocr_orders.order_id", ondelete="CASCADE"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.company_id"), nullable=False)
    doc_type_id = Column(Integer, ForeignKey("document_types.doc_type_id"), nullable=False)
    item_name = Column(String(255), nullable=True, comment='User-friendly name for this item')
    status = Column(Enum(OrderItemStatus), nullable=False, default=OrderItemStatus.PENDING)
    file_count = Column(Integer, nullable=False, default=0, comment='Number of files in this item')
    ocr_result_json_path = Column(String(500), nullable=True, comment='S3 path to OCR result JSON file')
    ocr_result_csv_path = Column(String(500), nullable=True, comment='S3 path to OCR result CSV file')
    mapping_keys = Column(JSON, nullable=True, comment='Selected mapping keys for this item (up to 3 keys)')
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    order = relationship("OcrOrder", back_populates="items")
    company = relationship("Company")
    document_type = relationship("DocumentType")
    files = relationship("OrderItemFile", back_populates="order_item", cascade="all, delete-orphan")


class OrderItemFile(Base):
    __tablename__ = "order_item_files"

    item_id = Column(Integer, ForeignKey("ocr_order_items.item_id", ondelete="CASCADE"), primary_key=True)
    file_id = Column(Integer, ForeignKey("files.file_id", ondelete="CASCADE"), primary_key=True)
    upload_order = Column(Integer, nullable=True, comment='Order in which file was uploaded to this item')
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    order_item = relationship("OcrOrderItem", back_populates="files")
    file = relationship("File")
