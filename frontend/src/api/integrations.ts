import api from './client';

export interface IntegrationStatus {
  name: string;
  connected: boolean;
  has_api_key: boolean;
}

export interface AllIntegrationsResponse {
  integrations: IntegrationStatus[];
}

export interface InstantlyDetails {
  connected: boolean;
  campaigns: Array<{
    id: string;
    name: string;
    status?: string;
  }>;
}

export interface FindymailDetails {
  connected: boolean;
  credits: {
    finder_credits?: number;
    verifier_credits?: number;
    [key: string]: any;
  } | null;
}

export interface SmartleadDetails {
  connected: boolean;
  campaigns: Array<{
    id: string;
    name: string;
    status?: string;
    [key: string]: any;
  }>;
}

export interface MillionVerifierDetails {
  connected: boolean;
  credits: {
    credits?: number;
    [key: string]: any;
  } | null;
}

export interface FirefliesDetails {
  connected: boolean;
  user: {
    name?: string;
    email?: string;
  } | null;
}

export interface SendLeadsRequest {
  campaign_id: string;
  dataset_id: number;
  row_ids?: number[];
  email_column: string;
  first_name_column?: string;
  last_name_column?: string;
  company_column?: string;
  custom_variables?: Record<string, string>;
}

export interface SendLeadsResponse {
  success: boolean;
  leads_sent: number;
  errors: string[];
}

export const integrationsApi = {
  // Get all integrations status
  getAll: async (): Promise<AllIntegrationsResponse> => {
    const response = await api.get('/integrations');
    return response.data;
  },

  // Instantly
  getInstantly: async (): Promise<InstantlyDetails> => {
    const response = await api.get('/integrations/instantly');
    return response.data;
  },

  connectInstantly: async (apiKey: string): Promise<InstantlyDetails> => {
    const response = await api.post('/integrations/instantly/connect', {
      api_key: apiKey,
    });
    return response.data;
  },

  disconnectInstantly: async (): Promise<void> => {
    await api.delete('/integrations/instantly/disconnect');
  },

  getInstantlyCampaigns: async (): Promise<InstantlyDetails['campaigns']> => {
    const response = await api.get('/integrations/instantly/campaigns');
    return response.data.campaigns;
  },

  sendLeadsToInstantly: async (data: SendLeadsRequest): Promise<SendLeadsResponse> => {
    const response = await api.post('/integrations/instantly/send-leads', data);
    return response.data;
  },

  // Findymail
  getFindymail: async (): Promise<FindymailDetails> => {
    const response = await api.get('/integrations/findymail');
    return response.data;
  },

  connectFindymail: async (apiKey: string): Promise<FindymailDetails> => {
    const response = await api.post('/integrations/findymail/connect', {
      api_key: apiKey,
    });
    return response.data;
  },

  disconnectFindymail: async (): Promise<void> => {
    await api.delete('/integrations/findymail/disconnect');
  },

  findEmail: async (name: string, domain: string): Promise<any> => {
    const response = await api.post('/integrations/findymail/find-email', null, {
      params: { name, domain },
    });
    return response.data;
  },

  verifyEmail: async (email: string): Promise<any> => {
    const response = await api.post('/integrations/findymail/verify-email', null, {
      params: { email },
    });
    return response.data;
  },

  // Findymail Enrichment
  findymailEnrich: async (data: {
    dataset_id: number;
    row_ids?: number[];
    enrichment_type: 'find_email' | 'find_by_linkedin' | 'verify_email';
    output_column: string;
    name_column?: string;
    domain_column?: string;
    email_column?: string; // Also used for linkedin_url in find_by_linkedin
  }): Promise<{
    success: boolean;
    processed: number;
    found: number;
    errors: string[];
    total_cost: number;
  }> => {
    const response = await api.post('/integrations/findymail/enrich', data);
    return response.data;
  },

  // Smartlead
  getSmartlead: async (): Promise<SmartleadDetails> => {
    const response = await api.get('/integrations/smartlead');
    return response.data;
  },

  connectSmartlead: async (apiKey: string): Promise<SmartleadDetails> => {
    const response = await api.post('/integrations/smartlead/connect', {
      api_key: apiKey,
    });
    return response.data;
  },

  disconnectSmartlead: async (): Promise<void> => {
    await api.delete('/integrations/smartlead/disconnect');
  },

  getSmartleadCampaigns: async (): Promise<SmartleadDetails['campaigns']> => {
    const response = await api.get('/integrations/smartlead/campaigns');
    return response.data.campaigns;
  },

  sendLeadsToSmartlead: async (data: SendLeadsRequest): Promise<SendLeadsResponse> => {
    const response = await api.post('/integrations/smartlead/send-leads', data);
    return response.data;
  },

  // MillionVerifier
  getMillionverifier: async (): Promise<MillionVerifierDetails> => {
    const response = await api.get('/integrations/millionverifier');
    return response.data;
  },

  connectMillionverifier: async (apiKey: string): Promise<MillionVerifierDetails> => {
    const response = await api.post('/integrations/millionverifier/connect', {
      api_key: apiKey,
    });
    return response.data;
  },

  disconnectMillionverifier: async (): Promise<void> => {
    await api.delete('/integrations/millionverifier/disconnect');
  },

  millionverifierVerify: async (data: {
    dataset_id: number;
    row_ids?: number[];
    email_column: string;
    output_column: string;
    timeout?: number;
  }): Promise<{
    success: boolean;
    rows_to_verify: number;
    message: string;
  }> => {
    const response = await api.post('/integrations/millionverifier/verify', data);
    return response.data;
  },

  // Fireflies
  getFireflies: async (): Promise<FirefliesDetails> => {
    const response = await api.get('/integrations/fireflies');
    return response.data;
  },

  connectFireflies: async (apiKey: string): Promise<FirefliesDetails> => {
    const response = await api.post('/integrations/fireflies/connect', {
      api_key: apiKey,
    });
    return response.data;
  },

  disconnectFireflies: async (): Promise<void> => {
    await api.delete('/integrations/fireflies/disconnect');
  },

  // Legacy compatibility
  updateInstantly: async (apiKey: string): Promise<{ instantly_connected: boolean; instantly_campaigns: any[] }> => {
    const result = await integrationsApi.connectInstantly(apiKey);
    return {
      instantly_connected: result.connected,
      instantly_campaigns: result.campaigns,
    };
  },

  testInstantly: async (): Promise<void> => {
    await api.get('/integrations/instantly');
  },
};
