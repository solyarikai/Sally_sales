import toast, { Toaster } from 'react-hot-toast';
import { useEffect, useState, useCallback, useRef } from 'react';
import {
  Search, RefreshCw, X,
  Building2, ExternalLink, ChevronDown,
  XCircle, Edit3,
  FolderOpen, Clock, MessageCircle, ArrowRight, Brain,
} from 'lucide-react';
import {
  repliesApi,
  type ProcessedReply,
  type ConversationMessage,
} from '../api/replies';
import { cn } from '../lib/utils';
import { useAppStore } from '../store/appStore';
import { useTheme } from '../hooks/useTheme';

/* ---------- Category labels ---------- */
const CATEGORY_LABEL: Record<string, string> = {
  interested: 'Interested',
  meeting_request: 'Meeting',
  not_interested: 'Not interested',
  out_of_office: 'OOO',
  wrong_person: 'Wrong person',
  unsubscribe: 'Unsubscribe',
  question: 'Question',
  other: 'Other',
};

/* ---------- Time helper ---------- */
function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  return date.toLocaleDateString();
}

/* ---------- Convert HTML email to clean readable text ---------- */
function stripHtml(raw: string): string {
  if (!raw) return '';
  // If no tags at all, just clean up the plain text
  if (!raw.includes('<')) return cleanPlainText(raw);

  try {
    const doc = new DOMParser().parseFromString(raw, 'text/html');

    // Remove <style>, <script>, <head> entirely
    doc.querySelectorAll('style, script, head').forEach(el => el.remove());

    // Remove common signature / disclaimer containers
    doc.querySelectorAll(
      '[class*="gmail_signature"], [class*="signature"], [data-smartmail]'
    ).forEach(el => el.remove());

    // Remove quoted email chains (gmail_quote, blockquote, mso-reply)
    doc.querySelectorAll(
      '[class*="gmail_quote"], [class*="gmail_extra"], blockquote[type="cite"], ' +
      '[class*="yahoo_quoted"], [class*="moz-cite-prefix"], [id*="replySplit"]'
    ).forEach(el => el.remove());

    // Walk the DOM, converting block elements to \n
    const text = domToText(doc.body);
    return cleanPlainText(text);
  } catch {
    // Fallback: regex approach
    let text = raw;
    // Block elements → newline
    text = text.replace(/<\s*(br|\/div|\/p|\/tr|\/li|\/h[1-6])\s*\/?>/gi, '\n');
    // All remaining tags → nothing
    text = text.replace(/<[^>]*>/g, '');
    // Decode common entities
    text = decodeEntities(text);
    return cleanPlainText(text);
  }
}

/** Recursively extract text from DOM, inserting newlines for block elements */
const BLOCK_TAGS = new Set([
  'DIV', 'P', 'BR', 'TR', 'LI', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6',
  'BLOCKQUOTE', 'SECTION', 'ARTICLE', 'HEADER', 'FOOTER', 'HR', 'UL', 'OL',
  'TABLE', 'THEAD', 'TBODY',
]);

function domToText(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) {
    return node.textContent || '';
  }
  if (node.nodeType !== Node.ELEMENT_NODE) return '';

  const el = node as HTMLElement;
  const tag = el.tagName;

  // Skip hidden elements
  if (el.style.display === 'none' || el.getAttribute('aria-hidden') === 'true') return '';
  // Skip images (often tracking pixels)
  if (tag === 'IMG') return '';

  let result = '';
  const isBlock = BLOCK_TAGS.has(tag);

  if (tag === 'BR') return '\n';
  if (tag === 'HR') return '\n---\n';

  if (isBlock) result += '\n';

  for (const child of Array.from(node.childNodes)) {
    result += domToText(child);
  }

  if (isBlock) result += '\n';
  return result;
}

function decodeEntities(text: string): string {
  return text
    .replace(/&nbsp;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&#x27;/gi, "'");
}

/** Clean up plain text: trim signatures, disclaimers, quoted chains, collapse whitespace */
function cleanPlainText(text: string): string {
  // Decode HTML entities that might remain (including &lt; &gt; common in plain-text emails)
  text = decodeEntities(text);

  // Normalize line endings
  text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

  // Trim each line
  text = text.split('\n').map(l => l.trimEnd()).join('\n');

  // Collapse 3+ blank lines into 2
  text = text.replace(/\n{3,}/g, '\n\n');

  // Cut at first matching marker (works on both multi-line and single-line text)
  // NOTE: No ^ or $ anchors — these patterns search anywhere in the text
  const cutMarkers = [
    // Quoted reply chains (most common patterns)
    /On [A-Z][a-z]{2,8},?\s.{5,80}\s+wrote:\s*/i,        // "On Thu, Feb 12, 2026 ... wrote:"
    /El [a-z]{2,10},?\s.{5,80}\s+escribi[oó]:\s*/i,       // Spanish: "El lun, 26 ene ... escribió:"
    /Le [a-z]{2,10},?\s.{5,80}\s+[aà] [eé]crit\s*:\s*/i,  // French
    /Am [A-Z0-9].{5,80}\s+schrieb\s*.*:\s*/i,              // German
    /\d{1,2}\/\d{1,2}\/\d{2,4}.{0,60}wrote/i,            // "2/12/2026 ... wrote"
    /-{2,}\s*Original Message\s*-{2,}/i,                    // "-- Original Message --"
    // Forwarded messages
    /-{5,}\s*Forwarded message\s*-{5,}/i,
    // Disclaimers / confidentiality
    /AVISO DE CONFIDENCIALIDAD/i,
    /CONFIDENTIALITY NOTICE/i,
    /This email and any attachments? (?:are|is) confidential/i,
    /CONSULTE NUESTRO AVISO/i,
    /_{10,}/,
    // Eco-friendly disclaimers (common in LATAM emails)
    /Cuidemos nuestro planeta/i,
    /Este correo electr[oó]nico y cualquier archivo/i,
  ];

  let earliest = text.length;
  for (const marker of cutMarkers) {
    const match = text.match(marker);
    if (match && match.index !== undefined && match.index > 20 && match.index < earliest) {
      earliest = match.index;
    }
  }
  if (earliest < text.length) {
    text = text.substring(0, earliest).trimEnd();
  }

  return text.trim();
}

/* ---------- Theme color tokens ---------- */
function themeColors(isDark: boolean) {
  return isDark
    ? {
        pageBg: '#1e1e1e',
        headerBg: '#252526',
        cardBg: '#252526',
        cardBorder: '#333',
        cardHoverBorder: '#3c3c3c',
        divider: '#2d2d2d',
        inputBg: '#3c3c3c',
        inputBorder: 'transparent',
        inputFocusBorder: '#505050',
        draftBg: '#1e1e1e',
        draftBorder: '#3c3c3c',
        text1: '#d4d4d4',   // primary
        text2: '#b0b0b0',   // secondary
        text3: '#969696',   // tertiary
        text4: '#858585',   // muted
        text5: '#6e6e6e',   // dim
        text6: '#4e4e4e',   // subtle
        badgeBg: '#2d2d2d',
        badgeText: '#858585',
        btnPrimaryBg: '#d4d4d4',
        btnPrimaryHover: '#e0e0e0',
        btnPrimaryText: '#1e1e1e',
        btnGhostHover: '#2d2d2d',
        threadInbound: '#2d2d2d',
        threadOutbound: '#37373d',
        reasoningBg: '#1e1e1e',
        reasoningBorder: '#2d2d2d',
        toastBg: '#252526',
        toastText: '#d4d4d4',
        toastBorder: '#3c3c3c',
        toastErrText: '#d4a4a4',
        scrollThumb: 'rgba(255,255,255,0.1)',
      }
    : {
        pageBg: '#f5f5f5',
        headerBg: '#ffffff',
        cardBg: '#ffffff',
        cardBorder: '#e0e0e0',
        cardHoverBorder: '#ccc',
        divider: '#eee',
        inputBg: '#f0f0f0',
        inputBorder: '#ddd',
        inputFocusBorder: '#bbb',
        draftBg: '#f8f8f8',
        draftBorder: '#ddd',
        text1: '#1a1a1a',
        text2: '#333',
        text3: '#555',
        text4: '#777',
        text5: '#999',
        text6: '#bbb',
        badgeBg: '#eee',
        badgeText: '#666',
        btnPrimaryBg: '#333',
        btnPrimaryHover: '#222',
        btnPrimaryText: '#fff',
        btnGhostHover: '#eee',
        threadInbound: '#f0f4ff',
        threadOutbound: '#f0f0f0',
        reasoningBg: '#f8f8f8',
        reasoningBorder: '#e8e8e8',
        toastBg: '#fff',
        toastText: '#333',
        toastBorder: '#ddd',
        toastErrText: '#c44',
        scrollThumb: 'rgba(0,0,0,0.12)',
      };
}

/* ====================================================================== */

export function RepliesPage() {
  const { currentProject, setCurrentProject, projects } = useAppStore();
  const { isDark } = useTheme();
  const t = themeColors(isDark);

  const [replies, setReplies] = useState<ProcessedReply[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  const [projectSearch, setProjectSearch] = useState('');
  const [showProjectDropdown, setShowProjectDropdown] = useState(false);
  const projectDropdownRef = useRef<HTMLDivElement>(null);
  const [search, setSearch] = useState('');

  const [editingDrafts, setEditingDrafts] = useState<Record<number, { reply: string; subject: string }>>({});
  const [sendingIds, setSendingIds] = useState<Set<number>>(new Set());
  const [expandedThreads, setExpandedThreads] = useState<Set<number>>(new Set());
  const [threadMessages, setThreadMessages] = useState<Record<number, ConversationMessage[]>>({});
  const [loadingThreads, setLoadingThreads] = useState<Set<number>>(new Set());

  const toastOk = { background: t.toastBg, color: t.toastText, border: `1px solid ${t.toastBorder}` };
  const toastErr = { background: t.toastBg, color: t.toastErrText, border: `1px solid ${t.toastBorder}` };

  /* ---- Data loading ---- */
  const loadReplies = useCallback(async () => {
    setIsLoading(true);
    try {
      const campaignNames = currentProject?.campaign_filters?.length
        ? currentProject.campaign_filters.join(',')
        : undefined;
      const response = await repliesApi.getReplies({
        campaign_names: campaignNames,
        needs_reply: true,
        page,
        page_size: pageSize,
      });
      setReplies(response.replies || []);
      setTotal(response.total || 0);
    } catch (err) {
      console.error('Failed to load replies:', err);
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, currentProject]);

  useEffect(() => { setPage(1); }, [currentProject]);
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (projectDropdownRef.current && !projectDropdownRef.current.contains(e.target as Node)) {
        setShowProjectDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  useEffect(() => { loadReplies(); }, [loadReplies]);

  /* ---- Actions ---- */
  const handleApproveAndSend = async (reply: ProcessedReply) => {
    setSendingIds(prev => new Set(prev).add(reply.id));
    try {
      const edited = editingDrafts[reply.id];
      const editedDraft = edited ? { draft_reply: edited.reply, draft_subject: edited.subject } : undefined;
      const result = await repliesApi.approveAndSendReply(reply.id, editedDraft);
      if (result.test_mode) {
        toast.success(`Test sent to ${result.sent_to || 'pn@getsally.io'}`, { style: toastOk });
      } else if (result.dry_run) {
        toast.success('Approved (dry run)', { style: toastOk });
      } else {
        toast.success('Reply sent', { style: toastOk });
      }
      setReplies(prev => prev.filter(r => r.id !== reply.id));
      setTotal(prev => Math.max(0, prev - 1));
      setEditingDrafts(prev => { const d = { ...prev }; delete d[reply.id]; return d; });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to send', { style: toastErr });
    } finally {
      setSendingIds(prev => { const s = new Set(prev); s.delete(reply.id); return s; });
    }
  };

  const handleDismiss = async (reply: ProcessedReply) => {
    try {
      await repliesApi.dismissReply(reply.id);
      toast.success('Skipped', { style: toastOk });
      setReplies(prev => prev.filter(r => r.id !== reply.id));
      setTotal(prev => Math.max(0, prev - 1));
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed', { style: toastErr });
    }
  };

  const startEditing = (reply: ProcessedReply) => {
    setEditingDrafts(prev => ({
      ...prev,
      [reply.id]: { reply: reply.draft_reply || '', subject: reply.draft_subject || '' },
    }));
  };
  const cancelEditing = (id: number) => {
    setEditingDrafts(prev => { const d = { ...prev }; delete d[id]; return d; });
  };

  const loadThread = async (reply: ProcessedReply) => {
    if (expandedThreads.has(reply.id)) {
      setExpandedThreads(prev => { const s = new Set(prev); s.delete(reply.id); return s; });
      return;
    }
    setExpandedThreads(prev => new Set(prev).add(reply.id));
    if (threadMessages[reply.id]) return;
    setLoadingThreads(prev => new Set(prev).add(reply.id));
    try {
      const data = await repliesApi.getConversation(reply.id);
      setThreadMessages(prev => ({ ...prev, [reply.id]: data.messages || [] }));
    } catch {
      setThreadMessages(prev => ({ ...prev, [reply.id]: [] }));
    } finally {
      setLoadingThreads(prev => { const s = new Set(prev); s.delete(reply.id); return s; });
    }
  };

  const filteredReplies = (replies || []).filter(reply => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      reply.lead_email?.toLowerCase().includes(s) ||
      reply.lead_first_name?.toLowerCase().includes(s) ||
      reply.lead_last_name?.toLowerCase().includes(s) ||
      reply.lead_company?.toLowerCase().includes(s) ||
      reply.email_subject?.toLowerCase().includes(s) ||
      reply.campaign_name?.toLowerCase().includes(s)
    );
  });

  const totalPages = Math.ceil(total / pageSize);

  /* ==================================================================== */
  return (
    <div className="h-full flex flex-col" style={{ background: t.pageBg }}>
      <Toaster position="top-center" />

      {/* Header bar */}
      <div
        className="border-b px-5 py-2.5 flex items-center justify-between"
        style={{ background: t.headerBg, borderColor: t.cardBorder }}
      >
        <div className="flex items-center gap-3">
          <div className="flex items-baseline gap-1.5">
            <span className="text-[14px] font-medium" style={{ color: t.text1 }}>{total}</span>
            <span className="text-[13px]" style={{ color: t.text4 }}>need reply</span>
          </div>

          <div className="w-px h-4" style={{ background: t.cardBorder }} />

          {/* Project selector */}
          <div className="relative" ref={projectDropdownRef}>
            <button
              onClick={() => { setShowProjectDropdown(!showProjectDropdown); setProjectSearch(''); }}
              className="flex items-center gap-1.5 px-2 py-1 rounded text-[13px] transition-colors"
              style={{ color: currentProject ? t.text1 : t.text3 }}
            >
              <FolderOpen className="w-3.5 h-3.5" />
              <span className="truncate max-w-[160px]">{currentProject ? currentProject.name : 'All Projects'}</span>
              <ChevronDown className="w-3 h-3" />
            </button>
            {showProjectDropdown && (
              <div
                className="absolute top-full left-0 mt-1 w-64 rounded-md shadow-xl z-50 overflow-hidden border"
                style={{ background: t.cardBg, borderColor: t.cardHoverBorder }}
              >
                <div className="p-1.5 border-b" style={{ borderColor: t.divider }}>
                  <input
                    type="text"
                    autoFocus
                    value={projectSearch}
                    onChange={e => setProjectSearch(e.target.value)}
                    placeholder="Search..."
                    className="w-full px-2 py-1 text-[13px] border-none rounded focus:outline-none"
                    style={{ background: t.inputBg, color: t.text1 }}
                  />
                </div>
                <div className="max-h-60 overflow-y-auto py-0.5">
                  {!projectSearch && (
                    <button
                      onClick={() => { setCurrentProject(null); setShowProjectDropdown(false); }}
                      className="w-full px-3 py-1.5 text-left text-[13px] transition-colors"
                      style={{
                        background: !currentProject ? t.badgeBg : undefined,
                        color: !currentProject ? t.text1 : t.text3,
                      }}
                    >
                      All Projects
                    </button>
                  )}
                  {projects.length === 0 ? (
                    <div className="px-3 py-1.5 text-[13px]" style={{ color: t.text5 }}>Loading...</div>
                  ) : (
                    projects
                      .filter(p => p.name.toLowerCase().includes(projectSearch.toLowerCase()))
                      .map(p => (
                        <button
                          key={p.id}
                          onClick={() => { setCurrentProject(p); setShowProjectDropdown(false); setProjectSearch(''); }}
                          className="w-full px-3 py-1.5 text-left text-[13px] truncate transition-colors"
                          style={{
                            background: currentProject?.id === p.id ? t.badgeBg : undefined,
                            color: currentProject?.id === p.id ? t.text1 : t.text3,
                          }}
                        >
                          {p.name}
                        </button>
                      ))
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-2 top-1/2 -translate-y-1/2" style={{ color: t.text5 }} />
            <input
              type="text"
              placeholder="Filter..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-7 pr-2 py-1 text-[13px] border-none rounded w-36 focus:outline-none"
              style={{ background: t.inputBg, color: t.text1 }}
            />
          </div>
          <button
            onClick={() => loadReplies()}
            className="p-1.5 rounded transition-colors"
            title="Refresh"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", isLoading && "animate-spin")} style={{ color: t.text4 }} />
          </button>
        </div>
      </div>

      {/* Reply queue */}
      <div className="flex-1 overflow-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <RefreshCw className="w-5 h-5 animate-spin" style={{ color: t.text5 }} />
          </div>
        ) : filteredReplies.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20">
            <p className="text-[13px]" style={{ color: t.text4 }}>All caught up</p>
          </div>
        ) : (
          <div className="max-w-5xl mx-auto py-3 px-4 space-y-2.5">
            {filteredReplies.map(reply => {
              const leadName = [reply.lead_first_name, reply.lead_last_name].filter(Boolean).join(' ') || reply.lead_email;
              const isEditing = reply.id in editingDrafts;
              const isSending = sendingIds.has(reply.id);
              const isThreadOpen = expandedThreads.has(reply.id);
              const isThreadLoading = loadingThreads.has(reply.id);
              const thread = threadMessages[reply.id];
              const draftText = isEditing ? editingDrafts[reply.id].reply : (reply.draft_reply || '');
              const catLabel = CATEGORY_LABEL[reply.category || ''] || reply.category || '';
              const hasReasoning = reply.classification_reasoning || reply.category_confidence;

              return (
                <div
                  key={reply.id}
                  className="rounded-md border transition-colors"
                  style={{
                    background: t.cardBg,
                    borderColor: t.cardBorder,
                  }}
                >
                  {/* Two-column layout: conversation | reasoning */}
                  <div className="flex">
                    {/* Left: conversation & draft */}
                    <div className="flex-1 min-w-0">
                      {/* Lead row */}
                      <div className="flex items-center justify-between px-4 pt-3 pb-1">
                        <div className="flex items-center gap-2 min-w-0 text-[13px]">
                          <span className="font-medium truncate" style={{ color: t.text1 }}>{leadName}</span>
                          {reply.lead_company && (
                            <span className="flex items-center gap-1 truncate" style={{ color: t.text5 }}>
                              <Building2 className="w-3 h-3" />{reply.lead_company}
                            </span>
                          )}
                          {catLabel && (
                            <span
                              className="text-[11px] px-1.5 py-0.5 rounded"
                              style={{ background: t.badgeBg, color: t.badgeText }}
                            >
                              {catLabel}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0 text-[11px]" style={{ color: t.text5 }}>
                          <span className="flex items-center gap-0.5">
                            <Clock className="w-3 h-3" />
                            {reply.received_at ? timeAgo(reply.received_at) : '?'}
                          </span>
                          {reply.inbox_link && (
                            <a
                              href={reply.inbox_link}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="transition-colors"
                              title="Smartlead"
                              onClick={e => e.stopPropagation()}
                              style={{ color: t.text5 }}
                            >
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                        </div>
                      </div>

                      {reply.campaign_name && (
                        <div className="px-4 text-[11px] pb-1" style={{ color: t.text6 }}>{reply.campaign_name}</div>
                      )}

                      {/* Their message -- NO max-height, full content visible */}
                      <div className="px-4 py-2">
                        {reply.email_subject && (
                          <div className="text-[13px] mb-1" style={{ color: t.text2 }}>{reply.email_subject}</div>
                        )}
                        <div
                          className="text-[13px] leading-relaxed whitespace-pre-wrap"
                          style={{ color: t.text3 }}
                        >
                          {stripHtml(reply.email_body || reply.reply_text || '') || '(empty)'}
                        </div>
                      </div>

                      {/* Thread */}
                      <div className="px-4">
                        <button
                          onClick={() => loadThread(reply)}
                          className="text-[11px] flex items-center gap-1 py-0.5 transition-colors"
                          style={{ color: t.text5 }}
                        >
                          <MessageCircle className="w-3 h-3" />
                          {isThreadOpen ? 'Hide thread' : 'Thread'}
                        </button>
                        {isThreadOpen && (
                          <div className="mt-1.5 mb-2 space-y-1.5">
                            {isThreadLoading ? (
                              <div className="flex items-center gap-1.5 py-1.5 text-[11px]" style={{ color: t.text5 }}>
                                <RefreshCw className="w-3 h-3 animate-spin" /> Loading...
                              </div>
                            ) : thread && thread.length > 0 ? (
                              <>
                                {thread.map((msg, i) => {
                                  const isInbound = msg.direction === 'inbound';
                                  return (
                                    <div key={i} className={cn("flex flex-col", isInbound ? "items-start" : "items-end")}>
                                      <div
                                        className="text-[10px] font-medium mb-0.5 px-1"
                                        style={{ color: t.text5 }}
                                      >
                                        {isInbound ? 'Lead' : 'Operator'}
                                      </div>
                                      <div
                                        className="max-w-[85%] rounded px-3 py-2 text-[13px]"
                                        style={{
                                          background: isInbound ? t.threadInbound : t.threadOutbound,
                                          color: isInbound ? t.text2 : t.text3,
                                        }}
                                      >
                                        <div className="whitespace-pre-wrap leading-relaxed">{stripHtml(msg.body || '') || '(no content)'}</div>
                                        <div className="text-[10px] mt-1" style={{ color: t.text6 }}>
                                          {msg.activity_at ? new Date(msg.activity_at).toLocaleString() : ''}
                                        </div>
                                      </div>
                                    </div>
                                  );
                                })}
                              </>
                            ) : (
                              <div className="text-[11px] py-1" style={{ color: t.text6 }}>No history</div>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="mx-4" style={{ borderTop: `1px solid ${t.divider}` }} />

                      {/* Draft -- always visible, NO max-height */}
                      <div className="px-4 py-2.5">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-[11px] uppercase tracking-wider" style={{ color: t.text5 }}>Draft</span>
                          {!isEditing && reply.draft_reply ? (
                            <button
                              onClick={() => startEditing(reply)}
                              className="text-[11px] flex items-center gap-1 transition-colors"
                              style={{ color: t.text5 }}
                            >
                              <Edit3 className="w-3 h-3" /> Edit
                            </button>
                          ) : isEditing ? (
                            <button
                              onClick={() => cancelEditing(reply.id)}
                              className="text-[11px] flex items-center gap-1 transition-colors"
                              style={{ color: t.text5 }}
                            >
                              <X className="w-3 h-3" /> Cancel
                            </button>
                          ) : null}
                        </div>

                        {isEditing ? (
                          <textarea
                            value={editingDrafts[reply.id].reply}
                            onChange={e => setEditingDrafts(prev => ({
                              ...prev,
                              [reply.id]: { ...prev[reply.id], reply: e.target.value },
                            }))}
                            className="w-full text-[13px] rounded p-2.5 focus:outline-none min-h-[80px] resize-y border"
                            style={{
                              background: t.draftBg,
                              borderColor: t.draftBorder,
                              color: t.text1,
                            }}
                            placeholder="Edit your reply..."
                          />
                        ) : (
                          <div
                            className="text-[13px] whitespace-pre-wrap leading-relaxed rounded p-2.5"
                            style={{ background: t.draftBg, color: t.text2 }}
                          >
                            {draftText || '(no draft)'}
                          </div>
                        )}
                      </div>

                      {/* Actions */}
                      <div className="px-4 pb-3 flex items-center gap-1.5">
                        <button
                          onClick={() => handleApproveAndSend(reply)}
                          disabled={isSending || !reply.draft_reply}
                          className={cn(
                            "flex items-center gap-1.5 px-3.5 py-1.5 rounded text-[13px] font-medium transition-colors",
                            isSending ? "cursor-wait" : ""
                          )}
                          style={{
                            background: isSending ? t.divider : t.btnPrimaryBg,
                            color: isSending ? t.text5 : t.btnPrimaryText,
                          }}
                        >
                          {isSending ? (
                            <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Sending...</>
                          ) : (
                            <><ArrowRight className="w-3.5 h-3.5" /> {isEditing ? 'Send edited' : 'Send'}</>
                          )}
                        </button>
                        <button
                          onClick={() => handleDismiss(reply)}
                          disabled={isSending}
                          className="flex items-center gap-1 px-3 py-1.5 rounded text-[13px] transition-colors"
                          style={{ color: t.text4 }}
                        >
                          <XCircle className="w-3.5 h-3.5" /> Skip
                        </button>
                      </div>
                    </div>

                    {/* Right: AI reasoning sidebar */}
                    {hasReasoning && (
                      <div
                        className="w-64 flex-shrink-0 border-l px-3 py-3"
                        style={{
                          borderColor: t.divider,
                          background: t.reasoningBg,
                        }}
                      >
                        <div className="flex items-center gap-1.5 mb-2">
                          <Brain className="w-3.5 h-3.5" style={{ color: t.text4 }} />
                          <span className="text-[11px] font-medium uppercase tracking-wider" style={{ color: t.text4 }}>
                            AI Analysis
                          </span>
                        </div>

                        {reply.category && (
                          <div className="mb-2">
                            <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: t.text5 }}>
                              Category
                            </div>
                            <div className="text-[13px] font-medium" style={{ color: t.text1 }}>
                              {CATEGORY_LABEL[reply.category] || reply.category}
                            </div>
                          </div>
                        )}

                        {reply.category_confidence && (
                          <div className="mb-2">
                            <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: t.text5 }}>
                              Confidence
                            </div>
                            <div className="text-[12px]" style={{ color: t.text3 }}>
                              {reply.category_confidence}
                            </div>
                          </div>
                        )}

                        {reply.classification_reasoning && (
                          <div>
                            <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: t.text5 }}>
                              Reasoning
                            </div>
                            <div
                              className="text-[12px] leading-relaxed whitespace-pre-wrap"
                              style={{ color: t.text3 }}
                            >
                              {reply.classification_reasoning}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div
          className="border-t px-5 py-2 flex items-center justify-between"
          style={{ background: t.headerBg, borderColor: t.cardBorder }}
        >
          <span className="text-[11px]" style={{ color: t.text5 }}>Page {page} of {totalPages}</span>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-2 py-1 text-[11px] rounded disabled:opacity-30 transition-colors"
              style={{ color: t.text4 }}
            >
              Prev
            </button>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-2 py-1 text-[11px] rounded disabled:opacity-30 transition-colors"
              style={{ color: t.text4 }}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default RepliesPage;
