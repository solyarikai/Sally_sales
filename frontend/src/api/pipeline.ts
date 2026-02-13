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

export interface SpendingDetail {
  yandex_cost: number;
  openai_cost_estimate: number;
  gemini_cost_estimate?: number;
  ai_cost_estimate?: number;
  crona_cost: number;
  apollo_credits_used: number;
  apollo_cost_estimate: number;
  total_estimate: number;
}

export interface PipelineStats {
  total_discovered: number;
  targets: number;
  targets_new: number;
  targets_in_campaigns: number;
  contacts_extracted: number;
  enriched: number;
  exported: number;
  rejected: number;
  total_contacts: number;
  total_apollo_people: number;
  spending?: SpendingDetail;
  apollo_contacts: number;
  apollo_with_email: number;
  apollo_with_linkedin: number;
  website_contacts: number;
  website_with_email: number;
  website_with_phone: number;
}

export interface AutoEnrichConfig {
  auto_extract: boolean;
  auto_apollo: boolean;
  apollo_titles: string[];
  apollo_max_people: number;
  apollo_max_credits: number;
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
    sort_by?: string;
    sort_order?: string;
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

  // Export to Google Sheet (companies)
  exportToGoogleSheet: async (projectId?: number, isTarget?: boolean): Promise<{ sheet_url: string }> => {
    const response = await api.post('/pipeline/export-sheet', {
      project_id: projectId,
      is_target: isTarget,
    });
    return response.data;
  },

  // Export contacts CSV (one row per contact, for Smartlead)
  exportContactsCsv: async (projectId?: number, emailOnly?: boolean, phoneOnly?: boolean, newOnly?: boolean): Promise<Blob> => {
    const response = await api.get('/pipeline/export-contacts-csv', {
      params: { project_id: projectId, email_only: emailOnly, phone_only: phoneOnly, new_only: newOnly },
      responseType: 'blob',
    });
    return response.data;
  },

  // Auto-enrich config
  getAutoEnrichConfig: async (projectId: number): Promise<AutoEnrichConfig> => {
    const response = await api.get(`/pipeline/auto-enrich-config/${projectId}`);
    return response.data;
  },

  updateAutoEnrichConfig: async (projectId: number, config: AutoEnrichConfig): Promise<AutoEnrichConfig> => {
    const response = await api.put(`/pipeline/auto-enrich-config/${projectId}`, config);
    return response.data;
  },

  // Export contacts to Google Sheets
  exportContactsSheet: async (projectId?: number, emailOnly?: boolean, phoneOnly?: boolean, newOnly?: boolean): Promise<{
    url: string;
    rows: number;
  }> => {
    const response = await api.post('/pipeline/export-contacts-sheet', null, {
      params: { project_id: projectId, email_only: emailOnly, phone_only: phoneOnly, new_only: newOnly },
    });
    return response.data;
  },

  // ===== Project-level convenience wrappers =====

  /** Fetch all target discovered companies for a project, then extract contacts from them. */
  extractContactsForProject: async (projectId: number, onProgress?: (done: number, total: number) => void): Promise<{
    processed: number;
    contacts_found: number;
    errors: number;
  }> => {
    const { items } = await pipelineApi.listDiscoveredCompanies({
      project_id: projectId,
      is_target: true,
      page_size: 200,
    });

    if (items.length === 0) return { processed: 0, contacts_found: 0, errors: 0 };

    const needExtraction = items.filter(c => (c.contacts_count || 0) === 0);
    if (needExtraction.length === 0) return { processed: 0, contacts_found: 0, errors: 0 };

    const ids = needExtraction.map(c => c.id);
    const BATCH = 10;
    let totalProcessed = 0, totalContacts = 0, totalErrors = 0;

    for (let i = 0; i < ids.length; i += BATCH) {
      const batch = ids.slice(i, i + BATCH);
      const result = await pipelineApi.extractContacts(batch);
      totalProcessed += result.processed;
      totalContacts += result.contacts_found;
      totalErrors += result.errors;
      onProgress?.(Math.min(i + BATCH, ids.length), ids.length);
    }

    return { processed: totalProcessed, contacts_found: totalContacts, errors: totalErrors };
  },

  /**
   * Server-side Apollo enrichment for entire project.
   * Queries ALL unenriched targets on backend — no pagination gap, no client-side batching.
   */
  enrichApolloForProject: async (projectId: number, config?: AutoEnrichConfig): Promise<{
    processed: number;
    people_found: number;
    errors: number;
    credits_used: number;
    skipped: number;
    total_unenriched: number;
  }> => {
    const response = await api.post(`/pipeline/enrich-project/${projectId}`, {
      max_people: config?.apollo_max_people ?? 5,
      titles: config?.apollo_titles,
      max_credits: config?.apollo_max_credits ?? 50,
    });
    return response.data;
  },

  // ===== Campaign Push Rules =====

  listPushRules: async (projectId: number): Promise<CampaignPushRule[]> => {
    const response = await api.get(`/pipeline/projects/${projectId}/push-rules`);
    return response.data;
  },

  createPushRule: async (projectId: number, rule: CampaignPushRuleCreate): Promise<CampaignPushRule> => {
    const response = await api.post(`/pipeline/projects/${projectId}/push-rules`, rule);
    return response.data;
  },

  updatePushRule: async (ruleId: number, updates: Partial<CampaignPushRuleCreate>): Promise<CampaignPushRule> => {
    const response = await api.put(`/pipeline/push-rules/${ruleId}`, updates);
    return response.data;
  },

  deletePushRule: async (ruleId: number): Promise<void> => {
    await api.delete(`/pipeline/push-rules/${ruleId}`);
  },

  pushToSmartlead: async (projectId: number): Promise<{ status: string; project_id: number }> => {
    const response = await api.post(`/pipeline/projects/${projectId}/push-to-smartlead`);
    return response.data;
  },

  listSmartleadEmailAccounts: async (): Promise<SmartleadEmailAccount[]> => {
    const response = await api.get('/pipeline/smartlead/email-accounts');
    return response.data;
  },

  // Full pipeline control
  startFullPipeline: async (projectId: number, config: FullPipelineConfig): Promise<{ status: string; project_id: number }> => {
    const response = await api.post(`/pipeline/full-pipeline/${projectId}`, config);
    return response.data;
  },

  getFullPipelineStatus: async (projectId: number): Promise<FullPipelineStatus> => {
    const response = await api.get(`/pipeline/full-pipeline/${projectId}/status`);
    return response.data;
  },

  stopFullPipeline: async (projectId: number): Promise<{ status: string }> => {
    const response = await api.post(`/pipeline/full-pipeline/${projectId}/stop`);
    return response.data;
  },

  generateSequences: async (req: GenerateSequencesRequest): Promise<GenerateSequencesResponse> => {
    const response = await api.post('/pipeline/generate-sequences', req);
    return response.data;
  },
};

// ============ Push Rules Types ============

export interface CampaignPushRule {
  id: number;
  project_id: number;
  name: string;
  description?: string;
  language: string;
  has_first_name?: boolean | null;
  name_pattern?: string;
  campaign_name_template: string;
  sequence_language: string;
  sequence_template?: any[];
  use_first_name_var: boolean;
  email_account_ids?: number[];
  schedule_config?: Record<string, any>;
  campaign_settings?: Record<string, any>;
  max_leads_per_campaign: number;
  priority: number;
  is_active: boolean;
  current_campaign_id?: string;
  current_campaign_lead_count?: number;
  created_at?: string;
  updated_at?: string;
}

export interface CampaignPushRuleCreate {
  name: string;
  description?: string;
  language: string;
  has_first_name?: boolean | null;
  name_pattern?: string;
  campaign_name_template: string;
  sequence_language: string;
  sequence_template?: any[];
  use_first_name_var: boolean;
  email_account_ids?: number[];
  schedule_config?: Record<string, any>;
  campaign_settings?: Record<string, any>;
  max_leads_per_campaign?: number;
  priority?: number;
  is_active?: boolean;
}

export interface SmartleadEmailAccount {
  id: number;
  email: string;
  name: string;
}

export interface FullPipelineConfig {
  max_queries?: number;
  target_goal?: number;
  apollo_search?: boolean;
  apollo_credits?: number;
  apollo_max_people?: number;
  apollo_titles?: string[];
  skip_search?: boolean;
  skip_extraction?: boolean;
  skip_enrichment?: boolean;
  skip_smartlead_push?: boolean;
}

export interface GenerateSequencesRequest {
  project_id: number;
  language: string;
  use_first_name: boolean;
  tone?: string;
  num_steps?: number;
  custom_instructions?: string;
}

export interface GenerateSequencesResponse {
  sequences: any[];
  language: string;
  use_first_name: boolean;
  tokens?: Record<string, number>;
}

export interface FullPipelineStatus {
  running: boolean;
  phase: string;
  started_at?: string;
  config?: FullPipelineConfig;
  targets_before_search?: number;
  search_results?: Record<string, any>;
  targets_after_search?: number;
  new_targets_from_search?: number;
  extraction_total?: number;
  extraction_stats?: Record<string, number>;
  enrichment_total?: number;
  enrichment_stats?: Record<string, number>;
  smartlead_push_stats?: Record<string, any>;
  completed_at?: string;
  error?: string;
  stop_requested?: boolean;
}
