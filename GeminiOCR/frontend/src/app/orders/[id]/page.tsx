'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';

interface Company {
  company_id: number;
  company_name: string;
}

interface DocumentType {
  doc_type_id: number;
  type_name: string;
}

interface OrderItem {
  item_id: number;
  order_id: number;
  company_id: number;
  doc_type_id: number;
  item_name: string;
  status: string;
  file_count: number;
  company_name: string;
  doc_type_name: string;
  ocr_result_json_path: string | null;
  ocr_result_csv_path: string | null;
  processing_started_at: string | null;
  processing_completed_at: string | null;
  processing_time_seconds: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

interface Order {
  order_id: number;
  order_name: string | null;
  status: string;
  total_items: number;
  completed_items: number;
  failed_items: number;
  mapping_file_path: string | null;
  mapping_keys: string[] | null;
  final_report_paths: any | null;
  error_message: string | null;
  items: OrderItem[];
  created_at: string;
  updated_at: string;
}

export default function OrderDetailsPage() {
  const router = useRouter();
  const params = useParams();
  const orderId = parseInt(params.id as string);

  const [order, setOrder] = useState<Order | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [documentTypes, setDocumentTypes] = useState<DocumentType[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // Add Item Modal State
  const [showAddItemModal, setShowAddItemModal] = useState(false);
  const [selectedCompany, setSelectedCompany] = useState<number | null>(null);
  const [selectedDocType, setSelectedDocType] = useState<number | null>(null);
  const [itemName, setItemName] = useState('');
  const [isAddingItem, setIsAddingItem] = useState(false);

  // File Upload State
  const [uploadingFiles, setUploadingFiles] = useState<{[key: number]: boolean}>({});

  // Mapping File State
  const [mappingFile, setMappingFile] = useState<File | null>(null);
  const [mappingHeaders, setMappingHeaders] = useState<{[sheet: string]: string[]} | null>(null);
  const [selectedMappingKeys, setSelectedMappingKeys] = useState<string[]>([]);
  const [isUploadingMapping, setIsUploadingMapping] = useState(false);

  useEffect(() => {
    loadOrder();
    loadCompanies();
    loadDocumentTypes();
  }, [orderId]);

  const loadOrder = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/orders/${orderId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch order');
      }
      const data = await response.json();
      setOrder(data);

      // Load mapping headers if mapping file exists
      if (data.mapping_file_path) {
        loadMappingHeaders();
      }

      setError('');
    } catch (error) {
      console.error('Error fetching order:', error);
      setError('Failed to load order');
    } finally {
      setIsLoading(false);
    }
  };

  const loadCompanies = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/companies`);
      if (!response.ok) throw new Error('Failed to fetch companies');
      const data = await response.json();
      setCompanies(data);
    } catch (error) {
      console.error('Error fetching companies:', error);
    }
  };

  const loadDocumentTypes = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/document-types`);
      if (!response.ok) throw new Error('Failed to fetch document types');
      const data = await response.json();
      setDocumentTypes(data);
    } catch (error) {
      console.error('Error fetching document types:', error);
    }
  };

  const loadMappingHeaders = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/orders/${orderId}/mapping-headers`);
      if (!response.ok) throw new Error('Failed to fetch mapping headers');
      const data = await response.json();
      setMappingHeaders(data.sheet_headers);
    } catch (error) {
      console.error('Error fetching mapping headers:', error);
    }
  };

  const addOrderItem = async () => {
    if (!selectedCompany || !selectedDocType) {
      setError('Please select both company and document type');
      return;
    }

    setIsAddingItem(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/orders/${orderId}/items`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          company_id: selectedCompany,
          doc_type_id: selectedDocType,
          item_name: itemName || undefined
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to add item');
      }

      // Reset form and close modal
      setSelectedCompany(null);
      setSelectedDocType(null);
      setItemName('');
      setShowAddItemModal(false);

      // Reload order to show new item
      loadOrder();
    } catch (error) {
      console.error('Error adding item:', error);
      setError('Failed to add item');
    } finally {
      setIsAddingItem(false);
    }
  };

  const uploadFilesToItem = async (itemId: number, files: FileList) => {
    setUploadingFiles(prev => ({ ...prev, [itemId]: true }));

    try {
      const formData = new FormData();
      Array.from(files).forEach(file => {
        formData.append('files', file);
      });

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/orders/${orderId}/items/${itemId}/files`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Failed to upload files');
      }

      // Reload order to show updated file counts
      loadOrder();
    } catch (error) {
      console.error('Error uploading files:', error);
      setError('Failed to upload files');
    } finally {
      setUploadingFiles(prev => ({ ...prev, [itemId]: false }));
    }
  };

  const uploadMappingFile = async () => {
    if (!mappingFile) return;

    setIsUploadingMapping(true);
    try {
      const formData = new FormData();
      formData.append('mapping_file', mappingFile);

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/orders/${orderId}/mapping-file`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Failed to upload mapping file');
      }

      // Load headers from uploaded file
      await loadMappingHeaders();

      // Reload order to show mapping file
      loadOrder();
    } catch (error) {
      console.error('Error uploading mapping file:', error);
      setError('Failed to upload mapping file');
    } finally {
      setIsUploadingMapping(false);
    }
  };

  const updateMappingKeys = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/orders/${orderId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          mapping_keys: selectedMappingKeys
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to update mapping keys');
      }

      loadOrder();
    } catch (error) {
      console.error('Error updating mapping keys:', error);
      setError('Failed to update mapping keys');
    }
  };

  const submitOrder = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/orders/${orderId}/submit`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to submit order');
      }

      loadOrder();
    } catch (error) {
      console.error('Error submitting order:', error);
      setError(error instanceof Error ? error.message : 'Failed to submit order');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'DRAFT':
        return 'bg-gray-100 text-gray-800';
      case 'PROCESSING':
        return 'bg-blue-100 text-blue-800';
      case 'MAPPING':
        return 'bg-yellow-100 text-yellow-800';
      case 'COMPLETED':
        return 'bg-green-100 text-green-800';
      case 'FAILED':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getItemStatusColor = (status: string) => {
    switch (status) {
      case 'PENDING':
        return 'bg-gray-100 text-gray-800';
      case 'PROCESSING':
        return 'bg-blue-100 text-blue-800';
      case 'COMPLETED':
        return 'bg-green-100 text-green-800';
      case 'FAILED':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  if (isLoading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center">Loading order details...</div>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center text-red-600">Order not found</div>
      </div>
    );
  }

  const canEdit = order.status === 'DRAFT';
  const canSubmit = order.status === 'DRAFT' && order.total_items > 0;

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <Link
            href="/orders"
            className="text-blue-600 hover:text-blue-800"
          >
            ← Back to Orders
          </Link>
          <h1 className="text-2xl font-bold">
            {order.order_name || `Order ${order.order_id}`}
          </h1>
          <span className={`px-3 py-1 text-sm font-semibold rounded-full ${getStatusColor(order.status)}`}>
            {order.status}
          </span>
        </div>
        {canSubmit && (
          <button
            onClick={submitOrder}
            className="bg-green-600 hover:bg-green-700 text-white py-2 px-6 rounded"
          >
            Submit Order
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-6">
          {error}
        </div>
      )}

      {/* Order Summary */}
      <div className="bg-white rounded-lg shadow p-6 mb-8">
        <h2 className="text-lg font-semibold mb-4">Order Summary</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <div className="text-sm text-gray-500">Total Items</div>
            <div className="text-2xl font-bold">{order.total_items}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500">Completed</div>
            <div className="text-2xl font-bold text-green-600">{order.completed_items}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500">Failed</div>
            <div className="text-2xl font-bold text-red-600">{order.failed_items}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500">Progress</div>
            <div className="text-2xl font-bold">
              {order.total_items > 0 ? Math.round((order.completed_items / order.total_items) * 100) : 0}%
            </div>
          </div>
        </div>
      </div>

      {/* Order Items Section */}
      <div className="bg-white rounded-lg shadow p-6 mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Order Items</h2>
          {canEdit && (
            <button
              onClick={() => setShowAddItemModal(true)}
              className="bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded"
            >
              Add Item
            </button>
          )}
        </div>

        {order.items.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No items added yet. Click "Add Item" to get started.
          </div>
        ) : (
          <div className="space-y-4">
            {order.items.map((item) => (
              <div key={item.item_id} className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-4">
                    <h3 className="font-medium">{item.item_name}</h3>
                    <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getItemStatusColor(item.status)}`}>
                      {item.status}
                    </span>
                  </div>
                  <div className="text-sm text-gray-500">
                    {item.files && item.files.length > 0 ? (
                      <div>
                        <div className="font-medium">Files ({item.files.length}):</div>
                        <div className="text-xs text-gray-600 space-y-1 mt-1">
                          {item.files.slice(0, 3).map((file: any) => (
                            <div key={file.file_id} className="truncate">
                              📄 {file.filename} ({(file.file_size / 1024).toFixed(1)}KB)
                            </div>
                          ))}
                          {item.files.length > 3 && (
                            <div className="text-gray-400">
                              ... and {item.files.length - 3} more files
                            </div>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div>Files: 0</div>
                    )}
                  </div>
                </div>
                <div className="text-sm text-gray-600 mb-3">
                  {item.company_name} - {item.doc_type_name}
                </div>

                {canEdit && (
                  <div className="flex items-center gap-4">
                    <label className="cursor-pointer bg-gray-100 hover:bg-gray-200 text-gray-700 py-2 px-4 rounded border">
                      {uploadingFiles[item.item_id] ? 'Uploading...' : 'Upload Files'}
                      <input
                        type="file"
                        multiple
                        accept=".pdf,.jpg,.jpeg,.png"
                        className="hidden"
                        disabled={uploadingFiles[item.item_id]}
                        onChange={(e) => {
                          if (e.target.files && e.target.files.length > 0) {
                            uploadFilesToItem(item.item_id, e.target.files);
                          }
                        }}
                      />
                    </label>
                    <span className="text-sm text-gray-500">
                      Supported: PDF, JPG, PNG
                    </span>
                  </div>
                )}

                {item.error_message && (
                  <div className="mt-2 text-sm text-red-600">
                    Error: {item.error_message}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Mapping Configuration Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold mb-4">Mapping Configuration</h2>

        {canEdit && (
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Upload Mapping File (Excel)
            </label>
            <div className="flex items-center gap-4">
              <input
                type="file"
                accept=".xlsx"
                onChange={(e) => setMappingFile(e.target.files?.[0] || null)}
                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              />
              <button
                onClick={uploadMappingFile}
                disabled={!mappingFile || isUploadingMapping}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white py-2 px-4 rounded"
              >
                {isUploadingMapping ? 'Uploading...' : 'Upload'}
              </button>
            </div>
          </div>
        )}

        {order.mapping_file_path && (
          <div className="mb-4">
            <div className="text-sm text-green-600 mb-2">
              ✓ Mapping file uploaded
            </div>
          </div>
        )}

        {mappingHeaders && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Select Mapping Keys (1-3 keys in priority order)
            </label>
            <div className="space-y-2 mb-4">
              {[1, 2, 3].map((keyNum) => (
                <div key={keyNum} className="flex items-center gap-2">
                  <span className="text-sm font-medium w-16">Key {keyNum}:</span>
                  <select
                    value={selectedMappingKeys[keyNum - 1] || ''}
                    onChange={(e) => {
                      const newKeys = [...selectedMappingKeys];
                      if (e.target.value) {
                        newKeys[keyNum - 1] = e.target.value;
                      } else {
                        newKeys.splice(keyNum - 1);
                      }
                      setSelectedMappingKeys(newKeys);
                    }}
                    className="border border-gray-300 rounded px-3 py-1 text-sm flex-1"
                    disabled={!canEdit}
                  >
                    <option value="">Select column...</option>
                    {Object.values(mappingHeaders).flat().map((header, index) => (
                      <option key={index} value={header}>{header}</option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
            {canEdit && selectedMappingKeys.length > 0 && (
              <button
                onClick={updateMappingKeys}
                className="bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded"
              >
                Save Mapping Keys
              </button>
            )}
          </div>
        )}

        {order.mapping_keys && (
          <div className="mt-4">
            <div className="text-sm font-medium text-gray-700 mb-2">Current Mapping Keys:</div>
            <div className="flex gap-2">
              {order.mapping_keys.map((key, index) => (
                <span key={index} className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-sm">
                  {index + 1}. {key}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Add Item Modal */}
      {showAddItemModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold mb-4">Add Order Item</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Company
                </label>
                <select
                  value={selectedCompany || ''}
                  onChange={(e) => setSelectedCompany(parseInt(e.target.value))}
                  className="w-full border border-gray-300 rounded px-3 py-2"
                >
                  <option value="">Select Company</option>
                  {companies.map((company) => (
                    <option key={company.company_id} value={company.company_id}>
                      {company.company_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Document Type
                </label>
                <select
                  value={selectedDocType || ''}
                  onChange={(e) => setSelectedDocType(parseInt(e.target.value))}
                  className="w-full border border-gray-300 rounded px-3 py-2"
                >
                  <option value="">Select Document Type</option>
                  {documentTypes.map((docType) => (
                    <option key={docType.doc_type_id} value={docType.doc_type_id}>
                      {docType.type_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Item Name (Optional)
                </label>
                <input
                  type="text"
                  value={itemName}
                  onChange={(e) => setItemName(e.target.value)}
                  placeholder="Leave empty for auto-generated name"
                  className="w-full border border-gray-300 rounded px-3 py-2"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => setShowAddItemModal(false)}
                className="px-4 py-2 text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={addOrderItem}
                disabled={isAddingItem || !selectedCompany || !selectedDocType}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-gray-400"
              >
                {isAddingItem ? 'Adding...' : 'Add Item'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}