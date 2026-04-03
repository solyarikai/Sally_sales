import api from './client';
import type { OpenAISettings } from '../types';

export const settingsApi = {
  getOpenAI: async (): Promise<OpenAISettings> => {
    const response = await api.get('/settings/openai');
    return response.data;
  },

  updateOpenAI: async (apiKey?: string, defaultModel?: string): Promise<OpenAISettings> => {
    const response = await api.put('/settings/openai', {
      api_key: apiKey,
      default_model: defaultModel,
    });
    return response.data;
  },

  testOpenAI: async (): Promise<{ status: string; message: string }> => {
    const response = await api.post('/settings/openai/test');
    return response.data;
  },
};
