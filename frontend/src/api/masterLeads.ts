import api from './client';

// Types
export interface MasterLead {
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
  created_at: string;
  updated_at: string;
}

export interface MasterLeadsListResponse {
  leads: MasterLead[];
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

export interface AddToMasterRequest {
  dataset_id: number;
  row_ids?: number[];
  field_mappings: FieldMapping[];
}

export interface AddToMasterResponse {
  success: boolean;
  total_processed: number;
  new_leads: number;
  updated_leads: number;
  errors: string[];
}

export interface MasterLeadsStats {
  total_leads: number;
  leads_with_email: number;
  leads_with_linkedin: number;
  sources_count: Record<string, number>;
  recent_additions: number;
}

export interface CoreField {
  name: string;
  label: string;
  type: string;
}

// API functions
export const masterLeadsApi = {
  // Get paginated list of master leads
  getLeads: async (params: {
    page?: number;
    page_size?: number;
    search?: string;
  } = {}): Promise<MasterLeadsListResponse> => {
    const searchParams = new URLSearchParams();
    if (params.page) searchParams.set('page', params.page.toString());
    if (params.page_size) searchParams.set('page_size', params.page_size.toString());
    if (params.search) searchParams.set('search', params.search);
    
    const response = await api.get(`/master-leads?${searchParams.toString()}`);
    return response.data;
  },

  // Get master leads statistics
  getStats: async (): Promise<MasterLeadsStats> => {
    const response = await api.get('/master-leads/stats');
    return response.data;
  },

  // Get core fields definition
  getCoreFields: async (): Promise<CoreField[]> => {
    const response = await api.get('/master-leads/core-fields');
    return response.data;
  },

  // Get AI-powered field mapping suggestions
  suggestMapping: async (params: {
    dataset_id: number;
    columns: string[];
    sample_data?: Record<string, any>[];
  }): Promise<FieldMappingSuggestion> => {
    const response = await api.post('/master-leads/suggest-mapping', params);
    return response.data;
  },

  // Add leads from dataset to master database
  addFromDataset: async (request: AddToMasterRequest): Promise<AddToMasterResponse> => {
    const response = await api.post('/master-leads/add-from-dataset', request);
    return response.data;
  },

  // Get single lead
  getLead: async (id: number): Promise<MasterLead> => {
    const response = await api.get(`/master-leads/${id}`);
    return response.data;
  },

  // Delete lead
  deleteLead: async (id: number): Promise<void> => {
    await api.delete(`/master-leads/${id}`);
  },

  // Export leads as CSV
  exportLeads: async (leadIds?: number[]): Promise<Blob> => {
    const response = await api.post('/master-leads/export', 
      { lead_ids: leadIds },
      { responseType: 'blob' }
    );
    return response.data;
  },

  // Delete all leads
  deleteAllLeads: async (): Promise<{ deleted: number }> => {
    const response = await api.delete('/master-leads?confirm=true');
    return response.data;
  },
};
