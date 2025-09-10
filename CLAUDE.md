# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Architecture

GeminiOCR is a document processing platform with FastAPI backend and Next.js frontend that uses Google Gemini AI for OCR and data extraction.

### Core Structure
```
GeminiOCR/
├── backend/           # FastAPI application
│   ├── app.py        # Main FastAPI app with WebSocket support
│   ├── main.py       # OCR processing logic
│   ├── config_loader.py # Centralized configuration management
│   ├── db/           # Database models and connection
│   └── utils/        # S3 storage, Excel conversion, API key management
├── frontend/         # Next.js React application
│   └── src/app/      # App router with admin, jobs, upload pages
```

### Key Architectural Patterns
- **Configuration Management**: Priority-based config loading (env vars > AWS Secrets > .env > defaults)
- **Multi-API Key Support**: Automatic failover and rotation for Gemini API keys
- **Dual Storage**: Local file storage with optional S3 integration
- **WebSocket Integration**: Real-time job progress updates
- **Batch Processing**: ZIP file handling with individual job tracking

## 🚀 Quick Start Guide

### Prerequisites
- Anaconda Python environment
- Access to Aurora RDS sandbox database
- AWS S3 sandbox bucket access

### Start Backend & Frontend (Sandbox)

**Backend (Terminal 1):**
```bash
cd /home/ubuntu/KH-COURSERA/GeminiOCR/backend
conda activate gemini-sandbox
export AWS_ACCESS_KEY_ID=your_aws_access_key_id
export AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
export AWS_DEFAULT_REGION=ap-southeast-1
uvicorn app:app --host 0.0.0.0 --port 8001
```

**Frontend (Terminal 2):**
```bash
cd /home/ubuntu/KH-COURSERA/GeminiOCR/frontend
npm run dev
```

**Access URLs:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8001
- API Docs: http://localhost:8001/docs

## Development Commands

### Environment Setup (Anaconda Recommended)

**First-time setup:**
```bash
# Install Anaconda (if not installed)
bash Anaconda3-2025.06-0-Linux-x86_64.sh -b -p $HOME/anaconda3

# Configure default Anaconda environment
export PATH=$HOME/anaconda3/bin:$PATH
echo 'export PATH=$HOME/anaconda3/bin:$PATH' >> ~/.bashrc
conda init bash
source ~/.bashrc

# Create and activate sandbox environment
conda create -n gemini-sandbox python=3.11 -y
conda activate gemini-sandbox

# Install dependencies
cd GeminiOCR/backend
pip install -r requirements.txt
pip install python-multipart  # Required for file uploads
```

### Backend Development
```bash
# Navigate to backend
cd GeminiOCR/backend

# Activate conda environment (if not already active)
conda activate gemini-sandbox

# Set AWS environment variables (for sandbox)
export AWS_ACCESS_KEY_ID=your_aws_access_key_id
export AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
export AWS_DEFAULT_REGION=ap-southeast-1

# Start backend server (sandbox environment - port 8001)
uvicorn app:app --host 0.0.0.0 --port 8001

# Check database connection
python check_db.py

# Initialize database
python init_db.py
```

### Frontend Development
```bash
# Navigate to frontend
cd GeminiOCR/frontend

# Start development server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Run linting
npm run lint

# Install dependencies
npm install
```

### Docker Development
```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# View development logs
docker-compose -f docker-compose.dev.yml logs -f

# Access development tools container
docker-compose -f docker-compose.dev.yml exec devtools bash

# Run database check in container
docker-compose -f docker-compose.dev.yml exec backend python check_db.py
```

### Production Deployment
```bash
# Deploy with zero-downtime (blue-green)
./deploy.sh blue-green

# Deploy with rolling updates
./deploy.sh rolling

# Standard production deployment
docker-compose up -d

# Using AWS RDS configuration
docker-compose -f docker-compose.prod.yml up -d
```

## Configuration System

The application uses a sophisticated configuration system managed by `config_loader.py`:

1. **Environment Variables** (highest priority)
2. **AWS Secrets Manager** (production)
3. **Local .env file** (`backend/env/.env`)
4. **config.json** (non-sensitive settings)
5. **Default values** (lowest priority)

### Environment Variables

**Sandbox Environment (backend/env/.env):**
```bash
# Environment Configuration
ENVIRONMENT=sandbox
PORT=8001

# Database (Aurora RDS Sandbox)
DATABASE_URL="postgresql://HYA_OCR:1JnQlgFO<t)<D8dLGn#3BBUTlE#Q@hya-ocr-sandbox.c94k46soeqmk.ap-southeast-1.rds.amazonaws.com:5432/postgres"

# Gemini API Keys (supports multiple with automatic failover)
GEMINI_API_KEY_1=your_sandbox_gemini_key
MODEL_NAME=gemini-2.5-flash-preview-05-20

# AWS S3 (Sandbox)
S3_ENABLED=true
S3_BUCKET_NAME=hya-ocr-sandbox
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_DEFAULT_REGION=ap-southeast-1

# API URLs
API_BASE_URL=18.142.68.48
NEXT_PUBLIC_API_URL=http://localhost:8001
```

**Frontend Environment (frontend/.env.local):**
```bash
# Frontend API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8001
```

## Database Schema

Key models in `db/models.py`:
- `Company`: Company management
- `DocumentType`: Document type definitions
- `CompanyDocumentConfig`: Company-specific processing configs
- `ProcessingJob`: Individual document jobs
- `BatchJob`: ZIP file batch processing
- `File`: File metadata and storage
- `ApiUsage`: API usage tracking

## Testing and Quality

### Frontend
```bash
cd GeminiOCR/frontend
npm run lint        # ESLint checking
npm run build       # TypeScript compilation check
```

### Backend
```bash
cd GeminiOCR/backend
python check_db.py  # Database connectivity test
# No formal test suite - validate with health endpoints
```

## Important File Locations & URLs

### Configuration Files
- **Backend config**: `backend/env/.env` (never commit)
- **Frontend env**: `frontend/.env.local`
- **Docker configs**: `docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.prod.yml`
- **Deployment script**: `deploy.sh` (automated zero-downtime deployment)

### Service URLs (Sandbox Environment)
- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs
- **Health Check**: http://localhost:8001/health
- **Frontend**: http://localhost:3000
- **Database**: hya-ocr-sandbox.c94k46soeqmk.ap-southeast-1.rds.amazonaws.com:5432
- **S3 Bucket**: hya-ocr-sandbox

## WebSocket Architecture

Real-time job progress via WebSocket endpoints:
- Connect to `/ws/{job_id}` for individual job updates
- Frontend components in `src/app/jobs/` handle WebSocket connections
- Backend WebSocket handlers in `app.py`