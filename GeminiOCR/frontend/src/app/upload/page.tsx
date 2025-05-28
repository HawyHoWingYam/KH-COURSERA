'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { fetchDocumentTypes, fetchCompaniesForDocType, processDocument } from '@/lib/api';
import type { DocumentType, Company } from '@/lib/api';

export default function Upload() {
  const router = useRouter();
  const [documentTypes, setDocumentTypes] = useState<DocumentType[]>([]);
  const [selectedType, setSelectedType] = useState<number | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  // Fetch document types on mount
  useEffect(() => {
    const loadDocumentTypes = async () => {
      try {
        const types = await fetchDocumentTypes();
        setDocumentTypes(types);
      } catch (err) {
        setError('Upload : Failed to load document types');
        console.error(err);
      }
    };

    loadDocumentTypes();
  }, []);

  // Fetch companies when document type changes
  useEffect(() => {
    const loadCompanies = async () => {
      if (!selectedType) {
        setCompanies([]);
        return;
      }

      try {
        const companiesData = await fetchCompaniesForDocType(selectedType);
        setCompanies(companiesData);
      } catch (err) {
        setError('Failed to load companies for the selected document type');
        console.error(err);
      }
    };

    loadCompanies();
    setSelectedCompany(null);
  }, [selectedType]);

  const handleDocTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = parseInt(e.target.value);
    setSelectedType(isNaN(value) ? null : value);
  };

  const handleCompanyChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = parseInt(e.target.value);
    setSelectedCompany(isNaN(value) ? null : value);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedType || !selectedCompany || !file) {
      setError('Please select document type, company, and file');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      const formData = new FormData();
      //formData.append('file', file);
      formData.append('document', file);
      formData.append('doc_type_id', selectedType.toString());
      formData.append('company_id', selectedCompany.toString());
      const job = await processDocument(formData);
      router.push(`/jobs/${job.job_id}`);
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
            value={selectedType || ''}
            onChange={handleDocTypeChange}
            required
          >
            <option value="">Select Document Type</option>
            {documentTypes.map((type) => (
              <option key={type.doc_type_id} value={type.doc_type_id}>
                {type.type_name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-gray-700 mb-2">Company</label>
          <select
            className="w-full border border-gray-300 rounded px-3 py-2"
            value={selectedCompany || ''}
            onChange={handleCompanyChange}
            disabled={!selectedType || companies.length === 0}
            required
          >
            <option value="">Select Company</option>
            {companies.map((company) => (
              <option key={company.company_id} value={company.company_id}>
                {company.company_name}
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