'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { fetchBatchJobs, BatchJob } from '@/lib/api';

interface PendingBatchUpload {
  batchId?: number;
  uploadType?: string;
  fileCount?: number;
  fileNames?: string[];
  documentType?: string;
  timestamp?: string;
}

export default function Jobs() {
  const [batchJobs, setBatchJobs] = useState<BatchJob[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [pendingUpload, setPendingUpload] = useState<PendingBatchUpload | null>(null);

  useEffect(() => {
    // Check for pending batch uploads from sessionStorage
    const batchUploadInfo = sessionStorage.getItem('pendingBatchUpload');
    if (batchUploadInfo) {
      setPendingUpload(JSON.parse(batchUploadInfo));
      // Clear it after displaying
      sessionStorage.removeItem('pendingBatchUpload');
    }

    // Load batch jobs
    const loadData = async () => {
      setIsLoading(true);
      try {
        const batchJobsData = await fetchBatchJobs();
        setBatchJobs(batchJobsData);
      } catch (error) {
        console.error('Error fetching batch jobs:', error);
        setError('Failed to load batch jobs');
      } finally {
        setIsLoading(false);
      }
    };

    loadData();

    // Set up an interval to refresh batch job data every 30 seconds
    const refreshInterval = setInterval(() => {
      fetchBatchJobs()
        .then(updatedBatchJobs => setBatchJobs(updatedBatchJobs))
        .catch(err => console.error('Error refreshing batch jobs:', err));
    }, 30000);

    return () => {
      clearInterval(refreshInterval);
    };
  }, []);


  const formatUploadDescription = (batchJob: BatchJob) => {
    // Show original file names if available, otherwise fall back to upload_description
    if (batchJob.zip_filename) {
      return batchJob.zip_filename;
    }
    return 'Batch processing';
  };

  const formatUploadType = (uploadType: string | undefined) => {
    if (!uploadType) return '';
    
    switch (uploadType) {
      case 'single_file': return 'Single file';
      case 'multiple_files': return 'Multiple files';
      case 'zip_file': return 'ZIP archive';
      case 'mixed': return 'Mixed files';
      default: return uploadType;
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">Processing Batches</h1>
        <Link
          href="/upload"
          className="bg-blue-600 hover:bg-blue-700 text-white py-2 px-6 rounded"
        >
          Upload New Documents
        </Link>
      </div>

      {/* Show pending batch upload notification */}
      {pendingUpload && (
        <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-blue-700">
                Your batch upload with <span className="font-medium">{pendingUpload.fileCount} file(s)</span> is being processed.
                {pendingUpload.uploadType && (
                  <span> Upload type: <span className="font-medium">{formatUploadType(pendingUpload.uploadType)}</span>.</span>
                )}
                It will appear in the list once processing starts.
              </p>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-6">
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg shadow overflow-hidden">
        {isLoading && batchJobs.length === 0 ? (
          <div className="text-center py-10">Loading batch jobs...</div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  BATCH ID
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  DESCRIPTION
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  DOCUMENT TYPE
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  COMPANY
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  STATUS
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  PROGRESS
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  DATE
                </th>
                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  ACTIONS
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {batchJobs.map((batchJob) => (
                <tr key={batchJob.batch_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-gray-900 font-medium">
                    {batchJob.batch_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-gray-500">
                    {formatUploadDescription(batchJob)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-gray-500">
                    {batchJob.type_name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-gray-500">
                    {batchJob.company_name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full 
                      ${batchJob.status === 'success' || batchJob.status === 'completed'
                          ? 'bg-green-100 text-green-800'
                          : batchJob.status === 'processing'
                            ? 'bg-blue-100 text-blue-800'
                            : batchJob.status === 'pending'
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-red-100 text-red-800'
                        }`}>
                      {batchJob.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center">
                      <div className="text-sm text-gray-900">
                        {batchJob.processed_files}/{batchJob.total_files}
                      </div>
                      {batchJob.status === 'processing' && batchJob.total_files > 0 && (
                        <div className="ml-2 w-16 bg-gray-200 rounded-full h-2">
                          <div 
                            className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
                            style={{ width: `${(batchJob.processed_files / Math.max(1, batchJob.total_files)) * 100}%` }}
                          ></div>
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-gray-500">
                    {new Date(batchJob.created_at).toLocaleString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-blue-600 hover:text-blue-800">
                    <Link href={`/batch-jobs/${batchJob.batch_id}`}>
                      View Details
                    </Link>
                  </td>
                </tr>
              ))}
              {isLoading && (
                <tr>
                  <td colSpan={8} className="px-6 py-4 text-center text-sm text-gray-500">
                    Loading additional batches...
                  </td>
                </tr>
              )}
              {!isLoading && batchJobs.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-6 py-4 text-center text-sm text-gray-500">
                    No batch jobs found. Upload some documents to get started!
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}