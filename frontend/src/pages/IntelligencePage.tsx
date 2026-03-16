import { useState, useEffect, useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Brain, Loader2, ChevronDown, ChevronRight, ExternalLink, RefreshCw, Search, Filter } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { useAppStore } from '../store/appStore';
import { intelligenceApi } from '../api/intelligence';
import type { ReplyAnalysisItem, IntelligenceSummary } from '../api/intelligence';
import { cn } from '../lib/utils';

// ── Constants ──────────────────────────────────────────────────

const INTENT_GROUP_ORDER = ['warm', 'questions', 'soft_objection', 'hard_objection', 'noise'] as const;

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

function WarmthDots({ score, isDark }: { score: number | null; isDark: boolean }) {
  const s = score ?? 0;
  const colors = [
    'bg-red-500', 'bg-orange-400', 'bg-yellow-400', 'bg-green-400', 'bg-green-500',
  ];
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

// ── Main Page Component ────────────────────────────────────────

export function IntelligencePage() {
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const [searchParams, setSearchParams] = useSearchParams();
  const { currentProject, projects } = useAppStore();

  const projectId = Number(searchParams.get('project_id')) || currentProject?.id || null;

  const [items, setItems] = useState<ReplyAnalysisItem[]>([]);
  const [summary, setSummary] = useState<IntelligenceSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [intentGroupFilter, setIntentGroupFilter] = useState<string | null>(
    searchParams.get('intent_group') || null
  );
  const [offerFilter, setOfferFilter] = useState<string | null>(null);
  const [searchText, setSearchText] = useState('');
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set(['noise']));

  // ── Data loading ──
  const loadData = useCallback(async () => {
    if (!projectId) return;
    try {
      setLoading(true);
      setError(null);
      const [listData, summaryData] = await Promise.all([
        intelligenceApi.list({
          project_id: projectId,
          intent_group: intentGroupFilter || undefined,
          offer: offerFilter || undefined,
          search: searchText || undefined,
          page_size: 200,
        }),
        intelligenceApi.summary(projectId),
      ]);
      setItems(listData);
      setSummary(summaryData);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [projectId, intentGroupFilter, offerFilter, searchText]);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Analyze ──
  const handleAnalyze = async () => {
    if (!projectId) return;
    try {
      setAnalyzing(true);
      const result = await intelligenceApi.analyze(projectId);
      await loadData();
      setAnalyzing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analysis failed');
      setAnalyzing(false);
    }
  };

  // ── Group items ──
  const grouped = useMemo(() => {
    const groups: Record<string, ReplyAnalysisItem[]> = {};
    for (const group of INTENT_GROUP_ORDER) {
      groups[group] = [];
    }
    for (const item of items) {
      const group = item.intent_group || 'noise';
      if (!groups[group]) groups[group] = [];
      groups[group].push(item);
    }
    return groups;
  }, [items]);

  // ── Toggle row expansion ──
  const toggleRow = (id: number) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleGroup = (group: string) => {
    setCollapsedGroups(prev => {
      const next = new Set(prev);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  };

  // ── Project selector ──
  const projectName = projects?.find(p => p.id === projectId)?.name || `Project ${projectId}`;

  const gc = isDark ? GROUP_COLORS : GROUP_COLORS_LIGHT;
  const oc = isDark ? OFFER_COLORS : OFFER_COLORS_LIGHT;

  if (!projectId) {
    return (
      <div className="h-full flex items-center justify-center" style={{ color: t.text2 }}>
        Select a project to view reply intelligence.
      </div>
    );
  }

  return (
    <div className={cn('h-full flex flex-col overflow-hidden', isDark ? 'bg-[#1e1e1e]' : 'bg-white')}>
      {/* Header */}
      <div className="flex-none px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: t.cardBorder }}>
        <div className="flex items-center gap-3">
          <Brain className="w-5 h-5" style={{ color: t.text2 }} />
          <h1 className="text-[15px] font-semibold" style={{ color: t.text1 }}>
            Reply Intelligence
          </h1>
          <span className="text-[12px] px-2 py-0.5 rounded" style={{ backgroundColor: isDark ? '#2a2a2a' : '#f3f4f6', color: t.text2 }}>
            {projectName}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {summary && (
            <span className="text-[12px]" style={{ color: t.text2 }}>
              {summary.total} analyzed
            </span>
          )}
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 rounded text-[12px] font-medium transition-colors',
              isDark
                ? 'bg-blue-600 hover:bg-blue-500 text-white disabled:bg-zinc-700 disabled:text-zinc-400'
                : 'bg-blue-600 hover:bg-blue-500 text-white disabled:bg-zinc-200 disabled:text-zinc-400',
            )}
          >
            {analyzing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
            {analyzing ? 'Analyzing...' : 'Analyze'}
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

          {/* Offer breakdown */}
          <div className="border-l ml-2 pl-3 flex gap-2 items-center" style={{ borderColor: t.cardBorder }}>
            {Object.entries(summary.by_offer).slice(0, 4).map(([offer, count]) => (
              <button
                key={offer}
                onClick={() => setOfferFilter(offerFilter === offer ? null : offer)}
                className={cn(
                  'px-2.5 py-1 rounded text-[11px] font-medium transition-all',
                  oc[offer] || (isDark ? 'bg-zinc-700 text-zinc-300' : 'bg-zinc-100 text-zinc-600'),
                  offerFilter === offer ? 'ring-2 ring-blue-500' : '',
                )}
              >
                {offer}: {count}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Search */}
      <div className="flex-none px-4 py-2 border-b flex gap-2" style={{ borderColor: t.cardBorder }}>
        <div className="relative flex-1 max-w-sm">
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
        {(intentGroupFilter || offerFilter || searchText) && (
          <button
            onClick={() => { setIntentGroupFilter(null); setOfferFilter(null); setSearchText(''); }}
            className="text-[11px] px-2 py-1 rounded hover:bg-zinc-700/50" style={{ color: t.text2 }}
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Error / Loading */}
      {error && (
        <div className="px-4 py-3 text-red-400 text-[13px]">{error}</div>
      )}

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
              No analyzed replies yet. Click "Analyze" to classify all replies.
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
                  <button
                    onClick={() => toggleGroup(group)}
                    className={cn(
                      'w-full px-4 py-2 flex items-center gap-2 text-left transition-colors',
                      isDark ? 'hover:bg-zinc-800/50' : 'hover:bg-zinc-50',
                    )}
                  >
                    {isCollapsed ? (
                      <ChevronRight className="w-4 h-4" style={{ color: t.text2 }} />
                    ) : (
                      <ChevronDown className="w-4 h-4" style={{ color: t.text2 }} />
                    )}
                    <span className={cn('text-[13px] font-semibold', gc[group].text)}>
                      {GROUP_LABELS[group]}
                    </span>
                    <span className={cn('text-[11px] px-1.5 py-0.5 rounded', gc[group].bg, gc[group].text)}>
                      {groupItems.length}
                    </span>
                  </button>

                  {/* Group items */}
                  {!isCollapsed && (
                    <div>
                      {/* Column headers */}
                      <div
                        className={cn('grid grid-cols-[1fr_1fr_80px_100px_60px_80px_90px_40px] px-4 py-1 text-[10px] uppercase tracking-wider',
                          isDark ? 'bg-zinc-800/30' : 'bg-zinc-50',
                        )}
                        style={{ color: t.text2 }}
                      >
                        <span>Lead</span>
                        <span>Company</span>
                        <span>Offer</span>
                        <span>Intent</span>
                        <span>W</span>
                        <span>Segment</span>
                        <span>Date</span>
                        <span>CRM</span>
                      </div>

                      {groupItems.map(item => (
                        <div key={item.id}>
                          {/* Row */}
                          <div
                            onClick={() => toggleRow(item.id)}
                            className={cn(
                              'grid grid-cols-[1fr_1fr_80px_100px_60px_80px_90px_40px] px-4 py-2 cursor-pointer items-center border-t transition-colors',
                              isDark ? 'border-zinc-800 hover:bg-zinc-800/40' : 'border-zinc-100 hover:bg-zinc-50',
                            )}
                          >
                            <span className="text-[12px] truncate" style={{ color: t.text1 }}>
                              {item.lead_name?.trim() || item.lead_email || '—'}
                            </span>
                            <span className="text-[12px] truncate" style={{ color: t.text2 }}>
                              {item.lead_company || '—'}
                            </span>
                            <span className={cn(
                              'text-[10px] px-1.5 py-0.5 rounded font-medium w-fit',
                              oc[item.offer_responded_to || 'general'] || (isDark ? 'bg-zinc-700 text-zinc-300' : 'bg-zinc-100 text-zinc-600'),
                            )}>
                              {item.offer_responded_to || 'general'}
                            </span>
                            <span className="text-[11px]" style={{ color: t.text2 }}>
                              {INTENT_LABELS[item.intent || ''] || item.intent || '—'}
                            </span>
                            <WarmthDots score={item.warmth_score} isDark={isDark} />
                            <span className="text-[10px]" style={{ color: t.text2 }}>
                              {item.campaign_segment || '—'}
                            </span>
                            <span className="text-[10px]" style={{ color: t.text2 }}>
                              {item.received_at ? new Date(item.received_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : '—'}
                            </span>
                            <a
                              href={`/contacts?project_id=${item.project_id}&search=${encodeURIComponent(item.lead_email || '')}`}
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
                            <div
                              className={cn('px-6 py-3 border-t', isDark ? 'bg-zinc-900/50 border-zinc-800' : 'bg-zinc-50 border-zinc-100')}
                            >
                              <div className="grid grid-cols-2 gap-4 text-[12px]">
                                <div>
                                  <div className="font-medium mb-1" style={{ color: t.text1 }}>Reply</div>
                                  <div className="whitespace-pre-wrap leading-relaxed max-h-[200px] overflow-y-auto" style={{ color: t.text2 }}>
                                    {item.reply_text || '(empty)'}
                                  </div>
                                </div>
                                <div className="space-y-2">
                                  <div>
                                    <span className="font-medium" style={{ color: t.text1 }}>Campaign: </span>
                                    <span style={{ color: t.text2 }}>{item.campaign_name}</span>
                                  </div>
                                  <div>
                                    <span className="font-medium" style={{ color: t.text1 }}>Category: </span>
                                    <span style={{ color: t.text2 }}>{item.category}</span>
                                  </div>
                                  <div>
                                    <span className="font-medium" style={{ color: t.text1 }}>Status: </span>
                                    <span style={{ color: t.text2 }}>{item.approval_status || 'pending'}</span>
                                  </div>
                                  <div>
                                    <span className="font-medium" style={{ color: t.text1 }}>Sequence: </span>
                                    <span style={{ color: t.text2 }}>{item.sequence_type}</span>
                                  </div>
                                  <div>
                                    <span className="font-medium" style={{ color: t.text1 }}>Language: </span>
                                    <span style={{ color: t.text2 }}>{item.language}</span>
                                  </div>
                                  <a
                                    href={`/contacts?project_id=${item.project_id}&search=${encodeURIComponent(item.lead_email || '')}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 text-[12px]"
                                  >
                                    <ExternalLink className="w-3 h-3" />
                                    Open in CRM
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
