# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Architecture

GeminiOCR is a document processing platform with FastAPI backend and Next.js frontend that uses Google Gemini AI for OCR and data extraction.

### Core Structure
```
KH-COURSERA/
├── GeminiOCR/         # Application code
│   ├── backend/       # FastAPI application
│   │   ├── app.py    # Main FastAPI app with WebSocket support
│   │   ├── main.py   # OCR processing logic
│   │   ├── config_loader.py # Centralized configuration management
│   │   ├── db/       # Database models and connection
│   │   └── utils/    # S3 storage, Excel conversion, API key management
│   └── frontend/     # Next.js React application
│       └── src/app/  # App router with admin, jobs, upload pages
├── env/              # Environment configuration files (.env, .env.example)
├── docker/           # Docker configuration (Dockerfiles, docker-compose.yml, deploy.sh)
├── migrations/       # Database migrations (Alembic)
├── scripts/          # Database and deployment scripts
├── terraform/        # Infrastructure as Code
└── config/           # Application configuration files
```

### Key Architectural Patterns
- **Configuration Management**: Priority-based config loading (env vars > AWS Secrets > .env > defaults)
- **Multi-API Key Support**: Automatic failover and rotation for Gemini API keys
- **Dual Storage**: Local file storage with optional S3 integration
- **WebSocket Integration**: Real-time job progress updates
- **Batch Processing**: ZIP file handling with individual job tracking
- **Centralized File Organization**: Infrastructure files organized by type (env/, docker/, scripts/, terraform/, migrations/)

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
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

**Frontend (Terminal 2):**
```bash
cd /home/ubuntu/KH-COURSERA/GeminiOCR/frontend
npm run dev
```

**Access URLs:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

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

# Start backend server (sandbox environment - port 8000)
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

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
docker-compose -f docker/docker-compose.dev.yml up -d

# View development logs
docker-compose -f docker/docker-compose.dev.yml logs -f

# Access development tools container
docker-compose -f docker/docker-compose.dev.yml exec devtools bash

# Run database check in container
docker-compose -f docker/docker-compose.dev.yml exec backend python check_db.py
```

### Production Deployment
```bash
# Deploy with zero-downtime (blue-green)
docker/deploy.sh blue-green

# Deploy with rolling updates
docker/deploy.sh rolling

# Standard production deployment
docker-compose -f docker/docker-compose.yml up -d

# Using AWS RDS configuration
docker-compose -f docker/docker-compose.prod.yml up -d
```

## Configuration System

The application uses a sophisticated configuration system managed by `config_loader.py`:

1. **Environment Variables** (highest priority)
2. **AWS Secrets Manager** (production)
3. **Local .env file** (`env/.env`)
4. **config.json** (non-sensitive settings)
5. **Default values** (lowest priority)

### Environment Variables

**Sandbox Environment (env/.env.sandbox):**
```bash
# Environment Configuration
ENVIRONMENT=sandbox
PORT=8000

# Database (Aurora RDS Sandbox)
# Note: credentials live in env/.env only. Example (do not commit real values):
# DATABASE_URL="postgresql://HYA_OCR:<ENCODED_PASSWORD>@hya-ocr-sandbox.c94k46soeqmk.ap-southeast-1.rds.amazonaws.com:5432/document_processing_platform"

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

# Production should use:
# NEXT_PUBLIC_API_URL=http://18.142.68.48:8000
```

**Frontend Environment (env/.env.local - Development):**
```bash
# Frontend API Configuration (Development)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Frontend Environment (Production - AWS):**
```bash
# Frontend API Configuration (Production)
NEXT_PUBLIC_API_URL=http://18.142.68.48:8000
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
- **Backend config**: `env/.env` (never commit)
- **Frontend env**: `env/.env.local`
- **Docker configs**: `docker/docker-compose.yml`, `docker/docker-compose.dev.yml`, `docker/docker-compose.prod.yml`
- **Deployment script**: `docker/deploy.sh` (automated zero-downtime deployment)

### Service URLs (Sandbox Environment)
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Frontend**: http://localhost:3000
- **Database**: hya-ocr-sandbox.c94k46soeqmk.ap-southeast-1.rds.amazonaws.com:5432
- **S3 Bucket**: hya-ocr-sandbox

### Service URLs (Production Environment)
- **Database**: hya-ocr-instance-dev.c94k46soeqmk.ap-southeast-1.rds.amazonaws.com:5432
- **Database Name**: document_processing_platform
- **Database User**: HYA_OCR

## WebSocket Architecture

Real-time job progress via WebSocket endpoints:
- Connect to `/ws/{job_id}` for individual job updates
- Frontend components in `src/app/jobs/` handle WebSocket connections
- Backend WebSocket handlers in `app.py`

## 🗄️ Database Infrastructure Management

### Multi-Environment Database Support

GeminiOCR now supports flexible database environment switching with Terraform-managed Aurora PostgreSQL clusters:

#### Environments
- **Local**: PostgreSQL on localhost (development)
- **Sandbox**: AWS Aurora PostgreSQL (integration testing)
- **UAT**: AWS Aurora PostgreSQL (user acceptance testing)
- **Production**: AWS Aurora PostgreSQL (production workloads)

### Quick Database Operations

#### Environment Switching
```bash
# Switch to local development
python scripts/switch_db_env.py --env local

# Switch to sandbox for integration testing
python scripts/switch_db_env.py --env sandbox

# Check current environment status
python scripts/switch_db_env.py --status

# Test database connection
python scripts/switch_db_env.py --test
```

#### Database Migration Management
```bash
# Create new migration
python scripts/manage_migrations.py create -m "Add new feature table"

# Apply all pending migrations
python scripts/manage_migrations.py upgrade

# Check migration status
python scripts/manage_migrations.py status

# Rollback one migration
python scripts/manage_migrations.py downgrade

# Environment-specific operations
python scripts/manage_migrations.py --env production status
```

### Terraform Infrastructure Management

#### Deploy Aurora Clusters
```bash
# Sandbox environment
cd terraform/environments/sandbox
terraform init
terraform plan -var="database_master_password=secure_password"
terraform apply

# Production environment (requires approval)
cd terraform/environments/production
terraform plan -var="database_master_password=secure_password"
terraform apply
```

#### Infrastructure Components
- **Aurora PostgreSQL Clusters**: Environment-specific sizing
- **Security Groups**: VPC-restricted access
- **KMS Encryption**: Data encryption at rest
- **CloudWatch Monitoring**: Performance and health metrics
- **Automated Backups**: Environment-specific retention policies

### Application Integration

#### Python Database Manager
```python
from database_manager import get_database_manager, health_check

# Get database manager (automatically detects environment)
db_manager = await get_database_manager()

# Synchronous operations
session = db_manager.get_session()

# Asynchronous operations with read/write splitting
async with db_manager.get_async_connection() as conn:
    result = await conn.fetch("SELECT * FROM users")

# Read-only operations (uses read replica if available)
async with db_manager.get_async_connection(readonly=True) as conn:
    reports = await conn.fetch("SELECT * FROM reports")

# Health check
health = await health_check()
```

#### FastAPI Integration
```python
from database_manager import get_database_manager

@app.get("/health/database")
async def database_health():
    return await health_check()

@app.get("/users")
async def get_users():
    db_manager = await get_database_manager()
    async with db_manager.get_async_connection(readonly=True) as conn:
        users = await conn.fetch("SELECT * FROM users")
        return users
```

### Configuration Files

#### Database Environment Configs
- `config/database/local.yml`: Local PostgreSQL settings
- `config/database/sandbox.yml`: Sandbox Aurora configuration
- `config/database/uat.yml`: UAT Aurora configuration  
- `config/database/production.yml`: Production Aurora configuration

#### Key Features
- **Connection Pooling**: Environment-optimized pool sizes
- **SSL/TLS**: Enforced encryption for AWS environments
- **Read/Write Splitting**: Automatic routing to appropriate endpoints
- **Health Monitoring**: Connection latency and pool status tracking
- **AWS Integration**: Secrets Manager and Parameter Store support

### Monitoring and Alerting

#### CloudWatch Metrics
- CPU utilization thresholds
- Database connection counts
- Query performance metrics
- Replication lag monitoring

#### Automated Alerts
- **Sandbox**: Basic monitoring (7-day retention)
- **UAT**: Enhanced monitoring (14-day retention)
- **Production**: Full monitoring with SNS alerts (30-day retention)

### Security Best Practices

#### Access Control
- VPC-only database access
- Security group IP restrictions
- IAM-based authentication where possible
- Encrypted connections required

#### Credential Management
- AWS Secrets Manager integration
- Automatic password rotation (production)
- Environment-specific access policies
- No hardcoded credentials

### CI/CD Integration

#### Automated Database Deployment
- **GitHub Actions**: `database-deployment.yml` workflow
- **Terraform Planning**: Infrastructure change validation
- **Migration Testing**: Automated migration validation
- **Environment Promotion**: Staging → Production deployment
- **Health Checks**: Post-deployment verification

#### Deployment Safety
- **Backup Verification**: Pre-migration backup checks
- **Migration Validation**: Test migrations on clean databases
- **Rollback Capability**: Automated rollback on failures
- **Manual Approval**: Production deployments require approval

### Troubleshooting

#### Common Issues
```bash
# Connection problems
python scripts/switch_db_env.py --info
python scripts/switch_db_env.py --test

# Migration issues
python scripts/manage_migrations.py status
python scripts/manage_migrations.py current

# Health checks
python -c "import asyncio; from database_manager import health_check; print(asyncio.run(health_check()))"
```

#### Performance Optimization
- **Connection Pooling**: Optimized per environment
- **Read Replicas**: Automatic read/write splitting
- **Query Monitoring**: Slow query detection and logging
- **Performance Insights**: Enabled for UAT/Production

For detailed documentation, see: `database-infrastructure-README.md`
