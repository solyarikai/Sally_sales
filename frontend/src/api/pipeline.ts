import { api } from './client';

// ============ Pipeline Types ============

export interface DiscoveredCompany {
  id: number;
  company_id: number;
  project_id?: number;
  domain: string;
  name?: string;
  url?: string;
  is_target: boolean;
  confidence?: number;
  reasoning?: string;
  company_info?: {
    name?: string;
    description?: string;
    services?: string[];
    location?: string;
    industry?: string;
  };
  status: string;
  contacts_count: number;
  emails_found?: string[];
  phones_found?: string[];
  apollo_people_count: number;
  apollo_enriched_at?: string;
  scraped_at?: string;
  search_job_id?: number;
  created_at?: string;
  updated_at?: string;
}

export interface ExtractedContact {
  id: number;
  discovered_company_id: number;
  email?: string;
  phone?: string;
  first_name?: string;
  last_name?: string;
  job_title?: string;
  linkedin_url?: string;
  source: string;
  is_verified: boolean;
  verification_method?: string;
  contact_id?: number;
  created_at?: string;
}

export interface PipelineEventItem {
  id: number;
  discovered_company_id?: number;
  company_id: number;
  event_type: string;
  detail?: Record<string, any>;
  error_message?: string;
  created_at?: string;
}

export interface DiscoveredCompanyDetail extends DiscoveredCompany {
  extracted_contacts: ExtractedContact[];
  events: PipelineEventItem[];
}

export interface PipelineStats {
  total_discovered: number;
  targets: number;
  contacts_extracted: number;
  enriched: number;
  exported: number;
  rejected: number;
  total_contacts: number;
  total_apollo_people: number;
  apollo_contacts: number;
  apollo_with_email: number;
  apollo_with_linkedin: number;
  website_contacts: number;
  website_with_email: number;
  website_with_phone: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export const pipelineApi = {
  // List discovered companies with filters
  listDiscoveredCompanies: async (params: {
    project_id?: number;
    status?: string;
    is_target?: boolean;
    search?: string;
    page?: number;
    page_size?: number;
  } = {}): Promise<PaginatedResponse<DiscoveredCompany>> => {
    const response = await api.get('/pipeline/discovered-companies', { params });
    return response.data;
  },

  // Get discovered company detail with contacts + events
  getDiscoveredCompany: async (id: number): Promise<DiscoveredCompanyDetail> => {
    const response = await api.get(`/pipeline/discovered-companies/${id}`);
    return response.data;
  },

  // Extract contacts from selected companies via GPT
  extractContacts: async (ids: number[]): Promise<{
    processed: number;
    contacts_found: number;
    errors: number;
  }> => {
    const response = await api.post('/pipeline/extract-contacts', {
      discovered_company_ids: ids,
    });
    return response.data;
  },

  // Enrich via Apollo
  enrichApollo: async (ids: number[], opts: {
    maxPeople?: number;
    titles?: string[];
    maxCredits?: number;
  } = {}): Promise<{
    processed: number;
    people_found: number;
    errors: number;
    credits_used: number;
    skipped: number;
  }> => {
    const response = await api.post('/pipeline/enrich-apollo', {
      discovered_company_ids: ids,
      max_people: opts.maxPeople ?? 5,
      titles: opts.titles?.length ? opts.titles : undefined,
      max_credits: opts.maxCredits ?? undefined,
    });
    return response.data;
  },

  // Promote extracted contacts to CRM
  promoteToCrm: async (ids: number[], projectId?: number, segment?: string): Promise<{
    promoted: number;
    skipped: number;
    errors: number;
  }> => {
    const response = await api.post('/pipeline/promote-to-crm', {
      extracted_contact_ids: ids,
      project_id: projectId,
      segment,
    });
    return response.data;
  },

  // List projects that have discovered companies (fast, for dropdown)
  listProjects: async (): Promise<{ id: number; name: string }[]> => {
    const response = await api.get('/pipeline/projects');
    return response.data;
  },

  // Get pipeline stats
  getStats: async (projectId?: number): Promise<PipelineStats> => {
    const response = await api.get('/pipeline/stats', {
      params: { project_id: projectId },
    });
    return response.data;
  },

  // Bulk update status
  updateStatus: async (ids: number[], status: string): Promise<{ updated: number }> => {
    const response = await api.post('/pipeline/update-status', {
      discovered_company_ids: ids,
      status,
    });
    return response.data;
  },

  // Export CSV (companies)
  exportCsv: async (projectId?: number, isTarget?: boolean): Promise<Blob> => {
    const response = await api.get('/pipeline/export-csv', {
      params: { project_id: projectId, is_target: isTarget },
      responseType: 'blob',
    });
    return response.data;
  },

  // Export contacts CSV (one row per contact, for Smartlead)
  exportContactsCsv: async (projectId?: number, emailOnly?: boolean, phoneOnly?: boolean): Promise<Blob> => {
    const response = await api.get('/pipeline/export-contacts-csv', {
      params: { project_id: projectId, email_only: emailOnly, phone_only: phoneOnly },
      responseType: 'blob',
    });
    return response.data;
  },

  // Export contacts to Google Sheets
  exportContactsSheet: async (projectId?: number, emailOnly?: boolean, phoneOnly?: boolean): Promise<{
    url: string;
    rows: number;
  }> => {
    const response = await api.post('/pipeline/export-contacts-sheet', null, {
      params: { project_id: projectId, email_only: emailOnly, phone_only: phoneOnly },
    });
    return response.data;
  },
};
