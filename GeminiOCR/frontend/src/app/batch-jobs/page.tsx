'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { fetchBatchJobs, BatchJob, PaginationInfo } from '@/lib/api';
import Pagination from '@/components/ui/Pagination';

export default function BatchJobsIndex() {
  const [batchJobs, setBatchJobs] = useState<BatchJob[]>([]);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [isPageLoading, setIsPageLoading] = useState(false);
  const [error, setError] = useState('');

  const loadData = async (page: number = 1, isPageChange: boolean = false) => {
    if (isPageChange) {
      setIsPageLoading(true);
    } else {
      setIsLoading(true);
    }
    
    try {
      const offset = (page - 1) * 20; // 20 items per page
      const response = await fetchBatchJobs({ limit: 20, offset });
      setBatchJobs(response.data);
      setPagination(response.pagination);
      setCurrentPage(page);
      setError('');
    } catch (error) {
      console.error('Error fetching batch jobs:', error);
      setError('Failed to load batch jobs');
    } finally {
      setIsLoading(false);
      setIsPageLoading(false);
    }
  };

  useEffect(() => {
    loadData(currentPage);

    // Set up refresh interval - only refresh current page
    const refreshInterval = setInterval(() => {
      const offset = (currentPage - 1) * 20;
      fetchBatchJobs({ limit: 20, offset })
        .then(response => {
          setBatchJobs(response.data);
          setPagination(response.pagination);
        })
        .catch(err => console.error('Error refreshing batch jobs:', err));
    }, 30000);

    return () => clearInterval(refreshInterval);
  }, [currentPage]);

  const handlePageChange = (page: number) => {
    if (page !== currentPage && page >= 1 && (!pagination || page <= Math.min(pagination.total_pages, 5))) {
      loadData(page, true);
    }
  };

  const formatUploadDescription = (batchJob: BatchJob) => {
    if (batchJob.zip_filename) {
      return batchJob.zip_filename;
    }
    return 'Batch processing';
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">Batch Jobs</h1>
        <Link
          href="/upload"
          className="bg-blue-600 hover:bg-blue-700 text-white py-2 px-6 rounded"
        >
          Upload New Documents
        </Link>
      </div>

      {error && (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-6">
          {error}
        </div>
      )}

      <div className="bg-white rounded-lg shadow overflow-hidden">
        {isLoading && batchJobs.length === 0 ? (
          <div className="text-center py-10">Loading batch jobs...</div>
        ) : (
          <>
          {isPageLoading && (
            <div className="bg-blue-50 border-l-4 border-blue-400 text-blue-700 p-4">
              <div className="flex items-center">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mr-2"></div>
                Loading page {currentPage}...
              </div>
            </div>
          )}
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
          
          {/* Pagination */}
          {pagination && (
            <Pagination 
              pagination={pagination} 
              onPageChange={handlePageChange}
              maxPages={5}
              disabled={isPageLoading}
            />
          )}
          </>
        )}
      </div>
    </div>
  );
} 