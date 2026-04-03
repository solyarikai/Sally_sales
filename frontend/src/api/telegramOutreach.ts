import { api } from './client';

// ── Types ─────────────────────────────────────────────────────────────

export interface TgAccountTag {
  id: number;
  name: string;
  color: string;
}

export interface TgAccount {
  id: number;
  phone: string;
  username?: string;
  first_name?: string;
  last_name?: string;
  bio?: string;
  device_model?: string;
  system_version?: string;
  app_version?: string;
  lang_code?: string;
  system_lang_code?: string;
  status: string;
  spamblock_type: string;
  spamblock_end?: string;
  daily_message_limit: number;
  is_premium?: boolean;
  effective_daily_limit?: number;
  warmup_day?: number | null;
  is_young_session?: boolean;
  skip_warmup?: boolean;
  warmup_active?: boolean;
  warmup_started_at?: string;
  warmup_actions_done?: number;
  warmup_progress?: { day: number; total_days: number; phase?: string } | null;
  messages_sent_today: number;
  total_messages_sent: number;
  proxy_group_id?: number;
  proxy_group_name?: string;
  assigned_proxy_id?: number;
  assigned_proxy_host?: string;
  tags: TgAccountTag[];
  campaigns_count: number;
  country_code?: string;
  session_created_at?: string;
  telegram_created_at?: string;
  last_connected_at?: string;
  last_checked_at?: string;
  created_at?: string;
  updated_at?: string;
}

export interface TgAccountListResponse {
  items: TgAccount[];
  total: number;
  page: number;
  page_size: number;
}

export interface TgProxyGroup {
  id: number;
  name: string;
  country?: string;
  description?: string;
  proxies_count: number;
  created_at?: string;
}

export interface TgProxy {
  id: number;
  proxy_group_id: number;
  host: string;
  port: number;
  username?: string;
  password?: string;
  protocol: string;
  is_active: boolean;
  last_checked_at?: string;
  created_at?: string;
}

export interface TgCampaign {
  id: number;
  name: string;
  status: string;
  daily_message_limit?: number;
  timezone: string;
  send_from_hour: number;
  send_to_hour: number;
  delay_between_sends_min: number;
  delay_between_sends_max: number;
  delay_randomness_percent: number;
  spamblock_errors_to_skip: number;
  messages_sent_today: number;
  total_messages_sent: number;
  total_recipients: number;
  tags: string[];
  accounts_count: number;
  replies_count: number;
  created_at?: string;
  updated_at?: string;
}

export interface TgCampaignListResponse {
  items: TgCampaign[];
  total: number;
}

export interface TgRecipient {
  id: number;
  campaign_id: number;
  username: string;
  first_name?: string;
  company_name?: string;
  custom_variables: Record<string, string>;
  status: string;
  current_step: number;
  assigned_account_id?: number;
  next_message_at?: string;
  last_message_sent_at?: string;
  created_at?: string;
}

export interface TgStepVariant {
  id?: number;
  variant_label: string;
  message_text: string;
  weight_percent: number;
  media_file_path?: string | null;
}

export type MessageType = 'text' | 'image' | 'video' | 'document' | 'voice';

export interface TgSequenceStep {
  id?: number;
  step_order: number;
  delay_days: number;
  message_type: MessageType;
  variants: TgStepVariant[];
}

export interface TgSequence {
  id?: number;
  name?: string;
  steps: TgSequenceStep[];
}

export interface TgCampaignStats {
  total_recipients: number;
  pending: number;
  in_sequence: number;
  completed: number;
  replied: number;
  failed: number;
  bounced: number;
  total_messages_sent: number;
  messages_sent_today: number;
}

export interface TgOutreachMessage {
  id: number;
  campaign_id: number;
  recipient_id: number;
  recipient_username?: string;
  account_id?: number;
  account_phone?: string;
  step_order?: number;
  variant_label?: string;
  rendered_text: string;
  status: string;
  error_message?: string;
  sent_at?: string;
}

// ── API ───────────────────────────────────────────────────────────────

const BASE = '/telegram-outreach';

export const telegramOutreachApi = {
  // Proxy Groups
  listProxyGroups: async () =>
    (await api.get<TgProxyGroup[]>(`${BASE}/proxy-groups`)).data,

  createProxyGroup: async (data: { name: string; country?: string; description?: string }) =>
    (await api.post<TgProxyGroup>(`${BASE}/proxy-groups`, data)).data,

  updateProxyGroup: async (id: number, data: Partial<{ name: string; country: string; description: string }>) =>
    (await api.put<TgProxyGroup>(`${BASE}/proxy-groups/${id}`, data)).data,

  deleteProxyGroup: async (id: number) =>
    (await api.delete(`${BASE}/proxy-groups/${id}`)).data,

  // Proxies
  listProxies: async (groupId: number) =>
    (await api.get<TgProxy[]>(`${BASE}/proxy-groups/${groupId}/proxies`)).data,

  addProxiesBulk: async (groupId: number, rawText: string, protocol: string = 'http') =>
    (await api.post<TgProxy[]>(`${BASE}/proxy-groups/${groupId}/proxies`, { raw_text: rawText, protocol })).data,

  deleteProxy: async (id: number) =>
    (await api.delete(`${BASE}/proxies/${id}`)).data,

  checkProxy: async (id: number) =>
    (await api.post<{ proxy_id: number; alive: boolean; latency_ms: number | null; error: string | null }>(
      `${BASE}/proxies/${id}/check`
    )).data,

  checkProxyGroup: async (groupId: number, autoDelete: boolean = false) =>
    (await api.post<{
      total: number; alive: number; dead: number; deleted: number;
      deleted_ids: number[];
      results: { proxy_id: number; host: string; port: number; alive: boolean; latency_ms: number | null; error: string | null }[];
    }>(`${BASE}/proxy-groups/${groupId}/check`, null, { params: { auto_delete: autoDelete } })).data,

  // Tags
  listTags: async () =>
    (await api.get<TgAccountTag[]>(`${BASE}/tags`)).data,

  createTag: async (data: { name: string; color?: string }) =>
    (await api.post<TgAccountTag>(`${BASE}/tags`, data)).data,

  deleteTag: async (id: number) =>
    (await api.delete(`${BASE}/tags/${id}`)).data,

  bulkTag: async (accountIds: number[], tagId: number) =>
    (await api.post(`${BASE}/accounts/bulk-tag`, { account_ids: accountIds, tag_id: tagId })).data,

  bulkUntag: async (accountIds: number[], tagId: number) =>
    (await api.post(`${BASE}/accounts/bulk-untag`, { account_ids: accountIds, tag_id: tagId })).data,

  // Accounts
  listAccounts: async (params: {
    page?: number; page_size?: number; status?: string;
    tag_id?: number; proxy_group_id?: number; search?: string;
  } = {}) =>
    (await api.get<TgAccountListResponse>(`${BASE}/accounts`, { params })).data,

  createAccount: async (data: Record<string, any>) =>
    (await api.post<TgAccount>(`${BASE}/accounts`, data)).data,

  updateAccount: async (id: number, data: Record<string, any>) =>
    (await api.put<TgAccount>(`${BASE}/accounts/${id}`, data)).data,

  deleteAccount: async (id: number) =>
    (await api.delete(`${BASE}/accounts/${id}`)).data,

  updateAccountLimit: async (id: number, limit: number) =>
    (await api.patch(`${BASE}/accounts/${id}/limit`, null, { params: { daily_message_limit: limit } })).data,

  bulkAssignProxy: async (accountIds: number[], proxyGroupId: number) =>
    (await api.post(`${BASE}/accounts/bulk-assign-proxy`, { account_ids: accountIds, proxy_group_id: proxyGroupId })).data,

  bulkSetLimit: async (accountIds: number[], limit: number) =>
    (await api.post(`${BASE}/accounts/bulk-set-limit`, { account_ids: accountIds }, { params: { daily_message_limit: limit } })).data,

  bulkSkipWarmup: async (accountIds: number[], skip: boolean = true) =>
    (await api.post(`${BASE}/accounts/bulk-skip-warmup`, { account_ids: accountIds }, { params: { skip } })).data,

  // Active warm-up
  warmupStart: async (accountId: number) =>
    (await api.post(`${BASE}/accounts/${accountId}/warmup/start`)).data,

  warmupStop: async (accountId: number) =>
    (await api.post(`${BASE}/accounts/${accountId}/warmup/stop`)).data,

  warmupStatus: async (accountId: number) =>
    (await api.get(`${BASE}/accounts/${accountId}/warmup/status`)).data,

  warmupLogs: async (accountId: number): Promise<{ action_type: string; detail: string | null; success: boolean; error_message: string | null; performed_at: string | null }[]> =>
    (await api.get(`${BASE}/accounts/${accountId}/warmup/logs`)).data,

  bulkWarmup: async (accountIds: number[], action: 'start' | 'stop' = 'start') =>
    (await api.post(`${BASE}/accounts/bulk-warmup`, { account_ids: accountIds }, { params: { action } })).data,

  // Warm-up channels
  getWarmupChannels: async () =>
    (await api.get<{ id: number; url: string; title: string | null; is_active: boolean; created_at: string }[]>(`${BASE}/warmup/channels`)).data,

  addWarmupChannel: async (url: string, title?: string) =>
    (await api.post(`${BASE}/warmup/channels`, { url, title })).data,

  deleteWarmupChannel: async (channelId: number) =>
    (await api.delete(`${BASE}/warmup/channels/${channelId}`)).data,

  toggleWarmupChannel: async (channelId: number, isActive: boolean) =>
    (await api.patch(`${BASE}/warmup/channels/${channelId}`, null, { params: { is_active: isActive } })).data,

  seedWarmupChannels: async () =>
    (await api.post(`${BASE}/warmup/channels/seed`)).data,

  bulkUpdateParams: async (accountIds: number[], params: {
    device_model?: string; system_version?: string; app_version?: string;
    lang_code?: string; system_lang_code?: string;
  }) =>
    (await api.post(`${BASE}/accounts/bulk-update-params`, { account_ids: accountIds }, { params })).data,

  bulkRandomizeDevice: async (accountIds: number[]) =>
    (await api.post(`${BASE}/accounts/bulk-randomize-device`, { account_ids: accountIds })).data,

  getDevicePresets: async () =>
    (await api.get<{
      devices: string[]; system_versions: string[]; app_versions: string[];
      lang_codes: string[]; system_lang_codes: string[];
    }>(`${BASE}/accounts/device-presets`)).data,

  getLatestAppVersion: async () =>
    (await api.get<{
      latest_version: string | null; raw_version: string | null;
      checked_at: string | null; current_presets: string[];
    }>(`${BASE}/app-version/latest`)).data,

  refreshAppVersion: async () =>
    (await api.post<{ latest_version: string | null; raw_version: string | null }>(`${BASE}/app-version/refresh`)).data,

  bulkUpdateAppVersion: async (accountIds: number[], version?: string) =>
    (await api.post(`${BASE}/accounts/bulk-update-app-version`,
      { account_ids: accountIds },
      { params: { ...(version ? { version } : {}), all_accounts: accountIds.length === 0 } }
    )).data,

  updateAllAppVersion: async (version?: string) =>
    (await api.post(`${BASE}/accounts/bulk-update-app-version`, null,
      { params: { all_accounts: true, ...(version ? { version } : {}) } }
    )).data,

  bulkRandomizeNames: async (accountIds: number[], category: string = 'male_en') =>
    (await api.post(`${BASE}/accounts/bulk-randomize-names`, { account_ids: accountIds }, { params: { category } })).data,

  bulkSetPhoto: async (accountIds: number[], photos: File[]) => {
    const formData = new FormData();
    formData.append('account_ids_json', JSON.stringify(accountIds));
    photos.forEach(p => formData.append('photos', p));
    return (await api.post(`${BASE}/accounts/bulk-set-photo`, formData, {
      headers: { 'Content-Type': undefined as any },
    })).data;
  },

  bulkSyncProfile: async (accountIds: number[]) =>
    (await api.post(`${BASE}/accounts/bulk-sync-profile`, { account_ids: accountIds })).data,

  bulkSetBio: async (accountIds: number[], bio: string) =>
    (await api.post(`${BASE}/accounts/bulk-set-bio`, { account_ids: accountIds }, { params: { bio } })).data,

  bulkSet2FA: async (accountIds: number[], password: string) =>
    (await api.post(`${BASE}/accounts/bulk-set-2fa`, { account_ids: accountIds }, { params: { password } })).data,

  bulkSetStatus: async (accountIds: number[], status: string) =>
    (await api.post(`${BASE}/accounts/bulk-set-status`, { account_ids: accountIds }, { params: { status } })).data,

  bulkUpdatePrivacy: async (accountIds: number[], settings: Record<string, string>) =>
    (await api.post(`${BASE}/accounts/bulk-update-privacy`, { account_ids: accountIds }, { params: settings })).data,

  bulkRevokeSessions: async (accountIds: number[]) =>
    (await api.post(`${BASE}/accounts/bulk-revoke-sessions`, { account_ids: accountIds })).data,

  bulkOpProgress: async (taskId: string) =>
    (await api.get(`${BASE}/accounts/bulk-op-progress/${taskId}`)).data,

  bulkReauthorize: async (accountIds: number[], params: { new_2fa?: string; close_old_sessions?: boolean } = {}) =>
    (await api.post(`${BASE}/accounts/bulk-reauthorize`, { account_ids: accountIds }, { params })).data,

  bulkCheck: async (accountIds: number[]) =>
    (await api.post(`${BASE}/accounts/bulk-check`, { account_ids: accountIds })).data,

  importTeleRaptor: async (accounts: Record<string, any>[]) =>
    (await api.post<{ added: number; skipped: number; errors: string[] }>(
      `${BASE}/accounts/import-teleraptor`, { accounts }
    )).data,

  importBundle: async (files: File[]) => {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    return (await api.post<{
      added: number; skipped: number; sessions_saved: number;
      total_files: number; pairs_found: number; errors: string[];
    }>(`${BASE}/accounts/import-bundle`, formData, {
      headers: { 'Content-Type': undefined as any },
      timeout: 120000,
    })).data;
  },

  convertToTdata: async (accountId: number) =>
    (await api.post(`${BASE}/accounts/${accountId}/convert-to-tdata`)).data,

  convertFromTdata: async (accountId: number) =>
    (await api.post(`${BASE}/accounts/${accountId}/convert-from-tdata`)).data,

  downloadTdata: (accountId: number) =>
    `${api.defaults.baseURL}${BASE}/accounts/${accountId}/download-tdata`,

  downloadSession: (accountId: number) =>
    `${api.defaults.baseURL}${BASE}/accounts/${accountId}/download-session`,

  uploadTdata: async (accountId: number, files: File[]) => {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    return (await api.post(`${BASE}/accounts/${accountId}/upload-tdata`, formData, {
      headers: { 'Content-Type': undefined as any },
    })).data;
  },

  getAccountCampaigns: async (id: number) =>
    (await api.get(`${BASE}/accounts/${id}/campaigns`)).data,

  // Campaigns
  listCampaigns: async () =>
    (await api.get<TgCampaignListResponse>(`${BASE}/campaigns`)).data,

  createCampaign: async (data: Record<string, any>) =>
    (await api.post<TgCampaign>(`${BASE}/campaigns`, data)).data,

  updateCampaign: async (id: number, data: Record<string, any>) =>
    (await api.put<TgCampaign>(`${BASE}/campaigns/${id}`, data)).data,

  deleteCampaign: async (id: number) =>
    (await api.delete(`${BASE}/campaigns/${id}`)).data,

  startCampaign: async (id: number) =>
    (await api.post(`${BASE}/campaigns/${id}/start`)).data,

  pauseCampaign: async (id: number) =>
    (await api.post(`${BASE}/campaigns/${id}/pause`)).data,

  getCampaignStats: async (id: number) =>
    (await api.get<TgCampaignStats>(`${BASE}/campaigns/${id}/stats`)).data,

  getCampaignStepStats: async (id: number, params: { period?: string; from_date?: string; to_date?: string } = {}) =>
    (await api.get(`${BASE}/campaigns/${id}/step-stats`, { params })).data as {
      steps: { step_order: number; step_id: number; delay_days: number; sent: number; read: number; replied: number }[];
      totals: { sent: number; read: number; replied: number; total_recipients: number };
      period: string | null;
    },

  getCampaignTimeline: async (id: number, params: { page?: number; page_size?: number; search?: string; sort_by?: string; sort_dir?: string } = {}) =>
    (await api.get(`${BASE}/campaigns/${id}/timeline`, { params })).data as {
      steps: { step_order: number; step_id: number; delay_days: number }[];
      recipients: {
        id: number; username: string; first_name: string | null; status: string;
        assigned_account_id: number | null; assigned_account_phone: string | null;
        next_message_at: string | null;
        steps: Record<string, { status: string; sent_at: string | null; read_at: string | null; replied_at: string | null; error_message: string | null }>;
      }[];
      total: number; page: number; page_size: number;
    },

  getCampaignAccounts: async (id: number) =>
    (await api.get(`${BASE}/campaigns/${id}/accounts`)).data,

  setCampaignAccounts: async (id: number, accountIds: number[]) =>
    (await api.put(`${BASE}/campaigns/${id}/accounts`, accountIds)).data,

  // Recipients
  listRecipients: async (campaignId: number, params: { page?: number; page_size?: number; status?: string } = {}) =>
    (await api.get(`${BASE}/campaigns/${campaignId}/recipients`, { params })).data,

  uploadRecipientsText: async (campaignId: number, rawText: string) =>
    (await api.post(`${BASE}/campaigns/${campaignId}/recipients/upload-text`, { raw_text: rawText })).data,

  uploadRecipientsCSV: async (campaignId: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return (await api.post(`${BASE}/campaigns/${campaignId}/recipients/upload-csv`, formData, {
      headers: { 'Content-Type': undefined as any },
    })).data;
  },

  mapColumnsCSV: async (campaignId: number, file: File, mapping: {
    username_column: string;
    phone_column?: string;
    first_name_column?: string;
    company_name_column?: string;
    custom_columns?: Record<string, string>;
  }) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('mapping_json', JSON.stringify(mapping));
    return (await api.post(`${BASE}/campaigns/${campaignId}/recipients/map-columns`, formData, {
      headers: { 'Content-Type': undefined as any },
    })).data;
  },

  addRecipientsFromCrm: async (campaignId: number, contactIds: number[]) =>
    (await api.post(`${BASE}/campaigns/${campaignId}/recipients/add-from-crm`, { contact_ids: contactIds })).data,

  deleteRecipient: async (campaignId: number, recipientId: number) =>
    (await api.delete(`${BASE}/campaigns/${campaignId}/recipients/${recipientId}`)).data,

  checkDuplicates: async (campaignId: number, usernames: string[]): Promise<{
    total_checked: number;
    duplicates_count: number;
    duplicates: Array<{
      username: string;
      campaign_id: number;
      campaign_name: string;
      campaign_status: string;
      current_step: number;
      total_steps: number;
      step_label: string;
      recipient_status: string;
      campaign_completion_pct: number;
      assigned_account: string | null;
    }>;
  }> =>
    (await api.post(`${BASE}/campaigns/${campaignId}/recipients/check-duplicates`, { usernames })).data,

  bulkRemoveRecipients: async (campaignId: number, usernames: string[]): Promise<{ ok: boolean; removed: number }> =>
    (await api.post(`${BASE}/campaigns/${campaignId}/recipients/bulk-remove`, { usernames })).data,

  // Sequences
  getSequence: async (campaignId: number) =>
    (await api.get<TgSequence>(`${BASE}/campaigns/${campaignId}/sequence`)).data,

  updateSequence: async (campaignId: number, data: TgSequence) =>
    (await api.put<TgSequence>(`${BASE}/campaigns/${campaignId}/sequence`, data)).data,

  uploadMedia: async (campaignId: number, file: File) => {
    const fd = new FormData();
    fd.append('file', file);
    return (await api.post<{ file_path: string; filename: string; size: number }>(`${BASE}/campaigns/${campaignId}/media`, fd)).data;
  },

  previewSequence: async (campaignId: number, recipientIndex: number = 0) =>
    (await api.post(`${BASE}/campaigns/${campaignId}/sequence/preview`, { recipient_index: recipientIndex })).data,

  // Messages
  listMessages: async (campaignId: number, params: { page?: number; page_size?: number } = {}) =>
    (await api.get(`${BASE}/campaigns/${campaignId}/messages`, { params })).data,

  // ── Telegram Engine (Phase 4) ────────────────────────────────────

  uploadSession: async (accountId: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return (await api.post(`${BASE}/accounts/${accountId}/upload-session`, formData, {
      headers: { 'Content-Type': undefined as any },
    })).data;
  },

  addByPhone: async (phone: string, twoFaPassword?: string) =>
    (await api.post<{ account_id: number; phone: string; status: string; device_model: string }>(
      `${BASE}/accounts/add-by-phone`, null,
      { params: { phone, ...(twoFaPassword ? { two_fa_password: twoFaPassword } : {}) } }
    )).data,

  authSendCode: async (accountId: number) =>
    (await api.post(`${BASE}/accounts/${accountId}/auth/send-code`)).data,

  authVerifyCode: async (accountId: number, code: string) =>
    (await api.post(`${BASE}/accounts/${accountId}/auth/verify-code`, null, { params: { code } })).data,

  authVerify2FA: async (accountId: number, password: string) =>
    (await api.post(`${BASE}/accounts/${accountId}/auth/verify-2fa`, null, { params: { password } })).data,

  checkAccount: async (accountId: number) =>
    (await api.post<Record<string, any>>(`${BASE}/accounts/${accountId}/check`)).data,

  bulkCheckLive: async (accountIds: number[]) =>
    (await api.post<{ results: Record<string, any>[] }>(`${BASE}/accounts/bulk-check-live`, { account_ids: accountIds })).data,

  bulkCheckAlive: async (accountIds: number[]) =>
    (await api.post<{ total: number; alive: number; frozen: number; banned: number; dead: number; results: Record<string, any>[] }>(`${BASE}/accounts/bulk-check-alive`, { account_ids: accountIds })).data,

  updateProfile: async (accountId: number, params: {
    first_name?: string; last_name?: string; about?: string; username?: string;
  }) =>
    (await api.post(`${BASE}/accounts/${accountId}/update-profile`, null, { params })).data,

  checkUsername: async (accountId: number, username: string) =>
    (await api.post<{ status: string; available?: boolean; reason?: string }>(`${BASE}/accounts/${accountId}/check-username`, null, { params: { username } })).data,

  suggestUsernames: async (accountId: number, firstName: string, lastName: string) =>
    (await api.post<{ suggestions: string[] }>(`${BASE}/accounts/${accountId}/suggest-usernames`, null, { params: { first_name: firstName, last_name: lastName } })).data,

  // CRM
  listCrmContacts: async (params: { page?: number; page_size?: number; status?: string; search?: string } = {}) =>
    (await api.get(`${BASE}/crm/contacts`, { params })).data,

  getCrmContact: async (id: number) =>
    (await api.get(`${BASE}/crm/contacts/${id}`)).data,

  updateCrmContact: async (id: number, data: Record<string, any>) =>
    (await api.put(`${BASE}/crm/contacts/${id}`, data)).data,

  bulkUpdateCrmStatus: async (contactIds: number[], status: string) =>
    (await api.post(`${BASE}/crm/contacts/bulk-update-status`, contactIds, { params: { status } })).data,

  deleteCrmContact: async (id: number) =>
    (await api.delete(`${BASE}/crm/contacts/${id}`)).data,

  bulkDeleteCrmContacts: async (ids: number[]) =>
    (await api.post(`${BASE}/crm/contacts/bulk-delete`, { ids })).data,

  getCrmStats: async () =>
    (await api.get(`${BASE}/crm/stats`)).data,

  getCrmContactHistory: async (id: number) =>
    (await api.get(`${BASE}/crm/contacts/${id}/history`)).data,

  getCrmContactCampaigns: async (id: number) =>
    (await api.get(`${BASE}/crm/contacts/${id}/campaigns`)).data,

  getCrmPipeline: async (params: { search?: string; limit_per_status?: number } = {}) =>
    (await api.get(`${BASE}/crm/pipeline`, { params })).data,

  // Tools
  checkPhones: async (phones: string[], accountId: number) =>
    (await api.post(`${BASE}/tools/check-phones`, phones, { params: { account_id: accountId } })).data,

  massViewStories: async (usernames: string[], accountIds: number[], react: boolean = false, emoji: string = '👍') =>
    (await api.post(`${BASE}/tools/mass-view-stories`, null, {
      params: { react, reaction_emoji: emoji },
      data: { usernames, account_ids: accountIds },
    })).data,

  // Parser
  scrapeGroup: async (groupUsername: string, accountId: number, limit: number = 500) =>
    (await api.post(`${BASE}/parser/scrape-group`, null, { params: { group_username: groupUsername, account_id: accountId, limit } })).data,

  addParsedToCampaign: async (campaignId: number, members: any[]) =>
    (await api.post(`${BASE}/parser/add-to-campaign`, members, { params: { campaign_id: campaignId } })).data,

  // Export & Clean
  exportAccountsURL: () => `${api.defaults.baseURL}${BASE}/accounts/export`,

  getAccountAnalytics: async (accountId: number) =>
    (await api.get(`${BASE}/accounts/${accountId}/analytics`)).data,

  getAccountsAnalyticsOverview: async () =>
    (await api.get(`${BASE}/accounts/analytics/overview`)).data,

  bulkClean: async (accountIds: number[], params: { delete_dialogs?: boolean; delete_contacts?: boolean }) =>
    (await api.post(`${BASE}/accounts/bulk-clean`, { account_ids: accountIds }, { params })).data,

  // Auto-Reply
  getAutoReplyConfig: async (campaignId: number) =>
    (await api.get(`${BASE}/campaigns/${campaignId}/auto-reply/config`)).data,

  updateAutoReplyConfig: async (campaignId: number, config: Record<string, any>) =>
    (await api.put(`${BASE}/campaigns/${campaignId}/auto-reply/config`, config)).data,

  listConversations: async (campaignId: number) =>
    (await api.get(`${BASE}/campaigns/${campaignId}/conversations`)).data,

  stopConversation: async (campaignId: number, convId: number) =>
    (await api.post(`${BASE}/campaigns/${campaignId}/conversations/${convId}/stop`)).data,

  // Reports
  downloadReportURL: (campaignId: number, format: string = 'html') =>
    `${api.defaults.baseURL}${BASE}/campaigns/${campaignId}/report?format=${format}`,

  analyticsExportCSVURL: (campaignId: number, params: { period?: string; from_date?: string; to_date?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.period) qs.set('period', params.period);
    if (params.from_date) qs.set('from_date', params.from_date);
    if (params.to_date) qs.set('to_date', params.to_date);
    const q = qs.toString();
    return `${api.defaults.baseURL}${BASE}/campaigns/${campaignId}/analytics/export-csv${q ? '?' + q : ''}`;
  },

  // Activity log
  getCampaignActivity: async (campaignId: number, limit: number = 50) =>
    (await api.get<{ activity: any[] }>(`${BASE}/campaigns/${campaignId}/activity`, { params: { limit } })).data,

  // ── Replies (Phase 6) ──────────────────────────────────────────

  listCampaignReplies: async (campaignId: number, params: { page?: number; page_size?: number } = {}) =>
    (await api.get(`${BASE}/campaigns/${campaignId}/replies`, { params })).data,

  listRecentReplies: async (params: { page?: number; page_size?: number } = {}) =>
    (await api.get(`${BASE}/replies/recent`, { params })).data,

  exportCampaignReplies: async (campaignId: number) =>
    (await api.get(`${BASE}/campaigns/${campaignId}/replies/export`)).data,

  // ── Sending Worker (Phase 5) ─────────────────────────────────────

  getWorkerStatus: async () =>
    (await api.get<{ running: boolean; sending: boolean; replies: boolean }>(`${BASE}/worker/status`)).data,

  startWorker: async () =>
    (await api.post(`${BASE}/worker/start`)).data,

  stopWorker: async () =>
    (await api.post(`${BASE}/worker/stop`)).data,

  resetDailyCounters: async () =>
    (await api.post(`${BASE}/worker/reset-daily-counters`)).data,

  // Inbox (legacy thread-based)
  listInboxThreads: async (params: { campaign_id?: number; account_id?: number; campaign_tag?: string; tag?: string; page?: number; page_size?: number }) =>
    (await api.get(`${BASE}/inbox/threads`, { params })).data,

  getThreadMessages: async (recipientId: number, limit: number = 50) =>
    (await api.get(`${BASE}/inbox/threads/${recipientId}/messages`, { params: { limit } })).data,

  sendInboxReply: async (recipientId: number, text: string) =>
    (await api.post(`${BASE}/inbox/threads/${recipientId}/send`, { text })).data,

  tagInboxThread: async (recipientId: number, tag: string) =>
    (await api.patch(`${BASE}/inbox/threads/${recipientId}/tag`, { tag })).data,

  // New inbox endpoints (dialog-based)
  listInboxDialogs: async (params: { account_id?: number; campaign_id?: number; campaign_tag?: string; tag?: string; search?: string; page?: number; page_size?: number }) =>
    (await api.get(`${BASE}/inbox/dialogs`, { params })).data,

  getDialogMessages: async (dialogId: number, limit: number = 30) =>
    (await api.get(`${BASE}/inbox/dialogs/${dialogId}/messages`, { params: { limit } })).data,

  sendDialogMessage: async (dialogId: number, text: string, opts?: { parseMode?: string; replyTo?: number }) =>
    (await api.post(`${BASE}/inbox/dialogs/${dialogId}/send`, { text, parseMode: opts?.parseMode, replyTo: opts?.replyTo })).data,

  sendDialogFile: async (dialogId: number, file: File, opts?: { caption?: string; parseMode?: string; replyTo?: number }) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('caption', opts?.caption || '');
    formData.append('parse_mode', opts?.parseMode || '');
    if (opts?.replyTo) formData.append('reply_to', String(opts.replyTo));
    return (await api.post(`${BASE}/inbox/dialogs/${dialogId}/send-file`, formData, {
      headers: { 'Content-Type': undefined as any },
    })).data;
  },

  editDialogMessage: async (dialogId: number, msgId: number, text: string, parseMode?: string) =>
    (await api.put(`${BASE}/inbox/dialogs/${dialogId}/messages/${msgId}/edit`, { text, parseMode })).data,

  deleteDialogMessage: async (dialogId: number, msgId: number, revoke: boolean = false) =>
    (await api.delete(`${BASE}/inbox/dialogs/${dialogId}/messages/${msgId}`, { params: { revoke } })).data,

  reactDialogMessage: async (dialogId: number, msgId: number, emoji: string) =>
    (await api.post(`${BASE}/inbox/dialogs/${dialogId}/messages/${msgId}/react`, { emoji })).data,

  forwardDialogMessages: async (dialogId: number, targetDialogId: number, msgIds: number[]) =>
    (await api.post(`${BASE}/inbox/dialogs/${dialogId}/forward`, { target_dialog_id: targetDialogId, msg_ids: msgIds })).data,

  tagDialog: async (dialogId: number, tag: string) =>
    (await api.patch(`${BASE}/inbox/dialogs/${dialogId}/tag`, { tag })).data,

  markDialogUnread: async (dialogId: number) =>
    (await api.post(`${BASE}/inbox/dialogs/${dialogId}/unread`)).data,

  getDialogCrm: async (dialogId: number) =>
    (await api.get(`${BASE}/inbox/dialogs/${dialogId}/crm`)).data,

  listCampaignTags: async () =>
    (await api.get(`${BASE}/inbox/campaign-tags`)).data as string[],

  triggerInboxSync: async (accountId?: number) =>
    (await api.post(`${BASE}/inbox/sync`, null, { params: accountId ? { account_id: accountId } : {} })).data,

  listInboxAccounts: async () =>
    (await api.get(`${BASE}/inbox/accounts`)).data as { id: number; phone: string; username?: string; first_name?: string; last_name?: string; is_connected: boolean; auth_status: string; tg_status?: string; campaign_ids: number[]; tag_names: string[] }[],

  updateCampaignTags: async (campaignId: number, tags: string[]) =>
    (await api.patch(`${BASE}/campaigns/${campaignId}/tags`, tags)).data,

  getDialogMediaUrl: (dialogId: number, msgId: number) =>
    `${api.defaults.baseURL}${BASE}/inbox/dialogs/${dialogId}/media/${msgId}`,

  createNewChat: async (accountId: number, username: string) =>
    (await api.post(`${BASE}/inbox/new-chat`, { account_id: accountId, username })).data,

  // Blacklist
  listBlacklist: async (params: { page?: number; page_size?: number; search?: string } = {}) =>
    (await api.get(`${BASE}/blacklist`, { params })).data,

  uploadBlacklist: async (raw_text: string, reason?: string) =>
    (await api.post(`${BASE}/blacklist/upload`, { raw_text, reason })).data,

  deleteBlacklistEntry: async (id: number) =>
    (await api.delete(`${BASE}/blacklist/${id}`)).data,

  bulkDeleteBlacklist: async (ids: number[]) =>
    (await api.post(`${BASE}/blacklist/bulk-delete`, { ids })).data,

  getBlacklistCount: async () =>
    (await api.get(`${BASE}/blacklist/count`)).data,
};
