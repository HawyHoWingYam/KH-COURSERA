'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { fetchDocumentTypes, fetchCompaniesForDocType, processDocument, processZipFile } from '@/lib/api';
import type { DocumentType, Company } from '@/lib/api';
import { MdZoomIn, MdZoomOut, MdRefresh } from 'react-icons/md';

export default function Upload() {
  const router = useRouter();
  const [documentTypes, setDocumentTypes] = useState<DocumentType[]>([]);
  const [selectedType, setSelectedType] = useState<number | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<number | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const fileUrlRef = useRef<string | null>(null);

  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB in bytes

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

  // Clean up object URLs when component unmounts
  useEffect(() => {
    const currentFileUrl = fileUrlRef.current;
    return () => {
      if (currentFileUrl) {
        URL.revokeObjectURL(currentFileUrl);
      }
    };
  }, []);

  const handleDocTypeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = parseInt(e.target.value);
    setSelectedType(isNaN(value) ? null : value);
  };

  const handleCompanyChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = parseInt(e.target.value);
    setSelectedCompany(isNaN(value) ? null : value);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];

    // Clear previous errors and preview
    setError('');
    
    // Clean up previous preview URL
    if (fileUrlRef.current) {
      URL.revokeObjectURL(fileUrlRef.current);
      fileUrlRef.current = null;
    }
    setPreviewUrl(null);

    // Check if file exists
    if (!selectedFile) {
      setFile(null);
      return;
    }

    // Check file size
    if (selectedFile.size > MAX_FILE_SIZE) {
      setError(`File size (${formatFileSize(selectedFile.size)}) exceeds the ${formatFileSize(MAX_FILE_SIZE)} limit`);
      setFile(null);
      // Reset the file input
      e.target.value = '';
      return;
    }

    // Create preview URL for image files
    if (selectedFile.type.startsWith('image/')) {
      const url = URL.createObjectURL(selectedFile);
      fileUrlRef.current = url;
      setPreviewUrl(url);
    }

    setFile(selectedFile);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' bytes';
    else if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    else return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  // Function to determine if file is PDF
  const isPDF = (fileName: string) => {
    return fileName?.toLowerCase().endsWith('.pdf');
  };

  // Zoom control functions
  const zoomIn = () => {
    setZoomLevel(prev => Math.min(prev + 0.25, 3)); // Max zoom 3x
  };

  const zoomOut = () => {
    setZoomLevel(prev => Math.max(prev - 0.25, 0.5)); // Min zoom 0.5x
  };

  const resetZoom = () => {
    setZoomLevel(1);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedType || !selectedCompany || !file) {
      setError('Please select document type, company, and file');
      return;
    }

    try {
      // Create the FormData object
      const formData = new FormData();
      formData.append('doc_type_id', selectedType.toString());
      formData.append('company_id', selectedCompany.toString());
      
      // Check if file is a ZIP (batch job) or individual file
      if (file.type === 'application/zip' || file.name.toLowerCase().endsWith('.zip')) {
        formData.append('zip_file', file);
        formData.append('uploader_user_id', '1');
        
        // Process as ZIP batch
        processZipFile(formData)
          .then(result => {
            console.log('ZIP upload completed in background:', result);
          })
          .catch(err => {
            console.error('Background ZIP upload failed:', err);
          });
        
        // Store batch upload info
        sessionStorage.setItem('pendingBatchUpload', JSON.stringify({
          fileName: file.name,
          documentType: documentTypes.find(dt => dt.doc_type_id === selectedType)?.type_name || 'Unknown',
          timestamp: new Date().toISOString()
        }));
      } else {
        // Process as single document (existing code)
        formData.append('document', file);
        
        processDocument(formData)
          .then(result => {
            console.log('Upload completed in background:', result);
          })
          .catch(err => {
            console.error('Background upload failed:', err);
          });
        
        // Store upload info for jobs page
        sessionStorage.setItem('pendingUpload', JSON.stringify({
          fileName: file.name,
          documentType: documentTypes.find(dt => dt.doc_type_id === selectedType)?.type_name || 'Unknown',
          timestamp: new Date().toISOString()
        }));
      }

      // Navigate to jobs page
      router.push('/jobs');

    } catch (err) {
      setError('Failed to start upload');
      console.error(err);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Upload Document</h1>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
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
            accept="image/jpeg,image/png,application/pdf,application/zip,.zip"
            onChange={handleFileChange}
            className="w-full"
            required
          />
          <p className="text-sm text-gray-500 mt-1">
            Supported formats: JPEG, JPG, PNG, PDF, ZIP (contains multiple images)
          </p>
        </div>

        {/* File Preview Section with Zoom Controls */}
        {previewUrl && file && (
          <div className="my-4">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-lg font-medium">File Preview</h3>
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={zoomOut}
                  className="p-2 rounded-full bg-gray-100 hover:bg-gray-200"
                  title="Zoom Out"
                >
                  <MdZoomOut size={18} />
                </button>
                <span className="text-sm font-medium">
                  {Math.round(zoomLevel * 100)}%
                </span>
                <button
                  type="button"
                  onClick={zoomIn}
                  className="p-2 rounded-full bg-gray-100 hover:bg-gray-200"
                  title="Zoom In"
                >
                  <MdZoomIn size={18} />
                </button>
                <button
                  type="button"
                  onClick={resetZoom}
                  className="p-2 rounded-full bg-gray-100 hover:bg-gray-200 ml-2"
                  title="Reset Zoom"
                >
                  <MdRefresh size={18} />
                </button>
              </div>
            </div>

            <div className="border rounded-md overflow-hidden max-h-[500px]">
              {isPDF(file.name) ? (
                <div>
                  <object
                    data={`${previewUrl}#zoom=${zoomLevel * 100}`}
                    type="application/pdf"
                    className="w-full h-[500px]"
                  >
                    <p>PDF preview not available. Please download to view.</p>
                  </object>
                  <p className="text-xs text-gray-500 mt-1 text-center">
                    Note: PDF zoom controls may vary by browser
                  </p>
                </div>
              ) : (
                <div className="overflow-auto max-h-[500px] max-w-full" style={{ position: 'relative' }}>
                  <div style={{
                    minHeight: '100%',
                    minWidth: '100%',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    position: 'relative'
                  }}>
                    <Image
                      src={previewUrl}
                      alt="File preview"
                      width={500}
                      height={500}
                      style={{
                        transform: `scale(${zoomLevel})`,
                        transformOrigin: 'center center',
                        maxWidth: zoomLevel <= 1 ? '100%' : 'none',
                        transition: 'transform 0.2s ease',
                        width: 'auto',
                        height: 'auto'
                      }}
                      unoptimized={true}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

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