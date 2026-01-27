import api from './client';
import type { EnrichmentJob, EnrichmentPreviewResponse } from '../types';

export interface CreateEnrichmentJobParams {
  dataset_id: number;
  prompt_template_id?: number;
  custom_prompt?: string;
  output_column: string;
  model: string;
  selected_row_ids?: number[];
}

export interface PreviewEnrichmentParams {
  dataset_id: number;
  prompt_template_id?: number;
  custom_prompt?: string;
  output_column: string;
  model: string;
  row_ids: number[];
}

export interface ScrapeWebsitesParams {
  dataset_id: number;
  row_ids?: number[];
  url_column: string;
  output_column: string;
  timeout?: number;
}

export interface ScrapeWebsitesResponse {
  success: boolean;
  processed: number;
  succeeded: number;
  failed: number;
  errors: string[];
}

export interface EnhancePromptParams {
  rough_prompt: string;
  columns: string[];
  output_description?: string;
  language?: string;
}

export interface EnhancePromptResponse {
  enhanced_prompt: string;
  suggested_output_column: string;
}

export const enrichmentApi = {
  createJob: async (params: CreateEnrichmentJobParams): Promise<EnrichmentJob> => {
    const response = await api.post('/enrichment/jobs', params);
    return response.data;
  },

  getJob: async (jobId: number): Promise<EnrichmentJob> => {
    const response = await api.get(`/enrichment/jobs/${jobId}`);
    return response.data;
  },

  listJobs: async (datasetId?: number): Promise<EnrichmentJob[]> => {
    const response = await api.get('/enrichment/jobs', {
      params: datasetId ? { dataset_id: datasetId } : {},
    });
    return response.data;
  },

  preview: async (params: PreviewEnrichmentParams): Promise<EnrichmentPreviewResponse> => {
    const response = await api.post('/enrichment/preview', params);
    return response.data;
  },

  stopJob: async (jobId: number): Promise<void> => {
    await api.post(`/enrichment/jobs/${jobId}/stop`);
  },

  scrapeWebsites: async (params: ScrapeWebsitesParams): Promise<ScrapeWebsitesResponse> => {
    const response = await api.post('/enrichment/scrape', params);
    return response.data;
  },

  enhancePrompt: async (params: EnhancePromptParams): Promise<EnhancePromptResponse> => {
    const response = await api.post('/enrichment/enhance-prompt', params);
    return response.data;
  },
};
