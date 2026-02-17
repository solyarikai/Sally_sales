import toast, { Toaster } from 'react-hot-toast';
import { useEffect, useState, useCallback, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  Search, RefreshCw, X,
  Building2, ExternalLink,
  XCircle, Edit3,
  Clock, MessageCircle, ArrowRight, Brain,
  Linkedin, Phone, MapPin, Tag, Globe, User,
} from 'lucide-react';
import {
  repliesApi,
  type ProcessedReply,
  type ConversationMessage,
  type ReplyCategory,
  type ContactInfo,
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
    // Outlook-style email headers (English)
    /\nFrom:\s.{3,80}\n\s*Sent:\s/i,                        // "From: Name\nSent: date"
    /\nFrom:\s.{3,80}\n\s*Date:\s/i,                        // "From: Name\nDate: date"
    // Outlook-style email headers (Russian)
    /\nОт:\s/i,                                             // "От: Name"
    /\nОтправлено:\s/i,                                     // "Отправлено: date"
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
  const [searchParams, setSearchParams] = useSearchParams();

  const [replies, setReplies] = useState<ProcessedReply[]>([]);
  const [total, setTotal] = useState(0);
  const [categoryCounts, setCategoryCounts] = useState<Record<string, number>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const pageRef = useRef(1);
  const PAGE_SIZE = 30;

  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string | null>('meeting_request');

  const [editingDrafts, setEditingDrafts] = useState<Record<number, { reply: string; subject: string }>>({});
  const [sendingIds, setSendingIds] = useState<Set<number>>(new Set());
  const [expandedThreads, setExpandedThreads] = useState<Set<number>>(new Set());
  const [threadMessages, setThreadMessages] = useState<Record<number, ConversationMessage[]>>({});
  const [loadingThreads, setLoadingThreads] = useState<Set<number>>(new Set());
  const [contactInfoMap, setContactInfoMap] = useState<Record<number, ContactInfo | null>>({});

  const scrollRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const toastOk = { background: t.toastBg, color: t.toastText, border: `1px solid ${t.toastBorder}` };
  const toastErr = { background: t.toastBg, color: t.toastErrText, border: `1px solid ${t.toastBorder}` };

  /* ---- URL ↔ project sync ---- */
  // URL is the source of truth on initial load.
  // initialUrlParam captures the raw ?project= value at mount time (before
  // the persisted store can clobber it).  We use a ref so the store→URL
  // effect skips writing until the URL→store effect has resolved.
  const initialUrlParam = useRef(searchParams.get('project'));
  const urlApplied = useRef(!initialUrlParam.current); // true when no URL param

  // URL → store: apply ?project=<name|id> to the store once projects load
  useEffect(() => {
    const projectParam = searchParams.get('project');
    if (!projectParam || !projects.length) return;
    const normalized = projectParam.toLowerCase().replace(/-/g, ' ');
    const match = projects.find(p => p.name.toLowerCase() === normalized)
      || projects.find(p => p.id === Number(projectParam));
    if (match && (!currentProject || currentProject.id !== match.id)) {
      setCurrentProject(match);
    }
    urlApplied.current = true;
  }, [projects, searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  // Store → URL: when project changes (dropdown), reflect in the URL
  useEffect(() => {
    // Don't overwrite the URL until the initial URL param has been resolved
    if (!urlApplied.current) return;
    const currentParam = searchParams.get('project');
    const targetParam = currentProject
      ? currentProject.name.toLowerCase().replace(/\s+/g, '-')
      : null;
    if (currentParam !== targetParam) {
      setSearchParams(prev => {
        const next = new URLSearchParams(prev);
        if (targetParam) next.set('project', targetParam);
        else next.delete('project');
        return next;
      }, { replace: true });
    }
  }, [currentProject]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ---- Data loading (infinite scroll) ---- */
  const loadReplies = useCallback(async (reset = false) => {
    if (reset) {
      setIsLoading(true);
      pageRef.current = 1;
    } else {
      setIsLoadingMore(true);
    }
    try {
      const pg = reset ? 1 : pageRef.current;
      const response = await repliesApi.getReplies({
        project_id: currentProject?.id,
        needs_reply: true,
        category: (categoryFilter as ReplyCategory) || undefined,
        page: pg,
        page_size: PAGE_SIZE,
      });
      const newReplies = response.replies || [];
      if (reset) {
        setReplies(newReplies);
      } else {
        setReplies(prev => [...prev, ...newReplies]);
      }
      setTotal(response.total || 0);
      setCategoryCounts(response.category_counts || {});
      setHasMore(newReplies.length >= PAGE_SIZE);
    } catch (err) {
      console.error('Failed to load replies:', err);
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, [currentProject, categoryFilter]);

  // Reset on project/filter change
  useEffect(() => { loadReplies(true); }, [loadReplies]);

  // Infinite scroll via IntersectionObserver
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasMore && !isLoadingMore && !isLoading) {
          pageRef.current += 1;
          loadReplies(false);
        }
      },
      { root: scrollRef.current, rootMargin: '200px' }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, isLoadingMore, isLoading, loadReplies]);

  /* ---- Actions ---- */
  const handleApproveAndSend = async (reply: ProcessedReply) => {
    setSendingIds(prev => new Set(prev).add(reply.id));
    try {
      const edited = editingDrafts[reply.id];
      const editedDraft = edited ? { draft_reply: edited.reply, draft_subject: edited.subject } : undefined;
      const result = await repliesApi.approveAndSendReply(reply.id, editedDraft);
      if (result.channel === 'linkedin') {
        toast.success('Approved — copy draft to LinkedIn', { style: toastOk });
      } else if (result.test_mode) {
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
      if (data.contact_info !== undefined) {
        setContactInfoMap(prev => ({ ...prev, [reply.id]: data.contact_info || null }));
      }
      // Auto-remove if operator already replied (detected by backend)
      if (data.approval_status === 'replied_externally') {
        toast.success('Operator already replied — removed from queue', { style: toastOk });
        setReplies(prev => prev.filter(r => r.id !== reply.id));
        setTotal(prev => Math.max(0, prev - 1));
      }
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

  const CATEGORY_FILTERS = [
    { key: null, label: 'All need reply', countKey: null },
    { key: 'meeting_request', label: 'Meetings', countKey: 'meeting_request' },
    { key: 'interested', label: 'Interested', countKey: 'interested' },
    { key: 'question', label: 'Questions', countKey: 'question' },
    { key: 'other', label: 'Other', countKey: 'other' },
  ] as const;

  const getTabCount = (countKey: string | null): number => {
    if (countKey === null) return Object.values(categoryCounts).reduce((a, b) => a + b, 0);
    return categoryCounts[countKey] || 0;
  };

  /* ==================================================================== */
  return (
    <div className="h-full flex flex-col" style={{ background: t.pageBg }}>
      <Toaster position="top-center" />

      {/* Header bar */}
      <div
        className="border-b px-5 py-2.5 flex items-center gap-3"
        style={{ background: t.headerBg, borderColor: t.cardBorder }}
      >
        {currentProject && (
          <>
            <Link
              to={`/projects/${currentProject.id}`}
              className="text-[13px] hover:underline"
              style={{ color: t.text4 }}
            >
              {currentProject.name}
            </Link>
            <div className="w-px h-4" style={{ background: t.cardBorder }} />
          </>
        )}

        {/* Category filter tabs with counts */}
        <div className="flex items-center gap-1">
          {CATEGORY_FILTERS.map(f => {
            const active = categoryFilter === f.key;
            const count = getTabCount(f.countKey);
            return (
              <button
                key={f.key ?? 'all'}
                onClick={() => setCategoryFilter(f.key)}
                className={cn("px-2.5 py-1 rounded text-[12px] transition-colors", active ? "font-medium" : "")}
                style={{
                  background: active ? t.btnPrimaryBg : 'transparent',
                  color: active ? t.btnPrimaryText : t.text4,
                }}
              >
                {f.label}{count > 0 ? ` ${count}` : ''}
              </button>
            );
          })}
        </div>

        <div className="flex-1" />

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
          onClick={() => loadReplies(true)}
          className="p-1.5 rounded transition-colors"
          title="Refresh"
        >
          <RefreshCw className={cn("w-3.5 h-3.5", isLoading && "animate-spin")} style={{ color: t.text4 }} />
        </button>
      </div>

      {/* Reply queue — infinite scroll */}
      <div ref={scrollRef} className="flex-1 overflow-auto">
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
              const contactInfo = contactInfoMap[reply.id];

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
                      {/* Sticky header: lead row + campaign */}
                      <div
                        style={{ position: 'sticky', top: 0, zIndex: 10, background: t.cardBg }}
                        className="rounded-t-md"
                      >
                        <div className="flex items-center justify-between px-4 pt-3 pb-1">
                          <div className="flex items-center gap-2 min-w-0 text-[13px]">
                            <span className="font-medium truncate" style={{ color: t.text1 }}>{leadName}</span>
                            {reply.lead_company && (
                              <span className="flex items-center gap-1 truncate" style={{ color: t.text5 }}>
                                <Building2 className="w-3 h-3" />{reply.lead_company}
                              </span>
                            )}
                            {reply.channel === 'linkedin' && (
                              <span
                                className="text-[11px] px-1.5 py-0.5 rounded font-medium"
                                style={{ background: '#e7f0fe', color: '#0a66c2' }}
                              >
                                LinkedIn
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
                        <div style={{ borderBottom: `1px solid ${t.divider}` }} />
                      </div>

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
                                  const cleaned = stripHtml(msg.body || '');
                                  if (!cleaned || cleaned === '(no content)') return null;
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
                                        <div className="whitespace-pre-wrap leading-relaxed">{cleaned}</div>
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

                      {/* Actions — sticky at bottom */}
                      <div
                        className="px-4 pb-3 pt-2 flex items-center gap-1.5"
                        style={{ position: 'sticky', bottom: 0, zIndex: 10, background: t.cardBg, borderTop: `1px solid ${t.divider}` }}
                      >
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
                            <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> {reply.channel === 'linkedin' ? 'Approving...' : 'Sending...'}</>
                          ) : (
                            <><ArrowRight className="w-3.5 h-3.5" /> {reply.channel === 'linkedin' ? (isEditing ? 'Approve edited' : 'Approve') : (isEditing ? 'Send edited' : 'Send')}</>
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

                    {/* Right: AI reasoning + contact info sidebar — sticky while scrolling */}
                    {(hasReasoning || contactInfo) && (
                      <div
                        className="w-64 flex-shrink-0 border-l px-3 py-3"
                        style={{
                          borderColor: t.divider,
                          background: t.reasoningBg,
                          position: 'sticky',
                          top: 0,
                          alignSelf: 'flex-start',
                        }}
                      >
                        {hasReasoning && (
                          <>
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
                          </>
                        )}

                        {contactInfo && (
                          <>
                            {hasReasoning && <div className="my-2.5" style={{ borderTop: `1px solid ${t.divider}` }} />}
                            <div className="flex items-center gap-1.5 mb-2">
                              <User className="w-3.5 h-3.5" style={{ color: t.text4 }} />
                              <span className="text-[11px] font-medium uppercase tracking-wider" style={{ color: t.text4 }}>
                                Contact
                              </span>
                            </div>

                            {contactInfo.linkedin_url && (
                              <div className="mb-1.5">
                                <a
                                  href={contactInfo.linkedin_url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="flex items-center gap-1.5 text-[12px] hover:underline"
                                  style={{ color: '#0a66c2' }}
                                >
                                  <Linkedin className="w-3.5 h-3.5" /> LinkedIn profile
                                </a>
                              </div>
                            )}

                            {contactInfo.job_title && (
                              <div className="mb-1.5 text-[12px]" style={{ color: t.text2 }}>
                                {contactInfo.job_title}
                              </div>
                            )}

                            {(contactInfo.company_name || contactInfo.domain) && (
                              <div className="mb-1.5 flex items-center gap-1 text-[12px]" style={{ color: t.text3 }}>
                                <Building2 className="w-3 h-3 flex-shrink-0" />
                                <span>{contactInfo.company_name}{contactInfo.domain ? ` · ${contactInfo.domain}` : ''}</span>
                              </div>
                            )}

                            {contactInfo.location && (
                              <div className="mb-1.5 flex items-center gap-1 text-[12px]" style={{ color: t.text3 }}>
                                <MapPin className="w-3 h-3 flex-shrink-0" />
                                <span>{contactInfo.location}</span>
                              </div>
                            )}

                            {contactInfo.segment && (
                              <div className="mb-1.5">
                                <span
                                  className="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded"
                                  style={{ background: t.badgeBg, color: t.badgeText }}
                                >
                                  <Tag className="w-3 h-3" />{contactInfo.segment}
                                </span>
                              </div>
                            )}

                            {contactInfo.phone && (
                              <div className="mb-1.5 flex items-center gap-1 text-[12px]" style={{ color: t.text3 }}>
                                <Phone className="w-3 h-3 flex-shrink-0" />
                                <span>{contactInfo.phone}</span>
                              </div>
                            )}

                            {contactInfo.source && (
                              <div className="mb-1.5">
                                <span
                                  className="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded"
                                  style={{ background: t.badgeBg, color: t.badgeText }}
                                >
                                  <Globe className="w-3 h-3" />{contactInfo.source}
                                </span>
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
            {/* Infinite scroll sentinel */}
            <div ref={sentinelRef} className="h-4" />
            {isLoadingMore && (
              <div className="flex items-center justify-center py-4">
                <RefreshCw className="w-4 h-4 animate-spin" style={{ color: t.text5 }} />
              </div>
            )}
            {!hasMore && replies.length > 0 && (
              <div className="text-center py-3 text-[11px]" style={{ color: t.text6 }}>
                Showing all {replies.length} of {total}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default RepliesPage;
