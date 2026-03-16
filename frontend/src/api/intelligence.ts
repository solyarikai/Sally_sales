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
  lead_email: string | null;
  lead_name: string | null;
  lead_company: string | null;
  campaign_name: string | null;
  reply_text: string | null;
  category: string | null;
  received_at: string | null;
  approval_status: string | null;
  intent_group: string | null;
}

export interface IntelligenceSummary {
  total: number;
  by_group: Record<string, number>;
  by_offer: Record<string, number>;
  by_segment: Record<string, number>;
  by_intent: Record<string, number>;
}

export const intelligenceApi = {
  async list(params: {
    project_id: number;
    intent_group?: string;
    offer?: string;
    segment?: string;
    warmth_min?: number;
    warmth_max?: number;
    language?: string;
    search?: string;
    sort_by?: string;
    page?: number;
    page_size?: number;
  }): Promise<ReplyAnalysisItem[]> {
    const { data } = await api.get('/intelligence/', { params });
    return data;
  },

  async summary(project_id: number): Promise<IntelligenceSummary> {
    const { data } = await api.get('/intelligence/summary/', { params: { project_id } });
    return data;
  },

  async analyze(project_id: number): Promise<{ classified: number; project_id: number }> {
    const { data } = await api.post('/intelligence/analyze/', null, { params: { project_id } });
    return data;
  },

  async count(project_id: number): Promise<{ count: number }> {
    const { data } = await api.get('/intelligence/count/', { params: { project_id } });
    return data;
  },
};
