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
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
from datetime import datetime, timedelta
import uuid
import json
import logging
import asyncio
import fitz  # PyMuPDF for PDF handling
import google.generativeai as genai  # Correct import for Google's Generative AI
from sqlalchemy import func

from db.database import get_db, engine
from db.models import (
    Base,
    Company,
    DocumentType,
    CompanyDocumentConfig,
    ProcessingJob,
    File as DBFile,
    DocumentFile,
    ApiUsage,
    SystemSettings,
)
import main as ocr_processor
from main import extract_text_from_image, extract_text_from_pdf
from utils.excel_converter import json_to_excel

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Document Processing API")

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
logger = logging.getLogger(__name__)

# WebSocket connections store
active_connections = {}

# Load config at module level
CONFIG_PATH = os.path.join("env", "config.json")
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)


# Health check endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


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
    company = db.query(Company).filter(Company.company_id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    db.delete(company)
    db.commit()

    return {"message": "Company deleted successfully"}


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
    doc_type = (
        db.query(DocumentType).filter(DocumentType.doc_type_id == doc_type_id).first()
    )
    if not doc_type:
        raise HTTPException(status_code=404, detail="Document type not found")

    db.delete(doc_type)
    db.commit()

    return {"message": "Document type deleted successfully"}


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
        prompt_path=config_data["prompt_path"],
        schema_path=config_data["schema_path"],
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

    config.prompt_path = config_data["prompt_path"]
    config.schema_path = config_data["schema_path"]
    config.active = config_data.get("active", config.active)

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


# File upload endpoint
@app.post("/upload", response_model=dict)
async def upload_file(file: UploadFile = File(...), path: str = Form(...)):
    try:
        # Create directories if they don't exist
        directory = os.path.join("uploads", os.path.dirname(path))
        os.makedirs(directory, exist_ok=True)

        # Generate full file path
        file_path = os.path.join("uploads", path)

        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return {"file_path": file_path}

    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


# WebSocket connection
@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    await websocket.accept()
    active_connections[job_id] = websocket

    try:
        while True:
            # Keep the connection alive
            await websocket.receive_text()
    except Exception as e:
        logger.info(f"WebSocket closed for job_id {job_id}: {str(e)}")
    finally:
        if job_id in active_connections:
            del active_connections[job_id]


# Process document endpoint
@app.post("/process", response_model=dict)
async def process_document(
    background_tasks: BackgroundTasks,
    document: UploadFile = File(...),
    company_id: int = Form(...),
    doc_type_id: int = Form(...),
    db: Session = Depends(get_db)
):
    try:
        # Check if company and document type exist
        company = db.query(Company).filter(Company.company_id == company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        doc_type = db.query(DocumentType).filter(DocumentType.doc_type_id == doc_type_id).first()
        if not doc_type:
            raise HTTPException(status_code=404, detail="Document type not found")
            
        # Check if configuration exists
        config = db.query(CompanyDocumentConfig).filter(
            CompanyDocumentConfig.company_id == company_id,
            CompanyDocumentConfig.doc_type_id == doc_type_id,
            CompanyDocumentConfig.active == True
        ).first()
        
        if not config:
            raise HTTPException(
                status_code=404, 
                detail=f"No active configuration found for company ID {company_id} and document type ID {doc_type_id}"
            )
            
        # Verify prompt_path and schema_path exist
        if not config.prompt_path or not os.path.exists(config.prompt_path):
            raise HTTPException(
                status_code=500,
                detail=f"Prompt template not found: {config.prompt_path}"
            )
            
        if not config.schema_path or not os.path.exists(config.schema_path):
            raise HTTPException(
                status_code=500,
                detail=f"Schema file not found: {config.schema_path}"
            )
        
        # Save the uploaded file
        upload_dir = os.path.join("uploads", company.company_code, doc_type.type_code, "jobs")
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate a unique filename
        file_path = os.path.join(upload_dir, document.filename)
        
        # Save file to disk
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(document.file, buffer)
        
        # Create a new processing job
        job = ProcessingJob(
            company_id=company_id,
            doc_type_id=doc_type_id,
            original_filename=document.filename,
            status="pending",
            s3_pdf_path=file_path
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
            config.prompt_path,
            config.schema_path,
            company.company_code,
            doc_type.type_code
        )
        
        # Return immediately with job ID
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Document processing started"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


# Add a helper function to get settings
def get_system_setting(db: Session, key: str, default: str = None):
    """Get a system setting value by key."""
    setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
    if setting:
        return setting.value
    return default

# Update the process_document_task function to use system settings
async def process_document_task(
    job_id: int,
    file_path: str,
    prompt_path: str,
    schema_path: str,
    company_code: str,
    doc_type_code: str,
):
    db = next(get_db())

    try:
        # Get system settings
        api_key = get_system_setting(db, 'gemini_api_key')
        model_name = get_system_setting(db, 'default_model', 'gemini-1.5-pro')
        temperature = float(get_system_setting(db, 'temperature', '0.3'))
        top_p = float(get_system_setting(db, 'top_p', '0.95'))
        top_k = int(get_system_setting(db, 'top_k', '40'))
        
        if not api_key:
            raise ValueError("Gemini API key not configured in system settings")
        
        # Update job status
        job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        # Update the s3_pdf_path to fix the NOT NULL constraint
        job.s3_pdf_path = file_path
        job.status = "processing"
        db.commit()

        # Send WebSocket notification
        await send_websocket_message(
            job_id, {"status": "processing", "message": "Document processing started"}
        )

        # Load prompt and schema
        with open(prompt_path, "r") as f:
            prompt_template = f.read()
        
        with open(schema_path, "r") as f:
            schema_json = json.load(f)

        await send_websocket_message(
            job_id, {"status": "processing", "message": "Extracting text from document..."}
        )

        # Process the document based on file type
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # Handle based on file type
        if file_extension in ['.jpg', '.jpeg', '.png']:
            # Process image directly
            result = await extract_text_from_image(
                file_path, 
                prompt_template, 
                schema_json, 
                api_key, 
                model_name,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k
            )
            json_result = result["text"]
            input_tokens = result["input_tokens"]
            output_tokens = result["output_tokens"]
        elif file_extension == '.pdf':
            # Process PDF directly
            result = await extract_text_from_pdf(
                file_path, 
                prompt_template, 
                schema_json, 
                api_key, 
                model_name,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k
            )
            json_result = result["text"]
            input_tokens = result["input_tokens"]
            output_tokens = result["output_tokens"]
        else:
            # Unsupported file type
            raise ValueError(f"Unsupported file type: {file_extension}")

        # Generate output files
        output_dir = os.path.join("uploads", company_code, doc_type_code, str(job_id))
        os.makedirs(output_dir, exist_ok=True)

        json_output_path = os.path.join(output_dir, "results.json")

        # Save JSON output
        with open(json_output_path, "w") as f:
            # If the result is a string, assume it's already JSON formatted
            if isinstance(json_result, str):
                f.write(json_result)
                # Parse the JSON string to get the object
                result_obj = json.loads(json_result)
            else:
                # Otherwise, dump the object as JSON
                json.dump(json_result, f, indent=2)
                result_obj = json_result

        # Get JSON file size
        json_file_size = os.path.getsize(json_output_path)

        # Create file entries for JSON output
        json_file = DBFile(
            file_path=json_output_path,
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
        
        # Generate Excel file dynamically
        excel_output_path = os.path.join(output_dir, "results.xlsx")
        json_to_excel(result_obj, excel_output_path, doc_type_code)
        
        # Get Excel file size
        excel_file_size = os.path.getsize(excel_output_path)

        excel_file = DBFile(
            file_path=excel_output_path,
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

        
        # Record API usage in database
        api_usage = ApiUsage(
            job_id=job_id,
            input_token_count=input_tokens,
            output_token_count=output_tokens,
            api_call_timestamp=datetime.now(),
            model=model_name
        )
        db.add(api_usage)
        db.commit()

        # Update job status to success
        job.status = "success"
        db.commit()

        # Send WebSocket notification
        await send_websocket_message(
            job_id,
            {
                "status": "success",
                "message": "Document processing completed",
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

        # Update job status to error
        if job:
            job.status = "error"
            job.error_message = str(e)
            db.commit()

        # Send WebSocket notification
        await send_websocket_message(
            job_id, {"status": "error", "message": f"Processing failed: {str(e)}"}
        )
    finally:
        db.close()


# WebSocket message sender
async def send_websocket_message(job_id: int, message: dict):
    if str(job_id) in active_connections:
        await active_connections[str(job_id)].send_json(message)


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
def list_jobs(
    company_id: Optional[int] = None,
    doc_type_id: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(ProcessingJob)

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

    return [
        {
            "job_id": job.job_id,
            "company_id": job.company_id,
            "company_name": job.company.company_name if job.company else None,
            "doc_type_id": job.doc_type_id,
            "type_name": job.document_type.type_name if job.document_type else None,
            "status": job.status,
            "original_filename": job.original_filename,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }
        for job in jobs
    ]


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

    if not os.path.exists(file.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=file.file_path,
        filename=file.file_name,
        media_type=file.file_type or "application/octet-stream",
    )


# Initialize database function
@app.on_event("startup")
async def startup_db_client():
    try:
        # Create necessary directories
        os.makedirs("uploads", exist_ok=True)

        # Try connecting to database
        db = next(get_db())
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
            CompanyDocumentConfig.active == True,
            Company.active == True,
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


@app.get("/admin/models")
async def get_models(db: Session = Depends(get_db)):
    """Get a list of all unique models used in API calls."""
    try:
        # Query for distinct models
        result = db.query(ApiUsage.model).distinct().all()
        models = [row[0] for row in result if row[0]]  # Filter out None values
        return models
    except Exception as e:
        logger.error(f"Error fetching models: {str(e)}")
        return []

@app.get("/admin/usage/daily")
async def get_daily_usage(
    start_date: str = None,
    end_date: str = None,
    model: str = None,
    doc_type_id: int = None,
    company_id: int = None,
    db: Session = Depends(get_db)
):
    """Get daily token usage with optional filters."""
    try:
        # Parse date strings to datetime objects
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d") if start_date else datetime.now() - timedelta(days=30)
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
        
        # Base query
        query = db.query(
            func.date_trunc('day', ApiUsage.api_call_timestamp).label('date'),
            func.sum(ApiUsage.input_token_count).label('input_tokens'),
            func.sum(ApiUsage.output_token_count).label('output_tokens'),
            func.count(ApiUsage.usage_id).label('request_count')
        )
        
        # Apply filters
        query = query.filter(ApiUsage.api_call_timestamp >= start_date_obj)
        
        # Add one day to include the end date fully
        query = query.filter(ApiUsage.api_call_timestamp < end_date_obj + timedelta(days=1))
            
        if model and model != 'all':
            query = query.filter(ApiUsage.model == model)
            
        if doc_type_id:
            query = query.filter(ApiUsage.doc_type_id == doc_type_id)
            
        if company_id:
            query = query.filter(ApiUsage.company_id == company_id)
        
        # Group and order
        query = query.group_by(
            func.date_trunc('day', ApiUsage.api_call_timestamp)
        ).order_by(
            func.date_trunc('day', ApiUsage.api_call_timestamp)
        )
        
        results = query.all()
        
        # Convert query results to a dictionary with date as key
        results_dict = {
            result.date.strftime("%Y-%m-%d"): {
                "date": result.date.strftime("%Y-%m-%d"),
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "total_tokens": result.input_tokens + result.output_tokens,
                "request_count": result.request_count
            }
            for result in results
        }
        
        # Create a list of all dates in the range
        all_dates = []
        current_date = start_date_obj
        while current_date <= end_date_obj:
            date_str = current_date.strftime("%Y-%m-%d")
            all_dates.append(date_str)
            current_date += timedelta(days=1)
        
        # Fill in missing dates with zero values
        complete_results = []
        for date_str in all_dates:
            if date_str in results_dict:
                complete_results.append(results_dict[date_str])
            else:
                complete_results.append({
                    "date": date_str,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "request_count": 0
                })
        
        return complete_results
    except Exception as e:
        logger.error(f"Error fetching daily usage: {str(e)}")
        return []

@app.get("/admin/usage/monthly")
async def get_monthly_usage(
    start_date: str = None,
    end_date: str = None,
    model: str = None,
    doc_type_id: int = None,
    company_id: int = None,
    db: Session = Depends(get_db)
):
    """Get monthly token usage with optional filters."""
    try:
        # Parse date strings to datetime objects
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d") if start_date else datetime.now() - timedelta(days=365)
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
        
        # Base query
        query = db.query(
            func.date_trunc('month', ApiUsage.api_call_timestamp).label('month'),
            func.sum(ApiUsage.input_token_count).label('input_tokens'),
            func.sum(ApiUsage.output_token_count).label('output_tokens'),
            func.count(ApiUsage.usage_id).label('request_count')
        )
        
        # Apply filters
        if start_date:
            query = query.filter(ApiUsage.api_call_timestamp >= start_date)
        else:
            # Default to last 12 months
            twelve_months_ago = datetime.now() - timedelta(days=365)
            query = query.filter(ApiUsage.api_call_timestamp >= twelve_months_ago)
            
        if end_date:
            # Add one day to include the end date fully
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(ApiUsage.api_call_timestamp < end_date_obj)
            
        if model and model != 'all':
            query = query.filter(ApiUsage.model == model)
        
        if doc_type_id:
            query = query.filter(ApiUsage.doc_type_id == doc_type_id)
            
        if company_id:
            query = query.filter(ApiUsage.company_id == company_id)
        
        # Group and order
        query = query.group_by(
            func.date_trunc('month', ApiUsage.api_call_timestamp)
        ).order_by(
            func.date_trunc('month', ApiUsage.api_call_timestamp)
        )
        
        results = query.all()
        
        # Convert query results to a dictionary with month as key
        results_dict = {
            result.month.strftime("%Y-%m"): {
                "month": result.month.strftime("%Y-%m"),
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "total_tokens": result.input_tokens + result.output_tokens,
                "request_count": result.request_count
            }
            for result in results
        }
        
        # Create a list of all months in the range
        all_months = []
        current_date = start_date_obj.replace(day=1)  # Start at first day of month
        end_month = end_date_obj.replace(day=1)
        
        while current_date <= end_month:
            month_str = current_date.strftime("%Y-%m")
            all_months.append(month_str)
            # Move to next month
            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1)
        
        # Fill in missing months with zero values
        complete_results = []
        for month_str in all_months:
            if month_str in results_dict:
                complete_results.append(results_dict[month_str])
            else:
                complete_results.append({
                    "month": month_str,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "request_count": 0
                })
        
        return complete_results
    except Exception as e:
        logger.error(f"Error fetching monthly usage: {str(e)}")
        return []

@app.get("/admin/settings")
async def get_settings(db: Session = Depends(get_db)):
    """Get all system settings."""
    try:
        settings = db.query(SystemSettings).all()
        return [
            {
                "key": setting.key,
                "value": mask_sensitive_value(setting.key, setting.value),
                "description": setting.description,
                "updated_at": setting.updated_at.isoformat() if setting.updated_at else None
            }
            for setting in settings
        ]
    except Exception as e:
        logger.error(f"Error fetching settings: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def mask_sensitive_value(key, value):
    """Mask sensitive values like API keys."""
    sensitive_keys = ['api_key', 'password', 'secret']
    if any(sensitive_word in key.lower() for sensitive_word in sensitive_keys) and value:
        # Show just the first and last 4 characters
        if len(value) > 8:
            return value[:4] + '*' * (len(value) - 8) + value[-4:]
        else:
            return '*' * len(value)
    return value

@app.put("/admin/settings/{key}")
async def update_setting(key: str, update: dict, db: Session = Depends(get_db)):
    """Update a system setting."""
    try:
        if 'value' not in update:
            raise HTTPException(status_code=400, detail="Value is required")
            
        setting = db.query(SystemSettings).filter(SystemSettings.key == key).first()
        if not setting:
            # If setting doesn't exist, create it
            setting = SystemSettings(key=key, value=update['value'])
            db.add(setting)
        else:
            # Update existing setting
            setting.value = update['value']
            
        db.commit()
        
        return {"message": f"Setting {key} updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating setting: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/settings/models")
async def get_available_models():
    """Get list of available Gemini models."""
    return [
        {"id": "gemini-1.0-pro", "name": "Gemini 1.0 Pro"},
        {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro"},
        {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"},
        {"id": "gemini-1.5-pro-preview", "name": "Gemini 1.5 Pro Preview"}
    ]

if __name__ == "__main__":
    import uvicorn

    with open("env/config.json") as f:
        config = json.load(f)
    uvicorn.run(app, host="0.0.0.0", port=config["port"])
