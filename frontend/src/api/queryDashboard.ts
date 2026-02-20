import { api } from './client';

// ── Types ────────────────────────────────────────────────────

export interface QueryRecord {
  query_id: number;
  query_text: string;
  segment: string | null;
  geo: string | null;
  country: string | null;
  language: string | null;
  source: string;
  job_id: number;
  status: string;
  domains_found: number;
  targets_found: number;
  effectiveness_score: number | null;
  estimated_cost_usd: number;
  is_saturated: boolean;
  created_at: string | null;
}

export interface QueryListResponse {
  total: number;
  page: number;
  page_size: number;
  data: QueryRecord[];
}

export interface SegmentSaturation {
  key: string;
  total: number;
  saturated: number;
  saturation_rate: number;
  total_domains: number;
  total_targets: number;
}

export interface QuerySummaryResponse {
  total_queries: number;
  done_queries: number;
  failed_queries: number;
  total_domains: number;
  total_targets: number;
  total_cost_usd: number;
  saturation_rate: number;
  avg_effectiveness: number | null;
  by_segment: SegmentSaturation[];
  by_geo: SegmentSaturation[];
  by_country: SegmentSaturation[];
  by_source: SegmentSaturation[];
}

export interface FilterOptionsResponse {
  segments: string[];
  geos: string[];
  countries: string[];
  languages: string[];
  sources: string[];
}

export interface GeoEntry {
  key: string;
  country_en: string;
  cities_en: string[];
}

export interface CountryGroup {
  country: string;
  geos: GeoEntry[];
}

export interface GeoHierarchyResponse {
  countries: CountryGroup[];
}

export interface QueryDashboardFilters {
  project_id: number;
  q?: string;
  segment?: string;
  geo?: string;
  country?: string;
  language?: string;
  source?: string;
  status?: string;
  domains_min?: number;
  domains_max?: number;
  targets_min?: number;
  targets_max?: number;
  date_from?: string;
  date_to?: string;
  is_saturated?: boolean;
  sort_by?: string;
  sort_order?: string;
  page?: number;
  page_size?: number;
}

// ── API methods ──────────────────────────────────────────────

export const queryDashboardApi = {
  async listQueries(filters: QueryDashboardFilters): Promise<QueryListResponse> {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params.append(key, String(value));
      }
    });
    const response = await api.get(`/dashboard/queries?${params.toString()}`);
    return response.data;
  },

  async getSummary(filters: Omit<QueryDashboardFilters, 'sort_by' | 'sort_order' | 'page' | 'page_size'>): Promise<QuerySummaryResponse> {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        params.append(key, String(value));
      }
    });
    const response = await api.get(`/dashboard/queries/summary?${params.toString()}`);
    return response.data;
  },

  async getFilterOptions(projectId: number): Promise<FilterOptionsResponse> {
    const response = await api.get(`/dashboard/queries/filter-options?project_id=${projectId}`);
    return response.data;
  },

  async getGeoHierarchy(): Promise<GeoHierarchyResponse> {
    const response = await api.get('/dashboard/queries/geo-hierarchy');
    return response.data;
  },
};
