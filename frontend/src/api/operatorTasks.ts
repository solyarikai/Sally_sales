import { api } from './client';

export interface TaskContact {
  id: number;
  email: string;
  first_name?: string;
  last_name?: string;
  company_name?: string;
  job_title?: string;
  linkedin_url?: string;
  status: string;
  last_reply_at?: string;
  platform_state?: Record<string, any>;
  project_id?: number;
  category?: string;
  days_since?: number;
  last_message?: string;
  campaign_name?: string;
}

export interface TabData {
  tab: string;
  count: number;
  contacts: TaskContact[];
}

export interface OperatorTasksResponse {
  replies: TabData;
  align_meetings: TabData;
  align_qualified: TabData;
}

export interface StatusTransitionResponse {
  success: boolean;
  contact_id: number;
  old_status: string;
  new_status: string;
  message: string;
}

export const operatorTasksApi = {
  getTasks: async (projectId?: number): Promise<OperatorTasksResponse> => {
    const params = projectId ? { project_id: projectId } : {};
    const { data } = await api.get('/operator-tasks', { params });
    return data;
  },

  transitionStatus: async (
    contactId: number,
    newStatus: string,
    force = false,
  ): Promise<StatusTransitionResponse> => {
    const { data } = await api.patch(`/operator-tasks/${contactId}/status`, {
      new_status: newStatus,
      force,
    });
    return data;
  },
};
