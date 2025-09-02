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

## Development Commands

### Backend Development
```bash
# Navigate to backend
cd GeminiOCR/backend

# Start backend server (development)
uvicorn app:app --reload

# Start with network access
uvicorn app:app --host 0.0.0.0 --port 8000

# Check database connection
python check_db.py

# Initialize database
python init_db.py

# Install dependencies
pip install -r requirements.txt
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

### Required Environment Variables
```bash
# Gemini API Keys (supports multiple with automatic failover)
GEMINI_API_KEY_1=your_first_key
GEMINI_API_KEY_2=your_second_key

# Database
DATABASE_URL=postgresql://user:pass@host:port/db

# AWS (optional)
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_DEFAULT_REGION=ap-southeast-1
AWS_S3_BUCKET=your_bucket
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

## Important File Locations

- **Backend config**: `backend/env/.env` (never commit)
- **API docs**: http://localhost:8000/docs (when backend running)
- **Health check**: http://localhost:8000/health
- **Frontend env**: `frontend/.env.local`
- **Docker configs**: `docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.prod.yml`
- **Deployment script**: `deploy.sh` (automated zero-downtime deployment)

## WebSocket Architecture

Real-time job progress via WebSocket endpoints:
- Connect to `/ws/{job_id}` for individual job updates
- Frontend components in `src/app/jobs/` handle WebSocket connections
- Backend WebSocket handlers in `app.py`