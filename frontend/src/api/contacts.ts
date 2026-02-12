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
  project_id?: number;
  project_name?: string;
  source: string;
  source_id?: string;
  status: string;
  phone?: string;
  linkedin_url?: string;
  location?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
  has_replied?: boolean;
  has_smartlead?: boolean;
  has_getsales?: boolean;
  campaign?: string;
  campaigns?: Array<{ id: string; name: string; source: string; status?: string }>;
  needs_followup?: boolean;
  smartlead_id?: string;
  getsales_id?: string;
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
  projects: Array<{ id: number; name: string }>;
}

export interface Project {
  id: number;
  name: string;
  description?: string;
  target_industries?: string;
  target_segments?: string;
  campaign_filters?: string[];
  telegram_chat_id?: string;
  telegram_username?: string;
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

export interface ImportResult {
  success: boolean;
  total_rows: number;
  created: number;
  skipped: number;
  errors: string[];
  sample_created: string[];
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
  has_replied: boolean;
  last_reply_at?: string;
  reply_channel?: string;
  smartlead_status?: string;
  getsales_status?: string;
  last_synced_at?: string;
  activities: ContactActivity[];
}

export interface SyncStatus {
  total_contacts: number;
  by_source: Record<string, number>;
  replied_contacts: number;
  total_activities: number;
  last_synced_at?: string;
}

export interface ContactFilters {
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  search?: string;
  project_id?: number;
  segment?: string;
  status?: string;
  source?: string;
  has_replied?: boolean;
  has_smartlead?: boolean;
  has_getsales?: boolean;
  campaign?: string;
  needs_followup?: boolean;
  smartlead_id?: string;
  getsales_id?: string;
  created_after?: string;
  created_before?: string;
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

  // Export contacts as CSV
  async exportCsv(contactIds?: number[]): Promise<Blob> {
    const response = await api.post('/contacts/export/csv', 
      contactIds ? { contact_ids: contactIds } : {},
      { responseType: 'blob' }
    );
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

  // List projects
  async listProjects(): Promise<Project[]> {
    const response = await api.get('/contacts/projects/list');
    return response.data;
  },

  // Create project
  async createProject(project: { name: string; description?: string; campaign_filters?: string[] }): Promise<Project> {
    const response = await api.post('/contacts/projects', project);
    return response.data;
  },

  // Update project
  async updateProject(id: number, updates: { name?: string; description?: string; campaign_filters?: string[]; telegram_username?: string }): Promise<Project> {
    const response = await api.patch(`/contacts/projects/${id}`, updates);
    return response.data;
  },

  // Delete project
  async deleteProject(id: number): Promise<void> {
    await api.delete(`/contacts/projects/${id}`);
  },

  // AI SDR - Get project with generated content
  async getProjectAISDR(projectId: number): Promise<AISDRProject> {
    const response = await api.get(`/contacts/projects/${projectId}/ai-sdr`);
    return response.data;
  },

  // AI SDR - Generate TAM analysis
  async generateTAM(projectId: number): Promise<AISDRGenerationResult> {
    const response = await api.post(`/contacts/projects/${projectId}/generate-tam`);
    return response.data;
  },

  // AI SDR - Generate GTM plan
  async generateGTM(projectId: number): Promise<AISDRGenerationResult> {
    const response = await api.post(`/contacts/projects/${projectId}/generate-gtm`);
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
};
