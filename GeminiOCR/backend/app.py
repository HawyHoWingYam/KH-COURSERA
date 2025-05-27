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

from pydantic import BaseModel, Field

# Import functions from main.py
from main import (
    extract_text_from_image,
    load_config,
    get_response_schema,
    configure_prompt,
)

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


# Models
class DocumentTypesList(BaseModel):
    document_types: List[str]


class ProvidersList(BaseModel):
    providers: List[str]


class ProcessResponse(BaseModel):
    job_id: str
    message: str
    status: str


class JobStatus(BaseModel):
    status: str
    message: str


# Helper functions
def get_config():
    config = load_config()
    if not config:
        raise HTTPException(status_code=500, detail="Failed to load configuration")
    return config


def get_api_key():
    config = get_config()
    api_key = config.get("api_key")
    if not api_key:
        raise HTTPException(
            status_code=500, detail="API key not found in configuration"
        )
    return api_key


def get_document_types():
    """Get available document types from the directory structure"""
    doc_type_dir = os.path.join(os.getcwd(), "document_type")
    if not os.path.exists(doc_type_dir):
        return []
    return [
        d
        for d in os.listdir(doc_type_dir)
        if os.path.isdir(os.path.join(doc_type_dir, d))
    ]


def get_providers(document_type):
    """Get available providers for a document type"""
    doc_type_dir = os.path.join(os.getcwd(), "document_type", document_type)
    if not os.path.exists(doc_type_dir):
        return []
    return [
        d
        for d in os.listdir(doc_type_dir)
        if os.path.isdir(os.path.join(doc_type_dir, d))
    ]


def ensure_provider_directories(document_type, provider):
    """Create necessary directories for a provider"""
    base_path = os.path.join(os.getcwd(), "document_type", document_type, provider)
    os.makedirs(os.path.join(base_path, "upload"), exist_ok=True)
    os.makedirs(os.path.join(base_path, "output"), exist_ok=True)
    os.makedirs(os.path.join(base_path, "processed"), exist_ok=True)
    return base_path


# Routes
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy"}


@app.get("/document-types", response_model=DocumentTypesList)
async def get_document_types_api():
    """Get list of available document types"""
    return {"document_types": get_document_types()}


@app.get("/document-types/{document_type}/providers", response_model=ProvidersList)
async def get_providers_api(document_type: str):
    """Get list of available providers for a document type"""
    if document_type not in get_document_types():
        raise HTTPException(
            status_code=404, detail=f"Document type '{document_type}' not found"
        )
    return {"providers": get_providers(document_type)}


@app.post("/process", response_model=ProcessResponse)
async def process_document(
    background_tasks: BackgroundTasks,
    document_type: str = Form(...),
    provider: str = Form(...),
    file: UploadFile = File(...),
):
    """Process a document"""
    # Validate document type and provider
    if document_type not in get_document_types():
        raise HTTPException(
            status_code=400, detail=f"Unknown document type: {document_type}"
        )

    if provider not in get_providers(document_type):
        raise HTTPException(
            status_code=400, detail=f"Unknown provider for {document_type}: {provider}"
        )

    # Generate job ID
    job_id = str(uuid.uuid4())

    # Ensure directories exist
    ensure_provider_directories(document_type, provider)

    # Save uploaded file
    file_extension = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
    upload_dir = os.path.join("document_type", document_type, provider, "upload")

    file_path = os.path.join(upload_dir, f"{job_id}{file_extension}")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Process in background
    background_tasks.add_task(
        process_document_task,
        job_id=job_id,
        document_type=document_type,
        provider=provider,
        file_path=file_path,
    )

    return {
        "job_id": job_id,
        "message": "Document processing started",
        "status": "processing",
    }


async def process_document_task(
    job_id: str, document_type: str, provider: str, file_path: str
):
    """Background task to process a document"""
    try:
        # Ensure directories exist
        ensure_provider_directories(document_type, provider)

        # Get configuration
        api_key = get_api_key()

        # Update client that we're starting
        await manager.send_message(
            job_id,
            json.dumps(
                {"status": "processing", "message": "Started processing document"}
            ),
        )

        # Get prompt and schema
        prompt = configure_prompt(document_type, provider)
        schema = get_response_schema(document_type, provider)

        if not prompt:
            raise FileNotFoundError(f"Prompt not found for {document_type}/{provider}")

        if not schema:
            raise FileNotFoundError(f"Schema not found for {document_type}/{provider}")

        # Update client
        await manager.send_message(
            job_id,
            json.dumps(
                {"status": "processing", "message": "Loaded configuration files"}
            ),
        )

        # Update client
        await manager.send_message(
            job_id,
            json.dumps({"status": "processing", "message": "Processing with AI model"}),
        )

        extracted_text = extract_text_from_image(file_path, prompt, schema, api_key)

        # Generate output filename
        output_dir = os.path.join("document_type", document_type, provider, "output")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = os.path.join(
            output_dir, f"{provider}_{job_id}_{timestamp}.json"
        )

        # Save extracted text to JSON file
        try:
            # Parse the extracted text as JSON
            json_data = json.loads(extracted_text)
            with open(output_filename, "w", encoding="utf-8") as json_file:
                json.dump(json_data, json_file, indent=2, ensure_ascii=False)

            # Update client on success
            await manager.send_message(
                job_id,
                json.dumps(
                    {
                        "status": "success",
                        "message": "Processing complete",
                        "result_path": output_filename,
                    }
                ),
            )

        except json.JSONDecodeError:
            # If not valid JSON, save as raw text
            with open(output_filename, "w", encoding="utf-8") as json_file:
                json.dump(
                    {"raw_text": extracted_text},
                    json_file,
                    indent=2,
                    ensure_ascii=False,
                )

            # Update client with warning
            await manager.send_message(
                job_id,
                json.dumps(
                    {
                        "status": "warning",
                        "message": "Processing complete, but result is not valid JSON",
                        "result_path": output_filename,
                    }
                ),
            )

    except Exception as e:
        # Handle errors
        error_message = str(e)
        await manager.send_message(
            job_id,
            json.dumps(
                {
                    "status": "error",
                    "message": f"Error processing document: {error_message}",
                }
            ),
        )


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


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a specific job"""
    # In a real implementation, this would query a database
    # For this example, we'll just check if the output file exists
    for doc_type in get_document_types():
        for provider in get_providers(doc_type):
            output_dir = os.path.join("document_type", doc_type, provider, "output")
            if not os.path.exists(output_dir):
                continue

            for file in os.listdir(output_dir):
                if job_id in file:
                    return {
                        "status": "complete",
                        "document_type": doc_type,
                        "provider": provider,
                        "result_path": os.path.join(output_dir, file),
                    }

    return {"status": "processing", "message": "Job is still processing or not found"}


@app.get("/download/{job_id}")
async def download_result(job_id: str):
    """Download the results for a specific job"""
    for doc_type in get_document_types():
        for provider in get_providers(doc_type):
            output_dir = os.path.join("document_type", doc_type, provider, "output")
            if not os.path.exists(output_dir):
                continue

            for file in os.listdir(output_dir):
                if job_id in file:
                    file_path = os.path.join(output_dir, file)
                    return FileResponse(
                        path=file_path, filename=file, media_type="application/json"
                    )

    raise HTTPException(status_code=404, detail=f"No results found for job {job_id}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
