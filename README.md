A comprehensive document processing platform built with FastAPI (backend) and Next.js (frontend) that leverages Google's Gemini AI for OCR and data extraction.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Requirements](#system-requirements)
- [Project Structure](#project-structure)
- [Installation](#installation)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Development](#development)
  - [Running the Backend](#running-the-backend)
  - [Running the Frontend](#running-the-frontend)
  - [Common Issues](#common-issues)
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

## System Requirements

- **Backend**:
  - Python 3.9+
  - PostgreSQL 13+
  - Google Gemini API key
  
- **Frontend**:
  - Node.js 18+
  - npm 9+

## Project Structure

```
GeminiOCR/
├── backend/
│   ├── app.py              # FastAPI application
│   ├── main.py             # OCR processing logic
│   ├── db/
│   │   ├── database.py     # Database connection
│   │   └── models.py       # SQLAlchemy models
│   └── utils/              # Utility functions
│       └── excel_converter.py
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
   - Create an `env` directory with a `config.json` file containing your Google Gemini API key and other settings

### Frontend Setup

1. Install dependencies:
   ```bash
   cd ../frontend
   npm install
   ```

2. Configure environment variables:
   - Create a `.env.local` file with the backend API URL

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






Old Version :
backend
cd GeminiOCR/backend     
uvicorn app:app --reload
or 
uvicorn app:app --host 0.0.0.0 --port 8000

frontend
cd GeminiOCR/frontend  
npm run dev


sudo systemctl restart gemini-ocr
npm run build
sudo systemctl restart gemini-frontend

To stop your backend and frontend services running on your EC2 instance, you can use the following commands:

### Stop the Backend (FastAPI)
If you're using systemd (which you are based on your previous setup):


```bash
sudo systemctl stop gemini-ocr
```

To verify it's stopped:
```bash
sudo systemctl status gemini-ocr
```

### Stop the Frontend (Next.js)
If you're using systemd:

```bash
sudo systemctl stop gemini-frontend
```

To verify it's stopped:
```bash
sudo systemctl status gemini-frontend
```

### Other Cleanup (Optional)

1. If you want to stop Nginx as well:
```bash
sudo systemctl stop nginx
```

2. If you used PM2 for any part of your setup:
```bash
pm2 stop all
```

### Disable Auto-start on Boot (Optional)

If you also want to prevent the services from starting automatically when the EC2 instance reboots:

```bash
sudo systemctl disable gemini-ocr
sudo systemctl disable gemini-frontend
sudo systemctl disable nginx  # if you want to disable Nginx too
```

These commands will gracefully shut down your services. You can always start them again later using the corresponding `start` commands:

```bash
sudo systemctl start gemini-ocr
sudo systemctl start gemini-frontend
sudo systemctl start nginx
```
