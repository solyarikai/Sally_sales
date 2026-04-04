import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Search, Send, Loader2, MessageCircle, User, ChevronRight, ChevronLeft,
  Tag, Hash, StickyNote, FileText, Download, X, Plus, Paperclip,
  Pencil, Copy, Trash2, Reply, CornerUpRight,
} from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { telegramOutreachApi } from '../api/telegramOutreach';
import { getAccounts } from '../api/telegram';
import type { TelegramDMAccount } from '../api/telegram';
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

interface MessageEntity {
  type: 'bold' | 'italic' | 'code' | 'pre' | 'url' | 'text_url' | 'mention' | 'strikethrough' | 'underline' | 'spoiler';
  offset: number;
  length: number;
  url?: string;
  language?: string;
}

interface MediaInfo {
  type: 'photo' | 'video' | 'voice' | 'sticker' | 'video_note' | 'document' | 'gif';
  duration?: number;
  file_name?: string;
  size?: number;
  mime_type?: string;
}

interface InboxMessage {
  id: number;
  direction: 'inbound' | 'outbound';
  text: string;
  sent_at: string | null;
  sender_name: string;
  is_read: boolean;
  media?: MediaInfo | null;
  reply_to_id?: number | null;
  reply_to?: { msg_id: number; text: string; sender_name: string } | null;
  entities?: MessageEntity[];
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

/* ─────────── formatted text renderer ─────────── */
function renderFormattedText(text: string, entities?: MessageEntity[]): React.ReactNode {
  if (!entities || entities.length === 0) return text;

  // Sort entities by offset, then by length descending (longer first for nesting)
  const sorted = [...entities].sort((a, b) => a.offset - b.offset || b.length - a.length);

  const parts: React.ReactNode[] = [];
  let cursor = 0;

  for (let i = 0; i < sorted.length; i++) {
    const ent = sorted[i];
    // Skip entities that overlap with already-processed text
    if (ent.offset < cursor) continue;

    // Add plain text before this entity
    if (ent.offset > cursor) {
      parts.push(text.slice(cursor, ent.offset));
    }

    const entityText = text.slice(ent.offset, ent.offset + ent.length);

    switch (ent.type) {
      case 'bold':
        parts.push(<strong key={i}>{entityText}</strong>);
        break;
      case 'italic':
        parts.push(<em key={i}>{entityText}</em>);
        break;
      case 'code':
        parts.push(
          <code key={i} className="bg-black/10 dark:bg-white/10 px-1 py-0.5 rounded text-[12px] font-mono">
            {entityText}
          </code>
        );
        break;
      case 'pre':
        parts.push(
          <pre key={i} className="bg-black/10 dark:bg-white/10 p-2 rounded text-[12px] font-mono overflow-x-auto my-1">
            <code>{entityText}</code>
          </pre>
        );
        break;
      case 'url':
        parts.push(
          <a key={i} href={entityText} target="_blank" rel="noopener noreferrer"
            className="underline opacity-90 hover:opacity-100">{entityText}</a>
        );
        break;
      case 'text_url':
        parts.push(
          <a key={i} href={ent.url} target="_blank" rel="noopener noreferrer"
            className="underline opacity-90 hover:opacity-100">{entityText}</a>
        );
        break;
      case 'mention':
        parts.push(
          <span key={i} className="font-medium opacity-90">{entityText}</span>
        );
        break;
      case 'strikethrough':
        parts.push(<s key={i}>{entityText}</s>);
        break;
      case 'underline':
        parts.push(<u key={i}>{entityText}</u>);
        break;
      case 'spoiler':
        parts.push(
          <span key={i} className="bg-current rounded px-0.5 hover:bg-transparent transition-colors cursor-pointer"
            onClick={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}>
            {entityText}
          </span>
        );
        break;
      default:
        parts.push(entityText);
    }

    cursor = ent.offset + ent.length;
  }

  // Add remaining text after last entity
  if (cursor < text.length) {
    parts.push(text.slice(cursor));
  }

  return <>{parts}</>;
}

/* ─────────── SVG check marks (Telegram-style) ─────────── */
function CheckMark({ read, className }: { read: boolean; className?: string }) {
  if (read) {
    // Double check — two overlapping ticks
    return (
      <svg className={className} width="16" height="11" viewBox="0 0 16 11" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M11.5 0.5L5.5 7.5L3 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M14.5 0.5L8.5 7.5L7.5 6.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  }
  // Single check
  return (
    <svg className={className} width="12" height="11" viewBox="0 0 12 11" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M10.5 0.5L4.5 7.5L1.5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ─────────── Voice player with waveform bars ─────────── */
function VoicePlayer({ src, duration, isOut }: { src: string; duration?: number; isOut: boolean }) {
  const [playing, setPlaying] = React.useState(false);
  const [progress, setProgress] = React.useState(0);
  const [currentTime, setCurrentTime] = React.useState(0);
  const audioRef = React.useRef<HTMLAudioElement>(null);
  const barsRef = React.useRef<number[]>([]);

  // Generate deterministic waveform bars on mount
  if (barsRef.current.length === 0) {
    const seed = (duration || 5) * 1000;
    for (let i = 0; i < 32; i++) {
      const val = Math.abs(Math.sin(seed * (i + 1) * 0.3 + i * 0.7)) * 0.7 + 0.3;
      barsRef.current.push(val);
    }
  }

  const toggle = () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (playing) { audio.pause(); } else { audio.play(); }
    setPlaying(!playing);
  };

  const handleTimeUpdate = () => {
    const audio = audioRef.current;
    if (!audio || !audio.duration) return;
    setProgress(audio.currentTime / audio.duration);
    setCurrentTime(audio.currentTime);
  };

  const handleEnded = () => { setPlaying(false); setProgress(0); setCurrentTime(0); };

  const handleBarClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current;
    if (!audio || !audio.duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    audio.currentTime = pct * audio.duration;
    setProgress(pct);
  };

  const accentColor = isOut ? '#78c272' : '#3390EC';
  const barInactive = isOut ? 'rgba(255,255,255,0.35)' : 'rgba(0,0,0,0.15)';
  const displayTime = playing || currentTime > 0
    ? formatDuration(Math.floor(currentTime))
    : (duration != null ? formatDuration(duration) : '0:00');

  return (
    <div className="tg-voice-player">
      <audio ref={audioRef} src={src} preload="metadata" onTimeUpdate={handleTimeUpdate} onEnded={handleEnded} />
      <button onClick={toggle} className="tg-voice-play-btn" style={{ color: accentColor }}>
        {playing ? (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="3" y="2" width="3.5" height="12" rx="1" /><rect x="9.5" y="2" width="3.5" height="12" rx="1" /></svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M4 2.5v11l9-5.5z" /></svg>
        )}
      </button>
      <div className="tg-voice-waveform" onClick={handleBarClick}>
        {barsRef.current.map((h, i) => {
          const filled = i / barsRef.current.length < progress;
          return (
            <div
              key={i}
              className="tg-voice-bar"
              style={{
                height: `${h * 100}%`,
                background: filled ? accentColor : barInactive,
              }}
            />
          );
        })}
      </div>
      <span className="tg-voice-time" style={{ color: isOut ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.4)' }}>
        {displayTime}
      </span>
    </div>
  );
}

/* ─────────── media helpers ─────────── */
function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}


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
  const [filterAccountId, setFilterAccountId] = useState<number | ''>('');
  const [accounts, setAccounts] = useState<TelegramDMAccount[]>([]);
  const [loading, setLoading] = useState({ dialogs: true, messages: false });
  const [crmData, setCrmData] = useState<CrmInfo | null>(null);
  const [crmLoading, setCrmLoading] = useState(false);
  const [showCrm, setShowCrm] = useState(true);
  const [noteText, setNoteText] = useState('');
  const [customFieldDefs, setCustomFieldDefs] = useState<any[]>([]);
  const [contactFieldVals, setContactFieldVals] = useState<any[]>([]);
  const [lightboxUrl, setLightboxUrl] = useState<string | null>(null);
  const [showNewChat, setShowNewChat] = useState(false);
  const [newChatUsername, setNewChatUsername] = useState('');
  const [newChatAccountId, setNewChatAccountId] = useState<number | ''>('');
  const [newChatLoading, setNewChatLoading] = useState(false);
  const [newChatError, setNewChatError] = useState('');

  /* ── context menu & edit/reply state ── */
  const [ctxMenu, setCtxMenu] = useState<{ x: number; y: number; msg: InboxMessage } | null>(null);
  const [editingMsg, setEditingMsg] = useState<{ id: number; originalText: string } | null>(null);
  const [replyTo, setReplyTo] = useState<InboxMessage | null>(null);
  const [forwardPopup, setForwardPopup] = useState<{ msgIds: number[] } | null>(null);
  const [forwardSearch, setForwardSearch] = useState('');

  const [msgError, setMsgError] = useState<string | null>(null);
  const [peerTyping, setPeerTyping] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [hasOlderMessages, setHasOlderMessages] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const dialogPollRef = useRef(false);
  const msgPollRef = useRef(false);
  const prevMsgCount = useRef(0);
  const msgErrorCount = useRef(0);
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /* ── load accounts + custom field defs ── */
  useEffect(() => {
    getAccounts().then(setAccounts).catch(() => {});
    telegramOutreachApi.listCustomFields(currentProject?.id).then(setCustomFieldDefs).catch(() => {});
  }, [currentProject?.id]);

  /* ── load dialogs ── */
  const loadDialogs = useCallback(async (silent = false) => {
    if (dialogPollRef.current) return;
    dialogPollRef.current = true;
    if (!silent) setLoading(l => ({ ...l, dialogs: true }));
    try {
      const params: any = { page_size: 100 };
      if (search) params.search = search;
      if (filterTag) params.tag = filterTag;
      if (filterAccountId) params.account_id = filterAccountId;
      if (currentProject?.id) params.project_id = currentProject.id;
      const data = await telegramOutreachApi.listInboxDialogs(params);
      setDialogs(data.items || data.dialogs || data || []);
    } catch { /* silent */ }
    if (!silent) setLoading(l => ({ ...l, dialogs: false }));
    dialogPollRef.current = false;
  }, [search, filterTag, filterAccountId, currentProject?.id]);

  useEffect(() => { loadDialogs(); }, [loadDialogs]);

  // Poll dialogs every 12s
  useEffect(() => {
    const iv = setInterval(() => loadDialogs(true), 12000);
    return () => clearInterval(iv);
  }, [loadDialogs]);

  /* ── load messages ── */
  const MSG_PAGE_SIZE = 50;
  const loadMessages = useCallback(async (dialogId: number, silent = false) => {
    if (msgPollRef.current) return;
    msgPollRef.current = true;
    if (!silent) setLoading(l => ({ ...l, messages: true }));
    try {
      const data = await telegramOutreachApi.getDialogMessages(dialogId, MSG_PAGE_SIZE);
      const msgs = data.messages || data || [];
      setMessages(msgs);
      setHasOlderMessages(msgs.length >= MSG_PAGE_SIZE);
      msgErrorCount.current = 0;
      setMsgError(null);
    } catch (e: any) {
      msgErrorCount.current++;
      // Show error only after 3 consecutive failures (avoid flashing on single blip)
      if (msgErrorCount.current >= 3) {
        const detail = e?.response?.data?.detail || 'Connection lost — retrying…';
        setMsgError(typeof detail === 'string' ? detail : 'Failed to load messages');
      }
    }
    if (!silent) setLoading(l => ({ ...l, messages: false }));
    msgPollRef.current = false;
  }, []);

  /* ── load older messages (scroll-up pagination) ── */
  const loadOlderMessages = useCallback(async () => {
    if (!selectedDialog || loadingOlder || !hasOlderMessages || messages.length === 0) return;
    const oldestId = Math.min(...messages.map(m => m.id));
    setLoadingOlder(true);
    try {
      const data = await telegramOutreachApi.getDialogMessages(selectedDialog.id, MSG_PAGE_SIZE, oldestId);
      const older = data.messages || data || [];
      if (older.length === 0) {
        setHasOlderMessages(false);
      } else {
        // Preserve scroll position: measure before prepending
        const container = messagesContainerRef.current;
        const prevScrollHeight = container?.scrollHeight || 0;
        const existingIds = new Set(messages.map(m => m.id));
        const newMsgs = older.filter((m: InboxMessage) => !existingIds.has(m.id));
        setMessages(prev => [...newMsgs, ...prev]);
        setHasOlderMessages(older.length >= MSG_PAGE_SIZE);
        // Restore scroll position after DOM update
        requestAnimationFrame(() => {
          if (container) {
            container.scrollTop = container.scrollHeight - prevScrollHeight;
          }
        });
      }
    } catch { /* silent */ }
    setLoadingOlder(false);
  }, [selectedDialog, loadingOlder, hasOlderMessages, messages]);

  // On dialog select
  const selectDialog = useCallback((d: InboxDialog) => {
    setSelectedDialog(d);
    setMessages([]);
    setCrmData(null);
    setMsgError(null);
    setHasOlderMessages(true);
    msgErrorCount.current = 0;
    prevMsgCount.current = 0;
    loadMessages(d.id);
    // Load CRM
    setCrmLoading(true);
    setContactFieldVals([]);
    telegramOutreachApi.getDialogCrm(d.id)
      .then((data: any) => {
        setCrmData(data);
        if (data?.contact_id) {
          telegramOutreachApi.getContactCustomFields(data.contact_id)
            .then(setContactFieldVals).catch(() => {});
        }
      })
      .catch(() => setCrmData(null))
      .finally(() => setCrmLoading(false));
  }, [loadMessages]);

  // Poll messages every 6s
  useEffect(() => {
    if (!selectedDialog) return;
    const iv = setInterval(() => loadMessages(selectedDialog.id, true), 6000);
    return () => clearInterval(iv);
  }, [selectedDialog?.id, loadMessages]);

  // Poll typing status every 3s
  useEffect(() => {
    if (!selectedDialog) { setPeerTyping(false); return; }
    setPeerTyping(false);
    const interval = setInterval(async () => {
      try {
        const data = await telegramOutreachApi.getDialogTyping(selectedDialog.id);
        setPeerTyping(data.typing);
      } catch { setPeerTyping(false); }
    }, 3_000);
    return () => { clearInterval(interval); setPeerTyping(false); };
  }, [selectedDialog?.id]);

  // Auto-scroll on new messages
  useEffect(() => {
    if (messages.length > prevMsgCount.current || prevMsgCount.current === 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
    prevMsgCount.current = messages.length;
  }, [messages]);

  /* ── send / edit message ── */
  const handleSend = async () => {
    if (!selectedDialog || !messageText.trim()) return;
    setSending(true);
    try {
      if (editingMsg) {
        await telegramOutreachApi.editDialogMessage(selectedDialog.id, editingMsg.id, messageText.trim());
        setEditingMsg(null);
      } else {
        await telegramOutreachApi.sendDialogMessage(selectedDialog.id, messageText.trim(), {
          replyTo: replyTo?.id,
        });
        setReplyTo(null);
      }
      setMessageText('');
      await loadMessages(selectedDialog.id, true);
    } catch { /* error handled by API client toast */ }
    setSending(false);
    editorRef.current?.focus();
  };

  /* ── send file attachment ── */
  const handleFileAttach = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedDialog) return;
    setSending(true);
    try {
      await telegramOutreachApi.sendDialogFile(selectedDialog.id, file, {
        caption: messageText.trim() || undefined,
        replyTo: replyTo?.id,
      });
      setMessageText('');
      setReplyTo(null);
      await loadMessages(selectedDialog.id, true);
    } catch { /* error handled by API client toast */ }
    setSending(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
    editorRef.current?.focus();
  };

  /* ── context menu actions ── */
  const handleContextMenu = (e: React.MouseEvent, msg: InboxMessage) => {
    e.preventDefault();
    setCtxMenu({ x: e.clientX, y: e.clientY, msg });
  };

  const handleReplyTo = (msg: InboxMessage) => {
    setEditingMsg(null);
    setReplyTo(msg);
    setCtxMenu(null);
    editorRef.current?.focus();
  };

  const handleEditStart = (msg: InboxMessage) => {
    setReplyTo(null);
    setEditingMsg({ id: msg.id, originalText: msg.text });
    setMessageText(msg.text);
    setCtxMenu(null);
    editorRef.current?.focus();
  };

  const handleCancelEdit = () => {
    setEditingMsg(null);
    setMessageText('');
  };

  const handleCopyText = (msg: InboxMessage) => {
    navigator.clipboard.writeText(msg.text).catch(() => {});
    setCtxMenu(null);
  };

  const handleDeleteMsg = async (msg: InboxMessage) => {
    if (!selectedDialog) return;
    setCtxMenu(null);
    try {
      await telegramOutreachApi.deleteDialogMessage(selectedDialog.id, msg.id, true);
      await loadMessages(selectedDialog.id, true);
    } catch { /* error handled by API client toast */ }
  };

  // Close context menu on click outside or Escape
  useEffect(() => {
    if (!ctxMenu) return;
    const close = () => setCtxMenu(null);
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setCtxMenu(null); };
    document.addEventListener('click', close);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('click', close); document.removeEventListener('keydown', esc); };
  }, [ctxMenu]);

  // Clear edit/reply when dialog changes
  useEffect(() => {
    setEditingMsg(null);
    setReplyTo(null);
    setMessageText('');
  }, [selectedDialog?.id]);

  /* ── add note ── */
  const handleAddNote = async () => {
    if (!crmData?.contact_id || !noteText.trim()) return;
    try {
      const n = await telegramOutreachApi.addCrmContactNote(crmData.contact_id, noteText.trim());
      setCrmData(prev => prev ? { ...prev, notes: [n, ...prev.notes] } : prev);
      setNoteText('');
    } catch { /* silent */ }
  };

  /* ── new chat ── */
  const handleNewChat = async () => {
    if (!newChatAccountId || !newChatUsername.trim()) return;
    setNewChatLoading(true);
    setNewChatError('');
    try {
      const result = await telegramOutreachApi.createNewChat(Number(newChatAccountId), newChatUsername.trim());
      setShowNewChat(false);
      setNewChatUsername('');
      setNewChatAccountId('');
      await loadDialogs();
      // Auto-select the new dialog
      if (result?.id) {
        const d: InboxDialog = {
          id: result.id,
          peer_id: result.peer_id,
          peer_name: result.peer_name || result.peer_username || 'Unknown',
          peer_username: result.peer_username,
          account_id: result.account_id,
          account_phone: '',
          account_username: null,
          last_message: result.last_message_text || null,
          last_message_at: result.last_message_at || null,
          last_direction: null,
          unread_count: 0,
          tag: result.tag || null,
          campaign_name: null,
          lead_status: null,
        };
        selectDialog(d);
      }
    } catch (err: any) {
      setNewChatError(err?.response?.data?.detail || err?.userMessage || 'Failed to create chat');
    }
    setNewChatLoading(false);
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

  /* ── colors (remaining inline ones — most now handled by CSS classes) ── */
  const dialogListBg = isDark ? '#17212B' : '#FFFFFF';
  const crmBg = isDark ? '#17212B' : '#FFFFFF';
  const borderColor = isDark ? '#0E1621' : '#E6E6E6';
  const searchBg = isDark ? '#242F3D' : '#F0F2F5';
  const timeColor = isDark ? '#6D7F8F' : '#8E9BA7';

  return (
    <div className="h-full flex tg-chat-bg">
      {/* ═══════════ COLUMN 1: DIALOGS ═══════════ */}
      <div
        className="flex flex-col flex-shrink-0"
        style={{ width: 320, background: dialogListBg, borderRight: `1px solid ${borderColor}` }}
      >
        {/* Header + search */}
        <div className="px-3 pt-3 pb-2" style={{ borderBottom: `1px solid ${borderColor}` }}>
          <div className="flex items-center gap-2 mb-2">
            <h2 className="text-base font-semibold flex-1" style={{ color: t.text1 }}>Inbox</h2>
            <button
              onClick={() => setShowNewChat(true)}
              className="p-1 rounded transition-colors"
              style={{ background: isDark ? '#242F3D' : '#F0F2F5', color: t.text4 }}
              title="New chat"
            >
              <Plus className="w-4 h-4" />
            </button>
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
          {/* Account filter */}
          {accounts.length > 0 && (
            <select
              value={filterAccountId}
              onChange={e => setFilterAccountId(e.target.value ? Number(e.target.value) : '')}
              className="w-full mt-2 px-2 py-1 rounded-lg text-xs outline-none appearance-none cursor-pointer"
              style={{ background: searchBg, color: t.text1, border: 'none' }}
            >
              <option value="">All accounts</option>
              {accounts.map(acc => (
                <option key={acc.id} value={acc.id}>
                  {acc.first_name || acc.username || acc.phone || `#${acc.id}`}
                  {acc.phone ? ` (${acc.phone})` : ''}
                </option>
              ))}
            </select>
          )}
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
                className={`tg-dialog-item ${isActive ? 'tg-dialog-item-active' : ''}`}
              >
                <Avatar name={d.peer_name || 'U'} size={48} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span
                      className="text-[13.5px] font-medium truncate"
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
                      className="text-[12.5px] truncate"
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
                        <span className="tg-unread-badge">{d.unread_count}</span>
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
              className="flex items-center gap-3 px-4 py-2 flex-shrink-0 tg-header"
            >
              <Avatar name={selectedDialog.peer_name || 'U'} size={36} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate" style={{ color: t.text1 }}>
                  {selectedDialog.peer_name}
                </div>
                <div className="text-[11px]" style={{ color: peerTyping ? '#22C55E' : t.text4 }}>
                  {peerTyping ? (
                    <span className="flex items-center gap-1">
                      <span className="flex gap-0.5">
                        <span className="w-1 h-1 rounded-full animate-bounce" style={{ background: '#22C55E', animationDelay: '0ms' }} />
                        <span className="w-1 h-1 rounded-full animate-bounce" style={{ background: '#22C55E', animationDelay: '150ms' }} />
                        <span className="w-1 h-1 rounded-full animate-bounce" style={{ background: '#22C55E', animationDelay: '300ms' }} />
                      </span>
                      typing...
                    </span>
                  ) : (
                    selectedDialog.peer_username ? `@${selectedDialog.peer_username}` : `via ${selectedDialog.account_username || selectedDialog.account_phone}`
                  )}
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
              ref={messagesContainerRef}
              className="flex-1 overflow-y-auto px-4 py-3 tg-chat-bg tg-chat-scroll"
              onScroll={(e) => {
                const el = e.currentTarget;
                if (el.scrollTop < 80 && hasOlderMessages && !loadingOlder) {
                  loadOlderMessages();
                }
              }}
            >
              {/* Load older indicator */}
              {loadingOlder && (
                <div className="flex justify-center py-2">
                  <Loader2 className="w-4 h-4 animate-spin" style={{ color: t.text4 }} />
                </div>
              )}
              {!hasOlderMessages && messages.length > 0 && (
                <div className="text-center py-2 text-xs" style={{ color: t.text5 }}>
                  Beginning of conversation
                </div>
              )}
              {loading.messages && messages.length === 0 && (
                <div className="flex justify-center py-12">
                  <Loader2 className="w-5 h-5 animate-spin" style={{ color: t.text4 }} />
                </div>
              )}
              {msgError && (
                <div className="flex items-center justify-center gap-2 py-2 px-3 mx-auto my-1 rounded-full text-xs max-w-fit"
                  style={{ background: 'rgba(239,68,68,0.12)', color: '#ef4444' }}>
                  <span>{msgError}</span>
                  <button className="underline opacity-80 hover:opacity-100"
                    onClick={() => { setMsgError(null); msgErrorCount.current = 0; selectedDialog && loadMessages(selectedDialog.id); }}>
                    Retry
                  </button>
                </div>
              )}
              {groupedMessages.map((group, gi) => (
                <div key={gi}>
                  {/* Date separator */}
                  {group.date && (
                    <div className="tg-date-sep">
                      <span>{formatDateSeparator(group.date)}</span>
                    </div>
                  )}
                  {/* Messages — grouped with tails */}
                  {group.msgs.map((msg, mi) => {
                    const isOut = msg.direction === 'outbound';
                    const next = group.msgs[mi + 1];
                    const sameDirNext = next && next.direction === msg.direction;
                    const isLast = !sameDirNext;
                    const spacing = isLast ? 'tg-bubble-group-last' : 'tg-bubble-group-mid';
                    const tail = isLast
                      ? (isOut ? 'tg-bubble-tail-out' : 'tg-bubble-tail-in')
                      : '';

                    return (
                      <div
                        key={msg.id}
                        className={`flex tg-msg-row ${spacing} ${isOut ? 'justify-end' : 'justify-start'}`}
                        style={{ paddingLeft: isOut ? 0 : (isLast ? 0 : 11), paddingRight: isOut ? (isLast ? 0 : 11) : 0 }}
                        onContextMenu={e => handleContextMenu(e, msg)}
                      >
                        <div className={`tg-bubble ${isOut ? 'tg-bubble-out' : 'tg-bubble-in'} ${tail} ${msg.media && !msg.text ? 'tg-bubble-media-only' : ''}`}>
                          {/* ── Reply-to preview ── */}
                          {msg.reply_to && (
                            <div className="tg-reply-preview" style={{
                              borderLeft: `2px solid ${isOut ? 'rgba(255,255,255,0.5)' : '#4fae4e'}`,
                              padding: '4px 8px', marginBottom: 4, borderRadius: 4,
                              background: isOut ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)',
                              fontSize: 12, lineHeight: '16px',
                            }}>
                              <div style={{ fontWeight: 600, color: isOut ? 'rgba(255,255,255,0.8)' : '#4fae4e' }}>
                                {msg.reply_to.sender_name}
                              </div>
                              <div style={{ opacity: 0.7, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 280 }}>
                                {msg.reply_to.text || 'Media'}
                              </div>
                            </div>
                          )}
                          {/* ── Media rendering ── */}
                          {msg.media && selectedDialog && (() => {
                            const mediaUrl = telegramOutreachApi.getDialogMediaUrl(selectedDialog.id, msg.id);
                            const m = msg.media;
                            switch (m.type) {
                              case 'photo':
                                return (
                                  <div className="tg-media-photo" onClick={() => setLightboxUrl(mediaUrl)}>
                                    <img src={mediaUrl} alt="" loading="lazy" />
                                  </div>
                                );
                              case 'video':
                              case 'video_note':
                                return (
                                  <div className={`tg-media-video ${m.type === 'video_note' ? 'tg-video-note' : ''}`}>
                                    <video src={mediaUrl} controls preload="metadata" />
                                  </div>
                                );
                              case 'gif':
                                return (
                                  <div className="tg-media-gif" onClick={() => setLightboxUrl(mediaUrl)}>
                                    <video src={mediaUrl} autoPlay loop muted playsInline />
                                    <span className="tg-gif-badge">GIF</span>
                                  </div>
                                );
                              case 'voice':
                                return (
                                  <VoicePlayer src={mediaUrl} duration={m.duration} isOut={isOut} />
                                );
                              case 'sticker':
                                return (
                                  <div className="tg-media-sticker">
                                    <img src={mediaUrl} alt="sticker" loading="lazy" />
                                  </div>
                                );
                              case 'document':
                                return (
                                  <a href={mediaUrl} download={m.file_name || 'file'} target="_blank" rel="noopener noreferrer" className="tg-media-doc">
                                    <FileText className="w-8 h-8 flex-shrink-0 opacity-70" />
                                    <div className="tg-doc-info">
                                      <span className="tg-doc-name">{m.file_name || 'File'}</span>
                                      {m.size != null && <span className="tg-doc-size">{formatFileSize(m.size)}</span>}
                                    </div>
                                    <Download className="w-4 h-4 flex-shrink-0 opacity-50" />
                                  </a>
                                );
                              default:
                                return null;
                            }
                          })()}
                          <span className={`tg-meta`}>
                            <span className={isOut ? 'tg-meta-time-out' : 'tg-meta-time'}>
                              {formatMessageTime(msg.sent_at)}
                            </span>
                            {isOut && (
                              <CheckMark read={msg.is_read} className="tg-meta-check" />
                            )}
                          </span>
                          {msg.text && renderFormattedText(msg.text, msg.entities)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
              {peerTyping && (
                <div className="flex justify-start">
                  <div className="flex items-center gap-1.5 px-3 py-2 rounded-2xl text-xs" style={{ background: isDark ? '#1C2733' : '#F5F5F5', border: `1px solid ${borderColor}` }}>
                    <span className="flex gap-0.5">
                      <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: t.text4, animationDelay: '0ms' }} />
                      <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: t.text4, animationDelay: '150ms' }} />
                      <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: t.text4, animationDelay: '300ms' }} />
                    </span>
                    <span style={{ color: t.text4 }}>typing</span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* ── Reply / Edit preview bar ── */}
            {(replyTo || editingMsg) && (
              <div className="flex items-center gap-2 px-4 py-2 tg-header" style={{ borderTop: `1px solid ${borderColor}`, borderBottom: 'none' }}>
                <div className="flex-shrink-0" style={{ color: '#4fae4e' }}>
                  {editingMsg ? <Pencil className="w-4 h-4" /> : <Reply className="w-4 h-4" />}
                </div>
                <div style={{ borderLeft: '2px solid #4fae4e', paddingLeft: 8, flex: 1, minWidth: 0 }}>
                  <div className="text-xs font-semibold" style={{ color: '#4fae4e' }}>
                    {editingMsg ? 'Editing message' : `Reply to ${replyTo?.sender_name}`}
                  </div>
                  <div className="text-xs truncate" style={{ color: t.text3 }}>
                    {editingMsg ? editingMsg.originalText : replyTo?.text || 'Media'}
                  </div>
                </div>
                <button
                  onClick={() => { editingMsg ? handleCancelEdit() : setReplyTo(null); }}
                  className="flex-shrink-0 p-1 rounded hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                  style={{ color: t.text4 }}
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}

            {/* Input area — Telegram-style composer */}
            <div className="tg-composer tg-header" style={{ borderTop: `1px solid ${borderColor}`, borderBottom: 'none' }}>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={handleFileAttach}
                accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.xls,.xlsx,.zip,.rar,.txt"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={sending}
                className="tg-attach-btn"
                title="Attach file"
              >
                <Paperclip className="w-[18px] h-[18px]" />
              </button>
              <textarea
                ref={editorRef}
                value={messageText}
                onChange={e => setMessageText(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                  if (e.key === 'Escape' && (editingMsg || replyTo)) {
                    editingMsg ? handleCancelEdit() : setReplyTo(null);
                  }
                }}
                placeholder={editingMsg ? 'Edit message...' : 'Message'}
                rows={1}
                className="tg-composer-input"
              />
              <button
                onClick={handleSend}
                disabled={sending || !messageText.trim()}
                className="tg-send-btn"
                title={editingMsg ? 'Save edit' : 'Send message'}
              >
                {sending ? (
                  <Loader2 className="w-[18px] h-[18px] animate-spin" />
                ) : editingMsg ? (
                  <Pencil className="w-[18px] h-[18px]" />
                ) : (
                  <Send className="w-[18px] h-[18px]" />
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
          className="flex flex-col flex-shrink-0 overflow-y-auto tg-crm-panel"
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
                {crmData.tags && crmData.tags.length > 0 && (
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
              {crmData.campaigns && crmData.campaigns.length > 0 && (
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

              {/* Custom Properties */}
              {customFieldDefs.length > 0 && crmData.contact_id && (
                <div className="px-4 py-3" style={{ borderBottom: `1px solid ${borderColor}` }}>
                  <div className="flex items-center gap-2 mb-2">
                    <FileText className="w-3.5 h-3.5" style={{ color: t.text4 }} />
                    <span className="text-xs font-medium" style={{ color: t.text3 }}>Properties</span>
                  </div>
                  <div className="space-y-2">
                    {customFieldDefs.map((fd: any) => {
                      const cv = contactFieldVals.find((v: any) => v.field_id === fd.id);
                      return (
                        <div key={fd.id}>
                          <label className="block text-[10px] font-medium mb-0.5" style={{ color: t.text4 }}>{fd.name}</label>
                          {fd.field_type === 'select' ? (
                            <select
                              className="w-full px-2 py-1 rounded border text-xs"
                              style={{ borderColor: borderColor, background: isDark ? '#1C2733' : '#F5F5F5', color: t.text1 }}
                              defaultValue={cv?.value || ''}
                              key={`${crmData.contact_id}-${fd.id}-${cv?.value}`}
                              onChange={async (e) => {
                                try {
                                  await telegramOutreachApi.updateContactCustomFields(crmData.contact_id!, [{ field_id: fd.id, value: e.target.value || null }]);
                                  setContactFieldVals(prev => {
                                    const idx = prev.findIndex((v: any) => v.field_id === fd.id);
                                    const val = { field_id: fd.id, value: e.target.value || null, field_name: fd.name, field_type: fd.field_type };
                                    return idx >= 0 ? prev.map((v: any, i: number) => i === idx ? { ...v, ...val } : v) : [...prev, val];
                                  });
                                } catch { /* */ }
                              }}
                            >
                              <option value="">--</option>
                              {(fd.options_json || []).map((o: string) => <option key={o} value={o}>{o}</option>)}
                            </select>
                          ) : fd.field_type === 'multi_select' ? (
                            <div className="flex flex-wrap gap-1">
                              {(fd.options_json || []).map((o: string) => {
                                const selected = (cv?.value || '').split(',').map((s: string) => s.trim()).includes(o);
                                return (
                                  <button key={o}
                                    className="text-[10px] px-1.5 py-0.5 rounded border transition-colors"
                                    style={{
                                      borderColor: selected ? '#3390EC' : borderColor,
                                      background: selected ? (isDark ? 'rgba(51,144,236,0.2)' : '#EBF3FE') : 'transparent',
                                      color: selected ? '#3390EC' : t.text3,
                                    }}
                                    onClick={async () => {
                                      const current = (cv?.value || '').split(',').map((s: string) => s.trim()).filter(Boolean);
                                      const next = selected ? current.filter((v: string) => v !== o) : [...current, o];
                                      const newVal = next.join(', ') || null;
                                      try {
                                        await telegramOutreachApi.updateContactCustomFields(crmData.contact_id!, [{ field_id: fd.id, value: newVal }]);
                                        setContactFieldVals(prev => {
                                          const idx = prev.findIndex((v: any) => v.field_id === fd.id);
                                          const val = { field_id: fd.id, value: newVal, field_name: fd.name, field_type: fd.field_type };
                                          return idx >= 0 ? prev.map((v: any, i: number) => i === idx ? { ...v, ...val } : v) : [...prev, val];
                                        });
                                      } catch { /* */ }
                                    }}
                                  >{o}</button>
                                );
                              })}
                            </div>
                          ) : (
                            <input
                              className="w-full px-2 py-1 rounded border text-xs outline-none"
                              style={{ borderColor: borderColor, background: isDark ? '#1C2733' : '#F5F5F5', color: t.text1 }}
                              type={fd.field_type === 'number' ? 'number' : fd.field_type === 'date' ? 'date' : fd.field_type === 'url' ? 'url' : 'text'}
                              defaultValue={cv?.value || ''}
                              key={`${crmData.contact_id}-${fd.id}-${cv?.value}`}
                              placeholder="--"
                              onBlur={async (e) => {
                                const newVal = e.target.value.trim() || null;
                                if (newVal === (cv?.value || null)) return;
                                try {
                                  await telegramOutreachApi.updateContactCustomFields(crmData.contact_id!, [{ field_id: fd.id, value: newVal }]);
                                  setContactFieldVals(prev => {
                                    const idx = prev.findIndex((v: any) => v.field_id === fd.id);
                                    const val = { field_id: fd.id, value: newVal, field_name: fd.name, field_type: fd.field_type };
                                    return idx >= 0 ? prev.map((v: any, i: number) => i === idx ? { ...v, ...val } : v) : [...prev, val];
                                  });
                                } catch { /* */ }
                              }}
                            />
                          )}
                        </div>
                      );
                    })}
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
                {crmData.notes && crmData.notes.length > 0 && (
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
                {(!crmData.notes || crmData.notes.length === 0) && (
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

      {/* ── Photo lightbox ── */}
      {lightboxUrl && (
        <div className="tg-lightbox" onClick={() => setLightboxUrl(null)}>
          <button className="tg-lightbox-close" onClick={() => setLightboxUrl(null)}>
            <X className="w-6 h-6" />
          </button>
          <img src={lightboxUrl} alt="" onClick={e => e.stopPropagation()} />
        </div>
      )}

      {/* ── Message context menu ── */}
      {ctxMenu && (
        <div
          className="fixed z-[100] py-1.5 rounded-xl min-w-[180px] tg-ctx-menu"
          style={{
            left: Math.min(ctxMenu.x, window.innerWidth - 200),
            top: Math.min(ctxMenu.y, window.innerHeight - 260),
            border: `1px solid ${isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'}`,
          }}
          onClick={e => e.stopPropagation()}
        >
          {[
            { icon: Reply, label: 'Reply', action: () => handleReplyTo(ctxMenu.msg), show: true },
            { icon: Pencil, label: 'Edit', action: () => handleEditStart(ctxMenu.msg), show: ctxMenu.msg.direction === 'outbound' && !!ctxMenu.msg.text },
            { icon: Copy, label: 'Copy Text', action: () => handleCopyText(ctxMenu.msg), show: !!ctxMenu.msg.text },
            { icon: CornerUpRight, label: 'Forward', action: () => { setForwardPopup({ msgIds: [ctxMenu.msg.id] }); setForwardSearch(''); setCtxMenu(null); }, show: true },
            { icon: Trash2, label: 'Delete', action: () => handleDeleteMsg(ctxMenu.msg), show: ctxMenu.msg.direction === 'outbound', danger: true },
          ].filter(item => item.show).map((item, i) => (
            <button
              key={i}
              onClick={item.action}
              className="flex items-center gap-3 w-full px-4 py-2 text-[13px] transition-colors"
              style={{
                color: (item as any).danger ? '#ef4444' : (isDark ? '#E1E3E6' : '#2C2C2C'),
              }}
              onMouseEnter={e => (e.currentTarget.style.background = isDark ? '#242F3D' : '#F0F2F5')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              <item.icon className="w-4 h-4 flex-shrink-0" style={{ opacity: 0.7 }} />
              {item.label}
            </button>
          ))}
        </div>
      )}

      {/* ── Forward dialog picker ── */}
      {forwardPopup && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.4)' }} onClick={() => setForwardPopup(null)}>
          <div
            className="rounded-xl shadow-xl w-[400px] flex flex-col"
            style={{ background: isDark ? '#1E2C3A' : '#fff', maxHeight: '70vh', overflow: 'hidden' }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ padding: '16px 20px', borderBottom: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}` }}>
              <h3 className="text-[15px] font-semibold mb-2.5" style={{ color: t.text1 }}>
                Forward {forwardPopup.msgIds.length > 1 ? `${forwardPopup.msgIds.length} messages` : 'message'}...
              </h3>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: t.text3 }} />
                <input
                  value={forwardSearch}
                  onChange={e => setForwardSearch(e.target.value)}
                  placeholder="Search contacts..."
                  className="w-full h-8 pl-8 pr-3 rounded-lg text-xs outline-none"
                  style={{ border: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.12)'}`, color: t.text1, background: isDark ? '#17212B' : '#F9FAFB' }}
                  autoFocus
                />
              </div>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
              {dialogs
                .filter(d => d.id !== selectedDialog?.id)
                .filter(d => !forwardSearch || (d.peer_name || '').toLowerCase().includes(forwardSearch.toLowerCase()) || (d.peer_username || '').toLowerCase().includes(forwardSearch.toLowerCase()))
                .map(d => (
                  <button
                    key={d.id}
                    onClick={async () => {
                      if (!selectedDialog) return;
                      try {
                        await telegramOutreachApi.forwardDialogMessages(selectedDialog.id, d.id, forwardPopup.msgIds);
                        setForwardPopup(null);
                      } catch { /* handled by API client */ }
                    }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors"
                    style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}
                    onMouseEnter={e => (e.currentTarget.style.background = isDark ? '#242F3D' : '#F0F2F5')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                  >
                    <div
                      className="flex-shrink-0 flex items-center justify-center text-white text-[13px] font-semibold"
                      style={{ width: 36, height: 36, borderRadius: 18, background: `hsl(${(d.peer_id || 0) % 360}, 45%, 55%)` }}
                    >
                      {((d.peer_name || '?')[0] || '?').toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate" style={{ color: t.text1 }}>{d.peer_name || 'Unknown'}</p>
                      {d.peer_username && <p className="text-[11px] truncate" style={{ color: t.text3 }}>@{d.peer_username}</p>}
                    </div>
                  </button>
                ))}
            </div>
            <div style={{ padding: '12px 20px', borderTop: `1px solid ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)'}`, textAlign: 'right' }}>
              <button
                onClick={() => setForwardPopup(null)}
                className="px-4 py-1.5 rounded-lg text-xs font-medium"
                style={{ background: isDark ? '#242F3D' : '#F0F2F5', color: t.text3 }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── New Chat modal ── */}
      {showNewChat && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)' }} onClick={() => setShowNewChat(false)}>
          <div
            className="rounded-xl shadow-xl w-[380px] p-5"
            style={{ background: isDark ? '#1E2C3A' : '#fff' }}
            onClick={e => e.stopPropagation()}
          >
            <h3 className="text-sm font-semibold mb-4" style={{ color: t.text1 }}>New Chat</h3>
            <div className="space-y-3">
              <div>
                <label className="text-[11px] font-medium mb-1 block" style={{ color: t.text3 }}>Account</label>
                <select
                  value={newChatAccountId}
                  onChange={e => setNewChatAccountId(e.target.value ? Number(e.target.value) : '')}
                  className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                  style={{ background: isDark ? '#242F3D' : '#F0F2F5', color: t.text1, border: 'none' }}
                >
                  <option value="">Select account...</option>
                  {accounts.filter(a => a.auth_status === 'active').map(acc => (
                    <option key={acc.id} value={acc.id}>
                      {acc.first_name || acc.username || acc.phone || `#${acc.id}`}
                      {acc.phone ? ` (${acc.phone})` : ''}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[11px] font-medium mb-1 block" style={{ color: t.text3 }}>Username</label>
                <input
                  type="text"
                  placeholder="@username"
                  value={newChatUsername}
                  onChange={e => setNewChatUsername(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleNewChat()}
                  className="w-full px-3 py-2 rounded-lg text-xs outline-none"
                  style={{ background: isDark ? '#242F3D' : '#F0F2F5', color: t.text1, border: 'none' }}
                  autoFocus
                />
              </div>
              {newChatError && (
                <div className="text-[11px] text-red-400">{newChatError}</div>
              )}
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setShowNewChat(false)}
                className="px-3 py-1.5 rounded-lg text-xs"
                style={{ background: isDark ? '#242F3D' : '#F0F2F5', color: t.text3 }}
              >
                Cancel
              </button>
              <button
                onClick={handleNewChat}
                disabled={newChatLoading || !newChatAccountId || !newChatUsername.trim()}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-white disabled:opacity-50"
                style={{ background: '#419FD9' }}
              >
                {newChatLoading ? 'Creating...' : 'Start Chat'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
