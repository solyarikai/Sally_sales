import { api } from './client';

// Types
export type ReplyCategory = 
  | 'interested' 
  | 'meeting_request' 
  | 'not_interested' 
  | 'out_of_office' 
  | 'wrong_person' 
  | 'unsubscribe' 
  | 'question' 
  | 'other';

export interface ReplyAutomation {
  id: number;
  name: string;
  company_id: number | null;
  environment_id: number | null;
  campaign_ids: string[];
  slack_webhook_url: string | null;
  slack_channel: string | null;
  google_sheet_id: string | null;
  google_sheet_name: string | null;
  auto_classify: boolean;
  auto_generate_reply: boolean;
  classification_prompt: string | null;
  reply_prompt: string | null;
  active: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ReplyAutomationCreate {
  name: string;
  company_id?: number;
  environment_id?: number;
  campaign_ids: string[];
  slack_webhook_url?: string;
  slack_channel?: string;
  google_sheet_id?: string;
  google_sheet_name?: string;
  classification_prompt?: string;
  reply_prompt?: string;
  create_google_sheet?: boolean;
  share_sheet_with_email?: string;
  auto_classify?: boolean;
  auto_generate_reply?: boolean;
  active?: boolean;
}

// Google Sheets types
export interface GoogleSheetsStatus {
  configured: boolean;
  service_account_email: string | null;
  message: string;
}

// Slack types
export interface SlackChannel {
  id: string;
  name: string;
  is_private: boolean;
  is_member: boolean;
  num_members: number;
  topic?: string;
  purpose?: string;
}

export interface SlackChannelsResponse {
  success: boolean;
  channels: SlackChannel[];
  total?: number;
  error?: string;
  action_required?: string;
}

export interface SlackStatus {
  configured: boolean;
  bot_token: boolean;
  valid?: boolean;
  message: string;
  missing_scopes: string[];
  has_channels_read?: boolean;
  has_chat_write?: boolean;
  bot_user_id?: string;
  team?: string;
  team_id?: string;
}

export interface SlackCreateChannelResponse {
  success: boolean;
  channel?: {
    id: string;
    name: string;
    is_private: boolean;
  };
  error?: string;
  action_required?: string;
}

export interface GoogleSheetCreateResponse {
  success: boolean;
  sheet_id: string;
  sheet_url: string;
  message: string;
}

export interface ReplyAutomationUpdate {
  google_sheet_id?: string;
  google_sheet_name?: string;
  classification_prompt?: string;
  reply_prompt?: string;
  name?: string;
  campaign_ids?: string[];
  slack_webhook_url?: string;
  slack_channel?: string;
  auto_classify?: boolean;
  auto_generate_reply?: boolean;
  active?: boolean;
}

export interface ProcessedReply {
  id: number;
  automation_id: number | null;
  campaign_id: string | null;
  campaign_name: string | null;
  lead_email: string;
  lead_first_name: string | null;
  lead_last_name: string | null;
  lead_company: string | null;
  email_subject: string | null;
  email_body: string | null;
  reply_text: string | null;
  received_at: string | null;
  category: ReplyCategory | null;
  category_confidence: string | null;
  classification_reasoning: string | null;
  draft_reply: string | null;
  draft_subject: string | null;
  inbox_link: string | null;
  processed_at: string;
  sent_to_slack: boolean;
  slack_sent_at: string | null;
  created_at: string;
}

export interface ProcessedReplyStats {
  total: number;
  by_category: Record<string, number>;
  by_status: Record<string, number>;
  today: number;
  this_week: number;
  sent_to_slack: number;
  pending: number;
  approved: number;
  dismissed: number;
}

export interface AutomationMonitoringStats {
  automation_id: number;
  automation_name: string;
  active: boolean;
  total_processed: number;
  total_errors: number;
  replies_today: number;
  replies_this_week: number;
  pending: number;
  approved: number;
  dismissed: number;
  by_category: Record<string, number>;
  last_run_at: string | null;
  last_error_at: string | null;
  last_error: string | null;
  created_at: string;
  health_status: 'healthy' | 'warning' | 'error' | 'paused';
}

export interface AutomationMonitoringResponse {
  automations: AutomationMonitoringStats[];
  total: number;
  total_active: number;
  total_paused: number;
  total_processed_all: number;
  total_errors_all: number;
}

export interface SmartleadCampaign {
  id: string;
  name: string;
  status?: string;
  created_at?: string;
}

// API Functions

// ============= Smartlead =============

export async function getSmartleadCampaigns(): Promise<SmartleadCampaign[]> {
  const response = await api.get('/smartlead/campaigns');
  return response.data.campaigns || [];
}

export async function getCampaignLeads(campaignId: string, offset = 0, limit = 100) {
  const response = await api.get(`/smartlead/campaigns/${campaignId}/leads`, {
    params: { offset, limit }
  });
  return response.data;
}

export async function getCampaignStatistics(campaignId: string) {
  const response = await api.get(`/smartlead/campaigns/${campaignId}/statistics`);
  return response.data;
}

// ============= Reply Automations =============

export async function getAutomations(activeOnly = true): Promise<ReplyAutomation[]> {
  const response = await api.get('/replies/automations', {
    params: { active_only: activeOnly }
  });
  return response.data.automations || [];
}

export async function getAutomation(id: number): Promise<ReplyAutomation> {
  const response = await api.get(`/replies/automations/${id}`);
  return response.data;
}

export async function createAutomation(data: ReplyAutomationCreate): Promise<ReplyAutomation> {
  const response = await api.post('/replies/automations', data);
  return response.data;
}

export async function updateAutomation(id: number, data: ReplyAutomationUpdate): Promise<ReplyAutomation> {
  const response = await api.patch(`/replies/automations/${id}`, data);
  return response.data;
}

export async function deleteAutomation(id: number): Promise<void> {
  await api.delete(`/replies/automations/${id}`);
}

export async function addCampaignToAutomation(automationId: number, campaignId: string): Promise<ReplyAutomation> {
  const response = await api.post(`/replies/automations/${automationId}/campaigns`, { campaign_id: campaignId });
  return response.data;
}

export async function testAutomationWebhook(id: number): Promise<{ success: boolean; message: string }> {
  const response = await api.post(`/replies/automations/${id}/test-webhook`);
  return response.data;
}

export async function pauseAutomation(id: number): Promise<{ success: boolean; message: string; active: boolean }> {
  const response = await api.post(`/replies/automations/${id}/pause`);
  return response.data;
}

export async function resumeAutomation(id: number): Promise<{ success: boolean; message: string; active: boolean }> {
  const response = await api.post(`/replies/automations/${id}/resume`);
  return response.data;
}

export async function getAutomationMonitoring(): Promise<AutomationMonitoringResponse> {
  const response = await api.get('/replies/automations/monitoring');
  return response.data;
}

export async function getSingleAutomationMonitoring(id: number): Promise<AutomationMonitoringStats> {
  const response = await api.get(`/replies/automations/${id}/monitoring`);
  return response.data;
}

// ============= Processed Replies =============

export async function getReplies(params: {
  automation_id?: number;
  campaign_id?: string;
  category?: ReplyCategory;
  page?: number;
  page_size?: number;
}): Promise<{ replies: ProcessedReply[]; total: number; page: number; page_size: number }> {
  const response = await api.get('/replies/', { params });
  return response.data;
}

export async function getReply(id: number): Promise<ProcessedReply> {
  const response = await api.get(`/replies/${id}`);
  return response.data;
}

export async function getReplyStats(params?: {
  automation_id?: number;
  campaign_id?: string;
}): Promise<ProcessedReplyStats> {
  const response = await api.get('/replies/stats', { params });
  return response.data;
}

export async function resendNotification(replyId: number): Promise<{ success: boolean; message: string }> {
  const response = await api.post(`/replies/${replyId}/resend-notification`);
  return response.data;
}

// ============= Testing =============

export interface SimulateReplyPayload {
  campaign_id?: string;
  campaign_name?: string;
  lead_email?: string;
  first_name?: string;
  last_name?: string;
  company_name?: string;
  email_subject?: string;
  email_body: string;
  classification_prompt?: string;
  reply_prompt?: string;
}

export interface SimulateReplyResponse {
  success: boolean;
  reply_id?: number;
  category?: ReplyCategory;
  confidence?: string;
  reasoning?: string;
  draft_subject?: string;
  draft_reply?: string;
  sent_to_slack?: boolean;
  error?: string;
  message?: string;
}

export async function simulateReply(payload: SimulateReplyPayload): Promise<SimulateReplyResponse> {
  const response = await api.post('/smartlead/simulate-reply', payload);
  return response.data;
}

// ============= Google Sheets =============

export async function getGoogleSheetsStatus(): Promise<GoogleSheetsStatus> {
  const response = await api.get('/replies/google-sheets/status');
  return response.data;
}

export async function createGoogleSheet(
  name: string, 
  shareWithEmail?: string,
  automationId?: number
): Promise<GoogleSheetCreateResponse> {
  const response = await api.post('/replies/google-sheets/create', null, {
    params: { 
      name, 
      share_with_email: shareWithEmail,
      automation_id: automationId 
    }
  });
  return response.data;
}

// ============= Slack Integration =============

export async function getSlackStatus(): Promise<SlackStatus> {
  const response = await api.get('/replies/slack/status');
  return response.data;
}

export async function getSlackChannels(includePrivate = false): Promise<SlackChannelsResponse> {
  const response = await api.get('/replies/slack/channels', {
    params: { include_private: includePrivate }
  });
  return response.data;
}

export async function createSlackChannel(name: string, isPrivate = false): Promise<SlackCreateChannelResponse> {
  const response = await api.post('/replies/slack/channels/create', null, {
    params: { name, is_private: isPrivate }
  });
  return response.data;
}

export async function testSlackChannel(channelId: string): Promise<{ success: boolean; message: string }> {
  const response = await api.post(`/replies/slack/test-channel/${channelId}`);
  return response.data;
}

// Export all functions as named object for consistency
export const repliesApi = {
  // Smartlead
  getSmartleadCampaigns,
  getCampaignLeads,
  getCampaignStatistics,
  // Automations
  getAutomations,
  getAutomation,
  createAutomation,
  updateAutomation,
  deleteAutomation,
  addCampaignToAutomation,
  testAutomationWebhook,
  pauseAutomation,
  resumeAutomation,
  getAutomationMonitoring,
  getSingleAutomationMonitoring,
  // Replies
  getReplies,
  getReply,
  getReplyStats,
  resendNotification,
  // Testing
  simulateReply,
  // Google Sheets
  getGoogleSheetsStatus,
  createGoogleSheet,
  // Slack
  getSlackStatus,
  getSlackChannels,
  createSlackChannel,
  testSlackChannel,
  // Test Flow APIs
  getTestEmailAccounts,
  createTestCampaign,
  getTestCampaigns,
  simulateTestReply,
  checkTestSetup,
  // Campaign control
  getCampaignStatus,
  launchCampaign,
  pauseCampaign,
};


// Test Flow APIs
export async function getTestEmailAccounts(): Promise<{accounts: Array<{id: number, email: string, name: string, remaining: number}>, total: number}> {
  const response = await api.get('/replies/test-flow/email-accounts');
  return response.data;
}

export async function createTestCampaign(userEmail: string, userName: string, emailAccountId?: number): Promise<{
  success: boolean;
  campaign_id?: string;
  campaign_name?: string;
  message: string;
  next_steps?: string[];
  error?: string;
}> {
  const params = new URLSearchParams({ user_email: userEmail, user_name: userName });
  if (emailAccountId) params.append('email_account_id', String(emailAccountId));
  const response = await api.post(`/replies/test-flow/create-real-campaign?${params}`);
  return response.data;
}

export async function getTestCampaigns(): Promise<{campaigns: Array<{id: string, name: string, status: string}>}> {
  const response = await api.get('/replies/test-flow/campaigns');
  return response.data;
}

export async function simulateTestReply(campaignId: string, message: string): Promise<{
  success: boolean;
  message: string;
  result?: { reply_id: number; category: string; slack_sent: boolean; sheet_row: number };
}> {
  const params = new URLSearchParams({ campaign_id: campaignId, message });
  const response = await api.post(`/replies/test-flow/simulate-reply?${params}`);
  return response.data;
}

export async function checkTestSetup(campaignId: string): Promise<{
  ready: boolean;
  message: string;
  automation?: { id: number; name: string; has_slack: boolean; has_sheet: boolean };
}> {
  const response = await api.get(`/replies/test-flow/check-setup/${campaignId}`);
  return response.data;
}

// Campaign control APIs
export async function getCampaignStatus(campaignId: string): Promise<{campaign_id: string, name: string, status: string}> {
  const response = await api.get(`/replies/campaign/${campaignId}/status`);
  return response.data;
}

export async function launchCampaign(campaignId: string): Promise<{success: boolean, message: string}> {
  const response = await api.post(`/replies/campaign/${campaignId}/launch`);
  return response.data;
}

export async function pauseCampaign(campaignId: string): Promise<{success: boolean, message: string}> {
  const response = await api.post(`/replies/campaign/${campaignId}/pause`);
  return response.data;
}
