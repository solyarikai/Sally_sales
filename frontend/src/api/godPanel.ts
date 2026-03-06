import { api } from './client';

export interface GodPanelCampaign {
  id: number;
  name: string;
  platform: string;
  channel: string;
  external_id?: string;
  project_id?: number;
  project_name?: string;
  status?: string;
  resolution_method?: string;
  resolution_detail?: string;
  first_seen_at?: string;
  acknowledged: boolean;
  replied_count: number;
  created_at?: string;
}

export interface ProjectRules {
  project_id: number;
  project_name: string;
  rules: string[];
}

export interface GodPanelStats {
  total_campaigns: number;
  smartlead_campaigns: number;
  getsales_campaigns: number;
  unresolved_count: number;
  unacknowledged_count: number;
  assignment_rate: number;
  reply_volume_7d: number;
  reply_volume_30d: number;
  newest_campaign?: string;
  newest_campaign_at?: string;
}

export interface ProjectMetric {
  project_id: number;
  project_name: string;
  contacts_uploaded: number;
  warm_replies: number;
}

export interface ProjectMetricsResponse {
  projects: ProjectMetric[];
  period: string;
}

export interface CleanupLogEntry {
  id: number;
  project_id?: number;
  project_name?: string;
  replies_checked: number;
  replies_resolved: number;
  resolved_replies?: { reply_id: number; lead_email: string; campaign_name?: string }[];
  errors: number;
  created_at?: string;
}

export interface CampaignAuditLogEntry {
  id: number;
  action: string;
  campaign_name?: string;
  source: string;
  learning_log_id?: number;
  details?: string;
  created_at?: string;
}

export const godPanelApi = {
  async listCampaigns(params?: {
    platform?: string;
    unresolved?: boolean;
    unacknowledged?: boolean;
    project_id?: number;
    since?: string;
  }): Promise<GodPanelCampaign[]> {
    const { data } = await api.get('/god-panel/campaigns/', { params });
    return data;
  },

  async acknowledgeCampaign(id: number): Promise<void> {
    await api.post(`/god-panel/campaigns/${id}/acknowledge`);
  },

  async assignCampaign(id: number, projectId: number): Promise<{ project_name: string }> {
    const { data } = await api.post(`/god-panel/campaigns/${id}/assign`, { project_id: projectId });
    return data;
  },

  async getProjectRules(projectId: number): Promise<ProjectRules> {
    const { data } = await api.get(`/god-panel/projects/${projectId}/rules`);
    return data;
  },

  async getStats(): Promise<GodPanelStats> {
    const { data } = await api.get('/god-panel/stats');
    return data;
  },

  async getUnresolvedCount(): Promise<{ count: number; newCount: number }> {
    const { data } = await api.get('/god-panel/unresolved-count');
    return { count: data.count, newCount: data.new_count ?? 0 };
  },

  async submitRuleFeedback(projectId: number, feedbackText: string): Promise<{ learning_log_id: number }> {
    const { data } = await api.post(`/god-panel/projects/${projectId}/rule-feedback`, { feedback_text: feedbackText });
    return data;
  },

  async getProjectMetrics(period: string = '30d'): Promise<ProjectMetricsResponse> {
    const { data } = await api.get('/god-panel/project-metrics', { params: { period } });
    return data;
  },

  async getCleanupLogs(projectId: number, page = 1, pageSize = 20): Promise<CleanupLogEntry[]> {
    const { data } = await api.get(`/god-panel/projects/${projectId}/cleanup-logs`, {
      params: { page, page_size: pageSize },
    });
    return data;
  },

  async getCampaignLogs(projectId: number, page = 1, pageSize = 50): Promise<CampaignAuditLogEntry[]> {
    const { data } = await api.get(`/god-panel/projects/${projectId}/campaign-logs`, {
      params: { page, page_size: pageSize },
    });
    return data;
  },
};
