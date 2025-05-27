from fastapi import (
    FastAPI,
    File,
    UploadFile,
    Form,
    HTTPException,
    Depends,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from typing import List, Optional, Dict, Any
import os
import json
import shutil
from datetime import datetime
import uuid
import asyncio
from starlette.background import BackgroundTasks
import uvicorn
from pathlib import Path
from sqlalchemy.orm import Session

from pydantic import BaseModel, Field
from db.database import get_db, engine, Base
from db.models import (
    Department, User, DocumentType, Company,
    CompanyDocumentConfig, ProcessingJob, File as DBFile, 
    DocumentFile, ApiUsage, FileCategory
)

# Import functions from main.py
from main import extract_text_from_image

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

# Create FastAPI application
app = FastAPI(
    title="Document OCR API",
    description="API for document OCR processing using Google Gemini",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create required directories for file uploads
os.makedirs("uploads", exist_ok=True)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, job_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[job_id] = websocket

    def disconnect(self, job_id: str):
        if job_id in self.active_connections:
            del self.active_connections[job_id]

    async def send_message(self, job_id: str, message: str):
        if job_id in self.active_connections:
            await self.active_connections[job_id].send_text(message)

manager = ConnectionManager()

# Pydantic models
class DocumentTypeBase(BaseModel):
    type_name: str
    type_code: str
    description: Optional[str] = None

class DocumentTypeCreate(DocumentTypeBase):
    pass

class DocumentTypeResponse(DocumentTypeBase):
    doc_type_id: int

    class Config:
        orm_mode = True

class CompanyBase(BaseModel):
    company_name: str
    company_code: str
    active: bool = True

class CompanyCreate(CompanyBase):
    pass

class CompanyResponse(CompanyBase):
    company_id: int

    class Config:
        orm_mode = True

class ConfigBase(BaseModel):
    prompt_path: str
    schema_path: str
    active: bool = True

class ConfigCreate(ConfigBase):
    company_id: int
    doc_type_id: int

class ConfigResponse(ConfigBase):
    config_id: int
    company_id: int
    doc_type_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class JobBase(BaseModel):
    original_filename: str
    status: str
    doc_type_id: int
    company_id: int

class JobCreate(JobBase):
    uploader_user_id: int
    config_id: Optional[int] = None

class JobResponse(BaseModel):
    job_id: int
    original_filename: str
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    company_id: int
    doc_type_id: int
    
    class Config:
        orm_mode = True

# Routes
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}

@app.get("/document-types", response_model=List[DocumentTypeResponse])
async def get_document_types(db: Session = Depends(get_db)):
    """Get list of available document types"""
    return db.query(DocumentType).all()

@app.get("/document-types/{doc_type_id}", response_model=DocumentTypeResponse)
async def get_document_type(doc_type_id: int, db: Session = Depends(get_db)):
    """Get a specific document type by ID"""
    doc_type = db.query(DocumentType).filter(DocumentType.doc_type_id == doc_type_id).first()
    if not doc_type:
        raise HTTPException(status_code=404, detail="Document type not found")
    return doc_type

@app.get("/companies", response_model=List[CompanyResponse])
async def get_companies(active: Optional[bool] = None, db: Session = Depends(get_db)):
    """Get list of companies, optionally filtered by active status"""
    query = db.query(Company)
    if active is not None:
        query = query.filter(Company.active == active)
    return query.all()

@app.get("/companies/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: int, db: Session = Depends(get_db)):
    """Get a specific company by ID"""
    company = db.query(Company).filter(Company.company_id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company

@app.get("/document-types/{doc_type_id}/companies", response_model=List[CompanyResponse])
async def get_companies_for_doc_type(
    doc_type_id: int, 
    active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Get companies with configurations for a specific document type"""
    query = db.query(Company).join(
        CompanyDocumentConfig, 
        CompanyDocumentConfig.company_id == Company.company_id
    ).filter(CompanyDocumentConfig.doc_type_id == doc_type_id)
    
    if active is not None:
        query = query.filter(CompanyDocumentConfig.active == active)
        
    return query.all()

@app.post("/process", response_model=JobResponse)
async def process_document(
    background_tasks: BackgroundTasks,
    document_type_id: int = Form(...),
    company_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Process a document"""
    # Verify document type and company exist and have a valid configuration
    doc_type = db.query(DocumentType).filter(DocumentType.doc_type_id == document_type_id).first()
    if not doc_type:
        raise HTTPException(status_code=400, detail=f"Unknown document type ID: {document_type_id}")
    
    company = db.query(Company).filter(Company.company_id == company_id).first()
    if not company:
        raise HTTPException(status_code=400, detail=f"Unknown company ID: {company_id}")
    
    config = db.query(CompanyDocumentConfig).filter(
        CompanyDocumentConfig.doc_type_id == document_type_id,
        CompanyDocumentConfig.company_id == company_id,
        CompanyDocumentConfig.active == True
    ).first()
    
    if not config:
        raise HTTPException(
            status_code=400, 
            detail=f"No active configuration found for document type {document_type_id} and company {company_id}"
        )
    
    # For now, assume user ID 1 (would be from authentication in real app)
    user_id = 1
    
    # Create job record in processing_jobs table
    new_job = ProcessingJob(
        original_filename=file.filename,
        status="pending",
        uploader_user_id=user_id,
        doc_type_id=document_type_id,
        company_id=company_id,
        config_id=config.config_id
    )
    db.add(new_job)
    db.flush()  # Flush to get the job_id without committing transaction
    
    # Save the file and create file record
    file_extension = os.path.splitext(file.filename)[1] if file.filename else ""
    upload_path = f"uploads/{new_job.job_id}{file_extension}"
    
    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Create file record
    file_size = os.path.getsize(upload_path)
    new_file = DBFile(
        file_name=file.filename,
        file_path=upload_path,
        file_type=file_extension.lstrip("."),
        file_size=file_size,
        mime_type=file.content_type
    )
    db.add(new_file)
    db.flush()
    
    # Link file to job
    file_link = DocumentFile(
        job_id=new_job.job_id,
        file_id=new_file.file_id,
        file_category=FileCategory.original_upload
    )
    db.add(file_link)
    db.commit()
    
    # Start processing in background
    background_tasks.add_task(
        process_document_task,
        job_id=new_job.job_id,
        db_session_factory=SessionLocal
    )
    
    return new_job

async def process_document_task(job_id: int, db_session_factory):
    """Background task to process a document"""
    db = db_session_factory()
    try:
        # Get job details
        job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
        if not job:
            await manager.send_message(str(job_id), json.dumps({
                "status": "error",
                "message": f"Job {job_id} not found"
            }))
            return
        
        # Get configuration
        config = db.query(CompanyDocumentConfig).filter(
            CompanyDocumentConfig.config_id == job.config_id
        ).first()
        
        if not config:
            error_msg = f"Configuration not found for job {job_id}"
            job.status = "failed"
            job.error_message = error_msg
            db.commit()
            await manager.send_message(str(job_id), json.dumps({
                "status": "error",
                "message": error_msg
            }))
            return
        
        # Get original file
        file_link = db.query(DocumentFile).filter(
            DocumentFile.job_id == job_id,
            DocumentFile.file_category == FileCategory.original_upload
        ).first()
        
        if not file_link:
            error_msg = f"Original file not found for job {job_id}"
            job.status = "failed"
            job.error_message = error_msg
            db.commit()
            await manager.send_message(str(job_id), json.dumps({
                "status": "error",
                "message": error_msg
            }))
            return
        
        file = db.query(DBFile).filter(DBFile.file_id == file_link.file_id).first()
        if not file:
            error_msg = f"File record not found for job {job_id}"
            job.status = "failed"
            job.error_message = error_msg
            db.commit()
            await manager.send_message(str(job_id), json.dumps({
                "status": "error",
                "message": error_msg
            }))
            return
        
        # Update job status to processing
        job.status = "processing"
        db.commit()
        
        # Send status update
        await manager.send_message(str(job_id), json.dumps({
            "status": "processing",
            "message": "Started processing document"
        }))
        
        # Read prompt and schema files
        try:
            with open(config.prompt_path, "r", encoding="utf-8") as f:
                prompt = f.read()
                
            with open(config.schema_path, "r", encoding="utf-8") as f:
                schema = json.load(f)
                
            await manager.send_message(str(job_id), json.dumps({
                "status": "processing",
                "message": "Loaded configuration files"
            }))
        except Exception as e:
            error_msg = f"Error loading prompt or schema: {str(e)}"
            job.status = "failed"
            job.error_message = error_msg
            db.commit()
            await manager.send_message(str(job_id), json.dumps({
                "status": "error",
                "message": error_msg
            }))
            return
        
        # Send status update
        await manager.send_message(str(job_id), json.dumps({
            "status": "processing",
            "message": "Processing with AI model"
        }))
        
        # Get API key - in a real app, this would be from a secure source
        with open("env/config.json", "r") as f:
            config_data = json.load(f)
            api_key = config_data["api_key"]
        
        # Process document with OCR
        try:
            extracted_text = extract_text_from_image(file.file_path, prompt, schema, api_key)
            
            # Parse the extracted text as JSON
            json_data = json.loads(extracted_text)
            
            # Save JSON output to a file
            json_output_path = f"uploads/json_{job_id}.json"
            with open(json_output_path, "w", encoding="utf-8") as json_file:
                json.dump(json_data, json_file, indent=2, ensure_ascii=False)
                
            # Create file record for JSON output
            json_file_size = os.path.getsize(json_output_path)
            json_file_record = DBFile(
                file_name=f"result_{job_id}.json",
                file_path=json_output_path,
                file_type="json",
                file_size=json_file_size,
                mime_type="application/json"
            )
            db.add(json_file_record)
            db.flush()
            
            # Link JSON file to job
            json_link = DocumentFile(
                job_id=job_id,
                file_id=json_file_record.file_id,
                file_category=FileCategory.json_output
            )
            db.add(json_link)
            
            # TODO: Generate Excel output if needed
            
            # Update job status to success
            job.status = "success"
            db.commit()
            
            # Send success message
            await manager.send_message(str(job_id), json.dumps({
                "status": "success",
                "message": "Processing complete",
                "file_id": json_file_record.file_id
            }))
            
        except Exception as e:
            error_msg = f"Error processing document: {str(e)}"
            job.status = "failed"
            job.error_message = error_msg
            db.commit()
            await manager.send_message(str(job_id), json.dumps({
                "status": "error",
                "message": error_msg
            }))
            
    except Exception as e:
        # Handle any other errors
        error_msg = f"Unexpected error: {str(e)}"
        try:
            job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = error_msg
                db.commit()
        except:
            pass
        
        await manager.send_message(str(job_id), json.dumps({
            "status": "error",
            "message": error_msg
        }))
    finally:
        db.close()

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job status updates"""
    await manager.connect(job_id, websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(job_id)

@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: int, db: Session = Depends(get_db)):
    """Get the status of a specific job"""
    job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job

@app.get("/jobs/{job_id}/files")
async def get_job_files(job_id: int, db: Session = Depends(get_db)):
    """Get files associated with a job"""
    files = db.query(DBFile).join(
        DocumentFile, DocumentFile.file_id == DBFile.file_id
    ).filter(DocumentFile.job_id == job_id).all()
    
    if not files:
        raise HTTPException(status_code=404, detail=f"No files found for job {job_id}")
    
    return files

@app.get("/files/{file_id}")
async def download_file(file_id: int, db: Session = Depends(get_db)):
    """Download a file"""
    file = db.query(DBFile).filter(DBFile.file_id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail=f"File {file_id} not found")
        
    return FileResponse(
        path=file.file_path,
        filename=file.file_name,
        media_type=file.mime_type or "application/octet-stream"
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
