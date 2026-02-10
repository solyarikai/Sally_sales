import { api } from './client';

// ============ Project Search Types ============

export interface SearchJobDetail {
  id: number;
  company_id: number;
  status: string;
  search_engine: string;
  queries_total: number;
  queries_completed: number;
  domains_found: number;
  domains_new: number;
  domains_trash: number;
  domains_duplicate: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  created_at?: string;
  project_id?: number;
  queries?: { id: number; query_text: string; status: string; domains_found: number }[];
}

export interface SearchResultItem {
  id: number;
  search_job_id: number;
  project_id?: number;
  domain: string;
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
  scores?: {
    language_match?: number;
    industry_match?: number;
    service_match?: number;
    company_type?: number;
    geography_match?: number;
  };
  review_status?: 'confirmed' | 'rejected' | 'flagged';
  review_note?: string;
  reviewed_at?: string;
  html_snippet?: string;
  scraped_at?: string;
  analyzed_at?: string;
}

export interface SpendingInfo {
  queries_count: number;
  yandex_cost: number;
  openai_tokens_used: number;
  openai_cost_estimate: number;
  openai_analysis_tokens: number;
  openai_query_gen_tokens: number;
  openai_review_tokens: number;
  crona_credits_used: number;
  crona_cost: number;
  total_estimate: number;
}

export interface SearchProgressEvent {
  phase: string;
  status: string;
  current: number;
  total: number;
  domains_found: number;
  domains_new: number;
  results_analyzed: number;
  elapsed_seconds: number;
  estimated_remaining_seconds?: number;
  error_message?: string;
}

export interface ProjectInfo {
  id: number;
  name: string;
  description?: string;
  target_segments?: string;
  target_industries?: string;
}

export interface SearchFilter {
  field: string;
  value: string;
  operator?: 'equals' | 'contains' | 'starts_with' | 'in';
}

export interface CompanyResult {
  id: string;
  name: string;
  domain: string;
  industry: string;
  employee_count: string;
  location: string;
  founded_year?: number;
  linkedin_url?: string;
  description?: string;
  technologies?: string[];
  revenue_range?: string;
  relevance_score?: number;
  verified?: boolean;
  verification_confidence?: number;
  verification_reasons?: string[];
  verification_warnings?: string[];
  detected_industry?: string;
  ai_description?: string;
}

export interface VerificationCriteria {
  industry?: string;
  employee_count?: string;
  location?: string;
  technologies?: string[];
  keywords?: string[];
  description?: string;
}

export interface VerificationResult {
  company_id: string;
  company_name: string;
  domain?: string;
  verified: boolean;
  confidence: number;
  match_reasons: string[];
  mismatch_reasons: string[];
  error?: string;
  detected_industry?: string;
  detected_employee_count?: string;
  detected_location?: string;
  detected_technologies?: string[];
  company_description?: string;
}

export interface BatchVerificationResult {
  total: number;
  verified_count: number;
  failed_count: number;
  results: VerificationResult[];
  summary: string;
}

export interface ExtractedPattern {
  field: string;
  value: string;
  confidence: number;
  count: number;
  total: number;
}

export interface ReverseEngineerResponse {
  patterns: ExtractedPattern[];
  suggested_filters: SearchFilter[];
  analysis_summary: string;
  example_companies_analyzed: number;
  search_strategy?: {
    primary_filters: SearchFilter[];
    secondary_filters: SearchFilter[];
    search_tips: string[];
  };
}

export interface SearchLikeResponse {
  analysis: {
    patterns: ExtractedPattern[];
    analysis_summary: string;
    example_companies_analyzed: number;
  };
  filters_applied: SearchFilter[];
  results: CompanyResult[];
  total: number;
  search_strategy: {
    primary_filters: SearchFilter[];
    secondary_filters: SearchFilter[];
    search_tips: string[];
  };
}

export interface SearchResponse {
  companies: CompanyResult[];
  total: number;
  filters_applied: SearchFilter[];
  suggestions?: string[];
  next_page_token?: string;
}

export interface ParsedQuery {
  filters: SearchFilter[];
  intent: string;
  clarifications?: string[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  filters?: SearchFilter[];
  results?: CompanyResult[];
  total?: number;
}

export const dataSearchApi = {
  // Parse natural language query into filters
  parseQuery: async (query: string): Promise<ParsedQuery> => {
    const response = await api.post('/data-search/parse', { query });
    return response.data;
  },

  // Search companies with filters
  search: async (
    filters: SearchFilter[],
    page: number = 1,
    limit: number = 25
  ): Promise<SearchResponse> => {
    const response = await api.post('/data-search/search', {
      filters,
      page,
      limit,
    });
    return response.data;
  },

  // Chat-based search (combines parse + search)
  chat: async (
    message: string,
    conversationHistory: { role: string; content: string }[] = []
  ): Promise<{
    response: string;
    filters: SearchFilter[];
    results: CompanyResult[];
    total: number;
  }> => {
    const response = await api.post('/data-search/chat', {
      message,
      conversation_history: conversationHistory,
    });
    return response.data;
  },

  // Submit feedback on a result
  feedback: async (
    companyId: string,
    searchId: string,
    isRelevant: boolean
  ): Promise<void> => {
    await api.post('/data-search/feedback', {
      company_id: companyId,
      search_id: searchId,
      is_relevant: isRelevant,
    });
  },

  // Get search suggestions based on partial input
  suggestions: async (partialQuery: string): Promise<string[]> => {
    const response = await api.get('/data-search/suggestions', {
      params: { q: partialQuery },
    });
    return response.data.suggestions;
  },

  // Export search results
  exportResults: async (
    filters: SearchFilter[],
    format: 'csv' | 'xlsx' = 'csv'
  ): Promise<Blob> => {
    const response = await api.post(
      '/data-search/export',
      { filters, format },
      { responseType: 'blob' }
    );
    return response.data;
  },

  // Reverse engineer search filters from example companies
  reverseEngineer: async (
    companies: Partial<CompanyResult>[],
    userContext?: string,
    useAi: boolean = true
  ): Promise<ReverseEngineerResponse> => {
    const response = await api.post('/data-search/reverse-engineer', {
      companies,
      user_context: userContext,
      use_ai: useAi,
    });
    return response.data;
  },

  // Search for similar companies (reverse engineer + search in one call)
  searchLike: async (
    companies: Partial<CompanyResult>[],
    userContext?: string,
    useAi: boolean = true
  ): Promise<SearchLikeResponse> => {
    const response = await api.post('/data-search/search-like', {
      companies,
      user_context: userContext,
      use_ai: useAi,
    });
    return response.data;
  },

  // ============================================================================
  // VERIFICATION ENDPOINTS - Crona scrape + OpenAI verify pipeline
  // ============================================================================

  // Verify a single company against criteria
  verifyCompany: async (
    company: Partial<CompanyResult>,
    criteria: VerificationCriteria,
    useAi: boolean = true
  ): Promise<VerificationResult> => {
    const response = await api.post('/data-search/verify', {
      company,
      criteria,
      use_ai: useAi,
    });
    return response.data;
  },

  // Verify multiple companies in batch
  verifyBatch: async (
    companies: Partial<CompanyResult>[],
    criteria: VerificationCriteria,
    options?: {
      useAi?: boolean;
      maxConcurrent?: number;
      verifyLimit?: number;
    }
  ): Promise<BatchVerificationResult> => {
    const response = await api.post('/data-search/verify/batch', {
      companies,
      criteria,
      use_ai: options?.useAi ?? true,
      max_concurrent: options?.maxConcurrent ?? 5,
      verify_limit: options?.verifyLimit ?? 10,
    });
    return response.data;
  },

  // Verify search results and return enriched results
  verifySearchResults: async (
    results: CompanyResult[],
    criteria: VerificationCriteria,
    options?: {
      useAi?: boolean;
      verifyLimit?: number;
    }
  ): Promise<{
    results: CompanyResult[];
    verified_count: number;
    total: number;
    verification_summary: string;
  }> => {
    const response = await api.post('/data-search/verify/search-results', {
      results,
      criteria,
      use_ai: options?.useAi ?? true,
      verify_limit: options?.verifyLimit ?? 10,
    });
    return response.data;
  },

  // Chat search with automatic verification (premium experience)
  chatVerified: async (
    message: string,
    conversationHistory: { role: string; content: string }[] = []
  ): Promise<{
    response: string;
    filters: SearchFilter[];
    results: CompanyResult[];
    total: number;
  }> => {
    const response = await api.post('/data-search/chat-verified', {
      message,
      conversation_history: conversationHistory,
    });
    return response.data;
  },
};


// ============================================================================
// PROJECT SEARCH API — Yandex + GPT analysis pipeline
// ============================================================================

export const projectSearchApi = {
  // Run full search pipeline for a project
  runProjectSearch: async (
    projectId: number,
    maxQueries: number = 500,
    targetGoal?: number
  ): Promise<{ job_id: number; status: string }> => {
    const body: any = { max_queries: maxQueries };
    if (targetGoal) body.target_goal = targetGoal;
    const response = await api.post(`/search/projects/${projectId}/run`, body);
    return response.data;
  },

  // Get search job status with queries
  getSearchJobStatus: async (jobId: number): Promise<SearchJobDetail> => {
    const response = await api.get(`/search/jobs/${jobId}`);
    return response.data;
  },

  // Get analyzed results for a project
  getProjectResults: async (
    projectId: number,
    targetsOnly: boolean = false
  ): Promise<SearchResultItem[]> => {
    const response = await api.get(`/search/projects/${projectId}/results`, {
      params: { targets_only: targetsOnly },
    });
    return response.data;
  },

  // Get cost tracking for a project
  getProjectSpending: async (projectId: number): Promise<SpendingInfo> => {
    const response = await api.get(`/search/projects/${projectId}/spending`);
    return response.data;
  },

  // Cancel a search job
  cancelSearchJob: async (jobId: number): Promise<void> => {
    await api.post(`/search/jobs/${jobId}/cancel`);
  },

  // SSE stream for real-time progress
  streamSearchJob: (
    jobId: number,
    onEvent: (event: SearchProgressEvent) => void,
    onError?: (error: Event) => void
  ): EventSource => {
    const baseUrl = import.meta.env.VITE_API_URL || '';
    const url = `${baseUrl}/api/search/jobs/${jobId}/stream`;
    const eventSource = new EventSource(url);

    eventSource.addEventListener('progress', (e) => {
      try {
        const data = JSON.parse(e.data) as SearchProgressEvent;
        onEvent(data);
      } catch (err) {
        console.error('Failed to parse SSE event:', err);
      }
    });

    eventSource.addEventListener('completed', (e) => {
      try {
        const data = JSON.parse(e.data) as SearchProgressEvent;
        onEvent(data);
      } catch (err) {
        console.error('Failed to parse SSE event:', err);
      }
      eventSource.close();
    });

    eventSource.addEventListener('error', (e) => {
      try {
        const data = JSON.parse((e as MessageEvent).data) as SearchProgressEvent;
        onEvent(data);
      } catch {
        // SSE connection error
      }
      eventSource.close();
    });

    eventSource.addEventListener('cancelled', (e) => {
      try {
        const data = JSON.parse(e.data) as SearchProgressEvent;
        onEvent(data);
      } catch (err) {
        console.error('Failed to parse SSE event:', err);
      }
      eventSource.close();
    });

    if (onError) {
      eventSource.onerror = onError;
    }

    return eventSource;
  },

  // Export results to Google Sheet
  exportToGoogleSheet: async (
    projectId: number,
    options?: { targets_only?: boolean; exclude_contacted?: boolean }
  ): Promise<{ sheet_url: string }> => {
    const response = await api.post(
      `/search/projects/${projectId}/export-sheet`,
      options || {},
    );
    return response.data;
  },

  // List search jobs
  listSearchJobs: async (
    page: number = 1,
    pageSize: number = 20
  ): Promise<SearchJobDetail[]> => {
    const response = await api.get('/search/jobs', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  // Generate queries
  generateQueries: async (
    count: number = 50,
    targetSegments?: string,
    projectId?: number,
    existingQueries: string[] = []
  ): Promise<{ queries: string[]; count: number }> => {
    const response = await api.post('/search/generate-queries', {
      count,
      target_segments: targetSegments,
      project_id: projectId,
      existing_queries: existingQueries,
    });
    return response.data;
  },

  // Get extended job detail with config, results summary, spending
  getJobFull: async (jobId: number): Promise<SearchJobFullDetail> => {
    const response = await api.get(`/search/jobs/${jobId}/full`);
    return response.data;
  },

  // Download job results as CSV
  downloadJobCsv: async (jobId: number): Promise<Blob> => {
    const response = await api.get(`/search/jobs/${jobId}/results/download`, {
      responseType: 'blob',
    });
    return response.data;
  },

  // Batch domain-campaign lookup
  getDomainCampaigns: async (
    domains: string[]
  ): Promise<DomainCampaignsMap> => {
    const response = await api.post('/search/domain-campaigns', { domains });
    return response.data;
  },

  // Search history — paginated job list with summary stats
  getSearchHistory: async (
    page: number = 1,
    pageSize: number = 20
  ): Promise<{
    items: SearchHistoryItem[];
    total: number;
    page: number;
    page_size: number;
  }> => {
    const response = await api.get('/search/history', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },
};

// ============ Extended types for search history ============

export interface SearchJobFullDetail {
  id: number;
  company_id: number;
  status: string;
  search_engine: string;
  project_id?: number;
  project_name?: string;
  queries_total: number;
  queries_completed: number;
  domains_found: number;
  domains_new: number;
  domains_trash: number;
  domains_duplicate: number;
  started_at?: string;
  completed_at?: string;
  created_at?: string;
  error_message?: string;
  config?: Record<string, any>;
  results_total: number;
  targets_found: number;
  avg_confidence?: number;
  yandex_cost: number;
  openai_tokens_used: number;
  openai_cost_estimate: number;
  crona_credits_used: number;
  crona_cost: number;
  total_cost_estimate: number;
}

// ============ Domain-Campaign lookup types ============

export interface DomainCampaignContact {
  id: number;
  name: string | null;
  email: string | null;
  status: string;
  has_replied: boolean;
  match_type?: 'email_domain' | 'website_domain';
}

export interface DomainCampaignInfo {
  contacts_count: number;
  has_replies: boolean;
  first_contacted_at: string | null;
  match_type: 'email_domain' | 'website_domain';
  campaigns: Array<{
    name: string;
    source: string;
    status?: string;
  }>;
  contacts: DomainCampaignContact[];
}

export type DomainCampaignsMap = Record<string, DomainCampaignInfo>;

export interface SearchHistoryItem {
  id: number;
  company_id: number;
  status: string;
  search_engine: string;
  project_id?: number;
  project_name?: string;
  queries_total: number;
  queries_completed: number;
  domains_found: number;
  domains_new: number;
  domains_trash: number;
  domains_duplicate: number;
  results_total: number;
  targets_found: number;
  started_at?: string;
  completed_at?: string;
  created_at?: string;
  error_message?: string;
  openai_tokens_used: number;
  crona_credits_used: number;
}
