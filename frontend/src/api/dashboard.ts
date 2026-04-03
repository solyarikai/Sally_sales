import { api } from './client';

export interface AutomationStats {
  total: number;
  active: number;
  paused: number;
}

export interface ReplyStats {
  total: number;
  today: number;
  this_week: number;
  pending: number;
  approved: number;
  dismissed: number;
  by_category: Record<string, number>;
}

export interface ContactStats {
  total: number;
  leads: number;
  contacted: number;
  replied: number;
  qualified: number;
}

export interface ActivityItem {
  id: string;
  type: string;
  title: string;
  description: string;
  timestamp: string;
  icon: string;
  link?: string;
}

export interface DashboardStats {
  automations: AutomationStats;
  replies: ReplyStats;
  contacts: ContactStats;
  companies_count: number;
  projects_count: number;
}

export interface DashboardResponse {
  stats: DashboardStats;
  recent_activity: ActivityItem[];
}

export interface QuickStats {
  automations: number;
  replies: number;
  contacts: number;
  pending_replies: number;
}

export const dashboardApi = {
  async getStats(): Promise<DashboardResponse> {
    const response = await api.get('/dashboard/stats');
    return response.data;
  },

  async getQuickStats(): Promise<QuickStats> {
    const response = await api.get('/dashboard/quick-stats');
    return response.data;
  },
};
