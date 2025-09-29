'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { fetchBatchJobStatus, BatchJob, deleteBatchJob } from '@/lib/api';

export default function BatchJobDetails() {
  const params = useParams();
  const router = useRouter();
  const [batchJob, setBatchJob] = useState<BatchJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const batchId = params?.id ? Number(params.id) : 0;

  useEffect(() => {
    if (batchId) {
      const loadBatchJob = async () => {
        try {
          setLoading(true);
          const data = await fetchBatchJobStatus(batchId);
          setBatchJob(data);
          setError(null);
        } catch (err) {
          console.error('Error fetching batch job:', err);
          setError('Failed to load batch job details');
        } finally {
          setLoading(false);
        }
      };

      loadBatchJob();

      // Set up polling for updates if job is still processing
      const interval = setInterval(async () => {
        try {
          const data = await fetchBatchJobStatus(batchId);
          setBatchJob(data);
          
          // Stop polling if job is complete or failed
          if (data.status !== 'pending' && data.status !== 'processing') {
            clearInterval(interval);
          }
        } catch (err) {
          console.error('Error polling batch job status:', err);
        }
      }, 5000); // Poll every 5 seconds

      return () => clearInterval(interval);
    }
  }, [batchId]);

  const getStatusBadge = (status: string) => {
    const statusColors: Record<string, string> = {
      pending: 'bg-yellow-100 text-yellow-800',
      processing: 'bg-blue-100 text-blue-800',
      success: 'bg-green-100 text-green-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
    };

    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColors[status] || 'bg-gray-100'}`}>
        {status}
      </span>
    );
  };

  // Update the download function to keep downloads in the same origin and force attachment behaviour
  const downloadFile = async (path: string | undefined) => {
    if (!path) return;

    const isS3Path = path.startsWith('s3://') || path.includes('s3.amazonaws.com');
    const endpoint = isS3Path ? '/api/download-s3' : '/api/download-by-path';
    const param = isS3Path ? 's3_path' : 'path';
    const downloadUrl = `${endpoint}?${param}=${encodeURIComponent(path)}`;
    const fallbackFilename = path.split('/').pop() || 'download';

    const extractFilename = (header: string | null): string | null => {
      if (!header) return null;

      const filenameStarMatch = header.match(/filename\*=UTF-8''([^;]+)/i);
      if (filenameStarMatch?.[1]) {
        try {
          return decodeURIComponent(filenameStarMatch[1]);
        } catch (error) {
          console.warn('Failed to decode RFC 5987 filename, falling back:', error);
        }
      }

      const filenameMatch = header.match(/filename="?([^";]+)"?/i);
      if (filenameMatch?.[1]) {
        return filenameMatch[1];
      }

      return null;
    };

    try {
      const response = await fetch(downloadUrl);

      if (!response.ok) {
        throw new Error(`下載失敗 (${response.status} ${response.statusText})`);
      }

      const blob = await response.blob();
      const contentDisposition = response.headers.get('content-disposition');
      const resolvedFilename = extractFilename(contentDisposition) || fallbackFilename;
      const blobUrl = window.URL.createObjectURL(blob);

      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = resolvedFilename;
      link.style.display = 'none';

      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      window.URL.revokeObjectURL(blobUrl);
    } catch (error) {
      console.error('Error downloading file:', error);

      const errorMessage = error instanceof Error ? error.message : 'Unknown error occurred';
      alert(`下載失敗: ${errorMessage}\n\n請稍後再試，或聯繫管理員。`);

      // Last resort fallback - open download URL directly in new tab
      if (confirm('是否要改為直接開啟下載連結？')) {
        window.open(downloadUrl, '_blank');
      }
    }
  };

  const handleDeleteBatchJob = async () => {
    if (!batchJob) return;

    setIsDeleting(true);
    setDeleteError(null);

    try {
      const result = await deleteBatchJob(batchJob.batch_id);
      console.log('Delete result:', result);
      
      // Show success message and redirect
      setShowDeleteDialog(false);
      router.push('/jobs?deleted=true');
    } catch (err) {
      console.error('Failed to delete batch job:', err);
      setDeleteError(err instanceof Error ? err.message : 'Failed to delete batch job');
    } finally {
      setIsDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-6">Batch Job Details</h1>
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-6">Batch Job Details</h1>
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
        <button 
          onClick={() => router.push('/jobs')}
          className="bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700"
        >
          Back to Jobs
        </button>
      </div>
    );
  }

  if (!batchJob) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-6">Batch Job Details</h1>
        <div className="bg-yellow-100 border border-yellow-400 text-yellow-700 px-4 py-3 rounded mb-4">
          No batch job found with ID {batchId}
        </div>
        <button 
          onClick={() => router.push('/jobs')}
          className="bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700"
        >
          Back to Jobs
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Batch Job #{batchJob.batch_id}</h1>
        <div className="flex space-x-3">
          <button
            onClick={() => setShowDeleteDialog(true)}
            className="bg-red-600 text-white py-2 px-4 rounded hover:bg-red-700 transition-colors"
            disabled={isDeleting}
          >
            Delete Job
          </button>
          <Link href="/jobs">
            <span className="bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 cursor-pointer">
              Back to Jobs
            </span>
          </Link>
        </div>
      </div>

      {/* Status Card */}
      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Status</h2>
          {getStatusBadge(batchJob.status)}
        </div>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-gray-600">Progress</p>
            <p className="font-medium">{batchJob.processed_files} / {batchJob.total_files} files</p>
          </div>
          <div>
            <p className="text-gray-600">Created</p>
            <p className="font-medium">{new Date(batchJob.created_at).toLocaleString()}</p>
          </div>
        </div>
        
        {batchJob.status === 'processing' && (
          <div className="mt-4">
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div 
                className="bg-blue-600 h-2.5 rounded-full" 
                style={{ width: `${(batchJob.processed_files / Math.max(1, batchJob.total_files)) * 100}%` }}
              ></div>
            </div>
          </div>
        )}
        
        {batchJob.error_message && (
          <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            <p className="font-medium">Error:</p>
            <p>{batchJob.error_message}</p>
          </div>
        )}
      </div>

      {/* Details Card */}
      <div className="bg-white shadow rounded-lg p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4">Job Details</h2>
        
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-gray-600">ZIP Filename</p>
            <p className="font-medium">{batchJob.zip_filename}</p>
          </div>
          <div>
            <p className="text-gray-600">Document Type</p>
            <p className="font-medium">{batchJob.type_name || 'Unknown'}</p>
          </div>
          <div>
            <p className="text-gray-600">Company</p>
            <p className="font-medium">{batchJob.company_name || 'Unknown'}</p>
          </div>
          <div>
            <p className="text-gray-600">Updated</p>
            <p className="font-medium">{new Date(batchJob.updated_at).toLocaleString()}</p>
          </div>
        </div>
      </div>

      {/* Results Card - Only show if job is completed */}
      {batchJob.status === 'completed' && (
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">Results</h2>
          
          <div className="space-y-4">
            {batchJob.json_output_path && (
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">JSON Results</p>
                  <p className="text-sm text-gray-500">{batchJob.json_output_path.split('/').pop()}</p>
                </div>
                <button 
                  onClick={() => downloadFile(batchJob.json_output_path)}
                  className="bg-blue-600 text-white py-1 px-3 rounded hover:bg-blue-700"
                >
                  Download
                </button>
              </div>
            )}
            
            {batchJob.excel_output_path && (
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Excel Results</p>
                  <p className="text-sm text-gray-500">{batchJob.excel_output_path.split('/').pop()}</p>
                </div>
                <button 
                  onClick={() => downloadFile(batchJob.excel_output_path)}
                  className="bg-blue-600 text-white py-1 px-3 rounded hover:bg-blue-700"
                >
                  Download
                </button>
              </div>
            )}

            {/* Cost Allocation Reports Section */}
            {(batchJob.netsuite_csv_path || batchJob.matching_report_path || batchJob.summary_report_path) && (
              <div className="border-t pt-4 mt-4">
                <h3 className="text-lg font-semibold mb-3 text-green-600">Cost Allocation Reports</h3>
                
                {batchJob.netsuite_csv_path && (
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="font-medium">NetSuite Import File</p>
                      <p className="text-sm text-gray-500">CSV file ready for NetSuite import</p>
                    </div>
                    <button 
                      onClick={() => downloadFile(batchJob.netsuite_csv_path)}
                      className="bg-green-600 text-white py-1 px-3 rounded hover:bg-green-700"
                    >
                      Download CSV
                    </button>
                  </div>
                )}

                {batchJob.matching_report_path && (
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="font-medium">Matching Details Report</p>
                      <p className="text-sm text-gray-500">Excel file with matched and unmatched records</p>
                    </div>
                    <button 
                      onClick={() => downloadFile(batchJob.matching_report_path)}
                      className="bg-green-600 text-white py-1 px-3 rounded hover:bg-green-700"
                    >
                      Download Report
                    </button>
                  </div>
                )}

                {batchJob.summary_report_path && (
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <p className="font-medium">Cost Summary Report</p>
                      <p className="text-sm text-gray-500">Excel file with cost breakdown by department and shop</p>
                    </div>
                    <button 
                      onClick={() => downloadFile(batchJob.summary_report_path)}
                      className="bg-green-600 text-white py-1 px-3 rounded hover:bg-green-700"
                    >
                      Download Summary
                    </button>
                  </div>
                )}

                {batchJob.unmatched_count !== undefined && batchJob.unmatched_count > 0 && (
                  <div className="bg-yellow-50 border border-yellow-200 rounded p-3 mt-3">
                    <p className="text-yellow-700 font-medium">
                      ⚠️ {batchJob.unmatched_count} records could not be matched to any shop/department
                    </p>
                    <p className="text-sm text-yellow-600 mt-1">
                      Check the matching details report to review unmatched records and update your mapping file if needed.
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {showDeleteDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-md w-full mx-4">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold text-gray-900">Delete Batch Job</h2>
                <button
                  onClick={() => setShowDeleteDialog(false)}
                  className="text-gray-400 hover:text-gray-600"
                  disabled={isDeleting}
                >
                  ✕
                </button>
              </div>

              {deleteError && (
                <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
                  {deleteError}
                </div>
              )}

              <div className="mb-4">
                <p className="text-gray-700">
                  Are you sure you want to delete <strong>Batch Job #{batchJob.batch_id}</strong>?
                </p>
                <p className="text-sm text-gray-600 mt-2">
                  This will permanently delete:
                </p>
                <ul className="text-sm text-gray-600 mt-2 list-disc ml-6">
                  <li>The batch job record</li>
                  <li>All related processing jobs ({batchJob.total_files} files)</li>
                  <li>All uploaded and generated files</li>
                  <li>All API usage records</li>
                </ul>
                <p className="text-sm text-red-600 mt-2 font-medium">
                  This action cannot be undone.
                </p>
              </div>

              <div className="flex justify-end space-x-4">
                <button
                  onClick={() => setShowDeleteDialog(false)}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800"
                  disabled={isDeleting}
                >
                  Cancel
                </button>
                <button
                  onClick={handleDeleteBatchJob}
                  className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                  disabled={isDeleting}
                >
                  {isDeleting ? 'Deleting...' : 'Delete Job'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
