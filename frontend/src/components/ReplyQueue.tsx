import toast, { Toaster } from 'react-hot-toast';
import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
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
  type ReplyCategory,
  type ContactInfo,
  type FullHistoryResponse,
} from '../api/replies';
import { cn } from '../lib/utils';
import { stripHtml } from '../lib/htmlUtils';
import { themeColors } from '../lib/themeColors';
import { ConversationThread, adaptContactHistory } from './ConversationThread';
import { CampaignDropdown } from './CampaignDropdown';
import { useAppStore } from '../store/appStore';

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

/* ---------- Campaign name display ---------- */
function displayCampaignName(name: string | null | undefined): string {
  if (!name) return 'Unknown';
  let clean = name
    .replace(/\s+[0-9a-f]{6,}$/i, '')
    .replace(/\s+\S+@\S+\.\S+$/i, '')
    .trim();
  if (clean.length > 30) clean = clean.slice(0, 27) + '...';
  return clean || name;
}

/* ---------- Draft / classification failure detection ---------- */
const FAILED_DRAFT_RE = /^\{?(Draft generation failed|Error generating)/i;
const FAILED_CLASS_RE = /Classification failed|failed after \d+ attempts/i;

function isDraftFailed(draft: string | null | undefined): boolean {
  return !!draft && FAILED_DRAFT_RE.test(draft.trim());
}

/* ---------- Props ---------- */
export interface ReplyQueueProps {
  isDark: boolean;
  campaignNames?: string;
  onCountsChange?: (categoryCounts: Record<string, number>, total: number) => void;
}

const CATEGORY_FILTERS = [
  { key: null, label: 'All need reply', countKey: null },
  { key: 'meeting_request', label: 'Meetings', countKey: 'meeting_request' },
  { key: 'interested', label: 'Interested', countKey: 'interested' },
  { key: 'question', label: 'Questions', countKey: 'question' },
  { key: 'other', label: 'Other', countKey: 'other' },
] as const;

export function ReplyQueue({ isDark, campaignNames, onCountsChange }: ReplyQueueProps) {
  const { currentProject } = useAppStore();
  const t = themeColors(isDark);
  const navigate = useNavigate();

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
  const [loadingThreads, setLoadingThreads] = useState<Set<number>>(new Set());
  const [contactInfoMap, setContactInfoMap] = useState<Record<number, ContactInfo | null>>({});
  const [regeneratingIds, setRegeneratingIds] = useState<Set<number>>(new Set());

  const [historyData, setHistoryData] = useState<Record<number, FullHistoryResponse>>({});
  const [selectedHistoryCampaign, setSelectedHistoryCampaign] = useState<Record<number, string | null>>({});
  const [confirmSendId, setConfirmSendId] = useState<number | null>(null);

  const [expandedCampaigns, setExpandedCampaigns] = useState<Set<string>>(new Set());

  const scrollRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const toastOk = { background: t.toastBg, color: t.toastText, border: `1px solid ${t.toastBorder}` };
  const toastErr = { background: t.toastBg, color: t.toastErrText, border: `1px solid ${t.toastBorder}` };

  /* ---- Notify parent of counts ---- */
  useEffect(() => {
    onCountsChange?.(categoryCounts, total);
  }, [categoryCounts, total]); // eslint-disable-line react-hooks/exhaustive-deps

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
        campaign_names: campaignNames,
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
  }, [currentProject, categoryFilter, campaignNames]);

  useEffect(() => { loadReplies(true); }, [loadReplies]);

  /* ---- Auto-refresh: poll for new replies every 30s ---- */
  const [newCount, setNewCount] = useState(0);
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const resp = await repliesApi.getReplies({
          project_id: currentProject?.id,
          campaign_names: campaignNames,
          needs_reply: true,
          category: (categoryFilter as ReplyCategory) || undefined,
          group_by_contact: true,
          page: 1,
          page_size: 1,
        });
        const serverTotal = resp.total || 0;
        setCategoryCounts(resp.category_counts || {});
        if (serverTotal > total && total > 0) {
          setNewCount(serverTotal - total);
        } else if (serverTotal !== total) {
          setTotal(serverTotal);
        }
      } catch { /* silent */ }
    }, 30_000);
    return () => clearInterval(interval);
  }, [currentProject, categoryFilter, campaignNames, total]);

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

  const guardSend = (reply: ProcessedReply) => {
    const selKey = selectedHistoryCampaign[reply.id];
    if (selKey && reply.campaign_name) {
      const viewedCampaign = selKey.split('::').slice(1).join('::');
      if (viewedCampaign && viewedCampaign !== reply.campaign_name) {
        setConfirmSendId(reply.id);
        return;
      }
    }
    handleApproveAndSend(reply);
  };

  const handleApproveAndSend = async (reply: ProcessedReply) => {
    setConfirmSendId(null);
    setSendingIds(prev => new Set(prev).add(reply.id));
    try {
      const edited = editingDrafts[reply.id];
      const editedDraft = edited ? { draft_reply: edited.reply, draft_subject: edited.subject } : undefined;
      const result = await repliesApi.approveAndSendReply(reply.id, editedDraft);
      const sentContent = edited ? edited.reply : (reply.draft_reply || '');
      if (sentContent && historyData[reply.id]) {
        setHistoryData(prev => {
          const existing = prev[reply.id];
          if (!existing) return prev;
          return {
            ...prev,
            [reply.id]: {
              ...existing,
              activities: [
                ...existing.activities,
                {
                  direction: 'outbound' as const,
                  content: sentContent,
                  timestamp: new Date().toISOString(),
                  channel: (reply.channel || 'email') as 'email' | 'linkedin',
                  campaign: reply.campaign_name || 'Unknown',
                },
              ],
            },
          };
        });
      }
      const contactId = result.contact_id;
      const toastMsg = result.channel === 'linkedin'
        ? (result.getsales_sent ? 'Sent via LinkedIn' : (result.send_error ? `Approved (send failed)` : 'Approved — copy draft to LinkedIn'))
        : 'Reply sent';
      toast(
        (tInstance) => (
          <span style={{ color: t.toastText }}>
            {toastMsg}
            {contactId && (
              <>
                {' · '}
                <a
                  href={`/contacts?contact_id=${contactId}&campaign=${encodeURIComponent(`${reply.channel || 'email'}::${reply.campaign_name || ''}`)}`}
                  onClick={(e) => {
                    e.preventDefault();
                    toast.dismiss(tInstance.id);
                    navigate(`/contacts?contact_id=${contactId}&campaign=${encodeURIComponent(`${reply.channel || 'email'}::${reply.campaign_name || ''}`)}`);
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
      optimisticRemoveReply(reply);
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
      optimisticRemoveReply(reply);
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

  const optimisticRemoveReply = (reply: ProcessedReply) => {
    setReplies(prev => prev.filter(r => r.id !== reply.id));
    setTotal(prev => Math.max(0, prev - 1));
    setCategoryCounts(prev => {
      const cat = reply.category || 'other';
      return { ...prev, [cat]: Math.max(0, (prev[cat] || 0) - 1) };
    });
    refreshCounts();
  };

  const loadHistory = async (reply: ProcessedReply) => {
    if (expandedThreads.has(reply.id)) {
      setExpandedThreads(prev => { const s = new Set(prev); s.delete(reply.id); return s; });
      return;
    }
    setExpandedThreads(prev => new Set(prev).add(reply.id));
    if (historyData[reply.id]) return;
    setLoadingThreads(prev => new Set(prev).add(reply.id));
    try {
      const data = await repliesApi.getFullHistory(reply.id);
      setHistoryData(prev => ({ ...prev, [reply.id]: data }));
      if (data.campaigns.length > 0) {
        const mostRecent = data.campaigns[0];
        setSelectedHistoryCampaign(prev => ({
          ...prev,
          [reply.id]: `${mostRecent.channel}::${mostRecent.campaign_name}`,
        }));
      }
      if (data.contact_info !== undefined) {
        setContactInfoMap(prev => ({ ...prev, [reply.id]: data.contact_info || null }));
      }
      if (data.approval_status === 'replied_externally') {
        toast.success('Operator already replied — removed from queue', { style: toastOk });
        optimisticRemoveReply(reply);
      }
    } catch {
      setExpandedThreads(prev => { const s = new Set(prev); s.delete(reply.id); return s; });
    } finally {
      setLoadingThreads(prev => { const s = new Set(prev); s.delete(reply.id); return s; });
    }
  };

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
        {/* Category filter tabs with counts */}
        <div className="flex items-center gap-1">
          {CATEGORY_FILTERS.map(f => {
            const active = categoryFilter === f.key;
            const count = getTabCount(f.countKey);
            return (
              <button
                key={f.key ?? 'all'}
                onClick={() => setCategoryFilter(f.key)}
                className={cn("px-2.5 py-1 rounded text-[12px] transition-colors cursor-pointer", active ? "font-medium" : "")}
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

      {/* New replies banner */}
      {newCount > 0 && (
        <div
          className="mx-4 mt-1 mb-0 flex items-center justify-between px-3 py-1.5 rounded-md cursor-pointer text-[12px] font-medium"
          style={{ background: isDark ? '#1a3a2a' : '#dcfce7', color: isDark ? '#4ade80' : '#166534', border: `1px solid ${isDark ? '#22543d' : '#bbf7d0'}` }}
          onClick={() => { setNewCount(0); loadReplies(true); }}
        >
          <span>{newCount} new {newCount === 1 ? 'reply' : 'replies'} — click to load</span>
          <RefreshCw className="w-3 h-3" />
        </div>
      )}

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
              const history = historyData[reply.id];
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
                            {(() => {
                              const selKey = selectedHistoryCampaign[reply.id];
                              const selCampName = selKey ? selKey.split('::').slice(1).join('::') : null;
                              const inboxUrl = (selCampName && history?.inbox_links?.[selCampName])
                                || reply.inbox_link
                                || (reply.campaign_name && history?.inbox_links?.[reply.campaign_name])
                                || (history?.inbox_links && Object.values(history.inbox_links)[0])
                                || null;
                              const isLinkedin = reply.channel === 'linkedin';
                              const platform = isLinkedin ? 'GetSales' : 'SmartLead';
                              return inboxUrl ? (
                                <a
                                  href={inboxUrl}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="transition-colors"
                                  title={selCampName ? `Open ${selCampName} in ${platform}` : `Open in ${platform}`}
                                  onClick={e => e.stopPropagation()}
                                  style={{ color: t.text5 }}
                                >
                                  <ExternalLink className="w-3 h-3" />
                                </a>
                              ) : null;
                            })()}
                          </div>
                        </div>

                        {reply.campaign_name && (
                          <div className="px-4 text-[11px] pb-1 truncate" style={{ color: t.text6 }}>
                            {displayCampaignName(reply.campaign_name)}
                          </div>
                        )}
                        <div style={{ borderBottom: `1px solid ${t.divider}` }} />
                      </div>

                      {/* Their message */}
                      <div className="px-4 py-2">
                        {reply.email_subject && (
                          <div className="text-[13px] mb-1" style={{ color: t.text2 }}>{reply.email_subject}</div>
                        )}
                        <div
                          className="text-[13px] leading-relaxed whitespace-pre-wrap break-words"
                          style={{ color: t.text3 }}
                        >
                          {stripHtml(reply.email_body || reply.reply_text || '') || '(empty)'}
                        </div>
                      </div>

                      {/* History */}
                      <div className="px-4">
                        <button
                          onClick={() => loadHistory(reply)}
                          className="text-[11px] flex items-center gap-1 py-0.5 transition-colors cursor-pointer"
                          style={{ color: t.text5 }}
                        >
                          <MessageCircle className="w-3 h-3" />
                          {isThreadOpen ? 'Hide history' : 'History'}
                        </button>
                        {isThreadOpen && (
                          <div className="mt-1.5 mb-2">
                            {history && history.campaigns.length > 1 && (
                              <div className="mb-1.5">
                                <CampaignDropdown
                                  campaigns={history.campaigns}
                                  selectedCampaign={selectedHistoryCampaign[reply.id] ?? null}
                                  onSelect={(c) => setSelectedHistoryCampaign(prev => ({ ...prev, [reply.id]: c }))}
                                  isDark={isDark}
                                />
                              </div>
                            )}
                            <ConversationThread
                              messages={history ? adaptContactHistory(history.activities) : []}
                              compact
                              isDark={isDark}
                              showDateSeparators
                              showCampaignMarkers={false}
                              filterCampaign={selectedHistoryCampaign[reply.id] ?? null}
                              loading={isThreadLoading}
                            />
                          </div>
                        )}
                      </div>

                      <div className="mx-4" style={{ borderTop: `1px solid ${t.divider}` }} />

                      {/* Draft */}
                      <div className="px-4 py-2.5">
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-[11px] uppercase tracking-wider" style={{ color: draftFailed ? t.errorText : t.text5 }}>
                            {draftFailed ? 'Draft (failed)' : 'Draft'}
                          </span>
                          {!isEditing && reply.draft_reply ? (
                            <button
                              onClick={() => startEditing(reply)}
                              className="text-[11px] flex items-center gap-1 transition-colors cursor-pointer"
                              style={{ color: draftFailed ? t.errorText : t.text5, fontWeight: draftFailed ? 500 : 400 }}
                            >
                              <Edit3 className="w-3 h-3" /> Edit
                            </button>
                          ) : isEditing ? (
                            <button
                              onClick={() => cancelEditing(reply.id)}
                              className="text-[11px] flex items-center gap-1 transition-colors cursor-pointer"
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

                      {/* Cross-campaign safety modal */}
                      {confirmSendId === reply.id && (() => {
                        const selKey = selectedHistoryCampaign[reply.id];
                        const viewedCampaign = selKey ? selKey.split('::').slice(1).join('::') : null;
                        const mostRecentCampaign = reply.campaign_name || '';
                        return (
                          <div
                            className="fixed inset-0 z-[100] flex items-center justify-center"
                            style={{ background: 'rgba(0,0,0,0.5)' }}
                            onClick={() => setConfirmSendId(null)}
                          >
                            <div
                              className="rounded-xl shadow-2xl p-5 max-w-[400px] w-full mx-4"
                              style={{ background: t.cardBg, color: t.text1 }}
                              onClick={e => e.stopPropagation()}
                            >
                              <div className="flex items-center gap-2 mb-3">
                                <AlertTriangle className="w-5 h-5" style={{ color: isDark ? '#fbbf24' : '#f59e0b' }} />
                                <h3 className="text-[15px] font-semibold">Sending to a different campaign</h3>
                              </div>
                              <p className="text-[13px] mb-4" style={{ color: t.text3 }}>
                                You're viewing <strong style={{ color: t.text1 }}>{displayCampaignName(viewedCampaign || '')}</strong> but this reply will be sent via <strong style={{ color: t.text1 }}>{displayCampaignName(mostRecentCampaign)}</strong>.
                              </p>
                              <div className="flex flex-col gap-2">
                                <button
                                  onClick={() => {
                                    setSelectedHistoryCampaign(prev => ({
                                      ...prev,
                                      [reply.id]: `${reply.channel || 'email'}::${mostRecentCampaign}`,
                                    }));
                                    handleApproveAndSend(reply);
                                  }}
                                  className="w-full px-3 py-2 rounded-lg text-[13px] font-medium cursor-pointer transition-opacity hover:opacity-90"
                                  style={{ background: t.btnPrimaryBg, color: t.btnPrimaryText }}
                                >
                                  Switch to {displayCampaignName(mostRecentCampaign)} and send
                                </button>
                                <button
                                  onClick={() => handleApproveAndSend(reply)}
                                  className="w-full px-3 py-2 rounded-lg text-[13px] cursor-pointer transition-opacity hover:opacity-80"
                                  style={{ background: isDark ? '#3a3a3a' : '#e5e7eb', color: t.text3 }}
                                >
                                  Send in {displayCampaignName(viewedCampaign || '')} anyway
                                </button>
                                <button
                                  onClick={() => setConfirmSendId(null)}
                                  className="w-full px-3 py-1.5 text-[12px] cursor-pointer"
                                  style={{ color: t.text5 }}
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          </div>
                        );
                      })()}

                      {/* Actions */}
                      <div
                        className="px-4 pb-3 pt-2 flex items-center gap-1.5"
                        style={{ position: 'sticky', bottom: 0, zIndex: 10, background: t.cardBg, borderTop: `1px solid ${t.divider}` }}
                      >
                        <button
                          onClick={() => guardSend(reply)}
                          disabled={isSending || !reply.draft_reply || (draftFailed && !isEditing)}
                          className={cn(
                            "flex items-center gap-1.5 px-3.5 py-1.5 rounded text-[13px] font-medium transition-all",
                            isSending ? "cursor-wait" : "cursor-pointer active:scale-[0.98]"
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
                            <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Sending...</>
                          ) : (
                            <><ArrowRight className="w-3.5 h-3.5" /> {isEditing ? 'Send edited' : 'Send'
                            }{reply.campaign_name
                              ? ` via ${displayCampaignName(reply.campaign_name)}`
                              : ''
                            }</>
                          )}
                        </button>
                        <button
                          onClick={() => handleDismiss(reply)}
                          disabled={isSending}
                          className="flex items-center gap-1 px-3 py-1.5 rounded text-[13px] transition-all cursor-pointer active:scale-[0.98]"
                          style={{ color: t.text4 }}
                          onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = t.btnGhostHover; }}
                          onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
                        >
                          <XCircle className="w-3.5 h-3.5" /> Skip
                        </button>
                      </div>
                    </div>

                    {/* Right: AI reasoning + contact info sidebar */}
                    {(hasReasoning || contactInfo) && (
                      <div
                        className="w-64 flex-shrink-0 border-l px-3 py-3 overflow-hidden"
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

                        {/* Contact section */}
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
