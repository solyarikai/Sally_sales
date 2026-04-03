/**
 * Client Dashboard API — aggregated client report data.
 */
import { api } from './client';

export interface LeadEntry {
  id: number;
  date: string | null;
  name: string;
  title: string | null;
  company: string | null;
  contact: string;
  website: string | null;
  channel: string | null;
  segment: string | null;
  answer_preview: string | null;
  status: 'positive' | 'neutral' | 'negative' | 'meeting_booked' | 'meeting_done';
  meeting_date: string | null;
  comment: string | null;
}

export interface MeetingEntry {
  id: number;
  contact_name: string;
  contact_title: string | null;
  contact_company: string | null;
  scheduled_at: string;
  status: string;
  outcome: string | null;
  channel: string | null;
  segment: string | null;
  client_notes: string | null;
}

export interface ChannelStats {
  channel: string;
  segment?: string | null;
  plan: number;
  sent: number;
  accepted: number;
  accept_rate: number;
  replies: number;
  reply_rate: number;
  positive: number;
  positive_rate: number;
  meetings: number;
  meeting_rate: number;
}

export interface KPIData {
  total_plan: number;
  total_contacted: number;
  total_replies: number;
  positive_replies: number;
  meetings_scheduled: number;
  meetings_completed: number;
  reply_rate: number;
  positive_rate: number;
  meeting_rate: number;
}

export interface MeetingSummary {
  total: number;
  scheduled: number;
  completed: number;
  no_show: number;
  cancelled: number;
  qualified: number;
  follow_up: number;
  negotiation: number;
  closed_won: number;
  closed_lost: number;
}

export interface ClientDashboardData {
  project_name: string;
  period: {
    from: string;
    to: string;
    label: string;
  };
  kpi: KPIData;
  by_channel: ChannelStats[];
  by_segment: ChannelStats[];
  leads: LeadEntry[];
  meetings: MeetingEntry[];
  meetings_summary: MeetingSummary;
}

export interface ClientDashboardParams {
  period?: '7d' | '30d' | '90d' | 'all' | 'custom';
  date_from?: string;
  date_to?: string;
}

export const clientDashboardApi = {
  /**
   * Get aggregated client dashboard data for a project.
   */
  async getDashboard(projectId: number, params?: ClientDashboardParams): Promise<ClientDashboardData> {
    const { data } = await api.get<ClientDashboardData>(
      `/projects/${projectId}/client-dashboard`,
      { params }
    );
    return data;
  },
};

export default clientDashboardApi;
