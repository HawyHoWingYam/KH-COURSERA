'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Company } from '@/lib/api';
// Get base URL and port from config
const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? 'http://localhost:8000' 
  : 'http://localhost:8000';
  
// Extended API methods for admin functions
async function fetchCompanies(): Promise<Company[]> {
  const res = await fetch(`${API_BASE_URL}/companies`);
  if (!res.ok) throw new Error('Failed to fetch companies');
  return res.json();
}

async function createCompany(data: { company_name: string; company_code: string; active: boolean }): Promise<Company> {
  const res = await fetch(`${API_BASE_URL}/companies`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to create company');
  return res.json();
}

async function updateCompany(id: number, data: { company_name: string; company_code: string; active: boolean }): Promise<Company> {
  const res = await fetch(`${API_BASE_URL}/companies/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Failed to update company');
  return res.json();
}

async function deleteCompany(id: number): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/companies/${id}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete company');
}

export default function CompaniesPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [isCreating, setIsCreating] = useState(false);
  const [editingCompany, setEditingCompany] = useState<Company | null>(null);
  
  const [formData, setFormData] = useState({
    company_name: '',
    company_code: '',
    active: true
  });
  
  // Load companies on mount
  useEffect(() => {
    const loadCompanies = async () => {
      try {
        setIsLoading(true);
        const data = await fetchCompanies();
        setCompanies(data);
      } catch (err) {
        setError('Failed to load companies');
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };
    
    loadCompanies();
  }, []);
  
  // Handle form input changes
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target as HTMLInputElement;
    
    setFormData(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? (e.target as HTMLInputElement).checked : value
    }));
  };
  
  // Start editing a company
  const handleEdit = (company: Company) => {
    setEditingCompany(company);
    setFormData({
      company_name: company.company_name,
      company_code: company.company_code,
      active: company.active
    });
    setIsCreating(false);
  };
  
  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      if (editingCompany) {
        // Update existing company
        const updated = await updateCompany(editingCompany.company_id, formData);
        setCompanies(prev => 
          prev.map(c => c.company_id === editingCompany.company_id ? updated : c)
        );
        setEditingCompany(null);
      } else {
        // Create new company
        const created = await createCompany(formData);
        setCompanies(prev => [...prev, created]);
        setIsCreating(false);
      }
      
      // Reset form
      setFormData({
        company_name: '',
        company_code: '',
        active: true
      });
    } catch (err) {
      setError(`Failed to ${editingCompany ? 'update' : 'create'} company`);
      console.error(err);
    }
  };
  
  // Handle company deletion
  const handleDelete = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this company?')) {
      return;
    }
    
    try {
      await deleteCompany(id);
      setCompanies(prev => prev.filter(c => c.company_id !== id));
    } catch (err) {
      setError('Failed to delete company');
      console.error(err);
    }
  };
  
  // Cancel editing/creating
  const handleCancel = () => {
    setIsCreating(false);
    setEditingCompany(null);
    setFormData({
      company_name: '',
      company_code: '',
      active: true
    });
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Company Management</h1>
        {!isCreating && !editingCompany && (
          <button 
            onClick={() => setIsCreating(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            Add New Company
          </button>
        )}
      </div>
      
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}
      
      {/* Create/Edit Form */}
      {(isCreating || editingCompany) && (
        <div className="bg-white shadow-md rounded-lg p-6 mb-6">
          <h2 className="text-lg font-medium mb-4">
            {editingCompany ? 'Edit Company' : 'Create New Company'}
          </h2>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-gray-700 mb-2">Company Name</label>
              <input
                type="text"
                name="company_name"
                value={formData.company_name}
                onChange={handleInputChange}
                className="w-full border border-gray-300 rounded px-3 py-2 text-black"
                required
              />
            </div>
            
            <div>
              <label className="block text-gray-700 mb-2">Company Code</label>
              <input
                type="text"
                name="company_code"
                value={formData.company_code}
                onChange={handleInputChange}
                className="w-full border border-gray-300 rounded px-3 py-2 text-black"
                required
              />
            </div>
            
            <div className="flex items-center">
              <input
                type="checkbox"
                name="active"
                checked={formData.active}
                onChange={handleInputChange}
                className="mr-2"
              />
              <label className="text-gray-700">Active</label>
            </div>
            
            <div className="flex space-x-4">
              <button
                type="submit"
                className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
              >
                {editingCompany ? 'Update' : 'Create'}
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
      
      {/* Companies List */}
      {isLoading ? (
        <div className="text-center py-10">Loading companies...</div>
      ) : companies.length === 0 ? (
        <div className="text-center py-10">
          <p className="text-gray-500">No companies found</p>
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
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Code
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
              {companies.map((company) => (
                <tr key={company.company_id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {company.company_id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {company.company_name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {company.company_code}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      company.active 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {company.active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                    <button
                      onClick={() => handleEdit(company)}
                      className="text-indigo-600 hover:text-indigo-900 mr-4"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => handleDelete(company.company_id)}
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