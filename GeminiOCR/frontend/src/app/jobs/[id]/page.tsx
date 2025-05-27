'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { fetchJobStatus, fetchJobFiles, getFileDownloadUrl } from '@/lib/api';
import type { Job, File as ApiFile } from '@/lib/api';

export default function JobDetails() {
  const params = useParams();
  const jobId = parseInt(params.id as string);

  const [job, setJob] = useState<Job | null>(null);
  const [files, setFiles] = useState<ApiFile[]>([]);
  const [wsMessages, setWsMessages] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  const wsRef = useRef<WebSocket | null>(null);

  // Fetch job details initially
  useEffect(() => {
    const loadJobDetails = async () => {
      try {
        const jobData = await fetchJobStatus(jobId);
        setJob(jobData);

        // If job is complete or failed, fetch associated files
        if (jobData.status === 'success' || jobData.status === 'complete') {
          try {
            const filesData = await fetchJobFiles(jobId);
            setFiles(filesData);
          } catch (err) {
            console.error('Failed to load files:', err);
          }
        }
      } catch (err) {
        setError('Failed to load job details');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };

    loadJobDetails();

    return () => {
      // Cleanup WebSocket on unmount
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [jobId]);

  // Connect to WebSocket if job is processing
  useEffect(() => {
    if (job?.status === 'processing') {
      // Close existing connection if any
      if (wsRef.current) {
        wsRef.current.close();
      }

      // Connect to WebSocket
      wsRef.current = new WebSocket(`ws://localhost:8000/ws/${jobId}`);

      wsRef.current.onopen = () => {
        setWsMessages(prev => [...prev, 'WebSocket connection established']);
      };

      wsRef.current.wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setWsMessages(prev => [...prev, `${data.message} (${data.status})`]);

          // If status is updated to success/error, refresh job details
          if (data.status === 'success' || data.status === 'error' || data.status === 'warning') {
            fetchJobStatus(jobId)
              .then(updatedJob => {
                setJob(updatedJob);
                // Also fetch files if job completed successfully
                if (data.status === 'success') {
                  return fetchJobFiles(jobId);
                }
              })
              .then(filesData => {
                if (filesData) setFiles(filesData);
              })
              .catch(err => console.error('Failed to refresh job details', err));
          }
        } catch (e) {
          console.error('Failed to parse WebSocket message', e);
          setWsMessages(prev => [...prev, `Raw message: ${event.data}`]);
        }
      };

      wsRef.current.onclose = () => {
        setWsMessages(prev => [...prev, 'WebSocket connection closed']);
      };

      wsRef.current.onerror = () => {
        setError('WebSocket connection error');
      };

      // Send ping every 30 seconds to keep connection alive
      const pingInterval = setInterval(() => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send('ping');
        }
      }, 30000);

      return () => {
        clearInterval(pingInterval);
        if (wsRef.current) {
          wsRef.current.close();
        }
      };
    }
  }, [jobId, job?.status]);

  // Get file by category
  const getFileByCategory = (category: string) => {
    return files.find(file =>
      file.file_name.includes(category) ||
      file.file_path.includes(category)
    );
  };

  if (isLoading) {
    return <div className="text-center py-10">Loading job details...</div>;
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto mt-8">
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
        <Link
          href="/jobs"
          className="text-blue-600 hover:underline"
        >
          Back to Jobs
        </Link>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="max-w-2xl mx-auto mt-8">
        <div className="bg-yellow-100 border border-yellow-400 text-yellow-700 px-4 py-3 rounded mb-4">
          Job not found
        </div>
        <Link
          href="/jobs"
          className="text-blue-600 hover:underline"
        >
          Back to Jobs
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Job Details</h1>
        <Link
          href="/jobs"
          className="text-blue-600 hover:underline"
        >
          Back to Jobs
        </Link>
      </div>

      <div className="bg-white shadow-md rounded-lg p-6 mb-6">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-gray-500 text-sm">Job ID</p>
            <p className="font-medium">{job.job_id}</p>
          </div>
          <div>
            <p className="text-gray-500 text-sm">Status</p>
            <p className="font-medium">
              <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${job.status === 'success' || job.status === 'complete'
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

        {(job.status === 'success' || job.status === 'complete') && files.length > 0 && (
          <div className="mt-6 pt-6 border-t border-gray-200">
            <h2 className="text-lg font-medium mb-4">Files</h2>
            <div className="space-y-3">
              {files.map(file => (
                <div key={file.file_id} className="flex justify-between items-center">
                  <div>
                    <p className="font-medium">{file.file_name}</p>
                    <p className="text-sm text-gray-500">
                      {file.file_type} • {(file.file_size / 1024).toFixed(2)} KB
                    </p>
                  </div>
                  <a
                    href={getFileDownloadUrl(file.file_id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700"
                  >
                    Download
                  </a>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {job.status === 'processing' && (
        <div className="bg-white shadow-md rounded-lg p-6">
          <h2 className="text-lg font-medium mb-4">Processing Updates</h2>
          <div className="bg-gray-50 p-4 rounded-lg h-60 overflow-y-auto">
            {wsMessages.length === 0 ? (
              <p className="text-gray-500 text-center">Waiting for updates...</p>
            ) : (
              <ul className="space-y-2">
                {wsMessages.map((msg, idx) => (
                  <li key={idx} className="border-l-4 border-blue-500 pl-3 py-1">
                    {msg}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}