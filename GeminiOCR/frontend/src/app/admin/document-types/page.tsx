'use client';

import { useState, useEffect, useCallback } from 'react';
import type { ChangeEvent, FormEvent } from 'react';
import { DocumentType } from '@/lib/api';
import SmartDeleteDialog from '@/components/ui/SmartDeleteDialog';
// Get base URL and port from config
const API_BASE_URL = '/api';

const extractTemplateVersion = (templatePath?: string | null): string | null => {
  if (!templatePath) return null;
  const match = templatePath.match(/template_v([^/]+?)\.json$/i);
  return match ? match[1] : null;
};

const validateTemplateStructure = (payload: unknown): void => {
  if (typeof payload !== 'object' || payload === null) {
    throw new Error('Template must be a JSON object');
  }

  const template = payload as Record<string, unknown>;
  const columnOrder = template.column_order;
  const columnDefinitions = template.column_definitions as Record<string, any> | null;

  if (!Array.isArray(columnOrder) || columnOrder.length === 0) {
    throw new Error('Template must include a non-empty column_order array');
  }

  if (!columnDefinitions || typeof columnDefinitions !== 'object') {
    throw new Error('Template must include column_definitions');
  }

  const allowedTypes = new Set(['source', 'computed', 'constant']);

  for (const columnName of columnOrder) {
    if (typeof columnName !== 'string' || !columnName.trim()) {
      throw new Error('column_order values must be non-empty strings');
    }

    const definition = columnDefinitions[columnName];
    if (!definition) {
      throw new Error(`Missing column definition for ${columnName}`);
    }

    if (!allowedTypes.has(definition.type)) {
      throw new Error(`Unsupported column type for ${columnName}`);
    }

    if (definition.type === 'source' && !definition.source_column) {
      throw new Error(`Source column ${columnName} is missing source_column`);
    }

    if (definition.type === 'computed' && !definition.expression) {
      throw new Error(`Computed column ${columnName} is missing expression`);
    }

    if (definition.type === 'constant' && typeof definition.value === 'undefined') {
      throw new Error(`Constant column ${columnName} is missing value`);
    }
  }
};

// Extended API methods for admin functions
async function fetchDocumentTypes(): Promise<DocumentType[]> {
  const res = await fetch(`${API_BASE_URL}/document-types`);
  if (!res.ok) throw new Error('Failed to fetch document types');
  return res.json();
}

async function createDocumentType(data: { type_name: string; type_code: string; description?: string }): Promise<DocumentType> {
  const res = await fetch(`${API_BASE_URL}/document-types`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create document type');
  return res.json();
}

async function updateDocumentType(id: number, data: { type_name: string; type_code: string; description?: string }): Promise<DocumentType> {
  const res = await fetch(`${API_BASE_URL}/document-types/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update document type');
  return res.json();
}

async function deleteDocumentType(id: number): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/document-types/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete document type');
}

export default function DocumentTypesPage() {
  const [documentTypes, setDocumentTypes] = useState<DocumentType[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [infoMessage, setInfoMessage] = useState('');

  const [isCreating, setIsCreating] = useState(false);
  const [editingDocType, setEditingDocType] = useState<DocumentType | null>(null);

  // Smart delete dialog state
  const [deleteDialog, setDeleteDialog] = useState<{
    isOpen: boolean;
    entity: { type: 'document-type'; id: number; name: string } | null;
  }>({
    isOpen: false,
    entity: null,
  });
  
  const [formData, setFormData] = useState({
    type_name: '',
    type_code: '',
    description: ''
  });

  const [templateFile, setTemplateFile] = useState<File | null>(null);
  const [templateError, setTemplateError] = useState('');
  const [isUploadingTemplate, setIsUploadingTemplate] = useState(false);
  const [isDeletingTemplate, setIsDeletingTemplate] = useState(false);
  const [isDownloadingTemplate, setIsDownloadingTemplate] = useState(false);
  
  const loadDocumentTypes = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await fetchDocumentTypes();
      setDocumentTypes(data);
      setError('');
    } catch (err) {
      setError('Failed to load document types');
      setInfoMessage('');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Load document types on mount
  useEffect(() => {
    loadDocumentTypes();
  }, [loadDocumentTypes]);
  
  // Handle form input changes
  const handleInputChange = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };
  
  // Start editing a document type
  const handleEdit = (docType: DocumentType) => {
    setEditingDocType(docType);
    setFormData({
      type_name: docType.type_name,
      type_code: docType.type_code,
      description: docType.description || ''
    });
    setIsCreating(false);
    setTemplateFile(null);
    setTemplateError('');
    setInfoMessage('');
  };
  
  // Handle form submission
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    
    try {
      if (editingDocType) {
        // Update existing document type
        const updated = await updateDocumentType(editingDocType.doc_type_id, formData);
        setDocumentTypes(prev => 
          prev.map(dt => dt.doc_type_id === editingDocType.doc_type_id ? updated : dt)
        );
        setEditingDocType(null);
        setInfoMessage('Document type updated successfully');
      } else {
        // Create new document type
        const created = await createDocumentType(formData);
        setDocumentTypes(prev => [...prev, created]);
        setIsCreating(false);
        setInfoMessage('Document type created successfully');
      }
      
      // Reset form
      setFormData({
        type_name: '',
        type_code: '',
        description: ''
      });
      setError('');
    } catch (err) {
      setError(`Failed to ${editingDocType ? 'update' : 'create'} document type`);
      setInfoMessage('');
      console.error(err);
    }
  };
  
  // Handle document type deletion - now uses smart delete dialog
  const handleDelete = (docType: DocumentType) => {
    setDeleteDialog({
      isOpen: true,
      entity: {
        type: 'document-type',
        id: docType.doc_type_id,
        name: docType.type_name,
      },
    });
  };

  // Handle successful deletion
  const handleDeleteSuccess = () => {
    setDocumentTypes(prev => 
      prev.filter(dt => dt.doc_type_id !== deleteDialog.entity?.id)
    );
    setError(''); // Clear any previous errors
    setInfoMessage('Document type deleted successfully');

    if (editingDocType && editingDocType.doc_type_id === deleteDialog.entity?.id) {
      handleCancel();
    }
  };

  // Close delete dialog
  const handleDeleteCancel = () => {
    setDeleteDialog({
      isOpen: false,
      entity: null,
    });
  };

  const handleTemplateFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    setTemplateError('');
    setInfoMessage('');
    setTemplateFile(event.target.files?.[0] ?? null);
  };

  const handleTemplateUpload = async () => {
    if (!editingDocType) {
      setTemplateError('Select a document type to manage its template');
      return;
    }

    if (!templateFile) {
      setTemplateError('Choose a template JSON file before uploading');
      return;
    }

    setTemplateError('');
    setError('');
    setInfoMessage('');
    setIsUploadingTemplate(true);

    try {
      const fileText = await templateFile.text();
      let parsedJson: unknown;
      try {
        parsedJson = JSON.parse(fileText);
      } catch (jsonError) {
        throw new Error('Template file is not valid JSON');
      }

      validateTemplateStructure(parsedJson);

      const formData = new FormData();
      formData.append('template_file', templateFile);

      const response = await fetch(`${API_BASE_URL}/document-types/${editingDocType.doc_type_id}/template`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => ({}));
        throw new Error(errorPayload.detail || 'Failed to upload template');
      }

      const payload = await response.json();
      const templatePath: string | undefined = payload.template_path;
      const derivedVersion = extractTemplateVersion(templatePath) || (parsedJson as any)?.version || null;

      setDocumentTypes(prev =>
        prev.map(dt =>
          dt.doc_type_id === editingDocType.doc_type_id
            ? {
                ...dt,
                template_json_path: templatePath ?? null,
                template_version: derivedVersion,
                has_template: Boolean(templatePath),
              }
            : dt
        )
      );

      setEditingDocType(prev =>
        prev
          ? {
              ...prev,
              template_json_path: templatePath ?? null,
              template_version: derivedVersion,
              has_template: Boolean(templatePath),
            }
          : prev
      );

      setTemplateFile(null);
      setInfoMessage('Template uploaded successfully');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to upload template';
      setTemplateError(message);
    } finally {
      setIsUploadingTemplate(false);
    }
  };

  const downloadTemplate = async () => {
    if (!editingDocType) {
      setTemplateError('Select a document type to download its template');
      return;
    }

    setTemplateError('');
    setError('');
    setInfoMessage('');
    setIsDownloadingTemplate(true);

    try {
      const response = await fetch(`${API_BASE_URL}/document-types/${editingDocType.doc_type_id}/template`);

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => ({}));
        throw new Error(errorPayload.detail || 'Failed to download template');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      const fallbackName = `doc_type_${editingDocType.doc_type_id}_template.json`;
      const fileName = editingDocType.template_json_path?.split('/').pop() || fallbackName;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      setInfoMessage('Template downloaded');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to download template';
      setTemplateError(message);
    } finally {
      setIsDownloadingTemplate(false);
    }
  };

  const deleteTemplate = async () => {
    if (!editingDocType) {
      setTemplateError('Select a document type to delete its template');
      return;
    }

    if (!editingDocType.has_template) {
      setTemplateError('This document type does not have a template to delete');
      return;
    }

    const confirmed = window.confirm('Remove the template from this document type?');
    if (!confirmed) {
      return;
    }

    setTemplateError('');
    setError('');
    setInfoMessage('');
    setIsDeletingTemplate(true);

    try {
      const response = await fetch(`${API_BASE_URL}/document-types/${editingDocType.doc_type_id}/template`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => ({}));
        throw new Error(errorPayload.detail || 'Failed to delete template');
      }

      setDocumentTypes(prev =>
        prev.map(dt =>
          dt.doc_type_id === editingDocType.doc_type_id
            ? {
                ...dt,
                template_json_path: null,
                template_version: null,
                has_template: false,
              }
            : dt
        )
      );

      setEditingDocType(prev =>
        prev
          ? {
              ...prev,
              template_json_path: null,
              template_version: null,
              has_template: false,
            }
          : prev
      );

      setTemplateFile(null);
      setInfoMessage('Template deleted successfully');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete template';
      setTemplateError(message);
    } finally {
      setIsDeletingTemplate(false);
    }
  };
  
  // Cancel editing/creating
  const handleCancel = () => {
    setIsCreating(false);
    setEditingDocType(null);
    setFormData({
      type_name: '',
      type_code: '',
      description: ''
    });
    setTemplateFile(null);
    setTemplateError('');
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Document Type Management</h1>
        {!isCreating && !editingDocType && (
          <button 
            onClick={() => setIsCreating(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            Add New Document Type
          </button>
        )}
      </div>
      
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {infoMessage && (
        <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4">
          {infoMessage}
        </div>
      )}
      
      {/* Create/Edit Form */}
      {(isCreating || editingDocType) && (
        <div className="bg-white shadow-md rounded-lg p-6 mb-6">
          <h2 className="text-lg font-medium mb-4 text-black">
            {editingDocType ? 'Edit Document Type' : 'Create New Document Type'}
          </h2>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-gray-700 mb-2">Type Name</label>
              <input
                type="text"
                name="type_name"
                value={formData.type_name}
                onChange={handleInputChange}
                className="w-full border border-gray-300 rounded px-3 py-2 text-black"
                required
              />
            </div>
            
            <div>
              <label className="block text-gray-700 mb-2">Type Code</label>
              <input
                type="text"
                name="type_code"
                value={formData.type_code}
                onChange={handleInputChange}
                className="w-full border border-gray-300 rounded px-3 py-2 text-black"
                required
              />
            </div>
            
            <div>
              <label className="block text-gray-700 mb-2">Description</label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleInputChange}
                className="w-full border border-gray-300 rounded px-3 py-2 text-black"
                rows={3}
              />
            </div>

            {editingDocType ? (
              <div className="border-t border-gray-200 pt-4 mt-6">
                <h3 className="text-md font-semibold text-gray-800 mb-2">Template Management</h3>
                <p className="text-sm text-gray-600 mb-3">
                  Upload a template.json to control special CSV generation, column ordering, and computed fields.
                </p>

                <div className="flex flex-wrap items-center gap-2 mb-3">
                  <span
                    className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${
                      editingDocType.has_template
                        ? 'bg-green-100 text-green-800'
                        : 'bg-gray-100 text-gray-600'
                    }`}
                  >
                    {editingDocType.has_template
                      ? `Template uploaded${editingDocType.template_version ? ` (v${editingDocType.template_version})` : ''}`
                      : 'No template uploaded'}
                  </span>
                  {editingDocType.template_json_path && (
                    <span className="text-xs text-gray-500 break-all">
                      {editingDocType.template_json_path}
                    </span>
                  )}
                </div>

                <div className="space-y-3">
                  <div>
                    <label className="block text-gray-700 mb-2">Upload JSON Template</label>
                    <input
                      type="file"
                      accept=".json"
                      onChange={handleTemplateFileChange}
                      className="w-full border border-dashed border-gray-300 rounded px-3 py-2 text-black"
                    />
                    {templateFile && (
                      <p className="text-xs text-gray-500 mt-1">Selected file: {templateFile.name}</p>
                    )}
                  </div>

                  {templateError && (
                    <div className="bg-red-100 border border-red-400 text-red-700 px-3 py-2 rounded text-sm">
                      {templateError}
                    </div>
                  )}

                  <div className="flex flex-wrap gap-3">
                    <button
                      type="button"
                      onClick={handleTemplateUpload}
                      disabled={isUploadingTemplate}
                      className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 text-white px-4 py-2 rounded"
                    >
                      {isUploadingTemplate ? 'Uploading…' : 'Upload Template'}
                    </button>
                    <button
                      type="button"
                      onClick={downloadTemplate}
                      disabled={!editingDocType.has_template || isDownloadingTemplate}
                      className="bg-blue-500 hover:bg-blue-600 disabled:bg-gray-400 text-white px-4 py-2 rounded"
                    >
                      {isDownloadingTemplate ? 'Downloading…' : 'Download Template'}
                    </button>
                    <button
                      type="button"
                      onClick={deleteTemplate}
                      disabled={!editingDocType.has_template || isDeletingTemplate}
                      className="bg-red-500 hover:bg-red-600 disabled:bg-gray-400 text-white px-4 py-2 rounded"
                    >
                      {isDeletingTemplate ? 'Deleting…' : 'Delete Template'}
                    </button>
                  </div>

                  <a
                    href="/docs/template-format"
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-blue-600 hover:underline"
                  >
                    View template format guide
                  </a>
                </div>
              </div>
            ) : (
              <div className="border border-dashed border-gray-300 rounded p-4 text-sm text-gray-600 mt-6">
                Save the document type before uploading a template.json definition.
              </div>
            )}
            
            <div className="flex space-x-4">
              <button
                type="submit"
                className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
              >
                {editingDocType ? 'Update' : 'Create'}
              </button>
              <button
                type="button"
                onClick={handleCancel}
                className="bg-gray-300 text-gray-800 px-4 py-2 rounded hover:bg-gray-400"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}
      
      {/* Document Types List */}
      {isLoading ? (
        <div className="text-center py-10">Loading document types...</div>
      ) : documentTypes.length === 0 ? (
        <div className="text-center py-10">
          <p className="text-gray-500">No document types found</p>
        </div>
      ) : (
        <div className="bg-white shadow-md rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Code
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Description
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Template
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {documentTypes.map((docType) => (
                <tr key={docType.doc_type_id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {docType.doc_type_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {docType.type_name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {docType.type_code}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">
                    {docType.description || '-'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm">
                    <span
                      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${
                        docType.has_template
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-600'
                      }`}
                    >
                      {docType.has_template
                        ? `Uploaded${docType.template_version ? ` (v${docType.template_version})` : ''}`
                        : 'Not uploaded'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      onClick={() => handleEdit(docType)}
                      className="text-indigo-600 hover:text-indigo-900 mr-4"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(docType)}
                      className="text-red-600 hover:text-red-900"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Smart Delete Dialog */}
      <SmartDeleteDialog
        isOpen={deleteDialog.isOpen}
        onClose={handleDeleteCancel}
        onSuccess={handleDeleteSuccess}
        entity={deleteDialog.entity!}
      />
    </div>
  );
} 
