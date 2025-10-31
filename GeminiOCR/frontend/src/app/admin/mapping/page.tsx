'use client';

import { useEffect, useMemo, useState } from 'react';
import type { Company, DocumentType } from '@/lib/api';

const API_BASE_URL = '/api';

type MappingItemType = 'single_source' | 'multi_source';

interface MappingTemplate {
  template_id: number;
  template_name: string;
  item_type: MappingItemType;
  company_id: number | null;
  doc_type_id: number | null;
  priority: number;
  config: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

interface MappingDefault {
  default_id: number;
  company_id: number;
  doc_type_id: number;
  item_type: MappingItemType;
  template_id: number | null;
  config_override: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

interface TemplateFormState {
  template_name: string;
  item_type: MappingItemType;
  company_id: string;
  doc_type_id: string;
  master_csv_path: string;
  external_join_keys: string;
  internal_join_key: string;
  column_aliases: string;
  priority: string;
}

interface DefaultFormState {
  company_id: string;
  doc_type_id: string;
  item_type: MappingItemType;
  template_id: string;
  override_enabled: boolean;
  master_csv_path: string;
  external_join_keys: string;
  internal_join_key: string;
  column_aliases: string;
}

const ITEM_TYPE_OPTIONS: Array<{ value: MappingItemType; label: string }> = [
  { value: 'single_source', label: 'Single Source' },
  { value: 'multi_source', label: 'Multiple Source' },
];

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const body = await response.text();
    const detail = (() => {
      try {
        return JSON.parse(body).detail as string;
      } catch {
        return body || response.statusText;
      }
    })();
    throw new Error(detail || 'Request failed');
  }
  return response.json();
}

const defaultTemplateFormState: TemplateFormState = {
  template_name: '',
  item_type: 'single_source',
  company_id: '',
  doc_type_id: '',
  master_csv_path: '',
  external_join_keys: '',
  internal_join_key: '',
  column_aliases: '',
  priority: '100',
};

const defaultDefaultFormState: DefaultFormState = {
  company_id: '',
  doc_type_id: '',
  item_type: 'single_source',
  template_id: '',
  override_enabled: false,
  master_csv_path: '',
  external_join_keys: '',
  internal_join_key: '',
  column_aliases: '',
};

const formatDate = (value: string) => new Date(value).toLocaleString();

const formatJoinKeys = (keys?: unknown) =>
  Array.isArray(keys) ? keys.join(', ') : typeof keys === 'string' ? keys : '—';

const stringifyConfig = (config: Record<string, any> | null) =>
  config ? JSON.stringify(config, null, 2) : '—';

export default function MappingAdminPage() {
  const [templates, setTemplates] = useState<MappingTemplate[]>([]);
  const [defaults, setDefaults] = useState<MappingDefault[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [docTypes, setDocTypes] = useState<DocumentType[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string>('');

  const [templateForm, setTemplateForm] = useState<TemplateFormState>(defaultTemplateFormState);
  const [defaultForm, setDefaultForm] = useState<DefaultFormState>(defaultDefaultFormState);
  const [isSubmittingTemplate, setIsSubmittingTemplate] = useState(false);
  const [isSubmittingDefault, setIsSubmittingDefault] = useState(false);

  const companyLookup = useMemo(() => {
    const map = new Map<number, Company>();
    companies.forEach((c) => map.set(c.company_id, c));
    return map;
  }, [companies]);

  const docTypeLookup = useMemo(() => {
    const map = new Map<number, DocumentType>();
    docTypes.forEach((d) => map.set(d.doc_type_id, d));
    return map;
  }, [docTypes]);

  const loadData = async () => {
    setIsLoading(true);
    setError('');
    try {
      const [tpl, def, comps, docs] = await Promise.all([
        fetchJson<MappingTemplate[]>('/mapping/templates'),
        fetchJson<MappingDefault[]>('/mapping/defaults'),
        fetchJson<Company[]>('/companies'),
        fetchJson<DocumentType[]>('/document-types'),
      ]);
      setTemplates(tpl);
      setDefaults(def);
      setCompanies(comps);
      setDocTypes(docs);
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'Failed to load mapping data');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const parseColumnAliases = (value: string) => {
    if (!value.trim()) {
      return {};
    }

    const aliases: Record<string, string> = {};
    value
      .split(',')
      .map((token) => token.trim())
      .filter(Boolean)
      .forEach((token) => {
        const [left, right] = token.split(':').map((part) => part.trim());
        if (left && right) {
          aliases[left] = right;
        }
      });
    return aliases;
  };

  const handleTemplateInput = (
    field: keyof TemplateFormState,
    value: string | boolean,
  ) => {
    setTemplateForm((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleDefaultInput = (
    field: keyof DefaultFormState,
    value: string | boolean,
  ) => {
    setDefaultForm((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const submitTemplate = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');

    if (!templateForm.template_name.trim()) {
      setError('Template name is required.');
      return;
    }

    if (!templateForm.master_csv_path.trim()) {
      setError('Master CSV path is required.');
      return;
    }

    if (
      templateForm.item_type === 'multi_source' &&
      !templateForm.internal_join_key.trim()
    ) {
      setError('Internal join key is required for multiple source templates.');
      return;
    }

    const payload: any = {
      template_name: templateForm.template_name.trim(),
      item_type: templateForm.item_type,
      config: {
        item_type: templateForm.item_type,
        master_csv_path: templateForm.master_csv_path.trim(),
        external_join_keys: templateForm.external_join_keys
          .split(',')
          .map((key) => key.trim())
          .filter(Boolean),
        column_aliases: parseColumnAliases(templateForm.column_aliases),
      },
      priority: Number.parseInt(templateForm.priority, 10) || 100,
    };

    if (templateForm.item_type === 'multi_source') {
      payload.config.internal_join_key = templateForm.internal_join_key.trim();
    }

    if (templateForm.company_id) {
      payload.company_id = Number(templateForm.company_id);
    }
    if (templateForm.doc_type_id) {
      payload.doc_type_id = Number(templateForm.doc_type_id);
    }

    setIsSubmittingTemplate(true);
    try {
      await fetchJson<MappingTemplate>('/mapping/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setTemplateForm(defaultTemplateFormState);
      await loadData();
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'Failed to create mapping template');
    } finally {
      setIsSubmittingTemplate(false);
    }
  };

  const submitDefault = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');

    if (!defaultForm.company_id || !defaultForm.doc_type_id) {
      setError('Company and document type are required for defaults.');
      return;
    }

    if (
      defaultForm.override_enabled &&
      defaultForm.override_enabled &&
      defaultForm.item_type === 'multi_source' &&
      !defaultForm.internal_join_key.trim()
    ) {
      setError('Internal join key override is required for multiple source mapping.');
      return;
    }

    const payload: any = {
      company_id: Number(defaultForm.company_id),
      doc_type_id: Number(defaultForm.doc_type_id),
      item_type: defaultForm.item_type,
      template_id: defaultForm.template_id ? Number(defaultForm.template_id) : null,
    };

    if (defaultForm.override_enabled) {
      payload.config_override = {
        item_type: defaultForm.item_type,
        master_csv_path: defaultForm.master_csv_path.trim(),
        external_join_keys: defaultForm.external_join_keys
          .split(',')
          .map((key) => key.trim())
          .filter(Boolean),
        column_aliases: parseColumnAliases(defaultForm.column_aliases),
      };
      if (defaultForm.item_type === 'multi_source') {
        payload.config_override.internal_join_key = defaultForm.internal_join_key.trim();
      }
    }

    setIsSubmittingDefault(true);
    try {
      await fetchJson<MappingDefault>('/mapping/defaults', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setDefaultForm(defaultDefaultFormState);
      await loadData();
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'Failed to save mapping default');
    } finally {
      setIsSubmittingDefault(false);
    }
  };

  const deleteTemplate = async (templateId: number) => {
    if (
      !window.confirm(
        'Delete this template? Any defaults referencing it will need to be updated.',
      )
    ) {
      return;
    }

    try {
      await fetchJson<{ message: string }>(`/mapping/templates/${templateId}`, {
        method: 'DELETE',
      });
      await loadData();
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'Failed to delete template');
    }
  };

  const deleteDefault = async (defaultId: number) => {
    if (!window.confirm('Delete this mapping default?')) {
      return;
    }

    try {
      await fetchJson<{ message: string }>(`/mapping/defaults/${defaultId}`, {
        method: 'DELETE',
      });
      await loadData();
    } catch (err) {
      console.error(err);
      setError(err instanceof Error ? err.message : 'Failed to delete mapping default');
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Mapping Templates & Defaults</h1>
        <button
          onClick={loadData}
          className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-4 py-2 rounded"
        >
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-100 border border-red-300 text-red-800 px-4 py-2 rounded mb-4">
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="text-gray-500">Loading mapping configuration data...</div>
      ) : (
        <div className="space-y-10">
          {/* Template Creation */}
          <section className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Create Mapping Template</h2>
            <p className="text-sm text-gray-600 mb-6">
              Templates capture reusable mapping logic. Assign them to specific companies or document types using defaults below.
            </p>

            <form onSubmit={submitTemplate} className="grid md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Template Name</label>
                <input
                  type="text"
                  value={templateForm.template_name}
                  onChange={(e) => handleTemplateInput('template_name', e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2"
                  placeholder="e.g. Telecom Master Mapping"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
                <input
                  type="number"
                  value={templateForm.priority}
                  onChange={(e) => handleTemplateInput('priority', e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2"
                  min={1}
                />
              </div>

              <div className="md:col-span-2">
                <span className="block text-sm font-medium text-gray-700 mb-2">Mapping Mode</span>
                <div className="flex items-center gap-6">
                  {ITEM_TYPE_OPTIONS.map((option) => (
                    <label key={option.value} className="flex items-center gap-2 text-sm">
                      <input
                        type="radio"
                        name="template_item_type"
                        value={option.value}
                        checked={templateForm.item_type === option.value}
                        onChange={() => handleTemplateInput('item_type', option.value)}
                        className="text-blue-600 focus:ring-blue-500"
                      />
                      {option.label}
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Company (optional)</label>
                <select
                  value={templateForm.company_id}
                  onChange={(e) => handleTemplateInput('company_id', e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2"
                >
                  <option value="">Any company</option>
                  {companies.map((company) => (
                    <option key={company.company_id} value={company.company_id}>
                      {company.company_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Document Type (optional)</label>
                <select
                  value={templateForm.doc_type_id}
                  onChange={(e) => handleTemplateInput('doc_type_id', e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2"
                >
                  <option value="">Any document type</option>
                  {docTypes.map((doc) => (
                    <option key={doc.doc_type_id} value={doc.doc_type_id}>
                      {doc.type_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Master CSV Path</label>
                <input
                  type="text"
                  value={templateForm.master_csv_path}
                  onChange={(e) => handleTemplateInput('master_csv_path', e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2"
                  placeholder="OneDrive path, e.g. HYA-OCR/Master Data/TELECOM_USERS.csv"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">External Join Keys</label>
                <input
                  type="text"
                  value={templateForm.external_join_keys}
                  onChange={(e) => handleTemplateInput('external_join_keys', e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2"
                  placeholder="Comma separated, e.g. phone_number, account_id"
                />
              </div>

              {templateForm.item_type === 'multi_source' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Internal Join Key</label>
                  <input
                    type="text"
                    value={templateForm.internal_join_key}
                    onChange={(e) => handleTemplateInput('internal_join_key', e.target.value)}
                    className="w-full border border-gray-300 rounded px-3 py-2"
                    placeholder="Field shared between primary and attachment OCR data"
                  />
                </div>
              )}

              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Column Aliases (optional)</label>
                <textarea
                  value={templateForm.column_aliases}
                  onChange={(e) => handleTemplateInput('column_aliases', e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2"
                  placeholder="Format: ocr_field:master_field, ..."
                  rows={2}
                />
              </div>

              <div className="md:col-span-2 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setTemplateForm(defaultTemplateFormState);
                    setError('');
                  }}
                  className="px-4 py-2 text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
                >
                  Reset
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingTemplate}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-blue-300"
                >
                  {isSubmittingTemplate ? 'Saving...' : 'Create Template'}
                </button>
              </div>
            </form>
          </section>

          {/* Templates List */}
          <section className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Existing Templates</h2>
            {templates.length === 0 ? (
              <div className="text-sm text-gray-500">No mapping templates defined yet.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full border border-gray-200 text-sm">
                  <thead className="bg-gray-50 text-left">
                    <tr>
                      <th className="px-4 py-2 border-b">Name</th>
                      <th className="px-4 py-2 border-b">Scope</th>
                      <th className="px-4 py-2 border-b">Mode</th>
                      <th className="px-4 py-2 border-b">Priority</th>
                      <th className="px-4 py-2 border-b">Master CSV</th>
                      <th className="px-4 py-2 border-b">Join Keys</th>
                      <th className="px-4 py-2 border-b">Updated</th>
                      <th className="px-4 py-2 border-b">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {templates.map((template) => {
                      const companyName =
                        template.company_id != null
                          ? companyLookup.get(template.company_id)?.company_name || `Company #${template.company_id}`
                          : 'All companies';
                      const docTypeName =
                        template.doc_type_id != null
                          ? docTypeLookup.get(template.doc_type_id)?.type_name || `DocType #${template.doc_type_id}`
                          : 'All document types';
                      const config = template.config || {};
                      return (
                        <tr key={template.template_id} className="odd:bg-white even:bg-slate-50">
                          <td className="px-4 py-2 border-b align-top">
                            <div className="font-medium text-gray-900">{template.template_name}</div>
                            <div className="text-xs text-gray-500">Template #{template.template_id}</div>
                          </td>
                          <td className="px-4 py-2 border-b align-top">
                            <div>{companyName}</div>
                            <div className="text-xs text-gray-500">{docTypeName}</div>
                          </td>
                          <td className="px-4 py-2 border-b align-top">{formatMappingType(template.item_type)}</td>
                          <td className="px-4 py-2 border-b align-top">{template.priority}</td>
                          <td className="px-4 py-2 border-b align-top">{config.master_csv_path || '—'}</td>
                          <td className="px-4 py-2 border-b align-top">{formatJoinKeys(config.external_join_keys)}</td>
                          <td className="px-4 py-2 border-b align-top text-xs text-gray-500">{formatDate(template.updated_at)}</td>
                          <td className="px-4 py-2 border-b align-top">
                            <button
                              onClick={() => deleteTemplate(template.template_id)}
                              className="text-red-600 hover:text-red-800 text-xs"
                            >
                              Delete
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* Defaults */}
          <section className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl font-semibold mb-4">Company & Document Defaults</h2>
            <p className="text-sm text-gray-600 mb-6">
              Defaults select which template applies by default for a company/document combination. Optional overrides tweak configuration without duplicating templates.
            </p>

            <form onSubmit={submitDefault} className="grid md:grid-cols-2 gap-6 mb-8">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Company</label>
                <select
                  value={defaultForm.company_id}
                  onChange={(e) => handleDefaultInput('company_id', e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2"
                  required
                >
                  <option value="">Select company…</option>
                  {companies.map((company) => (
                    <option key={company.company_id} value={company.company_id}>
                      {company.company_name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Document Type</label>
                <select
                  value={defaultForm.doc_type_id}
                  onChange={(e) => handleDefaultInput('doc_type_id', e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2"
                  required
                >
                  <option value="">Select document type…</option>
                  {docTypes.map((doc) => (
                    <option key={doc.doc_type_id} value={doc.doc_type_id}>
                      {doc.type_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="md:col-span-2">
                <span className="block text-sm font-medium text-gray-700 mb-2">Mapping Mode</span>
                <div className="flex items-center gap-6">
                  {ITEM_TYPE_OPTIONS.map((option) => (
                    <label key={option.value} className="flex items-center gap-2 text-sm">
                      <input
                        type="radio"
                        name="default_item_type"
                        value={option.value}
                        checked={defaultForm.item_type === option.value}
                        onChange={() => handleDefaultInput('item_type', option.value)}
                        className="text-blue-600 focus:ring-blue-500"
                      />
                      {option.label}
                    </label>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Template</label>
                <select
                  value={defaultForm.template_id}
                  onChange={(e) => handleDefaultInput('template_id', e.target.value)}
                  className="w-full border border-gray-300 rounded px-3 py-2"
                >
                  <option value="">Select template…</option>
                  {templates
                    .filter((tpl) => tpl.item_type === defaultForm.item_type)
                    .map((tpl) => (
                      <option key={tpl.template_id} value={tpl.template_id}>
                        {tpl.template_name}
                      </option>
                    ))}
                </select>
              </div>

              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
                  <input
                    type="checkbox"
                    checked={defaultForm.override_enabled}
                    onChange={(e) => handleDefaultInput('override_enabled', e.target.checked)}
                  />
                  Provide config override
                </label>
                <p className="text-xs text-gray-500 mt-1">
                  Overrides apply on top of the referenced template.
                </p>
              </div>

              {defaultForm.override_enabled && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Master CSV Override</label>
                    <input
                      type="text"
                      value={defaultForm.master_csv_path}
                      onChange={(e) => handleDefaultInput('master_csv_path', e.target.value)}
                      className="w-full border border-gray-300 rounded px-3 py-2"
                      placeholder="Override path if different for this company/doc type"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">External Join Keys Override</label>
                    <input
                      type="text"
                      value={defaultForm.external_join_keys}
                      onChange={(e) => handleDefaultInput('external_join_keys', e.target.value)}
                      className="w-full border border-gray-300 rounded px-3 py-2"
                      placeholder="Comma separated list"
                    />
                  </div>

                  {defaultForm.item_type === 'multi_source' && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Internal Join Key Override</label>
                      <input
                        type="text"
                        value={defaultForm.internal_join_key}
                        onChange={(e) => handleDefaultInput('internal_join_key', e.target.value)}
                        className="w-full border border-gray-300 rounded px-3 py-2"
                        placeholder="e.g. phone_number"
                      />
                    </div>
                  )}

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Column Aliases Override</label>
                    <textarea
                      value={defaultForm.column_aliases}
                      onChange={(e) => handleDefaultInput('column_aliases', e.target.value)}
                      className="w-full border border-gray-300 rounded px-3 py-2"
                      placeholder="Format: ocr_field:master_field, ..."
                      rows={2}
                    />
                  </div>
                </>
              )}

              <div className="md:col-span-2 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setDefaultForm(defaultDefaultFormState);
                    setError('');
                  }}
                  className="px-4 py-2 text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
                >
                  Reset
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingDefault}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-blue-300"
                >
                  {isSubmittingDefault ? 'Saving...' : 'Upsert Default'}
                </button>
              </div>
            </form>

            {defaults.length === 0 ? (
              <div className="text-sm text-gray-500">No mapping defaults configured yet.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full border border-gray-200 text-sm">
                  <thead className="bg-gray-50 text-left">
                    <tr>
                      <th className="px-4 py-2 border-b">Company</th>
                      <th className="px-4 py-2 border-b">Document Type</th>
                      <th className="px-4 py-2 border-b">Mode</th>
                      <th className="px-4 py-2 border-b">Template</th>
                      <th className="px-4 py-2 border-b">Override</th>
                      <th className="px-4 py-2 border-b">Updated</th>
                      <th className="px-4 py-2 border-b">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {defaults.map((record) => {
                      const companyName = companyLookup.get(record.company_id)?.company_name || `Company #${record.company_id}`;
                      const docTypeName = docTypeLookup.get(record.doc_type_id)?.type_name || `DocType #${record.doc_type_id}`;
                      const templateName = record.template_id
                        ? templates.find((tpl) => tpl.template_id === record.template_id)?.template_name || `Template #${record.template_id}`
                        : '—';
                      return (
                        <tr key={record.default_id} className="odd:bg-white even:bg-slate-50">
                          <td className="px-4 py-2 border-b">{companyName}</td>
                          <td className="px-4 py-2 border-b">{docTypeName}</td>
                          <td className="px-4 py-2 border-b">{formatMappingType(record.item_type)}</td>
                          <td className="px-4 py-2 border-b">{templateName}</td>
                          <td className="px-4 py-2 border-b align-top">
                            <pre className="bg-slate-100 text-slate-700 rounded px-2 py-1 text-xs whitespace-pre-wrap">
                              {stringifyConfig(record.config_override)}
                            </pre>
                          </td>
                          <td className="px-4 py-2 border-b text-xs text-gray-500">{formatDate(record.updated_at)}</td>
                          <td className="px-4 py-2 border-b">
                            <button
                              onClick={() => deleteDefault(record.default_id)}
                              className="text-red-600 hover:text-red-800 text-xs"
                            >
                              Delete
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
