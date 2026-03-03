import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ExternalLink, Loader2, ChevronDown, ChevronUp, Pencil, ChevronRight } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { getOperatorCorrections } from '../api/learning';
import type { OperatorCorrection } from '../api/learning';
import { TextDiff } from '../components/TextDiff';

// --- Column filter config ---

const ACTION_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'send', label: 'Sent' },
  { value: 'dismiss', label: 'Dismissed' },
  { value: 'regenerate', label: 'Regenerated' },
];

const CATEGORY_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'interested', label: 'interested' },
  { value: 'meeting_request', label: 'meeting_request' },
  { value: 'question', label: 'question' },
  { value: 'not_interested', label: 'not_interested' },
  { value: 'out_of_office', label: 'out_of_office' },
  { value: 'wrong_person', label: 'wrong_person' },
  { value: 'unsubscribe', label: 'unsubscribe' },
  { value: 'other', label: 'other' },
];

const CHANNEL_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'email', label: 'email' },
  { value: 'linkedin', label: 'linkedin' },
];

const ACTION_BADGES: Record<string, { label: string; bg: string; bgDark: string; color: string; colorDark: string }> = {
  send: { label: 'Sent', bg: '#dcfce7', bgDark: '#052e16', color: '#166534', colorDark: '#4ade80' },
  dismiss: { label: 'Dismissed', bg: '#fee2e2', bgDark: '#450a0a', color: '#991b1b', colorDark: '#fca5a5' },
  regenerate: { label: 'Regenerated', bg: '#dbeafe', bgDark: '#172554', color: '#1e40af', colorDark: '#93c5fd' },
};

const PAGE_SIZE = 30;

// --- ColumnFilter dropdown ---

function ColumnFilter({
  label,
  options,
  value,
  onChange,
  isDark,
  t,
}: {
  label: string;
  options: { value: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
  isDark: boolean;
  t: ReturnType<typeof themeColors>;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const activeLabel = options.find(o => o.value === value)?.label || label;
  const isFiltered = value !== '';

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div ref={ref} className="relative inline-block">
      <button
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-0.5 text-[11px] uppercase tracking-wide font-medium cursor-pointer hover:opacity-80"
        style={{ color: isFiltered ? (isDark ? '#93c5fd' : '#1e40af') : t.text4 }}
      >
        {isFiltered ? activeLabel : label}
        <ChevronDown className="w-3 h-3" />
      </button>
      {open && (
        <div
          className="absolute left-0 top-full mt-1 z-50 rounded-lg border py-1 min-w-[140px] shadow-lg"
          style={{ background: isDark ? '#2a2a2a' : '#fff', borderColor: t.cardBorder }}
        >
          {options.map(o => (
            <button
              key={o.value}
              onClick={() => { onChange(o.value); setOpen(false); }}
              className="block w-full text-left px-3 py-1.5 text-[12px] cursor-pointer hover:opacity-80"
              style={{
                color: o.value === value ? (isDark ? '#93c5fd' : '#1e40af') : t.text2,
                background: o.value === value ? (isDark ? '#333' : '#f0f4ff') : 'transparent',
              }}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Main page ---

export function OperatorActionsPage() {
  const { currentProject, setCurrentProject, projects } = useAppStore();
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [corrections, setCorrections] = useState<OperatorCorrection[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const pageRef = useRef(1);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const [actionFilter, setActionFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');
  const [channelFilter, setChannelFilter] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // URL -> project sync
  useEffect(() => {
    if (!projects.length) return;
    const projectParam = searchParams.get('project');
    if (projectParam) {
      const normalized = projectParam.toLowerCase().replace(/-/g, ' ');
      const match = projects.find(p => p.name.toLowerCase() === normalized)
        || projects.find(p => p.id === Number(projectParam));
      if (match && (!currentProject || currentProject.id !== match.id)) {
        setCurrentProject(match);
      }
    }
  }, [projects, searchParams]);

  // Project -> URL sync
  useEffect(() => {
    const slug = currentProject
      ? currentProject.name.toLowerCase().replace(/\s+/g, '-')
      : null;
    const currentParam = searchParams.get('project');
    if (slug && currentParam !== slug) {
      navigate(`/actions?project=${slug}`, { replace: true });
    } else if (!slug && currentParam) {
      navigate('/actions', { replace: true });
    }
  }, [currentProject]);

  // Load corrections (append=false → reset, append=true → add to list)
  const loadCorrections = useCallback(async (append = false) => {
    if (!currentProject) return;
    if (append) setIsLoadingMore(true); else setLoading(true);
    try {
      const page = append ? pageRef.current : 1;
      const data = await getOperatorCorrections(
        currentProject.id, page, PAGE_SIZE,
        {
          actionType: actionFilter || undefined,
          category: categoryFilter || undefined,
          channel: channelFilter || undefined,
        },
      );
      if (append) {
        setCorrections(prev => [...prev, ...data.items]);
      } else {
        setCorrections(data.items);
        setTotal(data.total);
      }
      setHasMore(data.items.length === PAGE_SIZE);
    } catch (e) {
      console.error('Failed to load corrections:', e);
    } finally {
      if (append) setIsLoadingMore(false); else setLoading(false);
    }
  }, [currentProject?.id, actionFilter, categoryFilter, channelFilter]);

  // Reset on filter/project change
  useEffect(() => {
    setCorrections([]);
    setTotal(0);
    pageRef.current = 1;
    setExpandedId(null);
    setHasMore(true);
  }, [currentProject?.id, actionFilter, categoryFilter, channelFilter]);

  // Fetch on filter/project change
  useEffect(() => {
    if (currentProject) loadCorrections(false);
  }, [loadCorrections]);

  // Infinite scroll observer
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasMore && !isLoadingMore && !loading) {
          pageRef.current += 1;
          loadCorrections(true);
        }
      },
      { rootMargin: '200px' },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, isLoadingMore, loading, loadCorrections]);

  if (!currentProject) {
    return (
      <div className="h-full flex flex-col items-center justify-center" style={{ background: t.pageBg, color: t.text4 }}>
        <p className="text-[14px]">Select a project to view operator actions</p>
      </div>
    );
  }

  const projectSlug = currentProject.name.toLowerCase().replace(/\s+/g, '-');

  return (
    <div className="h-full flex flex-col" style={{ background: t.pageBg }}>
      {/* Header */}
      <div
        className="border-b px-5 py-2 flex items-center gap-4"
        style={{ background: t.headerBg, borderColor: t.cardBorder }}
      >
        <a
          href={`/projects/${currentProject.id}`}
          onClick={(e) => { e.preventDefault(); navigate(`/projects/${currentProject.id}`); }}
          className="flex items-center gap-1 text-[13px] font-medium hover:underline cursor-pointer"
          style={{ color: t.text2 }}
        >
          <ExternalLink className="w-3 h-3 opacity-50" />
          {currentProject.name}
        </a>
        <div className="w-px h-4" style={{ background: t.cardBorder }} />
        <span className="text-[13px] font-medium" style={{ color: t.text1 }}>
          Operator Actions
        </span>
        <span className="text-[12px]" style={{ color: t.text4 }}>
          {total} total
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {loading && corrections.length === 0 ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-5 h-5 animate-spin" style={{ color: t.text4 }} />
          </div>
        ) : corrections.length === 0 && !loading ? (
          <div className="flex items-center justify-center py-20 text-[14px]" style={{ color: t.text4 }}>
            No operator actions recorded yet
          </div>
        ) : (
          <div className="px-5 py-3">
            <table className="w-full text-[13px]" style={{ color: t.text2 }}>
              <thead>
                <tr className="text-left" style={{ color: t.text4 }}>
                  <th className="pb-2 pr-2 font-medium w-[28px]"></th>
                  <th className="pb-2 pr-3 font-medium">
                    <ColumnFilter label="Action" options={ACTION_OPTIONS} value={actionFilter} onChange={setActionFilter} isDark={isDark} t={t} />
                  </th>
                  <th className="pb-2 pr-3 font-medium">
                    <ColumnFilter label="Category" options={CATEGORY_OPTIONS} value={categoryFilter} onChange={setCategoryFilter} isDark={isDark} t={t} />
                  </th>
                  <th className="pb-2 pr-3 font-medium">
                    <ColumnFilter label="Channel" options={CHANNEL_OPTIONS} value={channelFilter} onChange={setChannelFilter} isDark={isDark} t={t} />
                  </th>
                  <th className="pb-2 pr-3 font-medium text-[11px] uppercase tracking-wide" style={{ color: t.text4 }}>Lead</th>
                  <th className="pb-2 pr-3 font-medium text-[11px] uppercase tracking-wide" style={{ color: t.text4 }}>Campaign</th>
                  <th className="pb-2 pr-3 font-medium text-[11px] uppercase tracking-wide" style={{ color: t.text4 }}>AI Draft</th>
                  <th className="pb-2 pr-3 font-medium text-[11px] uppercase tracking-wide" style={{ color: t.text4 }}>Operator Sent</th>
                  <th className="pb-2 pr-3 font-medium text-[11px] uppercase tracking-wide" style={{ color: t.text4 }}>Time</th>
                  <th className="pb-2 font-medium text-[11px] uppercase tracking-wide" style={{ color: t.text4 }}>Source</th>
                </tr>
              </thead>
              <tbody>
                {corrections.map(c => (
                  <CorrectionRow
                    key={c.id}
                    c={c}
                    isExpanded={expandedId === c.id}
                    isDark={isDark}
                    t={t}
                    projectSlug={projectSlug}
                    onToggle={() => setExpandedId(expandedId === c.id ? null : c.id)}
                  />
                ))}
              </tbody>
            </table>

            {/* Infinite scroll sentinel */}
            <div ref={sentinelRef} className="h-4" />
            {isLoadingMore && (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="w-4 h-4 animate-spin" style={{ color: t.text5 }} />
              </div>
            )}
            {!hasMore && corrections.length > 0 && (
              <div className="text-center py-3 text-[11px]" style={{ color: t.text6 }}>
                Showing all {corrections.length} of {total}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// --- Row component ---

function CorrectionRow({
  c, isExpanded, isDark, t, projectSlug, onToggle,
}: {
  c: OperatorCorrection;
  isExpanded: boolean;
  isDark: boolean;
  t: ReturnType<typeof themeColors>;
  projectSlug: string;
  onToggle: () => void;
}) {
  const badge = ACTION_BADGES[c.action_type] || ACTION_BADGES.send;
  const edited = c.was_edited;
  const hasDetail = c.ai_draft_full || c.sent_full;

  const campaignShort = c.campaign_name
    ? (c.campaign_name.length > 30 ? c.campaign_name.slice(0, 28) + '\u2026' : c.campaign_name)
    : '\u2014';

  return (
    <>
      <tr
        className="border-t cursor-pointer"
        style={{ borderColor: t.cardBorder }}
        onClick={hasDetail ? onToggle : undefined}
      >
        <td className="py-2.5 pr-1">
          {hasDetail && (
            isExpanded
              ? <ChevronUp className="w-3.5 h-3.5" style={{ color: t.text4 }} />
              : <ChevronDown className="w-3.5 h-3.5" style={{ color: t.text4 }} />
          )}
        </td>
        {/* Action + actor */}
        <td className="py-2.5 pr-3">
          <span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium"
            style={{
              background: isDark ? badge.bgDark : badge.bg,
              color: isDark ? badge.colorDark : badge.color,
            }}
          >
            {badge.label}
            {edited && <Pencil className="w-2.5 h-2.5 opacity-70" />}
            {edited && <span className="opacity-70">(edited)</span>}
          </span>
          <div className="text-[10px] mt-0.5" style={{ color: t.text5 }}>
            {c.actor}
          </div>
        </td>
        {/* Category */}
        <td className="py-2.5 pr-3">
          <span className="text-[12px]" style={{ color: t.text3 }}>
            {c.reply_category || '\u2014'}
          </span>
        </td>
        {/* Channel */}
        <td className="py-2.5 pr-3">
          <span className="text-[12px]" style={{ color: t.text3 }}>
            {c.channel || '\u2014'}
          </span>
        </td>
        {/* Lead */}
        <td className="py-2.5 pr-3 max-w-[200px]">
          <div className="text-[12px] truncate" style={{ color: t.text2 }} title={c.lead_email || ''}>
            {c.lead_email || '\u2014'}
          </div>
          {c.lead_company && (
            <div className="text-[11px] truncate" style={{ color: t.text5 }}>
              {c.lead_company}
            </div>
          )}
        </td>
        {/* Campaign */}
        <td className="py-2.5 pr-3 max-w-[180px]">
          <div className="text-[12px] truncate" style={{ color: t.text4 }} title={c.campaign_name || ''}>
            {campaignShort}
          </div>
        </td>
        {/* AI Draft preview */}
        <td className="py-2.5 pr-3 max-w-[220px]">
          <div className="text-[12px] truncate" style={{ color: t.text4 }} title={c.ai_draft_preview}>
            {c.ai_draft_preview || '\u2014'}
          </div>
        </td>
        {/* Operator Sent preview */}
        <td className="py-2.5 pr-3 max-w-[220px]">
          <div className="text-[12px] truncate" style={{ color: edited ? t.text2 : t.text4 }} title={c.sent_preview}>
            {c.sent_preview || '\u2014'}
          </div>
        </td>
        {/* Time */}
        <td className="py-2.5 pr-3 whitespace-nowrap">
          <span className="text-[12px]" style={{ color: t.text4 }}>
            {c.created_at ? new Date(c.created_at).toLocaleString('en-GB', {
              day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
            }) : '\u2014'}
          </span>
        </td>
        {/* Source */}
        <td className="py-2.5">
          {c.inbox_link ? (
            <a
              href={c.inbox_link}
              target="_blank"
              rel="noopener noreferrer"
              title={`Open in ${c.channel === 'linkedin' ? 'GetSales' : 'SmartLead'}`}
              onClick={(e) => e.stopPropagation()}
              className="hover:opacity-70"
              style={{ color: t.text3 }}
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          ) : (
            <span style={{ color: t.text6 }}>{'\u2014'}</span>
          )}
        </td>
      </tr>
      {isExpanded && hasDetail && (
        <tr style={{ borderColor: t.cardBorder }}>
          <td colSpan={10} className="pb-4 pt-1 px-2">
            <DraftComparison c={c} isDark={isDark} t={t} edited={edited} projectSlug={projectSlug} />
          </td>
        </tr>
      )}
    </>
  );
}

// --- Expanded detail ---

function DraftComparison({
  c, isDark, t, edited, projectSlug,
}: {
  c: OperatorCorrection;
  isDark: boolean;
  t: ReturnType<typeof themeColors>;
  edited: boolean;
  projectSlug: string;
}) {
  const bgPanel = isDark ? '#2a2a2a' : '#f8f8f8';
  const borderPanel = isDark ? '#3c3c3c' : '#e0e0e0';
  const navigate = useNavigate();

  const showDiff = edited && c.ai_draft_full && c.sent_full;
  const showTwoPanels = c.action_type === 'send';
  const draftText = c.ai_draft_full || c.ai_draft_preview || '\u2014';
  const sentText = c.sent_full || c.sent_preview || '\u2014';

  return (
    <div>
      <div className={showTwoPanels ? 'flex gap-3' : ''}>
        {/* AI Draft */}
        <div className={showTwoPanels ? 'flex-1 min-w-0' : ''}>
          <div className="text-[11px] uppercase tracking-wide font-medium mb-1.5" style={{ color: t.text4 }}>
            AI Suggestion
          </div>
          {c.ai_draft_subject && (
            <div className="text-[12px] font-medium mb-1" style={{ color: t.text3 }}>
              Subject: {c.ai_draft_subject}
            </div>
          )}
          <div
            className="rounded p-3 text-[12px] whitespace-pre-wrap leading-relaxed max-h-[300px] overflow-y-auto"
            style={{ background: bgPanel, border: `1px solid ${borderPanel}`, color: t.text3 }}
          >
            {draftText}
          </div>
        </div>

        {/* Operator Sent / Diff */}
        {showTwoPanels && (
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-[11px] uppercase tracking-wide font-medium" style={{ color: t.text4 }}>
                Operator Sent
              </span>
              {edited && (
                <span
                  className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                  style={{
                    background: isDark ? '#3b2607' : '#fef3c7',
                    color: isDark ? '#fbbf24' : '#92400e',
                  }}
                >
                  Edited
                </span>
              )}
            </div>
            {c.sent_subject && c.sent_subject !== c.ai_draft_subject && (
              <div className="text-[12px] font-medium mb-1" style={{ color: edited ? t.text2 : t.text3 }}>
                Subject: {c.sent_subject}
              </div>
            )}
            <div
              className="rounded p-3 max-h-[300px] overflow-y-auto"
              style={{
                background: edited ? (isDark ? '#1a2e1a' : '#f0fdf4') : bgPanel,
                border: `1px solid ${edited ? (isDark ? '#2d5a2d' : '#bbf7d0') : borderPanel}`,
              }}
            >
              {showDiff ? (
                <TextDiff oldText={c.ai_draft_full!} newText={c.sent_full!} isDark={isDark} />
              ) : (
                <div className="text-[12px] whitespace-pre-wrap leading-relaxed" style={{ color: edited ? t.text2 : t.text3 }}>
                  {sentText}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Related learning log link */}
      {c.action_type === 'send' && edited && (
        <div className="mt-2 text-[12px]">
          {c.related_log_id ? (
            <button
              onClick={() => navigate(`/knowledge/logs?project=${projectSlug}&logId=${c.related_log_id}`)}
              className="inline-flex items-center gap-1 cursor-pointer hover:underline"
              style={{ color: isDark ? '#93c5fd' : '#1e40af' }}
            >
              View knowledge update <ChevronRight className="w-3 h-3" />
            </button>
          ) : (
            <span style={{ color: t.text5 }}>No knowledge update triggered yet</span>
          )}
        </div>
      )}
    </div>
  );
}
