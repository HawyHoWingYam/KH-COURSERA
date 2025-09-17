'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { fetchJobStatus, fetchJobFiles, getFileDownloadUrl, fetchFilePreview, FileInfo } from '@/lib/api';
import type { Job } from '@/lib/api';

// Add these imports for the preview components
import { JsonView } from 'react-json-view-lite';
import 'react-json-view-lite/dist/index.css';



export default function JobDetails() {
  const params = useParams();
  const jobId = parseInt(params.id as string);

  const [job, setJob] = useState<Job | null>(null);
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [wsMessages, setWsMessages] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  const [previewStates, setPreviewStates] = useState<Record<number, boolean>>({});
  const [filePreviewData, setFilePreviewData] = useState<Record<number, { loading?: boolean; error?: string; [key: string]: unknown }>>({});

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

      // Connect to WebSocket using config values
      wsRef.current = new WebSocket(`ws://${process.env.API_BASE_URL || 'localhost'}:${process.env.PORT || 8000}/ws/${jobId}`);

      wsRef.current.onopen = () => {
        setWsMessages(prev => [...prev, 'WebSocket connection established']);
      };

      wsRef.current.onmessage = (event: MessageEvent) => {
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
                return undefined;
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

  // Toggle preview for a file and fetch content if needed
  const togglePreview = async (fileId: number) => {
    const isCurrentlyShown = previewStates[fileId];
    
    // Toggle the preview state
    setPreviewStates(prev => ({ ...prev, [fileId]: !isCurrentlyShown }));
    
    // If we're showing the preview and don't have data yet, fetch it
    if (!isCurrentlyShown && !filePreviewData[fileId]) {
      try {
        // Set loading state
        setFilePreviewData(prev => ({ ...prev, [fileId]: { loading: true } }));
        
        const data = await fetchFilePreview(fileId);
        
        // For Excel files, we need to handle the blob differently
        if (data?.type === 'excel') {
          // For now, show a message that Excel preview is not fully implemented
          setFilePreviewData(prev => ({ 
            ...prev, 
            [fileId]: { 
              error: 'Excel preview is not yet fully implemented. Please download the file to view it.' 
            } 
          }));
        } else {
          setFilePreviewData(prev => ({ ...prev, [fileId]: data }));
        }
      } catch (error) {
        console.error('Failed to fetch preview data:', error);
        setFilePreviewData(prev => ({ 
          ...prev, 
          [fileId]: { 
            error: `Failed to load preview: ${error instanceof Error ? error.message : 'Unknown error'}` 
          } 
        }));
      }
    }
  };

  // Fix type annotations for renderPreview function
  const renderPreview = (file: FileInfo) => {
    const data = filePreviewData[file.file_id];
    
    if (!data) return <div className="text-center py-4">Loading preview...</div>;
    if (data.loading) return <div className="text-center py-4">Loading preview...</div>;
    if (data.error) return <div className="text-red-600 py-4">{data.error}</div>;
    
    if (file.file_name.endsWith('.json')) {
      return (
        <div className="bg-gray-50 p-4 rounded-md overflow-auto max-h-96">
          <JsonView data={data} />
        </div>
      );
    } else if (file.file_name.endsWith('.xlsx') || file.file_name.endsWith('.xls')) {
      return (
        <div className="bg-gray-50 p-4 rounded-md overflow-auto max-h-96">
          <table className="min-w-full divide-y divide-gray-300">
            <thead>
              <tr className="bg-gray-100">
                {data.headers?.map((header, idx) => (
                  <th key={idx} className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows?.map((row, idx) => (
                <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                  {row.map((cell, cellIdx) => (
                    <td key={cellIdx} className="px-4 py-2 text-sm text-gray-900">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    
    return <div className="text-center py-4">No preview available for this file type</div>;
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
            <p className="font-medium">{job?.job_id}</p>
          </div>
          <div>
            <p className="text-gray-500 text-sm">Status</p>
            <p className="font-medium">
              <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full 
              ${job?.status === 'success' || job?.status === 'complete'
                  ? 'bg-green-100 text-green-800'
                  : job?.status === 'processing'
                    ? 'bg-blue-100 text-blue-800'
                    : 'bg-red-100 text-red-800'
                }`}>
                {job?.status}
              </span>
            </p>
          </div>
          <div>
            <p className="text-gray-500 text-sm">Original Filename</p>
            <p className="font-medium">{job?.original_filename}</p>
          </div>
          <div>
            <p className="text-gray-500 text-sm">Created At</p>
            <p className="font-medium">
              {job?.created_at ? new Date(job.created_at).toLocaleString() : ''}
            </p>
          </div>
          {job?.error_message && (
            <div className="col-span-2">
              <p className="text-gray-500 text-sm">Error Message</p>
              <p className="font-medium text-red-600">{job.error_message}</p>
            </div>
          )}
        </div>

        {job && (job.status === 'success' || job.status === 'complete') && files.length > 0 && (
          <div className="mt-6 pt-6 border-t border-gray-200">
            <h2 className="text-lg font-medium mb-4">Files</h2>
            <div className="space-y-6">
              {files.map(file => (
                <div key={file.file_id} className="border border-gray-200 rounded-lg overflow-hidden">
                  <div className="flex justify-between items-center p-4">
                    <div>
                      <p className="font-medium">{file.file_name}</p>
                      <p className="text-sm text-gray-500">
                        {file.file_type} • {(file.file_size / 1024).toFixed(2)} KB
                      </p>
                    </div>
                    <div className="flex space-x-2">
                      {(file.file_name.endsWith('.json') || file.file_name.endsWith('.xlsx') || file.file_name.endsWith('.xls')) && (
                        <button
                          onClick={() => togglePreview(file.file_id)}
                          className="bg-gray-100 text-gray-700 py-2 px-4 rounded hover:bg-gray-200"
                        >
                          {previewStates[file.file_id] ? 'Hide Preview' : 'Show Preview'}
                        </button>
                      )}
                      <a
                        href={getFileDownloadUrl(file.file_id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700"
                      >
                        Download
                      </a>
                    </div>
                  </div>
                  
                  {/* Preview section */}
                  {previewStates[file.file_id] && (
                    <div className="border-t border-gray-200">
                      {renderPreview(file)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {job?.status === 'processing' && (
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