import { useState, useEffect } from 'react';
import { History, Loader2, ChevronDown, ChevronRight, MessageSquare, Zap, Clock } from 'lucide-react';
import { getLearningLogs, getLearningLogDetail } from '../../api/learning';
import type { LearningLogSummary, LearningLogDetail } from '../../api/learning';
import type { ThemeTokens } from '../../lib/themeColors';

interface Props {
  projectId: number;
  isDark: boolean;
  t: ThemeTokens;
  refreshKey?: number;
}

const TRIGGER_ICONS: Record<string, typeof Zap> = {
  manual: Zap,
  feedback: MessageSquare,
  scheduled: Clock,
};

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  completed: { bg: 'rgba(34, 197, 94, 0.15)', text: '#22c55e' },
  failed: { bg: 'rgba(239, 68, 68, 0.15)', text: '#ef4444' },
  processing: { bg: 'rgba(59, 130, 246, 0.15)', text: '#3b82f6' },
  insufficient_data: { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b' },
};

export function LearningLogsPanel({ projectId, isDark, t, refreshKey }: Props) {
  const [logs, setLogs] = useState<LearningLogSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<LearningLogDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    loadLogs();
  }, [projectId, page, refreshKey]);

  async function loadLogs() {
    setLoading(true);
    try {
      const result = await getLearningLogs(projectId, page);
      setLogs(result.items);
      setTotal(result.total);
    } catch (e) {
      console.error('Failed to load logs:', e);
    } finally {
      setLoading(false);
    }
  }

  async function toggleExpand(logId: number) {
    if (expandedId === logId) {
      setExpandedId(null);
      setDetail(null);
      return;
    }
    setExpandedId(logId);
    setDetailLoading(true);
    try {
      const d = await getLearningLogDetail(projectId, logId);
      setDetail(d);
    } catch (e) {
      console.error('Failed to load log detail:', e);
    } finally {
      setDetailLoading(false);
    }
  }

  if (loading && logs.length === 0) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-5 h-5 animate-spin" style={{ color: t.text4 }} />
      </div>
    );
  }

  if (logs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16" style={{ color: t.text4 }}>
        <History className="w-10 h-10 mb-3 opacity-40" />
        <p className="text-[14px] font-medium">No learning events yet</p>
        <p className="text-[12px] mt-1" style={{ color: t.text5 }}>
          Trigger a learning cycle from the Templates tab to see history here
        </p>
      </div>
    );
  }

  return (
    <div className="p-5 space-y-2">
      <div className="flex items-center gap-2 mb-3">
        <History className="w-4 h-4" style={{ color: t.text3 }} />
        <span className="text-[14px] font-medium" style={{ color: t.text1 }}>Learning History</span>
        <span className="text-[11px] px-1.5 py-0.5 rounded" style={{ color: t.text4, background: isDark ? '#2d2d2d' : '#f0f0f0' }}>
          {total} total
        </span>
      </div>

      {logs.map((log) => {
        const TriggerIcon = TRIGGER_ICONS[log.trigger] || Zap;
        const statusColor = STATUS_COLORS[log.status] || STATUS_COLORS.processing;
        const isExpanded = expandedId === log.id;

        return (
          <div
            key={log.id}
            className="rounded-lg border overflow-hidden"
            style={{ background: t.cardBg, borderColor: t.cardBorder }}
          >
            {/* Summary row */}
            <button
              onClick={() => toggleExpand(log.id)}
              className="w-full flex items-center gap-3 px-4 py-3 text-left hover:opacity-80 transition-opacity"
            >
              {isExpanded ? (
                <ChevronDown className="w-3.5 h-3.5 flex-shrink-0" style={{ color: t.text4 }} />
              ) : (
                <ChevronRight className="w-3.5 h-3.5 flex-shrink-0" style={{ color: t.text4 }} />
              )}
              <TriggerIcon className="w-3.5 h-3.5 flex-shrink-0" style={{ color: t.text3 }} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[13px] font-medium truncate" style={{ color: t.text1 }}>
                    {log.trigger === 'feedback' ? 'Feedback' : `Learning cycle`}
                  </span>
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                    style={{ background: statusColor.bg, color: statusColor.text }}
                  >
                    {log.status}
                  </span>
                </div>
                {log.change_summary && (
                  <div className="text-[11px] truncate mt-0.5" style={{ color: t.text4 }}>
                    {log.change_summary}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-3 text-[11px] flex-shrink-0" style={{ color: t.text5 }}>
                {log.conversations_analyzed != null && (
                  <span>{log.conversations_analyzed} convos</span>
                )}
                {log.created_at && (
                  <span>{new Date(log.created_at).toLocaleDateString()}</span>
                )}
              </div>
            </button>

            {/* Expanded detail */}
            {isExpanded && (
              <div className="border-t px-4 py-3" style={{ borderColor: t.divider }}>
                {detailLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="w-4 h-4 animate-spin" style={{ color: t.text4 }} />
                  </div>
                ) : detail ? (
                  <div className="space-y-3">
                    {/* Stats */}
                    <div className="flex flex-wrap gap-4 text-[12px]" style={{ color: t.text3 }}>
                      {detail.conversations_email != null && <span>Email: {detail.conversations_email}</span>}
                      {detail.conversations_linkedin != null && <span>LinkedIn: {detail.conversations_linkedin}</span>}
                      {detail.qualified_count != null && <span>Qualified: {detail.qualified_count}</span>}
                      {detail.tokens_used != null && <span>Tokens: {detail.tokens_used}</span>}
                      {detail.cost_usd != null && <span>${detail.cost_usd.toFixed(4)}</span>}
                    </div>

                    {/* Feedback text */}
                    {detail.feedback_text && (
                      <div>
                        <div className="text-[11px] font-medium uppercase mb-1" style={{ color: t.text4 }}>Feedback</div>
                        <div className="text-[12px] p-2 rounded" style={{ background: isDark ? '#1e1e1e' : '#f8f8f8', color: t.text2 }}>
                          {detail.feedback_text}
                        </div>
                      </div>
                    )}

                    {/* AI Reasoning */}
                    {detail.ai_reasoning && (
                      <div>
                        <div className="text-[11px] font-medium uppercase mb-1" style={{ color: t.text4 }}>AI Reasoning</div>
                        <div className="text-[12px] p-2 rounded whitespace-pre-wrap" style={{ background: isDark ? '#1e1e1e' : '#f8f8f8', color: t.text3 }}>
                          {detail.ai_reasoning}
                        </div>
                      </div>
                    )}

                    {/* Error */}
                    {detail.error_message && (
                      <div className="text-[12px] p-2 rounded" style={{ background: t.errorBg, color: t.errorText, border: `1px solid ${t.errorBorder}` }}>
                        {detail.error_message}
                      </div>
                    )}

                    {/* Before/After snapshots */}
                    {detail.before_snapshot && detail.after_snapshot && (
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <div className="text-[11px] font-medium uppercase mb-1" style={{ color: t.text4 }}>Before</div>
                          <pre className="text-[11px] p-2 rounded max-h-[200px] overflow-y-auto whitespace-pre-wrap" style={{ background: isDark ? '#1e1e1e' : '#f8f8f8', color: t.text4 }}>
                            {JSON.stringify(detail.before_snapshot, null, 2)}
                          </pre>
                        </div>
                        <div>
                          <div className="text-[11px] font-medium uppercase mb-1" style={{ color: t.text4 }}>After</div>
                          <pre className="text-[11px] p-2 rounded max-h-[200px] overflow-y-auto whitespace-pre-wrap" style={{ background: isDark ? '#1e1e1e' : '#f8f8f8', color: t.text3 }}>
                            {JSON.stringify(detail.after_snapshot, null, 2)}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            )}
          </div>
        );
      })}

      {/* Pagination */}
      {total > 20 && (
        <div className="flex items-center justify-center gap-3 pt-3">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1 rounded text-[12px]"
            style={{ background: t.btnGhostHover, color: page <= 1 ? t.text5 : t.text2 }}
          >
            Previous
          </button>
          <span className="text-[12px]" style={{ color: t.text4 }}>
            Page {page} of {Math.ceil(total / 20)}
          </span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={page >= Math.ceil(total / 20)}
            className="px-3 py-1 rounded text-[12px]"
            style={{ background: t.btnGhostHover, color: page >= Math.ceil(total / 20) ? t.text5 : t.text2 }}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
