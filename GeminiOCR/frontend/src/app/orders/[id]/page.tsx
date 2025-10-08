'use client';

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { DocumentType } from '@/lib/api';

interface Company {
  company_id: number;
  company_name: string;
}

interface PrimaryDocTypeInfo {
  doc_type_id: number;
  type_name: string;
  type_code: string;
  template_json_path: string | null;
  template_version?: string | null;
  has_template?: boolean;
}

interface OrderFinalReportPaths {
  mapped_csv?: string;
  mapped_excel?: string;
  special_csv?: string;
  [key: string]: string | undefined;
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
  primary_doc_type_id: number | null;
  primary_doc_type: PrimaryDocTypeInfo | null;
  final_report_paths: OrderFinalReportPaths | null;
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
  const [fileInputKeys, setFileInputKeys] = useState<{[key: number]: string}>({});

  // File Delete State
  const [deletingFiles, setDeletingFiles] = useState<{[key: string]: boolean}>({});

  // Item Delete State
  const [deletingItems, setDeletingItems] = useState<{[key: number]: boolean}>({});

  // Download State
  const [downloadingFiles, setDownloadingFiles] = useState<{[key: string]: boolean}>({});

  // Mapping File State
  const [mappingFile, setMappingFile] = useState<File | null>(null);
  const [mappingHeaders, setMappingHeaders] = useState<{[sheet: string]: string[]} | null>(null);
  const [selectedMappingKeys, setSelectedMappingKeys] = useState<string[]>([]);
  const [isUploadingMapping, setIsUploadingMapping] = useState(false);
  const [isDeletingMapping, setIsDeletingMapping] = useState(false);
  const [isUpdatingMappingKeys, setIsUpdatingMappingKeys] = useState(false);
  const [isStartingMapping, setIsStartingMapping] = useState(false);

  
  // Smart Recommendations functionality has been removed
  // const [smartRecommendations, setSmartRecommendations] = useState<{[key: number]: any[]}>({});
  // const [loadingRecommendations, setLoadingRecommendations] = useState<{[key: number]: boolean}>({});
  // const [orderLevelSuggestions, setOrderLevelSuggestions] = useState<any[]>([]);
  // const [loadingOrderSuggestions, setLoadingOrderSuggestions] = useState(false);

  // Order Management State
  const [isLockingOrder, setIsLockingOrder] = useState(false);
  const [isUnlockingOrder, setIsUnlockingOrder] = useState(false);
  const [isRestartingOcr, setIsRestartingOcr] = useState(false);
  const [isRestartingMapping, setIsRestartingMapping] = useState(false);

  useEffect(() => {
    loadOrder();
    loadCompanies();
    loadDocumentTypes();
  }, [orderId]);

  const loadOrder = async () => {
    try {
      const response = await fetch(`/api/orders/${orderId}`);
      if (!response.ok) {
        throw new Error('Failed to fetch order');
      }
      const data = await response.json();
      setOrder(data);

      // Initialize selectedMappingKeys with existing mapping keys
      if (data.mapping_keys && Array.isArray(data.mapping_keys)) {
        setSelectedMappingKeys(data.mapping_keys);
      } else {
        setSelectedMappingKeys([]);
      }

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
      const response = await fetch(`/api/companies`);
      if (!response.ok) throw new Error('Failed to fetch companies');
      const data = await response.json();
      setCompanies(data);
    } catch (error) {
      console.error('Error fetching companies:', error);
    }
  };

  const loadDocumentTypes = async () => {
    try {
      const response = await fetch(`/api/document-types`);
      if (!response.ok) throw new Error('Failed to fetch document types');
      const data = await response.json();
      setDocumentTypes(data);
    } catch (error) {
      console.error('Error fetching document types:', error);
    }
  };

  const loadMappingHeaders = async () => {
    try {
      const response = await fetch(`/api/orders/${orderId}/mapping-headers`);
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
      const response = await fetch(`/api/orders/${orderId}/items`, {
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

      const response = await fetch(`/api/orders/${orderId}/items/${itemId}/files`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Failed to upload files');
      }

      // Reload order to show updated file counts
      loadOrder();

      // Reset file input by changing its key to force re-render
      setFileInputKeys(prev => ({ ...prev, [itemId]: Date.now().toString() }));
    } catch (error) {
      console.error('Error uploading files:', error);
      setError('Failed to upload files');
    } finally {
      setUploadingFiles(prev => ({ ...prev, [itemId]: false }));
    }
  };

  const deleteFile = async (itemId: number, fileId: number, fileName: string) => {
    if (!window.confirm(`Are you sure you want to delete "${fileName}"?`)) {
      return;
    }

    const deleteKey = `${itemId}-${fileId}`;
    setDeletingFiles(prev => ({ ...prev, [deleteKey]: true }));

    try {
      const response = await fetch(`/api/orders/${orderId}/items/${itemId}/files/${fileId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete file');
      }

      // Reload order to show updated file counts and lists
      loadOrder();

      // Reset file input by changing its key to force re-render and allow same filename re-upload
      setFileInputKeys(prev => ({ ...prev, [itemId]: Date.now().toString() }));
    } catch (error) {
      console.error('Error deleting file:', error);
      setError('Failed to delete file');
    } finally {
      setDeletingFiles(prev => ({ ...prev, [deleteKey]: false }));
    }
  };

  const deleteItem = async (itemId: number, itemName: string) => {
    if (!window.confirm(`Are you sure you want to delete "${itemName}" and all its files?`)) {
      return;
    }

    setDeletingItems(prev => ({ ...prev, [itemId]: true }));

    try {
      const response = await fetch(`/api/orders/${orderId}/items/${itemId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete item');
      }

      // Reload order to show updated item counts and lists
      loadOrder();
    } catch (error) {
      console.error('Error deleting item:', error);
      setError('Failed to delete item');
    } finally {
      setDeletingItems(prev => ({ ...prev, [itemId]: false }));
    }
  };

  const downloadItemResult = async (itemId: number, format: 'json' | 'csv', itemName: string) => {
    const downloadKey = `${itemId}-${format}`;
    setDownloadingFiles(prev => ({ ...prev, [downloadKey]: true }));

    try {
      const response = await fetch(`/api/orders/${orderId}/items/${itemId}/download/${format}`);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to download ${format.toUpperCase()} file`);
      }

      // Create download link
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;

      // Get filename from response headers or create default
      const contentDisposition = response.headers.get('content-disposition');
      let filename = `order_${orderId}_item_${itemId}_${itemName || 'result'}.${format}`;

      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }

      link.download = filename;
      document.body.appendChild(link);
      link.click();

      // Cleanup
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

    } catch (error) {
      console.error(`Error downloading ${format} file:`, error);
      setError(error instanceof Error ? error.message : `Failed to download ${format.toUpperCase()} file`);
    } finally {
      setDownloadingFiles(prev => ({ ...prev, [downloadKey]: false }));
    }
  };

  const uploadMappingFile = async () => {
    if (!mappingFile) return;

    setIsUploadingMapping(true);
    try {
      const formData = new FormData();
      formData.append('mapping_file', mappingFile);

      const response = await fetch(`/api/orders/${orderId}/mapping-file`, {
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

  const deleteMappingFile = async () => {
    if (!window.confirm('Are you sure you want to delete the mapping file?')) {
      return;
    }

    setIsDeletingMapping(true);
    try {
      const response = await fetch(`/api/orders/${orderId}/mapping-file`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error('Failed to delete mapping file');
      }

      // Clear mapping related state
      setMappingHeaders(null);
      setSelectedMappingKeys([]);

      // Reload order to show updated mapping file status
      loadOrder();
    } catch (error) {
      console.error('Error deleting mapping file:', error);
      setError('Failed to delete mapping file');
    } finally {
      setIsDeletingMapping(false);
    }
  };

  const updateMappingKeys = async () => {
    setIsUpdatingMappingKeys(true);
    setError('');
    try {
      const response = await fetch(`/api/orders/${orderId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          mapping_keys: selectedMappingKeys
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to update mapping keys');
      }

      // Show success feedback
      setError('✅ Mapping keys saved successfully');
      setTimeout(() => setError(''), 3000);

      loadOrder();
    } catch (error) {
      console.error('Error updating mapping keys:', error);
      setError(error instanceof Error ? error.message : 'Failed to update mapping keys');
    } finally {
      setIsUpdatingMappingKeys(false);
    }
  };

  const submitOrder = async () => {
    try {
      // Save mapping keys first if they haven't been saved
      if (selectedMappingKeys.length > 0 && JSON.stringify(selectedMappingKeys) !== JSON.stringify(order.mapping_keys || [])) {
        await updateMappingKeys();
      }

      const response = await fetch(`/api/orders/${orderId}/submit`, {
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

  const startOcrOnlyProcessing = async () => {
    try {
      const response = await fetch(`/api/orders/${orderId}/process-ocr-only`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start OCR-only processing');
      }

      loadOrder();
    } catch (error) {
      console.error('Error starting OCR-only processing:', error);
      setError(error instanceof Error ? error.message : 'Failed to start OCR-only processing');
    }
  };

  const startMappingProcessing = async () => {
    setIsStartingMapping(true);
    setError('');
    try {
      // Save mapping keys first if they haven't been saved
      if (selectedMappingKeys.length > 0 && JSON.stringify(selectedMappingKeys) !== JSON.stringify(order.mapping_keys || [])) {
        await updateMappingKeys();
      }

      const response = await fetch(`/api/orders/${orderId}/process-mapping`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start mapping processing');
      }

      // Show success feedback
      setError('✅ Mapping processing started successfully');
      setTimeout(() => setError(''), 3000);

      loadOrder();
    } catch (error) {
      console.error('Error starting mapping processing:', error);
      setError(error instanceof Error ? error.message : 'Failed to start mapping processing');
    } finally {
      setIsStartingMapping(false);
    }
  };

  
  // Smart recommendations functionality has been removed
  const loadSmartRecommendations = async (itemId: number, csvHeaders?: string[]) => {
    // This functionality has been removed - mapping key recommender is no longer available
    console.log('Mapping key recommender functionality has been removed');
  };

  const loadOrderLevelSuggestions = async () => {
    // This functionality has been removed - mapping key recommender is no longer available
    console.log('Order-level suggestions functionality has been removed');
    // setLoadingOrderSuggestions(false); // Commented out as state is removed
  };

  // Smart recommendation functionality has been removed
  const applySmartRecommendation = (itemId: number, recommendedKey: string, keyIndex: number) => {
    console.log('Smart recommendation functionality has been removed');
  };

  const applyOrderLevelSuggestion = (keyIndex: number, suggestedKey: string) => {
    setSelectedMappingKeys(prev => {
      const newKeys = [...prev];
      newKeys[keyIndex] = suggestedKey;
      return newKeys;
    });
  };

  
  
  const downloadFinalMappedResults = async (format: 'csv' | 'excel' | 'special-csv') => {
    const downloadKey = format === 'special-csv' ? 'final-special-csv' : `final-${format}`;
    setDownloadingFiles(prev => ({ ...prev, [downloadKey]: true }));

    try {
      const endpoint = format === 'special-csv' ? 'special-csv' : `mapped-${format}`;
      const response = await fetch(`/api/orders/${orderId}/download/${endpoint}`);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.detail ||
            `Failed to download final ${format === 'special-csv' ? 'special CSV' : format.toUpperCase()} results`
        );
      }

      // Create download link
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;

      // Get filename from response headers or create default
      const contentDisposition = response.headers.get('content-disposition');
      let filename =
        format === 'excel'
          ? `order_${orderId}_mapped_results.xlsx`
          : format === 'special-csv'
            ? `order_${orderId}_special.csv`
            : `order_${orderId}_mapped_results.csv`;

      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (filenameMatch) {
          filename = filenameMatch[1].replace(/['"]/g, '');
        }
      }

      link.download = filename;
      document.body.appendChild(link);
      link.click();

      // Cleanup
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

    } catch (error) {
      console.error(`Error downloading final ${format} results:`, error);
      setError(
        error instanceof Error
          ? error.message
          : `Failed to download final ${format === 'special-csv' ? 'special CSV' : format.toUpperCase()} results`
      );
    } finally {
      setDownloadingFiles(prev => ({ ...prev, [downloadKey]: false }));
    }
  };

  // Order Management Functions
  const lockOrder = async () => {
    if (!window.confirm('Are you sure you want to lock this order? Locked orders cannot be modified.')) {
      return;
    }

    setIsLockingOrder(true);
    setError('');
    try {
      const response = await fetch(`/api/orders/${orderId}/lock`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to lock order');
      }

      setError('✅ Order locked successfully');
      setTimeout(() => setError(''), 3000);
      loadOrder();
    } catch (error) {
      console.error('Error locking order:', error);
      setError(error instanceof Error ? error.message : 'Failed to lock order');
    } finally {
      setIsLockingOrder(false);
    }
  };

  const unlockOrder = async () => {
    if (!window.confirm('Are you sure you want to unlock this order? This will allow modifications again.')) {
      return;
    }

    setIsUnlockingOrder(true);
    setError('');
    try {
      const response = await fetch(`/api/orders/${orderId}/unlock`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to unlock order');
      }

      setError('✅ Order unlocked successfully');
      setTimeout(() => setError(''), 3000);
      loadOrder();
    } catch (error) {
      console.error('Error unlocking order:', error);
      setError(error instanceof Error ? error.message : 'Failed to unlock order');
    } finally {
      setIsUnlockingOrder(false);
    }
  };

  const restartOcr = async () => {
    if (!window.confirm('Are you sure you want to restart OCR processing? This will reprocess all items and overwrite existing OCR results.')) {
      return;
    }

    setIsRestartingOcr(true);
    setError('');
    try {
      const response = await fetch(`/api/orders/${orderId}/restart-ocr`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to restart OCR processing');
      }

      setError('✅ OCR processing restarted successfully');
      setTimeout(() => setError(''), 3000);
      loadOrder();
    } catch (error) {
      console.error('Error restarting OCR:', error);
      setError(error instanceof Error ? error.message : 'Failed to restart OCR processing');
    } finally {
      setIsRestartingOcr(false);
    }
  };

  const restartMapping = async () => {
    if (!window.confirm('Are you sure you want to restart mapping processing? This will reprocess mapping with current configuration.')) {
      return;
    }

    setIsRestartingMapping(true);
    setError('');
    try {
      const response = await fetch(`/api/orders/${orderId}/restart-mapping`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to restart mapping processing');
      }

      setError('✅ Mapping processing restarted successfully');
      setTimeout(() => setError(''), 3000);
      loadOrder();
    } catch (error) {
      console.error('Error restarting mapping:', error);
      setError(error instanceof Error ? error.message : 'Failed to restart mapping processing');
    } finally {
      setIsRestartingMapping(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'DRAFT':
        return 'bg-gray-100 text-gray-800';
      case 'PROCESSING':
        return 'bg-blue-100 text-blue-800';
      case 'OCR_COMPLETED':
        return 'bg-purple-100 text-purple-800';
      case 'MAPPING':
        return 'bg-yellow-100 text-yellow-800';
      case 'COMPLETED':
        return 'bg-green-100 text-green-800';
      case 'FAILED':
        return 'bg-red-100 text-red-800';
      case 'LOCKED':
        return 'bg-orange-100 text-orange-800';
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

  // Helper functions to determine processing state
  const hasDoneOcr = (status: string) => {
    return status === 'OCR_COMPLETED' || status === 'MAPPING' || status === 'COMPLETED' || status === 'FAILED';
  };

  const hasDoneMapping = (status: string) => {
    return status === 'COMPLETED' || status === 'FAILED';
  };

  const isLocked = order.status === 'LOCKED';
  const canEdit = order.status === 'DRAFT' && !isLocked;
  const canSubmit = order.status === 'DRAFT' && order.total_items > 0 && !isLocked;
  const canStartOcrOnly = order.status === 'DRAFT' && order.total_items > 0 && !isLocked;
  // Use selectedMappingKeys (current user selection) if available, otherwise use saved mapping_keys
  const effectiveMappingKeys = selectedMappingKeys.length > 0 ? selectedMappingKeys : (order.mapping_keys || []);
  const canStartFullProcess = order.status === 'DRAFT' && order.total_items > 0 && order.mapping_file_path && effectiveMappingKeys.length > 0 && !isLocked;
  const canStartMapping = hasDoneOcr(order.status) && order.mapping_file_path && effectiveMappingKeys.length > 0 && !isLocked && !hasDoneMapping(order.status);
  const canConfigureMapping = (order.status === 'DRAFT' || order.status === 'OCR_COMPLETED' || order.status === 'COMPLETED' || order.status === 'MAPPING') && !isLocked;
  const canLock = !isLocked && (order.status === 'COMPLETED' || order.status === 'OCR_COMPLETED' || order.status === 'FAILED');
  const canUnlock = isLocked;
  const canRestartOcr = !isLocked && hasDoneOcr(order.status);
  const canRestartMapping = !isLocked && hasDoneMapping(order.status) && order.mapping_file_path;

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
        <div className="flex items-center gap-3">
          {/* Lock/Unlock Order Button */}
          {canLock && (
            <button
              onClick={lockOrder}
              disabled={isLockingOrder}
              className="bg-orange-600 hover:bg-orange-700 disabled:bg-gray-400 text-white py-2 px-4 rounded font-medium"
              title="Lock this order to prevent modifications"
            >
              {isLockingOrder ? '🔒 Locking...' : '🔒 Lock Order'}
            </button>
          )}
          {canUnlock && (
            <button
              onClick={unlockOrder}
              disabled={isUnlockingOrder}
              className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white py-2 px-4 rounded font-medium"
              title="Unlock this order to allow modifications"
            >
              {isUnlockingOrder ? '🔓 Unlocking...' : '🔓 Unlock Order'}
            </button>
          )}

          {/* Restart Buttons - Only show when unlocked */}
          {canRestartOcr && (
            <button
              onClick={restartOcr}
              disabled={isRestartingOcr}
              className="bg-yellow-600 hover:bg-yellow-700 disabled:bg-gray-400 text-white py-2 px-4 rounded font-medium"
              title="Restart OCR processing for all items"
            >
              {isRestartingOcr ? '🔄 Restarting OCR...' : '🔄 Re-OCR'}
            </button>
          )}
          {canRestartMapping && (
            <button
              onClick={restartMapping}
              disabled={isRestartingMapping}
              className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 text-white py-2 px-4 rounded font-medium"
              title="Restart mapping processing with current configuration"
            >
              {isRestartingMapping ? '🔄 Restarting Mapping...' : '🔄 Re-Mapping'}
            </button>
          )}

          {/* Processing Buttons - Only show when unlocked */}
          {canStartOcrOnly && (
            <button
              onClick={startOcrOnlyProcessing}
              className="bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded font-medium"
              title="Start OCR processing only. You can configure mapping later."
            >
              开始OCR处理
            </button>
          )}
          {canStartFullProcess && (
            <button
              onClick={submitOrder}
              className="bg-green-600 hover:bg-green-700 text-white py-2 px-4 rounded font-medium"
              title="Start OCR processing with mapping (requires mapping file and keys)"
            >
              OCR + 映射处理
            </button>
          )}
          {canStartMapping && (
            <button
              onClick={startMappingProcessing}
              disabled={isStartingMapping}
              className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-400 text-white py-2 px-4 rounded font-medium"
              title="Start mapping processing (OCR already completed)"
            >
              {isStartingMapping ? 'Map Processing...' : 'Start Mapping'}
            </button>
          )}
        </div>
      </div>

      {order.primary_doc_type && (
        <div className="mb-6 text-sm text-gray-600">
          Primary Document Type:{' '}
          <span className="font-medium text-gray-900">
            {order.primary_doc_type.type_name} ({order.primary_doc_type.type_code})
          </span>
          {order.primary_doc_type.template_json_path ? (
            <span className="ml-2 text-xs text-green-600">
              Template configured
              {order.primary_doc_type.template_version ? ` (v${order.primary_doc_type.template_version})` : ''}
            </span>
          ) : (
            <span className="ml-2 text-xs text-gray-500">No template uploaded</span>
          )}
        </div>
      )}

      {error && (
        <div className={`border-l-4 p-4 mb-6 ${
          error.startsWith('✅')
            ? 'bg-green-100 border-green-500 text-green-700'
            : 'bg-red-100 border-red-500 text-red-700'
        }`}>
          {error}
        </div>
      )}

      {/* Status Information */}
      {order.status === 'LOCKED' && (
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 mb-6">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-orange-600 font-semibold">🔒 Order Locked</span>
          </div>
          <p className="text-sm text-orange-700">
            This order is currently locked and cannot be modified. Auto-mapping configuration is applied from the document settings.
          </p>
          <ul className="text-sm text-orange-700 list-disc list-inside mt-1 space-y-1">
            <li>All processing operations are disabled</li>
            <li>File uploads and modifications are not allowed</li>
            <li>Use the "🔓 Unlock Order" button to enable modifications</li>
          </ul>
        </div>
      )}

      {order.status === 'OCR_COMPLETED' && (
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 mb-6">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-purple-600 font-semibold">🔍 OCR Processing Completed</span>
          </div>
          <p className="text-sm text-purple-700">
            All files have been processed with OCR. You can now:
          </p>
          <ul className="text-sm text-purple-700 list-disc list-inside mt-1 space-y-1">
            <li>Review the OCR results by downloading CSV files from individual items</li>
            <li>Configure mapping by uploading a mapping file and selecting keys</li>
            <li>Start mapping processing once configuration is complete</li>
          </ul>
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

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          <div>
            <div className="text-sm text-gray-500">Primary Document Type</div>
            <div className="mt-1 text-base font-medium text-gray-900">
              {order.primary_doc_type
                ? `${order.primary_doc_type.type_name} (${order.primary_doc_type.type_code})`
                : 'Not selected'}
            </div>
            {order.primary_doc_type ? (
              order.primary_doc_type.template_json_path ? (
                <div className="mt-1 text-xs text-green-600">
                  Template configured
                  {order.primary_doc_type.template_version
                    ? ` (v${order.primary_doc_type.template_version})`
                    : ''}
                </div>
              ) : (
                <div className="mt-1 text-xs text-gray-500">
                  No template uploaded; special CSV export will be skipped.
                </div>
              )
            ) : (
              <div className="mt-1 text-xs text-gray-500">
                Select a primary document type when creating an order to enable template-driven outputs.
              </div>
            )}
          </div>
          <div>
            <div className="text-sm text-gray-500">Special CSV</div>
            <div className="mt-1 text-base font-medium text-gray-900">
              {order.final_report_paths?.special_csv ? 'Ready for download' : 'Not generated'}
            </div>
            {order.final_report_paths?.special_csv ? (
              <div className="mt-1 text-xs text-green-600">
                Generated using the configured template.
              </div>
            ) : (
              <div className="mt-1 text-xs text-gray-500">
                {order.primary_doc_type?.template_json_path
                  ? 'Special CSV will become available after mapping completes.'
                  : 'Upload a template for the primary document type to produce a special CSV.'}
              </div>
            )}
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
                  <div className="flex items-center gap-2">
                    {canEdit && (
                      <button
                        onClick={() => deleteItem(item.item_id, item.item_name)}
                        disabled={deletingItems[item.item_id]}
                        className="text-red-600 hover:text-red-800 disabled:text-gray-400 text-sm font-medium"
                        title={`Delete ${item.item_name}`}
                      >
                        {deletingItems[item.item_id] ? 'Deleting...' : 'Delete Item'}
                      </button>
                    )}
                  </div>
                </div>
                <div className="text-sm text-gray-500">
                  {item.files && item.files.length > 0 ? (
                    <div>
                      <div className="font-medium">Files ({item.files.length}):</div>
                      <div className="text-xs text-gray-600 space-y-1 mt-1">
                        {item.files.map((file: any) => {
                          const deleteKey = `${item.item_id}-${file.file_id}`;
                          return (
                            <div key={file.file_id} className="flex items-center justify-between">
                              <div className="truncate flex-1">
                                📄 {file.filename} ({(file.file_size / 1024).toFixed(1)}KB)
                              </div>
                              {canEdit && (
                                <button
                                  onClick={() => deleteFile(item.item_id, file.file_id, file.filename)}
                                  disabled={deletingFiles[deleteKey]}
                                  className="ml-2 text-red-600 hover:text-red-800 disabled:text-gray-400 text-sm"
                                  title={`Delete ${file.filename}`}
                                >
                                  {deletingFiles[deleteKey] ? '...' : '×'}
                                </button>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ) : (
                    <div>Files: 0</div>
                  )}
                </div>
                <div className="text-sm text-gray-600 mb-3">
                  {item.company_name} - {item.doc_type_name}
                </div>

                {canEdit && (
                  <div className="flex items-center gap-4">
                    <label className="cursor-pointer bg-gray-100 hover:bg-gray-200 text-gray-700 py-2 px-4 rounded border">
                      {uploadingFiles[item.item_id] ? 'Uploading...' : 'Upload Files'}
                      <input
                        key={fileInputKeys[item.item_id] || `file-input-${item.item_id}`}
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

                {/* Download Results Section - Show for completed items */}
                {item.status === 'COMPLETED' && (item.ocr_result_json_path || item.ocr_result_csv_path) && (
                  <div className="mt-4 pt-3 border-t border-gray-200">
                    <div className="text-sm font-medium text-gray-700 mb-2">Download Results:</div>
                    <div className="flex items-center gap-2">
                      {item.ocr_result_json_path && (
                        <button
                          onClick={() => downloadItemResult(item.item_id, 'json', item.item_name)}
                          disabled={downloadingFiles[`${item.item_id}-json`]}
                          className="bg-blue-100 hover:bg-blue-200 disabled:bg-gray-200 text-blue-700 disabled:text-gray-500 py-1 px-3 rounded text-sm font-medium"
                          title="Download JSON results"
                        >
                          {downloadingFiles[`${item.item_id}-json`] ? 'Downloading...' : '📄 JSON'}
                        </button>
                      )}
                      {item.ocr_result_csv_path && (
                        <button
                          onClick={() => downloadItemResult(item.item_id, 'csv', item.item_name)}
                          disabled={downloadingFiles[`${item.item_id}-csv`]}
                          className="bg-green-100 hover:bg-green-200 disabled:bg-gray-200 text-green-700 disabled:text-gray-500 py-1 px-3 rounded text-sm font-medium"
                          title="Download CSV results"
                        >
                          {downloadingFiles[`${item.item_id}-csv`] ? 'Downloading...' : '📊 CSV'}
                        </button>
                      )}
                    </div>
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
        <div className="mb-4">
          <h2 className="text-lg font-semibold">Mapping Configuration (Optional)</h2>
          <p className="text-sm text-gray-600 mt-1">
            You can submit the order for OCR processing first, then configure mapping after reviewing the results.
          </p>
        </div>

        {canConfigureMapping && (
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Upload Mapping File (Excel/CSV)
            </label>
            <div className="flex items-center gap-4">
              <input
                type="file"
                accept=".xlsx,.csv"
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
            <div className="flex items-center justify-between">
              <div className="text-sm text-green-600">
                ✓ Mapping file uploaded
              </div>
              {canConfigureMapping && (
                <button
                  onClick={deleteMappingFile}
                  disabled={isDeletingMapping}
                  className="text-red-600 hover:text-red-800 disabled:text-gray-400 text-sm"
                  title="Delete mapping file"
                >
                  {isDeletingMapping ? 'Deleting...' : 'Delete'}
                </button>
              )}
            </div>
          </div>
        )}

        {/* Order-Level Smart Recommendations functionality has been removed */}

        {/* Order-Level Smart Recommendations display functionality has been removed */}

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
                        // Ensure we have enough slots in the array
                        while (newKeys.length <= keyNum - 1) {
                          newKeys.push('');
                        }
                        newKeys[keyNum - 1] = e.target.value;
                        // Remove empty trailing elements to keep array clean
                        while (newKeys.length > 0 && newKeys[newKeys.length - 1] === '') {
                          newKeys.pop();
                        }
                      } else {
                        // Clear the value at this index
                        if (keyNum - 1 < newKeys.length) {
                          newKeys[keyNum - 1] = '';
                          // Remove empty trailing elements
                          while (newKeys.length > 0 && newKeys[newKeys.length - 1] === '') {
                            newKeys.pop();
                          }
                        }
                      }
                      setSelectedMappingKeys(newKeys);
                    }}
                    className="border border-gray-300 rounded px-3 py-1 text-sm flex-1"
                    disabled={!canConfigureMapping}
                  >
                    <option value="">Select column...</option>
                    {Object.values(mappingHeaders).flat().map((header, index) => (
                      <option key={index} value={header}>{header}</option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
            {canConfigureMapping && selectedMappingKeys.some(key => key && key.trim() !== '') && (
              <button
                onClick={updateMappingKeys}
                disabled={isUpdatingMappingKeys}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white py-2 px-4 rounded"
              >
                {isUpdatingMappingKeys ? 'Saving...' : 'Save Mapping Keys'}
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

      {/* Final Mapped Results Section - Show only for completed orders with mapped results */}
      {order.status === 'COMPLETED' && (
        order.final_report_paths?.mapped_csv ||
        order.final_report_paths?.mapped_excel ||
        order.final_report_paths?.special_csv
      ) && (
        <div className="bg-white rounded-lg shadow p-6 mb-8">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-green-600">📊 Final Mapped Results</h2>
            <p className="text-sm text-gray-600 mt-1">
              Download the complete results with mapping applied based on your configured keys.
            </p>
          </div>

          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex items-center text-green-700">
                <svg className="w-5 h-5 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
                <span className="font-medium">Mapping Completed Successfully</span>
              </div>
            </div>

            <div className="text-sm text-green-700 mb-4">
              All order items have been processed and mapped according to your configuration. Download the final results below:
            </div>

            <div className="flex items-center gap-3">
              {order.final_report_paths?.mapped_csv && (
                <button
                  onClick={() => downloadFinalMappedResults('csv')}
                  disabled={downloadingFiles['final-csv']}
                  className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white py-2 px-4 rounded font-medium flex items-center gap-2"
                  title="Download final mapped results as CSV"
                >
                  {downloadingFiles['final-csv'] ? (
                    'Downloading...'
                  ) : (
                    <>
                      📊 Download CSV Results
                    </>
                  )}
                </button>
              )}

              {order.final_report_paths?.mapped_excel && (
                <button
                  onClick={() => downloadFinalMappedResults('excel')}
                  disabled={downloadingFiles['final-excel']}
                  className="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white py-2 px-4 rounded font-medium flex items-center gap-2"
                  title="Download final mapped results as Excel (includes analysis sheets)"
                >
                  {downloadingFiles['final-excel'] ? (
                    'Downloading...'
                  ) : (
                    <>
                      📈 Download Excel Report
                    </>
                  )}
                </button>
              )}

              {order.final_report_paths?.special_csv && (
                <button
                  onClick={() => downloadFinalMappedResults('special-csv')}
                  disabled={downloadingFiles['final-special-csv']}
                  className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-400 text-white py-2 px-4 rounded font-medium flex items-center gap-2"
                  title="Download template-driven special CSV output"
                >
                  {downloadingFiles['final-special-csv'] ? 'Downloading...' : '✨ Download Special CSV'}
                </button>
              )}
            </div>

            <div className="mt-3 text-xs text-green-600">
              💡 CSV delivers the raw mapped dataset, Excel provides analytics worksheets, and Special CSV applies template-defined formatting.
            </div>
          </div>
        </div>
      )}

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
