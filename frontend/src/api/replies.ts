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
  source: string | null;
  channel: string | null;
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
  draft_generated_at: string | null;
  detected_language: string | null;
  translated_body: string | null;
  translated_draft: string | null;
  inbox_link: string | null;
  sender_name: string | null;
  processed_at: string;
  sent_to_slack: boolean;
  slack_sent_at: string | null;
  approval_status: string | null;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  // Follow-up tracking
  parent_reply_id: number | null;
  follow_up_number: number | null;
  // Qualified flag — operator-controlled marker for truly warm leads
  is_qualified?: boolean;
  // Contact dedup: how many campaigns this contact has (only set with group_by_contact)
  contact_campaign_count?: number;
}

export interface ContactCampaignEntry {
  reply_id: number;
  campaign_id: string | null;
  campaign_name: string | null;
  category: string | null;
  classification_reasoning: string | null;
  received_at: string | null;
  email_subject: string | null;
  email_body: string | null;
  reply_text: string | null;
  draft_reply: string | null;
  draft_subject: string | null;
  approval_status: string | null;
  inbox_link: string | null;
  channel: string | null;
}

export interface ContactCampaignsResponse {
  lead_email: string;
  campaigns: ContactCampaignEntry[];
  total: number;
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
  campaign_names?: string;
  project_id?: number;
  category?: ReplyCategory;
  approval_status?: string;
  needs_reply?: boolean;
  channel?: string;
  source?: string;
  is_qualified?: boolean;
  lead_email?: string;
  group_by_contact?: boolean;
  needs_followup?: boolean;
  received_since?: string;
  page?: number;
  page_size?: number;
}): Promise<{ replies: ProcessedReply[]; total: number; meeting_count: number; category_counts: Record<string, number>; page: number; page_size: number }> {
  const response = await api.get('/replies/', { params });
  return response.data;
}

export async function getContactCampaigns(
  leadEmail: string,
  projectId?: number,
): Promise<ContactCampaignsResponse> {
  const response = await api.get(`/replies/contact-campaigns/${encodeURIComponent(leadEmail)}`, {
    params: projectId ? { project_id: projectId } : {},
  });
  return response.data;
}

export interface ConversationMessage {
  direction: string | null;
  channel: string;
  subject: string | null;
  body: string | null;
  activity_at: string | null;
  source: string;
  activity_type: string;
  extra_data: Record<string, unknown> | null;
}

export interface ContactInfo {
  linkedin_url: string | null;
  phone: string | null;
  job_title: string | null;
  company_name: string | null;
  domain: string | null;
  location: string | null;
  segment: string | null;
  source: string | null;
  campaigns: Array<Record<string, unknown>> | null;
}

export async function getConversation(replyId: number): Promise<{ messages: ConversationMessage[]; contact_id?: number; approval_status?: string; contact_info?: ContactInfo | null }> {
  const response = await api.get(`/replies/${replyId}/conversation`);
  return response.data;
}

// Full cross-campaign history
export interface FullHistoryCampaign {
  campaign_name: string;
  channel: string;
  message_count: number;
  latest_at: string;
  earliest_at: string;
}

export interface FullHistoryActivity {
  direction: 'inbound' | 'outbound';
  content: string;
  timestamp: string;
  channel: 'email' | 'linkedin';
  campaign: string;
}

export interface FullHistoryResponse {
  contact_id: number | null;
  contact_info: ContactInfo | null;
  campaigns: FullHistoryCampaign[];
  activities: FullHistoryActivity[];
  approval_status: string | null;
  inbox_links: Record<string, string>;
}

export async function getFullHistory(replyId: number): Promise<FullHistoryResponse> {
  const response = await api.get(`/replies/${replyId}/full-history`);
  return response.data;
}

export async function getCampaignThread(replyId: number, campaignName: string): Promise<{ activities: FullHistoryActivity[] }> {
  const response = await api.get(`/replies/${replyId}/campaign-thread`, { params: { campaign_name: campaignName } });
  return response.data;
}

export async function getReplyCounts(params: {
  project_id?: number;
  campaign_names?: string;
  received_since?: string;
  include_all?: boolean;
  needs_followup?: boolean;
}): Promise<{ total: number; category_counts: Record<string, number>; qualified_count?: number }> {
  const response = await api.get('/replies/counts', { params });
  return response.data;
}

export async function getContactInfoBatch(emails: string[]): Promise<Record<string, ContactInfo>> {
  const response = await api.post('/replies/contact-info-batch', emails);
  return response.data.contacts || {};
}

export async function getReply(id: number): Promise<ProcessedReply> {
  const response = await api.get(`/replies/${id}`);
  return response.data;
}

export async function getReplyStats(params?: {
  automation_id?: number;
  campaign_id?: string;
  campaign_names?: string;
}): Promise<ProcessedReplyStats> {
  const response = await api.get('/replies/stats', { params });
  return response.data;
}

export async function resendNotification(replyId: number): Promise<{ success: boolean; message: string }> {
  const response = await api.post(`/replies/${replyId}/resend-notification`);
  return response.data;
}

// ============= Campaign Analytics =============

export interface CampaignAnalyticsSummary {
  campaign_id: string;
  unique_replied: number;
  unique_replied_with_ooo: number;
  unique_positive: number;
  by_category: Record<string, number>;
}

export async function getCampaignAnalyticsSummary(campaignId: string): Promise<CampaignAnalyticsSummary> {
  const response = await api.get(`/replies/campaign/${campaignId}/analytics-summary`);
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

// ============= Approval / Moderation =============

export async function approveAndSendReply(
  replyId: number,
  editedDraft?: { draft_reply?: string; draft_subject?: string }
): Promise<{
  status: string;
  dry_run: boolean;
  reply_id: number;
  message?: string;
  lead_email?: string;
  sent_to?: string;
  test_mode?: boolean;
  campaign_id?: string;
  contact_id?: number;
  channel?: string;
  getsales_sent?: boolean;
  send_error?: string | null;
}> {
  // On localhost, always send in test_mode so emails go to pn@getsally.io instead of real leads
  const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  const params = isLocal ? { test_mode: true } : {};
  const body = editedDraft && (editedDraft.draft_reply || editedDraft.draft_subject) ? editedDraft : null;
  const response = await api.post(`/replies/${replyId}/approve-and-send`, body, { params });
  return response.data;
}

export async function regenerateDraft(replyId: number, model?: string, calendlyContext?: string): Promise<{
  reply_id: number;
  draft_reply: string;
  draft_subject: string;
  draft_generated_at: string;
  translated_draft: string | null;
  category: string;
  classification_reasoning: string;
}> {
  const params: Record<string, string> = {};
  if (model) params.model = model;
  if (calendlyContext) params.calendly_context = calendlyContext;
  const response = await api.post(`/replies/${replyId}/regenerate-draft`, null, { params });
  return response.data;
}

// Calendly
export interface CalendlyMember {
  id: string;
  display_name: string;
  is_default: boolean;
}

export async function getCalendlyConfig(projectId: number): Promise<{
  members: CalendlyMember[];
  has_calendly: boolean;
}> {
  const response = await api.get('/replies/calendly/config', { params: { project_id: projectId } });
  return response.data;
}

export async function getCalendlySlots(projectId: number, memberId?: string): Promise<{
  member_id: string;
  display_name: string;
  slots_display: string[];
  formatted_for_prompt: string;
  is_fallback: boolean;
}> {
  const params: Record<string, string | number> = { project_id: projectId };
  if (memberId) params.member_id = memberId;
  const response = await api.get('/replies/calendly/slots', { params });
  return response.data;
}

// Follow-up
export async function generateFollowupDraft(replyId: number, calendlyContext?: string): Promise<{
  draft_reply: string;
  draft_subject: string | null;
  parent_reply_id: number;
  days_since_sent: number;
}> {
  const params: Record<string, string> = {};
  if (calendlyContext) params.calendly_context = calendlyContext;
  const response = await api.post(`/replies/${replyId}/generate-followup-draft`, null, { params });
  return response.data;
}

export async function sendFollowup(
  replyId: number,
  draft: { draft_reply: string; draft_subject?: string },
): Promise<{
  status: string;
  reply_id: number;
  parent_reply_id: number;
  lead_email?: string;
  message?: string;
  contact_id?: number;
  channel?: string;
  getsales_sent?: boolean;
  send_error?: string | null;
}> {
  const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  const params = isLocal ? { test_mode: true } : {};
  const response = await api.post(`/replies/${replyId}/send-followup`, draft, { params });
  return response.data;
}

export async function dismissReply(replyId: number): Promise<{
  success: boolean;
  reply_id: number;
  approval_status: string;
}> {
  const response = await api.patch(`/replies/${replyId}/status`, null, {
    params: { approval_status: 'dismissed' }
  });
  return response.data;
}

export async function dismissFollowup(replyId: number): Promise<{
  status: string;
  reply_id: number;
}> {
  const response = await api.post(`/replies/${replyId}/dismiss-followup`);
  return response.data;
}

export async function toggleQualified(replyId: number, isQualified: boolean): Promise<{
  success: boolean;
  reply_id: number;
  is_qualified: boolean;
}> {
  const response = await api.patch(`/replies/${replyId}/qualified`, null, { params: { is_qualified: isQualified } });
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
  getReplyCounts,
  getContactCampaigns,
  getContactInfoBatch,
  getReply,
  getReplyStats,
  getConversation,
  getFullHistory,
  getCampaignThread,
  resendNotification,
  getCampaignAnalyticsSummary,
  // Approval / Moderation
  approveAndSendReply,
  dismissReply,
  regenerateDraft,
  toggleQualified,
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
  // Calendly
  getCalendlyConfig,
  getCalendlySlots,
  // Follow-up
  generateFollowupDraft,
  sendFollowup,
  dismissFollowup,
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
