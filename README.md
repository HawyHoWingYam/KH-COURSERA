# GeminiOCR

A comprehensive document processing platform built with FastAPI (backend) and Next.js (frontend) that leverages Google's Gemini AI for OCR and data extraction.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Requirements](#system-requirements)
- [Project Structure](#project-structure)
- [Installation](#installation)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Configuration System](#configuration-system)
  - [Environment Variables Setup](#environment-variables-setup)
  - [Configuration Priority](#configuration-priority)
  - [API Key Management](#api-key-management)
  - [Configuration Examples](#configuration-examples)
- [Development](#development)
  - [Running the Backend](#running-the-backend)
  - [Running the Frontend](#running-the-frontend)
  - [Common Issues](#common-issues)
- [Security Best Practices](#security-best-practices)
  - [Environment Variables](#environment-variables)
  - [AWS Secrets Manager](#aws-secrets-manager)
  - [Security Checklist](#security-checklist)
- [Production Deployment](#production-deployment)
  - [Building the Frontend](#building-the-frontend)
  - [Setting up Systemd Services](#setting-up-systemd-services)
  - [Managing Services](#managing-services)
- [API Documentation](#api-documentation)
- [Database Schema](#database-schema)
- [Contributing](#contributing)
- [License](#license)

## Overview

GeminiOCR is a powerful document processing platform that allows users to extract structured data from various document types using Google's Gemini AI. The system supports individual document processing as well as batch processing through ZIP files, with real-time progress updates via WebSockets.

## Features

- **Document Processing**: Extract data from PDFs and images using Google Gemini AI
- **Batch Processing**: Process multiple documents at once via ZIP files
- **Real-time Updates**: WebSocket integration for live processing status
- **Company & Document Type Management**: Organize documents by company and type
- **Configuration Management**: Customize processing parameters per company and document type
- **API Usage Tracking**: Monitor API usage with daily and monthly statistics
- **Excel Export**: Automatically convert extracted JSON data to Excel format
- **User Authentication**: Secure access control for different user roles
- **API Key Rotation**: Support for multiple API keys with automatic failover
- **Advanced Configuration System**: Centralized configuration with priority-based loading

## System Requirements

- **Backend**:
  - Python 3.9+
  - PostgreSQL 13+
  - Google Gemini API key
  - python-dotenv package
  
- **Frontend**:
  - Node.js 18+
  - npm 9+

## Project Structure

```
GeminiOCR/
├── backend/
│   ├── app.py              # FastAPI application
│   ├── main.py             # OCR processing logic
│   ├── config_loader.py    # Centralized configuration management
│   ├── env/
│   │   ├── .env            # Environment variables (not in Git)
│   │   ├── .env.example    # Example environment template
│   │   └── config.json     # Non-sensitive configuration
│   ├── db/
│   │   ├── database.py     # Database connection
│   │   └── models.py       # SQLAlchemy models
│   └── utils/              # Utility functions
│       ├── excel_converter.py
│       └── api_key_manager.py
│
├── frontend/
│   ├── src/
│   │   ├── app/            # Next.js pages
│   │   ├── components/     # React components
│   │   └── lib/            # Utility functions
│   ├── public/             # Static assets
│   └── package.json        # Dependencies
```

## Installation

### Backend Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/GeminiOCR.git
   cd GeminiOCR
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   # Create .env file from template
   cd env
   cp .env.example .env
   
   # Edit the .env file with your credentials
   nano .env
   ```

### Frontend Setup

1. Install dependencies:
   ```bash
   cd ../frontend
   npm install
   ```

2. Configure environment variables:
   - Create a `.env.local` file with the backend API URL
   ```bash
   echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
   ```

## Configuration System

### Environment Variables Setup

The application uses a `.env` file located in `backend/env/` to store sensitive configuration. This file should **never** be committed to Git.

1. Create a `.env` file in the `backend/env/` directory:
   ```bash
   # Navigate to the env directory
   cd backend/env
   
   # Create .env file from the example template
   cp .env.example .env
   
   # Edit the .env file
   nano .env
   ```

2. Add the following environment variables to your `.env` file:

   ```ini
   # Gemini API Keys
   GEMINI_API_KEY_1=your_first_api_key
   GEMINI_API_KEY_2=your_second_api_key
   
   # Database Connection
   DATABASE_URL=postgresql://username:password@host:port/database
   
   # AWS Configuration (for production)
   AWS_ACCESS_KEY_ID=your_aws_access_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret_key
   AWS_DEFAULT_REGION=ap-southeast-1
   AWS_SECRET_NAME=your_secret_name
   
   # Application Settings
   API_BASE_URL=localhost
   PORT=8000
   MODEL_NAME=gemini-2.5-flash-preview-05-20
   ENVIRONMENT=development
   ```

3. Set appropriate file permissions:
   ```bash
   chmod 600 .env  # Restrict access to owner only
   ```

### Configuration Priority

The configuration system follows this priority order:

1. **Environment variables** (highest priority)
2. **AWS Secrets Manager** (if configured and in production mode)
3. **Local .env file**
4. **config.json file** (for non-sensitive configuration)
5. **Default values** (lowest priority)

This allows for flexible configuration across different environments.

### API Key Management

The system supports multiple Gemini API keys with automatic failover and rotation:

1. **Multiple keys**: Add as many API keys as needed using `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, etc.
2. **Automatic rotation**: If one key fails, the system automatically tries the next one
3. **Load balancing**: Keys are used in a round-robin fashion to distribute usage

Example configuration:
```ini
GEMINI_API_KEY_1=456
GEMINI_API_KEY_2=123
```

### Configuration Examples

#### Development Environment

```ini
# .env for development
ENVIRONMENT=development
GEMINI_API_KEY_1=your_dev_api_key
DATABASE_URL=postgresql://user:pass@localhost:5432/gemini_dev
API_BASE_URL=localhost
PORT=8000
```

#### Production Environment

```ini
# .env for production
ENVIRONMENT=production
GEMINI_API_KEY_1=your_prod_api_key_1
GEMINI_API_KEY_2=your_prod_api_key_2
DATABASE_URL=postgresql://user:pass@production-db:5432/gemini_prod
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_DEFAULT_REGION=ap-southeast-1
AWS_SECRET_NAME=your_secret_name
API_BASE_URL=api.yourdomain.com
PORT=8000
```

## Development

### Running the Backend

```bash
cd GeminiOCR/backend
uvicorn app:app --reload
```

For network access:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

### Running the Frontend

```bash
cd GeminiOCR/frontend
npm run dev
```

The frontend will be available at http://localhost:3000

### Common Issues

- **Address already in use error**: If you encounter this error when starting the backend, find and kill the process using the port:
  ```bash
  lsof -i :8000
  kill -9 <PID>
  ```

- **Configuration not found**: Ensure your `.env` file exists in the `backend/env/` directory and has the correct permissions.

- **Database connection error**: Check your DATABASE_URL in the `.env` file and ensure the database server is running.

- **API key errors**: Verify your Gemini API keys are valid and have the necessary permissions.

- **WebSocket connection issues**: If you encounter WebSocket errors:
  
  **Missing WebSocket library warning**:
  ```
  WARNING: No supported WebSocket library detected
  ```
  Solution: Install WebSocket dependencies:
  ```bash
  pip install 'uvicorn[standard]' websockets
  ```
  
  **WebSocket 404 errors**:
  ```
  INFO: 127.0.0.1:51096 - "GET /ws/246 HTTP/1.1" 404 Not Found
  ```
  Solutions:
  - Ensure the backend is running with WebSocket support
  - Check that the WebSocket endpoint is properly registered
  - Verify the job ID format in the WebSocket URL
  
  **Testing WebSocket connections**:
  ```bash
  # Test WebSocket functionality
  cd backend
  python test_websocket.py localhost 8000
  ```
  
  **WebSocket connection debugging**:
  - Check the health endpoint: `http://localhost:8000/health`
  - Look for WebSocket status in the health response
  - Monitor backend logs for WebSocket connection attempts
  - Ensure CORS settings allow WebSocket connections

## Security Best Practices

### Environment Variables

In production environments, set up the following environment variables in the system or through a secure environment file:

```bash
# Google Gemini API Keys
export GEMINI_API_KEY_1="your_first_api_key"
export GEMINI_API_KEY_2="your_second_api_key"

# Database
export DATABASE_URL="postgresql://username:password@host:port/database"

# AWS Configuration
export AWS_ACCESS_KEY_ID="your_aws_access_key"
export AWS_SECRET_ACCESS_KEY="your_aws_secret_key"
export AWS_DEFAULT_REGION="ap-southeast-1"
export AWS_SECRET_NAME="your_secret_name"

# Application
export API_BASE_URL="localhost"
export PORT="8000"
export MODEL_NAME="gemini-2.5-flash-preview-05-20"
export ENVIRONMENT="production"
```

### AWS Secrets Manager

For production environments, it's recommended to use AWS Secrets Manager to store sensitive information:

1. Store your secrets in AWS Secrets Manager
2. Configure AWS credentials in your environment
3. The application will automatically retrieve secrets when running in production mode

The configuration loader will handle AWS Secrets Manager integration automatically when:
- `ENVIRONMENT` is set to "production"
- AWS credentials are properly configured
- `AWS_SECRET_NAME` is defined

### Security Checklist

- [ ] All sensitive data uses environment variables
- [ ] `.env` file is added to `.gitignore`
- [ ] Production environment uses AWS Secrets Manager
- [ ] API keys are rotated regularly
- [ ] Database connection uses SSL
- [ ] Application logging and monitoring is enabled
- [ ] Firewall rules are configured
- [ ] Different credentials are used for development, testing, and production

## Production Deployment

### Building the Frontend

```bash
cd GeminiOCR/frontend
npm run build
```

### Setting up Systemd Services

1. Create a systemd service file for the backend:
   ```bash
   sudo nano /etc/systemd/system/gemini-ocr.service
   ```
   
   Add the following content:
   ```
   [Unit]
   Description=GeminiOCR Backend
   After=network.target

   [Service]
   User=<your_user>
   WorkingDirectory=/path/to/GeminiOCR/backend
   ExecStart=/path/to/venv/bin/uvicorn app:app --host 0.0.0.0 --port 8000
   Restart=always
   
   # Environment variables
   Environment=ENVIRONMENT=production
   Environment=PORT=8000
   # Add other environment variables here or use EnvironmentFile
   EnvironmentFile=/path/to/GeminiOCR/backend/env/.env.production

   [Install]
   WantedBy=multi-user.target
   ```

2. Create a systemd service file for the frontend:
   ```bash
   sudo nano /etc/systemd/system/gemini-frontend.service
   ```
   
   Add the following content:
   ```
   [Unit]
   Description=GeminiOCR Frontend
   After=network.target

   [Service]
   User=<your_user>
   WorkingDirectory=/path/to/GeminiOCR/frontend
   ExecStart=/usr/bin/npm start
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and start the services:
   ```bash
   sudo systemctl enable gemini-ocr
   sudo systemctl enable gemini-frontend
   sudo systemctl start gemini-ocr
   sudo systemctl start gemini-frontend
   ```

### Managing Services

- **Restart services**:
  ```bash
  sudo systemctl restart gemini-ocr
  sudo systemctl restart gemini-frontend
  ```

- **Stop services**:
  ```bash
  sudo systemctl stop gemini-ocr
  sudo systemctl stop gemini-frontend
  ```

- **Check service status**:
  ```bash
  sudo systemctl status gemini-ocr
  sudo systemctl status gemini-frontend
  ```

- **View logs**:
  ```bash
  sudo journalctl -u gemini-ocr
  sudo journalctl -u gemini-frontend
  ```

- **Disable auto-start on boot**:
  ```bash
  sudo systemctl disable gemini-ocr
  sudo systemctl disable gemini-frontend
  ```

### Other Services

If you're using Nginx as a reverse proxy:

```bash
sudo systemctl start nginx
sudo systemctl stop nginx
sudo systemctl status nginx
```

If you're using PM2 for process management:

```bash
pm2 start all
pm2 stop all
pm2 status
```

## API Documentation

Once the backend is running, access the API documentation at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Database Schema

The application uses the following main tables:
- `Company`: Stores company information
- `DocumentType`: Defines different document types
- `CompanyDocumentConfig`: Links companies with document types and their processing configurations
- `ProcessingJob`: Tracks individual document processing jobs
- `BatchJob`: Manages batch processing jobs
- `File`: Stores file metadata
- `ApiUsage`: Tracks API usage statistics

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -m 'Add feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Important Reminders

1. **Never** commit real API keys or database passwords to Git
2. **Regularly rotate** API keys and passwords
3. **Use different credentials** for development, testing, and production environments
4. **Monitor** unusual API usage
5. **Backup** important configurations and data

## Developer Guide

### Configuration System Architecture

The configuration system is built around the `config_loader.py` module, which provides a centralized way to manage application settings:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Environment    │     │  AWS Secrets    │     │  Local .env &   │
│   Variables     │────▶│    Manager      │────▶│   config.json   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                      │                       │
         │                      │                       │
         ▼                      ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                       config_loader.py                          │
└─────────────────────────────────────────────────────────────────┘
         │                      │                       │
         ▼                      ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    database.py  │     │     app.py      │     │     main.py     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Extending the Configuration System

To add new configuration parameters:

1. Add the parameter to your `.env` file
2. Update the `config_loader.py` to include the new parameter
3. Access the parameter through the configuration object

Example:
```python
# In config_loader.py
def load_config():
    config = {}
    # ... existing code ...
    
    # Add your new parameter
    config['new_parameter'] = os.getenv('NEW_PARAMETER', 'default_value')
    
    return config

# In your application code
from config_loader import get_config
config = get_config()
new_parameter_value = config['new_parameter']
```

### Best Practices for Developers

1. **Never hardcode sensitive information** - Always use the configuration system
2. **Use environment-specific settings** - Different values for development, testing, and production
3. **Validate configuration** - Check that required values are present and valid
4. **Handle failures gracefully** - Provide meaningful error messages when configuration is missing
5. **Document configuration changes** - Update `.env.example` when adding new parameters
6. **Use type conversion** - Convert string environment variables to appropriate types
7. **Test with different configurations** - Ensure your code works with various settings

### Example: Adding a New API Integration

```python
# 1. Add to .env
# NEW_API_KEY=your_api_key
# NEW_API_URL=https://api.example.com

# 2. Update config_loader.py
def load_config():
    config = {}
    # ... existing code ...
    
    # New API configuration
    config['new_api'] = {
        'key': os.getenv('NEW_API_KEY'),
        'url': os.getenv('NEW_API_URL', 'https://api.example.com'),
        'timeout': int(os.getenv('NEW_API_TIMEOUT', '30'))
    }
    
    return config

# 3. Use in your code
from config_loader import get_config

def call_new_api():
    config = get_config()
    api_config = config['new_api']
    
    # Use the configuration
    headers = {'Authorization': f'Bearer {api_config["key"]}'}
    response = requests.get(api_config['url'], headers=headers, timeout=api_config['timeout'])
    return response.json()
```