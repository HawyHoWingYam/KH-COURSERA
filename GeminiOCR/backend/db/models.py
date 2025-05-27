from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text, DateTime, BigInteger, Enum, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .database import Base
import uuid

class FileCategory(enum.Enum):
    original_upload = "original_upload"
    processed_image = "processed_image"
    json_output = "json_output"
    excel_output = "excel_output"

class Department(Base):
    __tablename__ = "departments"
    
    department_id = Column(Integer, primary_key=True)
    department_name = Column(String(255), unique=True, nullable=False)
    
    users = relationship("User", back_populates="department")
    document_types = relationship("DocumentType", secondary="department_doc_type_access", back_populates="departments")

class User(Base):
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True)
    cognito_sub = Column(String(36), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(String(50), nullable=False, default="user")
    department_id = Column(Integer, ForeignKey("departments.department_id", ondelete="SET NULL"), nullable=True)
    
    department = relationship("Department", back_populates="users")
    jobs = relationship("ProcessingJob", back_populates="uploader")

class DocumentType(Base):
    __tablename__ = "document_types"
    
    doc_type_id = Column(Integer, primary_key=True)
    type_name = Column(String(255), unique=True, nullable=False)
    type_code = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    
    departments = relationship("Department", secondary="department_doc_type_access", back_populates="document_types")
    companies = relationship("CompanyDocumentConfig", back_populates="document_type")
    jobs = relationship("ProcessingJob", back_populates="document_type")

class DepartmentDocTypeAccess(Base):
    __tablename__ = "department_doc_type_access"
    
    department_id = Column(Integer, ForeignKey("departments.department_id", ondelete="CASCADE"), primary_key=True)
    doc_type_id = Column(Integer, ForeignKey("document_types.doc_type_id", ondelete="CASCADE"), primary_key=True)

class Company(Base):
    __tablename__ = "companies"
    
    company_id = Column(Integer, primary_key=True)
    company_name = Column(String(255), unique=True, nullable=False)
    company_code = Column(String(50), unique=True, nullable=False)
    active = Column(Boolean, default=True)
    
    document_configs = relationship("CompanyDocumentConfig", back_populates="company")
    jobs = relationship("ProcessingJob", back_populates="company")

class CompanyDocumentConfig(Base):
    __tablename__ = "company_document_configs"
    
    config_id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False)
    doc_type_id = Column(Integer, ForeignKey("document_types.doc_type_id", ondelete="CASCADE"), nullable=False)
    prompt_path = Column(String(512), nullable=False)
    schema_path = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    active = Column(Boolean, default=True)
    
    company = relationship("Company", back_populates="document_configs")
    document_type = relationship("DocumentType", back_populates="companies")
    jobs = relationship("ProcessingJob", back_populates="config")
    
    __table_args__ = (UniqueConstraint('company_id', 'doc_type_id'),)

class File(Base):
    __tablename__ = "files"
    
    file_id = Column(Integer, primary_key=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(BigInteger)
    mime_type = Column(String(100))
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    s3_bucket = Column(String(255))
    s3_key = Column(String(512))
    
    document_associations = relationship("DocumentFile", back_populates="file")

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    
    job_id = Column(Integer, primary_key=True)
    original_filename = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    error_message = Column(Text)
    uploader_user_id = Column(Integer, ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    doc_type_id = Column(Integer, ForeignKey("document_types.doc_type_id", ondelete="RESTRICT"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.company_id", ondelete="RESTRICT"), nullable=False)
    config_id = Column(Integer, ForeignKey("company_document_configs.config_id", ondelete="RESTRICT"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    uploader = relationship("User", back_populates="jobs")
    document_type = relationship("DocumentType", back_populates="jobs")
    company = relationship("Company", back_populates="jobs")
    config = relationship("CompanyDocumentConfig", back_populates="jobs")
    files = relationship("DocumentFile", back_populates="job")
    api_usages = relationship("ApiUsage", back_populates="job")

class DocumentFile(Base):
    __tablename__ = "document_files"
    
    document_file_id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("processing_jobs.job_id", ondelete="CASCADE"), nullable=False)
    file_id = Column(Integer, ForeignKey("files.file_id", ondelete="CASCADE"), nullable=False)
    file_category = Column(Enum(FileCategory), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    job = relationship("ProcessingJob", back_populates="files")
    file = relationship("File", back_populates="document_associations")
    
    __table_args__ = (UniqueConstraint('job_id', 'file_category'),)

class ApiUsage(Base):
    __tablename__ = "api_usage"
    
    usage_id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("processing_jobs.job_id", ondelete="CASCADE"), nullable=False)
    input_token_count = Column(Integer, nullable=False)
    output_token_count = Column(Integer, nullable=False)
    api_call_timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    job = relationship("ProcessingJob", back_populates="api_usages") 