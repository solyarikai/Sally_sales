import { api } from './client';

export interface ReplyAnalysisItem {
  id: number;
  processed_reply_id: number;
  project_id: number;
  offer_responded_to: string | null;
  intent: string | null;
  warmth_score: number | null;
  campaign_segment: string | null;
  sequence_type: string | null;
  language: string | null;
  reasoning: string | null;
  interests: string | null;
  tags: string[] | null;
  geo_tags: string[] | null;
  lead_email: string | null;
  lead_name: string | null;
  lead_company: string | null;
  campaign_name: string | null;
  reply_text: string | null;
  category: string | null;
  received_at: string | null;
  approval_status: string | null;
  intent_group: string | null;
  lead_domain: string | null;
  contact_id: number | null;
}

export interface IntelligenceSummary {
  total: number;
  by_group: Record<string, number>;
  by_offer: Record<string, number>;
  by_segment: Record<string, number>;
  by_intent: Record<string, number>;
  by_tag?: Record<string, number>;
  by_geo?: Record<string, number>;
}

export interface TagCount {
  tag: string;
  count: number;
}

export interface CampaignDebugItem {
  campaign_name: string;
  source: string;
  channel: string;
  reply_count: number;
}

export interface CampaignDebugResponse {
  campaigns: CampaignDebugItem[];
  total_replies: number;
  campaign_count: number;
}

export const intelligenceApi = {
  async list(params: {
    project_id: number;
    intent_group?: string;
    intent?: string;
    offer?: string;
    segment?: string;
    tags?: string;
    geo?: string;
    interests_search?: string;
    warmth_min?: number;
    warmth_max?: number;
    language?: string;
    search?: string;
    date_from?: string;
    date_to?: string;
    sort_by?: string;
    page?: number;
    page_size?: number;
  }): Promise<ReplyAnalysisItem[]> {
    const { data } = await api.get('/intelligence/', { params });
    return data;
  },

  async summary(project_id: number, date_from?: string, date_to?: string): Promise<IntelligenceSummary> {
    const params: Record<string, any> = { project_id };
    if (date_from) params.date_from = date_from;
    if (date_to) params.date_to = date_to;
    const { data } = await api.get('/intelligence/summary/', { params });
    return data;
  },

  async analyze(project_id: number, rebuild?: boolean, use_ai?: boolean): Promise<{ classified: number; ai_classified?: number; project_id: number }> {
    const params: Record<string, any> = { project_id };
    if (rebuild) params.rebuild = true;
    if (use_ai !== undefined) params.use_ai = use_ai;
    const { data } = await api.post('/intelligence/analyze/', null, { params });
    return data;
  },

  async tags(project_id: number): Promise<TagCount[]> {
    const { data } = await api.get('/intelligence/tags/', { params: { project_id } });
    return data;
  },

  async count(project_id: number): Promise<{ count: number }> {
    const { data } = await api.get('/intelligence/count/', { params: { project_id } });
    return data;
  },

  async campaigns(project_id: number, date_from?: string, date_to?: string): Promise<CampaignDebugResponse> {
    const params: Record<string, any> = { project_id };
    if (date_from) params.date_from = date_from;
    if (date_to) params.date_to = date_to;
    const { data } = await api.get('/intelligence/campaigns/', { params });
    return data;
  },
};
