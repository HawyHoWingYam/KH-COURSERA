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
const formatMappingType = (value: string) => value === 'multi_source' ? 'Multiple Source' : 'Single Source';

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
  // Attachment rules for defaults override
  const [defaultAttachmentRules, setDefaultAttachmentRules] = useState<Array<{ path?: string; filename_contains?: string; join_key?: string }>>([]);
  const addDefaultAttachmentRule = () => setDefaultAttachmentRules(prev => [...prev, { path: '', filename_contains: '', join_key: '' }]);
  const updateDefaultAttachmentRule = (idx: number, field: 'path' | 'filename_contains' | 'join_key', value: string) => {
    setDefaultAttachmentRules(prev => {
      const next = prev.slice();
      next[idx] = { ...next[idx], [field]: value };
      return next;
    });
  };
  const removeDefaultAttachmentRule = (idx: number) => setDefaultAttachmentRules(prev => prev.filter((_, i) => i !== idx));
  const [isSubmittingTemplate, setIsSubmittingTemplate] = useState(false);
  const [isSubmittingDefault, setIsSubmittingDefault] = useState(false);
  // Template editing state
  const [editingTemplateId, setEditingTemplateId] = useState<number | null>(null);
  const [editingTemplateOriginalConfig, setEditingTemplateOriginalConfig] = useState<Record<string, any> | null>(null);
  // Master CSV preview state (template)
  const [tplCsvPreview, setTplCsvPreview] = useState<{ headers: string[]; row_count: number } | null>(null);
  const [isPreviewingTplCsv, setIsPreviewingTplCsv] = useState(false);
  // Master CSV preview state (default override)
  const [defCsvPreview, setDefCsvPreview] = useState<{ headers: string[]; row_count: number } | null>(null);
  const [isPreviewingDefCsv, setIsPreviewingDefCsv] = useState(false);

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
  const parseTplJoinKeys = (): string[] => templateForm.external_join_keys.split(',').map(k => k.trim()).filter(Boolean);
  const toggleTplJoinKey = (key: string) => {
    const set = new Set(parseTplJoinKeys());
    set.has(key) ? set.delete(key) : set.add(key);
    setTemplateForm(prev => ({ ...prev, external_join_keys: Array.from(set).join(', ') }));
  };
  const previewTplCsv = async () => {
    if (!templateForm.master_csv_path.trim()) return;
    setIsPreviewingTplCsv(true);
    try {
      const resp = await fetch(`/api/mapping/master-csv/preview?path=${encodeURIComponent(templateForm.master_csv_path.trim())}`);
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to preview master CSV');
      }
      const data = await resp.json();
      setTplCsvPreview({ headers: data.headers || [], row_count: data.row_count || 0 });
    } catch (e) {
      console.error(e);
      setTplCsvPreview(null);
    } finally {
      setIsPreviewingTplCsv(false);
    }
  };

  // Attachment rules for template config (multi-source)
  type AttachmentRule = { path?: string; filename_contains?: string; join_key?: string };
  const [attachmentRules, setAttachmentRules] = useState<AttachmentRule[]>([]);
  const addAttachmentRule = () => setAttachmentRules((prev) => [...prev, { path: '', filename_contains: '', join_key: '' }]);
  const updateAttachmentRule = (idx: number, field: keyof AttachmentRule, value: string) => {
    setAttachmentRules((prev) => {
      const next = prev.slice();
      next[idx] = { ...next[idx], [field]: value };
      return next;
    });
  };
  const removeAttachmentRule = (idx: number) => setAttachmentRules((prev) => prev.filter((_, i) => i !== idx));

  const handleDefaultInput = (
    field: keyof DefaultFormState,
    value: string | boolean,
  ) => {
    setDefaultForm((prev) => ({
      ...prev,
      [field]: value,
    }));
  };
  const parseDefJoinKeys = (): string[] => defaultForm.external_join_keys.split(',').map(k => k.trim()).filter(Boolean);
  const toggleDefJoinKey = (key: string) => {
    const set = new Set(parseDefJoinKeys());
    set.has(key) ? set.delete(key) : set.add(key);
    setDefaultForm(prev => ({ ...prev, external_join_keys: Array.from(set).join(', ') }));
  };
  const previewDefCsv = async () => {
    if (!defaultForm.master_csv_path.trim()) return;
    setIsPreviewingDefCsv(true);
    try {
      const resp = await fetch(`/api/mapping/master-csv/preview?path=${encodeURIComponent(defaultForm.master_csv_path.trim())}`);
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to preview master CSV');
      }
      const data = await resp.json();
      setDefCsvPreview({ headers: data.headers || [], row_count: data.row_count || 0 });
    } catch (e) {
      console.error(e);
      setDefCsvPreview(null);
    } finally {
      setIsPreviewingDefCsv(false);
    }
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

    if (templateForm.item_type === 'multi_source') {
      const hasDefaultInternal = !!templateForm.internal_join_key.trim();
      const cleanedRules = attachmentRules.filter(r => ((r.path || '').trim().length > 0 || (r.join_key || '').trim().length > 0 || (r.filename_contains || '').trim().length > 0));
      const hasAnyRule = cleanedRules.some(r => (r.join_key || '').trim().length > 0);
      if (!hasDefaultInternal && !hasAnyRule) {
        setError('Provide a default internal join key or at least one attachment rule with join key.');
        return;
      }
      // If rules are provided, enforce path is present (backend requires path)
      const missingPath = cleanedRules.some(r => !(r.path || '').trim().length);
      if (cleanedRules.length > 0 && missingPath) {
        setError('Each attachment rule must include a OneDrive path.');
        return;
      }
    }

    const payload: any = {
      template_name: templateForm.template_name.trim(),
      item_type: templateForm.item_type,
      config: {} as Record<string, any>,
      priority: Number.parseInt(templateForm.priority, 10) || 100,
    };

    // For updates, preserve original config fields we don't expose in UI (e.g., attachment_sources with path)
    const baseConfig = editingTemplateId && editingTemplateOriginalConfig
      ? { ...editingTemplateOriginalConfig }
      : {};

    const nextConfig: Record<string, any> = {
      ...baseConfig,
      item_type: templateForm.item_type,
      master_csv_path: templateForm.master_csv_path.trim(),
      external_join_keys: templateForm.external_join_keys
        .split(',')
        .map((key) => key.trim())
        .filter(Boolean),
      column_aliases: parseColumnAliases(templateForm.column_aliases),
    };

    if (templateForm.item_type === 'multi_source') {
      if (templateForm.internal_join_key.trim()) {
        nextConfig.internal_join_key = templateForm.internal_join_key.trim();
      } else {
        delete nextConfig.internal_join_key;
      }
      // Build attachment_sources from UI rules; require non-empty path when a rule is present
      const cleaned = attachmentRules
        .filter(r => ((r.join_key || '').trim().length > 0 || (r.filename_contains || '').trim().length > 0 || (r.path || '').trim().length > 0))
        .map(r => ({
          kind: 'onedrive',
          path: (r.path || '').trim(),
          join_key: r.join_key?.trim() || undefined,
          filename_contains: r.filename_contains?.trim() || undefined,
        }))
        .filter(r => r.path.length > 0);
      if (cleaned.length > 0) {
        nextConfig.attachment_sources = cleaned;
      } else {
        delete nextConfig.attachment_sources;
      }
    } else {
      // Single source: remove multi-source only fields if any
      delete nextConfig.internal_join_key;
      delete nextConfig.attachment_sources;
    }

    payload.config = nextConfig;

  if (templateForm.company_id) {
      payload.company_id = Number(templateForm.company_id);
    }
    if (templateForm.doc_type_id) {
      payload.doc_type_id = Number(templateForm.doc_type_id);
    }

    setIsSubmittingTemplate(true);
    try {
      if (editingTemplateId) {
        await fetchJson<MappingTemplate>(`/mapping/templates/${editingTemplateId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      } else {
        await fetchJson<MappingTemplate>('/mapping/templates', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
      }
      setTemplateForm(defaultTemplateFormState);
      setAttachmentRules([]);
      setEditingTemplateId(null);
      await loadData();
    } catch (err) {
      console.error(err);
      setError(
        err instanceof Error
          ? err.message
          : editingTemplateId
          ? 'Failed to update mapping template'
          : 'Failed to create mapping template'
      );
    } finally {
      setIsSubmittingTemplate(false);
    }
  };

  const startEditTemplate = (template: MappingTemplate) => {
    const cfg = template.config || {};
    setEditingTemplateOriginalConfig(cfg);
    setTemplateForm({
      template_name: template.template_name,
      item_type: template.item_type,
      company_id: template.company_id != null ? String(template.company_id) : '',
      doc_type_id: template.doc_type_id != null ? String(template.doc_type_id) : '',
      master_csv_path: cfg.master_csv_path || '',
      external_join_keys: Array.isArray(cfg.external_join_keys) ? cfg.external_join_keys.join(', ') : '',
      internal_join_key: cfg.internal_join_key || '',
      column_aliases: cfg.column_aliases
        ? Object.entries(cfg.column_aliases)
            .map(([k, v]: any) => `${k}:${v}`)
            .join(', ')
        : '',
      priority: String(template.priority || 100),
    });
    // Only map filename/join_key rules for UI; ignore path/label/metadata
    const rules = Array.isArray(cfg.attachment_sources)
      ? cfg.attachment_sources.map((r: any) => ({
          path: r?.path || '',
          filename_contains: r?.filename_contains || '',
          join_key: r?.join_key || '',
        }))
      : [];
    setAttachmentRules(rules);
    setEditingTemplateId(template.template_id);
    setError('');
    setTplCsvPreview(null);
  };

  const submitDefault = async (event: React.FormEvent) => {
    event.preventDefault();
    setError('');

    if (!defaultForm.company_id || !defaultForm.doc_type_id) {
      setError('Company and document type are required for defaults.');
      return;
    }

    // attachment override rules
    const hasDefaultInternal = !!defaultForm.internal_join_key.trim();
    // parse later from UI (below) – simple validation will be done when sending payload

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
      if (defaultForm.item_type === 'multi_source' && defaultForm.internal_join_key.trim()) {
        payload.config_override.internal_join_key = defaultForm.internal_join_key.trim();
      }
      // Include attachment_sources override if present
      if (defaultForm.item_type === 'multi_source' && (defaultAttachmentRules.length > 0)) {
        const missingPath = defaultAttachmentRules
          .filter(r => (r.join_key || r.filename_contains))
          .some(r => !(r.path || '').trim().length);
        if (missingPath) {
          setIsSubmittingDefault(false);
          setError('Each default attachment rule must include a OneDrive path.');
          return;
        }
        const cleaned = defaultAttachmentRules
          .filter(r => ((r.path || '').trim().length > 0 || (r.join_key || '').trim().length > 0 || (r.filename_contains || '').trim().length > 0))
          .map(r => ({ kind: 'onedrive', path: (r.path || '').trim(), join_key: r.join_key?.trim() || undefined, filename_contains: r.filename_contains?.trim() || undefined }))
          .filter(r => r.path.length > 0);
        if (cleaned.length > 0) {
          payload.config_override.attachment_sources = cleaned;
        }
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
      setDefaultAttachmentRules([]);
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
                <div className="mt-2 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={previewTplCsv}
                    disabled={isPreviewingTplCsv || !templateForm.master_csv_path.trim()}
                    className="px-3 py-1 text-xs font-medium text-white bg-gray-700 hover:bg-gray-800 rounded disabled:bg-gray-300"
                  >
                    {isPreviewingTplCsv ? 'Loading…' : 'Preview Columns'}
                  </button>
                  {tplCsvPreview && (
                    <span className="text-xs text-gray-600">{tplCsvPreview.headers.length} columns · {tplCsvPreview.row_count} rows</span>
                  )}
                </div>
                {tplCsvPreview && tplCsvPreview.headers.length > 0 && (
                  <div className="mt-2 bg-gray-50 border border-gray-200 rounded p-2">
                    <div className="text-xs text-gray-600 mb-1">Columns (click to toggle in External Join Keys):</div>
                    <div className="flex flex-wrap gap-1">
                      {tplCsvPreview.headers.slice(0, 24).map((h, i) => {
                        const selected = parseTplJoinKeys().includes(h);
                        return (
                          <button
                            type="button"
                            key={i}
                            onClick={() => toggleTplJoinKey(h)}
                            className={`text-[11px] border rounded px-2 py-0.5 ${selected ? 'bg-blue-600 text-white border-blue-700' : 'bg-white text-gray-800 border-gray-300'}`}
                            title={selected ? 'Remove from join keys' : 'Add to join keys'}
                          >
                            {h}
                          </button>
                        );
                      })}
                      {tplCsvPreview.headers.length > 24 && (
                        <span className="text-[11px] text-gray-500">+{tplCsvPreview.headers.length - 24} more</span>
                      )}
                    </div>
                  </div>
                )}
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
                <div className="md:col-span-2 space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Internal Join Key (default)</label>
                    <input
                      type="text"
                      value={templateForm.internal_join_key}
                      onChange={(e) => handleTemplateInput('internal_join_key', e.target.value)}
                      className="w-full border border-gray-300 rounded px-3 py-2"
                      placeholder="Field shared between primary and attachments (optional if rules set)"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Attachment Rules</label>
                    <div className="space-y-2">
                      {attachmentRules.map((rule, idx) => (
                        <div key={idx} className="grid md:grid-cols-3 gap-3 items-end">
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">OneDrive Path</label>
                            <input
                              type="text"
                              value={rule.path || ''}
                              onChange={(e) => updateAttachmentRule(idx, 'path', e.target.value)}
                              className="w-full border border-gray-300 rounded px-3 py-2"
                              placeholder="e.g. HYA-OCR/Attachments/2025-10/"
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Filename Contains</label>
                            <input
                              type="text"
                              value={rule.filename_contains || ''}
                              onChange={(e) => updateAttachmentRule(idx, 'filename_contains', e.target.value)}
                              className="w-full border border-gray-300 rounded px-3 py-2"
                              placeholder="Optional, e.g. INV-"
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Join Key</label>
                            <input
                              type="text"
                              value={rule.join_key || ''}
                              onChange={(e) => updateAttachmentRule(idx, 'join_key', e.target.value)}
                              className="w-full border border-gray-300 rounded px-3 py-2"
                              placeholder="e.g. invoice_no"
                            />
                          </div>
                          <button type="button" onClick={() => removeAttachmentRule(idx)} className="px-3 py-2 text-sm bg-red-600 text-white rounded">Remove</button>
                        </div>
                      ))}
                      <button type="button" onClick={addAttachmentRule} className="px-3 py-2 text-sm bg-gray-700 text-white rounded">+ Add Rule</button>
                    </div>
                  </div>
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
                    setAttachmentRules([]);
                    setEditingTemplateId(null);
                    setEditingTemplateOriginalConfig(null);
                    setError('');
                  }}
                  className="px-4 py-2 text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
                >
                  {editingTemplateId ? 'Cancel' : 'Reset'}
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingTemplate}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:bg-blue-300"
                >
                  {isSubmittingTemplate ? 'Saving...' : editingTemplateId ? 'Update Template' : 'Create Template'}
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
                          <td className="px-4 py-2 border-b align-top space-x-3">
                            <button
                              onClick={() => startEditTemplate(template)}
                              className="text-blue-600 hover:text-blue-800 text-xs"
                            >
                              Edit
                            </button>
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
                <div className="mt-2 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={previewDefCsv}
                    disabled={isPreviewingDefCsv || !defaultForm.master_csv_path.trim()}
                    className="px-3 py-1 text-xs font-medium text-white bg-gray-700 hover:bg-gray-800 rounded disabled:bg-gray-300"
                  >
                    {isPreviewingDefCsv ? 'Loading…' : 'Preview Columns'}
                  </button>
                  {defCsvPreview && (
                    <span className="text-xs text-gray-600">{defCsvPreview.headers.length} columns · {defCsvPreview.row_count} rows</span>
                  )}
                </div>
                {defCsvPreview && defCsvPreview.headers.length > 0 && (
                  <div className="mt-2 bg-gray-50 border border-gray-200 rounded p-2">
                    <div className="text-xs text-gray-600 mb-1">Columns (click to toggle in External Join Keys):</div>
                    <div className="flex flex-wrap gap-1">
                      {defCsvPreview.headers.slice(0, 24).map((h, i) => {
                        const selected = parseDefJoinKeys().includes(h);
                        return (
                          <button
                            type="button"
                            key={i}
                            onClick={() => toggleDefJoinKey(h)}
                            className={`text-[11px] border rounded px-2 py-0.5 ${selected ? 'bg-blue-600 text-white border-blue-700' : 'bg-white text-gray-800 border-gray-300'}`}
                            title={selected ? 'Remove from join keys' : 'Add to join keys'}
                          >
                            {h}
                          </button>
                        );
                      })}
                      {defCsvPreview.headers.length > 24 && (
                        <span className="text-[11px] text-gray-500">+{defCsvPreview.headers.length - 24} more</span>
                      )}
                    </div>
                  </div>
                )}
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
                <>
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
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Attachment Rules Override</label>
                    <div className="space-y-2">
                      {defaultAttachmentRules.map((rule, idx) => (
                        <div key={idx} className="grid md:grid-cols-3 gap-3 items-end">
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">OneDrive Path</label>
                            <input
                              type="text"
                              value={rule.path || ''}
                              onChange={(e) => updateDefaultAttachmentRule(idx, 'path', e.target.value)}
                              className="w-full border border-gray-300 rounded px-3 py-2"
                              placeholder="e.g. HYA-OCR/Attachments/2025-10/"
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Filename Contains</label>
                            <input
                              type="text"
                              value={rule.filename_contains || ''}
                              onChange={(e) => updateDefaultAttachmentRule(idx, 'filename_contains', e.target.value)}
                              className="w-full border border-gray-300 rounded px-3 py-2"
                              placeholder="e.g. INV-"
                            />
                          </div>
                          <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Join Key</label>
                            <input
                              type="text"
                              value={rule.join_key || ''}
                              onChange={(e) => updateDefaultAttachmentRule(idx, 'join_key', e.target.value)}
                              className="w-full border border-gray-300 rounded px-3 py-2"
                              placeholder="e.g. invoice_no"
                            />
                          </div>
                          <button type="button" onClick={() => removeDefaultAttachmentRule(idx)} className="px-3 py-2 text-sm bg-red-600 text-white rounded">Remove</button>
                        </div>
                      ))}
                      <button type="button" onClick={addDefaultAttachmentRule} className="px-3 py-2 text-sm bg-gray-700 text-white rounded">+ Add Rule</button>
                    </div>
                  </div>
                </>
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
