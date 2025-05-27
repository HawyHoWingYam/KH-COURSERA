// API client for backend

export interface DocumentType {
  doc_type_id: number;
  type_name: string;
  type_code: string;
  description?: string;
}

export interface Company {
  company_id: number;
  company_name: string;
  company_code: string;
  active: boolean;
}

export interface Job {
  job_id: number;
  original_filename: string;
  status: string;
  error_message?: string;
  created_at: string;
  company_id: number;
  doc_type_id: number;
}

export interface File {
  file_id: number;
  file_name: string;
  file_path: string;
  file_type: string;
  file_size: number;
  mime_type?: string;
  uploaded_at: string;
}

// API base URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

// Fetch document types
export async function fetchDocumentTypes(): Promise<DocumentType[]> {
  const res = await fetch(`${API_BASE_URL}/document-types`);
  if (!res.ok) {
    throw new Error('Failed to fetch document types');
  }
  return res.json();
}

// Fetch companies for a document type
export async function fetchCompaniesForDocType(docTypeId: number): Promise<Company[]> {
  const res = await fetch(`${API_BASE_URL}/document-types/${docTypeId}/companies`);
  if (!res.ok) {
    throw new Error(`Failed to fetch companies for document type ${docTypeId}`);
  }
  return res.json();
}

// Fetch job status
export async function fetchJobStatus(jobId: number): Promise<Job> {
  const res = await fetch(`${API_BASE_URL}/jobs/${jobId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch job ${jobId}`);
  }
  return res.json();
}

// Fetch files for a job
export async function fetchJobFiles(jobId: number): Promise<File[]> {
  const res = await fetch(`${API_BASE_URL}/jobs/${jobId}/files`);
  if (!res.ok) {
    throw new Error(`Failed to fetch files for job ${jobId}`);
  }
  return res.json();
}

// Process a document
export async function processDocument(
  documentTypeId: number,
  companyId: number,
  file: File
): Promise<Job> {
  const formData = new FormData();
  formData.append('document_type_id', documentTypeId.toString());
  formData.append('company_id', companyId.toString());
  formData.append('file', file);

  const res = await fetch(`${API_BASE_URL}/process`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    throw new Error('Failed to process document');
  }

  return res.json();
}

// Generate file download URL
export function getFileDownloadUrl(fileId: number): string {
  return `${API_BASE_URL}/files/${fileId}`;
} 