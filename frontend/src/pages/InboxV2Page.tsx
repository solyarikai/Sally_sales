import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Search, Send, Loader2, MessageCircle, User, ChevronRight, ChevronLeft,
  Tag, Clock, Paperclip, X, Hash, StickyNote, MoreVertical, ArrowLeft,
} from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { telegramOutreachApi } from '../api/telegramOutreach';
import { useAppStore } from '../store/appStore';
import { Link } from 'react-router-dom';

/* ─────────── types ─────────── */
interface InboxDialog {
  id: number;
  peer_id: number;
  peer_name: string;
  peer_username: string | null;
  account_id: number;
  account_phone: string;
  account_username: string | null;
  last_message: string | null;
  last_message_at: string | null;
  last_direction: string | null;
  unread_count: number;
  tag: string | null;
  campaign_name: string | null;
  lead_status: string | null;
}

interface InboxMessage {
  id: number;
  direction: 'inbound' | 'outbound';
  text: string;
  sent_at: string | null;
  sender_name: string;
  is_read: boolean;
  media_type?: string | null;
  reply_to_id?: number | null;
}

interface CrmInfo {
  contact_id: number | null;
  status: string | null;
  tags: string[];
  campaigns: { id: number; name: string; step: number; sent_at: string }[];
  notes: { id: number; text: string; created_at: string; author: string }[];
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  company: string | null;
}

/* ─────────── avatar colors ─────────── */
const AVATAR_COLORS = [
  '#E17076', '#7BC862', '#6EC9CB', '#65AADD', '#EE7AE6',
  '#E2A62F', '#7B72E9', '#6DAFCF',
];
function avatarColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) | 0;
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

function Avatar({ name, size = 40 }: { name: string; size?: number }) {
  const bg = avatarColor(name);
  const initials = name.split(/\s+/).map(w => w[0]).slice(0, 2).join('').toUpperCase() || '?';
  return (
    <div
      className="rounded-full flex items-center justify-center flex-shrink-0 font-medium text-white select-none"
      style={{ width: size, height: size, background: bg, fontSize: size * 0.38 }}
    >
      {initials}
    </div>
  );
}

/* ─────────── helpers ─────────── */
function formatTime(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
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

function formatMessageTime(iso: string | null): string {
  if (!iso) return '';
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatDateSeparator(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffDays = Math.floor((now.getTime() - d.getTime()) / 86400000);
  if (diffDays === 0 && d.getDate() === now.getDate()) return 'Today';
  if (diffDays <= 1 && d.getDate() === now.getDate() - 1) return 'Yesterday';
  return d.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' });
}

const TAG_COLORS: Record<string, string> = {
  interested: '#22c55e',
  not_interested: '#ef4444',
  meeting_booked: '#3b82f6',
  follow_up: '#f59e0b',
  spam: '#6b7280',
};

/* ─────────── main component ─────────── */
export function InboxV2Page() {
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const currentProject = useAppStore(s => s.currentProject);

  /* ── state ── */
  const [dialogs, setDialogs] = useState<InboxDialog[]>([]);
  const [selectedDialog, setSelectedDialog] = useState<InboxDialog | null>(null);
  const [messages, setMessages] = useState<InboxMessage[]>([]);
  const [messageText, setMessageText] = useState('');
  const [sending, setSending] = useState(false);
  const [search, setSearch] = useState('');
  const [filterTag, setFilterTag] = useState('');
  const [loading, setLoading] = useState({ dialogs: true, messages: false });
  const [crmData, setCrmData] = useState<CrmInfo | null>(null);
  const [crmLoading, setCrmLoading] = useState(false);
  const [showCrm, setShowCrm] = useState(true);
  const [noteText, setNoteText] = useState('');

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const dialogPollRef = useRef(false);
  const msgPollRef = useRef(false);
  const prevMsgCount = useRef(0);
  const editorRef = useRef<HTMLTextAreaElement>(null);

  /* ── load dialogs ── */
  const loadDialogs = useCallback(async (silent = false) => {
    if (dialogPollRef.current) return;
    dialogPollRef.current = true;
    if (!silent) setLoading(l => ({ ...l, dialogs: true }));
    try {
      const params: any = { page_size: 100 };
      if (search) params.search = search;
      if (filterTag) params.tag = filterTag;
      if (currentProject?.id) params.project_id = currentProject.id;
      const data = await telegramOutreachApi.listInboxDialogs(params);
      setDialogs(data.items || data.dialogs || data || []);
    } catch { /* silent */ }
    if (!silent) setLoading(l => ({ ...l, dialogs: false }));
    dialogPollRef.current = false;
  }, [search, filterTag, currentProject?.id]);

  useEffect(() => { loadDialogs(); }, [loadDialogs]);

  // Poll dialogs every 12s
  useEffect(() => {
    const iv = setInterval(() => loadDialogs(true), 12000);
    return () => clearInterval(iv);
  }, [loadDialogs]);

  /* ── load messages ── */
  const loadMessages = useCallback(async (dialogId: number, silent = false) => {
    if (msgPollRef.current) return;
    msgPollRef.current = true;
    if (!silent) setLoading(l => ({ ...l, messages: true }));
    try {
      const data = await telegramOutreachApi.getDialogMessages(dialogId, 50);
      setMessages(data.messages || data || []);
    } catch { /* silent */ }
    if (!silent) setLoading(l => ({ ...l, messages: false }));
    msgPollRef.current = false;
  }, []);

  // On dialog select
  const selectDialog = useCallback((d: InboxDialog) => {
    setSelectedDialog(d);
    setMessages([]);
    setCrmData(null);
    prevMsgCount.current = 0;
    loadMessages(d.id);
    // Load CRM
    setCrmLoading(true);
    telegramOutreachApi.getDialogCrm(d.id)
      .then((data: any) => setCrmData(data))
      .catch(() => setCrmData(null))
      .finally(() => setCrmLoading(false));
  }, [loadMessages]);

  // Poll messages every 6s
  useEffect(() => {
    if (!selectedDialog) return;
    const iv = setInterval(() => loadMessages(selectedDialog.id, true), 6000);
    return () => clearInterval(iv);
  }, [selectedDialog?.id, loadMessages]);

  // Auto-scroll on new messages
  useEffect(() => {
    if (messages.length > prevMsgCount.current || prevMsgCount.current === 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
    prevMsgCount.current = messages.length;
  }, [messages]);

  /* ── send message ── */
  const handleSend = async () => {
    if (!selectedDialog || !messageText.trim()) return;
    setSending(true);
    try {
      await telegramOutreachApi.sendDialogMessage(selectedDialog.id, messageText.trim());
      setMessageText('');
      await loadMessages(selectedDialog.id, true);
    } catch { /* error handled by API client toast */ }
    setSending(false);
    editorRef.current?.focus();
  };

  /* ── add note ── */
  const handleAddNote = async () => {
    if (!crmData?.contact_id || !noteText.trim()) return;
    try {
      const n = await telegramOutreachApi.addCrmContactNote(crmData.contact_id, noteText.trim());
      setCrmData(prev => prev ? { ...prev, notes: [n, ...prev.notes] } : prev);
      setNoteText('');
    } catch { /* silent */ }
  };

  /* ── group messages by date ── */
  const groupedMessages = (() => {
    const groups: { date: string; msgs: InboxMessage[] }[] = [];
    let lastDate = '';
    for (const msg of messages) {
      const d = msg.sent_at ? new Date(msg.sent_at).toDateString() : 'Unknown';
      if (d !== lastDate) {
        groups.push({ date: msg.sent_at || '', msgs: [] });
        lastDate = d;
      }
      groups[groups.length - 1].msgs.push(msg);
    }
    return groups;
  })();

  /* ── colors ── */
  const bubbleOut = isDark ? '#2B5278' : '#EFFDDE';
  const bubbleOutText = isDark ? '#E1E3E6' : '#000000';
  const bubbleIn = isDark ? '#212121' : '#FFFFFF';
  const bubbleInText = isDark ? '#E1E3E6' : '#000000';
  const chatBg = isDark ? '#0E1621' : '#E6EBEE';
  const dialogListBg = isDark ? '#17212B' : '#FFFFFF';
  const dialogActive = isDark ? '#2B5278' : '#419FD9';
  const dialogHover = isDark ? '#202B36' : '#F4F4F5';
  const headerBg = isDark ? '#17212B' : '#FFFFFF';
  const crmBg = isDark ? '#17212B' : '#FFFFFF';
  const borderColor = isDark ? '#0E1621' : '#E6E6E6';
  const searchBg = isDark ? '#242F3D' : '#F0F2F5';
  const timeColor = isDark ? '#6D7F8F' : '#8E9BA7';

  return (
    <div className="h-full flex" style={{ background: chatBg }}>
      {/* ═══════════ COLUMN 1: DIALOGS ═══════════ */}
      <div
        className="flex flex-col flex-shrink-0"
        style={{ width: 320, background: dialogListBg, borderRight: `1px solid ${borderColor}` }}
      >
        {/* Header + search */}
        <div className="px-3 pt-3 pb-2" style={{ borderBottom: `1px solid ${borderColor}` }}>
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-base font-semibold flex-1" style={{ color: t.text1 }}>Inbox</h2>
            <Link
              to="/outreach/inbox"
              className="text-[11px] px-2 py-0.5 rounded transition-colors"
              style={{ background: isDark ? '#242F3D' : '#F0F2F5', color: t.text4 }}
            >
              Classic
            </Link>
          </div>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: t.text5 }} />
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 rounded-lg text-xs outline-none"
              style={{ background: searchBg, color: t.text1 }}
            />
          </div>
          {/* Tag filters */}
          <div className="flex gap-1 mt-2 overflow-x-auto pb-0.5">
            {['', 'interested', 'not_interested', 'meeting_booked', 'follow_up'].map(tag => (
              <button
                key={tag}
                onClick={() => setFilterTag(tag)}
                className="px-2 py-0.5 rounded-full text-[10px] font-medium whitespace-nowrap transition-colors"
                style={{
                  background: filterTag === tag ? (isDark ? '#2B5278' : '#419FD9') : (isDark ? '#242F3D' : '#F0F2F5'),
                  color: filterTag === tag ? '#fff' : t.text3,
                }}
              >
                {tag === '' ? 'All' : tag.replace('_', ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Dialog list */}
        <div className="flex-1 overflow-y-auto">
          {loading.dialogs && dialogs.length === 0 && (
            <div className="flex justify-center py-12">
              <Loader2 className="w-5 h-5 animate-spin" style={{ color: t.text4 }} />
            </div>
          )}
          {dialogs.map(d => {
            const isActive = selectedDialog?.id === d.id;
            return (
              <div
                key={d.id}
                onClick={() => selectDialog(d)}
                className="flex items-center gap-3 px-3 py-2 cursor-pointer transition-colors"
                style={{
                  background: isActive ? dialogActive : 'transparent',
                }}
                onMouseEnter={e => { if (!isActive) (e.currentTarget as HTMLElement).style.background = dialogHover; }}
                onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
              >
                <Avatar name={d.peer_name || 'U'} size={46} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span
                      className="text-[13px] font-medium truncate"
                      style={{ color: isActive ? '#fff' : t.text1 }}
                    >
                      {d.peer_name}
                    </span>
                    <span className="text-[11px] flex-shrink-0 ml-1" style={{ color: isActive ? 'rgba(255,255,255,0.6)' : timeColor }}>
                      {formatTime(d.last_message_at)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between mt-0.5">
                    <span
                      className="text-xs truncate"
                      style={{ color: isActive ? 'rgba(255,255,255,0.7)' : t.text4 }}
                    >
                      {d.last_direction === 'outbound' && (
                        <span style={{ color: isActive ? 'rgba(255,255,255,0.5)' : t.text5 }}>You: </span>
                      )}
                      {d.last_message || 'No messages'}
                    </span>
                    <div className="flex items-center gap-1 ml-1 flex-shrink-0">
                      {d.tag && (
                        <span
                          className="w-2 h-2 rounded-full"
                          style={{ background: TAG_COLORS[d.tag] || t.text5 }}
                          title={d.tag}
                        />
                      )}
                      {d.unread_count > 0 && (
                        <span
                          className="text-[10px] min-w-[18px] h-[18px] px-1 rounded-full font-bold flex items-center justify-center text-white"
                          style={{ background: '#3390EC' }}
                        >
                          {d.unread_count}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
          {!loading.dialogs && dialogs.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12" style={{ color: t.text4 }}>
              <MessageCircle className="w-10 h-10 mb-2 opacity-30" />
              <span className="text-sm">No conversations</span>
            </div>
          )}
        </div>
      </div>

      {/* ═══════════ COLUMN 2: CHAT ═══════════ */}
      <div className="flex-1 flex flex-col min-w-0">
        {selectedDialog ? (
          <>
            {/* Chat header */}
            <div
              className="flex items-center gap-3 px-4 py-2 flex-shrink-0"
              style={{ background: headerBg, borderBottom: `1px solid ${borderColor}` }}
            >
              <Avatar name={selectedDialog.peer_name || 'U'} size={36} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate" style={{ color: t.text1 }}>
                  {selectedDialog.peer_name}
                </div>
                <div className="text-[11px]" style={{ color: t.text4 }}>
                  {selectedDialog.peer_username ? `@${selectedDialog.peer_username}` : `via ${selectedDialog.account_username || selectedDialog.account_phone}`}
                </div>
              </div>
              <div className="flex items-center gap-1">
                {selectedDialog.tag && (
                  <span
                    className="text-[10px] px-2 py-0.5 rounded-full font-medium"
                    style={{ background: TAG_COLORS[selectedDialog.tag] || t.text5, color: '#fff' }}
                  >
                    {selectedDialog.tag.replace('_', ' ')}
                  </span>
                )}
                <button
                  onClick={() => setShowCrm(!showCrm)}
                  className="p-1.5 rounded transition-colors"
                  style={{ color: t.text4 }}
                  onMouseEnter={e => (e.currentTarget.style.background = isDark ? '#242F3D' : '#F0F2F5')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  title={showCrm ? 'Hide CRM panel' : 'Show CRM panel'}
                >
                  {showCrm ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Messages area */}
            <div
              className="flex-1 overflow-y-auto px-4 py-3"
              style={{ background: chatBg }}
            >
              {loading.messages && messages.length === 0 && (
                <div className="flex justify-center py-12">
                  <Loader2 className="w-5 h-5 animate-spin" style={{ color: t.text4 }} />
                </div>
              )}
              {groupedMessages.map((group, gi) => (
                <div key={gi}>
                  {/* Date separator */}
                  {group.date && (
                    <div className="flex justify-center my-3">
                      <span
                        className="text-[11px] px-3 py-1 rounded-full font-medium"
                        style={{
                          background: isDark ? 'rgba(0,0,0,0.35)' : 'rgba(0,0,0,0.08)',
                          color: isDark ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.45)',
                        }}
                      >
                        {formatDateSeparator(group.date)}
                      </span>
                    </div>
                  )}
                  {/* Messages */}
                  {group.msgs.map(msg => (
                    <div
                      key={msg.id}
                      className={`flex mb-1 ${msg.direction === 'outbound' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className="max-w-[55%] px-2.5 py-1.5 relative"
                        style={{
                          background: msg.direction === 'outbound' ? bubbleOut : bubbleIn,
                          color: msg.direction === 'outbound' ? bubbleOutText : bubbleInText,
                          borderRadius: msg.direction === 'outbound'
                            ? '12px 12px 4px 12px'
                            : '12px 12px 12px 4px',
                          boxShadow: isDark ? 'none' : '0 1px 2px rgba(0,0,0,0.08)',
                        }}
                      >
                        <div className="text-[13px] whitespace-pre-wrap break-words leading-[1.35]">
                          {msg.text}
                        </div>
                        <div className="flex items-center justify-end gap-1 mt-0.5 -mb-0.5">
                          <span className="text-[10px]" style={{ color: timeColor }}>
                            {formatMessageTime(msg.sent_at)}
                          </span>
                          {msg.direction === 'outbound' && (
                            <span className="text-[10px]" style={{ color: msg.is_read ? '#53BDEB' : timeColor }}>
                              {msg.is_read ? '\u2713\u2713' : '\u2713'}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            <div
              className="px-3 py-2 flex items-end gap-2 flex-shrink-0"
              style={{ background: headerBg, borderTop: `1px solid ${borderColor}` }}
            >
              <textarea
                ref={editorRef}
                value={messageText}
                onChange={e => setMessageText(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Message"
                rows={1}
                className="flex-1 resize-none px-3 py-2 rounded-xl text-sm outline-none"
                style={{
                  background: searchBg,
                  color: t.text1,
                  maxHeight: 120,
                  minHeight: 36,
                }}
              />
              <button
                onClick={handleSend}
                disabled={sending || !messageText.trim()}
                className="p-2 rounded-full transition-colors disabled:opacity-40"
                style={{ background: '#3390EC', color: '#fff' }}
              >
                {sending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
          </>
        ) : (
          /* Empty state */
          <div className="flex-1 flex flex-col items-center justify-center" style={{ color: t.text4 }}>
            <div
              className="w-24 h-24 rounded-full flex items-center justify-center mb-4"
              style={{ background: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)' }}
            >
              <MessageCircle className="w-12 h-12 opacity-30" />
            </div>
            <div className="text-lg font-medium mb-1">Select a chat</div>
            <div className="text-sm" style={{ color: t.text5 }}>
              {dialogs.length} conversations
            </div>
          </div>
        )}
      </div>

      {/* ═══════════ COLUMN 3: CRM CARD ═══════════ */}
      {showCrm && selectedDialog && (
        <div
          className="flex flex-col flex-shrink-0 overflow-y-auto"
          style={{ width: 340, background: crmBg, borderLeft: `1px solid ${borderColor}` }}
        >
          {/* CRM header */}
          <div className="flex flex-col items-center pt-6 pb-4 px-4" style={{ borderBottom: `1px solid ${borderColor}` }}>
            <Avatar name={selectedDialog.peer_name || 'U'} size={72} />
            <div className="text-base font-semibold mt-3" style={{ color: t.text1 }}>
              {selectedDialog.peer_name}
            </div>
            {selectedDialog.peer_username && (
              <div className="text-xs mt-0.5" style={{ color: t.text4 }}>
                @{selectedDialog.peer_username}
              </div>
            )}
            {crmData?.company && (
              <div className="text-xs mt-1" style={{ color: t.text3 }}>
                {crmData.company}
              </div>
            )}
          </div>

          {crmLoading && (
            <div className="flex justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin" style={{ color: t.text4 }} />
            </div>
          )}

          {crmData && !crmLoading && (
            <div className="flex-1">
              {/* Status & Tags */}
              <div className="px-4 py-3" style={{ borderBottom: `1px solid ${borderColor}` }}>
                <div className="flex items-center gap-2 mb-2">
                  <Tag className="w-3.5 h-3.5" style={{ color: t.text4 }} />
                  <span className="text-xs font-medium" style={{ color: t.text3 }}>Status</span>
                </div>
                <span
                  className="text-xs px-2 py-0.5 rounded-full font-medium capitalize"
                  style={{
                    background: crmData.status ? (TAG_COLORS[crmData.status] || t.text5) : t.badgeBg,
                    color: crmData.status ? '#fff' : t.text4,
                  }}
                >
                  {(crmData.status || 'new').replace('_', ' ')}
                </span>
                {crmData.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {crmData.tags.map((tag, i) => (
                      <span key={i} className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: t.badgeBg, color: t.text3 }}>
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Account info */}
              <div className="px-4 py-3" style={{ borderBottom: `1px solid ${borderColor}` }}>
                <div className="flex items-center gap-2 mb-2">
                  <User className="w-3.5 h-3.5" style={{ color: t.text4 }} />
                  <span className="text-xs font-medium" style={{ color: t.text3 }}>Sender Account</span>
                </div>
                <div className="text-xs" style={{ color: t.text1 }}>
                  {selectedDialog.account_username ? `@${selectedDialog.account_username}` : selectedDialog.account_phone}
                </div>
              </div>

              {/* Campaign history */}
              {crmData.campaigns.length > 0 && (
                <div className="px-4 py-3" style={{ borderBottom: `1px solid ${borderColor}` }}>
                  <div className="flex items-center gap-2 mb-2">
                    <Hash className="w-3.5 h-3.5" style={{ color: t.text4 }} />
                    <span className="text-xs font-medium" style={{ color: t.text3 }}>Campaigns</span>
                  </div>
                  <div className="space-y-1.5">
                    {crmData.campaigns.map((c, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="truncate" style={{ color: t.text1 }}>{c.name}</span>
                        <span className="flex-shrink-0 ml-2" style={{ color: t.text5 }}>
                          Step {c.step} &middot; {formatTime(c.sent_at)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Notes */}
              <div className="px-4 py-3" style={{ borderBottom: `1px solid ${borderColor}` }}>
                <div className="flex items-center gap-2 mb-2">
                  <StickyNote className="w-3.5 h-3.5" style={{ color: t.text4 }} />
                  <span className="text-xs font-medium" style={{ color: t.text3 }}>Notes</span>
                </div>
                <div className="flex gap-1 mb-2">
                  <input
                    type="text"
                    value={noteText}
                    onChange={e => setNoteText(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') handleAddNote(); }}
                    placeholder="Add a note..."
                    className="flex-1 px-2 py-1 rounded text-xs outline-none"
                    style={{ background: searchBg, color: t.text1 }}
                  />
                  <button
                    onClick={handleAddNote}
                    disabled={!noteText.trim()}
                    className="px-2 py-1 rounded text-xs font-medium disabled:opacity-40"
                    style={{ background: '#3390EC', color: '#fff' }}
                  >
                    Add
                  </button>
                </div>
                {crmData.notes.length > 0 && (
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {crmData.notes.map(n => (
                      <div key={n.id} className="text-xs px-2 py-1.5 rounded" style={{ background: isDark ? '#1C2733' : '#F5F5F5' }}>
                        <div style={{ color: t.text1 }}>{n.text}</div>
                        <div className="mt-0.5" style={{ color: t.text5 }}>
                          {n.author} &middot; {formatTime(n.created_at)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                {crmData.notes.length === 0 && (
                  <div className="text-[11px]" style={{ color: t.text5 }}>No notes yet</div>
                )}
              </div>
            </div>
          )}

          {!crmData && !crmLoading && (
            <div className="flex-1 flex items-center justify-center px-4">
              <div className="text-center">
                <User className="w-8 h-8 mx-auto mb-2 opacity-20" style={{ color: t.text4 }} />
                <div className="text-xs" style={{ color: t.text5 }}>No CRM data for this contact</div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
