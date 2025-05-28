'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { fetchJobStatus } from '@/lib/api';
import type { Job } from '@/lib/api';

export default function Jobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  // In a real app, you would have an API endpoint to list all jobs
  // For now, we'll mock this with some sample data
  useEffect(() => {
    // Mock function to simulate API call
    const fetchJobs = async () => {
      try {
        // In a real app, this would be an API call like:
        const response = await fetch(`http://${process.env.API_BASE_URL || 'localhost'}:${process.env.PORT || 8000}/jobs`);
        const data = await response.json();
        
        // Mock data for demonstration
        // const mockJobs: Job[] = [
        //   {
        //     job_id: 1,
        //     original_filename: 'invoice_sample.pdf',
        //     status: 'complete',
        //     company_id: 1,
        //     doc_type_id: 1,
        //     created_at: new Date(Date.now() - 3600000).toISOString() // 1 hour ago
        //   },
        //   {
        //     job_id: 2,
        //     original_filename: 'receipt.jpg',
        //     status: 'processing',
        //     company_id: 2,
        //     doc_type_id: 1,
        //     created_at: new Date(Date.now() - 1800000).toISOString() // 30 min ago
        //   },
        //   {
        //     job_id: 3,
        //     original_filename: 'document.pdf',
        //     status: 'failed',
        //     error_message: 'Document format not recognized',
        //     company_id: 1,
        //     doc_type_id: 2,
        //     created_at: new Date(Date.now() - 7200000).toISOString() // 2 hours ago
        //   }
        // ];
        
        // setJobs(mockJobs);
        setJobs(data);
        setIsLoading(false);
      } catch (err) {
        setError('Failed to load jobs');
        setIsLoading(false);
      }
    };

    fetchJobs();
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
                  Filename
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Date
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
                    {job.job_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {job.original_filename}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      job.status === 'success' || job.status === 'complete' 
                        ? 'bg-green-100 text-green-800' 
                        : job.status === 'processing' 
                        ? 'bg-blue-100 text-blue-800'
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {job.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(job.created_at).toLocaleString()}
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