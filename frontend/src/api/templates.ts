import api from './client';
import type { PromptTemplate } from '../types';

export interface CreateTemplateParams {
  name: string;
  description?: string;
  category?: string;
  tags?: string[];
  prompt_template: string;
  output_column: string;
  system_prompt?: string;
}

export const templatesApi = {
  list: async (tag?: string): Promise<PromptTemplate[]> => {
    const response = await api.get('/templates', {
      params: tag ? { tag } : {},
    });
    return response.data;
  },

  get: async (id: number): Promise<PromptTemplate> => {
    const response = await api.get(`/templates/${id}`);
    return response.data;
  },

  create: async (params: CreateTemplateParams): Promise<PromptTemplate> => {
    const response = await api.post('/templates', params);
    return response.data;
  },

  update: async (id: number, params: Partial<CreateTemplateParams>): Promise<PromptTemplate> => {
    const response = await api.put(`/templates/${id}`, params);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/templates/${id}`);
  },
};
