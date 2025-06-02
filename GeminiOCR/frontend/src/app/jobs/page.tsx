'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { fetchJobs, Job } from '@/lib/api';

export default function Jobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [pendingUpload, setPendingUpload] = useState<any>(null);

  useEffect(() => {
    // Check for pending uploads from sessionStorage first - do this immediately
    const uploadInfo = sessionStorage.getItem('pendingUpload');
    if (uploadInfo) {
      setPendingUpload(JSON.parse(uploadInfo));
      // Clear it after displaying
      sessionStorage.removeItem('pendingUpload');
    }

    // Load jobs in the background
    fetchJobs()
      .then(jobsData => {
        setJobs(jobsData);
        setIsLoading(false);
      })
      .catch(err => {
        console.error('Failed to load jobs:', err);
        setError('Failed to load jobs. Please try again.');
        setIsLoading(false);
      });

    // Set up an interval to refresh job data every 10 seconds
    const refreshInterval = setInterval(() => {
      fetchJobs()
        .then(updatedJobs => setJobs(updatedJobs))
        .catch(err => console.error('Error refreshing jobs:', err));
    }, 10000);

    return () => clearInterval(refreshInterval);
  }, []);

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold">Processing Jobs</h1>
        <Link
          href="/upload"
          className="bg-blue-600 hover:bg-blue-700 text-white py-2 px-6 rounded"
        >
          Upload New Document
        </Link>
      </div>

      {/* Show pending upload notification */}
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
                Your document <span className="font-medium">{pendingUpload.fileName}</span> is being processed. 
                It will appear in the list once processing is complete.
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
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                JOB ID
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                FILENAME
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                STATUS
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                DATE
              </th>
              <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                ACTIONS
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200 text-black">
            {jobs.map((job) => (
              <tr key={job.job_id}>
                <td className="px-6 py-4 whitespace-nowrap text-black">
                  {job.job_id}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-black">
                  {job.original_filename}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full 
                    ${job.status === 'success' || job.status === 'complete'
                        ? 'bg-green-100 text-green-800'
                        : job.status === 'processing'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-red-100 text-red-800'
                      }`}>
                    {job.status}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {new Date(job.created_at).toLocaleString()}
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-blue-600 hover:text-blue-800">
                  <Link href={`/jobs/${job.job_id}`}>
                    View
                  </Link>
                </td>
              </tr>
            ))}
            {isLoading && (
              <tr>
                <td colSpan={5} className="px-6 py-4 text-center text-sm text-gray-500">
                  <div className="flex justify-center items-center space-x-2">
                    <svg className="animate-spin h-5 w-5 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span>Loading jobs...</span>
                  </div>
                </td>
              </tr>
            )}
            {!isLoading && jobs.length === 0 && (
              <tr>
                <td colSpan={5} className="px-6 py-4 text-center text-sm text-gray-500">
                  No jobs found. Your new jobs will appear here when processing begins.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}