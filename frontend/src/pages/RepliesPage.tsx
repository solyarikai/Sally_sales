import toast, { Toaster } from 'react-hot-toast';
import { useEffect, useState, useCallback, useRef } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import {
  Search, RefreshCw, X,
  Building2, ExternalLink,
  XCircle, Edit3, AlertTriangle,
  Clock, MessageCircle, ArrowRight, Brain,
  Linkedin, Phone, MapPin, Tag, User, Copy, Mail,
} from 'lucide-react';
import {
  repliesApi,
  type ProcessedReply,
  type ConversationMessage,
  type ReplyCategory,
  type ContactInfo,
  type ContactCampaignEntry,
} from '../api/replies';
import { cn } from '../lib/utils';
import { stripHtml } from '../lib/htmlUtils';
import { ConversationThread, adaptReplyThread } from '../components/ConversationThread';
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

/* ---------- Campaign name display (strip hex IDs, emails, long suffixes) ---------- */
function displayCampaignName(name: string | null | undefined): string {
  if (!name) return 'Unknown';
  let clean = name
    .replace(/\s+[0-9a-f]{6,}$/i, '')   // strip trailing hex IDs
    .replace(/\s+\S+@\S+\.\S+$/i, '')   // strip trailing email addresses
    .trim();
  // Truncate if still too long for a button label
  if (clean.length > 30) clean = clean.slice(0, 27) + '...';
  return clean || name;
}

/* ---------- Draft / classification failure detection ---------- */
const FAILED_DRAFT_RE = /^\{?(Draft generation failed|Error generating)/i;
const FAILED_CLASS_RE = /Classification failed|failed after \d+ attempts/i;

function isDraftFailed(draft: string | null | undefined): boolean {
  return !!draft && FAILED_DRAFT_RE.test(draft.trim());
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
        errorBg: '#3a2020',
        errorBorder: '#5a3030',
        errorText: '#d4a4a4',
        warnText: '#d4a464',
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
        errorBg: '#fef2f2',
        errorBorder: '#fecaca',
        errorText: '#b91c1c',
        warnText: '#b45309',
        scrollThumb: 'rgba(0,0,0,0.12)',
      };
}

/* ====================================================================== */

export function RepliesPage() {
  const { currentProject, setCurrentProject, projects } = useAppStore();
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const navigate = useNavigate();
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
  const [regeneratingIds, setRegeneratingIds] = useState<Set<number>>(new Set());

  // Campaign selector state (for group_by_contact dedup)
  const [contactCampaigns, setContactCampaigns] = useState<Record<string, ContactCampaignEntry[]>>({});
  const [loadingCampaigns, setLoadingCampaigns] = useState<Set<string>>(new Set());
  const [expandedCampaigns, setExpandedCampaigns] = useState<Set<string>>(new Set());

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
        group_by_contact: true,
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
  /** Re-fetch just the category counts from server after a reply is removed. */
  const refreshCounts = () => {
    repliesApi.getReplies({
      project_id: currentProject?.id,
      needs_reply: true,
      category: (categoryFilter as ReplyCategory) || undefined,
      group_by_contact: true,
      page: 1,
      page_size: 0,
    }).then(response => {
      setCategoryCounts(response.category_counts || {});
      setTotal(response.total || 0);
    }).catch(() => {});
  };

  const handleApproveAndSend = async (reply: ProcessedReply) => {
    setSendingIds(prev => new Set(prev).add(reply.id));
    try {
      const edited = editingDrafts[reply.id];
      const editedDraft = edited ? { draft_reply: edited.reply, draft_subject: edited.subject } : undefined;
      const result = await repliesApi.approveAndSendReply(reply.id, editedDraft);
      const contactId = result.contact_id;
      const toastMsg = result.channel === 'linkedin'
        ? 'Approved — copy draft to LinkedIn'
        : 'Reply sent';
      toast(
        (tInstance) => (
          <span style={{ color: t.toastText }}>
            {toastMsg}
            {contactId && (
              <>
                {' · '}
                <a
                  href={`/contacts?contact_id=${contactId}`}
                  onClick={(e) => {
                    e.preventDefault();
                    toast.dismiss(tInstance.id);
                    navigate(`/contacts?contact_id=${contactId}`);
                  }}
                  style={{ textDecoration: 'underline', color: t.toastText }}
                >
                  View conversation
                </a>
              </>
            )}
          </span>
        ),
        { style: toastOk, duration: 6000 }
      );
      setReplies(prev => prev.filter(r => r.id !== reply.id));
      refreshCounts();
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
      refreshCounts();
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

  /* ---- Campaign selector (for group_by_contact dedup) ---- */
  const loadContactCampaigns = async (email: string) => {
    if (contactCampaigns[email] || loadingCampaigns.has(email)) return;
    setLoadingCampaigns(prev => new Set(prev).add(email));
    try {
      const data = await repliesApi.getContactCampaigns(email, currentProject?.id);
      setContactCampaigns(prev => ({ ...prev, [email]: data.campaigns }));
    } catch {
      setContactCampaigns(prev => ({ ...prev, [email]: [] }));
    } finally {
      setLoadingCampaigns(prev => { const s = new Set(prev); s.delete(email); return s; });
    }
  };

  const toggleCampaignSelector = (email: string) => {
    setExpandedCampaigns(prev => {
      const s = new Set(prev);
      if (s.has(email)) { s.delete(email); } else { s.add(email); loadContactCampaigns(email); }
      return s;
    });
  };

  const switchCampaign = (reply: ProcessedReply, entry: ContactCampaignEntry) => {
    if (entry.reply_id === reply.id) return; // already active
    setReplies(prev => prev.map(r => {
      if (r.id !== reply.id) return r;
      return {
        ...r,
        id: entry.reply_id,
        campaign_id: entry.campaign_id,
        campaign_name: entry.campaign_name,
        category: entry.category as ReplyCategory | null,
        classification_reasoning: entry.classification_reasoning,
        received_at: entry.received_at,
        email_subject: entry.email_subject,
        email_body: entry.email_body,
        reply_text: entry.reply_text,
        draft_reply: entry.draft_reply,
        draft_subject: entry.draft_subject,
        approval_status: entry.approval_status,
        inbox_link: entry.inbox_link,
        channel: entry.channel,
      };
    }));
    // Clear editing & thread state for old reply
    setEditingDrafts(prev => { const d = { ...prev }; delete d[reply.id]; return d; });
    setExpandedThreads(prev => { const s = new Set(prev); s.delete(reply.id); return s; });
  };

  // Close campaign dropdown on outside click
  useEffect(() => {
    if (expandedCampaigns.size === 0) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('[data-campaign-dropdown]')) {
        setExpandedCampaigns(new Set());
      }
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [expandedCampaigns.size]);

  const handleRegenerate = async (reply: ProcessedReply) => {
    setRegeneratingIds(prev => new Set(prev).add(reply.id));
    try {
      const result = await repliesApi.regenerateDraft(reply.id);
      setReplies(prev => prev.map(r => {
        if (r.id !== reply.id) return r;
        return {
          ...r,
          draft_reply: result.draft_reply,
          draft_subject: result.draft_subject,
          category: result.category as ProcessedReply['category'],
          classification_reasoning: result.classification_reasoning,
        };
      }));
      toast.success('Draft regenerated', { style: toastOk });
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Regeneration failed', { style: toastErr });
    } finally {
      setRegeneratingIds(prev => { const s = new Set(prev); s.delete(reply.id); return s; });
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
              const draftFailed = isDraftFailed(reply.draft_reply);
              const classificationFailed = FAILED_CLASS_RE.test(reply.classification_reasoning || '');
              const catLabel = CATEGORY_LABEL[reply.category || ''] || reply.category || '';
              const hasReasoning = !!reply.classification_reasoning;
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

                        {/* Campaign dropdown selector */}
                        {reply.campaign_name && (
                          <div className="px-4 text-[11px] pb-1" style={{ color: t.text6 }}>
                            {(reply.contact_campaign_count ?? 0) > 1 ? (
                              <div className="relative inline-block" data-campaign-dropdown>
                                <button
                                  onClick={() => toggleCampaignSelector(reply.lead_email)}
                                  className="inline-flex items-center gap-1 hover:opacity-80 transition-opacity"
                                >
                                  <span className="truncate max-w-[300px]">{displayCampaignName(reply.campaign_name)}</span>
                                  <span
                                    className="px-1 py-0.5 rounded text-[10px] font-medium"
                                    style={{ background: t.badgeBg, color: t.badgeText }}
                                  >
                                    {reply.contact_campaign_count}
                                  </span>
                                  <span className="text-[10px]">{expandedCampaigns.has(reply.lead_email) ? '▲' : '▼'}</span>
                                </button>
                                {expandedCampaigns.has(reply.lead_email) && (
                                  <div
                                    className="absolute left-0 top-full mt-1 rounded-md border shadow-lg z-20 min-w-[260px] py-1"
                                    style={{ background: t.cardBg, borderColor: t.cardBorder }}
                                  >
                                    {loadingCampaigns.has(reply.lead_email) ? (
                                      <div className="px-3 py-2 text-[11px]" style={{ color: t.text5 }}>Loading...</div>
                                    ) : (contactCampaigns[reply.lead_email] || []).map(entry => {
                                      const isActive = entry.reply_id === reply.id;
                                      return (
                                        <button
                                          key={entry.reply_id}
                                          onClick={() => { switchCampaign(reply, entry); setExpandedCampaigns(new Set()); }}
                                          className="w-full px-3 py-1.5 text-left text-[11px] flex items-center justify-between gap-2 transition-colors"
                                          style={{
                                            background: isActive ? t.badgeBg : 'transparent',
                                            color: isActive ? t.text1 : t.text3,
                                            fontWeight: isActive ? 600 : 400,
                                          }}
                                        >
                                          <span className="truncate">{displayCampaignName(entry.campaign_name)}</span>
                                          {entry.received_at && (
                                            <span className="flex-shrink-0" style={{ color: t.text5 }}>{timeAgo(entry.received_at)}</span>
                                          )}
                                        </button>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                            ) : (
                              <span className="truncate">{displayCampaignName(reply.campaign_name)}</span>
                            )}
                          </div>
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
                          <div className="mt-1.5 mb-2">
                            <ConversationThread
                              messages={thread ? adaptReplyThread(thread) : []}
                              compact
                              isDark={isDark}
                              loading={isThreadLoading}
                            />
                          </div>
                        )}
                      </div>

                      <div className="mx-4" style={{ borderTop: `1px solid ${t.divider}` }} />

                      {/* Draft -- always visible, NO max-height */}
                      <div className="px-4 py-2.5">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-[11px] uppercase tracking-wider" style={{ color: draftFailed ? t.errorText : t.text5 }}>
                            {draftFailed ? 'Draft (failed)' : 'Draft'}
                          </span>
                          {!isEditing && reply.draft_reply ? (
                            <button
                              onClick={() => startEditing(reply)}
                              className="text-[11px] flex items-center gap-1 transition-colors"
                              style={{ color: draftFailed ? t.errorText : t.text5, fontWeight: draftFailed ? 500 : 400 }}
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
                            onKeyDown={e => {
                              if (e.key === 'Escape') { cancelEditing(reply.id); }
                            }}
                            className="w-full text-[13px] rounded p-2.5 focus:outline-none min-h-[80px] resize-y border"
                            style={{
                              background: t.draftBg,
                              borderColor: t.draftBorder,
                              color: t.text1,
                            }}
                            placeholder="Edit your reply..."
                          />
                        ) : draftFailed ? (
                          <div
                            className="text-[13px] leading-relaxed rounded p-2.5 border flex items-start gap-2"
                            style={{ background: t.errorBg, borderColor: t.errorBorder, color: t.errorText }}
                          >
                            <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                            <div className="flex-1">
                              <div className="font-medium mb-0.5">Draft generation failed</div>
                              <div className="text-[12px] opacity-80">
                                AI could not generate a reply. Edit manually or skip this reply.
                              </div>
                            </div>
                            <button
                              onClick={() => handleRegenerate(reply)}
                              disabled={regeneratingIds.has(reply.id)}
                              className="flex items-center gap-1 px-2.5 py-1 rounded text-[12px] font-medium transition-colors flex-shrink-0"
                              style={{
                                background: t.btnPrimaryBg,
                                color: t.btnPrimaryText,
                                opacity: regeneratingIds.has(reply.id) ? 0.7 : 1,
                              }}
                            >
                              <RefreshCw className={cn("w-3.5 h-3.5", regeneratingIds.has(reply.id) && "animate-spin")} />
                              {regeneratingIds.has(reply.id) ? 'Regenerating...' : 'Regenerate'}
                            </button>
                          </div>
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
                          disabled={isSending || !reply.draft_reply || (draftFailed && !isEditing)}
                          className={cn(
                            "flex items-center gap-1.5 px-3.5 py-1.5 rounded text-[13px] font-medium transition-all",
                            isSending ? "cursor-wait" : "active:scale-[0.98]"
                          )}
                          style={{
                            background: (isSending || (draftFailed && !isEditing)) ? t.divider : t.btnPrimaryBg,
                            color: (isSending || (draftFailed && !isEditing)) ? t.text5 : t.btnPrimaryText,
                            opacity: (draftFailed && !isEditing) ? 0.5 : 1,
                          }}
                          onMouseEnter={e => {
                            if (!isSending && !(draftFailed && !isEditing)) {
                              (e.currentTarget as HTMLElement).style.background = t.btnPrimaryHover;
                            }
                          }}
                          onMouseLeave={e => {
                            (e.currentTarget as HTMLElement).style.background =
                              (isSending || (draftFailed && !isEditing)) ? t.divider : t.btnPrimaryBg;
                          }}
                        >
                          {isSending ? (
                            <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> {reply.channel === 'linkedin' ? 'Approving...' : 'Sending...'}</>
                          ) : (
                            <><ArrowRight className="w-3.5 h-3.5" /> {reply.channel === 'linkedin'
                              ? (isEditing ? 'Approve edited' : 'Approve')
                              : (isEditing ? 'Send edited' : 'Send')
                            }{(reply.contact_campaign_count ?? 0) > 1 && reply.campaign_name
                              ? ` via ${displayCampaignName(reply.campaign_name)}`
                              : ''
                            }</>
                          )}
                        </button>
                        <button
                          onClick={() => handleDismiss(reply)}
                          disabled={isSending}
                          className="flex items-center gap-1 px-3 py-1.5 rounded text-[13px] transition-all active:scale-[0.98]"
                          style={{ color: t.text4 }}
                          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = t.btnGhostHover; }}
                          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
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
                                <div className="text-[13px] font-medium flex items-center gap-1.5" style={{ color: classificationFailed ? t.warnText : t.text1 }}>
                                  {classificationFailed && <AlertTriangle className="w-3.5 h-3.5" />}
                                  {CATEGORY_LABEL[reply.category] || reply.category}
                                </div>
                              </div>
                            )}

                            {reply.classification_reasoning && (
                              <div>
                                <div className="text-[10px] uppercase tracking-wider mb-0.5" style={{ color: t.text5 }}>
                                  {classificationFailed ? 'Error' : 'Reasoning'}
                                </div>
                                <div
                                  className="text-[12px] leading-relaxed whitespace-pre-wrap"
                                  style={{ color: classificationFailed ? t.warnText : t.text3 }}
                                >
                                  {reply.classification_reasoning}
                                </div>
                              </div>
                            )}
                          </>
                        )}

                        {/* Contact section — always show email, extras from contactInfo */}
                        <>
                          {hasReasoning && <div className="my-2.5" style={{ borderTop: `1px solid ${t.divider}` }} />}
                          <div className="flex items-center gap-1.5 mb-2">
                            <User className="w-3.5 h-3.5" style={{ color: t.text4 }} />
                            <span className="text-[11px] font-medium uppercase tracking-wider" style={{ color: t.text4 }}>
                              Contact
                            </span>
                          </div>

                          {reply.lead_email && (
                            <div className="mb-1.5 flex items-center gap-1 text-[12px]" style={{ color: t.text3 }}>
                              <Mail className="w-3 h-3 flex-shrink-0" />
                              <span>{reply.lead_email}</span>
                            </div>
                          )}

                          {contactInfo?.linkedin_url && (
                            <div className="mb-1.5 flex items-center justify-between">
                              <a
                                href={contactInfo.linkedin_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-1.5 text-[12px] hover:underline"
                                style={{ color: '#0a66c2' }}
                              >
                                <Linkedin className="w-3.5 h-3.5" /> LinkedIn profile
                              </a>
                              <button
                                onClick={() => {
                                  navigator.clipboard.writeText(contactInfo!.linkedin_url!);
                                  toast.success('LinkedIn URL copied', { style: toastOk });
                                }}
                                className="p-0.5 rounded transition-colors"
                                style={{ color: t.text5 }}
                                title="Copy LinkedIn URL"
                              >
                                <Copy className="w-3 h-3" />
                              </button>
                            </div>
                          )}

                          {contactInfo?.job_title && (
                            <div className="mb-1.5 text-[12px]" style={{ color: t.text2 }}>
                              {contactInfo.job_title}
                            </div>
                          )}

                          {(contactInfo?.company_name || contactInfo?.domain) && (
                            <div className="mb-1.5 flex items-center gap-1 text-[12px]" style={{ color: t.text3 }}>
                              <Building2 className="w-3 h-3 flex-shrink-0" />
                              <span>
                                {contactInfo.company_name}
                                {contactInfo.domain && (
                                  <>
                                    {contactInfo.company_name ? ' · ' : ''}
                                    <a
                                      href={`https://${contactInfo.domain}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="hover:underline"
                                      style={{ color: t.text3 }}
                                    >
                                      {contactInfo.domain}
                                    </a>
                                  </>
                                )}
                              </span>
                            </div>
                          )}

                          {contactInfo?.location && (
                            <div className="mb-1.5 flex items-center gap-1 text-[12px]" style={{ color: t.text3 }}>
                              <MapPin className="w-3 h-3 flex-shrink-0" />
                              <span>{contactInfo.location}</span>
                            </div>
                          )}

                          {contactInfo?.segment && (
                            <div className="mb-1.5">
                              <span
                                className="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded"
                                style={{ background: t.badgeBg, color: t.badgeText }}
                              >
                                <Tag className="w-3 h-3" />{contactInfo.segment}
                              </span>
                            </div>
                          )}

                          {contactInfo?.phone && (
                            <div className="mb-1.5 flex items-center gap-1 text-[12px]" style={{ color: t.text3 }}>
                              <Phone className="w-3 h-3 flex-shrink-0" />
                              <span>{contactInfo.phone}</span>
                            </div>
                          )}
                        </>
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
