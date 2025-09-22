'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { fetchDocumentTypes, fetchCompaniesForDocType, processBatch } from '@/lib/api';
import type { DocumentType, Company } from '@/lib/api';
import { MdZoomIn, MdZoomOut, MdRefresh } from 'react-icons/md';

export default function Upload() {
  const router = useRouter();
  const [documentTypes, setDocumentTypes] = useState<DocumentType[]>([]);
  const [selectedType, setSelectedType] = useState<number | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [selectedCompany, setSelectedCompany] = useState<number | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [mappingFile, setMappingFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
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
    const selectedFiles = Array.from(e.target.files || []);

    // Clear previous errors and preview
    setError('');
    
    // Clean up previous preview URL
    if (fileUrlRef.current) {
      URL.revokeObjectURL(fileUrlRef.current);
      fileUrlRef.current = null;
    }
    setPreviewUrl(null);

    // Check if files exist
    if (selectedFiles.length === 0) {
      setFiles([]);
      return;
    }

    // Check file sizes and types
    const validFiles: File[] = [];
    let totalSize = 0;
    
    for (const file of selectedFiles) {
      // Check individual file size
      if (file.size > MAX_FILE_SIZE) {
        setError(`File "${file.name}" size (${formatFileSize(file.size)}) exceeds the ${formatFileSize(MAX_FILE_SIZE)} limit`);
        e.target.value = '';
        return;
      }
      
      totalSize += file.size;
      
      // Check file type
      const validTypes = ['image/jpeg', 'image/png', 'application/pdf', 'application/zip'];
      const validExtensions = ['.jpg', '.jpeg', '.png', '.pdf', '.zip'];
      const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
      
      if (!validTypes.includes(file.type) && !validExtensions.includes(fileExtension)) {
        setError(`File "${file.name}" type not supported. Please upload images, PDFs, or ZIP files.`);
        e.target.value = '';
        return;
      }
      
      validFiles.push(file);
    }

    // Check total size (50MB limit for batch uploads)
    const BATCH_SIZE_LIMIT = 50 * 1024 * 1024; // 50MB
    if (totalSize > BATCH_SIZE_LIMIT) {
      setError(`Total file size (${formatFileSize(totalSize)}) exceeds the ${formatFileSize(BATCH_SIZE_LIMIT)} limit for batch uploads`);
      e.target.value = '';
      return;
    }

    // Create preview URL for first image file
    const firstImage = validFiles.find(f => f.type.startsWith('image/'));
    if (firstImage) {
      const url = URL.createObjectURL(firstImage);
      fileUrlRef.current = url;
      setPreviewUrl(url);
    }

    setFiles(validFiles);
  };

  const handleMappingFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    setError('');

    if (!selectedFile) {
      setMappingFile(null);
      return;
    }

    // Check file extension
    if (!selectedFile.name.toLowerCase().endsWith('.xlsx')) {
      setError('Mapping file must be an Excel (.xlsx) file');
      e.target.value = '';
      return;
    }

    // Check file size (max 10MB)
    if (selectedFile.size > MAX_FILE_SIZE) {
      setError(`Mapping file size (${formatFileSize(selectedFile.size)}) exceeds the ${formatFileSize(MAX_FILE_SIZE)} limit`);
      e.target.value = '';
      return;
    }

    setMappingFile(selectedFile);
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

    if (!selectedType || !selectedCompany || files.length === 0) {
      setError('Please select document type, company, and at least one file');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // Create the FormData object for unified batch processing
      const formData = new FormData();
      formData.append('doc_type_id', selectedType.toString());
      formData.append('company_id', selectedCompany.toString());
      
      // Add all files to the form data
      files.forEach((file, index) => {
        formData.append('files', file);
      });

      // Add mapping file if selected
      if (mappingFile) {
        formData.append('mapping_file', mappingFile);
      }
      
      // Process as unified batch (handles all file types)
      const result = await processBatch(formData);
      
      console.log('Batch upload completed:', result);
      
      // Store batch upload info for jobs page
      sessionStorage.setItem('pendingBatchUpload', JSON.stringify({
        batchId: result.batch_id,
        uploadType: result.upload_type,
        fileCount: result.file_count,
        fileNames: files.map(f => f.name),
        documentType: documentTypes.find(dt => dt.doc_type_id === selectedType)?.type_name || 'Unknown',
        timestamp: new Date().toISOString()
      }));

      // Navigate to jobs page
      router.push('/jobs');

    } catch (err) {
      setError('Failed to start upload');
      console.error(err);
    } finally {
      setIsLoading(false);
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
          <label className="block text-gray-700 mb-2">Document Files</label>
          <input
            type="file"
            accept="image/jpeg,image/png,application/pdf,application/zip,.zip"
            onChange={handleFileChange}
            className="w-full"
            multiple
            required
          />
          <p className="text-sm text-gray-500 mt-1">
            Supported formats: JPEG, JPG, PNG, PDF, ZIP. You can select multiple files for batch processing.
          </p>
          {files.length > 0 && (
            <div className="mt-3 p-3 bg-gray-50 rounded border">
              <p className="text-sm font-medium text-gray-700 mb-2">
                Selected files ({files.length}):
              </p>
              <div className="space-y-1">
                {files.map((file, index) => (
                  <div key={index} className="flex justify-between items-center text-sm">
                    <span className="text-gray-600">{file.name}</span>
                    <span className="text-gray-500">{formatFileSize(file.size)}</span>
                  </div>
                ))}
              </div>
              <p className="text-xs text-gray-500 mt-2">
                Total size: {formatFileSize(files.reduce((sum, f) => sum + f.size, 0))}
              </p>
            </div>
          )}
        </div>

        {/* Cost Allocation Mapping File */}
        <div>
          <label className="block text-gray-700 mb-2">
            Cost Allocation Mapping File 
            <span className="text-gray-500 text-sm">(Optional)</span>
          </label>
          <input
            type="file"
            accept=".xlsx"
            onChange={handleMappingFileChange}
            className="w-full"
          />
          <p className="text-sm text-gray-500 mt-1">
            Upload an Excel (.xlsx) file containing phone number to shop/department mappings for automatic cost allocation. 
            The file should contain multiple sheets (Phone, Broadband, CLP, Water, HKELE) with appropriate mapping data.
          </p>
          {mappingFile && (
            <div className="mt-3 p-3 bg-green-50 rounded border border-green-200">
              <p className="text-sm font-medium text-green-700 mb-1">
                Mapping file selected:
              </p>
              <div className="flex justify-between items-center text-sm">
                <span className="text-green-600">{mappingFile.name}</span>
                <span className="text-green-500">{formatFileSize(mappingFile.size)}</span>
              </div>
              <p className="text-xs text-green-600 mt-1">
                ✓ Cost allocation will be performed automatically after OCR processing
              </p>
            </div>
          )}
        </div>

        {/* File Preview Section with Zoom Controls */}
        {previewUrl && files.length > 0 && (
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