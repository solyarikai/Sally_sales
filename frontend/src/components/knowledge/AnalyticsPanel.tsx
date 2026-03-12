import { useState, useEffect } from 'react';
import { Loader2, BarChart3, Users, MessageSquare, CalendarCheck, ThumbsUp, Clock, ExternalLink, AlertCircle, CheckCircle2 } from 'lucide-react';
import type { ThemeTokens } from '../../lib/themeColors';
import { contactsApi } from '../../api/contacts';
import type { SegmentFunnelData, SegmentFunnelSegment, GTMStrategyLogEntry } from '../../api/contacts';

interface Props {
  projectId: number;
  isDark: boolean;
  t: ThemeTokens;
}

const PERIODS = [
  { key: '7d', label: '7d' },
  { key: '30d', label: '30d' },
  { key: '90d', label: '90d' },
  { key: 'all', label: 'All time' },
] as const;

function fmtNum(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1).replace(/\.0$/, '')}k`;
  return String(n);
}

function rateColor(rate: number, isDark: boolean): string {
  if (rate >= 10) return isDark ? '#4ade80' : '#16a34a';
  if (rate >= 5) return isDark ? '#facc15' : '#ca8a04';
  return isDark ? '#a1a1aa' : '#71717a';
}

function timeAgo(dateStr: string | null): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  const now = new Date();
  const mins = Math.floor((now.getTime() - d.getTime()) / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export function AnalyticsPanel({ projectId, isDark, t }: Props) {
  const [data, setData] = useState<SegmentFunnelData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<string>('all');
  const [logs, setLogs] = useState<GTMStrategyLogEntry[]>([]);
  const [logsLoading, setLogsLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, [projectId, period]);

  useEffect(() => {
    loadLogs();
  }, [projectId]);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const result = await contactsApi.getSegmentFunnel(projectId, period);
      setData(result);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  }

  async function loadLogs() {
    setLogsLoading(true);
    try {
      const result = await contactsApi.getGTMStrategyLogs(projectId);
      setLogs(result.items);
    } catch {
      // silent
    } finally {
      setLogsLoading(false);
    }
  }

  if (loading && !data) {
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

  if (!data || data.segments.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 px-6">
        <BarChart3 className="w-10 h-10 mb-3 opacity-30" style={{ color: t.text4 }} />
        <p className="text-[13px]" style={{ color: t.text2 }}>No campaign data available</p>
        <p className="text-[12px] mt-1" style={{ color: t.text4 }}>
          Segments are derived from campaign names. Add campaigns to see analytics.
        </p>
      </div>
    );
  }

  const { totals, segments } = data;
  const maxContacts = Math.max(...segments.map(s => s.total_contacts), 1);

  return (
    <div className="flex gap-5 p-5">
      {/* Left: Analytics */}
      <div className="flex-1 min-w-0 space-y-5 max-w-[960px]">
        {/* Header + period filter */}
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-[15px] font-semibold" style={{ color: t.text1 }}>
              Segment Funnel Analytics
            </h3>
            <p className="text-[12px] mt-0.5" style={{ color: t.text4 }}>
              Segments derived from campaign names · {segments.length} segments
            </p>
          </div>
          <div
            className="flex items-center gap-0.5 p-0.5 rounded-lg"
            style={{ background: isDark ? '#2a2a2a' : '#e8e8e8' }}
          >
            {PERIODS.map(p => {
              const isActive = period === p.key;
              return (
                <button
                  key={p.key}
                  onClick={() => setPeriod(p.key)}
                  className="px-3 py-1 rounded-md text-[12px] font-medium transition-all cursor-pointer"
                  style={{
                    background: isActive ? (isDark ? '#3c3c3c' : '#ffffff') : 'transparent',
                    color: isActive ? t.text1 : t.text4,
                    boxShadow: isActive ? (isDark ? '0 1px 3px rgba(0,0,0,0.3)' : '0 1px 3px rgba(0,0,0,0.08)') : 'none',
                  }}
                >
                  {p.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-4 gap-3">
          {[
            { icon: Users, label: 'Contacts', value: totals.total_contacts, color: isDark ? '#60a5fa' : '#2563eb' },
            { icon: MessageSquare, label: 'Replies', value: totals.total_replies, color: isDark ? '#a78bfa' : '#7c3aed' },
            { icon: ThumbsUp, label: 'Positive', value: totals.positive, color: isDark ? '#4ade80' : '#16a34a' },
            { icon: CalendarCheck, label: 'Meetings', value: totals.meeting_requests, color: isDark ? '#f59e0b' : '#d97706' },
          ].map(card => (
            <div
              key={card.label}
              className="rounded-xl px-4 py-3"
              style={{ background: t.cardBg, border: `1px solid ${t.cardBorder}` }}
            >
              <div className="flex items-center gap-1.5 mb-1">
                <card.icon className="w-3.5 h-3.5" style={{ color: card.color }} />
                <span className="text-[11px] font-medium uppercase tracking-wide" style={{ color: t.text4 }}>
                  {card.label}
                </span>
              </div>
              <span className="text-[20px] font-bold" style={{ color: t.text1 }}>
                {fmtNum(card.value)}
              </span>
            </div>
          ))}
        </div>

        {loading && (
          <div className="flex items-center gap-2 text-[12px]" style={{ color: t.text4 }}>
            <Loader2 className="w-3.5 h-3.5 animate-spin" /> Updating...
          </div>
        )}

        {/* Segment funnel table */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <BarChart3 className="w-4 h-4" style={{ color: t.text3 }} />
            <h4 className="text-[13px] font-semibold uppercase tracking-wide" style={{ color: t.text3 }}>
              Segments
            </h4>
          </div>

          {/* Table header */}
          <div
            className="grid gap-2 px-3 py-2 rounded-t-lg text-[11px] font-medium uppercase tracking-wide"
            style={{
              gridTemplateColumns: '140px 1fr 70px 60px 60px 60px 60px 60px',
              background: isDark ? '#1a1a1a' : '#f5f5f5',
              color: t.text4,
            }}
          >
            <span>Segment</span>
            <span>Contacts</span>
            <span className="text-right">Replies</span>
            <span className="text-right">Reply%</span>
            <span className="text-right">Positive</span>
            <span className="text-right">Pos%</span>
            <span className="text-right">Meetings</span>
            <span className="text-right">Not Int.</span>
          </div>

          {/* Rows */}
          <div className="divide-y" style={{ borderColor: isDark ? '#2a2a2a' : '#f0f0f0' }}>
            {segments.map((seg: SegmentFunnelSegment) => {
              const barWidth = Math.round((seg.total_contacts / maxContacts) * 100);
              return (
                <div
                  key={seg.segment}
                  className="grid gap-2 px-3 py-2.5 items-center transition-colors"
                  style={{
                    gridTemplateColumns: '140px 1fr 70px 60px 60px 60px 60px 60px',
                    borderColor: isDark ? '#2a2a2a' : '#f0f0f0',
                  }}
                >
                  <span className="text-[12px] font-medium truncate" style={{ color: t.text1 }}>
                    {seg.segment}
                  </span>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-4 rounded-full overflow-hidden" style={{ background: isDark ? '#2a2a2a' : '#e5e7eb' }}>
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${barWidth}%`,
                          background: isDark ? '#3b82f6' : '#3b82f6',
                          opacity: isDark ? 0.7 : 0.8,
                        }}
                      />
                    </div>
                    <span className="text-[12px] font-mono w-[50px] text-right shrink-0" style={{ color: t.text2 }}>
                      {fmtNum(seg.total_contacts)}
                    </span>
                  </div>
                  <span className="text-[12px] font-mono text-right" style={{ color: t.text2 }}>
                    {fmtNum(seg.total_replies)}
                  </span>
                  <span className="text-[12px] font-mono text-right font-medium" style={{ color: rateColor(seg.reply_rate, isDark) }}>
                    {seg.reply_rate > 0 ? `${seg.reply_rate}%` : '-'}
                  </span>
                  <span className="text-[12px] font-mono text-right" style={{ color: seg.positive > 0 ? (isDark ? '#4ade80' : '#16a34a') : t.text4 }}>
                    {seg.positive || '-'}
                  </span>
                  <span className="text-[12px] font-mono text-right font-medium" style={{ color: rateColor(seg.positive_rate, isDark) }}>
                    {seg.positive_rate > 0 ? `${seg.positive_rate}%` : '-'}
                  </span>
                  <span className="text-[12px] font-mono text-right" style={{ color: seg.meeting_requests > 0 ? (isDark ? '#f59e0b' : '#d97706') : t.text4 }}>
                    {seg.meeting_requests || '-'}
                  </span>
                  <span className="text-[12px] font-mono text-right" style={{ color: t.text4 }}>
                    {seg.not_interested || '-'}
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      </div>

      {/* Right: Analytics Thinking Logs */}
      <div className="w-[280px] shrink-0">
        <div
          className="rounded-xl overflow-hidden"
          style={{ background: t.cardBg, border: `1px solid ${t.cardBorder}` }}
        >
          <div className="px-4 py-3" style={{ borderBottom: `1px solid ${t.cardBorder}` }}>
            <div className="flex items-center gap-2">
              <Clock className="w-3.5 h-3.5" style={{ color: t.text3 }} />
              <h4 className="text-[13px] font-semibold" style={{ color: t.text1 }}>
                Analytics Thinking
              </h4>
            </div>
            <p className="text-[11px] mt-0.5" style={{ color: t.text4 }}>
              Opus 4.6 GTM strategy runs (2x daily)
            </p>
          </div>

          <div className="max-h-[500px] overflow-y-auto">
            {logsLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-4 h-4 animate-spin" style={{ color: t.text4 }} />
              </div>
            ) : logs.length === 0 ? (
              <div className="px-4 py-6 text-center">
                <p className="text-[12px]" style={{ color: t.text4 }}>No strategy runs yet</p>
                <p className="text-[11px] mt-1" style={{ color: t.text4 }}>
                  Generate one from the GTM Strategy tab
                </p>
              </div>
            ) : (
              <div className="divide-y" style={{ borderColor: isDark ? '#2a2a2a' : '#f0f0f0' }}>
                {logs.map(log => (
                  <a
                    key={log.id}
                    href={`/knowledge/gtm?project=${new URLSearchParams(window.location.search).get('project') || ''}&logId=${log.id}`}
                    className="block px-4 py-3 transition-colors hover:opacity-80"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-1.5">
                        {log.status === 'completed' ? (
                          <CheckCircle2 className="w-3 h-3" style={{ color: isDark ? '#4ade80' : '#16a34a' }} />
                        ) : (
                          <AlertCircle className="w-3 h-3" style={{ color: '#ef4444' }} />
                        )}
                        <span className="text-[11px] font-medium" style={{ color: t.text2 }}>
                          {log.trigger === 'manual' ? 'Manual' : 'Scheduled'}
                        </span>
                      </div>
                      <span className="text-[10px]" style={{ color: t.text4 }}>
                        {timeAgo(log.created_at)}
                      </span>
                    </div>
                    <p className="text-[11px] truncate" style={{ color: t.text3 }}>
                      {log.input_summary || 'No summary'}
                    </p>
                    <div className="flex items-center gap-2 mt-1">
                      {log.cost_usd && (
                        <span className="text-[10px] font-mono" style={{ color: t.text4 }}>
                          ${log.cost_usd}
                        </span>
                      )}
                      {log.input_tokens && (
                        <span className="text-[10px] font-mono" style={{ color: t.text4 }}>
                          {fmtNum(log.input_tokens + (log.output_tokens || 0))}t
                        </span>
                      )}
                      {log.has_strategy && (
                        <ExternalLink className="w-2.5 h-2.5 ml-auto" style={{ color: t.text4 }} />
                      )}
                    </div>
                  </a>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
