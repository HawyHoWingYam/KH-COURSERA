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
import time

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
    BatchJob,
    User,
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
                CompanyDocumentConfig.active == True,
            )
            .first()
        )

        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"No active configuration found for company ID {company_id} and document type ID {doc_type_id}",
            )

        # Verify prompt_path and schema_path exist
        if not config.prompt_path or not os.path.exists(config.prompt_path):
            raise HTTPException(
                status_code=500,
                detail=f"Prompt template not found: {config.prompt_path}",
            )

        if not config.schema_path or not os.path.exists(config.schema_path):
            raise HTTPException(
                status_code=500, detail=f"Schema file not found: {config.schema_path}"
            )

        # Save the uploaded file
        upload_dir = os.path.join(
            "uploads", company.company_code, doc_type.type_code, "jobs"
        )
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
            s3_pdf_path=file_path,
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
            doc_type.type_code,
        )

        # Return immediately with job ID
        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Document processing started",
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
    prompt_path: str,
    schema_path: str,
    company_code: str,
    doc_type_code: str,
):
    db = next(get_db())

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

        # Load prompt and schema
        with open(prompt_path, "r") as f:
            prompt_template = f.read()

        with open(schema_path, "r") as f:
            schema_json = json.load(f)

        # Get API key from config
        api_key = config.get("api_key")
        model_name = config.get("model_name")
        if not api_key:
            raise ValueError("API key not found in config.json")

        await send_websocket_message(
            job_id,
            {"status": "processing", "message": "Extracting text from document..."},
        )

        # Process the document based on file type
        file_extension = os.path.splitext(file_path)[1].lower()

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
                file_path, prompt_template, schema_json, api_key, model_name
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
                file_path, prompt_template, schema_json, api_key, model_name
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
                json.dump(json_result, f, indent=2, ensure_ascii=False)
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
                CompanyDocumentConfig.active == True,
            )
            .first()
        )

        if not config:
            raise HTTPException(
                status_code=404,
                detail=f"No active configuration found for company ID {company_id} and document type ID {doc_type_id}",
            )

        # Verify prompt_path and schema_path exist
        if not config.prompt_path or not os.path.exists(config.prompt_path):
            raise HTTPException(
                status_code=500,
                detail=f"Prompt template not found: {config.prompt_path}",
            )

        if not config.schema_path or not os.path.exists(config.schema_path):
            raise HTTPException(
                status_code=500, detail=f"Schema file not found: {config.schema_path}"
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

        # Create a new batch job
        batch_job = BatchJob(
            company_id=company_id,
            doc_type_id=doc_type_id,
            # uploader_user_id=uploader_user_id,
            zip_filename=zip_file.filename,
            s3_zipfile_path=zip_path,
            original_zipfile=zip_path,
            status="pending",
        )

        db.add(batch_job)
        db.commit()
        db.refresh(batch_job)

        batch_id = batch_job.batch_id

        # Start processing in background but return immediately
        background_tasks.add_task(
            process_zip_task,
            batch_id,
            zip_path,
            config.prompt_path,
            config.schema_path,
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
    prompt_path: str,
    schema_path: str,
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

                # Load prompt and schema
                with open(prompt_path, "r") as f:
                    prompt_template = f.read()

                with open(schema_path, "r") as f:
                    schema_json = json.load(f)

                # Get API key from config
                api_key = config.get("api_key")
                model_name = config.get("model_name", "gemini-1.5-pro-vision")

                if not api_key:
                    raise ValueError("API key not found in config.json")

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
                                raise KeyError(f"Result missing 'text' key")

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
                                        item["__filename"] = os.path.basename(image_path)
                                        processed_results.append(item)
                                    else:
                                        # Handle non-dict items
                                        processed_results.append({
                                            "__filename": os.path.basename(image_path),
                                            "value": item,
                                            "__non_dict_item": True
                                        })
                                
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

                # Save all results to a single JSON file
                json_output_path = os.path.join(output_dir, "batch_results.json")
                with open(json_output_path, "w") as f:
                    json.dump(all_results, f, indent=2, ensure_ascii=False)

                # Convert to Excel
                excel_output_path = os.path.join(output_dir, "batch_results.xlsx")
                await asyncio.to_thread(json_to_excel, all_results, excel_output_path)

                # Update batch job with output paths and complete status
                batch_job.json_output_path = json_output_path
                batch_job.excel_output_path = excel_output_path
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
        "zip_filename": batch_job.zip_filename,
        "s3_zipfile_path": batch_job.s3_zipfile_path,
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
            "zip_filename": job.zip_filename,
            "s3_zipfile_path": job.s3_zipfile_path,
            "total_files": job.total_files,
            "processed_files": job.processed_files,
            "status": job.status,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }
        for job in batch_jobs
    ]


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
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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


if __name__ == "__main__":
    import uvicorn

    with open("env/config.json") as f:
        config = json.load(f)
    uvicorn.run(app, host="0.0.0.0", port=config["port"])
