'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function Upload() {
  const router = useRouter();
  const [documentTypes, setDocumentTypes] = useState<string[]>([]);
  const [selectedType, setSelectedType] = useState('');
  const [providers, setProviders] = useState<string[]>([]);
  const [selectedProvider, setSelectedProvider] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    // Fetch document types when component mounts
    fetch('http://localhost:8000/document-types')
      .then(response => response.json())
      .then(data => setDocumentTypes(data.document_types))
      .catch(err => setError('Failed to load document types'));
  }, []);

  useEffect(() => {
    // Fetch providers when document type changes
    if (selectedType) {
      fetch(`http://localhost:8000/document-types/${selectedType}/providers`)
        .then(response => response.json())
        .then(data => setProviders(data.providers))
        .catch(err => setError('Failed to load providers'));
    } else {
      setProviders([]);
    }
    setSelectedProvider('');
  }, [selectedType]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedType || !selectedProvider || !file) {
      setError('Please select document type, provider, and file');
      return;
    }

    setIsLoading(true);
    setError('');

    const formData = new FormData();
    formData.append('document_type', selectedType);
    formData.append('provider', selectedProvider);
    formData.append('file', file);

    try {
      const response = await fetch('http://localhost:8000/process', {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) {
        throw new Error(`Error: ${response.status}`);
      }
      
      const result = await response.json();
      router.push(`/jobs/${result.job_id}`);
    } catch (err) {
      setError('Failed to upload document. Please try again.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto bg-white p-6 rounded-lg shadow-md">
      <h1 className="text-2xl font-bold mb-6">Upload Document</h1>
      
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}
      
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-gray-700 mb-2">Document Type</label>
          <select
            className="w-full border border-gray-300 rounded px-3 py-2"
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            required
          >
            <option value="">Select Document Type</option>
            {documentTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
        
        <div>
          <label className="block text-gray-700 mb-2">Provider</label>
          <select
            className="w-full border border-gray-300 rounded px-3 py-2"
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value)}
            disabled={!selectedType}
            required
          >
            <option value="">Select Provider</option>
            {providers.map((provider) => (
              <option key={provider} value={provider}>
                {provider}
              </option>
            ))}
          </select>
        </div>
        
        <div>
          <label className="block text-gray-700 mb-2">Document File</label>
          <input
            type="file"
            accept="image/jpeg,image/png,application/pdf"
            onChange={handleFileChange}
            className="w-full"
            required
          />
          <p className="text-sm text-gray-500 mt-1">
            Supported formats: JPEG, PNG, PDF
          </p>
        </div>
        
        <div className="pt-4">
          <button
            type="submit"
            className="bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 disabled:bg-blue-300"
            disabled={isLoading}
          >
            {isLoading ? 'Processing...' : 'Upload and Process'}
          </button>
        </div>
      </form>
    </div>
  );
}