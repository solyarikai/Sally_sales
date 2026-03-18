import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { Brain, Loader2, ChevronDown, ChevronRight, ExternalLink, RefreshCw, Search, X, Tag } from 'lucide-react';
import { intelligenceApi } from '../../api/intelligence';
import type { ReplyAnalysisItem, IntelligenceSummary } from '../../api/intelligence';
import { cn } from '../../lib/utils';

// ── Props ───────────────────────────────────────────────────────

interface IntelligencePanelProps {
  projectId: number;
  isDark: boolean;
  t: Record<string, string>;
}

// ── Constants ──────────────────────────────────────────────────

const INTENT_GROUP_ORDER = ['warm', 'questions', 'soft_objection', 'hard_objection', 'noise'] as const;

const GROUP_CRM_CATEGORIES: Record<string, string> = {
  warm: 'interested,meeting_request',
  questions: 'question',
  soft_objection: 'not_interested',
  hard_objection: 'not_interested',
  noise: 'other,wrong_person,unsubscribe',
};

const GROUP_LABELS: Record<string, string> = {
  warm: 'Warm Replies',
  questions: 'Questions',
  soft_objection: 'Soft Objections',
  hard_objection: 'Hard Objections',
  noise: 'Noise',
};

const GROUP_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  warm: { bg: 'bg-green-500/10', text: 'text-green-400', border: 'border-green-500/30' },
  questions: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/30' },
  soft_objection: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/30' },
  hard_objection: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30' },
  noise: { bg: 'bg-zinc-500/10', text: 'text-zinc-400', border: 'border-zinc-500/30' },
};

const GROUP_COLORS_LIGHT: Record<string, { bg: string; text: string; border: string }> = {
  warm: { bg: 'bg-green-50', text: 'text-green-700', border: 'border-green-200' },
  questions: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
  soft_objection: { bg: 'bg-yellow-50', text: 'text-yellow-700', border: 'border-yellow-200' },
  hard_objection: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
  noise: { bg: 'bg-zinc-50', text: 'text-zinc-500', border: 'border-zinc-200' },
};

const OFFER_COLORS: Record<string, string> = {
  paygate: 'bg-blue-500/20 text-blue-300',
  payout: 'bg-green-500/20 text-green-300',
  otc: 'bg-orange-500/20 text-orange-300',
  general: 'bg-zinc-500/20 text-zinc-300',
};

const OFFER_COLORS_LIGHT: Record<string, string> = {
  paygate: 'bg-blue-100 text-blue-700',
  payout: 'bg-green-100 text-green-700',
  otc: 'bg-orange-100 text-orange-700',
  general: 'bg-zinc-100 text-zinc-600',
};

const INTENT_LABELS: Record<string, string> = {
  send_info: 'Send info',
  schedule_call: 'Schedule call',
  interested_vague: 'Interested',
  redirect_colleague: 'Redirect',
  pricing: 'Pricing',
  how_it_works: 'How it works',
  compliance: 'Compliance',
  specific_use_case: 'Use case',
  adjacent_demand: 'Adjacent demand',
  not_relevant: 'Not relevant',
  no_crypto: 'No crypto',
  not_now: 'Not now',
  have_solution: 'Have solution',
  regulatory: 'Regulatory',
  hard_no: 'Hard no',
  spam_complaint: 'Spam complaint',
  empty: 'Empty',
  auto_response: 'Auto-response',
  bounce: 'Bounce',
  gibberish: 'Gibberish',
  wrong_person_forward: 'Wrong person',
};

const PERIOD_OPTIONS = [
  { label: '7d', days: 7 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
  { label: 'All time', days: 0 },
];

// ── Sub-components ──────────────────────────────────────────────

function WarmthDots({ score, isDark }: { score: number | null; isDark: boolean }) {
  const s = score ?? 0;
  const colors = ['bg-red-500', 'bg-orange-400', 'bg-yellow-400', 'bg-green-400', 'bg-green-500'];
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map(i => (
        <div
          key={i}
          className={cn(
            'w-2 h-2 rounded-full',
            i <= s ? colors[s - 1] : (isDark ? 'bg-zinc-700' : 'bg-zinc-200'),
          )}
        />
      ))}
    </div>
  );
}

function TagChip({ tag, isDark, onClick }: { tag: string; isDark: boolean; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors',
        isDark
          ? 'bg-violet-500/15 text-violet-300 hover:bg-violet-500/25'
          : 'bg-violet-50 text-violet-600 hover:bg-violet-100',
      )}
    >
      <Tag className="w-2.5 h-2.5" />
      {tag}
    </button>
  );
}

function MultiSelectFilter({
  label,
  options,
  selected,
  onToggle,
  isDark,
}: {
  label: string;
  options: { value: string; label: string; count?: number }[];
  selected: Set<string>;
  onToggle: (value: string) => void;
  isDark: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const filtered = search
    ? options.filter(o => o.label.toLowerCase().includes(search.toLowerCase()))
    : options;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium border transition-colors',
          isDark
            ? 'border-zinc-700 text-zinc-300 hover:border-zinc-500'
            : 'border-zinc-200 text-zinc-600 hover:border-zinc-400',
          selected.size > 0 && 'ring-1 ring-blue-500',
        )}
      >
        {label}
        {selected.size > 0 && (
          <span className="px-1 rounded-full text-[9px] bg-blue-500 text-white">{selected.size}</span>
        )}
        <ChevronDown className="w-3 h-3" />
      </button>
      {open && (
        <div className={cn(
          'absolute top-full left-0 mt-1 w-56 rounded-md shadow-xl z-50 border',
          isDark ? 'bg-zinc-800 border-zinc-700' : 'bg-white border-zinc-200',
        )}>
          {options.length > 5 && (
            <div className="p-1.5">
              <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search..."
                autoFocus
                className={cn(
                  'w-full px-2 py-1 rounded text-[11px] border-none outline-none',
                  isDark ? 'bg-zinc-700 text-zinc-200' : 'bg-zinc-50 text-zinc-800',
                )}
              />
            </div>
          )}
          <div className="max-h-48 overflow-y-auto py-0.5">
            {filtered.map(opt => (
              <button
                key={opt.value}
                onClick={() => onToggle(opt.value)}
                className={cn(
                  'w-full px-3 py-1.5 text-left text-[12px] flex items-center gap-2',
                  isDark ? 'hover:bg-zinc-700' : 'hover:bg-zinc-50',
                )}
              >
                <div className={cn(
                  'w-3.5 h-3.5 rounded border flex items-center justify-center',
                  selected.has(opt.value)
                    ? 'bg-blue-500 border-blue-500'
                    : isDark ? 'border-zinc-600' : 'border-zinc-300',
                )}>
                  {selected.has(opt.value) && <span className="text-white text-[8px]">✓</span>}
                </div>
                <span className={isDark ? 'text-zinc-200' : 'text-zinc-700'}>{opt.label}</span>
                {opt.count !== undefined && (
                  <span className={cn('ml-auto text-[10px]', isDark ? 'text-zinc-500' : 'text-zinc-400')}>
                    {opt.count}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main Panel ──────────────────────────────────────────────────

export function IntelligencePanel({ projectId, isDark, t }: IntelligencePanelProps) {
  const [items, setItems] = useState<ReplyAnalysisItem[]>([]);
  const [summary, setSummary] = useState<IntelligenceSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [intentGroupFilter, setIntentGroupFilter] = useState<string | null>(null);
  const [offerFilter, setOfferFilter] = useState<Set<string>>(new Set());
  const [intentFilter, setIntentFilter] = useState<Set<string>>(new Set());
  const [segmentFilter, setSegmentFilter] = useState<Set<string>>(new Set());
  const [tagFilter, setTagFilter] = useState<Set<string>>(new Set());
  const [geoFilter, setGeoFilter] = useState<Set<string>>(new Set());
  const [searchText, setSearchText] = useState('');
  const [period, setPeriod] = useState(0); // 0 = all time
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set(['noise']));

  const dateFrom = useMemo(() => {
    if (!period) return undefined;
    const d = new Date();
    d.setDate(d.getDate() - period);
    return d.toISOString();
  }, [period]);

  // ── Data loading ──
  const loadData = useCallback(async () => {
    if (!projectId) return;
    try {
      setLoading(true);
      setError(null);
      const params: Parameters<typeof intelligenceApi.list>[0] = {
        project_id: projectId,
        page_size: 200,
      };
      if (intentGroupFilter) params.intent_group = intentGroupFilter;
      if (offerFilter.size) params.offer = Array.from(offerFilter).join(',');
      if (intentFilter.size) params.intent = Array.from(intentFilter).join(',');
      if (segmentFilter.size) params.segment = Array.from(segmentFilter).join(',');
      if (tagFilter.size) params.tags = Array.from(tagFilter).join(',');
      if (geoFilter.size) params.geo = Array.from(geoFilter).join(',');
      if (searchText) params.search = searchText;
      if (dateFrom) params.date_from = dateFrom;

      const [listData, summaryData] = await Promise.all([
        intelligenceApi.list(params),
        intelligenceApi.summary(projectId, dateFrom),
      ]);
      setItems(listData);
      setSummary(summaryData);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [projectId, intentGroupFilter, offerFilter, intentFilter, segmentFilter, tagFilter, geoFilter, searchText, dateFrom]);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Analyze ──
  const handleAnalyze = async (useAi = true) => {
    if (!projectId) return;
    try {
      setAnalyzing(true);
      await intelligenceApi.analyze(projectId, false, useAi);
      await loadData();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  // ── Group items ──
  const grouped = useMemo(() => {
    const groups: Record<string, ReplyAnalysisItem[]> = {};
    for (const group of INTENT_GROUP_ORDER) groups[group] = [];
    for (const item of items) {
      const group = item.intent_group || 'noise';
      if (!groups[group]) groups[group] = [];
      groups[group].push(item);
    }
    return groups;
  }, [items]);

  // ── Filter options from summary ──
  const offerOptions = useMemo(() =>
    summary ? Object.entries(summary.by_offer).map(([v, c]) => ({ value: v, label: v, count: c })) : [],
    [summary]
  );
  const intentOptions = useMemo(() =>
    summary ? Object.entries(summary.by_intent).map(([v, c]) => ({ value: v, label: INTENT_LABELS[v] || v, count: c })) : [],
    [summary]
  );
  const segmentOptions = useMemo(() =>
    summary ? Object.entries(summary.by_segment).map(([v, c]) => ({ value: v, label: v, count: c })) : [],
    [summary]
  );
  const tagOptions = useMemo(() =>
    summary?.by_tag ? Object.entries(summary.by_tag).map(([v, c]) => ({ value: v, label: v, count: c })) : [],
    [summary]
  );
  const geoOptions = useMemo(() =>
    summary?.by_geo ? Object.entries(summary.by_geo).map(([v, c]) => ({ value: v, label: v, count: c })) : [],
    [summary]
  );

  const toggleSet = (setter: React.Dispatch<React.SetStateAction<Set<string>>>, value: string) => {
    setter(prev => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  };

  const toggleRow = (id: number) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleGroup = (group: string) => {
    setCollapsedGroups(prev => {
      const next = new Set(prev);
      if (next.has(group)) next.delete(group); else next.add(group);
      return next;
    });
  };

  const hasFilters = intentGroupFilter || offerFilter.size || intentFilter.size || segmentFilter.size || tagFilter.size || geoFilter.size || searchText || period;

  const clearFilters = () => {
    setIntentGroupFilter(null);
    setOfferFilter(new Set());
    setIntentFilter(new Set());
    setSegmentFilter(new Set());
    setTagFilter(new Set());
    setGeoFilter(new Set());
    setSearchText('');
    setPeriod(0);
  };

  const gc = isDark ? GROUP_COLORS : GROUP_COLORS_LIGHT;
  const oc = isDark ? OFFER_COLORS : OFFER_COLORS_LIGHT;

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header bar */}
      <div className="flex-none px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: t.cardBorder }}>
        <div className="flex items-center gap-3">
          <Brain className="w-5 h-5" style={{ color: t.text2 }} />
          <span className="text-[15px] font-semibold" style={{ color: t.text1 }}>
            Reply Intelligence
          </span>
          {summary && (
            <span className="text-[12px]" style={{ color: t.text2 }}>
              {summary.total} analyzed
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Period selector */}
          <div className="flex items-center gap-0.5 p-0.5 rounded-lg" style={{ background: isDark ? '#2a2a2a' : '#e8e8e8' }}>
            {PERIOD_OPTIONS.map(opt => (
              <button
                key={opt.days}
                onClick={() => setPeriod(opt.days)}
                className="px-2.5 py-1 rounded-md text-[11px] font-medium transition-all"
                style={{
                  background: period === opt.days ? (isDark ? '#3c3c3c' : '#fff') : 'transparent',
                  color: period === opt.days ? t.text1 : t.text4,
                  boxShadow: period === opt.days ? (isDark ? '0 1px 3px rgba(0,0,0,0.3)' : '0 1px 3px rgba(0,0,0,0.08)') : 'none',
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => handleAnalyze(true)}
            disabled={analyzing}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded text-[12px] font-medium transition-colors',
              isDark
                ? 'bg-blue-600 hover:bg-blue-500 text-white disabled:bg-zinc-700 disabled:text-zinc-400'
                : 'bg-blue-600 hover:bg-blue-500 text-white disabled:bg-zinc-200 disabled:text-zinc-400',
            )}
          >
            {analyzing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            {analyzing ? 'Analyzing...' : 'Analyze (AI)'}
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="flex-none px-4 py-3 border-b flex gap-3 overflow-x-auto" style={{ borderColor: t.cardBorder }}>
          {INTENT_GROUP_ORDER.map(group => (
            <button
              key={group}
              onClick={() => setIntentGroupFilter(intentGroupFilter === group ? null : group)}
              className={cn(
                'flex flex-col items-center px-4 py-2 rounded-lg border transition-all min-w-[100px]',
                gc[group].bg, gc[group].border,
                intentGroupFilter === group ? 'ring-2 ring-blue-500' : '',
              )}
            >
              <span className={cn('text-[18px] font-bold', gc[group].text)}>
                {summary.by_group[group] || 0}
              </span>
              <span className="text-[11px]" style={{ color: t.text2 }}>
                {GROUP_LABELS[group]}
              </span>
            </button>
          ))}

          {/* Top tags + geo as compact chips */}
          {((summary.by_tag && Object.keys(summary.by_tag).length > 0) || (summary.by_geo && Object.keys(summary.by_geo).length > 0)) && (
            <div className="border-l ml-2 pl-3 flex gap-1 items-center flex-wrap max-w-[400px]" style={{ borderColor: t.cardBorder }}>
              {summary.by_tag && Object.entries(summary.by_tag).slice(0, 5).map(([tag, count]) => (
                <button
                  key={tag}
                  onClick={() => toggleSet(setTagFilter, tag)}
                  className={cn(
                    'px-1.5 py-0.5 rounded text-[9px] font-medium transition-all',
                    isDark ? 'bg-violet-500/15 text-violet-300' : 'bg-violet-50 text-violet-600',
                    tagFilter.has(tag) ? 'ring-1 ring-blue-500' : '',
                  )}
                >
                  {tag}: {count}
                </button>
              ))}
              {summary.by_geo && Object.entries(summary.by_geo).slice(0, 4).map(([geo, count]) => (
                <button
                  key={geo}
                  onClick={() => toggleSet(setGeoFilter, geo)}
                  className={cn(
                    'px-1.5 py-0.5 rounded text-[9px] font-medium transition-all',
                    isDark ? 'bg-emerald-500/15 text-emerald-300' : 'bg-emerald-50 text-emerald-600',
                    geoFilter.has(geo) ? 'ring-1 ring-blue-500' : '',
                  )}
                >
                  {geo}: {count}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Filters bar */}
      <div className="flex-none px-4 py-2 border-b flex gap-2 items-center flex-wrap" style={{ borderColor: t.cardBorder }}>
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: t.text2 }} />
          <input
            type="text"
            placeholder="Search replies, leads, companies..."
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && loadData()}
            className={cn(
              'w-full pl-8 pr-3 py-1.5 rounded text-[12px] border outline-none',
              isDark ? 'bg-[#2a2a2a] border-zinc-700 text-white placeholder-zinc-500' : 'bg-white border-zinc-200 text-zinc-900 placeholder-zinc-400',
            )}
          />
        </div>
        <MultiSelectFilter label="Offer" options={offerOptions} selected={offerFilter} onToggle={v => toggleSet(setOfferFilter, v)} isDark={isDark} />
        <MultiSelectFilter label="Intent" options={intentOptions} selected={intentFilter} onToggle={v => toggleSet(setIntentFilter, v)} isDark={isDark} />
        <MultiSelectFilter label="Segment" options={segmentOptions} selected={segmentFilter} onToggle={v => toggleSet(setSegmentFilter, v)} isDark={isDark} />
        {tagFilter.size > 0 && (
          <div className="flex items-center gap-1">
            {Array.from(tagFilter).map(tag => (
              <button key={tag} onClick={() => toggleSet(setTagFilter, tag)} className={cn('flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium', isDark ? 'bg-violet-500/20 text-violet-300' : 'bg-violet-100 text-violet-600')}>
                {tag} <X className="w-2.5 h-2.5" />
              </button>
            ))}
          </div>
        )}
        {geoFilter.size > 0 && (
          <div className="flex items-center gap-1">
            {Array.from(geoFilter).map(geo => (
              <button key={geo} onClick={() => toggleSet(setGeoFilter, geo)} className={cn('flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium', isDark ? 'bg-emerald-500/20 text-emerald-300' : 'bg-emerald-100 text-emerald-600')}>
                {geo} <X className="w-2.5 h-2.5" />
              </button>
            ))}
          </div>
        )}
        {hasFilters && (
          <button
            onClick={clearFilters}
            className="flex items-center gap-1 text-[11px] px-2 py-1 rounded hover:bg-zinc-700/50"
            style={{ color: t.text2 }}
          >
            <X className="w-3 h-3" /> Clear
          </button>
        )}
      </div>

      {/* Error */}
      {error && <div className="px-4 py-3 text-red-400 text-[13px]">{error}</div>}

      {/* Table */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin" style={{ color: t.text2 }} />
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-3">
            <Brain className="w-10 h-10" style={{ color: t.text2 }} />
            <p className="text-[13px]" style={{ color: t.text2 }}>
              No analyzed replies yet. Click "Analyze (AI)" to classify all replies.
            </p>
          </div>
        ) : (
          <div className="pb-4">
            {INTENT_GROUP_ORDER.map(group => {
              const groupItems = grouped[group] || [];
              if (groupItems.length === 0) return null;
              const isCollapsed = collapsedGroups.has(group);

              return (
                <div key={group} className="border-b" style={{ borderColor: t.cardBorder }}>
                  {/* Group header */}
                  <div className={cn(
                    'w-full px-4 py-2 flex items-center gap-2 transition-colors',
                    isDark ? 'hover:bg-zinc-800/50' : 'hover:bg-zinc-50',
                  )}>
                    <button onClick={() => toggleGroup(group)} className="flex items-center gap-2 flex-1 text-left">
                      {isCollapsed
                        ? <ChevronRight className="w-4 h-4" style={{ color: t.text2 }} />
                        : <ChevronDown className="w-4 h-4" style={{ color: t.text2 }} />
                      }
                      <span className={cn('text-[13px] font-semibold', gc[group].text)}>{GROUP_LABELS[group]}</span>
                      <span className={cn('text-[11px] px-1.5 py-0.5 rounded', gc[group].bg, gc[group].text)}>{groupItems.length}</span>
                    </button>
                    {group !== 'noise' && (
                      <a
                        href={`/contacts?project_id=${projectId}&replied=true&reply_category=${GROUP_CRM_CATEGORIES[group] || ''}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={cn(
                          'flex items-center gap-1 text-[11px] px-2 py-0.5 rounded transition-colors',
                          isDark ? 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700/50' : 'text-zinc-500 hover:text-zinc-700 hover:bg-zinc-100',
                        )}
                        onClick={e => e.stopPropagation()}
                      >
                        <ExternalLink className="w-3 h-3" /> View in CRM
                      </a>
                    )}
                  </div>

                  {/* Group items */}
                  {!isCollapsed && (
                    <div>
                      {/* Column headers */}
                      <div
                        className={cn('grid grid-cols-[1fr_0.8fr_110px_70px_90px_50px_1.2fr_1fr_0.7fr_70px_32px] px-4 py-1 text-[10px] uppercase tracking-wider',
                          isDark ? 'bg-zinc-800/30' : 'bg-zinc-50',
                        )}
                        style={{ color: t.text2 }}
                      >
                        <span>Lead</span>
                        <span>Company</span>
                        <span>Website</span>
                        <span>Offer</span>
                        <span>Intent</span>
                        <span>W</span>
                        <span>Interests</span>
                        <span>Tags</span>
                        <span>Geo</span>
                        <span>Date</span>
                        <span></span>
                      </div>

                      {groupItems.map(item => (
                        <div key={item.id}>
                          <div
                            onClick={() => toggleRow(item.id)}
                            className={cn(
                              'grid grid-cols-[1fr_0.8fr_110px_70px_90px_50px_1.2fr_1fr_0.7fr_70px_32px] px-4 py-2 cursor-pointer items-center border-t transition-colors',
                              isDark ? 'border-zinc-800 hover:bg-zinc-800/40' : 'border-zinc-100 hover:bg-zinc-50',
                            )}
                          >
                            <span className="text-[12px] truncate" style={{ color: t.text1 }}>
                              {item.lead_name?.trim() || item.lead_email || '—'}
                            </span>
                            <span className="text-[12px] truncate" style={{ color: t.text2 }}>
                              {item.lead_company || '—'}
                            </span>
                            <span className="text-[11px] truncate">
                              {item.lead_domain ? (
                                <a
                                  href={`https://${item.lead_domain}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  onClick={e => e.stopPropagation()}
                                  className="text-blue-400 hover:underline"
                                >
                                  {item.lead_domain}
                                </a>
                              ) : '—'}
                            </span>
                            <span className={cn(
                              'text-[10px] px-1.5 py-0.5 rounded font-medium w-fit cursor-pointer',
                              oc[item.offer_responded_to || 'general'] || (isDark ? 'bg-zinc-700 text-zinc-300' : 'bg-zinc-100 text-zinc-600'),
                            )}
                              onClick={e => { e.stopPropagation(); toggleSet(setOfferFilter, item.offer_responded_to || 'general'); }}
                            >
                              {item.offer_responded_to || 'general'}
                            </span>
                            <span
                              className="text-[11px] cursor-pointer hover:underline"
                              style={{ color: t.text2 }}
                              onClick={e => { e.stopPropagation(); toggleSet(setIntentFilter, item.intent || ''); }}
                            >
                              {INTENT_LABELS[item.intent || ''] || item.intent || '—'}
                            </span>
                            <WarmthDots score={item.warmth_score} isDark={isDark} />
                            <span className="text-[11px] truncate" style={{ color: t.text2 }}>
                              {item.interests || '—'}
                            </span>
                            {/* Tags column */}
                            <div className="flex flex-wrap gap-0.5 overflow-hidden max-h-[20px]">
                              {item.tags && item.tags.length > 0 ? item.tags.slice(0, 3).map(tag => (
                                <button
                                  key={tag}
                                  onClick={e => { e.stopPropagation(); toggleSet(setTagFilter, tag); }}
                                  className={cn(
                                    'px-1 py-0 rounded text-[9px] font-medium whitespace-nowrap',
                                    isDark ? 'bg-violet-500/15 text-violet-300 hover:bg-violet-500/30' : 'bg-violet-50 text-violet-600 hover:bg-violet-100',
                                    tagFilter.has(tag) && 'ring-1 ring-blue-500',
                                  )}
                                >
                                  {tag}
                                </button>
                              )) : <span className="text-[10px]" style={{ color: t.text2 }}>—</span>}
                            </div>
                            {/* Geo column */}
                            <div className="flex flex-wrap gap-0.5 overflow-hidden max-h-[20px]">
                              {item.geo_tags && item.geo_tags.length > 0 ? item.geo_tags.slice(0, 2).map(geo => (
                                <button
                                  key={geo}
                                  onClick={e => { e.stopPropagation(); toggleSet(setGeoFilter, geo); }}
                                  className={cn(
                                    'px-1 py-0 rounded text-[9px] font-medium whitespace-nowrap',
                                    isDark ? 'bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/30' : 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100',
                                    geoFilter.has(geo) && 'ring-1 ring-blue-500',
                                  )}
                                >
                                  {geo}
                                </button>
                              )) : <span className="text-[10px]" style={{ color: t.text2 }}>—</span>}
                            </div>
                            <span className="text-[10px]" style={{ color: t.text2 }}>
                              {item.received_at ? new Date(item.received_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : '—'}
                            </span>
                            <a
                              href={item.contact_id
                                ? `/contacts/${item.contact_id}?tab=conversation`
                                : `/contacts?project_id=${item.project_id}&search=${encodeURIComponent(item.lead_email || '')}`
                              }
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={e => e.stopPropagation()}
                              className="text-blue-400 hover:text-blue-300"
                            >
                              <ExternalLink className="w-3.5 h-3.5" />
                            </a>
                          </div>

                          {/* Expanded detail */}
                          {expandedRows.has(item.id) && (
                            <div className={cn('px-6 py-3 border-t', isDark ? 'bg-zinc-900/50 border-zinc-800' : 'bg-zinc-50 border-zinc-100')}>
                              <div className="grid grid-cols-2 gap-4 text-[12px]">
                                <div>
                                  <div className="font-medium mb-1" style={{ color: t.text1 }}>Reply</div>
                                  <div className="whitespace-pre-wrap leading-relaxed max-h-[200px] overflow-y-auto" style={{ color: t.text2 }}>
                                    {item.reply_text || '(empty)'}
                                  </div>
                                </div>
                                <div className="space-y-2">
                                  {item.interests && (
                                    <div>
                                      <span className="font-medium" style={{ color: t.text1 }}>Interests: </span>
                                      <span style={{ color: t.text2 }}>{item.interests}</span>
                                    </div>
                                  )}
                                  {item.tags && item.tags.length > 0 && (
                                    <div>
                                      <span className="font-medium block mb-1" style={{ color: t.text1 }}>Tags:</span>
                                      <div className="flex flex-wrap gap-1">
                                        {item.tags.map(tag => (
                                          <TagChip
                                            key={tag}
                                            tag={tag}
                                            isDark={isDark}
                                            onClick={() => toggleSet(setTagFilter, tag)}
                                          />
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                  {item.geo_tags && item.geo_tags.length > 0 && (
                                    <div>
                                      <span className="font-medium block mb-1" style={{ color: t.text1 }}>Geography:</span>
                                      <div className="flex flex-wrap gap-1">
                                        {item.geo_tags.map(geo => (
                                          <button
                                            key={geo}
                                            onClick={() => toggleSet(setGeoFilter, geo)}
                                            className={cn(
                                              'inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium transition-colors',
                                              isDark
                                                ? 'bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25'
                                                : 'bg-emerald-50 text-emerald-600 hover:bg-emerald-100',
                                            )}
                                          >
                                            {geo}
                                          </button>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                  <div>
                                    <span className="font-medium" style={{ color: t.text1 }}>Campaign: </span>
                                    <span style={{ color: t.text2 }}>{item.campaign_name}</span>
                                  </div>
                                  <div>
                                    <span className="font-medium" style={{ color: t.text1 }}>Segment: </span>
                                    <span style={{ color: t.text2 }}>{item.campaign_segment || '—'}</span>
                                  </div>
                                  <div>
                                    <span className="font-medium" style={{ color: t.text1 }}>Status: </span>
                                    <span style={{ color: t.text2 }}>{item.approval_status || 'pending'}</span>
                                  </div>
                                  <div>
                                    <span className="font-medium" style={{ color: t.text1 }}>Model: </span>
                                    <span style={{ color: t.text2 }}>{item.reasoning === 'deterministic_v1' ? 'Rules' : 'Gemini AI'}</span>
                                  </div>
                                  <a
                                    href={item.contact_id
                                      ? `/contacts/${item.contact_id}?tab=conversation`
                                      : `/contacts?project_id=${item.project_id}&search=${encodeURIComponent(item.lead_email || '')}`
                                    }
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 text-[12px]"
                                  >
                                    <ExternalLink className="w-3 h-3" /> Open in CRM
                                  </a>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
