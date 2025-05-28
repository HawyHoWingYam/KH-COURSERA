'use client';

import { useState, useEffect } from 'react';
import { DocumentType, Company, FileInfo } from '@/lib/api';

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
}
// Get base URL and port from config
const API_BASE_URL = `http://${process.env.API_BASE_URL || 'localhost'}:${process.env.PORT || 8000}`;

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
        active: true
    });

    const [promptFile, setPromptFile] = useState<File | null>(null);
    const [schemaFile, setSchemaFile] = useState<File | null>(null);

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
    const handleEdit = (config: ConfigType) => {
        setEditingConfig(config);
        setFormData({
            company_id: config.company_id,
            doc_type_id: config.doc_type_id,
            prompt_path: config.prompt_path,
            schema_path: config.schema_path,
            active: config.active
        });
        setIsCreating(false);
        setPromptFile(null);
        setSchemaFile(null);
    };

    // Handle form submission
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        try {
            let updatedFormData = { ...formData };

            // If files were uploaded, upload them first
            if (promptFile) {
                const company = companies.find(c => c.company_id === formData.company_id);
                const docType = documentTypes.find(dt => dt.doc_type_id === formData.doc_type_id);

                if (!company || !docType) {
                    throw new Error('Invalid company or document type');
                }

                const promptPath = `document_type/${docType.type_code}/${company.company_code}/prompt/${promptFile.name}`;
                updatedFormData.prompt_path = await uploadFile(promptFile, promptPath);
            }

            if (schemaFile) {
                const company = companies.find(c => c.company_id === formData.company_id);
                const docType = documentTypes.find(dt => dt.doc_type_id === formData.doc_type_id);

                if (!company || !docType) {
                    throw new Error('Invalid company or document type');
                }

                const schemaPath = `document_type/${docType.type_code}/${company.company_code}/schema/${schemaFile.name}`;
                updatedFormData.schema_path = await uploadFile(schemaFile, schemaPath);
            }

            if (editingConfig) {
                // Update existing config
                const { prompt_path, schema_path, active } = updatedFormData;
                const updated = await updateConfig(editingConfig.config_id, {
                    prompt_path, schema_path, active
                });
                setConfigs(prev =>
                    prev.map(c => c.config_id === editingConfig.config_id ? updated : c)
                );
                setEditingConfig(null);
            } else {
                // Create new config
                const created = await createConfig(updatedFormData);
                setConfigs(prev => [...prev, created]);
                setIsCreating(false);
            }

            // Reset form
            setFormData({
                company_id: 0,
                doc_type_id: 0,
                prompt_path: '',
                schema_path: '',
                active: true
            });
            setPromptFile(null);
            setSchemaFile(null);
        } catch (err) {
            setError(`Failed to ${editingConfig ? 'update' : 'create'} configuration`);
            console.error(err);
        }
    };

    // Handle config deletion
    const handleDelete = async (id: number) => {
        if (!window.confirm('Are you sure you want to delete this configuration?')) {
            return;
        }

        try {
            await deleteConfig(id);
            setConfigs(prev => prev.filter(c => c.config_id !== id));
        } catch (err) {
            setError('Failed to delete configuration');
            console.error(err);
        }
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
            active: true
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
                            <label className="block text-gray-700 mb-2">Prompt File</label>
                            {editingConfig && !promptFile ? (
                                <div className="flex items-center mb-2">
                                    <span className="text-gray-600 mr-2">{formData.prompt_path}</span>
                                    <button
                                        type="button"
                                        onClick={() => document.getElementById('prompt_file')?.click()}
                                        className="text-blue-600 hover:text-blue-800 text-sm"
                                    >
                                        Replace
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
                            <label className="block text-gray-700 mb-2">Schema File</label>
                            {editingConfig && !schemaFile ? (
                                <div className="flex items-center mb-2">
                                    <span className="text-gray-600 mr-2">{formData.schema_path}</span>
                                    <button
                                        type="button"
                                        onClick={() => document.getElementById('schema_file')?.click()}
                                        className="text-blue-600 hover:text-blue-800 text-sm"
                                    >
                                        Replace
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
                                    <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">
                                        {config.prompt_path}
                                    </td>
                                    <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">
                                        {config.schema_path}
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
                                            onClick={() => handleDelete(config.config_id)}
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
        </div>
    );
}