from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    Form,
    WebSocket,
    Depends,
    BackgroundTasks,
    Query,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
import tempfile
import zipfile
from datetime import datetime, timedelta
import json
import logging
import asyncio
from sqlalchemy import func
import time

# 導入配置管理器
from config_loader import config_loader, get_api_key_manager, validate_and_log_config

from db.database import get_db, engine, get_database_info
from db.models import (
    Base,
    Company,
    DocumentType,
    CompanyDocumentConfig,
    ProcessingJob,
    File as DBFile,
    DocumentFile,
    ApiUsage,
    BatchJob,
    UploadType,
)
from main import extract_text_from_image, extract_text_from_pdf
from utils.excel_converter import json_to_excel
from utils.s3_storage import get_s3_manager, is_s3_enabled
from utils.file_storage import get_file_storage
from utils.prompt_schema_manager import get_prompt_schema_manager, load_prompt_and_schema
from utils.company_file_manager import FileType
from utils.force_delete_manager import ForceDeleteManager

# 獲取應用配置
try:
    app_config = config_loader.get_app_config()
    logger = logging.getLogger(__name__)

    # 驗證配置
    validate_and_log_config()

except Exception as e:
    logging.error(f"Failed to load configuration: {e}")
    raise

# Create tables only in development/test environments; rely on Alembic elsewhere
try:
    env = app_config.get("environment", "development") if 'app_config' in globals() else os.getenv("ENVIRONMENT", "development")
    if env in {"development", "test"}:
        if engine:
            Base.metadata.create_all(bind=engine)
            logger.info("✅ Database tables created/verified (dev/test mode)")
        else:
            logger.warning("⚠️  Database engine not initialized, tables not created")
    else:
        logger.info("ℹ️ Skipping Base.metadata.create_all outside dev/test (use Alembic)")
except Exception as e:
    logger.error(f"❌ Failed during table initialization: {e}")

app = FastAPI(title="Document Processing API")

# Request models for migration
class MigrateJobsRequest(BaseModel):
    target_company_id: int

class MigrateDocTypeJobsRequest(BaseModel):
    target_doc_type_id: int

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# WebSocket connections store
active_connections = {}


# Health check endpoint
@app.get("/health")
def health_check():
    """增強的健康檢查端點"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {},
        "config": {},
    }

    # 檢查數據庫連接
    try:
        db_info = get_database_info()
        health_status["services"]["database"] = {
            "status": "healthy" if db_info["status"] == "connected" else "unhealthy",
            "info": db_info,
        }
        if db_info["status"] != "connected":
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "unhealthy"

    # 檢查上傳目錄
    try:
        uploads_path = "uploads"
        if os.path.exists(uploads_path) and os.access(uploads_path, os.W_OK):
            health_status["services"]["storage"] = {
                "status": "healthy",
                "message": "Uploads directory accessible",
            }
        else:
            health_status["services"]["storage"] = {
                "status": "unhealthy",
                "message": "Uploads directory not accessible",
            }
            if health_status["status"] == "healthy":
                health_status["status"] = "degraded"
    except Exception as e:
        health_status["services"]["storage"] = {"status": "unhealthy", "error": str(e)}
        if health_status["status"] == "healthy":
            health_status["status"] = "degraded"

    # 檢查配置狀態
    try:
        api_keys = config_loader.get_gemini_api_keys()
        app_config = config_loader.get_app_config()

        health_status["config"] = {
            "gemini_api_keys": len(api_keys),
            "environment": app_config["environment"],
            "model": app_config["model_name"],
            "api_base_url": app_config["api_base_url"],
        }

        health_status["services"]["configuration"] = {
            "status": "healthy",
            "message": "Configuration loaded successfully",
        }
    except Exception as e:
        health_status["services"]["configuration"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        if health_status["status"] == "healthy":
            health_status["status"] = "degraded"

    # 檢查 S3 存储状态
    try:
        if is_s3_enabled():
            s3_manager = get_s3_manager()
            s3_health = s3_manager.get_health_status()
            health_status["services"]["s3_storage"] = {
                "status": s3_health["status"],
                "info": s3_health,
                "message": f"S3 storage: {s3_health['status']}",
            }
            if (
                s3_health["status"] != "healthy"
                and health_status["status"] == "healthy"
            ):
                health_status["status"] = "degraded"
        else:
            health_status["services"]["s3_storage"] = {
                "status": "disabled",
                "message": "Using local file storage",
            }
            health_status["config"]["storage_type"] = "local"
    except Exception as e:
        health_status["services"]["s3_storage"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        if health_status["status"] == "healthy":
            health_status["status"] = "degraded"

    # 檢查 WebSocket 連接狀態
    try:
        websocket_status = {
            "active_connections": len(active_connections),
            "connection_ids": list(active_connections.keys()),
        }

        health_status["services"]["websocket"] = {
            "status": "healthy",
            "info": websocket_status,
            "message": f"{len(active_connections)} active WebSocket connections",
        }

        health_status["websocket"] = websocket_status

    except Exception as e:
        health_status["services"]["websocket"] = {
            "status": "unhealthy",
            "error": str(e),
        }
        if health_status["status"] == "healthy":
            health_status["status"] = "degraded"

    # 設置適當的 HTTP 狀態碼
    status_code = 200
    if health_status["status"] == "unhealthy":
        status_code = 503
    elif health_status["status"] == "degraded":
        status_code = 200  # 對於降級服務仍返回 200

    return JSONResponse(content=health_status, status_code=status_code)


# Companies API endpoints
@app.get("/companies", response_model=List[dict])
def get_companies(db: Session = Depends(get_db)):
    companies = db.query(Company).all()
    return [
        {
            "company_id": company.company_id,
            "company_name": company.company_name,
            "company_code": company.company_code,
            "active": company.active,
            "created_at": company.created_at.isoformat(),
            "updated_at": company.updated_at.isoformat(),
        }
        for company in companies
    ]


@app.post("/companies", response_model=dict)
def create_company(company_data: dict, db: Session = Depends(get_db)):
    company = Company(
        company_name=company_data["company_name"],
        company_code=company_data["company_code"],
        active=company_data.get("active", True),
    )

    db.add(company)
    db.commit()
    db.refresh(company)

    return {
        "company_id": company.company_id,
        "company_name": company.company_name,
        "company_code": company.company_code,
        "active": company.active,
        "created_at": company.created_at.isoformat(),
        "updated_at": company.updated_at.isoformat(),
    }


@app.get("/companies/{company_id}", response_model=dict)
def get_company(company_id: int, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.company_id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    return {
        "company_id": company.company_id,
        "company_name": company.company_name,
        "company_code": company.company_code,
        "active": company.active,
        "created_at": company.created_at.isoformat(),
        "updated_at": company.updated_at.isoformat(),
    }


@app.put("/companies/{company_id}", response_model=dict)
def update_company(company_id: int, company_data: dict, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.company_id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    company.company_name = company_data["company_name"]
    company.company_code = company_data["company_code"]
    company.active = company_data.get("active", company.active)

    db.commit()
    db.refresh(company)

    return {
        "company_id": company.company_id,
        "company_name": company.company_name,
        "company_code": company.company_code,
        "active": company.active,
        "created_at": company.created_at.isoformat(),
        "updated_at": company.updated_at.isoformat(),
    }


@app.delete("/companies/{company_id}")
def delete_company(company_id: int, db: Session = Depends(get_db)):
    from utils.dependency_checker import check_can_delete_company
    
    # 使用統一的依賴檢查服務
    can_delete, error_message = check_can_delete_company(db, company_id)
    
    if not can_delete:
        if "not found" in error_message:
            raise HTTPException(status_code=404, detail=error_message)
        else:
            raise HTTPException(status_code=400, detail=error_message)
    
    # 獲取公司信息
    company = db.query(Company).filter(Company.company_id == company_id).first()
    
    try:
        db.delete(company)
        db.commit()
        return {"message": f"Company '{company.company_name}' deleted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting company {company_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete company: {str(e)}"
        )


# Document Types API endpoints
@app.get("/document-types", response_model=List[dict])
def get_document_types(db: Session = Depends(get_db)):
    doc_types = db.query(DocumentType).all()
    return [
        {
            "doc_type_id": doc_type.doc_type_id,
            "type_name": doc_type.type_name,
            "type_code": doc_type.type_code,
            "description": doc_type.description,
            "created_at": doc_type.created_at.isoformat(),
            "updated_at": doc_type.updated_at.isoformat(),
        }
        for doc_type in doc_types
    ]


@app.post("/document-types", response_model=dict)
def create_document_type(doc_type_data: dict, db: Session = Depends(get_db)):
    doc_type = DocumentType(
        type_name=doc_type_data["type_name"],
        type_code=doc_type_data["type_code"],
        description=doc_type_data.get("description", ""),
    )

    db.add(doc_type)
    db.commit()
    db.refresh(doc_type)

    return {
        "doc_type_id": doc_type.doc_type_id,
        "type_name": doc_type.type_name,
        "type_code": doc_type.type_code,
        "description": doc_type.description,
        "created_at": doc_type.created_at.isoformat(),
        "updated_at": doc_type.updated_at.isoformat(),
    }


@app.get("/document-types/{doc_type_id}", response_model=dict)
def get_document_type(doc_type_id: int, db: Session = Depends(get_db)):
    doc_type = (
        db.query(DocumentType).filter(DocumentType.doc_type_id == doc_type_id).first()
    )
    if not doc_type:
        raise HTTPException(status_code=404, detail="Document type not found")

    return {
        "doc_type_id": doc_type.doc_type_id,
        "type_name": doc_type.type_name,
        "type_code": doc_type.type_code,
        "description": doc_type.description,
        "created_at": doc_type.created_at.isoformat(),
        "updated_at": doc_type.updated_at.isoformat(),
    }


@app.put("/document-types/{doc_type_id}", response_model=dict)
def update_document_type(
    doc_type_id: int, doc_type_data: dict, db: Session = Depends(get_db)
):
    doc_type = (
        db.query(DocumentType).filter(DocumentType.doc_type_id == doc_type_id).first()
    )
    if not doc_type:
        raise HTTPException(status_code=404, detail="Document type not found")

    doc_type.type_name = doc_type_data["type_name"]
    doc_type.type_code = doc_type_data["type_code"]
    doc_type.description = doc_type_data.get("description", doc_type.description)

    db.commit()
    db.refresh(doc_type)

    return {
        "doc_type_id": doc_type.doc_type_id,
        "type_name": doc_type.type_name,
        "type_code": doc_type.type_code,
        "description": doc_type.description,
        "created_at": doc_type.created_at.isoformat(),
        "updated_at": doc_type.updated_at.isoformat(),
    }


@app.delete("/document-types/{doc_type_id}")
def delete_document_type(doc_type_id: int, db: Session = Depends(get_db)):
    from utils.dependency_checker import check_can_delete_document_type
    
    # 使用統一的依賴檢查服務
    can_delete, error_message = check_can_delete_document_type(db, doc_type_id)
    
    if not can_delete:
        if "not found" in error_message:
            raise HTTPException(status_code=404, detail=error_message)
        else:
            raise HTTPException(status_code=400, detail=error_message)
    
    # 獲取文檔類型信息
    doc_type = db.query(DocumentType).filter(DocumentType.doc_type_id == doc_type_id).first()
    
    try:
        db.delete(doc_type)
        db.commit()
        return {"message": f"Document type '{doc_type.type_name}' deleted successfully"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting document type {doc_type_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document type: {str(e)}"
        )


# Dependency Management API endpoints
@app.get("/companies/{company_id}/dependencies")
def get_company_dependencies(company_id: int, db: Session = Depends(get_db)):
    """獲取公司的詳細依賴關係信息"""
    from utils.dependency_checker import DependencyChecker
    
    checker = DependencyChecker(db)
    dependencies = checker.check_company_dependencies(company_id)
    
    if not dependencies["exists"]:
        raise HTTPException(status_code=404, detail=dependencies["error"])
    
    # 如果有依賴，獲取詳細信息和遷移建議
    if not dependencies["can_delete"]:
        dependencies["detailed_dependencies"] = checker.get_detailed_dependencies("company", company_id)
        dependencies["migration_targets"] = checker.suggest_migration_targets("company", company_id)
    
    return dependencies


@app.get("/document-types/{doc_type_id}/dependencies")
def get_document_type_dependencies(doc_type_id: int, db: Session = Depends(get_db)):
    """獲取文檔類型的詳細依賴關係信息"""
    from utils.dependency_checker import DependencyChecker
    
    checker = DependencyChecker(db)
    dependencies = checker.check_document_type_dependencies(doc_type_id)
    
    if not dependencies["exists"]:
        raise HTTPException(status_code=404, detail=dependencies["error"])
    
    # 如果有依賴，獲取詳細信息和遷移建議
    if not dependencies["can_delete"]:
        dependencies["detailed_dependencies"] = checker.get_detailed_dependencies("document_type", doc_type_id)
        dependencies["migration_targets"] = checker.suggest_migration_targets("document_type", doc_type_id)
    
    return dependencies


@app.post("/companies/{company_id}/migrate-jobs")
def migrate_company_jobs(
    company_id: int, 
    request: MigrateJobsRequest,
    db: Session = Depends(get_db)
):
    """將公司的處理作業遷移到另一個公司"""
    from utils.dependency_checker import DependencyChecker
    
    # 驗證源公司和目標公司存在
    source_company = db.query(Company).filter(Company.company_id == company_id).first()
    target_company = db.query(Company).filter(Company.company_id == request.target_company_id).first()
    
    if not source_company:
        raise HTTPException(status_code=404, detail="Source company not found")
    if not target_company:
        raise HTTPException(status_code=404, detail="Target company not found")
    
    try:
        # 遷移 processing jobs
        processing_jobs_updated = (
            db.query(ProcessingJob)
            .filter(ProcessingJob.company_id == company_id)
            .update({"company_id": request.target_company_id})
        )
        
        # 遷移 batch jobs
        batch_jobs_updated = (
            db.query(BatchJob)
            .filter(BatchJob.company_id == company_id)
            .update({"company_id": request.target_company_id})
        )
        
        db.commit()
        
        return {
            "message": f"Successfully migrated jobs from '{source_company.company_name}' to '{target_company.company_name}'",
            "processing_jobs_migrated": processing_jobs_updated,
            "batch_jobs_migrated": batch_jobs_updated
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error migrating company jobs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to migrate jobs: {str(e)}"
        )


@app.post("/document-types/{doc_type_id}/migrate-jobs")
def migrate_document_type_jobs(
    doc_type_id: int, 
    request: MigrateDocTypeJobsRequest,
    db: Session = Depends(get_db)
):
    """將文檔類型的處理作業遷移到另一個文檔類型"""
    from utils.dependency_checker import DependencyChecker
    
    # 驗證源文檔類型和目標文檔類型存在
    source_doc_type = db.query(DocumentType).filter(DocumentType.doc_type_id == doc_type_id).first()
    target_doc_type = db.query(DocumentType).filter(DocumentType.doc_type_id == request.target_doc_type_id).first()
    
    if not source_doc_type:
        raise HTTPException(status_code=404, detail="Source document type not found")
    if not target_doc_type:
        raise HTTPException(status_code=404, detail="Target document type not found")
    
    try:
        # 遷移 processing jobs
        processing_jobs_updated = (
            db.query(ProcessingJob)
            .filter(ProcessingJob.doc_type_id == doc_type_id)
            .update({"doc_type_id": request.target_doc_type_id})
        )
        
        # 遷移 batch jobs
        batch_jobs_updated = (
            db.query(BatchJob)
            .filter(BatchJob.doc_type_id == doc_type_id)
            .update({"doc_type_id": request.target_doc_type_id})
        )
        
        db.commit()
        
        return {
            "message": f"Successfully migrated jobs from '{source_doc_type.type_name}' to '{target_doc_type.type_name}'",
            "processing_jobs_migrated": processing_jobs_updated,
            "batch_jobs_migrated": batch_jobs_updated
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error migrating document type jobs: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to migrate jobs: {str(e)}"
        )


# Configuration API endpoints
@app.get("/configs", response_model=List[dict])
def get_configurations(db: Session = Depends(get_db)):
    configs = db.query(CompanyDocumentConfig).all()
    return [
        {
            "config_id": config.config_id,
            "company_id": config.company_id,
            "company_name": config.company.company_name if config.company else None,
            "doc_type_id": config.doc_type_id,
            "type_name": (
                config.document_type.type_name if config.document_type else None
            ),
            "prompt_path": config.prompt_path,
            "schema_path": config.schema_path,
            "active": config.active,
            "created_at": config.created_at.isoformat(),
            "updated_at": config.updated_at.isoformat(),
        }
        for config in configs
    ]


@app.post("/configs", response_model=dict)
def create_configuration(config_data: dict, db: Session = Depends(get_db)):
    # Check if company and document type exist
    company = (
        db.query(Company)
        .filter(Company.company_id == config_data["company_id"])
        .first()
    )
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    doc_type = (
        db.query(DocumentType)
        .filter(DocumentType.doc_type_id == config_data["doc_type_id"])
        .first()
    )
    if not doc_type:
        raise HTTPException(status_code=404, detail="Document type not found")

    # Check if config already exists
    existing_config = (
        db.query(CompanyDocumentConfig)
        .filter(
            CompanyDocumentConfig.company_id == config_data["company_id"],
            CompanyDocumentConfig.doc_type_id == config_data["doc_type_id"],
        )
        .first()
    )

    if existing_config:
        raise HTTPException(
            status_code=400,
            detail="Configuration already exists for this company and document type",
        )

    config = CompanyDocumentConfig(
        company_id=config_data["company_id"],
        doc_type_id=config_data["doc_type_id"],
        prompt_path=config_data.get("prompt_path"),  # Allow None for new configs
        schema_path=config_data.get("schema_path"),  # Allow None for new configs
        original_prompt_filename=config_data.get("original_prompt_filename"),
        original_schema_filename=config_data.get("original_schema_filename"),
        active=config_data.get("active", True),
    )

    db.add(config)
    db.commit()
    db.refresh(config)

    return {
        "config_id": config.config_id,
        "company_id": config.company_id,
        "company_name": config.company.company_name,
        "doc_type_id": config.doc_type_id,
        "type_name": config.document_type.type_name,
        "prompt_path": config.prompt_path,
        "schema_path": config.schema_path,
        "active": config.active,
        "created_at": config.created_at.isoformat(),
        "updated_at": config.updated_at.isoformat(),
    }


@app.get("/configs/{config_id}", response_model=dict)
def get_configuration(config_id: int, db: Session = Depends(get_db)):
    config = (
        db.query(CompanyDocumentConfig)
        .filter(CompanyDocumentConfig.config_id == config_id)
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    return {
        "config_id": config.config_id,
        "company_id": config.company_id,
        "company_name": config.company.company_name,
        "doc_type_id": config.doc_type_id,
        "type_name": config.document_type.type_name,
        "prompt_path": config.prompt_path,
        "schema_path": config.schema_path,
        "active": config.active,
        "created_at": config.created_at.isoformat(),
        "updated_at": config.updated_at.isoformat(),
    }


@app.put("/configs/{config_id}", response_model=dict)
def update_configuration(
    config_id: int, config_data: dict, db: Session = Depends(get_db)
):
    config = (
        db.query(CompanyDocumentConfig)
        .filter(CompanyDocumentConfig.config_id == config_id)
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    # Update only provided fields (support partial updates)
    if "prompt_path" in config_data:
        config.prompt_path = config_data["prompt_path"]
    if "schema_path" in config_data:
        config.schema_path = config_data["schema_path"]
    if "original_prompt_filename" in config_data:
        config.original_prompt_filename = config_data["original_prompt_filename"]
    if "original_schema_filename" in config_data:
        config.original_schema_filename = config_data["original_schema_filename"]
    if "active" in config_data:
        config.active = config_data["active"]

    db.commit()
    db.refresh(config)

    return {
        "config_id": config.config_id,
        "company_id": config.company_id,
        "company_name": config.company.company_name,
        "doc_type_id": config.doc_type_id,
        "type_name": config.document_type.type_name,
        "prompt_path": config.prompt_path,
        "schema_path": config.schema_path,
        "active": config.active,
        "created_at": config.created_at.isoformat(),
        "updated_at": config.updated_at.isoformat(),
    }


@app.delete("/configs/{config_id}")
def delete_configuration(config_id: int, db: Session = Depends(get_db)):
    config = (
        db.query(CompanyDocumentConfig)
        .filter(CompanyDocumentConfig.config_id == config_id)
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    db.delete(config)
    db.commit()

    return {"message": "Configuration deleted successfully"}


# Configuration file download endpoint (S3-only)
@app.get("/configs/{config_id}/download/{file_type}")
def download_config_file(config_id: int, file_type: str, db: Session = Depends(get_db)):
    """
    Download prompt or schema file for a configuration (S3-only)
    
    Args:
        config_id: Configuration ID
        file_type: "prompt" or "schema"
    """
    # Validate file_type parameter
    if file_type not in ["prompt", "schema"]:
        raise HTTPException(status_code=400, detail="file_type must be 'prompt' or 'schema'")
    
    # Get configuration from database
    config = (
        db.query(CompanyDocumentConfig)
        .filter(CompanyDocumentConfig.config_id == config_id)
        .first()
    )
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    # Get company and document type for S3 path construction
    company = config.company
    doc_type = config.document_type
    if not company or not doc_type:
        raise HTTPException(status_code=500, detail="Configuration missing company or document type")
    
    logger.info(f"📥 S3-only download request - Config ID: {config_id}, Type: {file_type}, Company: {company.company_code}, DocType: {doc_type.type_code}")
    
    try:
        # Always try S3 download first
        s3_manager = get_s3_manager()
        if not s3_manager:
            raise HTTPException(status_code=500, detail="S3 storage not available - S3 is required for downloads")
        
        # Extract filename from stored path or use default
        stored_path = config.prompt_path if file_type == "prompt" else config.schema_path
        if stored_path and "/" in stored_path:
            filename = stored_path.split("/")[-1]
        else:
            # Default filename based on type
            filename = f"{file_type}.{'txt' if file_type == 'prompt' else 'json'}"
        
        # 🚀 SMART DYNAMIC FILE DISCOVERY - Multiple strategies for resilient file finding
        file_content = None
        successful_path = None
        
        # === PRIORITY STRATEGY: STORED DATABASE PATH (highest priority) ===
        logger.info("🎯 Trying STORED database path first")
        try:
            if stored_path:
                logger.info(f"📍 Found stored path in database: {stored_path}")
                
                # Use the new S3 manager method for direct path download
                file_content = s3_manager.download_file_by_stored_path(stored_path)
                
                if file_content is not None:
                    successful_path = stored_path
                    
                    # Get filename from path
                    if "/" in stored_path:
                        filename = stored_path.split("/")[-1]
                    
                    logger.info(f"✅ Downloaded using STORED database path: {stored_path}")
                    logger.info(f"📂 Download filename: {filename}")
                else:
                    logger.info(f"⚠️ Could not download from stored path: {stored_path}")
            else:
                logger.info("⚠️ No stored path in database, trying other strategies...")
                
        except Exception as e:
            logger.warning(f"⚠️ STORED path download failed: {e}")
        
        # === STRATEGY 0: CLEAN PATH STRUCTURE (highest priority fallback) ===
        if file_content is None:
            logger.info("🎯 Trying CLEAN path structure with database-stored filename first")
            try:
                # Get original filename from database first
                original_filename = None
                if file_type == "prompt" and config.original_prompt_filename:
                    original_filename = config.original_prompt_filename
                elif file_type == "schema" and config.original_schema_filename:
                    original_filename = config.original_schema_filename
                
                # Try with original filename from database
                if original_filename:
                    logger.info(f"📁 Using original filename from database: {original_filename}")
                    
                    # Construct clean S3 path: companies/{company_id}/{type}/{doc_type_id}/{config_id}/filename
                    clean_s3_path = f"companies/{company.company_id}/{'prompts' if file_type == 'prompt' else 'schemas'}/{doc_type.doc_type_id}/{config_id}/{original_filename}"
                    
                    # Try to download directly using clean path
                    if file_type == "prompt":
                        file_content = s3_manager.download_prompt_by_id(
                            company_id=company.company_id,
                            doc_type_id=doc_type.doc_type_id,
                            config_id=config_id,
                            filename=original_filename
                        )
                    else:
                        schema_data = s3_manager.download_schema_by_id(
                            company_id=company.company_id,
                            doc_type_id=doc_type.doc_type_id,
                            config_id=config_id,
                            filename=original_filename
                        )
                        if schema_data:
                            import json
                            file_content = json.dumps(schema_data, indent=2, ensure_ascii=False).encode('utf-8')
                    
                    if file_content is not None:
                        successful_path = clean_s3_path
                        filename = original_filename  # Use original filename for download
                        logger.info(f"✅ Found using CLEAN path structure: {successful_path}")
                        logger.info(f"📂 Download filename: {filename}")
                    else:
                        logger.info("⚠️ CLEAN path not found, trying fallback strategies...")
                else:
                    logger.info("⚠️ No original filename in database, trying fallback strategies...")
                    
            except Exception as e:
                logger.info(f"⚠️ CLEAN path download failed: {e}")
        
        # === STRATEGY 1: CONFIG-SPECIFIC paths (most unique) ===
        config_specific_paths = [
            f"config_{config_id}",  # config_6, config_5 (unique per config)
            f"company_{company.company_id}/doctype_{doc_type.doc_type_id}/config_{config_id}",  # company_1/doctype_11/config_6
            f"c{company.company_id}/d{doc_type.doc_type_id}/cfg{config_id}",  # c1/d11/cfg6
        ]
        
        # === STRATEGY 2: ID-based paths (stable) ===
        id_based_paths = [
            f"company_{company.company_id}/doctype_{doc_type.doc_type_id}",  # company_1/doctype_11
            f"c{company.company_id}/d{doc_type.doc_type_id}",  # c1/d11 (shorter)
            f"{company.company_id}_{doc_type.doc_type_id}",    # 1_11 (minimal)
        ]
        
        # === STRATEGY 3: Current name-based paths ===
        name_based_paths = []
        
        # Company variants
        company_variants = [
            company.company_code if company.company_code else "unknown",
            company.company_code.lower() if company.company_code else "unknown",
            company.company_code.upper() if company.company_code else "unknown",
            company.company_name.lower().replace(" ", "_") if company.company_name else "unknown",
            "hana",  # Common fallback
        ]
        
        # Document type variants  
        doc_type_variants = [
            doc_type.type_code if doc_type.type_code else "unknown",
            doc_type.type_name if doc_type.type_name else "unknown", 
            # Handle common transformations
            doc_type.type_code.replace("[Admin]", "[Finance]") if doc_type.type_code and "[Admin]" in doc_type.type_code else None,
            doc_type.type_code.replace("[Finance]", "[Admin]") if doc_type.type_code and "[Finance]" in doc_type.type_code else None,
            doc_type.type_code.replace("[Production]", "[Admin]") if doc_type.type_code and "[Production]" in doc_type.type_code else None,
            # Remove prefixes and clean up
            doc_type.type_code.replace("[Admin]_", "").replace("[Finance]_", "").replace("[Production]_", "") if doc_type.type_code else None,
            # Common patterns
            "[Finance]_hkbn_billing",  # Known working pattern
            "hkbn_billing", "admin_hkbn_billing", "finance_hkbn_billing",
        ]
        
        # Remove None and duplicates
        doc_type_variants = list(set([v for v in doc_type_variants if v]))
        
        # Build all name-based combinations
        for company_variant in set(company_variants):
            for doc_type_variant in doc_type_variants:
                name_based_paths.append(f"{company_variant}/{doc_type_variant}")
        
        # === STRATEGY 4: Enhanced wildcard search in S3 with disambiguation ===
        def try_wildcard_search():
            logger.info(f"🔍 Attempting enhanced wildcard search for config_id={config_id}")
            # List all files and find matches by filename pattern
            all_prompts = s3_manager.list_prompts() if file_type == "prompt" else []
            all_schemas = s3_manager.list_schemas() if file_type == "schema" else []
            all_files = all_prompts if file_type == "prompt" else all_schemas
            
            # Enhanced search terms with priority scoring
            high_priority_terms = [
                f"config_{config_id}",  # Highest priority: exact config match
                f"cfg{config_id}",
                str(config_id),
            ]
            
            medium_priority_terms = [
                f"{company.company_id}_{doc_type.doc_type_id}",
                company.company_code.lower() if company.company_code else "",
                doc_type.type_code.lower() if doc_type.type_code else "",
            ]
            
            low_priority_terms = [
                filename.replace('.txt', '').replace('.json', ''),
                "hkbn", "billing",
                company.company_name.lower() if company.company_name else "",
                doc_type.type_name.lower().replace("[", "").replace("]", "") if doc_type.type_name else ""
            ]
            
            # Find files with scoring system
            scored_matches = []
            
            for file_info in all_files:
                file_key = file_info['key'].lower()
                score = 0
                
                # High priority matches (config-specific)
                for term in high_priority_terms:
                    if term and term.lower() in file_key:
                        score += 100
                        logger.info(f"🎯 HIGH PRIORITY match: {term} in {file_info['key']}")
                
                # Medium priority matches 
                for term in medium_priority_terms:
                    if term and term.lower() in file_key:
                        score += 10
                        logger.info(f"🔍 MEDIUM PRIORITY match: {term} in {file_info['key']}")
                
                # Low priority matches
                for term in low_priority_terms:
                    if term and term.lower() in file_key:
                        score += 1
                        logger.info(f"🔍 LOW PRIORITY match: {term} in {file_info['key']}")
                
                if score > 0:
                    scored_matches.append((score, file_info))
            
            # Sort by score (highest first) and return best match
            if scored_matches:
                scored_matches.sort(key=lambda x: x[0], reverse=True)
                best_score, best_file = scored_matches[0]
                logger.info(f"🏆 Best match with score {best_score}: {best_file['key']}")
                
                # Extract company and doctype from the found path
                path_parts = best_file['key'].split('/')
                if len(path_parts) >= 2:
                    found_company, found_doctype = path_parts[0], path_parts[1]
                    found_filename = path_parts[-1]
                    
                    if file_type == "prompt":
                        return s3_manager.download_prompt_raw(found_company, found_doctype, found_filename), f"{found_company}/{found_doctype}/{found_filename}"
                    else:
                        return s3_manager.download_schema_raw(found_company, found_doctype, found_filename), f"{found_company}/{found_doctype}/{found_filename}"
            
            logger.warning(f"❌ No matches found via wildcard search for config_id={config_id}")
            return None, None
        
        # === EXECUTE SEARCH STRATEGIES ===
        all_paths_to_try = config_specific_paths + id_based_paths + name_based_paths
        
        # Try all path combinations
        for path in all_paths_to_try:
            if file_content is not None:
                break
                
            if '/' in path:
                company_part, doc_type_part = path.split('/', 1)
                logger.info(f"🔍 Trying path: {path}/{filename}")
                
                if file_type == "prompt":
                    file_content = s3_manager.download_prompt_raw(company_part, doc_type_part, filename)
                else:
                    file_content = s3_manager.download_schema_raw(company_part, doc_type_part, filename)
                
                if file_content is not None:
                    successful_path = f"{path}/{filename}"
                    logger.info(f"✅ Found file at: {successful_path}")
                    break
        
        # Try alternative filenames if primary filename fails - with unique identifiers
        if file_content is None:
            alternative_filenames = [
                # Config-specific filenames (most unique)
                f"config_{config_id}_{file_type}.{'txt' if file_type == 'prompt' else 'json'}",  # config_6_prompt.txt
                f"cfg{config_id}_{file_type}.{'txt' if file_type == 'prompt' else 'json'}",      # cfg6_prompt.txt
                f"{config_id}_{file_type}.{'txt' if file_type == 'prompt' else 'json'}",        # 6_prompt.txt
                
                # Company+DocType+Config combinations
                f"{company.company_id}_{doc_type.doc_type_id}_{config_id}_{file_type}.{'txt' if file_type == 'prompt' else 'json'}",  # 2_3_6_prompt.txt
                f"c{company.company_id}_d{doc_type.doc_type_id}_cfg{config_id}_{file_type}.{'txt' if file_type == 'prompt' else 'json'}",  # c2_d3_cfg6_prompt.txt
                
                # Timestamp-based alternatives
                f"{filename.split('.')[0]}_config_{config_id}.{'txt' if file_type == 'prompt' else 'json'}",  # invoice_prompt_config_6.txt
                f"{config_id}_{filename}",  # 6_invoice_prompt.txt
                
                # Original alternatives
                "prompt.txt" if file_type == "prompt" else "schema.json",
                f"{company.company_id}_{doc_type.doc_type_id}_{file_type}.{'txt' if file_type == 'prompt' else 'json'}",
                filename.replace(" ", "_").replace(".", "_").replace("_txt", ".txt").replace("_json", ".json"),
            ]
            
            for alt_filename in alternative_filenames:
                if file_content is not None:
                    break
                    
                for path in all_paths_to_try:
                    if file_content is not None:
                        break
                    
                    if '/' in path:
                        company_part, doc_type_part = path.split('/', 1)
                        logger.info(f"🔍 Trying alternative: {path}/{alt_filename}")
                        
                        if file_type == "prompt":
                            file_content = s3_manager.download_prompt_raw(company_part, doc_type_part, alt_filename)
                        else:
                            file_content = s3_manager.download_schema_raw(company_part, doc_type_part, alt_filename)
                        
                        if file_content is not None:
                            filename = alt_filename
                            successful_path = f"{path}/{alt_filename}"
                            logger.info(f"✅ Found file with alternative name: {successful_path}")
                            break
        
        # Last resort: wildcard search
        if file_content is None:
            logger.info("🔍 Attempting wildcard search as last resort")
            file_content, successful_path = try_wildcard_search()
            if successful_path:
                filename = successful_path.split('/')[-1]
        
        if file_content is None:
            raise HTTPException(
                status_code=404, 
                detail=f"{file_type.title()} file not found in S3 for {company.company_code}/{doc_type.type_code}"
            )
        
        # PRIORITY 1: Try to get original filename from database (most reliable)
        original_filename = filename  # fallback to current filename
        try:
            if file_type == "prompt" and config.original_prompt_filename:
                original_filename = config.original_prompt_filename
                logger.info(f"📁 Using original filename from database: {original_filename}")
            elif file_type == "schema" and config.original_schema_filename:
                original_filename = config.original_schema_filename
                logger.info(f"📁 Using original filename from database: {original_filename}")
            else:
                logger.info(f"⚠️ No original filename in database for {file_type}, trying S3 metadata")
        except Exception as e:
            logger.warning(f"⚠️ Failed to get original filename from database: {e}")
        
        # PRIORITY 2: Try to get original filename from S3 metadata (backup method)
        # Only try S3 metadata if database didn't provide original filename
        if (original_filename == filename and successful_path):
            try:
                # Extract the S3 key from successful_path and get file info
                s3_key = successful_path
                if s3_key.startswith('companies/'):
                    # For ID-based paths, use company file manager to get proper folder
                    folder_type = "prompts" if file_type == "prompt" else "schemas"
                    file_info = s3_manager.get_file_info(s3_key.replace("companies/", ""), folder_type)
                else:
                    # For legacy paths, use the path directly
                    folder_type = "prompts" if file_type == "prompt" else "schemas"
                    file_info = s3_manager.get_file_info(s3_key, folder_type)
                
                if file_info and "metadata" in file_info:
                    metadata = file_info["metadata"]
                    if "original_filename" in metadata:
                        original_filename = metadata["original_filename"]
                        logger.info(f"📁 Retrieved original filename from S3 metadata: {original_filename}")
                    else:
                        logger.info("⚠️ No original_filename in S3 metadata, using stored filename")
            except Exception as e:
                logger.warning(f"⚠️ Failed to retrieve original filename from S3 metadata: {e}")
        
        # Create temporary file for FileResponse
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{original_filename}") as temp_file:
            # Ensure file_content is bytes for writing
            if isinstance(file_content, str):
                temp_file.write(file_content.encode('utf-8'))
            else:
                temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        # Determine content type
        content_type = "text/plain" if file_type == "prompt" else "application/json"
        
        logger.info(f"✅ S3 file download successful: {company.company_code}/{doc_type.type_code}/{original_filename}")
        return FileResponse(
            path=temp_file_path,
            filename=original_filename,
            media_type=content_type
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ S3-only config file download failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download {file_type} file from S3: {str(e)}")


# File upload endpoint
@app.post("/upload", response_model=dict)
async def upload_file(file: UploadFile = File(...), path: str = Form(...)):
    import json  # Import here to ensure availability for exception handling
    
    try:
        # Check if this is a prompt or schema file for S3 upload
        path_parts = path.split('/')
        
        # NEW ID-BASED FORMAT: document_type/{doc_type_id}/{company_id}/prompt|schema/{filename}
        if (len(path_parts) >= 5 and 
            path_parts[0] == "document_type" and 
            path_parts[3] in ["prompt", "schema"]):
            
            # Parse IDs from path
            try:
                doc_type_id = int(path_parts[1])  # Now expecting ID, not code
                company_id = int(path_parts[2])   # Now expecting ID, not code  
            except ValueError:
                # Fallback to legacy name-based format for compatibility
                doc_type_code = path_parts[1]
                company_code = path_parts[2]
                
                # Convert codes to IDs by querying database
                db = next(get_db())
                try:
                    company = db.query(Company).filter(Company.company_code == company_code).first()
                    doc_type = db.query(DocumentType).filter(DocumentType.type_code == doc_type_code).first()
                    
                    if not company or not doc_type:
                        raise HTTPException(status_code=404, detail="Company or document type not found")
                    
                    company_id = company.company_id
                    doc_type_id = doc_type.doc_type_id
                finally:
                    db.close()
            
            file_type = path_parts[3]  # "prompt" or "schema"
            filename = path_parts[4]
            
            logger.info(f"Uploading {file_type} file using ID-based path: company_id={company_id}, doc_type_id={doc_type_id}, filename={filename}")
            
            # Parse config_id from filename if it follows the new format
            config_id = None
            if filename.startswith('config_'):
                try:
                    config_id = int(filename.split('_')[1])
                except (IndexError, ValueError):
                    logger.warning(f"Could not parse config_id from filename: {filename}")
            
            # Get S3 manager for direct ID-based upload
            s3_manager = get_s3_manager()
            if not s3_manager:
                raise HTTPException(status_code=500, detail="S3 storage not available")
            
            # Read file content
            file_content = await file.read()
            
            # Use new ID-based upload methods
            if file_type == "prompt":
                # For prompt files, decode to text
                content_text = file_content.decode('utf-8')
                
                # Use original filename from the upload, not the path filename
                original_filename = file.filename if hasattr(file, 'filename') else filename
                
                # Prepare metadata with original filename
                upload_metadata = {
                    "original_filename": original_filename,
                    "upload_source": "admin_config"
                }
                
                if config_id:
                    # Use ID-based method with config_id and original filename
                    s3_path = s3_manager.upload_prompt_by_id(
                        company_id=company_id,
                        doc_type_id=doc_type_id,
                        config_id=config_id,
                        prompt_content=content_text,
                        filename=original_filename,  # Use original filename instead
                        metadata=upload_metadata
                    )
                else:
                    # Use generic company file method with original filename
                    s3_path = s3_manager.upload_company_file(
                        company_id=company_id,
                        file_type=FileType.PROMPT,
                        content=content_text,
                        filename=original_filename,  # Use original filename instead
                        doc_type_id=doc_type_id,
                        metadata=upload_metadata
                    )
                    
                if s3_path:
                    full_s3_path = f"s3://{s3_manager.bucket_name}/{s3_path}"
                else:
                    raise HTTPException(status_code=500, detail="Failed to upload prompt to S3")
                
            else:  # schema
                # For schema files, parse JSON
                content_text = file_content.decode('utf-8')
                try:
                    schema_data = json.loads(content_text)
                except json.JSONDecodeError as e:
                    raise HTTPException(status_code=400, detail=f"Invalid JSON format: {str(e)}")
                
                # Use original filename from the upload, not the path filename
                original_filename = file.filename if hasattr(file, 'filename') else filename
                
                # Prepare metadata with original filename
                upload_metadata = {
                    "original_filename": original_filename,
                    "upload_source": "admin_config"
                }
                
                if config_id:
                    # Use ID-based method with config_id and original filename
                    s3_path = s3_manager.upload_schema_by_id(
                        company_id=company_id,
                        doc_type_id=doc_type_id,
                        config_id=config_id,
                        schema_data=schema_data,
                        filename=original_filename,  # Use original filename instead
                        metadata=upload_metadata
                    )
                else:
                    # Use generic company file method with original filename
                    s3_path = s3_manager.upload_company_file(
                        company_id=company_id,
                        file_type=FileType.SCHEMA,
                        content=content_text,
                        filename=original_filename,  # Use original filename instead
                        doc_type_id=doc_type_id,
                        metadata=upload_metadata
                    )
                
                if s3_path:
                    full_s3_path = f"s3://{s3_manager.bucket_name}/{s3_path}"
                else:
                    raise HTTPException(status_code=500, detail="Failed to upload schema to S3")
            
            logger.info(f"✅ Successfully uploaded {file_type} using clean path structure: {full_s3_path}")
            logger.info(f"🎯 Clean S3 path format: companies/{company_id}/{file_type}s/{doc_type_id}/{config_id if config_id else 'temp'}/{original_filename}")
            
            # Auto-update configuration with file path if config_id exists
            if config_id:
                try:
                    db = next(get_db())
                    try:
                        config = db.query(CompanyDocumentConfig).filter(
                            CompanyDocumentConfig.config_id == config_id
                        ).first()
                        
                        if config:
                            # Store clean S3 path and original filename
                            original_filename = file.filename if hasattr(file, 'filename') else filename
                            
                            if file_type == "prompt":
                                config.prompt_path = full_s3_path
                                config.original_prompt_filename = original_filename
                                logger.info(f"📝 Updated config {config_id} with clean prompt_path: {full_s3_path} and original_filename: {original_filename}")
                            else:  # schema
                                config.schema_path = full_s3_path
                                config.original_schema_filename = original_filename
                                logger.info(f"📝 Updated config {config_id} with clean schema_path: {full_s3_path} and original_filename: {original_filename}")
                            
                            db.commit()
                        else:
                            logger.warning(f"⚠️ Config {config_id} not found for path update")
                    finally:
                        db.close()
                except Exception as e:
                    logger.error(f"❌ Failed to update config {config_id} with file path: {e}")
                    # Don't fail the upload if config update fails
            
            return {"file_path": full_s3_path}
        
        else:
            # For other file types, use local storage (backward compatibility)
            logger.info(f"Uploading non-prompt/schema file to local storage: {path}")
            
            # Create directories if they don't exist
            directory = os.path.join("uploads", os.path.dirname(path))
            os.makedirs(directory, exist_ok=True)

            # Generate full file path
            file_path = os.path.join("uploads", path)

            # Save file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            return {"file_path": file_path}

    except json.JSONDecodeError as e:
        logger.error(f"Error parsing schema JSON: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON format in schema file: {str(e)}")
    except UnicodeDecodeError as e:
        logger.error(f"Error decoding file content: {str(e)}")
        raise HTTPException(status_code=400, detail=f"File encoding error - ensure UTF-8 encoding: {str(e)}")
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


# WebSocket connection
@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    try:
        await websocket.accept()
        active_connections[job_id] = websocket
        logger.info(f"✅ WebSocket connection established for job_id: {job_id}")

        # Send initial connection confirmation
        await websocket.send_json(
            {
                "type": "connection_established",
                "job_id": job_id,
                "message": "WebSocket connection established successfully",
            }
        )

        try:
            while True:
                # Keep the connection alive and handle any incoming messages
                try:
                    data = await websocket.receive_text()
                    logger.debug(f"Received WebSocket message for job {job_id}: {data}")

                    # Handle ping messages to keep connection alive
                    if data == "ping":
                        await websocket.send_json({"type": "pong", "job_id": job_id})

                except asyncio.TimeoutError:
                    # Send periodic ping to keep connection alive
                    await websocket.send_json({"type": "ping", "job_id": job_id})

        except Exception as connection_error:
            logger.warning(
                f"WebSocket connection error for job_id {job_id}: {str(connection_error)}"
            )

    except Exception as accept_error:
        logger.error(
            f"❌ Failed to accept WebSocket connection for job_id {job_id}: {str(accept_error)}"
        )

    finally:
        if job_id in active_connections:
            del active_connections[job_id]
            logger.info(f"🔌 WebSocket connection closed for job_id: {job_id}")


# Process document endpoint
@app.post("/process", response_model=dict)
async def process_document(
    background_tasks: BackgroundTasks,
    document: UploadFile = File(...),
    company_id: int = Form(...),
    doc_type_id: int = Form(...),
    db: Session = Depends(get_db),
):
    try:
        # Check if company and document type exist
        company = db.query(Company).filter(Company.company_id == company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        doc_type = (
            db.query(DocumentType)
            .filter(DocumentType.doc_type_id == doc_type_id)
            .first()
        )
        if not doc_type:
            raise HTTPException(status_code=404, detail="Document type not found")

        # Check if configuration exists
        config = (
            db.query(CompanyDocumentConfig)
            .filter(
                CompanyDocumentConfig.company_id == company_id,
                CompanyDocumentConfig.doc_type_id == doc_type_id,
                CompanyDocumentConfig.active,
            )
            .first()
        )

        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"No active configuration found for company ID {company_id} and document type ID {doc_type_id}",
            )

        # Verify prompt and schema are accessible (supports both local and S3)
        prompt_schema_manager = get_prompt_schema_manager()
        
        # Check if prompt exists
        prompt_test = await prompt_schema_manager.get_prompt(company.company_code, doc_type.type_code)
        if not prompt_test:
            raise HTTPException(
                status_code=500,
                detail=f"Prompt template not found for {company.company_code}/{doc_type.type_code}",
            )
        
        # Check if schema exists
        schema_test = await prompt_schema_manager.get_schema(company.company_code, doc_type.type_code)
        if not schema_test:
            raise HTTPException(
                status_code=500, 
                detail=f"Schema file not found for {company.company_code}/{doc_type.type_code}"
            )

        # 使用文件存储服务保存上传的文件
        file_storage = get_file_storage()
        try:
            file_path, original_filename = file_storage.save_uploaded_file(
                document, company.company_code, doc_type.type_code
            )
            logger.info(f"📁 文件已保存：{file_path}")
        except Exception as e:
            logger.error(f"❌ 文件保存失败：{e}")
            raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")

        # Create a new processing job
        job = ProcessingJob(
            company_id=company_id,
            doc_type_id=doc_type_id,
            original_filename=original_filename,
            status="pending",
            s3_pdf_path=file_path,  # 现在可能是S3 URL或本地路径
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        job_id = job.job_id

        # Start processing in background but return immediately
        background_tasks.add_task(
            process_document_task,
            job_id,
            file_path,
            company.company_code,
            doc_type.type_code,
        )

        # Return immediately with job ID
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Document processing started",
            "storage_type": "S3" if file_path.startswith("s3://") else "local",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error processing document: {str(e)}"
        )


# Background processing task
async def process_document_task(
    job_id: int,
    file_path: str,
    company_code: str,
    doc_type_code: str,
):
    db = next(get_db())
    file_storage = get_file_storage()
    temp_file_path = None

    try:
        # Update job status
        job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        # Update only existing columns
        job.s3_pdf_path = file_path
        job.status = "processing"
        # Comment out the timing fields until database is updated
        # job.processing_started_at = datetime.now()
        db.commit()

        # Send WebSocket notification
        await send_websocket_message(
            job_id, {"status": "processing", "message": "Document processing started"}
        )

        # Load prompt and schema using the new manager (supports both S3 and local)
        prompt_template, schema_json = await load_prompt_and_schema(company_code, doc_type_code)
        
        if not prompt_template:
            raise ValueError(f"Prompt not found for {company_code}/{doc_type_code}")
        
        if not schema_json:
            raise ValueError(f"Schema not found for {company_code}/{doc_type_code}")

        # Get API key and model from config loader
        try:
            api_key = get_api_key_manager().get_least_used_key()
            model_name = app_config.get("model_name", "gemini-2.5-flash-preview-05-20")
        except ValueError as e:
            raise ValueError(f"API key configuration error: {e}")

        await send_websocket_message(
            job_id,
            {"status": "processing", "message": "Extracting text from document..."},
        )

        # 创建本地临时文件用于处理（如果需要）
        temp_file_path = file_storage.create_temp_file_from_storage(file_path)
        if not temp_file_path:
            raise Exception(f"无法访问文件：{file_path}")

        # Process the document based on file type
        file_extension = os.path.splitext(temp_file_path)[1].lower()

        process_start_time = time.time()

        # Handle based on file type
        if file_extension in [".jpg", ".jpeg", ".png"]:
            # Process image directly
            await send_websocket_message(
                job_id,
                {
                    "status": "processing",
                    "message": "Processing image with Gemini API...",
                },
            )
            result = await extract_text_from_image(
                temp_file_path, prompt_template, schema_json, api_key, model_name
            )
        elif file_extension == ".pdf":
            # Process PDF directly
            await send_websocket_message(
                job_id,
                {
                    "status": "processing",
                    "message": "Processing PDF with Gemini API...",
                },
            )
            result = await extract_text_from_pdf(
                temp_file_path, prompt_template, schema_json, api_key, model_name
            )
        else:
            # Unsupported file type
            raise ValueError(f"Unsupported file type: {file_extension}")

        # Extract results
        json_result = result["text"]
        input_tokens = result["input_tokens"]
        output_tokens = result["output_tokens"]
        processing_time = time.time() - process_start_time

        # Update WebSocket with processing time
        await send_websocket_message(
            job_id,
            {
                "status": "processing",
                "message": f"API processing completed in {processing_time:.2f} seconds",
            },
        )

        # Record API usage with timing metrics
        api_usage = ApiUsage(
            job_id=job_id,
            input_token_count=input_tokens,
            output_token_count=output_tokens,
            api_call_timestamp=datetime.now(),
            model=model_name,
            processing_time_seconds=processing_time,
            status="success",
        )
        db.add(api_usage)
        db.commit()

        # Generate output files - 使用S3存储结果文件
        s3_manager = get_s3_manager()

        # Prepare JSON content
        if isinstance(json_result, str):
            json_content = json_result
            result_obj = json.loads(json_result)
        else:
            json_content = json.dumps(json_result, indent=2, ensure_ascii=False)
            result_obj = json_result

        # Generate S3 key for JSON result
        json_key = f"{company_code}/{doc_type_code}/{job_id}/results.json"

        # Save JSON to S3 results folder
        json_saved = False
        json_file_size = len(json_content.encode("utf-8"))

        if s3_manager:
            json_saved = s3_manager.save_json_result(json_key, result_obj)

        if not json_saved:
            # Fallback to local storage
            output_dir = os.path.join(
                "uploads", company_code, doc_type_code, str(job_id)
            )
            os.makedirs(output_dir, exist_ok=True)
            json_output_path = os.path.join(output_dir, "results.json")

            with open(json_output_path, "w", encoding="utf-8") as f:
                f.write(json_content)
            json_file_size = os.path.getsize(json_output_path)
            json_s3_path = json_output_path
        else:
            json_s3_path = f"s3://{s3_manager.bucket_name}/results/{json_key}"

        # Create file entries for JSON output
        json_file = DBFile(
            file_path=json_s3_path,
            file_name="results.json",
            file_type="application/json",
            file_size=json_file_size,
        )

        db.add(json_file)
        db.commit()
        db.refresh(json_file)

        # Create document file relationship
        json_doc_file = DocumentFile(
            job_id=job_id, file_id=json_file.file_id, file_category="json_output"
        )

        db.add(json_doc_file)

        # Generate Excel file
        excel_key = f"{company_code}/{doc_type_code}/{job_id}/results.xlsx"
        excel_saved = False

        if s3_manager:
            # Create temporary Excel file
            with tempfile.NamedTemporaryFile(
                suffix=".xlsx", delete=False
            ) as temp_excel:
                temp_excel_path = temp_excel.name

            try:
                # Generate Excel file to temporary location
                json_to_excel(result_obj, temp_excel_path, doc_type_code)
                excel_file_size = os.path.getsize(temp_excel_path)

                # Upload to S3 exports folder
                with open(temp_excel_path, "rb") as excel_file_obj:
                    excel_saved = s3_manager.save_excel_export(
                        excel_key, excel_file_obj
                    )
            finally:
                # Clean up temporary file
                if os.path.exists(temp_excel_path):
                    os.unlink(temp_excel_path)

        if not excel_saved:
            # Fallback to local storage
            output_dir = os.path.join(
                "uploads", company_code, doc_type_code, str(job_id)
            )
            os.makedirs(output_dir, exist_ok=True)
            excel_output_path = os.path.join(output_dir, "results.xlsx")

            json_to_excel(result_obj, excel_output_path, doc_type_code)
            excel_file_size = os.path.getsize(excel_output_path)
            excel_s3_path = excel_output_path
        else:
            excel_s3_path = f"s3://{s3_manager.bucket_name}/exports/{excel_key}"

        excel_file = DBFile(
            file_path=excel_s3_path,
            file_name="results.xlsx",
            file_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            file_size=excel_file_size,
        )

        db.add(excel_file)
        db.commit()
        db.refresh(excel_file)

        # Create document file relationship
        excel_doc_file = DocumentFile(
            job_id=job_id, file_id=excel_file.file_id, file_category="excel_output"
        )

        db.add(excel_doc_file)

        # Update job completion info
        job.status = "success"
        # Comment out these lines
        # job.processing_completed_at = datetime.now()
        # job.processing_time_seconds = time.time() - process_start_time
        db.commit()

        # Send WebSocket notification with timing info
        await send_websocket_message(
            job_id,
            {
                "status": "success",
                "message": f"Document processing completed in {processing_time:.2f} seconds",
                "processing_time": processing_time,
                "storage_type": "S3" if file_path.startswith("s3://") else "local",
                "files": [
                    {
                        "id": json_file.file_id,
                        "name": "results.json",
                        "type": "json_output",
                    },
                    {
                        "id": excel_file.file_id,
                        "name": "results.xlsx",
                        "type": "excel_output",
                    },
                ],
            },
        )

    except Exception as e:
        logger.error(f"Error in background processing task for job {job_id}: {str(e)}")

        # Update job status to error with timing info
        if job:
            job.status = "error"
            job.error_message = str(e)
            # Comment out these lines
            # job.processing_completed_at = datetime.now()
            # if hasattr(job, 'processing_started_at') and job.processing_started_at:
            #     job.processing_time_seconds = (datetime.now() - job.processing_started_at).total_seconds()
            db.commit()

        # Send WebSocket notification
        await send_websocket_message(
            job_id, {"status": "error", "message": f"Processing failed: {str(e)}"}
        )
    finally:
        # 清理临时文件
        if temp_file_path and temp_file_path != file_path:  # 只清理真正的临时文件
            file_storage.cleanup_temp_file(temp_file_path)

        db.close()
        db = next(get_db())


# WebSocket message sender
# Enhanced WebSocket message sender with error handling
async def send_websocket_message(job_id: int, message: dict):
    """Send WebSocket message with improved error handling"""
    job_id_str = str(job_id)

    if job_id_str not in active_connections:
        logger.debug(f"No WebSocket connection found for job_id: {job_id}")
        return False

    try:
        websocket = active_connections[job_id_str]

        # Add metadata to message
        enhanced_message = {
            **message,
            "job_id": job_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await websocket.send_json(enhanced_message)
        logger.debug(
            f"✅ WebSocket message sent for job_id {job_id}: {message.get('status', 'unknown')}"
        )
        return True

    except Exception as e:
        logger.warning(
            f"⚠️  Failed to send WebSocket message for job_id {job_id}: {str(e)}"
        )

        # Remove the broken connection
        if job_id_str in active_connections:
            del active_connections[job_id_str]

        return False


# Get job status endpoint
@app.get("/jobs/{job_id}", response_model=dict)
def get_job_status(job_id: int, db: Session = Depends(get_db)):
    job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get associated files
    files_query = (
        db.query(DocumentFile, DBFile)
        .join(DBFile, DocumentFile.file_id == DBFile.file_id)
        .filter(DocumentFile.job_id == job_id)
    )

    files = []
    for doc_file, file in files_query:
        # Calculate file size if not already stored
        file_size = file.file_size
        if file_size is None and os.path.exists(file.file_path):
            file_size = os.path.getsize(file.file_path)
            # Update the file size in the database
            file.file_size = file_size
            db.commit()

        files.append(
            {
                "file_id": file.file_id,
                "file_name": file.file_name,
                "file_path": file.file_path,
                "file_category": doc_file.file_category,
                "file_size": file_size or 0,  # Default to 0 if size can't be determined
                "file_type": file.file_type
                or "application/octet-stream",  # Default content type
                "created_at": file.created_at.isoformat(),
            }
        )

    return {
        "job_id": job.job_id,
        "company_id": job.company_id,
        "company_name": job.company.company_name if job.company else None,
        "doc_type_id": job.doc_type_id,
        "type_name": job.document_type.type_name if job.document_type else None,
        "status": job.status,
        "original_filename": job.original_filename,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "files": files,
    }


# List jobs endpoint
@app.get("/jobs", response_model=List[dict])
async def list_jobs(
    company_id: Optional[int] = None,
    doc_type_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    # Create a regular function (not async) to run in the executor
    def get_jobs():
        # Create a new session to avoid sharing with busy sessions
        with Session(engine) as session:
            query = session.query(ProcessingJob)

            if company_id is not None:
                query = query.filter(ProcessingJob.company_id == company_id)

            if doc_type_id is not None:
                query = query.filter(ProcessingJob.doc_type_id == doc_type_id)

            if status is not None:
                query = query.filter(ProcessingJob.status == status)

            # Order by most recent first
            query = query.order_by(ProcessingJob.created_at.desc())

            # Apply pagination
            jobs = query.offset(offset).limit(limit).all()

            # Convert to dict before leaving the function to avoid session issues
            result = []
            for job in jobs:
                result.append(
                    {
                        "job_id": job.job_id,
                        "company_id": job.company_id,
                        "company_name": job.company.company_name
                        if job.company
                        else None,
                        "doc_type_id": job.doc_type_id,
                        "type_name": job.document_type.type_name
                        if job.document_type
                        else None,
                        "status": job.status,
                        "original_filename": job.original_filename,
                        "created_at": job.created_at.isoformat(),
                        "updated_at": job.updated_at.isoformat(),
                    }
                )
            return result

    # Run the database query in a separate thread using ThreadPoolExecutor
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    executor = ThreadPoolExecutor()
    result = await asyncio.get_event_loop().run_in_executor(executor, get_jobs)

    return result


# Get file download endpoint
@app.get("/files/{file_id}")
def get_file(file_id: int, db: Session = Depends(get_db)):
    file = db.query(DBFile).filter(DBFile.file_id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    if not os.path.exists(file.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return {
        "file_path": file.file_path,
        "file_name": file.file_name,
        "file_type": file.file_type,
    }


# Add this endpoint
@app.get("/download/{file_id}")
def download_file(file_id: int, db: Session = Depends(get_db)):
    file = db.query(DBFile).filter(DBFile.file_id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    logger.info(f"📥 下载请求 - 文件ID: {file_id}, 路径: {file.file_path}")

    # Check if file is stored in S3
    if file.file_path.startswith("s3://"):
        logger.info(f"📥 从S3下载文件: {file.file_path}")
        s3_manager = get_s3_manager()

        if not s3_manager:
            raise HTTPException(status_code=500, detail="S3存储不可用")

        try:
            # Parse S3 path to extract bucket and key
            # Format: s3://bucket-name/folder/path/to/file
            s3_parts = file.file_path.replace("s3://", "").split("/", 1)
            if len(s3_parts) != 2:
                raise HTTPException(status_code=500, detail="无效的S3文件路径")

            bucket_name, full_key = s3_parts

            # Determine folder from the full key
            if full_key.startswith("results/"):
                key = full_key[8:]  # Remove "results/" prefix
                file_content = s3_manager.get_json_result(key)
                if file_content is not None:
                    # Convert dict back to JSON string for download
                    json_str = json.dumps(file_content, ensure_ascii=False, indent=2)
                    file_bytes = json_str.encode("utf-8")
                else:
                    raise HTTPException(status_code=404, detail="S3中未找到文件")
            elif full_key.startswith("exports/"):
                key = full_key[8:]  # Remove "exports/" prefix
                file_bytes = s3_manager.get_excel_export(key)
                if file_bytes is None:
                    raise HTTPException(status_code=404, detail="S3中未找到文件")
            elif full_key.startswith("upload/"):
                key = full_key[7:]  # Remove "upload/" prefix
                file_bytes = s3_manager.download_file(key, folder="upload")
                if file_bytes is None:
                    raise HTTPException(status_code=404, detail="S3中未找到文件")
            else:
                raise HTTPException(status_code=500, detail="无法识别的S3文件夹路径")

            # Create temporary file for FileResponse
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=f"_{file.file_name}"
            ) as temp_file:
                temp_file.write(file_bytes)
                temp_file_path = temp_file.name

            logger.info(f"✅ S3文件下载成功: {file.file_name}")

            # Create custom FileResponse that cleans up temp file
            class CleanupFileResponse(FileResponse):
                def __init__(self, *args, temp_path=None, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.temp_path = temp_path

                async def __call__(self, scope, receive, send):
                    try:
                        await super().__call__(scope, receive, send)
                    finally:
                        if self.temp_path and os.path.exists(self.temp_path):
                            try:
                                os.unlink(self.temp_path)
                                logger.info(f"🧹 清理临时文件: {self.temp_path}")
                            except Exception as e:
                                logger.warning(f"⚠️ 清理临时文件失败: {e}")

            return CleanupFileResponse(
                path=temp_file_path,
                filename=file.file_name,
                media_type=file.file_type or "application/octet-stream",
                temp_path=temp_file_path,
            )

        except Exception as e:
            logger.error(f"❌ S3文件下载失败: {str(e)}")
            raise HTTPException(status_code=500, detail=f"S3文件下载失败: {str(e)}")

    else:
        # Local file handling
        logger.info(f"📥 从本地下载文件: {file.file_path}")
        if not os.path.exists(file.file_path):
            raise HTTPException(status_code=404, detail="本地文件未找到")

        return FileResponse(
            path=file.file_path,
            filename=file.file_name,
            media_type=file.file_type or "application/octet-stream",
        )


# Prompt and Schema Management API endpoints
@app.get("/health/prompts-schemas", response_model=dict)
async def get_prompt_schema_health():
    """Get prompt and schema management system health status"""
    try:
        prompt_schema_manager = get_prompt_schema_manager()
        health = prompt_schema_manager.get_health_status()
        return health
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/prompts-schemas/templates", response_model=dict)
async def list_templates(company_code: Optional[str] = None):
    """List available prompt and schema templates"""
    try:
        prompt_schema_manager = get_prompt_schema_manager()
        templates = await prompt_schema_manager.list_available_templates(company_code)
        return {
            "status": "success",
            "data": templates,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list templates: {e}")


@app.get("/prompts-schemas/{company_code}/{doc_type_code}/prompt", response_model=dict)
async def get_prompt(company_code: str, doc_type_code: str, filename: str = "prompt.txt"):
    """Get prompt content for a specific company and document type"""
    try:
        prompt_schema_manager = get_prompt_schema_manager()
        prompt_content = await prompt_schema_manager.get_prompt(company_code, doc_type_code, filename)
        
        if not prompt_content:
            raise HTTPException(
                status_code=404, 
                detail=f"Prompt not found for {company_code}/{doc_type_code}/{filename}"
            )
        
        return {
            "status": "success",
            "data": {
                "company_code": company_code,
                "doc_type_code": doc_type_code,
                "filename": filename,
                "content": prompt_content,
                "content_length": len(prompt_content)
            },
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get prompt: {e}")


@app.get("/prompts-schemas/{company_code}/{doc_type_code}/schema", response_model=dict)
async def get_schema(company_code: str, doc_type_code: str, filename: str = "schema.json"):
    """Get schema data for a specific company and document type"""
    try:
        prompt_schema_manager = get_prompt_schema_manager()
        schema_data = await prompt_schema_manager.get_schema(company_code, doc_type_code, filename)
        
        if not schema_data:
            raise HTTPException(
                status_code=404, 
                detail=f"Schema not found for {company_code}/{doc_type_code}/{filename}"
            )
        
        return {
            "status": "success",
            "data": {
                "company_code": company_code,
                "doc_type_code": doc_type_code,
                "filename": filename,
                "schema": schema_data
            },
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get schema: {e}")


@app.post("/prompts-schemas/{company_code}/{doc_type_code}/prompt", response_model=dict)
async def upload_prompt(
    company_code: str, 
    doc_type_code: str, 
    prompt_data: dict,
    filename: str = "prompt.txt"
):
    """Upload a new prompt for a specific company and document type"""
    try:
        if "content" not in prompt_data:
            raise HTTPException(status_code=400, detail="Missing 'content' field in request body")
        
        content = prompt_data["content"]
        metadata = prompt_data.get("metadata", {})
        
        prompt_schema_manager = get_prompt_schema_manager()
        success = await prompt_schema_manager.upload_prompt(
            company_code, doc_type_code, content, filename, metadata
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to upload prompt")
        
        return {
            "status": "success",
            "message": f"Prompt uploaded successfully for {company_code}/{doc_type_code}/{filename}",
            "data": {
                "company_code": company_code,
                "doc_type_code": doc_type_code,
                "filename": filename,
                "content_length": len(content)
            },
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload prompt: {e}")


@app.post("/prompts-schemas/{company_code}/{doc_type_code}/schema", response_model=dict)
async def upload_schema(
    company_code: str, 
    doc_type_code: str, 
    schema_request: dict,
    filename: str = "schema.json"
):
    """Upload a new schema for a specific company and document type"""
    try:
        if "schema" not in schema_request:
            raise HTTPException(status_code=400, detail="Missing 'schema' field in request body")
        
        schema_data = schema_request["schema"]
        metadata = schema_request.get("metadata", {})
        
        prompt_schema_manager = get_prompt_schema_manager()
        success = await prompt_schema_manager.upload_schema(
            company_code, doc_type_code, schema_data, filename, metadata
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to upload schema")
        
        return {
            "status": "success",
            "message": f"Schema uploaded successfully for {company_code}/{doc_type_code}/{filename}",
            "data": {
                "company_code": company_code,
                "doc_type_code": doc_type_code,
                "filename": filename,
                "schema_properties": len(schema_data.get("properties", {}))
            },
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload schema: {e}")


@app.post("/prompts-schemas/{company_code}/{doc_type_code}/validate", response_model=dict)
async def validate_prompt_schema(company_code: str, doc_type_code: str):
    """Validate that both prompt and schema exist and are valid for a company/doc_type combination"""
    try:
        # Load both prompt and schema
        prompt_content, schema_data = await load_prompt_and_schema(company_code, doc_type_code)
        
        validation_results = {
            "company_code": company_code,
            "doc_type_code": doc_type_code,
            "prompt": {
                "exists": prompt_content is not None,
                "valid": False,
                "message": ""
            },
            "schema": {
                "exists": schema_data is not None,
                "valid": False,
                "message": ""
            }
        }
        
        # Validate prompt
        if prompt_content:
            from utils.prompt_schema_manager import PromptSchemaValidator
            validator = PromptSchemaValidator()
            is_valid, message = validator.validate_prompt(prompt_content)
            validation_results["prompt"]["valid"] = is_valid
            validation_results["prompt"]["message"] = message
            validation_results["prompt"]["length"] = len(prompt_content)
        else:
            validation_results["prompt"]["message"] = "Prompt not found"
        
        # Validate schema
        if schema_data:
            from utils.prompt_schema_manager import PromptSchemaValidator
            validator = PromptSchemaValidator()
            is_valid, message = validator.validate_schema(schema_data)
            validation_results["schema"]["valid"] = is_valid
            validation_results["schema"]["message"] = message
            validation_results["schema"]["properties_count"] = len(schema_data.get("properties", {}))
        else:
            validation_results["schema"]["message"] = "Schema not found"
        
        overall_valid = (validation_results["prompt"]["valid"] and 
                        validation_results["schema"]["valid"])
        
        return {
            "status": "success",
            "data": validation_results,
            "overall_valid": overall_valid,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate prompt/schema: {e}")


# Initialize database function
@app.on_event("startup")
async def startup_db_client():
    try:
        # Create necessary directories
        os.makedirs("uploads", exist_ok=True)

        # Try connecting to database
        next(get_db())
        logger.info("Successfully connected to database")
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        raise e


# Add this endpoint to your FastAPI app
@app.get("/document-types/{doc_type_id}/companies", response_model=List[dict])
def get_companies_for_document_type(doc_type_id: int, db: Session = Depends(get_db)):
    # Verify document type exists
    doc_type = (
        db.query(DocumentType).filter(DocumentType.doc_type_id == doc_type_id).first()
    )
    if not doc_type:
        raise HTTPException(status_code=404, detail="Document type not found")

    # Get companies that have configurations for this document type
    companies_query = (
        db.query(Company)
        .join(
            CompanyDocumentConfig,
            Company.company_id == CompanyDocumentConfig.company_id,
        )
        .filter(
            CompanyDocumentConfig.doc_type_id == doc_type_id,
            CompanyDocumentConfig.active,
            Company.active,
        )
        .all()
    )

    return [
        {
            "company_id": company.company_id,
            "company_name": company.company_name,
            "company_code": company.company_code,
            "active": company.active,
            "created_at": company.created_at.isoformat(),
            "updated_at": company.updated_at.isoformat(),
        }
        for company in companies_query
    ]


@app.get("/api/admin/usage/daily", response_model=List[dict])
async def get_daily_usage(db: Session = Depends(get_db)):
    """Get daily token usage for the last 30 days."""
    # SQL query using SQLAlchemy to get daily usage
    thirty_days_ago = datetime.now() - timedelta(days=30)

    query = (
        db.query(
            func.date_trunc("day", ApiUsage.api_call_timestamp).label("date"),
            func.sum(ApiUsage.input_token_count).label("input_tokens"),
            func.sum(ApiUsage.output_token_count).label("output_tokens"),
            func.count(ApiUsage.usage_id).label("request_count"),
        )
        .filter(ApiUsage.api_call_timestamp >= thirty_days_ago)
        .group_by(func.date_trunc("day", ApiUsage.api_call_timestamp))
        .order_by(func.date_trunc("day", ApiUsage.api_call_timestamp))
    )

    results = query.all()

    return [
        {
            "date": result.date.strftime("%Y-%m-%d"),
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "total_tokens": result.input_tokens + result.output_tokens,
            "request_count": result.request_count,
        }
        for result in results
    ]


@app.get("/api/admin/usage/monthly", response_model=List[dict])
async def get_monthly_usage(db: Session = Depends(get_db)):
    """Get monthly token usage for the last 12 months."""
    # SQL query using SQLAlchemy to get monthly usage
    twelve_months_ago = datetime.now() - timedelta(days=365)

    query = (
        db.query(
            func.date_trunc("month", ApiUsage.api_call_timestamp).label("month"),
            func.sum(ApiUsage.input_token_count).label("input_tokens"),
            func.sum(ApiUsage.output_token_count).label("output_tokens"),
            func.count(ApiUsage.usage_id).label("request_count"),
        )
        .filter(ApiUsage.api_call_timestamp >= twelve_months_ago)
        .group_by(func.date_trunc("month", ApiUsage.api_call_timestamp))
        .order_by(func.date_trunc("month", ApiUsage.api_call_timestamp))
    )

    results = query.all()

    return [
        {
            "month": result.month.strftime("%Y-%m"),
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "total_tokens": result.input_tokens + result.output_tokens,
            "request_count": result.request_count,
        }
        for result in results
    ]


@app.post("/process-zip", response_model=dict)
async def process_zip_file(
    background_tasks: BackgroundTasks,
    zip_file: UploadFile = File(...),
    company_id: int = Form(...),
    doc_type_id: int = Form(...),
    # uploader_user_id: int = Form(...),
    db: Session = Depends(get_db),
):
    try:
        # Check if company and document type exist
        company = db.query(Company).filter(Company.company_id == company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        doc_type = (
            db.query(DocumentType)
            .filter(DocumentType.doc_type_id == doc_type_id)
            .first()
        )
        if not doc_type:
            raise HTTPException(status_code=404, detail="Document type not found")

        # Check if user exists
        # user = db.query(User).filter(User.user_id == uploader_user_id).first()
        # if not user:
        #     raise HTTPException(status_code=404, detail="User not found")

        # Check if configuration exists
        config = (
            db.query(CompanyDocumentConfig)
            .filter(
                CompanyDocumentConfig.company_id == company_id,
                CompanyDocumentConfig.doc_type_id == doc_type_id,
                CompanyDocumentConfig.active,
            )
            .first()
        )

        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"No active configuration found for company ID {company_id} and document type ID {doc_type_id}",
            )

        # Verify prompt and schema are accessible (supports both local and S3)
        prompt_schema_manager = get_prompt_schema_manager()
        
        # Check if prompt exists
        prompt_test = await prompt_schema_manager.get_prompt(company.company_code, doc_type.type_code)
        if not prompt_test:
            raise HTTPException(
                status_code=500,
                detail=f"Prompt template not found for {company.company_code}/{doc_type.type_code}",
            )
        
        # Check if schema exists
        schema_test = await prompt_schema_manager.get_schema(company.company_code, doc_type.type_code)
        if not schema_test:
            raise HTTPException(
                status_code=500, 
                detail=f"Schema file not found for {company.company_code}/{doc_type.type_code}"
            )

        # Save the uploaded zip file
        upload_dir = os.path.join(
            "uploads", company.company_code, doc_type.type_code, "batch_jobs"
        )
        os.makedirs(upload_dir, exist_ok=True)

        # Generate a unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        zip_path = os.path.join(upload_dir, f"{timestamp}_{zip_file.filename}")

        # Save file to disk
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(zip_file.file, buffer)

        logger.info(f"Zip file saved to: {zip_file.filename}")

        batch_job = BatchJob(
            # uploader_user_id=3,
            company_id=company_id,
            doc_type_id=doc_type_id,
            upload_description=zip_file.filename,
            s3_upload_path=zip_path,
            original_zipfile=zip_path,
            status="pending",
        )
        logger.info(f"batch_job: {str(batch_job.__dict__)}")

        db.add(batch_job)
        db.commit()
        db.refresh(batch_job)
        logger.info(f"Batch job created: {batch_job.batch_id}")
        batch_id = batch_job.batch_id

        # Start processing in background but return immediately
        background_tasks.add_task(
            process_zip_task,
            batch_id,
            zip_path,
            company.company_code,
            doc_type.type_code,
        )

        # Return immediately with batch ID
        return {
            "batch_id": batch_id,
            "status": "pending",
            "message": "ZIP file processing started",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing ZIP file: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error processing ZIP file: {str(e)}"
        )


# Add the process_zip_task function
async def process_zip_task(
    batch_id: int,
    zip_path: str,
    company_code: str,
    doc_type_code: str,
):
    db = next(get_db())
    import zipfile
    import tempfile

    try:
        # Update batch job status
        batch_job = db.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()
        if not batch_job:
            logger.error(f"Batch job {batch_id} not found")
            return

        batch_job.status = "processing"
        db.commit()

        # Create output directory for extracted files and results
        output_dir = os.path.join(
            "uploads", company_code, doc_type_code, f"batch_{batch_id}"
        )
        os.makedirs(output_dir, exist_ok=True)

        # Extract zip file
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            # First, count the number of valid image files
            image_files = [
                f
                for f in zip_ref.namelist()
                if f.lower().endswith((".jpg", ".jpeg", ".png"))
                and not f.startswith("__MACOSX")
            ]

            batch_job.total_files = len(image_files)
            batch_job.processed_files = 0
            db.commit()

            if batch_job.total_files == 0:
                batch_job.status = "failed"
                batch_job.error_message = "No valid image files found in ZIP"
                db.commit()
                return

            # Extract files to temp directory
            with tempfile.TemporaryDirectory() as temp_dir:
                zip_ref.extractall(temp_dir)

                # Load prompt and schema using the new manager (supports both S3 and local)
                prompt_template, schema_json = await load_prompt_and_schema(company_code, doc_type_code)
                
                if not prompt_template:
                    raise ValueError(f"Prompt not found for {company_code}/{doc_type_code}")
                
                if not schema_json:
                    raise ValueError(f"Schema not found for {company_code}/{doc_type_code}")

                # Get API key from config loader
                try:
                    api_key = get_api_key_manager().get_least_used_key()
                    model_name = app_config.get(
                        "model_name", "gemini-2.5-flash-preview-05-20"
                    )
                except ValueError as e:
                    raise ValueError(f"API key configuration error: {e}")

                # Prepare the results file
                all_results = []

                # Process each image
                for image_path_rel in image_files:
                    image_path = os.path.join(temp_dir, image_path_rel)
                    if not os.path.exists(image_path) or os.path.isdir(image_path):
                        continue

                    # Create a job record for this image
                    job = ProcessingJob(
                        company_id=batch_job.company_id,
                        doc_type_id=batch_job.doc_type_id,
                        batch_id=batch_id,
                        original_filename=os.path.basename(image_path),
                        status="processing",
                        s3_pdf_path=image_path,  # Reusing PDF field for image path
                    )

                    db.add(job)
                    db.commit()
                    db.refresh(job)

                    try:
                        # Process the image
                        result = await extract_text_from_image(
                            image_path,
                            prompt_template,
                            schema_json,
                            api_key,
                            model_name,
                        )

                        # Parse the JSON result with better error handling
                        try:
                            # First check if result is a dictionary with the expected keys
                            if not isinstance(result, dict):
                                raise TypeError(
                                    f"Expected dict result, got {type(result)}"
                                )

                            if "text" not in result:
                                raise KeyError("Result missing 'text' key")

                            # Now handle the text content - always parse it as JSON string first
                            json_text = result["text"]
                            if not isinstance(json_text, str):
                                json_text = str(
                                    json_text
                                )  # Convert to string if it's not already

                            # Parse the JSON string
                            json_data = json.loads(json_text)

                            # Handle case where the parsed JSON is a list
                            if isinstance(json_data, list):
                                # Process all items in the list
                                processed_results = []

                                for item in json_data:
                                    # Add filename to each item
                                    if isinstance(item, dict):
                                        item["__filename"] = os.path.basename(
                                            image_path
                                        )
                                        processed_results.append(item)
                                    else:
                                        # Handle non-dict items
                                        processed_results.append(
                                            {
                                                "__filename": os.path.basename(
                                                    image_path
                                                ),
                                                "value": item,
                                                "__non_dict_item": True,
                                            }
                                        )

                                # Add all processed items to the results
                                all_results.extend(processed_results)
                            else:
                                # Handle single object case (original behavior)
                                json_data["__filename"] = os.path.basename(image_path)
                                all_results.append(json_data)
                        except (
                            json.JSONDecodeError,
                            TypeError,
                            KeyError,
                            IndexError,
                        ) as json_err:
                            logger.error(
                                f"Error parsing JSON result for {image_path}: {str(json_err)}"
                            )
                            logger.error(f"Raw result type: {type(result)}")
                            if isinstance(result, dict) and "text" in result:
                                logger.error(f"Raw text type: {type(result['text'])}")
                                logger.error(
                                    f"Raw text content: {str(result['text'])[:500]}"
                                )

                            # Create a simple JSON with error info instead
                            json_data = {
                                "__filename": os.path.basename(image_path),
                                "__error": f"Failed to parse result: {str(json_err)}",
                                "__raw_text": str(result)[
                                    :500
                                ],  # Include first 500 chars of raw result
                            }
                            all_results.append(json_data)

                        # Record API usage with safer access to token counts
                        api_usage = ApiUsage(
                            job_id=job.job_id,
                            input_token_count=result.get("input_tokens", 0),
                            output_token_count=result.get("output_tokens", 0),
                            api_call_timestamp=datetime.now(),
                            model=model_name,
                            status=(
                                "success" if "__error" not in json_data else "failed"
                            ),
                        )
                        db.add(api_usage)

                        # Update job status
                        if "__error" not in json_data:
                            job.status = "success"
                        else:
                            job.status = "failed"
                            job.error_message = json_data["__error"]
                        db.commit()

                    except Exception as e:
                        job.status = "failed"
                        job.error_message = str(e)
                        db.commit()
                        logger.error(f"Error processing image {image_path}: {str(e)}")
                        # Still add a placeholder in results so we know which file failed
                        all_results.append(
                            {
                                "__filename": os.path.basename(image_path),
                                "__error": f"Processing failed: {str(e)}",
                            }
                        )

                    # Update batch job progress
                    batch_job.processed_files += 1
                    db.commit()

                # Save all results using S3 storage
                s3_manager = get_s3_manager()

                # Generate S3 keys for batch results
                batch_json_key = f"{company_code}/{doc_type_code}/batch_{batch_job.batch_job_id}/batch_results.json"
                batch_excel_key = f"{company_code}/{doc_type_code}/batch_{batch_job.batch_job_id}/batch_results.xlsx"

                json_saved = False
                excel_saved = False

                if s3_manager:
                    # Save JSON results to S3 results folder
                    json_saved = s3_manager.save_json_result(
                        batch_json_key, all_results
                    )

                    if json_saved:
                        json_s3_path = (
                            f"s3://{s3_manager.bucket_name}/results/{batch_json_key}"
                        )

                    # Create temporary Excel file and upload to S3
                    with tempfile.NamedTemporaryFile(
                        suffix=".xlsx", delete=False
                    ) as temp_excel:
                        temp_excel_path = temp_excel.name

                    try:
                        # Convert to Excel
                        await asyncio.to_thread(
                            json_to_excel, all_results, temp_excel_path
                        )

                        # Upload to S3 exports folder
                        with open(temp_excel_path, "rb") as excel_file_obj:
                            excel_saved = s3_manager.save_excel_export(
                                batch_excel_key, excel_file_obj
                            )

                        if excel_saved:
                            excel_s3_path = f"s3://{s3_manager.bucket_name}/exports/{batch_excel_key}"
                    finally:
                        # Clean up temporary file
                        if os.path.exists(temp_excel_path):
                            os.unlink(temp_excel_path)

                # Fallback to local storage if S3 fails
                if not json_saved or not excel_saved:
                    if not json_saved:
                        json_output_path = os.path.join(
                            output_dir, "batch_results.json"
                        )
                        with open(json_output_path, "w", encoding="utf-8") as f:
                            json.dump(all_results, f, indent=2, ensure_ascii=False)
                        json_s3_path = json_output_path

                    if not excel_saved:
                        excel_output_path = os.path.join(
                            output_dir, "batch_results.xlsx"
                        )
                        await asyncio.to_thread(
                            json_to_excel, all_results, excel_output_path
                        )
                        excel_s3_path = excel_output_path

                # Update batch job with output paths and complete status
                batch_job.json_output_path = json_s3_path
                batch_job.excel_output_path = excel_s3_path
                batch_job.status = "success"
                db.commit()

    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}")
        try:
            batch_job.status = "failed"
            batch_job.error_message = str(e)
            db.commit()
        except Exception:
            pass


# Unified batch processing endpoint (replaces both /process and /process-zip)
@app.post("/process-batch", response_model=dict)
async def process_batch(
    background_tasks: BackgroundTasks,
    company_id: int = Form(...),
    doc_type_id: int = Form(...),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Unified batch processing endpoint that handles all file types:
    - Single images -> batch of 1 image
    - Single PDFs -> batch of 1 PDF (split into pages)
    - Multiple files -> batch of all files
    - ZIP files -> batch of extracted contents
    - Mixed uploads -> batch of all processed content
    """
    try:
        # Validate company and document type
        company = db.query(Company).filter(Company.company_id == company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")

        doc_type = db.query(DocumentType).filter(DocumentType.doc_type_id == doc_type_id).first()
        if not doc_type:
            raise HTTPException(status_code=404, detail="Document type not found")

        # Verify configuration exists
        config = (
            db.query(CompanyDocumentConfig)
            .filter(
                CompanyDocumentConfig.company_id == company_id,
                CompanyDocumentConfig.doc_type_id == doc_type_id,
                CompanyDocumentConfig.active,
            )
            .first()
        )

        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"No active configuration found for company ID {company_id} and document type ID {doc_type_id}",
            )

        # Verify prompt and schema are accessible
        prompt_schema_manager = get_prompt_schema_manager()
        
        prompt_test = await prompt_schema_manager.get_prompt(company.company_code, doc_type.type_code)
        if not prompt_test:
            raise HTTPException(
                status_code=500,
                detail=f"Prompt template not found for {company.company_code}/{doc_type.type_code}",
            )
        
        schema_test = await prompt_schema_manager.get_schema(company.company_code, doc_type.type_code)
        if not schema_test:
            raise HTTPException(
                status_code=500, 
                detail=f"Schema file not found for {company.company_code}/{doc_type.type_code}"
            )

        # Analyze uploaded files and determine batch type
        file_names = [f.filename for f in files]
        file_types = []
        total_size = 0
        
        for file in files:
            total_size += len(await file.read())
            await file.seek(0)  # Reset file pointer
            
            # Determine file type
            if file.content_type:
                if file.content_type.startswith('image/'):
                    file_types.append('image')
                elif file.content_type == 'application/pdf':
                    file_types.append('pdf')
                elif file.content_type == 'application/zip':
                    file_types.append('zip')
                else:
                    file_types.append('other')
            else:
                # Fallback to extension checking
                ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
                if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp']:
                    file_types.append('image')
                elif ext == 'pdf':
                    file_types.append('pdf')
                elif ext == 'zip':
                    file_types.append('zip')
                else:
                    file_types.append('other')

        # Determine upload type
        unique_types = set(file_types)
        if len(files) == 1:
            if 'zip' in unique_types:
                upload_type = UploadType.zip_file
            else:
                upload_type = UploadType.single_file
        elif len(unique_types) > 1:
            upload_type = UploadType.mixed
        else:
            upload_type = UploadType.multiple_files

        # Create upload description
        if len(files) == 1:
            upload_description = files[0].filename
        else:
            upload_description = f"{len(files)} files uploaded"

        # Save uploaded files to S3
        s3_manager = get_s3_manager()
        if not s3_manager:
            raise HTTPException(status_code=500, detail="S3 storage not available")
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_file_paths = []
        s3_upload_base = f"batch_uploads/{company.company_code}/{doc_type.type_code}/batch_{timestamp}"

        for i, file in enumerate(files):
            # Generate unique filename
            safe_filename = f"{timestamp}_{i}_{file.filename}"
            s3_key = f"{s3_upload_base}/{safe_filename}"
            
            # Upload file to S3
            file_content = file.file.read()
            upload_success = s3_manager.upload_file(file_content, s3_key)
            
            if not upload_success:
                raise HTTPException(status_code=500, detail=f"Failed to upload {file.filename} to S3")
            
            # Construct S3 path (S3 manager adds 'upload/' prefix automatically)
            s3_path = f"s3://{s3_manager.bucket_name}/{s3_manager.upload_prefix}{s3_key}"
            saved_file_paths.append(s3_path)
            
            # Reset file pointer for potential reuse
            file.file.seek(0)

        # Create BatchJob record
        batch_job = BatchJob(
            company_id=company_id,
            doc_type_id=doc_type_id,
            upload_description=upload_description,
            s3_upload_path=f"s3://{s3_manager.bucket_name}/{s3_upload_base}",  # Store the S3 base path
            upload_type=upload_type,
            original_file_names=file_names,
            file_count=len(files),
            status="pending",
        )

        db.add(batch_job)
        db.commit()
        db.refresh(batch_job)

        logger.info(f"Created unified batch job {batch_job.batch_id} with {len(files)} files")

        # Start background processing
        background_tasks.add_task(
            process_unified_batch, 
            batch_job.batch_id, 
            saved_file_paths,
            company.company_code,
            doc_type.type_code
        )

        return {
            "batch_id": batch_job.batch_id,
            "status": "success",
            "message": f"Batch upload started with {len(files)} files",
            "upload_type": upload_type.value,
            "file_count": len(files)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in unified batch processing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


async def process_unified_batch(batch_id: int, file_paths: List[str], company_code: str, doc_type_code: str):
    """Background task to process unified batch of any file types"""
    
    with Session(engine) as db:
        try:
            # Get batch job
            batch_job = db.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()
            if not batch_job:
                logger.error(f"Batch job {batch_id} not found")
                return

            batch_job.status = "processing"
            db.commit()

            # Load prompt and schema
            prompt_schema_manager = get_prompt_schema_manager()
            prompt = await prompt_schema_manager.get_prompt(company_code, doc_type_code)
            schema = await prompt_schema_manager.get_schema(company_code, doc_type_code)

            if not prompt or not schema:
                batch_job.status = "failed"
                batch_job.error_message = "Prompt or schema not found"
                db.commit()
                return

            # Process all files and collect processable units
            processable_files = []
            s3_manager = get_s3_manager()
            temp_files_to_cleanup = []
            
            for file_path in file_paths:
                # Check if this is an S3 path
                if file_path.startswith('s3://'):
                    # Download S3 file to temporary location
                    file_content = s3_manager.download_file_by_stored_path(file_path)
                    if not file_content:
                        logger.error(f"Failed to download S3 file: {file_path}")
                        continue
                    
                    # Create temporary file
                    import tempfile
                    original_filename = file_path.split('/')[-1]
                    file_ext = os.path.splitext(original_filename)[1].lower()
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
                        temp_file.write(file_content)
                        local_file_path = temp_file.name
                        temp_files_to_cleanup.append(local_file_path)
                else:
                    # Use local file path as-is
                    local_file_path = file_path
                    original_filename = os.path.basename(file_path)
                    file_ext = os.path.splitext(original_filename)[1].lower()
                
                if file_ext == '.zip':
                    # Extract ZIP and add images
                    with zipfile.ZipFile(local_file_path, 'r') as zip_ref:
                        extract_dir = local_file_path + "_extracted"
                        os.makedirs(extract_dir, exist_ok=True)
                        zip_ref.extractall(extract_dir)
                        temp_files_to_cleanup.append(extract_dir)
                        
                        # Find images in extracted files
                        for root, dirs, files in os.walk(extract_dir):
                            for file in files:
                                if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                                    processable_files.append(os.path.join(root, file))
                
                elif file_ext == '.pdf':
                    # For PDF files, add both the local path and original filename
                    processable_files.append((local_file_path, original_filename))
                
                elif file_ext in ['.jpg', '.jpeg', '.png']:
                    # Direct image processing
                    processable_files.append((local_file_path, original_filename))

            # Update total files count based on what we actually found
            batch_job.total_files = len(processable_files)
            batch_job.processed_files = 0
            db.commit()

            if len(processable_files) == 0:
                batch_job.status = "failed"
                batch_job.error_message = "No processable files found"
                db.commit()
                return

            # Process each file
            all_results = []
            
            for i, file_info in enumerate(processable_files):
                try:
                    # Handle both tuple (local_path, original_filename) and string formats
                    if isinstance(file_info, tuple):
                        local_file_path, original_filename = file_info
                    else:
                        local_file_path = file_info
                        original_filename = os.path.basename(file_info)
                    
                    # Create individual ProcessingJob for tracking
                    job = ProcessingJob(
                        company_id=batch_job.company_id,
                        doc_type_id=batch_job.doc_type_id,
                        batch_id=batch_id,
                        original_filename=original_filename,
                        status="processing"
                    )
                    db.add(job)
                    db.commit()

                    # Process the file
                    if local_file_path.lower().endswith('.pdf'):
                        result = await extract_text_from_pdf(local_file_path, prompt, schema)
                    else:
                        result = await extract_text_from_image(local_file_path, prompt, schema)
                    
                    # Add filename to result
                    if isinstance(result, dict):
                        result["__filename"] = original_filename
                        all_results.append(result)
                    
                    # Update job status
                    job.status = "success"
                    db.commit()

                except Exception as e:
                    logger.error(f"Error processing {file_path}: {str(e)}")
                    job.status = "failed"
                    job.error_message = str(e)
                    db.commit()
                    
                    # Add error result
                    all_results.append({
                        "__filename": os.path.basename(file_path),
                        "__error": f"Processing failed: {str(e)}"
                    })

                # Update batch progress
                batch_job.processed_files += 1
                db.commit()

            # Save batch results to S3
            if all_results:
                s3_manager = get_s3_manager()
                s3_results_base = f"batch_results/{company_code}/{doc_type_code}/batch_{batch_id}"

                # Save JSON to S3
                json_content = json.dumps(all_results, indent=2, ensure_ascii=False)
                json_s3_key = f"{s3_results_base}/batch_results.json"
                json_upload_success = s3_manager.upload_file(json_content.encode('utf-8'), json_s3_key)
                
                if json_upload_success:
                    batch_job.json_output_path = f"s3://{s3_manager.bucket_name}/{s3_manager.upload_prefix}{json_s3_key}"
                else:
                    logger.error(f"Failed to upload JSON results to S3 for batch {batch_id}")

                # Save Excel to S3
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_excel:
                    temp_excel_path = temp_excel.name
                
                # Generate Excel file locally first
                json_to_excel(all_results, temp_excel_path)
                
                # Upload Excel to S3
                with open(temp_excel_path, 'rb') as excel_file:
                    excel_content = excel_file.read()
                    excel_s3_key = f"{s3_results_base}/batch_results.xlsx"
                    excel_upload_success = s3_manager.upload_file(excel_content, excel_s3_key)
                    
                    if excel_upload_success:
                        batch_job.excel_output_path = f"s3://{s3_manager.bucket_name}/{s3_manager.upload_prefix}{excel_s3_key}"
                    else:
                        logger.error(f"Failed to upload Excel results to S3 for batch {batch_id}")
                
                # Clean up temporary file
                os.unlink(temp_excel_path)

            batch_job.status = "completed"
            db.commit()

            logger.info(f"Unified batch {batch_id} completed successfully")

        except Exception as e:
            logger.error(f"Error in unified batch processing: {str(e)}")
            try:
                batch_job.status = "failed"
                batch_job.error_message = str(e)
                db.commit()
            except Exception:
                pass
        
        finally:
            # Clean up temporary files
            import shutil
            for temp_path in temp_files_to_cleanup:
                try:
                    if os.path.isfile(temp_path):
                        os.unlink(temp_path)
                    elif os.path.isdir(temp_path):
                        shutil.rmtree(temp_path)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to cleanup temporary file {temp_path}: {cleanup_error}")


# Add new endpoints to get batch job status and list batch jobs
@app.get("/batch-jobs/{batch_id}", response_model=dict)
def get_batch_job_status(batch_id: int, db: Session = Depends(get_db)):
    batch_job = db.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()
    if not batch_job:
        raise HTTPException(status_code=404, detail="Batch job not found")

    return {
        "batch_id": batch_job.batch_id,
        "company_id": batch_job.company_id,
        "company_name": batch_job.company.company_name if batch_job.company else None,
        "doc_type_id": batch_job.doc_type_id,
        "type_name": (
            batch_job.document_type.type_name if batch_job.document_type else None
        ),
        "uploader_user_id": (
            batch_job.uploader_user_id
            if hasattr(batch_job, "uploader_user_id")
            else None
        ),
        "uploader_name": (
            batch_job.uploader.name
            if hasattr(batch_job, "uploader") and batch_job.uploader
            else None
        ),
        "zip_filename": batch_job.upload_description,
        "s3_zipfile_path": batch_job.s3_upload_path,
        "total_files": batch_job.total_files,
        "processed_files": batch_job.processed_files,
        "status": batch_job.status,
        "error_message": batch_job.error_message,
        "json_output_path": batch_job.json_output_path,
        "excel_output_path": batch_job.excel_output_path,
        "created_at": batch_job.created_at.isoformat(),
        "updated_at": batch_job.updated_at.isoformat(),
    }


@app.get("/batch-jobs", response_model=List[dict])
def list_batch_jobs(
    company_id: Optional[int] = None,
    doc_type_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(BatchJob)

    if company_id is not None:
        query = query.filter(BatchJob.company_id == company_id)

    if doc_type_id is not None:
        query = query.filter(BatchJob.doc_type_id == doc_type_id)

    if status is not None:
        query = query.filter(BatchJob.status == status)

    # Order by most recent first
    query = query.order_by(BatchJob.created_at.desc())

    # Apply pagination
    batch_jobs = query.offset(offset).limit(limit).all()

    return [
        {
            "batch_id": job.batch_id,
            "company_id": job.company_id,
            "company_name": job.company.company_name if job.company else None,
            "doc_type_id": job.doc_type_id,
            "type_name": job.document_type.type_name if job.document_type else None,
            "uploader_user_id": (
                job.uploader_user_id if hasattr(job, "uploader_user_id") else None
            ),
            "uploader_name": (
                job.uploader.name if hasattr(job, "uploader") and job.uploader else None
            ),
            "zip_filename": job.upload_description,
            "s3_zipfile_path": job.s3_upload_path,
            "total_files": job.total_files,
            "processed_files": job.processed_files,
            "status": job.status,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }
        for job in batch_jobs
    ]


@app.delete("/batch-jobs/{batch_id}", response_model=dict)
def delete_batch_job(batch_id: int, db: Session = Depends(get_db)):
    """
    Delete a batch job and all its related files and data.
    
    This endpoint will:
    - Delete all related ProcessingJobs and their files
    - Delete all associated file records and S3 files
    - Delete the batch job record itself
    - Clean up any API usage records
    
    Returns a summary of what was deleted.
    """
    try:
        # Check if batch job exists
        batch_job = db.query(BatchJob).filter(BatchJob.batch_id == batch_id).first()
        if not batch_job:
            raise HTTPException(status_code=404, detail="Batch job not found")
        
        # Use ForceDeleteManager to handle the deletion
        delete_manager = ForceDeleteManager(db)
        result = delete_manager.force_delete_batch_job(batch_id)
        
        logger.info(f"Successfully deleted batch job {batch_id}: {result['message']}")
        
        return {
            "success": True,
            "message": result["message"],
            "batch_id": batch_id,
            "deleted_entity": result["deleted_entity"],
            "statistics": result["statistics"]
        }
        
    except ValueError as e:
        # Batch job not found
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete batch job {batch_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete batch job: {str(e)}")


@app.get("/download-by-path")
def download_file_by_path(path: str):
    """Download a file by its full path."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found on disk: {path}")

    # Get the filename from the path
    filename = os.path.basename(path)

    # Determine content type based on file extension
    file_extension = os.path.splitext(filename)[1].lower()
    content_type = "application/octet-stream"  # Default content type

    if file_extension == ".json":
        content_type = "application/json"
    elif file_extension == ".xlsx":
        content_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    elif file_extension == ".pdf":
        content_type = "application/pdf"
    elif file_extension in [".jpg", ".jpeg"]:
        content_type = "image/jpeg"
    elif file_extension == ".png":
        content_type = "image/png"

    return FileResponse(
        path=path,
        filename=filename,
        media_type=content_type,
    )


@app.get("/download-s3")
def download_s3_file(s3_path: str):
    """Download a file from S3 by its S3 path or URI."""
    try:
        s3_manager = get_s3_manager()
        if not s3_manager:
            raise HTTPException(status_code=500, detail="S3 storage not available")
        
        # Download file content from S3
        file_content = s3_manager.download_file_by_stored_path(s3_path)
        if not file_content:
            raise HTTPException(status_code=404, detail=f"File not found in S3: {s3_path}")
        
        # Extract filename from S3 path
        if s3_path.startswith('s3://'):
            # Handle s3://bucket/path format
            path_parts = s3_path.replace('s3://', '').split('/')
            filename = path_parts[-1] if path_parts else "download"
        else:
            # Handle direct S3 key format
            filename = s3_path.split('/')[-1] if '/' in s3_path else s3_path
        
        # Determine content type based on file extension
        file_extension = os.path.splitext(filename)[1].lower()
        content_type = "application/octet-stream"  # Default
        
        if file_extension == ".json":
            content_type = "application/json"
        elif file_extension == ".xlsx":
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif file_extension == ".pdf":
            content_type = "application/pdf"
        elif file_extension in [".jpg", ".jpeg"]:
            content_type = "image/jpeg"
        elif file_extension == ".png":
            content_type = "image/png"
        
        # Create temporary file to serve
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name
        
        # Return file response and schedule cleanup
        response = FileResponse(
            path=temp_file_path,
            filename=filename,
            media_type=content_type,
        )
        
        # Add header to indicate this is from S3
        response.headers["X-File-Source"] = "S3"
        
        return response
        
    except Exception as e:
        logger.error(f"Error downloading S3 file {s3_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")


@app.get("/files")
def get_file_by_path(path: str, db: Session = Depends(get_db)):
    """Get file information by path."""
    file = db.query(DBFile).filter(DBFile.file_path == path).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    return {
        "file_id": file.file_id,
        "file_name": file.file_name,
        "file_path": file.file_path,
        "file_type": file.file_type,
    }


# Force Delete API Endpoints
@app.delete("/document-types/{doc_type_id}/force-delete")
def force_delete_document_type(
    doc_type_id: int,
    db: Session = Depends(get_db)
):
    """強制刪除文檔類型及其所有依賴"""
    try:
        force_delete_manager = ForceDeleteManager(db)
        result = force_delete_manager.force_delete_document_type(doc_type_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Force delete document type failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Force delete failed: {str(e)}"
        )


@app.delete("/companies/{company_id}/force-delete")
def force_delete_company(
    company_id: int,
    db: Session = Depends(get_db)
):
    """強制刪除公司及其所有依賴"""
    try:
        force_delete_manager = ForceDeleteManager(db)
        result = force_delete_manager.force_delete_company(company_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Force delete company failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Force delete failed: {str(e)}"
        )


@app.delete("/configs/{config_id}/force-delete")
def force_delete_config(
    config_id: int,
    db: Session = Depends(get_db)
):
    """強制刪除配置及其相關文件"""
    try:
        force_delete_manager = ForceDeleteManager(db)
        result = force_delete_manager.force_delete_config(config_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Force delete config failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Force delete failed: {str(e)}"
        )


# 為 Configurations 添加依賴檢查端點
@app.get("/configs/{config_id}/dependencies")
def get_config_dependencies(config_id: int, db: Session = Depends(get_db)):
    """獲取配置的依賴信息"""
    try:
        from utils.dependency_checker import DependencyChecker
        
        # 獲取配置信息
        config = db.query(CompanyDocumentConfig).filter(
            CompanyDocumentConfig.config_id == config_id
        ).first()
        
        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        # 檢查是否有相關的處理任務（通過 company_id 和 doc_type_id）
        processing_jobs_count = db.query(ProcessingJob).filter(
            ProcessingJob.company_id == config.company_id,
            ProcessingJob.doc_type_id == config.doc_type_id
        ).count()
        
        batch_jobs_count = db.query(BatchJob).filter(
            BatchJob.company_id == config.company_id,
            BatchJob.doc_type_id == config.doc_type_id
        ).count()
        
        s3_files_count = 0
        if config.prompt_path and config.prompt_path.startswith('s3://'):
            s3_files_count += 1
        if config.schema_path and config.schema_path.startswith('s3://'):
            s3_files_count += 1
        
        total_dependencies = processing_jobs_count + batch_jobs_count + s3_files_count
        can_delete = total_dependencies == 0
        
        config_name = f"{config.company.company_name} - {config.document_type.type_name}"
        
        dependencies = {
            "exists": True,
            "config_name": config_name,
            "can_delete": can_delete,
            "total_dependencies": total_dependencies,
            "dependencies": {
                "processing_jobs": processing_jobs_count,
                "batch_jobs": batch_jobs_count,
                "s3_files": s3_files_count
            },
            "blocking_message": None if can_delete else f"Cannot delete configuration '{config_name}': {processing_jobs_count} processing job(s), {batch_jobs_count} batch job(s), {s3_files_count} S3 file(s) exist."
        }
        
        return dependencies
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking config dependencies: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check dependencies: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    # Use the secure configuration loader
    try:
        app_config = config_loader.get_app_config()
        port = app_config["port"]
        logger.info(f"🚀 Starting application on port {port}")
    except Exception as e:
        logger.error(f"Failed to load application config: {e}")
        port = 8000  # Fallback port

    # Use multiple workers to handle concurrent requests
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        workers=4,  # Use multiple workers to handle concurrent requests
    )
