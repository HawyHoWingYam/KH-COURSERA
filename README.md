# 🔍 GeminiOCR - AI-Powered Document Processing Platform

A comprehensive document processing platform built with FastAPI (backend) and Next.js (frontend) that leverages Google's Gemini AI for OCR and data extraction from various document types.

## 🚀 Quick Start (Anaconda - Recommended)

### Prerequisites
- Anaconda Python environment
- Node.js and npm
- Access to AWS resources (RDS, S3)

### 1. Backend Setup (Terminal 1)
```bash
cd GeminiOCR/backend
conda activate gemini-sandbox
export AWS_ACCESS_KEY_ID=your_aws_access_key_id
export AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
export AWS_DEFAULT_REGION=ap-southeast-1
uvicorn app:app --host 0.0.0.0 --port 8001
```

### 2. Frontend Setup (Terminal 2)
```bash
cd GeminiOCR/frontend
npm run dev
```

### 3. Access Application
- **Frontend**: http://localhost:3000
- **API Documentation**: http://localhost:8001/docs
- **Health Check**: http://localhost:8001/health

## 📚 Documentation

- **[CLAUDE.md](./CLAUDE.md)** - Complete development setup and commands
- **[DOCKER_DEPLOYMENT.md](./GeminiOCR/DOCKER_DEPLOYMENT.md)** - Production deployment with Docker

## 🏗️ Architecture & Features

**Core Components:**
- **Backend**: FastAPI with WebSocket support
- **Frontend**: Next.js React application with real-time updates  
- **Database**: PostgreSQL (Aurora RDS for sandbox/production)
- **Storage**: AWS S3 with local file fallback
- **AI Engine**: Google Gemini for OCR and data extraction

**Key Features:**
- 🔍 **Multi-format Support**: Process PDFs, images, and ZIP archives
- ⚡ **Real-time Updates**: WebSocket integration for live processing status
- 📦 **Batch Processing**: Handle multiple documents simultaneously
- 🏢 **Multi-tenant**: Company-specific document configurations
- ☁️ **Cloud Integration**: AWS S3 storage and RDS database
- 📊 **API Usage Tracking**: Monitor usage with comprehensive statistics
- 🔄 **API Key Rotation**: Multiple keys with automatic failover
- 📈 **Excel Export**: Automatic JSON to Excel conversion

## 🔧 Environment Setup

### Sandbox Configuration
- **Database**: Aurora RDS Sandbox (`hya-ocr-sandbox`)
- **Storage**: S3 Bucket (`hya-ocr-sandbox`)
- **API Port**: 8001 (Backend), 3000 (Frontend)
- **Environment**: `sandbox`

### Requirements
- **Backend**: Python 3.11+ (Anaconda recommended)
- **Frontend**: Node.js 18+, npm 9+
- **Database**: PostgreSQL 13+ (Aurora RDS)
- **Storage**: AWS S3 bucket access

## 📁 Project Structure

```
GeminiOCR/
├── backend/              # FastAPI application
│   ├── app.py           # Main FastAPI app with WebSocket support
│   ├── config_loader.py # Centralized configuration management
│   ├── env/.env         # Environment variables (not committed)
│   ├── db/              # Database models and connection
│   └── utils/           # S3 storage, Excel conversion, API utilities
├── frontend/            # Next.js React application
│   ├── src/app/         # App router with admin, jobs, upload pages
│   └── .env.local       # Frontend API configuration
└── CLAUDE.md            # Complete development guide
```

## ⚙️ Configuration

### Environment Files
- `backend/env/.env` - Backend configuration (sandbox settings)
- `frontend/.env.local` - Frontend API URL configuration

### Key Settings (Sandbox)
```bash
# Backend (backend/env/.env)
ENVIRONMENT=sandbox
PORT=8001
DATABASE_URL="postgresql://HYA_OCR:password@hya-ocr-sandbox.c94k46soeqmk.ap-southeast-1.rds.amazonaws.com:5432/postgres"
S3_BUCKET_NAME=hya-ocr-sandbox
GEMINI_API_KEY_1=your_sandbox_gemini_key

# Frontend (frontend/.env.local)  
NEXT_PUBLIC_API_URL=http://localhost:8001
```

## 🔍 Monitoring & Health

### Service URLs (Sandbox)
- **Backend API**: http://localhost:8001
- **API Documentation**: http://localhost:8001/docs
- **Health Check**: http://localhost:8001/health
- **Frontend**: http://localhost:3000

### Database & Storage
- **Database**: hya-ocr-sandbox.c94k46soeqmk.ap-southeast-1.rds.amazonaws.com:5432
- **S3 Bucket**: hya-ocr-sandbox

## 🚨 Important Notes

- **Never commit** environment files (`.env`, `.env.local`)
- **Use Anaconda** for consistent Python environment management
- **Sandbox environment** is configured for safe testing
- **Configuration priority**: Environment variables > AWS Secrets > .env > defaults
- **Multi-API key support** with automatic failover and rotation

## 🛠️ Troubleshooting

**Common Issues:**
- **Port conflicts**: Use `lsof -i :8001` to find and kill processes using the port
- **Missing dependencies**: Ensure `pip install python-multipart` for file uploads
- **Database connection**: Verify DATABASE_URL and database accessibility
- **WebSocket issues**: Check health endpoint and install `uvicorn[standard] websockets`

**For detailed troubleshooting**: See [CLAUDE.md](./CLAUDE.md#testing-and-quality)

## 📞 Support

**For development issues:**
1. Check [health endpoints](http://localhost:8001/health)
2. Review logs in terminal
3. Verify environment variables
4. Consult [CLAUDE.md](./CLAUDE.md) for detailed setup

**Environment Status**: Sandbox ✅ | **Last Updated**: 2025-09-06

---

**Note**: This is the main project README. For detailed development commands and Docker deployment, see the documentation links above.