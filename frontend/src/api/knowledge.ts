import { api } from './client';

export interface KnowledgeEntry {
  id: number;
  category: string;
  key: string;
  title: string | null;
  value: any;
  source: string;
  updated_at: string | null;
}

export interface KnowledgeGrouped {
  [category: string]: KnowledgeEntry[];
}

export const knowledgeApi = {
  getAll: async (projectId: number): Promise<{ project_id: number; knowledge: KnowledgeGrouped }> => {
    const response = await api.get(`/projects/${projectId}/knowledge`);
    return response.data;
  },

  getByCategory: async (
    projectId: number,
    category: string,
  ): Promise<{ project_id: number; category: string; entries: KnowledgeEntry[] }> => {
    const response = await api.get(`/projects/${projectId}/knowledge/${category}`);
    return response.data;
  },

  upsert: async (
    projectId: number,
    category: string,
    key: string,
    value: any,
    title?: string,
    source?: string,
  ): Promise<KnowledgeEntry> => {
    const response = await api.put(`/projects/${projectId}/knowledge/${category}/${key}`, {
      value,
      title,
      source: source || 'manual',
    });
    return response.data;
  },

  delete: async (projectId: number, category: string, key: string): Promise<void> => {
    await api.delete(`/projects/${projectId}/knowledge/${category}/${key}`);
  },

  sync: async (projectId: number): Promise<{ project_id: number; entries_synced: number }> => {
    const response = await api.post(`/projects/${projectId}/knowledge/sync`);
    return response.data;
  },
};
