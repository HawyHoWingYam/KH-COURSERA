'use client';

import { useState, useEffect } from 'react';
import { DocumentType } from '@/lib/api';
import SmartDeleteDialog from '@/components/ui/SmartDeleteDialog';
// Get base URL and port from config
const API_BASE_URL = '/api';

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
  
  // Load document types on mount
  useEffect(() => {
    const loadDocumentTypes = async () => {
      try {
        setIsLoading(true);
        const data = await fetchDocumentTypes();
        setDocumentTypes(data);
      } catch (err) {
        setError('Failed to load document types');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };
    
    loadDocumentTypes();
  }, []);
  
  // Handle form input changes
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
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
  };
  
  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      if (editingDocType) {
        // Update existing document type
        const updated = await updateDocumentType(editingDocType.doc_type_id, formData);
        setDocumentTypes(prev => 
          prev.map(dt => dt.doc_type_id === editingDocType.doc_type_id ? updated : dt)
        );
        setEditingDocType(null);
      } else {
        // Create new document type
        const created = await createDocumentType(formData);
        setDocumentTypes(prev => [...prev, created]);
        setIsCreating(false);
      }
      
      // Reset form
      setFormData({
        type_name: '',
        type_code: '',
        description: ''
      });
    } catch (err) {
      setError(`Failed to ${editingDocType ? 'update' : 'create'} document type`);
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
  };

  // Close delete dialog
  const handleDeleteCancel = () => {
    setDeleteDialog({
      isOpen: false,
      entity: null,
    });
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