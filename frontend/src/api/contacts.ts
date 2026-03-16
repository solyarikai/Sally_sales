import { api } from './client';

export interface Contact {
  id: number;
  email: string;
  first_name?: string;
  last_name?: string;
  company_name?: string;
  domain?: string;
  job_title?: string;
  segment?: string;
  suitable_for?: string[];
  geo?: string;
  project_id?: number;
  project_name?: string;
  source: string;
  source_id?: string;
  status: string;
  status_external?: string;
  phone?: string;
  linkedin_url?: string;
  location?: string;
  notes?: string;
  smartlead_id?: string;
  getsales_id?: string;
  // Canonical funnel
  last_reply_at?: string;
  has_replied?: boolean;       // computed by backend from last_reply_at
  needs_followup?: boolean;
  // Reply classification (enriched from ProcessedReply)
  latest_reply_category?: string;
  latest_reply_confidence?: string;
  // Canonical data
  provenance?: Record<string, any>;
  platform_state?: Record<string, any>;
  campaigns?: Array<{ id: string; name: string; source: string; status?: string }>;
  // Timestamps
  created_at: string;
  updated_at: string;
}

export interface ContactListResponse {
  contacts: Contact[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ContactStats {
  total: number;
  by_status: Record<string, number>;
  by_segment: Record<string, number>;
  by_source: Record<string, number>;
  by_project: Record<string, number>;
}

export interface FilterOptions {
  statuses: string[];
  sources: string[];
  segments: string[];
  geos: string[];
  projects: Array<{ id: number; name: string }>;
}

export interface SheetSyncConfig {
  enabled: boolean;
  sheet_id: string;
  leads_tab?: string;
  replies_tab?: string;
  last_replies_sync_at?: string;
  last_leads_push_at?: string;
  last_qualification_poll_at?: string;
  replies_synced_count?: number;
  leads_pushed_count?: number;
  last_error?: string | null;
  last_error_at?: string | null;
}

export interface CampaignOwnershipRules {
  prefixes?: string[];
  contains?: string[];
  smartlead_tags?: string[];
}

export interface Project {
  id: number;
  name: string;
  description?: string;
  target_industries?: string;
  target_segments?: string;
  campaign_filters?: string[];
  campaign_ownership_rules?: CampaignOwnershipRules | null;
  telegram_chat_id?: string;
  telegram_username?: string;
  webhooks_enabled?: boolean;
  sheet_sync_config?: SheetSyncConfig | null;
  sdr_email?: string;  // SDR email for test campaign notifications
  contact_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectLite {
  id: number;
  name: string;
  campaign_filters: string[];
  telegram_username?: string;
}

export interface AISDRProject extends Project {
  tam_analysis?: string;
  gtm_plan?: string;
  pitch_templates?: string;
}

export interface AISDRGenerationResult {
  success: boolean;
  tam_analysis?: string;
  gtm_plan?: string;
  pitch_templates?: string;
}

export interface TelegramSubscriber {
  id: number;
  chat_id: string;
  username: string | null;
  first_name: string | null;
  subscribed_at: string | null;
}

export interface TelegramStatus {
  connected: boolean;
  first_name?: string;
  username?: string;
  subscribers: TelegramSubscriber[];
}

export interface ProjectMonitoring {
  project: { id: number; name: string; webhooks_enabled: boolean };
  scheduler: { running: boolean; task_health: Record<string, string> };
  webhooks: { healthy: boolean; last_received: string | null; last_check: string | null };
  polling: {
    intervals: { task: string; interval_seconds: number | null; last_run: string | null; next_run: string | null }[];
    reply_checks_count: number;
    sync_count: number;
  };
  reply_stats: {
    total_contacts: number;
    total_replied: number;
    replies_24h: number;
    replies_7d: number;
    failed_events_24h: number;
  };
  campaigns: {
    name: string;
    platform: string;
    status: string;
    active: boolean;
    contacts: number;
    replied: number;
    external_id: string | null;
  }[];
  active_campaigns_count: number;
  latest_events: {
    events: {
      id: string;
      type: string;
      source: string | null;
      channel: string | null;
      campaign_name: string | null;
      lead_email: string | null;
      lead_name: string | null;
      category: string | null;
      approval_status: string | null;
      at: string | null;
      error?: string | null;
    }[];
  };
}

export interface GTMData {
  project_id: number;
  project_name: string;
  total_contacts: number;
  classified: number;
  unclassified: number;
  avg_confidence: number | null;
  segments: Array<{ segment: string; count: number }>;
  industries: Array<{ industry: string; count: number }>;
  top_keywords: Array<{ keyword: string; count: number }>;
  cross_project_matches: Array<{ target: string; count: number }>;
  status_by_segment: Record<string, Record<string, number>>;
  gtm_plan: string | null;
}

export interface SegmentFunnelSegment {
  segment: string;
  total_contacts: number;
  total_replies: number;
  positive: number;
  meeting_requests: number;
  interested: number;
  questions: number;
  not_interested: number;
  ooo: number;
  reply_rate: number;
  positive_rate: number;
}

export interface SegmentFunnelData {
  project_id: number;
  period: string;
  totals: {
    total_contacts: number;
    total_replies: number;
    positive: number;
    meeting_requests: number;
  };
  segments: SegmentFunnelSegment[];
}

export interface GTMStrategyLogEntry {
  id: number;
  trigger: string;
  model: string;
  status: string;
  input_summary: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: string | null;
  error_message: string | null;
  created_at: string | null;
  has_strategy: boolean;
}

export interface GTMStrategyLogsResponse {
  items: GTMStrategyLogEntry[];
  total: number;
}

export interface ImportResult {
  success: boolean;
  total_rows: number;
  created: number;
  skipped: number;
  errors: string[];
  sample_created: string[];
}

export interface EnrichResult {
  success: boolean;
  total_rows: number;
  enriched: number;
  skipped: number;
  not_found: number;
  errors: string[];
}

export interface ContactCreate {
  email: string;
  first_name?: string;
  last_name?: string;
  company_name?: string;
  domain?: string;
  job_title?: string;
  segment?: string;
  project_id?: number;
  source?: string;
  status?: string;
  phone?: string;
  linkedin_url?: string;
  location?: string;
  notes?: string;
}

// Activity tracking
export interface ContactActivity {
  id: number;
  contact_id: number;
  activity_type: string;
  channel: string;
  direction?: string;
  source: string;
  subject?: string;
  snippet?: string;
  activity_at: string;
  created_at: string;
}

export interface ContactWithActivities extends Contact {
  activities: ContactActivity[];
}

export interface SyncStatus {
  total_contacts: number;
  by_source: Record<string, number>;
  replied_contacts: number;
  total_activities: number;
}

export interface ContactFilters {
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  search?: string;
  project_id?: number;
  segment?: string;
  geo?: string;
  status?: string;
  source?: string;
  has_replied?: boolean;
  has_smartlead?: boolean;
  has_getsales?: boolean;
  campaign?: string;
  campaign_id?: string;
  needs_followup?: boolean;
  smartlead_id?: string;
  getsales_id?: string;
  created_after?: string;
  created_before?: string;
  domain?: string;
  suitable_for?: string;
  reply_category?: string;
  reply_since?: string;
  source_id?: string;
}

export interface GenerateReplyResponse {
  has_reply: boolean;
  cached?: boolean;
  category?: string;
  draft_subject?: string;
  draft_body?: string;
  channel?: string;
  reply_text?: string;
  message?: string;
  error?: string;
  contact?: { name: string; email: string; company: string };
}

export interface OperatorTask {
  id: number;
  project_id?: number;
  contact_id?: number;
  task_type: string;
  title: string;
  description?: string;
  due_at: string;
  status: string;
  contact_email?: string;
  contact_name?: string;
  created_at: string;
  updated_at: string;
}

export interface TasksListResponse {
  tasks: OperatorTask[];
  total: number;
  pending: number;
  done: number;
}

export const contactsApi = {
  // List contacts with filters
  async list(filters: ContactFilters = {}): Promise<ContactListResponse> {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params.append(key, String(value));
      }
    });
    const response = await api.get(`/contacts?${params.toString()}`);
    return response.data;
  },

  // Get contact stats
  async getStats(): Promise<ContactStats> {
    const response = await api.get('/contacts/stats');
    return response.data;
  },

  // Get filter options
  async getFilterOptions(): Promise<FilterOptions> {
    const response = await api.get('/contacts/filters');
    return response.data;
  },

  // Create contact
  async create(contact: ContactCreate): Promise<Contact> {
    const response = await api.post('/contacts', contact);
    return response.data;
  },

  // Update contact
  async update(id: number, updates: Partial<ContactCreate>): Promise<Contact> {
    const response = await api.patch(`/contacts/${id}`, updates);
    return response.data;
  },

  // Delete contact
  async delete(id: number): Promise<void> {
    await api.delete(`/contacts/${id}`);
  },

  // Delete multiple contacts
  async deleteMany(ids: number[]): Promise<{ deleted: number }> {
    const response = await api.delete('/contacts', { data: ids });
    return response.data;
  },

  // Bulk create contacts
  async bulkCreate(contacts: ContactCreate[]): Promise<{ created: number; skipped: number }> {
    const response = await api.post('/contacts/bulk', contacts);
    return response.data;
  },

  // Export contacts as CSV (with filters or specific IDs)
  async exportCsv(filters?: ContactFilters & { contact_ids?: number[] }): Promise<Blob> {
    const response = await api.post('/contacts/export/csv', 
      filters || {},
      { responseType: 'blob' }
    );
    return response.data;
  },

  // Export contacts to Google Sheet (with filters)
  async exportGoogleSheet(filters: ContactFilters & { contact_ids?: number[] }): Promise<{ url: string; rows: number }> {
    const response = await api.post('/contacts/export/google-sheet', filters);
    return response.data;
  },

  // Verify campaign counts (DB vs SmartLead)
  async verifyCampaigns(projectId: number): Promise<{
    campaigns: Array<{
      name: string;
      campaign_id: string | null;
      db_count: number;
      db_rule_count: number;
      smartlead_count: number | null;
      match: boolean;
      error: string | null;
    }>;
    total_db: number;
    total_smartlead: number;
    all_match: boolean;
  }> {
    const response = await api.get(`/contacts/verify-campaigns?project_id=${projectId}`);
    return response.data;
  },

  // Import contacts from CSV
  async importCsv(
    file: File, 
    options?: { project_id?: number; segment?: string; skip_duplicates?: boolean }
  ): Promise<ImportResult> {
    const formData = new FormData();
    formData.append('file', file);
    
    const params = new URLSearchParams();
    if (options?.project_id) params.append('project_id', String(options.project_id));
    if (options?.segment) params.append('segment', options.segment);
    if (options?.skip_duplicates !== undefined) params.append('skip_duplicates', String(options.skip_duplicates));
    
    const url = `/contacts/import/csv${params.toString() ? '?' + params.toString() : ''}`;
    const response = await api.post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },

  // Enrich existing contacts from CSV (fill empty fields only)
  async enrichCsv(
    file: File,
    options?: { project_id?: number }
  ): Promise<EnrichResult> {
    const formData = new FormData();
    formData.append('file', file);

    const params = new URLSearchParams();
    if (options?.project_id) params.append('project_id', String(options.project_id));

    const url = `/contacts/enrich/csv${params.toString() ? '?' + params.toString() : ''}`;
    const response = await api.post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },

  // Push selected contacts to a new SmartLead draft campaign
  async pushToSmartlead(contactIds: number[], campaignName?: string, opts?: { source_id?: string; project_id?: number }): Promise<{
    campaign_id: string;
    campaign_name: string;
    campaign_url: string;
    leads_added: number;
    leads_total: number;
    error?: string;
  }> {
    const response = await api.post('/contacts/push-to-smartlead', {
      contact_ids: contactIds,
      campaign_name: campaignName || undefined,
      source_id: opts?.source_id,
      project_id: opts?.project_id,
    });
    return response.data;
  },

  // Download import template
  async getImportTemplate(): Promise<Blob> {
    const response = await api.get('/contacts/import/template', { responseType: 'blob' });
    return response.data;
  },

  // List projects (lightweight — no contact counts)
  async listProjectsLite(): Promise<ProjectLite[]> {
    const response = await api.get('/contacts/projects/list-lite');
    return response.data;
  },

  // List projects (full data — slow, use listProjectNames for dropdowns)
  async listProjects(): Promise<Project[]> {
    const response = await api.get('/contacts/projects/list');
    return response.data;
  },

  // List project names only (fast — for dropdowns and nav)
  async listProjectNames(): Promise<Pick<Project, 'id' | 'name'>[]> {
    const response = await api.get('/contacts/projects/names');
    return response.data;
  },

  // Get single project by ID
  async getProject(id: number): Promise<Project> {
    const response = await api.get(`/contacts/projects/${id}`);
    return response.data;
  },

  // Create project
  async createProject(project: { name: string; description?: string; campaign_filters?: string[] }): Promise<Project> {
    const response = await api.post('/contacts/projects', project);
    return response.data;
  },

  // Update project
  async updateProject(id: number, updates: { name?: string; description?: string; campaign_filters?: string[]; campaign_ownership_rules?: CampaignOwnershipRules | Record<string, string[]> | null; telegram_username?: string; webhooks_enabled?: boolean; sheet_sync_config?: SheetSyncConfig | null; sdr_email?: string }): Promise<Project> {
    const response = await api.patch(`/contacts/projects/${id}`, updates);
    return response.data;
  },

  // Delete project
  async deleteProject(id: number): Promise<void> {
    await api.delete(`/contacts/projects/${id}`);
  },

  async getTelegramStatus(projectId: number): Promise<TelegramStatus> {
    const response = await api.get(`/replies/telegram/project-status`, { params: { project_id: projectId } });
    return response.data;
  },

  async disconnectTelegram(projectId: number, chatId?: string): Promise<void> {
    const params: Record<string, string | number> = { project_id: projectId };
    if (chatId) params.chat_id = chatId;
    await api.post(`/replies/telegram/disconnect`, null, { params });
  },

  // Calendly integration
  async getCalendlyStatus(projectId: number): Promise<{ connected: boolean; user_name?: string; user_email?: string; webhook_url: string }> {
    const response = await api.get(`/replies/calendly/project-status`, { params: { project_id: projectId } });
    return response.data;
  },

  async connectCalendly(projectId: number, token: string): Promise<{ ok: boolean; user_name: string; user_email: string; webhook_url: string; message: string }> {
    const response = await api.post(`/replies/calendly/connect`, { token }, { params: { project_id: projectId } });
    return response.data;
  },

  async disconnectCalendly(projectId: number): Promise<void> {
    await api.post(`/replies/calendly/disconnect`, null, { params: { project_id: projectId } });
  },

  // Fireflies integration (per-project)
  async getFirefliesStatus(projectId: number): Promise<{ connected: boolean; user_name?: string; user_email?: string; webhook_url: string }> {
    const response = await api.get(`/fireflies/project-status`, { params: { project_id: projectId } });
    return response.data;
  },

  async connectFireflies(projectId: number, token: string): Promise<{ ok: boolean; user_name: string; user_email: string; webhook_url: string; message: string }> {
    const response = await api.post(`/fireflies/connect`, { token }, { params: { project_id: projectId } });
    return response.data;
  },

  async disconnectFireflies(projectId: number): Promise<void> {
    await api.post(`/fireflies/disconnect`, null, { params: { project_id: projectId } });
  },

  // Project monitoring data
  async getProjectMonitoring(projectId: number): Promise<ProjectMonitoring> {
    const response = await api.get(`/crm-sync/project/${projectId}/monitoring`);
    return response.data;
  },

  // AI SDR - Get project with generated content
  async getProjectAISDR(projectId: number): Promise<AISDRProject> {
    const response = await api.get(`/contacts/projects/${projectId}/ai-sdr`);
    return response.data;
  },

  // GTM data — real segment stats from DB
  async getGTMData(projectId: number): Promise<GTMData> {
    const response = await api.get(`/contacts/projects/${projectId}/gtm-data`);
    return response.data;
  },

  // Segment funnel analytics — campaign-name-derived segments
  async getSegmentFunnel(projectId: number, period: string = 'all'): Promise<SegmentFunnelData> {
    const response = await api.get(`/contacts/projects/${projectId}/segment-funnel`, {
      params: { period },
    });
    return response.data;
  },

  // GTM strategy logs
  async getGTMStrategyLogs(projectId: number, page = 1): Promise<GTMStrategyLogsResponse> {
    const response = await api.get(`/contacts/projects/${projectId}/gtm-strategy-logs`, {
      params: { page, page_size: 20 },
    });
    return response.data;
  },

  // GTM strategy log detail (specific log with full strategy JSON)
  async getGTMStrategyLogDetail(projectId: number, logId: number): Promise<{
    id: number;
    trigger: string;
    strategy_json: string | null;
    cost_usd: string | null;
    input_tokens: number | null;
    output_tokens: number | null;
    created_at: string | null;
  }> {
    const response = await api.get(`/contacts/projects/${projectId}/gtm-strategy-logs/${logId}`);
    return response.data;
  },

  // AI SDR - Generate TAM analysis
  async generateTAM(projectId: number): Promise<AISDRGenerationResult> {
    const response = await api.post(`/contacts/projects/${projectId}/generate-tam`);
    return response.data;
  },

  // AI SDR - Generate GTM plan (Gemini 2.5)
  async generateGTM(projectId: number): Promise<AISDRGenerationResult> {
    const response = await api.post(`/contacts/projects/${projectId}/generate-gtm`);
    return response.data;
  },

  // CRM Spotlight GTM — analyze warm contacts + conversations with Gemini 2.5 Pro
  async crmSpotlightGTM(projectId: number, question: string, filters?: Record<string, any>): Promise<{
    success: boolean;
    gtm_plan?: string;
    contacts_analyzed?: number;
    project_slug?: string;
  }> {
    const response = await api.post(`/contacts/projects/${projectId}/crm-spotlight-gtm`, {
      question,
      filters: filters || {},
    });
    return response.data;
  },

  // AI SDR - Generate pitch templates
  async generatePitches(projectId: number): Promise<AISDRGenerationResult> {
    const response = await api.post(`/contacts/projects/${projectId}/generate-pitches`);
    return response.data;
  },

  // AI SDR - Generate all content
  async generateAllAISDR(projectId: number): Promise<AISDRGenerationResult> {
    const response = await api.post(`/contacts/projects/${projectId}/generate-all`);
    return response.data;
  },

  // Get contact with full activity history
  async getContactWithActivities(contactId: number): Promise<ContactWithActivities> {
    const response = await api.get(`/crm-sync/contacts/${contactId}/full`);
    return response.data;
  },

  // Get contact activities
  async getContactActivities(contactId: number, limit = 50): Promise<ContactActivity[]> {
    const response = await api.get(`/crm-sync/contacts/${contactId}/activities?limit=${limit}`);
    return response.data;
  },

  // Get recent replies
  async getRecentReplies(limit = 50): Promise<ContactWithActivities[]> {
    const response = await api.get(`/crm-sync/replies/recent?limit=${limit}`);
    return response.data;
  },

  // Get sync status
  async getSyncStatus(): Promise<SyncStatus> {
    const response = await api.get('/crm-sync/status');
    return response.data;
  },

  // Trigger manual sync
  async triggerSync(sources = ['smartlead', 'getsales']): Promise<{ success: boolean; message: string }> {
    const response = await api.post('/crm-sync/trigger', { sources, full_sync: true });
    return response.data;
  },

  // Generate AI draft reply for a contact
  async generateReply(contactId: number): Promise<GenerateReplyResponse> {
    const response = await api.post(`/contacts/${contactId}/generate-reply`);
    return response.data;
  },

  // Update contact status (with Smartlead sync + auto-task creation)
  async updateStatus(contactId: number, status: string, syncToSmartlead = true): Promise<any> {
    const response = await api.patch(`/contacts/${contactId}/status`, {
      status,
      sync_to_smartlead: syncToSmartlead,
    });
    return response.data;
  },

  // Tasks
  async listTasks(params: { project_id?: number; status?: string; contact_id?: number } = {}): Promise<TasksListResponse> {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
    const response = await api.get(`/tasks?${searchParams.toString()}`);
    return response.data;
  },

  async updateTask(taskId: number, updates: { status?: string; title?: string }): Promise<OperatorTask> {
    const response = await api.patch(`/tasks/${taskId}`, updates);
    return response.data;
  },

  // Sheet sync
  async getSheetSyncStatus(projectId: number): Promise<Record<string, any>> {
    const response = await api.get(`/contacts/projects/${projectId}/sheet-sync/status`);
    return response.data;
  },

  async testSheetConnection(projectId: number): Promise<{
    success: boolean;
    sheet_title?: string;
    tabs?: Array<{ name: string; row_count: number }>;
    leads_tab_found: boolean;
    replies_tab_found: boolean;
    leads_headers?: string[];
    service_account?: string;
  }> {
    const response = await api.post(`/contacts/projects/${projectId}/sheet-sync/test`);
    return response.data;
  },

  async triggerSheetSync(projectId: number, syncType: 'all' | 'replies' | 'leads' | 'qualification' = 'all'): Promise<Record<string, any>> {
    const response = await api.post(`/contacts/projects/${projectId}/sheet-sync/trigger?sync_type=${syncType}`);
    return response.data;
  },
};
