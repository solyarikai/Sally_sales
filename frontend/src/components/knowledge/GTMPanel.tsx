import { useState, useEffect } from 'react';
import { Loader2, RefreshCw, Target, TrendingUp, ExternalLink, BarChart3, Sparkles, Users, Search } from 'lucide-react';
import type { ThemeTokens } from '../../lib/themeColors';
import { contactsApi } from '../../api/contacts';
import type { GTMData } from '../../api/contacts';

interface Props {
  projectId: number;
  isDark: boolean;
  t: ThemeTokens;
}

interface GTMSegment {
  segment: string;
  priority: number;
  size: number;
  rationale?: string;
  characteristics?: string[];
  apollo_query?: string;
  outreach_angle?: string;
}

interface GTMPlan {
  segments: GTMSegment[];
  summary?: string;
  total_addressable?: string;
}

function parseGTMPlan(raw?: string | null): GTMPlan | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (parsed.segments && Array.isArray(parsed.segments)) {
      return parsed as GTMPlan;
    }
    if (Array.isArray(parsed)) {
      return { segments: parsed };
    }
  } catch {
    // Not JSON
  }
  return null;
}

function crmLink(projectId: number, params: Record<string, string>): string {
  const p = new URLSearchParams({ project_id: String(projectId), ...params });
  return `/contacts?${p.toString()}`;
}

export function GTMPanel({ projectId, isDark, t }: Props) {
  const [data, setData] = useState<GTMData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, [projectId]);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const result = await contactsApi.getGTMData(projectId);
      setData(result);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load GTM data');
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    try {
      const result = await contactsApi.generateGTM(projectId);
      // Refresh data to get updated gtm_plan
      if (result.gtm_plan) {
        setData(prev => prev ? { ...prev, gtm_plan: result.gtm_plan! } : null);
      } else {
        await loadData();
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'GTM generation failed');
    } finally {
      setGenerating(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-5 h-5 animate-spin" style={{ color: t.text4 }} />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex flex-col items-center justify-center py-20 px-6">
        <p className="text-[13px] mb-4" style={{ color: '#ef4444' }}>{error}</p>
        <button onClick={loadData} className="text-[13px] underline" style={{ color: t.text3 }}>Retry</button>
      </div>
    );
  }

  if (!data) return null;

  const plan = parseGTMPlan(data.gtm_plan);
  const hasClassified = data.classified > 0;
  const maxSegmentCount = data.segments.length > 0 ? data.segments[0].count : 1;

  return (
    <div className="p-5 space-y-6 max-w-[900px]">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-[15px] font-semibold" style={{ color: t.text1 }}>
            Go-To-Market Strategy
          </h3>
          <p className="text-[12px] mt-0.5" style={{ color: t.text4 }}>
            {data.classified} classified / {data.total_contacts} total contacts
            {data.avg_confidence != null && ` · avg confidence ${(data.avg_confidence * 100).toFixed(0)}%`}
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors"
          style={{ background: isDark ? '#2d2d2d' : '#f0f0f0', color: t.text2 }}
        >
          {generating ? (
            <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Generating (Gemini 2.5)...</>
          ) : (
            <><Sparkles className="w-3.5 h-3.5" /> {plan ? 'Regenerate' : 'Generate'} Strategy</>
          )}
        </button>
      </div>

      {error && (
        <div className="rounded-lg px-3 py-2 text-[12px]" style={{ background: isDark ? '#3b1c1c' : '#fef2f2', color: '#ef4444' }}>
          {error}
        </div>
      )}

      {/* Section 1: Segment Intelligence (real DB data) */}
      {hasClassified && (
        <section>
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 className="w-4 h-4" style={{ color: t.text3 }} />
            <h4 className="text-[13px] font-semibold uppercase tracking-wide" style={{ color: t.text3 }}>
              Segment Distribution
            </h4>
          </div>
          <div className="space-y-1.5">
            {data.segments.map(seg => {
              const pct = Math.round((seg.count / data.total_contacts) * 100);
              const barWidth = Math.round((seg.count / maxSegmentCount) * 100);
              return (
                <a
                  key={seg.segment}
                  href={crmLink(projectId, { segment: seg.segment })}
                  className="flex items-center gap-3 group rounded-lg px-3 py-2 transition-colors"
                  style={{ background: isDark ? '#1a1a1a' : '#fafafa' }}
                >
                  <span className="text-[12px] font-medium w-[140px] shrink-0 truncate" style={{ color: t.text1 }}>
                    {seg.segment}
                  </span>
                  <div className="flex-1 h-5 rounded-full overflow-hidden" style={{ background: isDark ? '#2a2a2a' : '#e5e7eb' }}>
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${barWidth}%`,
                        background: isDark ? '#3b82f6' : '#3b82f6',
                        opacity: isDark ? 0.7 : 0.8,
                      }}
                    />
                  </div>
                  <span className="text-[12px] font-mono w-[60px] text-right shrink-0" style={{ color: t.text2 }}>
                    {seg.count}
                  </span>
                  <span className="text-[11px] w-[40px] text-right shrink-0" style={{ color: t.text4 }}>
                    {pct}%
                  </span>
                  <ExternalLink className="w-3 h-3 opacity-0 group-hover:opacity-50 shrink-0" style={{ color: t.text4 }} />
                </a>
              );
            })}
          </div>
        </section>
      )}

      {/* Section 2: Cross-project matches */}
      {data.cross_project_matches.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-3">
            <Users className="w-4 h-4" style={{ color: t.text3 }} />
            <h4 className="text-[13px] font-semibold uppercase tracking-wide" style={{ color: t.text3 }}>
              Cross-Project Matches
            </h4>
          </div>
          <div className="flex flex-wrap gap-2">
            {data.cross_project_matches.map(m => (
              <a
                key={m.target}
                href={crmLink(projectId, { suitable_for: m.target })}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors"
                style={{
                  background: isDark ? '#0a2e1a' : '#dcfce7',
                  color: isDark ? '#86efac' : '#16a34a',
                  border: `1px solid ${isDark ? '#166534' : '#bbf7d0'}`,
                }}
              >
                <Target className="w-3 h-3" />
                {m.count} suitable for {m.target}
                <ExternalLink className="w-3 h-3 opacity-50" />
              </a>
            ))}
          </div>
        </section>
      )}

      {/* Section 3: Top Industries */}
      {data.industries.length > 0 && (
        <section>
          <div className="flex items-center gap-2 mb-3">
            <Search className="w-4 h-4" style={{ color: t.text3 }} />
            <h4 className="text-[13px] font-semibold uppercase tracking-wide" style={{ color: t.text3 }}>
              Top Industries
            </h4>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {data.industries.slice(0, 15).map(ind => (
              <span
                key={ind.industry}
                className="px-2 py-1 rounded text-[11px] font-medium"
                style={{
                  background: isDark ? '#1e293b' : '#f1f5f9',
                  color: t.text2,
                }}
              >
                {ind.industry} ({ind.count})
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Section 4: AI GTM Strategy (Gemini 2.5) */}
      {plan ? (
        <section>
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-4 h-4" style={{ color: t.text3 }} />
            <h4 className="text-[13px] font-semibold uppercase tracking-wide" style={{ color: t.text3 }}>
              AI Strategy (Gemini 2.5)
            </h4>
          </div>

          {plan.summary && (
            <p className="text-[13px] mb-4 leading-relaxed" style={{ color: t.text2 }}>
              {plan.summary}
            </p>
          )}

          <div className="grid gap-3">
            {plan.segments.sort((a, b) => (a.priority ?? 99) - (b.priority ?? 99)).map((seg, i) => (
              <div
                key={i}
                className="rounded-xl p-4"
                style={{ background: t.cardBg, border: `1px solid ${t.cardBorder}` }}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold"
                      style={{
                        background: i < 3 ? (isDark ? '#1e3a5f' : '#dbeafe') : (isDark ? '#2d2d2d' : '#f0f0f0'),
                        color: i < 3 ? (isDark ? '#93c5fd' : '#1d4ed8') : t.text3,
                      }}
                    >
                      {seg.priority ?? i + 1}
                    </span>
                    <h5 className="text-[13px] font-semibold" style={{ color: t.text1 }}>
                      {seg.segment}
                    </h5>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className="px-2 py-0.5 rounded text-[11px] font-medium"
                      style={{
                        background: isDark ? '#1a2e1a' : '#dcfce7',
                        color: isDark ? '#86efac' : '#16a34a',
                      }}
                    >
                      {seg.size} leads
                    </span>
                    <a
                      href={crmLink(projectId, { segment: seg.segment })}
                      className="text-[11px] underline opacity-60 hover:opacity-100"
                      style={{ color: t.text3 }}
                    >
                      View in CRM
                    </a>
                  </div>
                </div>

                {seg.rationale && (
                  <p className="text-[12px] mb-2 leading-relaxed" style={{ color: t.text2 }}>
                    {seg.rationale}
                  </p>
                )}

                {seg.characteristics && seg.characteristics.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 mb-2">
                    {seg.characteristics.map((ch, j) => (
                      <span
                        key={j}
                        className="px-2 py-0.5 rounded text-[11px]"
                        style={{ background: isDark ? '#2d2d2d' : '#f0f0f0', color: t.text2 }}
                      >
                        {ch}
                      </span>
                    ))}
                  </div>
                )}

                {seg.outreach_angle && (
                  <p className="text-[12px] mb-2" style={{ color: t.text3 }}>
                    <span className="font-medium" style={{ color: t.text2 }}>Outreach:</span> {seg.outreach_angle}
                  </p>
                )}

                {seg.apollo_query && (
                  <div className="mt-2">
                    <span className="text-[10px] font-medium uppercase tracking-wider" style={{ color: t.text4 }}>
                      Apollo Query
                    </span>
                    <p
                      className="text-[12px] mt-1 p-2 rounded-lg font-mono leading-relaxed"
                      style={{ background: isDark ? '#1a1a1a' : '#f5f5f5', color: t.text3 }}
                    >
                      {seg.apollo_query}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>

          {plan.total_addressable && (
            <p className="text-[12px] mt-3" style={{ color: t.text4 }}>
              Estimated total addressable: {plan.total_addressable}
            </p>
          )}
        </section>
      ) : !hasClassified ? (
        <div className="flex flex-col items-center justify-center py-12 px-6">
          <Target className="w-10 h-10 mb-3 opacity-30" style={{ color: t.text4 }} />
          <p className="text-[13px] mb-1" style={{ color: t.text2 }}>No classified contacts yet</p>
          <p className="text-[12px] mb-4" style={{ color: t.text4 }}>
            Run segment classification first, then generate a GTM strategy
          </p>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-12 px-6">
          <Sparkles className="w-10 h-10 mb-3 opacity-30" style={{ color: t.text4 }} />
          <p className="text-[13px] mb-1" style={{ color: t.text2 }}>No AI strategy generated yet</p>
          <p className="text-[12px] mb-4" style={{ color: t.text4 }}>
            {data.classified} contacts classified across {data.segments.length} segments. Click Generate to create a strategy.
          </p>
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-medium text-white transition-colors"
            style={{ background: t.btnPrimaryBg }}
          >
            {generating ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
            ) : (
              <><Sparkles className="w-4 h-4" /> Generate GTM Strategy</>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
