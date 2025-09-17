'use client';

import { useState, useEffect } from 'react';
import { dependencyApi, DependencyInfo, DocumentType, Company } from '@/lib/api';

interface SmartDeleteDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  entity: {
    type: 'company' | 'document-type' | 'config';
    id: number;
    name: string;
  };
}

export default function SmartDeleteDialog({ 
  isOpen, 
  onClose, 
  onSuccess, 
  entity
}: SmartDeleteDialogProps) {
  const [isLoading, setIsLoading] = useState(false);
  const [dependencies, setDependencies] = useState<DependencyInfo | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState('');
  const [showConfirmation, setShowConfirmation] = useState(false);

  // Check dependencies when dialog opens
  useEffect(() => {
    if (isOpen && entity) {
      checkDependencies();
    }
  }, [isOpen, entity]);

  const checkDependencies = async () => {
    setIsLoading(true);
    setError('');
    try {
      let deps: DependencyInfo;
      if (entity.type === 'company') {
        deps = await dependencyApi.getCompanyDependencies(entity.id);
      } else if (entity.type === 'document-type') {
        deps = await dependencyApi.getDocumentTypeDependencies(entity.id);
      } else if (entity.type === 'config') {
        deps = await dependencyApi.getConfigDependencies(entity.id);
      } else {
        throw new Error('Unknown entity type');
      }
      setDependencies(deps);
    } catch (err) {
      setError('Failed to check dependencies');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleForceDelete = async () => {
    setIsDeleting(true);
    setError('');
    try {
      let endpoint;
      if (entity.type === 'company') {
        endpoint = `/api/companies/${entity.id}/force-delete`;
      } else if (entity.type === 'document-type') {
        endpoint = `/api/document-types/${entity.id}/force-delete`;
      } else if (entity.type === 'config') {
        endpoint = `/api/configs/${entity.id}/force-delete`;
      } else {
        throw new Error('Unknown entity type');
      }

      const response = await fetch(endpoint, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Force delete failed');
      }

      const result = await response.json();
      console.log('Force delete result:', result);
      
      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    } finally {
      setIsDeleting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-gray-900">
              Delete {entity.type === 'company' ? 'Company' : entity.type === 'document-type' ? 'Document Type' : 'Configuration'}
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
              disabled={isDeleting}
            >
              ✕
            </button>
          </div>

          {error && (
            <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
              {error}
            </div>
          )}

          {isLoading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
              <p className="mt-2 text-gray-600">Checking dependencies...</p>
            </div>
          ) : dependencies ? (
            <div>
              <div className="mb-4">
                <p className="text-gray-700">
                  You are about to delete <strong>{entity.name}</strong>
                </p>
              </div>

              {dependencies.can_delete ? (
                // No dependencies - simple confirmation
                <div>
                  <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4">
                    ✅ This {entity.type === 'company' ? 'company' : entity.type === 'document-type' ? 'document type' : 'configuration'} has no dependencies and can be safely deleted.
                  </div>
                  <div className="flex justify-end space-x-4">
                    <button
                      onClick={onClose}
                      className="px-4 py-2 text-gray-600 hover:text-gray-800"
                      disabled={isDeleting}
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleForceDelete}
                      className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                      disabled={isDeleting}
                    >
                      {isDeleting ? 'Deleting...' : 'Delete'}
                    </button>
                  </div>
                </div>
              ) : (
                // Has dependencies - show force delete warning
                <div>
                  <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
                    ⚠️ <strong>DANGER: Force Delete Operation</strong>
                    <br />
                    This will permanently delete this {entity.type === 'company' ? 'company' : entity.type === 'document-type' ? 'document type' : 'configuration'} and all {dependencies.total_dependencies} related records.
                  </div>

                  {/* Dependency Details */}
                  <div className="mb-4">
                    <h3 className="font-medium text-gray-900 mb-2">The following will be permanently deleted:</h3>
                    <div className="bg-gray-50 rounded p-3 space-y-2">
                      {dependencies.dependencies.processing_jobs > 0 && (
                        <div className="flex justify-between">
                          <span className="text-gray-700">• Processing Jobs:</span>
                          <span className="font-medium text-red-600">{dependencies.dependencies.processing_jobs}</span>
                        </div>
                      )}
                      {dependencies.dependencies.batch_jobs > 0 && (
                        <div className="flex justify-between">
                          <span className="text-gray-700">• Batch Jobs:</span>
                          <span className="font-medium text-red-600">{dependencies.dependencies.batch_jobs}</span>
                        </div>
                      )}
                      {dependencies.dependencies.company_configs > 0 && (
                        <div className="flex justify-between">
                          <span className="text-gray-700">• Configurations:</span>
                          <span className="font-medium text-red-600">{dependencies.dependencies.company_configs}</span>
                        </div>
                      )}
                      {dependencies.dependencies.s3_files > 0 && (
                        <div className="flex justify-between">
                          <span className="text-gray-700">• S3 Files:</span>
                          <span className="font-medium text-red-600">{dependencies.dependencies.s3_files}</span>
                        </div>
                      )}
                      {dependencies.dependencies.department_access && dependencies.dependencies.department_access > 0 && (
                        <div className="flex justify-between">
                          <span className="text-gray-700">• Department Access:</span>
                          <span className="font-medium text-red-600">{dependencies.dependencies.department_access}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Warning Message */}
                  <div className="bg-red-50 border-l-4 border-red-400 p-4 mb-4">
                    <div className="flex">
                      <div className="flex-shrink-0">
                        <span className="text-red-400 text-xl">⚠️</span>
                      </div>
                      <div className="ml-3">
                        <p className="text-sm text-red-700">
                          <strong>This action cannot be undone!</strong>
                          <br />
                          All data will be permanently deleted from the database and cannot be recovered.
                        </p>
                      </div>
                    </div>
                  </div>

                  {!showConfirmation ? (
                    <div className="flex justify-end space-x-4">
                      <button
                        onClick={onClose}
                        className="px-4 py-2 text-gray-600 hover:text-gray-800"
                        disabled={isDeleting}
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => setShowConfirmation(true)}
                        className="px-4 py-2 bg-orange-600 text-white rounded hover:bg-orange-700"
                        disabled={isDeleting}
                      >
                        I Understand the Risk
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="p-4 bg-red-50 rounded border">
                        <p className="text-red-800 font-medium mb-2">
                          Final Confirmation Required
                        </p>
                        <p className="text-red-700 text-sm">
                          Type <strong>DELETE</strong> to confirm you want to permanently delete "{entity.name}" and all its dependencies:
                        </p>
                        <input
                          type="text"
                          placeholder="Type DELETE to confirm"
                          className="mt-2 w-full px-3 py-2 border border-red-300 rounded focus:outline-none focus:ring-2 focus:ring-red-500"
                          onChange={(e) => {
                            // Enable delete button only if user types "DELETE"
                            const deleteButton = document.getElementById('final-delete-button') as HTMLButtonElement;
                            if (deleteButton) {
                              deleteButton.disabled = e.target.value !== 'DELETE' || isDeleting;
                            }
                          }}
                        />
                      </div>
                      
                      <div className="flex justify-end space-x-4">
                        <button
                          onClick={() => setShowConfirmation(false)}
                          className="px-4 py-2 text-gray-600 hover:text-gray-800"
                          disabled={isDeleting}
                        >
                          Back
                        </button>
                        <button
                          id="final-delete-button"
                          onClick={handleForceDelete}
                          disabled={true} // Initially disabled, enabled by typing "DELETE"
                          className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {isDeleting ? 'Force Deleting...' : 'Force Delete Everything'}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}