import { api } from './client';

export interface TelegramDMAccount {
  id: number;
  phone: string | null;
  telegram_user_id: number | null;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  auth_status: string;
  is_connected: boolean;
  project_id: number | null;
  last_connected_at: string | null;
  last_error: string | null;
  created_at: string | null;
}

export interface TelegramDialog {
  peer_id: number;
  peer_name: string;
  peer_username: string | null;
  last_message: string | null;
  last_message_at: string | null;
  unread_count: number;
}

export interface TelegramMessage {
  id: number;
  direction: 'inbound' | 'outbound';
  text: string;
  sent_at: string | null;
  sender_name: string;
}

export async function uploadTdata(file: File): Promise<TelegramDMAccount> {
  const form = new FormData();
  form.append('file', file);
  const res = await api.post('/telegram-dm/accounts/upload-tdata/', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function getAccounts(): Promise<TelegramDMAccount[]> {
  const res = await api.get('/telegram-dm/accounts/');
  return res.data;
}

export async function connectAccount(id: number): Promise<TelegramDMAccount> {
  const res = await api.post(`/telegram-dm/accounts/${id}/connect/`);
  return res.data;
}

export async function disconnectAccount(id: number): Promise<TelegramDMAccount> {
  const res = await api.post(`/telegram-dm/accounts/${id}/disconnect/`);
  return res.data;
}

export async function deleteAccount(id: number): Promise<void> {
  await api.delete(`/telegram-dm/accounts/${id}/`);
}

export async function updateAccount(id: number, data: { project_id?: number | null }): Promise<TelegramDMAccount> {
  const res = await api.patch(`/telegram-dm/accounts/${id}/`, data);
  return res.data;
}

export async function getDialogs(accountId: number, limit = 50): Promise<TelegramDialog[]> {
  const res = await api.get(`/telegram-dm/accounts/${accountId}/dialogs/`, { params: { limit } });
  return res.data;
}

export async function getMessages(accountId: number, peerId: number, limit = 50): Promise<TelegramMessage[]> {
  const res = await api.get(`/telegram-dm/accounts/${accountId}/messages/${peerId}/`, { params: { limit } });
  return res.data;
}

export async function sendMessage(accountId: number, peerId: number, text: string): Promise<{ success: boolean; message_id?: number }> {
  const res = await api.post(`/telegram-dm/accounts/${accountId}/messages/${peerId}/`, { text });
  return res.data;
}
