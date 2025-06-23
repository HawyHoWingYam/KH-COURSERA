// API client for interacting with the backend

export interface Company {
  company_id: number;
  company_name: string;
  company_code: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DocumentType {
  doc_type_id: number;
  type_name: string;
  type_code: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface Config {
  config_id: number;
  company_id: number;
  company_name: string;
  doc_type_id: number;
  type_name: string;
  prompt_path: string;
  schema_path: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

// Renamed from File to FileInfo to avoid conflict with the browser's File type
export interface FileInfo {
  file_id: number;
  file_name: string;
  file_path: string;
  file_category: string;
  file_size: number;
  file_type: string;
  created_at: string;
}

export interface Job {
  job_id: number;
  company_id: number;
  company_name?: string;
  doc_type_id: number;
  type_name?: string;
  status: string;
  original_filename: string;
  error_message?: string;
  created_at: string;
  updated_at: string;
  files?: FileInfo[];
}

// Add this interface for batch jobs
export interface BatchJob {
  batch_id: number;
  company_id: number;
  company_name?: string;
  doc_type_id: number;
  type_name?: string;
  zip_filename: string;
  s3_zipfile_path?: string;
  original_zipfile?: string;
  total_files: number;
  processed_files: number;
  status: string;
  error_message?: string;
  json_output_path?: string;
  excel_output_path?: string;
  created_at: string;
  updated_at: string;
  uploader_user_id?: number;
  uploader_name?: string;
}

// Base API URL and port from config
const API_BASE_URL = typeof window !== 'undefined' && process.env.API_BASE_URL 
  ? `http://${process.env.API_BASE_URL}:${process.env.PORT || 8000}`
  : 'http://52.220.245.213:8000';

// Generic fetch function with error handling
export async function fetchApi<T>(url: string, options?: RequestInit): Promise<T> {
  const fullUrl = `${API_BASE_URL}${url.startsWith('/') ? url : `/${url}`}`;
  
  console.log(`Fetching from: ${fullUrl}`);
  
  const response = await fetch(fullUrl, {
    ...options,
    headers: {
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error('API error:', errorText);
    try {
      const errorJson = JSON.parse(errorText);
      throw new Error(errorJson.detail || 'API request failed');
    } catch {
      throw new Error(`API request failed: ${response.status} ${response.statusText}`);
    }
  }

  return response.json();
}

// Exposed API functions that match the existing frontend usage
export async function fetchJobStatus(jobId: number): Promise<Job> {
  return fetchApi<Job>(`/jobs/${jobId}`);
}

export async function fetchJobFiles(jobId: number): Promise<FileInfo[]> { // Updated return type
  const job = await fetchApi<Job>(`/jobs/${jobId}`);
  return job.files || [];
}

export function getFileDownloadUrl(fileId: number): string {
  return `${API_BASE_URL}/download/${fileId}`;
}

// Companies API
export const companiesApi = {
  getAll: () => fetchApi<Company[]>('/companies'),
  getById: (id: number) => fetchApi<Company>(`/companies/${id}`),
  create: (data: Omit<Company, 'company_id' | 'created_at' | 'updated_at'>) =>
    fetchApi<Company>('/companies', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  update: (id: number, data: Partial<Omit<Company, 'company_id' | 'created_at' | 'updated_at'>>) =>
    fetchApi<Company>(`/companies/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  delete: (id: number) =>
    fetchApi<{ message: string }>(`/companies/${id}`, {
      method: 'DELETE',
    }),
};

// Document Types API
export const documentTypesApi = {
  getAll: () => fetchApi<DocumentType[]>('/document-types'),
  getById: (id: number) => fetchApi<DocumentType>(`/document-types/${id}`),
  create: (data: Omit<DocumentType, 'doc_type_id' | 'created_at' | 'updated_at'>) =>
    fetchApi<DocumentType>('/document-types', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  update: (id: number, data: Partial<Omit<DocumentType, 'doc_type_id' | 'created_at' | 'updated_at'>>) =>
    fetchApi<DocumentType>(`/document-types/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  delete: (id: number) =>
    fetchApi<{ message: string }>(`/document-types/${id}`, {
      method: 'DELETE',
    }),
};

// Configurations API
export const configsApi = {
  getAll: () => fetchApi<Config[]>('/configs'),
  getById: (id: number) => fetchApi<Config>(`/configs/${id}`),
  create: (data: Omit<Config, 'config_id' | 'created_at' | 'updated_at' | 'company_name' | 'type_name'>) =>
    fetchApi<Config>('/configs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  update: (id: number, data: Partial<Omit<Config, 'config_id' | 'company_id' | 'doc_type_id' | 'created_at' | 'updated_at' | 'company_name' | 'type_name'>>) =>
    fetchApi<Config>(`/configs/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
  delete: (id: number) =>
    fetchApi<{ message: string }>(`/configs/${id}`, {
      method: 'DELETE',
    }),
};

// File upload API - Fixed parameter type to use browser's File type instead of our FileInfo
export async function uploadFile(file: globalThis.File, path: string): Promise<{ file_path: string }> {
  const formData = new FormData();
  formData.append('file', file); // This will work correctly now
  formData.append('path', path);

  return fetchApi<{ file_path: string }>('/upload', {
    method: 'POST',
    body: formData,
  });
}

// WebSocket connection
export function connectWebSocket(jobId: number, onMessage: (data: any) => void) {
  const socket = new WebSocket(`ws://${process.env.API_BASE_URL || 'localhost'}:${process.env.PORT || 8000}/ws/${jobId}`);
  socket.onopen = () => {
    console.log(`WebSocket connection established for job ${jobId}`);
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  };

  socket.onerror = (error) => {
    console.error('WebSocket error:', error);
  };

  socket.onclose = () => {
    console.log(`WebSocket connection closed for job ${jobId}`);
  };

  return {
    close: () => socket.close(),
  };
}

// Download file
export async function downloadFile(fileId: number): Promise<Blob> {
  const fileInfo = await fetchApi<{ file_path: string; file_name: string; file_type: string }>(`/files/${fileId}`);
  const response = await fetch(`${API_BASE_URL}/download/${fileId}`);

  if (!response.ok) {
    throw new Error(`Download failed: ${response.status}`);
  }

  return response.blob();
}

// Add this function to your api.ts file
export async function fetchCompaniesForDocType(docTypeId: number): Promise<Company[]> {
  // This endpoint will need to be implemented on the backend
  return fetchApi<Company[]>(`/document-types/${docTypeId}/companies`);
}

// Also make sure this function exists since it's imported in upload/page.tsx
export async function fetchDocumentTypes(): Promise<DocumentType[]> {
  return fetchApi<DocumentType[]>('/document-types');
}

// And this one for processing documents
export async function processDocument(formData: FormData): Promise<{ job_id: number; status: string; message: string }> {
  console.log('Processing document:', formData);
  
  // Make sure we're using the backend API URL
  return fetchApi<{ job_id: number; status: string; message: string }>('/process', {
    method: 'POST',
    body: formData,
    // Don't set Content-Type header - the browser will set it with the correct boundary for FormData
  });
}

// Add the fetchJobs function
export async function fetchJobs(
  params: { company_id?: number; doc_type_id?: number; status?: string; limit?: number; offset?: number } = {}
): Promise<Job[]> {
  const queryParams = new URLSearchParams();
  
  if (params.company_id) queryParams.append('company_id', params.company_id.toString());
  if (params.doc_type_id) queryParams.append('doc_type_id', params.doc_type_id.toString());
  if (params.status) queryParams.append('status', params.status);
  if (params.limit) queryParams.append('limit', params.limit.toString());
  if (params.offset) queryParams.append('offset', params.offset.toString());
  
  const queryString = queryParams.toString();
  const endpoint = `/jobs${queryString ? `?${queryString}` : ''}`;
  
  return fetchApi<Job[]>(endpoint);
}

// Add function to process ZIP files
export async function processZipFile(formData: FormData): Promise<{ batch_id: number; status: string; message: string }> {
  console.log('Processing ZIP file:', formData);
  
  // Log the form data contents for debugging
  for (const [key, value] of formData.entries()) {
    console.log(`${key}: ${value instanceof File ? value.name : value}`);
  }
  
  return fetchApi<{ batch_id: number; status: string; message: string }>('/process-zip', {
    method: 'POST',
    body: formData,
  });
}

// Add functions for batch job management
export async function fetchBatchJobStatus(batchId: number): Promise<BatchJob> {
  return fetchApi<BatchJob>(`/batch-jobs/${batchId}`);
}

export async function fetchBatchJobs(
  params: { company_id?: number; doc_type_id?: number; status?: string; limit?: number; offset?: number } = {}
): Promise<BatchJob[]> {
  const queryParams = new URLSearchParams();
  
  if (params.company_id) queryParams.append('company_id', params.company_id.toString());
  if (params.doc_type_id) queryParams.append('doc_type_id', params.doc_type_id.toString());
  if (params.status) queryParams.append('status', params.status);
  if (params.limit) queryParams.append('limit', params.limit.toString());
  if (params.offset) queryParams.append('offset', params.offset.toString());
  
  const queryString = queryParams.toString();
  const endpoint = `/batch-jobs${queryString ? `?${queryString}` : ''}`;
  
  return fetchApi<BatchJob[]>(endpoint);
} 