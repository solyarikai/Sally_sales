import api from './client';

// Types
export interface Prospect {
  id: number;
  email: string | null;
  linkedin_url: string | null;
  first_name: string | null;
  last_name: string | null;
  full_name: string | null;
  company_name: string | null;
  company_domain: string | null;
  company_linkedin: string | null;
  job_title: string | null;
  phone: string | null;
  location: string | null;
  country: string | null;
  city: string | null;
  industry: string | null;
  company_size: string | null;
  website: string | null;
  custom_fields: Record<string, any>;
  sources: Array<{
    dataset_id: number;
    dataset_name: string;
    row_id: number;
    added_at: string;
  }>;
  enrichment_history: any[];
  is_verified: number;
  // Outreach tracking - Email
  sent_to_email: boolean;
  sent_to_email_at: string | null;
  email_campaign_id: string | null;
  email_campaign_name: string | null;
  email_tool: string | null;
  // Outreach tracking - LinkedIn
  sent_to_linkedin: boolean;
  sent_to_linkedin_at: string | null;
  linkedin_campaign_id: string | null;
  linkedin_campaign_name: string | null;
  linkedin_tool: string | null;
  // Status
  status: string;
  status_updated_at: string | null;
  // Segment
  segment_id: number | null;
  segment_name: string | null;
  // Other
  tags: string[];
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface LeadStatus {
  value: string;
  label: string;
  color: string;
}

export interface ProspectActivity {
  id: number;
  prospect_id: number;
  activity_type: string;
  description: string | null;
  activity_data: Record<string, any>;
  created_at: string;
}

export interface ProspectsListResponse {
  prospects: Prospect[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface FieldMapping {
  source_column: string;
  target_field: string;
  custom_field_name?: string;
  confidence: number;
}

export interface FieldMappingSuggestion {
  mappings: FieldMapping[];
  unmapped_columns: string[];
}

export interface AddToProspectsRequest {
  dataset_id: number;
  row_ids?: number[];
  field_mappings: FieldMapping[];
}

export interface AddToProspectsResponse {
  success: boolean;
  total_processed: number;
  new_prospects: number;
  updated_prospects: number;
  errors: string[];
}

export interface ProspectStats {
  total_prospects: number;
  prospects_with_email: number;
  prospects_with_linkedin: number;
  sent_to_email: number;
  sent_to_linkedin: number;
  recent_additions: number;
  call_done: number;
  status_new: number;
  status_contacted: number;
  status_interested: number;
  status_not_interested: number;
}

export interface CoreField {
  name: string;
  label: string;
  type: string;
}

export interface ColumnInfo {
  field: string;
  header: string;
  type: string;
  custom?: boolean;
}

export interface ProspectFilters {
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  search?: string;
  status?: string;
  sent_to_email?: boolean;
  sent_to_linkedin?: boolean;
  has_email?: boolean;
  has_linkedin?: boolean;
  segment_id?: number;
}

// API functions
export const prospectsApi = {
  // Get paginated list of prospects
  getProspects: async (params: ProspectFilters = {}): Promise<ProspectsListResponse> => {
    const searchParams = new URLSearchParams();
    if (params.page) searchParams.set('page', params.page.toString());
    if (params.page_size) searchParams.set('page_size', params.page_size.toString());
    if (params.sort_by) searchParams.set('sort_by', params.sort_by);
    if (params.sort_order) searchParams.set('sort_order', params.sort_order);
    if (params.search) searchParams.set('search', params.search);
    if (params.status) searchParams.set('status', params.status);
    if (params.sent_to_email !== undefined) searchParams.set('sent_to_email', params.sent_to_email.toString());
    if (params.sent_to_linkedin !== undefined) searchParams.set('sent_to_linkedin', params.sent_to_linkedin.toString());
    if (params.has_email) searchParams.set('has_email', 'true');
    if (params.has_linkedin) searchParams.set('has_linkedin', 'true');
    if (params.segment_id) searchParams.set('segment_id', params.segment_id.toString());
    
    const response = await api.get(`/prospects?${searchParams.toString()}`);
    return response.data;
  },

  // Get prospect statistics
  getStats: async (): Promise<ProspectStats> => {
    const response = await api.get('/prospects/stats');
    return response.data;
  },

  // Get all available columns
  getColumns: async (): Promise<ColumnInfo[]> => {
    const response = await api.get('/prospects/columns');
    return response.data;
  },

  // Get core fields definition
  getCoreFields: async (): Promise<CoreField[]> => {
    const response = await api.get('/prospects/core-fields');
    return response.data;
  },

  // Get AI-powered field mapping suggestions
  suggestMapping: async (params: {
    dataset_id: number;
    columns: string[];
    sample_data?: Record<string, any>[];
  }): Promise<FieldMappingSuggestion> => {
    const response = await api.post('/prospects/suggest-mapping', params);
    return response.data;
  },

  // Add prospects from dataset
  addFromDataset: async (request: AddToProspectsRequest): Promise<AddToProspectsResponse> => {
    const response = await api.post('/prospects/add-from-dataset', request);
    return response.data;
  },

  // Get single prospect
  getProspect: async (id: number): Promise<Prospect> => {
    const response = await api.get(`/prospects/${id}`);
    return response.data;
  },

  // Update prospect
  updateProspect: async (id: number, updates: Partial<Prospect>): Promise<Prospect> => {
    const response = await api.patch(`/prospects/${id}`, updates);
    return response.data;
  },

  // Delete prospect
  deleteProspect: async (id: number): Promise<void> => {
    await api.delete(`/prospects/${id}`);
  },

  // Delete multiple prospects
  deleteProspects: async (ids: number[]): Promise<{ deleted: number }> => {
    const response = await api.delete('/prospects', { data: ids });
    return response.data;
  },

  // Get prospect activities
  getActivities: async (id: number, limit?: number): Promise<ProspectActivity[]> => {
    const params = limit ? `?limit=${limit}` : '';
    const response = await api.get(`/prospects/${id}/activities${params}`);
    return response.data;
  },

  // Update tags
  updateTags: async (id: number, tags: string[]): Promise<Prospect> => {
    const response = await api.post(`/prospects/${id}/tags`, { tags });
    return response.data;
  },

  // Update notes
  updateNotes: async (id: number, notes: string): Promise<Prospect> => {
    const response = await api.patch(`/prospects/${id}/notes`, { notes });
    return response.data;
  },

  // Get lead statuses
  getStatuses: async (): Promise<LeadStatus[]> => {
    const response = await api.get('/prospects/statuses');
    return response.data;
  },

  // Update status
  updateStatus: async (id: number, status: string): Promise<Prospect> => {
    const response = await api.patch(`/prospects/${id}/status`, { status });
    return response.data;
  },

  // Mark as sent to email
  markSentToEmail: async (
    prospectIds: number[],
    campaignId: string,
    campaignName: string,
    tool: string = 'instantly'
  ): Promise<{ updated: number }> => {
    const response = await api.post('/prospects/mark-sent-email', {
      prospect_ids: prospectIds,
      campaign_id: campaignId,
      campaign_name: campaignName,
      tool
    });
    return response.data;
  },

  // Mark as sent to LinkedIn
  markSentToLinkedIn: async (
    prospectIds: number[],
    campaignId: string,
    campaignName: string,
    tool: string = 'expandi'
  ): Promise<{ updated: number }> => {
    const response = await api.post('/prospects/mark-sent-linkedin', {
      prospect_ids: prospectIds,
      campaign_id: campaignId,
      campaign_name: campaignName,
      tool
    });
    return response.data;
  },

  // Export as CSV
  exportCsv: async (prospectIds?: number[], columns?: string[]): Promise<Blob> => {
    const response = await api.post('/prospects/export/csv', 
      { prospect_ids: prospectIds, columns, include_custom_fields: true },
      { responseType: 'blob' }
    );
    return response.data;
  },

  // Export for clipboard (TSV)
  exportClipboard: async (prospectIds?: number[]): Promise<{
    data: string[][];
    row_count: number;
    columns: string[];
  }> => {
    const response = await api.post('/prospects/export/clipboard', {
      prospect_ids: prospectIds
    });
    return response.data;
  },
};
