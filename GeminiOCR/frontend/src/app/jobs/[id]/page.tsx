'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { fetchJobStatus } from '@/lib/api';
import type { Job } from '@/lib/api';



export default function JobDetails() {
  const params = useParams();
  const router = useRouter();
  const jobId = parseInt(params.id as string);

  const [job, setJob] = useState<Job | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadJobDetails = async () => {
      try {
        const jobData = await fetchJobStatus(jobId);
        setJob(jobData);
        
        // If this is part of a batch, redirect to batch details
        if (jobData.batch_id) {
          router.push(`/batch-jobs/${jobData.batch_id}`);
          return;
        }
      } catch (err) {
        setError('Failed to load job details');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    loadJobDetails();
  }, [jobId, router]);

  if (isLoading) {
    return <div className="text-center py-10">Loading...</div>;
  }

  return (
    <div className="max-w-2xl mx-auto mt-8">
      <div className="bg-blue-50 border-l-4 border-blue-500 p-6 mb-6">
        <div className="flex">
          <div className="flex-shrink-0">
            <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-lg font-medium text-blue-800">System Updated to Batch Processing</h3>
            <div className="mt-2 text-sm text-blue-700">
              <p>Our system has been updated to use batch processing for all uploads. Individual job tracking has been consolidated into batch jobs for better organization and efficiency.</p>
              <div className="mt-4 space-y-2">
                <p><strong>What this means:</strong></p>
                <ul className="list-disc list-inside space-y-1">
                  <li>All uploads (single files, multiple files, ZIP archives) are now processed as batches</li>
                  <li>Better progress tracking and status updates</li>
                  <li>Consolidated results and downloads</li>
                  <li>Enhanced upload capabilities for mixed file types</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {job && (
        <div className="bg-white shadow-md rounded-lg p-6 mb-6">
          <h2 className="text-lg font-medium mb-4">Legacy Job Information</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-gray-500 text-sm">Job ID</p>
              <p className="font-medium">{job.job_id}</p>
            </div>
            <div>
              <p className="text-gray-500 text-sm">Status</p>
              <p className="font-medium">
                <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full 
                ${job.status === 'success' || job.status === 'complete'
                    ? 'bg-green-100 text-green-800'
                    : job.status === 'processing'
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-red-100 text-red-800'
                  }`}>
                  {job.status}
                </span>
              </p>
            </div>
            <div>
              <p className="text-gray-500 text-sm">Original Filename</p>
              <p className="font-medium">{job.original_filename}</p>
            </div>
            <div>
              <p className="text-gray-500 text-sm">Created At</p>
              <p className="font-medium">
                {new Date(job.created_at).toLocaleString()}
              </p>
            </div>
            {job.error_message && (
              <div className="col-span-2">
                <p className="text-gray-500 text-sm">Error Message</p>
                <p className="font-medium text-red-600">{job.error_message}</p>
              </div>
            )}
          </div>
          
          {job.batch_id && (
            <div className="mt-4 p-4 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-700">
                This job is part of batch #{job.batch_id}. 
                <Link 
                  href={`/batch-jobs/${job.batch_id}`}
                  className="ml-1 font-medium underline"
                >
                  View batch details
                </Link>
              </p>
            </div>
          )}
        </div>
      )}

      <div className="flex space-x-4">
        <Link
          href="/jobs"
          className="bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700"
        >
          View All Batches
        </Link>
        <Link
          href="/upload"
          className="bg-green-600 text-white py-2 px-4 rounded hover:bg-green-700"
        >
          Upload New Documents
        </Link>
      </div>
    </div>
  );
}