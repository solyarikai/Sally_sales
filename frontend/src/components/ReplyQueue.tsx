import toast, { Toaster } from 'react-hot-toast';
import { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Search, RefreshCw, X,
  Building2, ExternalLink, Link2,
  XCircle, Edit3, AlertTriangle,
  Clock, MessageCircle, ArrowRight, Brain, Command, Loader2,
  Linkedin, Phone, MapPin, Tag, User, Copy, Mail, Download, FileText, Languages,
  CalendarClock,
} from 'lucide-react';
import {
  repliesApi,
  type ProcessedReply,
  type ReplyCategory,
  type ContactInfo,
  type FullHistoryResponse,
  type CalendlyMember,
} from '../api/replies';
import { knowledgeApi, type KnowledgeEntry } from '../api/knowledge';
import { getLearningStatus } from '../api/learning';
import { cn } from '../lib/utils';
import { stripHtml } from '../lib/htmlUtils';
import { themeColors } from '../lib/themeColors';
import { ConversationThread, adaptContactHistory } from './ConversationThread';
import { CampaignDropdown } from './CampaignDropdown';
import { useAppStore } from '../store/appStore';

/* ---------- Clipboard fallback for non-HTTPS ---------- */
function fallbackCopy(text: string) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  document.execCommand('copy');
  document.body.removeChild(ta);
}

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
  const clean = name
    .replace(/\s+[0-9a-f]{6,}$/i, '')
    .replace(/\s+\S+@\S+\.\S+$/i, '')
    .trim();
  return clean || name;
}

/* ---------- Draft / classification failure detection ---------- */
const FAILED_DRAFT_RE = /^\{?(Draft generation failed|Error generating)/i;
const FAILED_CLASS_RE = /Classification failed|failed after \d+ attempts/i;

function isDraftFailed(draft: string | null | undefined): boolean {
  return !!draft && FAILED_DRAFT_RE.test(draft.trim());
}

/* ---------- Document relevance detection ---------- */
const DOC_REQUEST_RE = /презентац|presentation|прайс|price.?list|тариф|tarif|условия|condition|pdf|документ|document|материал|material|скиньте|пришлите|отправьте|send.*info|send.*detail|ознакомить|брошюр|brochure|каталог|catalog/i;

function leadsAsksForDocs(reply: ProcessedReply): boolean {
  const text = [reply.reply_text, reply.email_body].filter(Boolean).join(' ');
  return DOC_REQUEST_RE.test(text);
}

/* ---------- Staleness detection ---------- */
function isReplyStale(reply: ProcessedReply, knowledgeUpdatedAt: string | null): boolean {
  if (!knowledgeUpdatedAt || !reply.draft_generated_at || !reply.draft_reply) return false;
  return new Date(reply.draft_generated_at) < new Date(knowledgeUpdatedAt);
}

/* ---------- Props ---------- */
export interface ReplyQueueProps {
  isDark: boolean;
  campaignNames?: string;
  initialSearch?: string;
  mode?: 'replies' | 'followups';
  onCountsChange?: (categoryCounts: Record<string, number>, total: number) => void;
}

// "All" shows everything (no needs_reply filter). Actionable tabs use needs_reply=true.
const ALL_TAB = { key: '__all__', label: 'All', countKey: '__all__' } as const;

const ACTIONABLE_CATEGORY_FILTERS = [
  { key: 'meeting_request', label: 'Meetings', countKey: 'meeting_request' },
  { key: 'interested', label: 'Interested', countKey: 'interested' },
  { key: 'question', label: 'Questions', countKey: 'question' },
  { key: 'other', label: 'Other', countKey: 'other' },
] as const;

const ARCHIVE_CATEGORY_FILTERS = [
  { key: 'not_interested', label: 'Not Interested', countKey: 'not_interested' },
  { key: 'out_of_office',  label: 'OOO',            countKey: 'out_of_office' },
  { key: 'wrong_person',   label: 'Wrong Person',   countKey: 'wrong_person' },
  { key: 'unsubscribe',    label: 'Unsubscribe',    countKey: 'unsubscribe' },
] as const;

const ARCHIVE_KEYS = new Set<string>(ARCHIVE_CATEGORY_FILTERS.map(f => f.key));

const TIMING_OPTIONS = [
  { value: '1w', label: '1 week' },
  { value: '1m', label: '1 month' },
  { value: 'all', label: 'All time' },
] as const;

const VALID_CATEGORIES = new Set<string>([
  ALL_TAB.key,
  ...ACTIONABLE_CATEGORY_FILTERS.map(f => f.key),
  ...ARCHIVE_CATEGORY_FILTERS.map(f => f.key),
]);

export function ReplyQueue({ isDark, campaignNames, initialSearch, mode = 'replies', onCountsChange }: ReplyQueueProps) {
  const { currentProject } = useAppStore();
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

  const [search, setSearch] = useState(initialSearch || '');
  // Read category from URL ?category=interested, default to meeting_request
  const urlCategory = searchParams.get('category');
  const [categoryFilter, setCategoryFilterState] = useState(
    initialSearch ? '__all__' : (urlCategory && VALID_CATEGORIES.has(urlCategory) ? urlCategory : 'meeting_request')
  );
  // Sync category to URL when it changes
  const setCategoryFilter = useCallback((key: string) => {
    setCategoryFilterState(key);
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      if (key && key !== '__all__') next.set('category', key);
      else next.delete('category');
      return next;
    }, { replace: true });
  }, [setSearchParams]);
  // Timing filter state + URL sync
  const urlTiming = searchParams.get('timing');
  const [timingFilter, setTimingFilterState] = useState<string>(
    urlTiming && ['1w', '1m', 'all'].includes(urlTiming) ? urlTiming : (mode === 'followups' ? 'all' : '1w')
  );
  const setTimingFilter = useCallback((val: string) => {
    setTimingFilterState(val);
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      if (val && val !== '1w') next.set('timing', val);
      else next.delete('timing');
      return next;
    }, { replace: true });
  }, [setSearchParams]);
  // When opened via Telegram link (?lead=...), use server-side lead_email filter
  // and skip needs_reply/category/group_by_contact so the reply is always visible
  const isDeepLink = Boolean(initialSearch);

  const [allCounts, setAllCounts] = useState<Record<string, number>>({});
  const isArchiveMode = ARCHIVE_KEYS.has(categoryFilter);
  const isAllMode = categoryFilter === '__all__';

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
  const [projectDocs, setProjectDocs] = useState<KnowledgeEntry[]>([]);

  // Knowledge-driven draft staleness — on-demand regen when reply enters viewport
  // Only activates after a learning cycle completes during this session (never on initial load)
  const [knowledgeUpdatedAt, setKnowledgeUpdatedAt] = useState<string | null>(null);
  const [autoRegeneratingIds, setAutoRegeneratingIds] = useState<Set<number>>(new Set());
  const [justUpdatedIds, setJustUpdatedIds] = useState<Set<number>>(new Set());
  const everQueuedRef = useRef<Set<number>>(new Set());

  // Learning feedback polling
  const pendingLearning = useAppStore(s => s.pendingLearning);
  const setPendingLearning = useAppStore(s => s.setPendingLearning);
  const [learningBanner, setLearningBanner] = useState<string | null>(null);

  // Calendly time slots
  const [calendlyMembers, setCalendlyMembers] = useState<CalendlyMember[]>([]);
  const [hasCalendly, setHasCalendly] = useState(false);
  const [selectedCalendlyMember, setSelectedCalendlyMember] = useState<string>('');
  const [calendlySlots, setCalendlySlots] = useState<string[]>([]);
  const [calendlyPrompt, setCalendlyPrompt] = useState<string>('');
  const [calendlyLoading, setCalendlyLoading] = useState(false);
  const [calendlyFallback, setCalendlyFallback] = useState(false);

  // Follow-up drafts (stored in component state, not DB)
  const [followupDrafts, setFollowupDrafts] = useState<Record<number, { reply: string; subject: string }>>({});
  const [followupGenerating, setFollowupGenerating] = useState<Set<number>>(new Set());

  const scrollRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const toastOk = { background: t.toastBg, color: t.toastText, border: `1px solid ${t.toastBorder}` };
  const toastErr = { background: t.toastBg, color: t.toastErrText, border: `1px solid ${t.toastBorder}` };

  /* ---- Notify parent of counts ---- */
  useEffect(() => {
    onCountsChange?.(categoryCounts, total);
  }, [categoryCounts, total]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ---- Load project documents (knowledge files category) ---- */
  useEffect(() => {
    if (!currentProject) { setProjectDocs([]); return; }
    knowledgeApi.getByCategory(currentProject.id, 'files').then(
      res => setProjectDocs(res.entries || []),
      () => setProjectDocs([]),
    );
  }, [currentProject?.id]);

  /* ---- Load Calendly config for project ---- */
  useEffect(() => {
    if (!currentProject) { setHasCalendly(false); setCalendlyMembers([]); return; }
    repliesApi.getCalendlyConfig(currentProject.id).then(
      res => {
        setHasCalendly(res.has_calendly);
        setCalendlyMembers(res.members);
        const defaultMember = res.members.find(m => m.is_default) || res.members[0];
        if (defaultMember) setSelectedCalendlyMember(defaultMember.id);
      },
      () => { setHasCalendly(false); setCalendlyMembers([]); },
    );
  }, [currentProject?.id]);

  const fetchCalendlySlots = useCallback(async (memberId: string) => {
    if (!currentProject) return null;
    setCalendlyLoading(true);
    try {
      const data = await repliesApi.getCalendlySlots(currentProject.id, memberId);
      setCalendlySlots(data.slots_display);
      setCalendlyPrompt(data.formatted_for_prompt);
      setCalendlyFallback(data.is_fallback);
      return data;
    } catch {
      setCalendlySlots([]);
      setCalendlyPrompt('');
      return null;
    } finally {
      setCalendlyLoading(false);
    }
  }, [currentProject?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Track which replies already got calendly auto-regen (prevent infinite loops)
  const calendlyRegenRef = useRef<Set<number>>(new Set());

  // Auto-fetch slots when meeting/interested tab is active and we have calendly
  useEffect(() => {
    if (!hasCalendly || !selectedCalendlyMember) return;
    if (categoryFilter !== 'meeting_request' && categoryFilter !== 'interested') return;
    fetchCalendlySlots(selectedCalendlyMember);
  }, [hasCalendly, selectedCalendlyMember, categoryFilter, fetchCalendlySlots]);

  // Auto-regen drafts that don't have slots yet (once slots are loaded)
  useEffect(() => {
    if (!calendlyPrompt || !hasCalendly) return;
    if (categoryFilter !== 'meeting_request' && categoryFilter !== 'interested') return;

    // Find meeting/interested replies without slot-like text in their draft
    const slotPattern = /\d{2}\.\d{2}\s+с\s+\d{1,2}:\d{2}/;
    const needsRegen = replies.filter(r =>
      (r.category === 'meeting_request' || r.category === 'interested') &&
      r.draft_reply &&
      !slotPattern.test(r.draft_reply) &&
      !calendlyRegenRef.current.has(r.id) &&
      !regeneratingIds.has(r.id)
    );

    if (needsRegen.length === 0) return;

    // Regen sequentially to avoid API overload — first visible one
    const first = needsRegen[0];
    calendlyRegenRef.current.add(first.id);
    handleRegenerate(first, calendlyPrompt);
  }, [calendlyPrompt, hasCalendly, replies, categoryFilter]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ---- Learning feedback polling ---- */
  useEffect(() => {
    if (!pendingLearning || !currentProject || pendingLearning.projectId !== currentProject.id) return;
    setLearningBanner('AI is processing your feedback...');
    let cancelled = false;
    const poll = setInterval(async () => {
      try {
        const status = await getLearningStatus(pendingLearning.projectId, pendingLearning.logId);
        if (cancelled) return;
        if (status.status === 'completed') {
          clearInterval(poll);
          setLearningBanner('Knowledge updated! Drafts will regenerate as you scroll.');
          // Refresh knowledge timestamp to trigger staleness detection → auto-regen
          knowledgeApi.getKnowledgeTimestamp(currentProject.id)
            .then(res => setKnowledgeUpdatedAt(res.knowledge_updated_at))
            .catch(() => {});
          setPendingLearning(null);
          setTimeout(() => setLearningBanner(null), 3000);
        } else if (status.status === 'failed') {
          clearInterval(poll);
          setLearningBanner('Feedback processing failed');
          setPendingLearning(null);
          setTimeout(() => setLearningBanner(null), 3000);
        }
      } catch {
        // silent — keep polling
      }
    }, 2000);
    return () => { cancelled = true; clearInterval(poll); };
  }, [pendingLearning?.logId, currentProject?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ---- Knowledge timestamp tracking ---- */
  // Don't load on mount — only set after a learning cycle completes during this session
  useEffect(() => {
    if (!currentProject) { setKnowledgeUpdatedAt(null); }
  }, [currentProject?.id]);

  /* ---- On-demand auto-regen: regenerate stale drafts when they enter viewport ---- */
  const regenObserverRef = useRef<IntersectionObserver | null>(null);
  const observedNodesRef = useRef<Set<HTMLDivElement>>(new Set());

  // Create observer — only active when knowledgeUpdatedAt is set (after learning cycle completes)
  useEffect(() => {
    regenObserverRef.current?.disconnect();
    if (!knowledgeUpdatedAt) return;

    regenObserverRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const replyId = Number((entry.target as HTMLElement).dataset.replyId);
          if (!replyId || everQueuedRef.current.has(replyId)) continue;

          // Check if this reply is stale
          const reply = replies.find(r => r.id === replyId);
          if (!reply || !isReplyStale(reply, knowledgeUpdatedAt)) continue;

          everQueuedRef.current.add(replyId);
          setAutoRegeneratingIds(prev => new Set(prev).add(replyId));

          repliesApi.regenerateDraft(replyId).then(result => {
            setReplies(prev => prev.map(r => {
              if (r.id !== replyId) return r;
              return {
                ...r,
                draft_reply: result.draft_reply,
                draft_subject: result.draft_subject,
                draft_generated_at: result.draft_generated_at,
                translated_draft: result.translated_draft ?? r.translated_draft,
                category: result.category as ProcessedReply['category'],
                classification_reasoning: result.classification_reasoning,
              };
            }));
            setAutoRegeneratingIds(prev => { const s = new Set(prev); s.delete(replyId); return s; });
            setJustUpdatedIds(prev => new Set(prev).add(replyId));
            setTimeout(() => setJustUpdatedIds(prev => { const s = new Set(prev); s.delete(replyId); return s; }), 3000);
          }).catch(() => {
            setAutoRegeneratingIds(prev => { const s = new Set(prev); s.delete(replyId); return s; });
          });
        }
      },
      { root: scrollRef.current, rootMargin: '0px' }
    );

    // Re-observe all tracked nodes
    for (const node of observedNodesRef.current) {
      regenObserverRef.current.observe(node);
    }

    return () => regenObserverRef.current?.disconnect();
  }, [knowledgeUpdatedAt, replies]); // eslint-disable-line react-hooks/exhaustive-deps

  const observeReplyCard = useCallback((node: HTMLDivElement | null) => {
    if (!node) return;
    observedNodesRef.current.add(node);
    regenObserverRef.current?.observe(node);
  }, []);

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
      // "All" tab: no needs_reply, no category filter — shows everything
      // Archive tabs: no needs_reply, specific category filter
      // Actionable tabs: needs_reply=true, specific category filter (or all actionable if none)
      const useNeedsReply = isDeepLink ? undefined : (isAllMode || isArchiveMode ? undefined : true);
      const useCategory = isDeepLink ? undefined :
        (isAllMode ? undefined : (categoryFilter as ReplyCategory) || undefined);
      const response = await repliesApi.getReplies({
        project_id: currentProject?.id,
        campaign_names: campaignNames,
        needs_reply: mode === 'followups' ? undefined : useNeedsReply,
        needs_followup: mode === 'followups' ? true : undefined,
        lead_email: isDeepLink ? initialSearch : undefined,
        category: mode === 'followups' ? undefined : useCategory,
        group_by_contact: true,
        received_since: isDeepLink ? 'all' : timingFilter,
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
      // Actionable tab counts come from the reply list response (needs_reply=true context).
      // All/archive modes have different filter contexts, so only update from actionable tabs.
      if (!isArchiveMode && !isAllMode) {
        setCategoryCounts(response.category_counts || {});
      }
      setHasMore(newReplies.length >= PAGE_SIZE);
    } catch (err) {
      console.error('Failed to load replies:', err);
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, [currentProject, categoryFilter, campaignNames, timingFilter]);

  useEffect(() => { loadReplies(true); }, [loadReplies]);

  /* ---- Eagerly load contact info for visible replies ---- */
  useEffect(() => {
    if (!replies.length) return;
    const needInfo = replies.filter(r => !(r.id in contactInfoMap));
    if (!needInfo.length) return;
    const emails = [...new Set(needInfo.map(r => r.lead_email).filter(Boolean))];
    if (!emails.length) return;
    repliesApi.getContactInfoBatch(emails).then(byEmail => {
      setContactInfoMap(prev => {
        const next = { ...prev };
        for (const r of needInfo) {
          if (!(r.id in next) && byEmail[r.lead_email]) {
            next[r.id] = byEmail[r.lead_email];
          }
        }
        return next;
      });
    }).catch(() => { /* silent */ });
  }, [replies]);

  /* ---- Auto-refresh: lightweight count poll every 30s (disabled for deep links) ---- */
  const [newCount, setNewCount] = useState(0);
  const allTotalRef = useRef(-1); // -1 = not yet initialized
  useEffect(() => {
    if (isDeepLink) return;
    let cancelled = false;
    // Reset baseline so a timing/project change doesn't produce a false "N new replies" banner
    allTotalRef.current = -1;
    setNewCount(0);

    const fetchCounts = async () => {
      try {
        const resp = await repliesApi.getReplyCounts({
          project_id: currentProject?.id,
          campaign_names: campaignNames,
          received_since: timingFilter,
          needs_followup: mode === 'followups' ? true : undefined,
        });
        if (cancelled) return;
        const serverTotal = resp.total || 0;
        setCategoryCounts(resp.category_counts || {});
        const prev = allTotalRef.current;
        allTotalRef.current = serverTotal;
        if (prev >= 0 && serverTotal > prev) {
          setNewCount(serverTotal - prev);
        }
      } catch { /* silent */ }
    };

    // Immediately establish baseline from /counts (same endpoint used for polling)
    fetchCounts();
    const interval = setInterval(fetchCounts, 30_000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [currentProject, campaignNames, isDeepLink, timingFilter, mode]);

  /* ---- Fetch all counts (include_all) — drives "All" tab total + archive tab counts ---- */
  useEffect(() => {
    if (isDeepLink) return;
    let cancelled = false;
    const fetchAllCounts = async () => {
      try {
        const resp = await repliesApi.getReplyCounts({
          project_id: currentProject?.id,
          campaign_names: campaignNames,
          received_since: timingFilter,
          include_all: true,
          needs_followup: mode === 'followups' ? true : undefined,
        });
        if (cancelled) return;
        setAllCounts(resp.category_counts || {});
      } catch { /* silent */ }
    };
    fetchAllCounts();
    const interval = setInterval(fetchAllCounts, 60_000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [currentProject, campaignNames, isDeepLink, timingFilter, mode]);

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
    if (isDeepLink) return;
    repliesApi.getReplyCounts({
      project_id: currentProject?.id,
      campaign_names: campaignNames,
      received_since: timingFilter,
      needs_followup: mode === 'followups' ? true : undefined,
    }).then(response => {
      setCategoryCounts(response.category_counts || {});
      setTotal(response.total || 0);
      allTotalRef.current = response.total || 0;
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
      {
        const replyChannel = reply.channel || (reply.source === 'getsales' ? 'linkedin' : 'email');
        const replyCampaign = reply.campaign_name || 'Unknown';
        setSelectedHistoryCampaign(prev => ({
          ...prev,
          [reply.id]: `${replyChannel}::${replyCampaign}`,
        }));
      }
      if (data.contact_info !== undefined) {
        setContactInfoMap(prev => ({ ...prev, [reply.id]: data.contact_info || null }));
      }
      // If history loading revealed operator already replied, remove from list
      if ((data as any).auto_dismissed) {
        setReplies(prev => prev.filter(r => r.id !== reply.id));
        setCategoryCounts(prev => {
          const cat = reply.category || 'other';
          return { ...prev, [cat]: Math.max(0, (prev[cat] || 0) - 1) };
        });
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

  const handleRegenerate = async (reply: ProcessedReply, calendlyCtx?: string) => {
    setRegeneratingIds(prev => new Set(prev).add(reply.id));
    try {
      const result = await repliesApi.regenerateDraft(reply.id, undefined, calendlyCtx);
      setReplies(prev => prev.map(r => {
        if (r.id !== reply.id) return r;
        return {
          ...r,
          draft_reply: result.draft_reply,
          draft_subject: result.draft_subject,
          draft_generated_at: result.draft_generated_at,
          translated_draft: result.translated_draft ?? r.translated_draft,
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

  const handleCalendlyMemberChange = async (reply: ProcessedReply, memberId: string) => {
    setSelectedCalendlyMember(memberId);
    const data = await fetchCalendlySlots(memberId);
    if (data?.formatted_for_prompt) {
      handleRegenerate(reply, data.formatted_for_prompt);
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

  // "All" tab count = sum of all categories from include_all endpoint
  // Actionable tab counts come from needs_reply=true counts
  // Archive tab counts come from include_all endpoint
  const allTotal = Object.values(allCounts).reduce((a, b) => a + b, 0);
  const getActionableCount = (countKey: string): number => categoryCounts[countKey] || 0;
  const getArchiveCount = (countKey: string): number => allCounts[countKey] || 0;

  /* ==================================================================== */
  return (
    <div className="h-full flex flex-col" style={{ background: t.pageBg }}>
      <Toaster position="top-center" />

      {/* Header bar */}
      <div
        className="border-b px-5 py-2.5 flex items-center gap-3"
        style={{ background: t.headerBg, borderColor: t.cardBorder }}
      >
        {/* Category tabs: All | actionable tabs | separator | archive tabs — hidden in followup mode */}
        <div className="flex items-center gap-1">
          {mode === 'followups' ? (
            <span className="px-2.5 py-1 rounded text-[12px] font-medium" style={{ background: t.btnPrimaryBg, color: t.btnPrimaryText }}>
              All{allTotal > 0 ? ` ${allTotal}` : ''}
            </span>
          ) : (
            <>
              {/* "All" tab */}
              <button
                onClick={() => setCategoryFilter('__all__')}
                className={cn("px-2.5 py-1 rounded text-[12px] transition-colors cursor-pointer", isAllMode ? "font-medium" : "")}
                style={{
                  background: isAllMode ? t.btnPrimaryBg : 'transparent',
                  color: isAllMode ? t.btnPrimaryText : t.text4,
                }}
              >
                All{allTotal > 0 ? ` ${allTotal}` : ''}
              </button>
              {/* Actionable category tabs (needs_reply) */}
              {ACTIONABLE_CATEGORY_FILTERS.map(f => {
                const active = categoryFilter === f.key;
                const count = getActionableCount(f.countKey);
                return (
                  <button
                    key={f.key}
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
              {/* Separator + archive tabs (always visible) */}
              <div className="w-px h-4 mx-1" style={{ background: t.cardBorder }} />
              {ARCHIVE_CATEGORY_FILTERS.map(f => {
                const count = getArchiveCount(f.countKey);
                const active = categoryFilter === f.key;
                return (
                  <button
                    key={f.key}
                    onClick={() => setCategoryFilter(f.key)}
                    className={cn("px-2.5 py-1 rounded text-[12px] transition-colors cursor-pointer", active ? "font-medium" : "")}
                    style={{
                      background: active ? (isDark ? '#4a3333' : '#fef2f2') : 'transparent',
                      color: active ? (isDark ? '#fca5a5' : '#b91c1c') : t.text5,
                    }}
                  >
                    {f.label}{count > 0 ? ` ${count}` : ''}
                  </button>
                );
              })}
            </>
          )}
        </div>

        <div className="flex-1" />

        <select
          value={timingFilter}
          onChange={e => { setTimingFilter(e.target.value); }}
          className="text-xs px-2 py-1 rounded border"
          style={{
            background: t.inputBg,
            color: t.text1,
            borderColor: t.cardBorder,
          }}
        >
          {TIMING_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>

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

        {currentProject && (
          <button
            onClick={() => document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }))}
            className="flex items-center gap-1 px-2 py-1 rounded text-[12px] transition-colors cursor-pointer"
            style={{ color: t.text4 }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = t.btnGhostHover; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
            title={`Feedback (${navigator.platform?.includes('Mac') ? '⌘' : 'Ctrl+'}K)`}
          >
            <Command className="w-3 h-3" />
            Feedback
          </button>
        )}

        <button
          onClick={() => loadReplies(true)}
          className="p-1.5 rounded transition-colors"
          title="Refresh"
        >
          <RefreshCw className={cn("w-3.5 h-3.5", isLoading && "animate-spin")} style={{ color: t.text4 }} />
        </button>
      </div>

      {/* Learning feedback banner */}
      {learningBanner && (
        <div
          className="mx-4 mt-1 mb-0 flex items-center gap-2 px-3 py-1.5 rounded-md text-[12px] font-medium"
          style={{
            background: isDark ? '#1a2a3a' : '#dbeafe',
            color: isDark ? '#60a5fa' : '#1e40af',
            border: `1px solid ${isDark ? '#1e3a5f' : '#93c5fd'}`,
          }}
        >
          <Loader2 className="w-3 h-3 animate-spin" />
          {learningBanner}
        </div>
      )}

      {/* New replies banner */}
      {newCount > 0 && (
        <div
          className="mx-4 mt-1 mb-0 flex items-center justify-between px-3 py-1.5 rounded-md cursor-pointer text-[12px] font-medium"
          style={{ background: isDark ? '#1a3a2a' : '#dcfce7', color: isDark ? '#4ade80' : '#166534', border: `1px solid ${isDark ? '#22543d' : '#bbf7d0'}` }}
          onClick={() => { setNewCount(0); allTotalRef.current = -1; loadReplies(true); }}
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
              const fuDraft = mode === 'followups' ? followupDrafts[reply.id] : undefined;
              const isFuGenerating = mode === 'followups' && followupGenerating.has(reply.id);
              const draftText = isEditing ? editingDrafts[reply.id].reply
                : (mode === 'followups' ? (fuDraft?.reply || '') : (reply.draft_reply || ''));
              const draftFailed = mode === 'followups' ? false : isDraftFailed(reply.draft_reply);
              const classificationFailed = FAILED_CLASS_RE.test(reply.classification_reasoning || '');
              const catLabel = CATEGORY_LABEL[reply.category || ''] || reply.category || '';
              const hasReasoning = !!reply.classification_reasoning;
              const contactInfo = contactInfoMap[reply.id];
              const isAutoRegen = autoRegeneratingIds.has(reply.id);
              const wasJustUpdated = justUpdatedIds.has(reply.id);
              return (
                <div
                  key={reply.id}
                  ref={observeReplyCard}
                  data-reply-id={reply.id}
                  className="rounded-md border transition-colors relative"
                  style={{
                    background: t.cardBg,
                    borderColor: t.cardBorder,
                  }}
                >
                  {/* Auto-regeneration overlay */}
                  {isAutoRegen && (
                    <div
                      className="absolute inset-0 z-20 flex items-center justify-center rounded-md"
                      style={{ background: isDark ? 'rgba(0,0,0,0.5)' : 'rgba(255,255,255,0.7)' }}
                    >
                      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-medium"
                        style={{ background: t.cardBg, color: t.text3, boxShadow: '0 2px 8px rgba(0,0,0,0.15)' }}
                      >
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Updating draft...
                      </div>
                    </div>
                  )}
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
                            {reply.channel === 'linkedin' ? (
                              <span
                                className="text-[11px] px-1.5 py-0.5 rounded font-medium"
                                style={{ background: '#e7f0fe', color: '#0a66c2' }}
                              >
                                LinkedIn
                              </span>
                            ) : (
                              <span
                                className="text-[11px] px-1.5 py-0.5 rounded font-medium"
                                style={{ background: '#fef3e2', color: '#b45309' }}
                              >
                                Email
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
                            {/* Stale badge removed — auto-regen handles it silently */}
                            {wasJustUpdated && (
                              <span
                                className="text-[11px] px-1.5 py-0.5 rounded font-medium animate-pulse"
                                style={{ background: isDark ? '#052e16' : '#dcfce7', color: isDark ? '#4ade80' : '#166534' }}
                              >
                                Updated
                              </span>
                            )}
                            {reply.follow_up_number && (
                              <span
                                className="text-[11px] px-1.5 py-0.5 rounded font-medium"
                                style={{ background: isDark ? '#1e1b4b' : '#eef2ff', color: isDark ? '#a5b4fc' : '#4338ca' }}
                              >
                                Follow-up
                              </span>
                            )}
                            {mode === 'followups' && reply.approved_at && (
                              <span
                                className="text-[11px] px-1.5 py-0.5 rounded"
                                style={{ background: isDark ? '#422006' : '#fff7ed', color: isDark ? '#fdba74' : '#c2410c' }}
                              >
                                Sent {(() => {
                                  const days = Math.floor((Date.now() - new Date(reply.approved_at).getTime()) / 86400000);
                                  return days === 1 ? '1 day ago' : `${days} days ago`;
                                })()}
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
                            <button
                              className="transition-colors cursor-pointer"
                              title="Copy link to this reply"
                              style={{ color: t.text5 }}
                              onClick={e => {
                                e.stopPropagation();
                                const url = new URL(window.location.href);
                                url.searchParams.set('lead', reply.lead_email);
                                url.searchParams.delete('category');
                                const link = url.toString();
                                (navigator.clipboard?.writeText(link) ?? Promise.reject()).catch(() => fallbackCopy(link));
                                toast.success('Link copied', { style: toastOk, duration: 1500 });
                              }}
                            >
                              <Link2 className="w-3 h-3" />
                            </button>
                          </div>
                        </div>

                        {(reply.sender_name || reply.campaign_name) && (
                          <div className="px-4 text-[11px] pb-1" style={{ color: t.text6 }}>
                            {reply.campaign_name && displayCampaignName(reply.campaign_name)}
                            {reply.sender_name && reply.campaign_name && ' · '}
                            {reply.sender_name && (
                              <span style={{ color: t.text5 }}>via {reply.sender_name}</span>
                            )}
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
                        {reply.translated_body && (
                          <div className="mt-2 pt-2" style={{ borderTop: `1px dashed ${t.divider}` }}>
                            <div className="flex items-center gap-1 text-[11px] mb-1" style={{ color: t.text5 }}>
                              <Languages className="w-3 h-3" />
                              English translation
                            </div>
                            <div
                              className="text-[13px] leading-relaxed whitespace-pre-wrap break-words"
                              style={{ color: t.text4 }}
                            >
                              {reply.translated_body}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* History */}
                      <div className="px-4">
                        {isThreadOpen && (
                          <div
                            className="flex items-center gap-2 py-1.5 -mx-4 px-4"
                            style={{
                              position: 'sticky',
                              top: 56,
                              zIndex: 9,
                              background: t.cardBg,
                              borderBottom: `1px solid ${t.divider}`,
                            }}
                          >
                            <button
                              onClick={() => loadHistory(reply)}
                              className="text-[11px] flex items-center gap-1 transition-colors cursor-pointer"
                              style={{ color: t.text5 }}
                            >
                              <MessageCircle className="w-3 h-3" />
                              Hide history
                            </button>
                            {history && history.campaigns.length > 1 && (
                              <CampaignDropdown
                                campaigns={history.campaigns}
                                selectedCampaign={selectedHistoryCampaign[reply.id] ?? null}
                                onSelect={(c) => {
                                  setSelectedHistoryCampaign(prev => ({ ...prev, [reply.id]: c }));
                                  const campName = c ? c.split('::').slice(1).join('::') : null;
                                  const isDefault = campName === reply.campaign_name;
                                  if (isDefault) {
                                    setEditingDrafts(prev => { const n = { ...prev }; delete n[reply.id]; return n; });
                                  } else if (campName) {
                                    setEditingDrafts(prev => ({
                                      ...prev,
                                      [reply.id]: { reply: '', subject: reply.draft_subject || '' },
                                    }));
                                  }
                                  if (c && campName) {
                                    const alreadyLoaded = history.activities.some(a => a.campaign === campName);
                                    if (!alreadyLoaded) {
                                      setLoadingThreads(prev => new Set(prev).add(reply.id));
                                      repliesApi.getCampaignThread(reply.id, campName).then(data => {
                                        if (data.activities.length > 0) {
                                          setHistoryData(prev => {
                                            const existing = prev[reply.id];
                                            if (!existing) return prev;
                                            return { ...prev, [reply.id]: {
                                              ...existing,
                                              activities: [...existing.activities, ...data.activities]
                                                .sort((a, b) => a.timestamp.localeCompare(b.timestamp)),
                                            }};
                                          });
                                        }
                                      }).catch(() => {}).finally(() => {
                                        setLoadingThreads(prev => { const s = new Set(prev); s.delete(reply.id); return s; });
                                      });
                                    }
                                  }
                                }}
                                isDark={isDark}
                              />
                            )}
                          </div>
                        )}
                        {!isThreadOpen && (
                          <button
                            onClick={() => loadHistory(reply)}
                            className="text-[11px] flex items-center gap-1 py-0.5 transition-colors cursor-pointer"
                            style={{ color: t.text5 }}
                          >
                            <MessageCircle className="w-3 h-3" />
                            History
                          </button>
                        )}
                        {isThreadOpen && (
                          <div className="mt-1.5 mb-2">
                            <ConversationThread
                              messages={history ? adaptContactHistory(history.activities) : []}
                              compact
                              isDark={isDark}
                              showDateSeparators
                              showCampaignMarkers={false}
                              filterCampaign={
                                (() => {
                                  const sel = selectedHistoryCampaign[reply.id];
                                  if (!sel) return null;
                                  const selName = sel.split('::').slice(1).join('::');
                                  const isOwnCampaign = selName === (reply.campaign_name || '');
                                  return isOwnCampaign ? null : sel;
                                })()
                              }
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
                            {mode === 'followups' ? 'Follow-up Draft' : (draftFailed ? 'Draft (failed)' : 'Draft')}
                          </span>
                          {mode === 'followups' && !fuDraft && !isFuGenerating ? (
                            <button
                              onClick={async () => {
                                setFollowupGenerating(prev => new Set(prev).add(reply.id));
                                try {
                                  const data = await repliesApi.generateFollowupDraft(reply.id, calendlyPrompt || undefined);
                                  setFollowupDrafts(prev => ({
                                    ...prev,
                                    [reply.id]: { reply: data.draft_reply, subject: data.draft_subject || '' },
                                  }));
                                } catch (err: any) {
                                  toast.error(err.response?.data?.detail || 'Failed to generate follow-up', { style: toastErr });
                                } finally {
                                  setFollowupGenerating(prev => { const s = new Set(prev); s.delete(reply.id); return s; });
                                }
                              }}
                              className="text-[11px] flex items-center gap-1 transition-colors cursor-pointer px-2 py-1 rounded"
                              style={{ background: t.btnPrimaryBg, color: t.btnPrimaryText }}
                            >
                              <RefreshCw className="w-3 h-3" /> Generate Follow-up
                            </button>
                          ) : mode === 'followups' && fuDraft && !isEditing ? (
                            <div className="flex items-center gap-2">
                              <button
                                onClick={async () => {
                                  setFollowupGenerating(prev => new Set(prev).add(reply.id));
                                  try {
                                    const data = await repliesApi.generateFollowupDraft(reply.id, calendlyPrompt || undefined);
                                    setFollowupDrafts(prev => ({
                                      ...prev,
                                      [reply.id]: { reply: data.draft_reply, subject: data.draft_subject || '' },
                                    }));
                                    setEditingDrafts(prev => { const d = { ...prev }; delete d[reply.id]; return d; });
                                  } catch (err: any) {
                                    toast.error('Regen failed', { style: toastErr });
                                  } finally {
                                    setFollowupGenerating(prev => { const s = new Set(prev); s.delete(reply.id); return s; });
                                  }
                                }}
                                className="text-[11px] flex items-center gap-1 transition-colors cursor-pointer"
                                style={{ color: t.text5 }}
                              >
                                <RefreshCw className={cn("w-3 h-3", isFuGenerating && "animate-spin")} /> Regen
                              </button>
                              <button
                                onClick={() => {
                                  setEditingDrafts(prev => ({
                                    ...prev,
                                    [reply.id]: { reply: fuDraft.reply, subject: fuDraft.subject },
                                  }));
                                }}
                                className="text-[11px] flex items-center gap-1 transition-colors cursor-pointer"
                                style={{ color: t.text5 }}
                              >
                                <Edit3 className="w-3 h-3" /> Edit
                              </button>
                            </div>
                          ) : !isEditing && reply.draft_reply && mode !== 'followups' ? (
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

                        {/* Quick document download — only when lead asked for materials */}
                        {projectDocs.length > 0 && leadsAsksForDocs(reply) && (
                          <div className="flex items-center gap-1.5 mb-2 flex-wrap">
                            <span className="text-[10px] uppercase tracking-wider" style={{ color: t.text5 }}>Attach:</span>
                            {projectDocs.map(doc => (
                              <a
                                key={doc.id}
                                href={String(doc.value)}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium transition-opacity hover:opacity-80"
                                style={{ background: isDark ? '#1e293b' : '#eff6ff', color: '#3b82f6' }}
                                title={`Download ${doc.title || doc.key}`}
                              >
                                <FileText className="w-3 h-3" />
                                {doc.title || doc.key}
                                <Download className="w-3 h-3 opacity-60" />
                              </a>
                            ))}
                          </div>
                        )}

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
                        ) : isFuGenerating ? (
                          <div
                            className="text-[13px] leading-relaxed rounded p-2.5 flex items-center gap-2"
                            style={{ background: t.draftBg, color: t.text4 }}
                          >
                            <Loader2 className="w-4 h-4 animate-spin" />
                            Generating follow-up draft...
                          </div>
                        ) : mode === 'followups' && !fuDraft ? (
                          <div
                            className="text-[13px] leading-relaxed rounded p-2.5"
                            style={{ background: t.draftBg, color: t.text5 }}
                          >
                            Click "Generate Follow-up" to create a draft
                          </div>
                        ) : (
                          <>
                            <div
                              className="text-[13px] whitespace-pre-wrap leading-relaxed rounded p-2.5"
                              style={{ background: t.draftBg, color: t.text2 }}
                            >
                              {draftText || '(no draft)'}
                            </div>
                            {reply.translated_draft && (
                              <div className="mt-1.5 pt-1.5" style={{ borderTop: `1px dashed ${t.divider}` }}>
                                <div className="flex items-center gap-1 text-[11px] mb-1 px-1" style={{ color: t.text5 }}>
                                  <Languages className="w-3 h-3" />
                                  English translation
                                </div>
                                <div
                                  className="text-[13px] whitespace-pre-wrap leading-relaxed rounded p-2.5"
                                  style={{ background: t.draftBg, color: t.text4 }}
                                >
                                  {reply.translated_draft}
                                </div>
                              </div>
                            )}
                          </>
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
                        {mode === 'followups' ? (
                          <>
                            <button
                              onClick={async () => {
                                const draft = isEditing ? editingDrafts[reply.id] : fuDraft;
                                if (!draft?.reply) return;
                                setSendingIds(prev => new Set(prev).add(reply.id));
                                try {
                                  const result = await repliesApi.sendFollowup(reply.id, {
                                    draft_reply: draft.reply,
                                    draft_subject: draft.subject || undefined,
                                  });
                                  toast.success(result.message || 'Follow-up sent', { style: toastOk });
                                  optimisticRemoveReply(reply);
                                  setFollowupDrafts(prev => { const d = { ...prev }; delete d[reply.id]; return d; });
                                  setEditingDrafts(prev => { const d = { ...prev }; delete d[reply.id]; return d; });
                                } catch (err: any) {
                                  toast.error(err.response?.data?.detail || 'Failed to send follow-up', { style: toastErr });
                                } finally {
                                  setSendingIds(prev => { const s = new Set(prev); s.delete(reply.id); return s; });
                                }
                              }}
                              disabled={isSending || !(isEditing ? editingDrafts[reply.id]?.reply : fuDraft?.reply)}
                              className={cn(
                                "flex items-center gap-1.5 px-3.5 py-1.5 rounded text-[13px] font-medium transition-all",
                                isSending ? "cursor-wait" : "cursor-pointer active:scale-[0.98]"
                              )}
                              style={{
                                background: isSending || !(isEditing ? editingDrafts[reply.id]?.reply : fuDraft?.reply) ? t.divider : t.btnPrimaryBg,
                                color: isSending || !(isEditing ? editingDrafts[reply.id]?.reply : fuDraft?.reply) ? t.text5 : t.btnPrimaryText,
                              }}
                              onMouseEnter={e => {
                                if (!isSending && (isEditing ? editingDrafts[reply.id]?.reply : fuDraft?.reply)) {
                                  (e.currentTarget as HTMLElement).style.background = t.btnPrimaryHover;
                                }
                              }}
                              onMouseLeave={e => {
                                (e.currentTarget as HTMLElement).style.background =
                                  isSending || !(isEditing ? editingDrafts[reply.id]?.reply : fuDraft?.reply) ? t.divider : t.btnPrimaryBg;
                              }}
                            >
                              {isSending ? (
                                <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Sending...</>
                              ) : (
                                <><ArrowRight className="w-3.5 h-3.5" /> Send Follow-up</>
                              )}
                            </button>
                            <button
                              onClick={async () => {
                                try {
                                  await repliesApi.dismissFollowup(reply.id);
                                  toast.success('Follow-up skipped', { style: toastOk });
                                  optimisticRemoveReply(reply);
                                  setFollowupDrafts(prev => { const d = { ...prev }; delete d[reply.id]; return d; });
                                } catch (err: any) {
                                  toast.error(err.response?.data?.detail || 'Failed', { style: toastErr });
                                }
                              }}
                              disabled={isSending}
                              className="flex items-center gap-1 px-3 py-1.5 rounded text-[13px] transition-all cursor-pointer active:scale-[0.98]"
                              style={{ color: t.text4 }}
                              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = t.btnGhostHover; }}
                              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
                            >
                              <XCircle className="w-3.5 h-3.5" /> Skip
                            </button>
                          </>
                        ) : (
                          <>
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
                          </>
                        )}
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

                        {/* Calendar section — only for meeting_request/interested with Calendly config */}
                        {hasCalendly && (reply.category === 'meeting_request' || reply.category === 'interested') && (
                          <>
                            {hasReasoning && <div className="my-2.5" style={{ borderTop: `1px solid ${t.divider}` }} />}
                            <div className="flex items-center gap-1.5 mb-2">
                              <CalendarClock className="w-3.5 h-3.5" style={{ color: t.text4 }} />
                              <span className="text-[11px] font-medium uppercase tracking-wider" style={{ color: t.text4 }}>
                                Calendar
                              </span>
                            </div>

                            {/* Member dropdown */}
                            {calendlyMembers.length > 1 && (
                              <div className="mb-2">
                                <select
                                  value={selectedCalendlyMember}
                                  onChange={e => handleCalendlyMemberChange(reply, e.target.value)}
                                  disabled={calendlyLoading || regeneratingIds.has(reply.id)}
                                  className="w-full text-[12px] px-2 py-1 rounded border appearance-none cursor-pointer"
                                  style={{
                                    background: t.cardBg,
                                    borderColor: t.divider,
                                    color: t.text2,
                                    opacity: (calendlyLoading || regeneratingIds.has(reply.id)) ? 0.6 : 1,
                                  }}
                                >
                                  {calendlyMembers.map(m => (
                                    <option key={m.id} value={m.id}>{m.display_name}</option>
                                  ))}
                                </select>
                              </div>
                            )}

                            {/* Slot display */}
                            {calendlyLoading ? (
                              <div className="flex items-center gap-1.5 text-[11px]" style={{ color: t.text5 }}>
                                <Loader2 className="w-3 h-3 animate-spin" /> Loading slots...
                              </div>
                            ) : calendlySlots.length > 0 ? (
                              <div className="space-y-0.5 mb-2">
                                {calendlySlots.map((line, i) => (
                                  <div key={i} className="text-[12px] font-mono" style={{ color: t.text2 }}>
                                    {line}
                                  </div>
                                ))}
                                {calendlyFallback && (
                                  <div className="text-[10px] mt-1" style={{ color: t.text5 }}>
                                    Merged from team calendars
                                  </div>
                                )}
                              </div>
                            ) : (
                              <div className="text-[11px] mb-2" style={{ color: t.text5 }}>
                                No available slots found
                              </div>
                            )}

                            {/* Regen with slots button */}
                            {calendlyPrompt && !regeneratingIds.has(reply.id) && (
                              <button
                                onClick={() => handleRegenerate(reply, calendlyPrompt)}
                                className="flex items-center gap-1 text-[11px] px-2 py-1 rounded transition-colors w-full justify-center"
                                style={{
                                  background: t.btnPrimaryBg,
                                  color: t.btnPrimaryText,
                                }}
                                onMouseOver={e => (e.currentTarget.style.opacity = '0.85')}
                                onMouseOut={e => (e.currentTarget.style.opacity = '1')}
                              >
                                <RefreshCw className="w-3 h-3" />
                                Regen with slots
                              </button>
                            )}
                            {regeneratingIds.has(reply.id) && calendlyPrompt && (
                              <div className="flex items-center gap-1.5 text-[11px] justify-center py-1" style={{ color: t.text5 }}>
                                <Loader2 className="w-3 h-3 animate-spin" /> Regenerating...
                              </div>
                            )}
                          </>
                        )}

                        {/* Contact section */}
                        <>
                          {(hasReasoning || (hasCalendly && (reply.category === 'meeting_request' || reply.category === 'interested'))) && <div className="my-2.5" style={{ borderTop: `1px solid ${t.divider}` }} />}
                          <div className="flex items-center gap-1.5 mb-2">
                            <User className="w-3.5 h-3.5" style={{ color: t.text4 }} />
                            <span className="text-[11px] font-medium uppercase tracking-wider" style={{ color: t.text4 }}>
                              Contact
                            </span>
                          </div>

                          {reply.lead_email && !reply.lead_email.includes('@linkedin.placeholder') && !reply.lead_email.startsWith('gs_') && (
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
                                  const url = contactInfo!.linkedin_url!;
                                  if (navigator.clipboard?.writeText) {
                                    navigator.clipboard.writeText(url).then(
                                      () => toast.success('LinkedIn URL copied', { style: toastOk }),
                                      () => { fallbackCopy(url); toast.success('LinkedIn URL copied', { style: toastOk }); }
                                    );
                                  } else {
                                    fallbackCopy(url);
                                    toast.success('LinkedIn URL copied', { style: toastOk });
                                  }
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

                          {(() => {
                            const companyName = contactInfo?.company_name || reply.lead_company || null;
                            const domain = contactInfo?.domain || (reply.lead_email?.split('@')[1] || null);
                            const isGenericDomain = domain && /^(gmail|yahoo|hotmail|outlook|mail|icloud|aol|proton|yandex|live)\./i.test(domain);
                            const showDomain = domain && !isGenericDomain;
                            if (!companyName && !showDomain) return null;
                            return (
                              <div className="mb-1.5 flex items-center gap-1 text-[12px]" style={{ color: t.text3 }}>
                                <Building2 className="w-3 h-3 flex-shrink-0" />
                                <span>
                                  {companyName}
                                  {showDomain && (
                                    <>
                                      {companyName ? ' · ' : ''}
                                      <a
                                        href={`https://${domain}`}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="hover:underline"
                                        style={{ color: t.text3 }}
                                      >
                                        {domain}
                                      </a>
                                    </>
                                  )}
                                </span>
                              </div>
                            );
                          })()}

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
