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
  company_name: string;
  doc_type_id: number;
  type_name: string;
  status: 'pending' | 'processing' | 'success' | 'complete' | 'error';
  original_filename: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  files?: FileInfo[]; // Updated to use FileInfo
}

// Base API URL
const API_BASE_URL = 'http://localhost:8000';

// Generic fetch function with error handling
async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, options);
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `API error: ${response.status}`);
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
  const socket = new WebSocket(`ws://localhost:8000/ws/${jobId}`);
  
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