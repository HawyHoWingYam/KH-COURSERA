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

  // Update the download function
  const downloadFile = (path: string | undefined) => {
    if (!path) return;
    
    // Check if path is S3 URI or local path and use appropriate endpoint
    const isS3Path = path.startsWith('s3://') || path.includes('s3.amazonaws.com');
    const endpoint = isS3Path ? '/download-s3' : '/download-by-path';
    const downloadUrl = `${process.env.API_BASE_URL || 'http://localhost:8000'}${endpoint}?${isS3Path ? 's3_path' : 'path'}=${encodeURIComponent(path)}`;
    
    // Open the download URL in a new tab
    window.open(downloadUrl, '_blank');
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