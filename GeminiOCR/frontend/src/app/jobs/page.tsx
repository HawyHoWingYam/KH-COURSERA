'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface Job {
  job_id: string;
  document_type: string;
  provider: string;
  status: string;
  timestamp: string;
}

export default function Jobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // In a real implementation, you would fetch jobs from your backend
  // This is a mock implementation since our API doesn't have a list jobs endpoint yet
  useEffect(() => {
    // This would typically be a real API call
    // fetch('http://localhost:8000/jobs')
    //   .then(res => res.json())
    //   .then(data => setJobs(data))
    //   .catch(err => setError('Failed to load jobs'))
    //   .finally(() => setIsLoading(false));

    // Mocking jobs data for now
    setTimeout(() => {
      setJobs([
        { 
          job_id: '123e4567-e89b-12d3-a456-426614174000', 
          document_type: 'invoice',
          provider: 'hanamusubi',
          status: 'complete',
          timestamp: '2023-10-15 14:32:12'
        },
        { 
          job_id: '223e4567-e89b-12d3-a456-426614174001', 
          document_type: 'invoice',
          provider: 'archers',
          status: 'processing',
          timestamp: '2023-10-15 14:35:22' 
        }
      ]);
      setIsLoading(false);
    }, 1000);
  }, []);

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Processing Jobs</h1>
        <Link 
          href="/upload"
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
        >
          Upload New Document
        </Link>
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="text-center py-10">Loading jobs...</div>
      ) : jobs.length === 0 ? (
        <div className="text-center py-10">
          <p className="text-gray-500">No jobs found</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Job ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Document Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Provider
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Timestamp
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {jobs.map((job) => (
                <tr key={job.job_id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {job.job_id.substring(0, 8)}...
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {job.document_type}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {job.provider}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      job.status === 'complete' 
                        ? 'bg-green-100 text-green-800' 
                        : job.status === 'processing' 
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {job.timestamp}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <Link 
                      href={`/jobs/${job.job_id}`}
                      className="text-blue-600 hover:text-blue-900"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}