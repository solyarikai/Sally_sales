import { api } from './client';

// ── Types ─────────────────────────────────────────────────────────────

export interface IGamingContact {
  id: number;
  source_id?: string;
  first_name?: string;
  last_name?: string;
  email?: string;
  phone?: string;
  linkedin_url?: string;
  job_title?: string;
  bio?: string;
  other_contact?: string;
  organization_name?: string;
  website_url?: string;
  business_type_raw?: string;
  business_type?: string;
  company_id?: number;
  source_conference?: string;
  source_file?: string;
  import_id?: number;
  sector?: string;
  regions?: string[];
  new_regions_targeting?: string[];
  channel?: string;
  products_services?: string;
  custom_fields: Record<string, any>;
  tags: string[];
  notes?: string;
  company_name?: string;
  company_website?: string;
  created_at?: string;
  updated_at?: string;
}

export interface IGamingCompany {
  id: number;
  name: string;
  name_aliases: string[];
  website?: string;
  business_type?: string;
  business_type_raw?: string;
  description?: string;
  sector?: string;
  regions?: string[];
  headquarters?: string;
  contacts_count: number;
  employees_count: number;
  enrichment_data?: Record<string, any>;
  custom_fields: Record<string, any>;
  created_at?: string;
  updated_at?: string;
}

export interface IGamingEmployee {
  id: number;
  company_id: number;
  full_name?: string;
  first_name?: string;
  last_name?: string;
  job_title?: string;
  email?: string;
  linkedin_url?: string;
  phone?: string;
  source?: string;
  search_query?: string;
  company_name?: string;
  company_website?: string;
  created_at?: string;
}

export interface IGamingImport {
  id: number;
  filename: string;
  source_conference?: string;
  status: string;
  rows_total: number;
  rows_imported: number;
  rows_skipped: number;
  rows_updated: number;
  companies_created: number;
  created_at?: string;
}

export interface IGamingStats {
  total_contacts: number;
  total_companies: number;
  total_employees: number;
  contacts_with_email: number;
  contacts_with_linkedin: number;
  companies_with_website: number;
  top_conferences: { name: string; count: number }[];
  top_business_types: { name: string; count: number }[];
  recent_imports: IGamingImport[];
}

export interface ListResponse<T> {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  contacts?: T[];
  companies?: T[];
  employees?: T[];
}

export interface FilterOption {
  value: string;
  count: number;
}

export interface AIColumn {
  id: number;
  name: string;
  target: string;
  prompt_template: string;
  model: string;
  is_active: boolean;
  rows_processed: number;
  rows_total: number;
  status: string;
  created_at?: string;
}

export interface ImportUploadResponse {
  file_id: string;
  filename: string;
  rows_preview: number;
  columns: string[];
  preview: Record<string, string>[];
}

// ── API ───────────────────────────────────────────────────────────────

export const igamingApi = {
  // Stats
  getStats: async () => {
    const res = await api.get<IGamingStats>('/igaming/stats');
    return res.data;
  },

  // Contacts
  listContacts: async (params: Record<string, any>) => {
    const res = await api.get<ListResponse<IGamingContact> & { contacts: IGamingContact[] }>(
      '/igaming/contacts', { params }
    );
    return res.data;
  },

  getContact: async (id: number) => {
    const res = await api.get<IGamingContact>(`/igaming/contacts/${id}`);
    return res.data;
  },

  updateContact: async (id: number, data: Partial<IGamingContact>) => {
    const res = await api.patch<IGamingContact>(`/igaming/contacts/${id}`, data);
    return res.data;
  },

  deleteContact: async (id: number) => {
    await api.delete(`/igaming/contacts/${id}`);
  },

  batchDeleteContacts: async (ids: number[]) => {
    const res = await api.post<{ deleted: number }>('/igaming/contacts/batch-delete', ids);
    return res.data;
  },

  batchTagContacts: async (ids: number[], tag: string) => {
    const res = await api.post<{ tagged: number }>('/igaming/contacts/batch-tag', ids, {
      params: { tag },
    });
    return res.data;
  },

  // Companies
  listCompanies: async (params: Record<string, any>) => {
    const res = await api.get<ListResponse<IGamingCompany> & { companies: IGamingCompany[] }>(
      '/igaming/companies', { params }
    );
    return res.data;
  },

  getCompany: async (id: number) => {
    const res = await api.get<IGamingCompany>(`/igaming/companies/${id}`);
    return res.data;
  },

  updateCompany: async (id: number, data: Partial<IGamingCompany>) => {
    const res = await api.patch<IGamingCompany>(`/igaming/companies/${id}`, data);
    return res.data;
  },

  mergeCompanies: async (sourceId: number, targetId: number) => {
    const res = await api.post<{ merged: boolean; contacts_moved: number }>(
      '/igaming/companies/merge', null, { params: { source_id: sourceId, target_id: targetId } }
    );
    return res.data;
  },

  // Employees
  listEmployees: async (params: Record<string, any>) => {
    const res = await api.get<ListResponse<IGamingEmployee> & { employees: IGamingEmployee[] }>(
      '/igaming/employees', { params }
    );
    return res.data;
  },

  // Import
  uploadFile: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    const res = await api.post<ImportUploadResponse>('/igaming/import/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  startImport: async (data: { file_id: string; column_mapping: Record<string, string>; source_conference?: string; update_existing?: boolean }) => {
    const res = await api.post<IGamingImport>('/igaming/import/start', data, {
      timeout: 600000, // 10 minutes — large CSV imports take time
    });
    return res.data;
  },

  listImports: async () => {
    const res = await api.get<IGamingImport[]>('/igaming/imports');
    return res.data;
  },

  // Fix names (PROPER case)
  fixNames: async () => {
    const res = await api.post<{ updated: number; total_checked: number }>('/igaming/contacts/fix-names');
    return res.data;
  },

  // Find Websites (Yandex + Gemini)
  findWebsites: async (data?: { company_ids?: number[]; limit?: number }) => {
    const res = await api.post<Record<string, any>>('/igaming/companies/find-websites', data || {}, {
      timeout: 600000,
    });
    return res.data;
  },

  // Autofill
  runAutofill: async () => {
    const res = await api.post<{ contacts_website_updated: number; contacts_type_updated: number }>(
      '/igaming/autofill/run'
    );
    return res.data;
  },

  // Filters
  getConferences: async () => {
    const res = await api.get<FilterOption[]>('/igaming/filters/conferences');
    return res.data;
  },

  getBusinessTypes: async () => {
    const res = await api.get<FilterOption[]>('/igaming/filters/business-types');
    return res.data;
  },

  getSectors: async () => {
    const res = await api.get<FilterOption[]>('/igaming/filters/sectors');
    return res.data;
  },

  // AI Columns
  createAIColumn: async (data: { name: string; target: string; prompt_template: string; model: string }) => {
    const res = await api.post<AIColumn>('/igaming/ai-columns', data);
    return res.data;
  },

  listAIColumns: async () => {
    const res = await api.get<AIColumn[]>('/igaming/ai-columns');
    return res.data;
  },

  deleteAIColumn: async (id: number) => {
    await api.delete(`/igaming/ai-columns/${id}`);
  },

  runAIColumn: async (id: number, filterParams?: Record<string, any>) => {
    const res = await api.post<{ processed: number; total: number; errors: number }>(
      `/igaming/ai-columns/${id}/run`, { filter_params: filterParams }
    );
    return res.data;
  },

  getAIColumnProgress: async (id: number) => {
    const res = await api.get<{ processed: number; total: number; status: string; errors: any[] }>(
      `/igaming/ai-columns/${id}/progress`
    );
    return res.data;
  },

  // Employee Search
  searchEmployees: async (data: {
    company_ids: number[];
    titles: string[];
    limit_per_company?: number;
    source?: string;
    clay_webhook_url?: string;
  }) => {
    const res = await api.post<Record<string, any>>('/igaming/employees/search', data);
    return res.data;
  },

  getSearchProgress: async (taskId: string) => {
    const res = await api.get<{ processed: number; total: number; found: number; status: string }>(
      `/igaming/employees/search/progress/${taskId}`
    );
    return res.data;
  },
};
