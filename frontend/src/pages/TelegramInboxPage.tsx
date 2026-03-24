import { useState, useEffect, useRef, useCallback } from 'react';
import { Upload, Wifi, WifiOff, Trash2, Send, Loader2, MessageCircle, User, AlertCircle } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import * as tgApi from '../api/telegram';
import type { TelegramDMAccount, TelegramDialog, TelegramMessage } from '../api/telegram';

export function TelegramInboxPage() {
  const { isDark } = useTheme();
  const t = themeColors(isDark);

  const [accounts, setAccounts] = useState<TelegramDMAccount[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<TelegramDMAccount | null>(null);
  const [dialogs, setDialogs] = useState<TelegramDialog[]>([]);
  const [selectedDialog, setSelectedDialog] = useState<TelegramDialog | null>(null);
  const [messages, setMessages] = useState<TelegramMessage[]>([]);
  const [messageText, setMessageText] = useState('');

  const [loading, setLoading] = useState({ accounts: false, dialogs: false, messages: false, sending: false, uploading: false });
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Load accounts on mount ─────────────────────────────────────
  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    setLoading(l => ({ ...l, accounts: true }));
    try {
      const accs = await tgApi.getAccounts();
      setAccounts(accs);
      if (accs.length > 0 && !selectedAccount) {
        setSelectedAccount(accs[0]);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load accounts');
    }
    setLoading(l => ({ ...l, accounts: false }));
  };

  // ── Load dialogs when account selected ─────────────────────────
  useEffect(() => {
    if (selectedAccount?.is_connected) {
      loadDialogs(selectedAccount.id);
    } else {
      setDialogs([]);
    }
    setSelectedDialog(null);
    setMessages([]);
  }, [selectedAccount?.id]);

  const loadDialogs = async (accountId: number) => {
    setLoading(l => ({ ...l, dialogs: true }));
    try {
      const d = await tgApi.getDialogs(accountId);
      setDialogs(d);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load dialogs');
    }
    setLoading(l => ({ ...l, dialogs: false }));
  };

  // ── Load messages when dialog selected ─────────────────────────
  useEffect(() => {
    if (selectedAccount && selectedDialog) {
      loadMessages(selectedAccount.id, selectedDialog.peer_id);
    }
  }, [selectedAccount?.id, selectedDialog?.peer_id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadMessages = async (accountId: number, peerId: number) => {
    setLoading(l => ({ ...l, messages: true }));
    try {
      const msgs = await tgApi.getMessages(accountId, peerId);
      setMessages(msgs);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load messages');
    }
    setLoading(l => ({ ...l, messages: false }));
  };

  // ── Upload tdata ───────────────────────────────────────────────
  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(l => ({ ...l, uploading: true }));
    setError(null);
    try {
      const acc = await tgApi.uploadTdata(file);
      setAccounts(prev => [acc, ...prev.filter(a => a.id !== acc.id)]);
      setSelectedAccount(acc);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Upload failed');
    }
    setLoading(l => ({ ...l, uploading: false }));
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ── Send message ───────────────────────────────────────────────
  const handleSend = async () => {
    if (!selectedAccount || !selectedDialog || !messageText.trim()) return;
    setLoading(l => ({ ...l, sending: true }));
    try {
      await tgApi.sendMessage(selectedAccount.id, selectedDialog.peer_id, messageText.trim());
      setMessageText('');
      await loadMessages(selectedAccount.id, selectedDialog.peer_id);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Send failed');
    }
    setLoading(l => ({ ...l, sending: false }));
  };

  // ── Account actions ────────────────────────────────────────────
  const handleConnect = async (acc: TelegramDMAccount) => {
    try {
      const updated = await tgApi.connectAccount(acc.id);
      setAccounts(prev => prev.map(a => a.id === acc.id ? updated : a));
      if (selectedAccount?.id === acc.id) setSelectedAccount(updated);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Connect failed');
    }
  };

  const handleDisconnect = async (acc: TelegramDMAccount) => {
    try {
      const updated = await tgApi.disconnectAccount(acc.id);
      setAccounts(prev => prev.map(a => a.id === acc.id ? updated : a));
      if (selectedAccount?.id === acc.id) setSelectedAccount(updated);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Disconnect failed');
    }
  };

  const handleDelete = async (acc: TelegramDMAccount) => {
    if (!confirm(`Delete account @${acc.username || acc.phone}?`)) return;
    try {
      await tgApi.deleteAccount(acc.id);
      setAccounts(prev => prev.filter(a => a.id !== acc.id));
      if (selectedAccount?.id === acc.id) {
        setSelectedAccount(null);
        setDialogs([]);
        setMessages([]);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Delete failed');
    }
  };

  // ── Render ─────────────────────────────────────────────────────
  return (
    <div className="h-full flex flex-col" style={{ background: t.bgApp, color: t.text }}>
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b" style={{ borderColor: t.border }}>
        <div className="flex items-center gap-2">
          <MessageCircle className="w-5 h-5" style={{ color: t.accent }} />
          <h1 className="text-lg font-semibold">Telegram Inbox</h1>
          <span className="text-xs px-2 py-0.5 rounded" style={{ background: isDark ? '#1a1a2e' : '#f0f0f0', color: t.textMuted }}>
            MVP
          </span>
        </div>
        <div className="flex items-center gap-2">
          <input ref={fileInputRef} type="file" accept=".zip" className="hidden" onChange={handleUpload} />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={loading.uploading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium transition-colors"
            style={{ background: t.accent, color: '#fff' }}
          >
            {loading.uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            Upload tdata
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 px-5 py-2 text-sm" style={{ background: isDark ? '#2d1515' : '#fef2f2', color: '#ef4444' }}>
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-xs underline">dismiss</button>
        </div>
      )}

      {/* Three-panel layout */}
      <div className="flex-1 flex min-h-0">
        {/* Left: Accounts */}
        <div className="w-56 flex-shrink-0 border-r overflow-y-auto" style={{ borderColor: t.border }}>
          <div className="px-3 py-2 text-xs font-medium uppercase tracking-wide" style={{ color: t.textMuted }}>
            Accounts ({accounts.length})
          </div>
          {accounts.map(acc => (
            <div
              key={acc.id}
              onClick={() => setSelectedAccount(acc)}
              className={`px-3 py-2.5 cursor-pointer border-b transition-colors ${selectedAccount?.id === acc.id ? '' : 'hover:opacity-80'}`}
              style={{
                borderColor: t.border,
                background: selectedAccount?.id === acc.id ? (isDark ? '#1a1a2e' : '#f0f4ff') : 'transparent',
              }}
            >
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${acc.is_connected ? 'bg-green-500' : 'bg-red-400'}`} />
                <span className="text-sm font-medium truncate">
                  {acc.first_name || acc.username || acc.phone || `#${acc.id}`}
                </span>
              </div>
              {acc.username && (
                <div className="text-xs mt-0.5 ml-4" style={{ color: t.textMuted }}>@{acc.username}</div>
              )}
              <div className="flex items-center gap-1 mt-1.5 ml-4">
                {acc.is_connected ? (
                  <button onClick={e => { e.stopPropagation(); handleDisconnect(acc); }}
                    className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: isDark ? '#2d1515' : '#fef2f2', color: '#ef4444' }}>
                    <WifiOff className="w-3 h-3 inline" /> off
                  </button>
                ) : (
                  <button onClick={e => { e.stopPropagation(); handleConnect(acc); }}
                    className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: isDark ? '#052e16' : '#dcfce7', color: '#16a34a' }}>
                    <Wifi className="w-3 h-3 inline" /> on
                  </button>
                )}
                <button onClick={e => { e.stopPropagation(); handleDelete(acc); }}
                  className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: isDark ? '#1a1a1a' : '#f5f5f5', color: t.textMuted }}>
                  <Trash2 className="w-3 h-3 inline" />
                </button>
              </div>
            </div>
          ))}
          {accounts.length === 0 && !loading.accounts && (
            <div className="px-3 py-8 text-center text-sm" style={{ color: t.textMuted }}>
              No accounts yet.<br />Upload a tdata ZIP to start.
            </div>
          )}
        </div>

        {/* Middle: Dialogs */}
        <div className="w-80 flex-shrink-0 border-r overflow-y-auto" style={{ borderColor: t.border }}>
          <div className="px-3 py-2 text-xs font-medium uppercase tracking-wide" style={{ color: t.textMuted }}>
            Conversations {dialogs.length > 0 && `(${dialogs.length})`}
          </div>
          {loading.dialogs && (
            <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin" style={{ color: t.textMuted }} /></div>
          )}
          {!loading.dialogs && dialogs.map(d => (
            <div
              key={d.peer_id}
              onClick={() => setSelectedDialog(d)}
              className={`px-3 py-2.5 cursor-pointer border-b transition-colors ${selectedDialog?.peer_id === d.peer_id ? '' : 'hover:opacity-80'}`}
              style={{
                borderColor: t.border,
                background: selectedDialog?.peer_id === d.peer_id ? (isDark ? '#1a1a2e' : '#f0f4ff') : 'transparent',
              }}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium truncate">{d.peer_name}</span>
                <div className="flex items-center gap-1.5">
                  {d.unread_count > 0 && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full font-bold" style={{ background: t.accent, color: '#fff' }}>
                      {d.unread_count}
                    </span>
                  )}
                  {d.last_message_at && (
                    <span className="text-[10px]" style={{ color: t.textMuted }}>
                      {formatTime(d.last_message_at)}
                    </span>
                  )}
                </div>
              </div>
              {d.peer_username && (
                <div className="text-[11px]" style={{ color: t.textMuted }}>@{d.peer_username}</div>
              )}
              {d.last_message && (
                <div className="text-xs mt-0.5 truncate" style={{ color: t.textMuted }}>
                  {d.last_message}
                </div>
              )}
            </div>
          ))}
          {!loading.dialogs && selectedAccount && !selectedAccount.is_connected && (
            <div className="px-3 py-8 text-center text-sm" style={{ color: t.textMuted }}>
              Account disconnected.<br />Connect to see dialogs.
            </div>
          )}
          {!loading.dialogs && selectedAccount?.is_connected && dialogs.length === 0 && (
            <div className="px-3 py-8 text-center text-sm" style={{ color: t.textMuted }}>
              No DM conversations found.
            </div>
          )}
        </div>

        {/* Right: Conversation */}
        <div className="flex-1 flex flex-col min-w-0">
          {selectedDialog ? (
            <>
              {/* Conversation header */}
              <div className="px-4 py-2.5 border-b flex items-center gap-2" style={{ borderColor: t.border }}>
                <User className="w-4 h-4" style={{ color: t.textMuted }} />
                <span className="font-medium text-sm">{selectedDialog.peer_name}</span>
                {selectedDialog.peer_username && (
                  <span className="text-xs" style={{ color: t.textMuted }}>@{selectedDialog.peer_username}</span>
                )}
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
                {loading.messages && (
                  <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin" style={{ color: t.textMuted }} /></div>
                )}
                {messages.map(msg => (
                  <div key={msg.id} className={`flex ${msg.direction === 'outbound' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className="max-w-[70%] px-3 py-2 rounded-lg text-sm"
                      style={{
                        background: msg.direction === 'outbound'
                          ? (isDark ? '#1a3a5c' : '#dcebff')
                          : (isDark ? '#2a2a2a' : '#f3f4f6'),
                        color: t.text,
                      }}
                    >
                      <div className="text-[10px] mb-0.5 font-medium" style={{ color: t.textMuted }}>
                        {msg.sender_name}
                      </div>
                      <div className="whitespace-pre-wrap break-words">{msg.text}</div>
                      {msg.sent_at && (
                        <div className="text-[10px] mt-1 text-right" style={{ color: t.textMuted }}>
                          {formatTime(msg.sent_at)}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>

              {/* Input */}
              <div className="px-4 py-3 border-t flex gap-2" style={{ borderColor: t.border }}>
                <input
                  value={messageText}
                  onChange={e => setMessageText(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                  placeholder="Type a message..."
                  className="flex-1 px-3 py-2 rounded text-sm border outline-none"
                  style={{ background: isDark ? '#1a1a1a' : '#fff', borderColor: t.border, color: t.text }}
                />
                <button
                  onClick={handleSend}
                  disabled={loading.sending || !messageText.trim()}
                  className="px-3 py-2 rounded flex items-center gap-1 text-sm font-medium transition-colors disabled:opacity-50"
                  style={{ background: t.accent, color: '#fff' }}
                >
                  {loading.sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </button>
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center" style={{ color: t.textMuted }}>
              <div className="text-center">
                <MessageCircle className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <div className="text-sm">Select a conversation</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function formatTime(isoStr: string): string {
  const d = new Date(isoStr);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  if (diff < 86400000 && d.getDate() === now.getDate()) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  if (diff < 604800000) {
    return d.toLocaleDateString([], { weekday: 'short' });
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}
