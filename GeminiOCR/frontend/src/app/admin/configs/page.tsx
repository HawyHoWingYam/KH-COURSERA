'use client';

import { useState, useEffect } from 'react';
import { DocumentType, Company } from '@/lib/api';
import SmartDeleteDialog from '@/components/ui/SmartDeleteDialog';

// Define ConfigType for document configurations
interface ConfigType {
    config_id: number;
    company_id: number;
    doc_type_id: number;
    prompt_path: string;
    schema_path: string;
    active: boolean;
    created_at: string;
    updated_at: string;
    company_name?: string;  // Joined from companies
    type_name?: string;     // Joined from document_types
    // Auto-mapping fields
    auto_mapping_enabled?: boolean;
    default_mapping_keys?: string[];
    }
// Get base URL and port from config
const API_BASE_URL = '/api';
  
// Extended API methods for admin functions
async function fetchConfigs(): Promise<ConfigType[]> {
    const res = await fetch(`${API_BASE_URL}/configs`);
    if (!res.ok) throw new Error('Failed to fetch configurations');
    return res.json();
}

async function createConfig(data: {
    company_id: number;
    doc_type_id: number;
    prompt_path: string;
    schema_path: string;
    active: boolean;
}): Promise<ConfigType> {
    const res = await fetch(`${API_BASE_URL}/configs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to create configuration');
    return res.json();
}

async function updateConfig(id: number, data: {
    prompt_path: string;
    schema_path: string;
    active: boolean;
}): Promise<ConfigType> {
    const res = await fetch(`${API_BASE_URL}/configs/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to update configuration');
    return res.json();
}

async function deleteConfig(id: number): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/configs/${id}`, {
        method: 'DELETE',
    });
    if (!res.ok) throw new Error('Failed to delete configuration');
}

async function uploadFile(file: File, path: string): Promise<string> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('path', path);

    const res = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        body: formData,
    });

    if (!res.ok) throw new Error('Failed to upload file');
    const data = await res.json();
    return data.file_path;
}

export default function ConfigsPage() {
    const [configs, setConfigs] = useState<ConfigType[]>([]);
    const [companies, setCompanies] = useState<Company[]>([]);
    const [documentTypes, setDocumentTypes] = useState<DocumentType[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState('');

    const [isCreating, setIsCreating] = useState(false);
    const [editingConfig, setEditingConfig] = useState<ConfigType | null>(null);

    const [formData, setFormData] = useState({
        company_id: 0,
        doc_type_id: 0,
        prompt_path: '',
        schema_path: '',
        active: true,
        // Auto-mapping fields
        auto_mapping_enabled: false,
        default_mapping_keys: [] as string[]
    });

    const [promptFile, setPromptFile] = useState<File | null>(null);
    const [schemaFile, setSchemaFile] = useState<File | null>(null);
    
    // Smart delete dialog state
    const [deleteDialog, setDeleteDialog] = useState<{
        isOpen: boolean;
        entity: { type: 'config'; id: number; name: string } | null;
    }>({
        isOpen: false,
        entity: null,
    });

    // Load configs, companies and document types on mount
    useEffect(() => {
        const loadData = async () => {
            try {
                setIsLoading(true);
                // These would be actual API calls in a real implementation
                const configsData = await fetchConfigs();
                const companiesRes = await fetch(`${API_BASE_URL}/companies`);
                const companiesData = await companiesRes.json();
                const docTypesRes = await fetch(`${API_BASE_URL}/document-types`);
                const docTypesData = await docTypesRes.json();

                setConfigs(configsData);
                setCompanies(companiesData);
                setDocumentTypes(docTypesData);
            } catch (err) {
                setError('Failed to load data');
                console.error(err);
            } finally {
                setIsLoading(false);
            }
        };

        loadData();
    }, []);

    // Handle form input changes
    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const { name, value, type } = e.target as HTMLInputElement;

        setFormData(prev => ({
            ...prev,
            [name]: type === 'checkbox'
                ? (e.target as HTMLInputElement).checked
                : name === 'company_id' || name === 'doc_type_id'
                    ? parseInt(value)
                    : value
        }));
    };

    // Handle default mapping keys changes
    const handleMappingKeyChange = (index: number, value: string) => {
        setFormData(prev => {
            const newKeys = [...prev.default_mapping_keys];
            newKeys[index] = value;
            return { ...prev, default_mapping_keys: newKeys };
        });
    };

    // Add new mapping key (max 3)
    const addMappingKey = () => {
        if (formData.default_mapping_keys.length < 3) {
            setFormData(prev => ({
                ...prev,
                default_mapping_keys: [...prev.default_mapping_keys, '']
            }));
        }
    };

    // Remove mapping key
    const removeMappingKey = (index: number) => {
        setFormData(prev => ({
            ...prev,
            default_mapping_keys: prev.default_mapping_keys.filter((_, i) => i !== index)
        }));
    };

    
    // Handle file selection
    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, fileType: 'prompt' | 'schema') => {
        if (e.target.files && e.target.files[0]) {
            if (fileType === 'prompt') {
                setPromptFile(e.target.files[0]);
            } else {
                setSchemaFile(e.target.files[0]);
            }
        }
    };

    // Start editing a config
    const handleEdit = async (config: ConfigType) => {
        setEditingConfig(config);

        // Load auto-mapping configuration
        let autoMappingData = {
            auto_mapping_enabled: false,
            default_mapping_keys: [] as string[]
        };

        try {
            const autoMappingRes = await fetch(`${API_BASE_URL}/companies/${config.company_id}/document-types/${config.doc_type_id}/auto-mapping-config`);
            if (autoMappingRes.ok) {
                autoMappingData = await autoMappingRes.json();
            }
        } catch (err) {
            console.warn('Failed to load auto-mapping configuration:', err);
        }

        setFormData({
            company_id: config.company_id,
            doc_type_id: config.doc_type_id,
            prompt_path: config.prompt_path,
            schema_path: config.schema_path,
            active: config.active,
            // Auto-mapping fields
            auto_mapping_enabled: autoMappingData.auto_mapping_enabled || false,
            default_mapping_keys: autoMappingData.default_mapping_keys || []
        });
        setIsCreating(false);
        setPromptFile(null);
        setSchemaFile(null);
    };

    
    // Handle form submission
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        try {
            const updatedFormData = { ...formData };

            // If files were uploaded, upload them first
            if (promptFile) {
                const company = companies.find(c => c.company_id === formData.company_id);
                const docType = documentTypes.find(dt => dt.doc_type_id === formData.doc_type_id);

                if (!company || !docType) {
                    throw new Error('Invalid company or document type');
                }

                // Use original filename - let backend handle uniqueness via S3 path structure
                const filename = promptFile.name;

                // NEW ID-BASED PATH FORMAT: document_type/{doc_type_id}/{company_id}/prompt/{filename}
                const promptPath = `document_type/${docType.doc_type_id}/${company.company_id}/prompt/${filename}`;
                updatedFormData.prompt_path = await uploadFile(promptFile, promptPath);
            }

            if (schemaFile) {
                const company = companies.find(c => c.company_id === formData.company_id);
                const docType = documentTypes.find(dt => dt.doc_type_id === formData.doc_type_id);

                if (!company || !docType) {
                    throw new Error('Invalid company or document type');
                }

                // Use original filename - let backend handle uniqueness via S3 path structure
                const filename = schemaFile.name;

                // NEW ID-BASED PATH FORMAT: document_type/{doc_type_id}/{company_id}/schema/{filename}
                const schemaPath = `document_type/${docType.doc_type_id}/${company.company_id}/schema/${filename}`;
                updatedFormData.schema_path = await uploadFile(schemaFile, schemaPath);
            }

            if (editingConfig) {
                // Update existing config
                const { prompt_path, schema_path, active } = updatedFormData;
                const updated = await updateConfig(editingConfig.config_id, {
                    prompt_path, schema_path, active
                });

                // Update auto-mapping configuration
                const autoMappingConfig = {
                    auto_mapping_enabled: formData.auto_mapping_enabled,
                    default_mapping_keys: formData.default_mapping_keys
                };

                const response = await fetch(`${API_BASE_URL}/companies/${editingConfig.company_id}/document-types/${editingConfig.doc_type_id}/auto-mapping-config`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(autoMappingConfig)
                });

                if (!response.ok) {
                    throw new Error('Failed to update auto-mapping configuration');
                }

                setConfigs(prev =>
                    prev.map(c => c.config_id === editingConfig.config_id ? updated : c)
                );
                setEditingConfig(null);
            } else {
                // Create new config
                const created = await createConfig(updatedFormData);

                // Set auto-mapping configuration for new config
                const autoMappingConfig = {
                    auto_mapping_enabled: formData.auto_mapping_enabled,
                    default_mapping_keys: formData.default_mapping_keys
                };

                const response = await fetch(`${API_BASE_URL}/companies/${formData.company_id}/document-types/${formData.doc_type_id}/auto-mapping-config`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(autoMappingConfig)
                });

                if (!response.ok) {
                    throw new Error('Failed to set auto-mapping configuration');
                }

                setConfigs(prev => [...prev, created]);
                setIsCreating(false);
            }

            // Reset form
            setFormData({
                company_id: 0,
                doc_type_id: 0,
                prompt_path: '',
                schema_path: '',
                active: true,
                // Auto-mapping fields
                auto_mapping_enabled: false,
                default_mapping_keys: [],
                cross_field_mappings: {}
            });
            setPromptFile(null);
            setSchemaFile(null);
        } catch (err) {
            setError(`Failed to ${editingConfig ? 'update' : 'create'} configuration`);
            console.error(err);
        }
    };

    // Handle config deletion - now uses smart delete dialog
    const handleDelete = (config: ConfigType) => {
        const configName = `${config.company_name || 'Unknown Company'} - ${config.type_name || 'Unknown Type'}`;
        setDeleteDialog({
            isOpen: true,
            entity: {
                type: 'config',
                id: config.config_id,
                name: configName,
            },
        });
    };

    // Handle successful deletion
    const handleDeleteSuccess = () => {
        setConfigs(prev => 
            prev.filter(c => c.config_id !== deleteDialog.entity?.id)
        );
        setError(''); // Clear any previous errors
    };

    // Close delete dialog
    const handleDeleteCancel = () => {
        setDeleteDialog({
            isOpen: false,
            entity: null,
        });
    };

    // Cancel editing/creating
    const handleCancel = () => {
        setIsCreating(false);
        setEditingConfig(null);
        setFormData({
            company_id: 0,
            doc_type_id: 0,
            prompt_path: '',
            schema_path: '',
            active: true,
            // Auto-mapping fields
            auto_mapping_enabled: false,
            default_mapping_keys: [],
            cross_field_mappings: {}
        });
        setPromptFile(null);
        setSchemaFile(null);
    };

    // Get company and document type names for display
    const getCompanyName = (id: number) => {
        const company = companies.find(c => c.company_id === id);
        return company?.company_name || 'Unknown';
    };

    const getDocTypeName = (id: number) => {
        const docType = documentTypes.find(dt => dt.doc_type_id === id);
        return docType?.type_name || 'Unknown';
    };

    // Helper function to display S3 paths in a user-friendly way
    const formatFilePath = (path: string) => {
        if (path.startsWith('s3://')) {
            // Extract filename from S3 URI: s3://prompts/company/doctype/filename.txt
            const parts = path.split('/');
            const filename = parts[parts.length - 1];
            const fileType = parts.includes('prompts') ? '📄 Prompt' : '🔧 Schema';
            return `${fileType}: ${filename}`;
        }
        // For local paths, show the filename part
        const parts = path.split('/');
        return parts[parts.length - 1] || path;
    };

    // Download file function
    const downloadFile = async (configId: number, fileType: 'prompt' | 'schema') => {
        try {
            const response = await fetch(`${API_BASE_URL}/configs/${configId}/download/${fileType}`);
            
            if (!response.ok) {
                throw new Error(`Failed to download ${fileType} file`);
            }

            // Get the filename from the response headers or use a default
            const contentDisposition = response.headers.get('content-disposition');
            let filename = `${fileType}.${fileType === 'prompt' ? 'txt' : 'json'}`;
            
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
                if (filenameMatch && filenameMatch[1]) {
                    filename = filenameMatch[1].replace(/['"]/g, '');
                }
            }

            // Create blob and download
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

        } catch (err) {
            setError(`Failed to download ${fileType} file`);
            console.error(err);
        }
    };

    return (
        <div>
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold">Document Configuration Management</h1>
                {!isCreating && !editingConfig && (
                    <button
                        onClick={() => setIsCreating(true)}
                        className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                    >
                        Add New Configuration
                    </button>
                )}
            </div>

            {error && (
                <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
                    {error}
                </div>
            )}

            {/* Create/Edit Form */}
            {(isCreating || editingConfig) && (
                <div className="bg-white shadow-md rounded-lg p-6 mb-6">
                    <h2 className="text-lg font-medium mb-4">
                        {editingConfig ? 'Edit Configuration' : 'Create New Configuration'}
                    </h2>

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <label className="block text-gray-700 mb-2">Company</label>
                                <select
                                    name="company_id"
                                    value={formData.company_id}
                                    onChange={handleInputChange}
                                    className="w-full border border-gray-300 rounded px-3 py-2"
                                    required
                                    disabled={!!editingConfig}
                                >
                                    <option value="">Select Company</option>
                                    {companies.map(company => (
                                        <option key={company.company_id} value={company.company_id}>
                                            {company.company_name}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div>
                                <label className="block text-gray-700 mb-2">Document Type</label>
                                <select
                                    name="doc_type_id"
                                    value={formData.doc_type_id}
                                    onChange={handleInputChange}
                                    className="w-full border border-gray-300 rounded px-3 py-2"
                                    required
                                    disabled={!!editingConfig}
                                >
                                    <option value="">Select Document Type</option>
                                    {documentTypes.map(docType => (
                                        <option key={docType.doc_type_id} value={docType.doc_type_id}>
                                            {docType.type_name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        <div>
                            <label className="block text-gray-700 mb-2">Prompt File(txt)</label>
                            {editingConfig && !promptFile ? (
                                <div className="flex items-center mb-2">
                                    <span className="text-gray-600 mr-2 text-sm" title={formData.prompt_path}>
                                        Current: {formatFilePath(formData.prompt_path)}
                                    </span>
                                    <button
                                        type="button"
                                        onClick={() => document.getElementById('prompt_file')?.click()}
                                        className="text-blue-600 hover:text-blue-800 text-sm mr-2"
                                    >
                                        Replace
                                    </button>
                                    <span className="text-gray-400 text-sm mr-2">|</span>
                                    <button
                                        type="button"
                                        onClick={() => downloadFile(editingConfig.config_id, 'prompt')}
                                        className="text-green-600 hover:text-green-800 text-sm"
                                    >
                                        Download
                                    </button>
                                </div>
                            ) : null}

                            <input
                                id="prompt_file"
                                type="file"
                                accept=".txt"
                                onChange={(e) => handleFileChange(e, 'prompt')}
                                className="w-full border border-gray-300 rounded px-3 py-2"
                                required={isCreating}
                                style={{ display: editingConfig && !promptFile ? 'none' : 'block' }}
                            />
                            {promptFile && (
                                <p className="mt-1 text-sm text-green-600">
                                    Selected:                  {promptFile.name}
                                </p>
                            )}
                        </div>

                        <div>
                            <label className="block text-gray-700 mb-2">Schema File(json)</label>
                            {editingConfig && !schemaFile ? (
                                <div className="flex items-center mb-2">
                                    <span className="text-gray-600 mr-2 text-sm" title={formData.schema_path}>
                                        Current: {formatFilePath(formData.schema_path)}
                                    </span>
                                    <button
                                        type="button"
                                        onClick={() => document.getElementById('schema_file')?.click()}
                                        className="text-blue-600 hover:text-blue-800 text-sm mr-2"
                                    >
                                        Replace
                                    </button>
                                    <span className="text-gray-400 text-sm mr-2">|</span>
                                    <button
                                        type="button"
                                        onClick={() => downloadFile(editingConfig.config_id, 'schema')}
                                        className="text-green-600 hover:text-green-800 text-sm"
                                    >
                                        Download
                                    </button>
                                </div>
                            ) : null}

                            <input
                                id="schema_file"
                                type="file"
                                accept=".json"
                                onChange={(e) => handleFileChange(e, 'schema')}
                                className="w-full border border-gray-300 rounded px-3 py-2"
                                required={isCreating}
                                style={{ display: editingConfig && !schemaFile ? 'none' : 'block' }}
                            />
                            {schemaFile && (
                                <p className="mt-1 text-sm text-green-600">
                                    Selected: {schemaFile.name}
                                </p>
                            )}
                        </div>

                        {/* Auto-Mapping Configuration Section */}
                        <div className="border-t pt-6">
                            <h3 className="text-lg font-medium mb-4 text-gray-900">Auto-Mapping Configuration</h3>

                            {/* Enable Auto-Mapping Toggle */}
                            <div className="flex items-center mb-4">
                                <input
                                    type="checkbox"
                                    id="auto_mapping_enabled"
                                    name="auto_mapping_enabled"
                                    checked={formData.auto_mapping_enabled}
                                    onChange={handleInputChange}
                                    className="mr-2"
                                />
                                <label htmlFor="auto_mapping_enabled" className="text-gray-700">
                                    Enable Auto-Mapping
                                </label>
                                <span className="ml-2 text-sm text-gray-500">
                                    (Automatically apply mapping keys when orders have no user-configured keys)
                                </span>
                            </div>

                            {/* Default Mapping Keys (1-3 priority) */}
                            {formData.auto_mapping_enabled && (
                                <div className="mb-4">
                                    <label className="block text-gray-700 mb-2">
                                        Default Mapping Keys (Priority 1-3)
                                    </label>
                                    <div className="space-y-2">
                                        {formData.default_mapping_keys.map((key, index) => (
                                            <div key={index} className="flex items-center space-x-2">
                                                <span className="text-sm text-gray-500 w-16">
                                                    Priority {index + 1}:
                                                </span>
                                                <input
                                                    type="text"
                                                    value={key}
                                                    onChange={(e) => handleMappingKeyChange(index, e.target.value)}
                                                    placeholder={`Mapping key ${index + 1}`}
                                                    className="flex-1 border border-gray-300 rounded px-3 py-2"
                                                />
                                                <button
                                                    type="button"
                                                    onClick={() => removeMappingKey(index)}
                                                    className="text-red-600 hover:text-red-800 text-sm px-2 py-1"
                                                >
                                                    Remove
                                                </button>
                                            </div>
                                        ))}
                                        {formData.default_mapping_keys.length < 3 && (
                                            <button
                                                type="button"
                                                onClick={addMappingKey}
                                                className="text-blue-600 hover:text-blue-800 text-sm"
                                            >
                                                + Add Mapping Key ({formData.default_mapping_keys.length}/3)
                                            </button>
                                        )}
                                    </div>
                                </div>
                            )}

                            {/* Cross-Field Mappings functionality has been removed - system now uses only Default Mapping Keys */}
                            {/* {formData.auto_mapping_enabled && (
                                <div className="mb-4">
                                    <label className="block text-gray-700 mb-2">
                                        Cross-Field Mappings
                                    </label>
                                    <p className="text-sm text-gray-500 mb-3">
                                        Map OCR field names to different mapping field names (e.g., "service_number" → "PHONE")
                                    </p>
                                    <div className="space-y-2">
                                        {Object.entries(formData.cross_field_mappings).map(([ocrField, mappingField], index) => {
                                            const isTemporary = ocrField.startsWith('temp_');
                                            const hasEmptyFields = !ocrField.trim() || !mappingField.trim();
                                            const hasValidationError = isTemporary || hasEmptyFields;

                                            return (
                                            <div key={index} className="space-y-1">
                                                <div className="flex items-center space-x-2">
                                                    <input
                                                        type="text"
                                                        value={ocrField}
                                                        onChange={(e) => handleCrossFieldMappingChange(e.target.value, mappingField, ocrField)}
                                                        placeholder="OCR field name"
                                                        className={`flex-1 border rounded px-3 py-2 ${
                                                            isTemporary || !ocrField.trim()
                                                                ? 'border-red-300 bg-red-50'
                                                                : 'border-gray-300'
                                                        }`}
                                                    />
                                                    <span className="text-gray-500">→</span>
                                                    <input
                                                        type="text"
                                                        value={mappingField}
                                                        onChange={(e) => handleCrossFieldMappingChange(ocrField, e.target.value)}
                                                        placeholder="Mapping field name"
                                                        className={`flex-1 border rounded px-3 py-2 ${
                                                            !mappingField.trim()
                                                                ? 'border-red-300 bg-red-50'
                                                                : 'border-gray-300'
                                                        }`}
                                                    />
                                                    <button
                                                        type="button"
                                                        onClick={() => removeCrossFieldMapping(ocrField)}
                                                        className="text-red-600 hover:text-red-800 text-sm px-2 py-1"
                                                    >
                                                        Remove
                                                    </button>
                                                </div>
                                                {hasValidationError && (
                                                    <div className="text-xs text-red-600 ml-1">
                                                        {isTemporary && "Please enter a real OCR field name"}
                                                        {!isTemporary && hasEmptyFields && "Both fields are required"}
                                                    </div>
                                                )}
                                            </div>
                                            );
                                        })}
                                        <button
                                            type="button"
                                            onClick={addCrossFieldMapping}
                                            className="text-blue-600 hover:text-blue-800 text-sm"
                                        >
                                            + Add Cross-Field Mapping
                                        </button>
                                    </div>
                                </div>
                            )} */}
                        </div>

                        <div className="flex items-center">
                            <input
                                type="checkbox"
                                id="active"
                                name="active"
                                checked={formData.active}
                                onChange={handleInputChange}
                                className="mr-2"
                            />
                            <label htmlFor="active" className="text-gray-700">Active</label>
                        </div>

                        <div className="flex space-x-4">
                            <button
                                type="submit"
                                className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
                            >
                                {editingConfig ? 'Update' : 'Create'}
                            </button>
                            <button
                                type="button"
                                onClick={handleCancel}
                                className="bg-gray-300 text-gray-800 px-4 py-2 rounded hover:bg-gray-400"
                            >
                                Cancel
                            </button>
                        </div>
                    </form>
                </div>
            )}

            {/* Configurations List */}
            {isLoading ? (
                <div className="text-center py-10">Loading configurations...</div>
            ) : configs.length === 0 ? (
                <div className="text-center py-10">
                    <p className="text-gray-500">No configurations found</p>
                </div>
            ) : (
                <div className="bg-white shadow-md rounded-lg overflow-hidden">
                    <table className="min-w-full divide-y divide-gray-200">
                        <thead className="bg-gray-50">
                            <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    ID
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Company
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Document Type
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Prompt Path
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Schema Path
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Status
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                    Actions
                                </th>
                            </tr>
                        </thead>
                        <tbody className="bg-white divide-y divide-gray-200">
                            {configs.map((config) => (
                                <tr key={config.config_id}>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                        {config.config_id}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                        {getCompanyName(config.company_id)}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                        {getDocTypeName(config.doc_type_id)}
                                    </td>
                                    <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate" title={config.prompt_path}>
                                        {formatFilePath(config.prompt_path)}
                                    </td>
                                    <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate" title={config.schema_path}>
                                        {formatFilePath(config.schema_path)}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${config.active
                                                ? 'bg-green-100 text-green-800'
                                                : 'bg-red-100 text-red-800'
                                            }`}>
                                            {config.active ? 'Active' : 'Inactive'}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                                        <button
                                            onClick={() => handleEdit(config)}
                                            className="text-indigo-600 hover:text-indigo-900 mr-4"
                                        >
                                            Edit
                                        </button>
                                        <button
                                            onClick={() => handleDelete(config)}
                                            className="text-red-600 hover:text-red-900"
                                        >
                                            Delete
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {/* Smart Delete Dialog */}
            <SmartDeleteDialog
                isOpen={deleteDialog.isOpen}
                onClose={handleDeleteCancel}
                onSuccess={handleDeleteSuccess}
                entity={deleteDialog.entity!}
            />
        </div>
    );
}