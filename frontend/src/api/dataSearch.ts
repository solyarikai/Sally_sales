import { api } from './client';

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
