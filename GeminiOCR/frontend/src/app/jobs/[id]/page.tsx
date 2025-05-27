'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';

interface JobDetails {
  status: string;
  document_type?: string;
  provider?: string;
  result_path?: string;
  message?: string;
}

export default function JobDetails() {
  const params = useParams();
  const jobId = params.id as string;
  
  const [jobDetails, setJobDetails] = useState<JobDetails | null>(null);
  const [wsMessages, setWsMessages] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  
  const wsRef = useRef<WebSocket | null>(null);

  // Fetch job details initially
  useEffect(() => {
    fetch(`http://localhost:8000/jobs/${jobId}`)
      .then(response => response.json())
      .then(data => {
        setJobDetails(data);
        setIsLoading(false);
      })
      .catch(err => {
        setError('Failed to load job details');
        setIsLoading(false);
      });
      
    return () => {
      // Cleanup WebSocket on unmount
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [jobId]);

  // Connect to WebSocket if job is processing
  useEffect(() => {
    if (jobDetails?.status === 'processing') {
      // Close existing connection if any
      if (wsRef.current) {
        wsRef.current.close();
      }

      // Connect to WebSocket
      wsRef.current = new WebSocket(`ws://localhost:8000/ws/${jobId}`);
      
      wsRef.current.onopen = () => {
        setWsMessages(prev => [...prev, 'WebSocket connection established']);
      };
      
      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setWsMessages(prev => [...prev, `${data.message} (${data.status})`]);
          
          // If status is updated to success/error, refresh job details
          if (data.status === 'success' || data.status === 'error' || data.status === 'warning') {
            fetch(`http://localhost:8000/jobs/${jobId}`)
              .then(response => response.json())
              .then(data => setJobDetails(data))
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
  }, [jobId, jobDetails?.status]);

  // Handle download
  const handleDownload = () => {
    window.open(`http://localhost:8000/download/${jobId}`, '_blank');
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

  if (!jobDetails) {
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
            <p className="font-medium">{jobId}</p>
          </div>
          <div>
            <p className="text-gray-500 text-sm">Status</p>
            <p className="font-medium">
              <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${
                jobDetails.status === 'complete' 
                  ? 'bg-green-100 text-green-800' 
                  : jobDetails.status === 'processing' 
                  ? 'bg-blue-100 text-blue-800'
                  : 'bg-red-100 text-red-800'
              }`}>
                {jobDetails.status}
              </span>
            </p>
          </div>
          {jobDetails.document_type && (
            <div>
              <p className="text-gray-500 text-sm">Document Type</p>
              <p className="font-medium">{jobDetails.document_type}</p>
            </div>
          )}
          {jobDetails.provider && (
            <div>
              <p className="text-gray-500 text-sm">Provider</p>
              <p className="font-medium">{jobDetails.provider}</p>
            </div>
          )}
          {jobDetails.message && (
            <div className="col-span-2">
              <p className="text-gray-500 text-sm">Message</p>
              <p className="font-medium">{jobDetails.message}</p>
            </div>
          )}
        </div>

        {jobDetails.status === 'complete' && (
          <div className="mt-6 pt-6 border-t border-gray-200">
            <button
              onClick={handleDownload}
              className="bg-green-600 text-white py-2 px-4 rounded hover:bg-green-700"
            >
              Download Results
            </button>
          </div>
        )}
      </div>

      {jobDetails.status === 'processing' && (
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