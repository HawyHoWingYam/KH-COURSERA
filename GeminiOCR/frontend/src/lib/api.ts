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

// Base API URL - use Next.js proxy path to avoid CORS issues
const API_BASE_URL = '/api';

// Enhanced error type for better error handling
export interface ApiError extends Error {
  status?: number;
  isDependencyError?: boolean;
  dependencyMessage?: string;
}

// Generic fetch function with enhanced error handling
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
      const errorMessage = errorJson.detail || 'API request failed';
      
      // Create enhanced error object
      const error = new Error(errorMessage) as ApiError;
      error.status = response.status;
      
      // Check if this is a dependency constraint error
      if (response.status === 400 && errorMessage.includes('Cannot delete')) {
        error.isDependencyError = true;
        error.dependencyMessage = errorMessage;
      }
      
      throw error;
    } catch (parseError) {
      if (parseError instanceof Error && 'isDependencyError' in parseError) {
        throw parseError; // Re-throw if it's already our enhanced error
      }
      
      const error = new Error(`API request failed: ${response.status} ${response.statusText}`) as ApiError;
      error.status = response.status;
      throw error;
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
export function connectWebSocket(jobId: number, onMessage: (data: unknown) => void) {
  // Derive WS base from configured HTTP API URL to avoid using the Next.js PORT (3000)
  const httpBase = (process.env.NEXT_PUBLIC_API_URL || process.env.API_BASE_URL || 'http://localhost:8000');
  const apiUrl = new URL(httpBase);
  const wsProtocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsBase = `${wsProtocol}//${apiUrl.host}`;
  const socket = new WebSocket(`${wsBase}/ws/${jobId}`);
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
  const response = await fetch(`${API_BASE_URL}/download/${fileId}`);

  if (!response.ok) {
    throw new Error(`Download failed: ${response.status}`);
  }

  return response.blob();
}

// Fetch file content for preview
export async function fetchFilePreview(fileId: number): Promise<unknown> {
  const response = await fetch(`${API_BASE_URL}/download/${fileId}`);

  if (!response.ok) {
    throw new Error(`Preview failed: ${response.status}`);
  }

  // Get the content type to determine how to parse the file
  const contentType = response.headers.get('content-type') || '';
  
  if (contentType.includes('application/json') || contentType.includes('text/plain')) {
    const text = await response.text();
    try {
      return JSON.parse(text);
    } catch {
      return text;
    }
  } else if (contentType.includes('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') || 
             contentType.includes('application/vnd.ms-excel')) {
    // For Excel files, we'll need to parse them differently
    // For now, return an indication that it's an Excel file
    const blob = await response.blob();
    return { type: 'excel', blob };
  } else {
    // For other file types, return as text
    return await response.text();
  }
}

// Dependency Management Interfaces
export interface DependencyInfo {
  exists: boolean;
  entity_name?: string;
  can_delete: boolean;
  total_dependencies: number;
  dependencies: {
    processing_jobs: number;
    batch_jobs: number;
    company_configs: number;
    department_access?: number;
  };
  blocking_message?: string;
  detailed_dependencies?: {
    processing_jobs?: Array<{
      job_id: number;
      filename: string;
      status: string;
      company_id?: number;
      created_at: string;
    }>;
    batch_jobs?: Array<{
      batch_id: number;
      status: string;
      created_at: string;
    }>;
  };
  migration_targets?: MigrationTarget[];
}

export interface MigrationTarget {
  id: number;
  name: string;
  code: string;
}

export interface MigrationResult {
  message: string;
  processing_jobs_migrated?: number;
  batch_jobs_migrated?: number;
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
// DEPRECATED - use processBatch instead
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

// Add function to process ZIP files (DEPRECATED - use processBatch instead)
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

// Unified batch processing function (replaces processDocument and processZipFile)
export async function processBatch(formData: FormData): Promise<{ 
  batch_id: number; 
  status: string; 
  message: string; 
  upload_type: string;
  file_count: number;
}> {
  console.log('Processing unified batch:', formData);
  
  // Log the form data contents for debugging
  for (const [key, value] of formData.entries()) {
    console.log(`${key}: ${value instanceof File ? `${value.name} (${value.size} bytes)` : value}`);
  }
  
  return fetchApi<{ 
    batch_id: number; 
    status: string; 
    message: string; 
    upload_type: string;
    file_count: number;
  }>('/process-batch', {
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

// Dependency Management API
export const dependencyApi = {
  // Get company dependencies
  getCompanyDependencies: (companyId: number): Promise<DependencyInfo> =>
    fetchApi<DependencyInfo>(`/companies/${companyId}/dependencies`),
  
  // Get document type dependencies
  getDocumentTypeDependencies: (docTypeId: number): Promise<DependencyInfo> =>
    fetchApi<DependencyInfo>(`/document-types/${docTypeId}/dependencies`),
  
  // Get configuration dependencies
  getConfigDependencies: (configId: number): Promise<DependencyInfo> =>
    fetchApi<DependencyInfo>(`/configs/${configId}/dependencies`),
};

// Force Delete API - Deletes entities and all their dependencies
export const forceDeleteApi = {
  // Force delete company and all its dependencies
  deleteCompanyWithDependencies: (companyId: number): Promise<any> =>
    fetchApi(`/companies/${companyId}/force-delete`, {
      method: 'DELETE',
    }),
  
  // Force delete document type and all its dependencies  
  deleteDocumentTypeWithDependencies: (docTypeId: number): Promise<any> =>
    fetchApi(`/document-types/${docTypeId}/force-delete`, {
      method: 'DELETE',
    }),
  
  // Force delete configuration and its related files
  deleteConfigWithDependencies: (configId: number): Promise<any> =>
    fetchApi(`/configs/${configId}/force-delete`, {
      method: 'DELETE',
    }),
};
