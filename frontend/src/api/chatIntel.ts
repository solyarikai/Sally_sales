import { api } from './client';

export interface ChatCluster {
  id: string;
  name: string;
  description: string;
  icon: string;
}

export interface ChatMessage {
  id: number;
  message_id: number;
  sender_name: string;
  sender_username: string | null;
  text: string;
  sent_at: string;
  message_type: string;
  cluster: string | null;
}

export interface ChatInsight {
  id: number;
  topic: string;
  summary: string;
  key_points: string[] | null;
  action_items: string[] | null;
  created_at: string;
}

export interface ChatStats {
  total: number;
  chat_title: string;
  by_sender: { name: string; count: number }[];
  by_month: { month: string; count: number }[];
  date_range: { first: string; last: string } | null;
}

export const chatIntelApi = {
  getMessages: (projectId: number, params?: { limit?: number; offset?: number; cluster?: string; search?: string }) =>
    api.get(`/chat-intel/projects/${projectId}/messages`, { params }).then((r: any) => r.data),

  getStats: (projectId: number) =>
    api.get(`/chat-intel/projects/${projectId}/stats`).then((r: any) => r.data as ChatStats),

  getInsights: (projectId: number) =>
    api.get(`/chat-intel/projects/${projectId}/insights`).then((r: any) => r.data),

  analyze: (projectId: number) =>
    api.post(`/chat-intel/projects/${projectId}/analyze`).then((r: any) => r.data),
};
