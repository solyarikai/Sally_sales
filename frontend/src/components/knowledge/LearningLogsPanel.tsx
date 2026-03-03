import { useState, useEffect, useRef, useCallback } from 'react';
import { History, Loader2, ChevronDown, ChevronRight, MessageSquare, Zap, Clock, BarChart3, FileText, Eye } from 'lucide-react';
import { getLearningLogs, getLearningLogDetail, getLearningStatus } from '../../api/learning';
import type { LearningLogSummary, LearningLogDetail, TemplateChange, EditPattern } from '../../api/learning';
import type { ThemeTokens } from '../../lib/themeColors';
import { TextDiff } from '../TextDiff';

interface Props {
  projectId: number;
  isDark: boolean;
  t: ThemeTokens;
  refreshKey?: number;
  highlightLogId?: number;
}

const TRIGGER_ICONS: Record<string, typeof Zap> = {
  manual: Zap,
  feedback: MessageSquare,
  scheduled: Clock,
  auto_corrections: BarChart3,
};

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  completed: { bg: 'rgba(34, 197, 94, 0.15)', text: '#22c55e' },
  failed: { bg: 'rgba(239, 68, 68, 0.15)', text: '#ef4444' },
  processing: { bg: 'rgba(59, 130, 246, 0.15)', text: '#3b82f6' },
  insufficient_data: { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b' },
};

export function LearningLogsPanel({ projectId, isDark, t, refreshKey, highlightLogId }: Props) {
  const [logs, setLogs] = useState<LearningLogSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<LearningLogDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [pollingLogId, setPollingLogId] = useState<number | null>(null);
  const [showPrompt, setShowPrompt] = useState(false);
  const [showCorrections, setShowCorrections] = useState(false);
  const highlightRef = useRef<HTMLDivElement>(null);
  const didAutoExpand = useRef(false);

  useEffect(() => {
    loadLogs();
  }, [projectId, page, refreshKey]);

  useEffect(() => {
    if (!highlightLogId || didAutoExpand.current || loading || logs.length === 0) return;
    const found = logs.find(l => l.id === highlightLogId);
    if (found) {
      didAutoExpand.current = true;
      toggleExpand(found.id);
      if (found.status === 'processing') {
        setPollingLogId(found.id);
      }
      setTimeout(() => highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 200);
    }
  }, [highlightLogId, logs, loading]);

  useEffect(() => {
    if (!pollingLogId) return;
    const interval = setInterval(async () => {
      try {
        const status = await getLearningStatus(projectId, pollingLogId);
        if (status.status !== 'processing') {
          setPollingLogId(null);
          loadLogs();
          const d = await getLearningLogDetail(projectId, pollingLogId);
          setDetail(d);
        }
      } catch {
        // ignore
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [pollingLogId, projectId]);

  const loadLogs = useCallback(async () => {
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
  }, [projectId, page]);

  async function toggleExpand(logId: number) {
    if (expandedId === logId) {
      setExpandedId(null);
      setDetail(null);
      setShowPrompt(false);
      setShowCorrections(false);
      return;
    }
    setExpandedId(logId);
    setDetailLoading(true);
    setShowPrompt(false);
    setShowCorrections(false);
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

  const kpi = detail?.corrections_snapshot?.kpi;
  const templateChanges = detail?.after_snapshot?.template_changes || [];
  const editPatterns = detail?.after_snapshot?.edit_patterns || [];
  const correctionAnalysis = detail?.after_snapshot?.correction_analysis || [];
  const beforeTemplate = detail?.before_snapshot?.template || '';
  const afterTemplate = detail?.after_snapshot?.template || '';

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
        const isHighlighted = highlightLogId === log.id;
        const isPolling = pollingLogId === log.id;

        return (
          <div
            key={log.id}
            ref={isHighlighted ? highlightRef : undefined}
            className="rounded-lg border overflow-hidden transition-all duration-500"
            style={{
              background: t.cardBg,
              borderColor: isHighlighted ? '#3b82f6' : t.cardBorder,
              boxShadow: isHighlighted ? '0 0 0 1px rgba(59,130,246,0.3), 0 4px 12px rgba(59,130,246,0.1)' : undefined,
            }}
          >
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
                    {log.trigger === 'feedback' ? 'Feedback' : log.trigger === 'auto_corrections' ? 'Auto-learn (edited send)' : 'Learning cycle'}
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

            {isExpanded && (
              <div className="border-t px-4 py-3 space-y-3" style={{ borderColor: t.divider }}>
                {isPolling && (
                  <div
                    className="flex items-center gap-2 px-3 py-2 rounded-lg text-[12px]"
                    style={{ background: 'rgba(59,130,246,0.1)', color: '#3b82f6' }}
                  >
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Processing... This page will update automatically.
                  </div>
                )}
                {detailLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="w-4 h-4 animate-spin" style={{ color: t.text4 }} />
                  </div>
                ) : detail ? (
                  <>
                    {/* KPI Bar */}
                    {kpi && kpi.total_actions > 0 && (
                      <div
                        className="flex items-center gap-4 px-3 py-2.5 rounded-lg text-[12px]"
                        style={{ background: isDark ? '#1e1e1e' : '#f8f8f8' }}
                      >
                        <div className="flex items-center gap-1.5">
                          <span style={{ color: t.text4 }}>Edit rate:</span>
                          <span className="font-medium" style={{ color: kpi.edit_rate > 50 ? '#ef4444' : kpi.edit_rate > 20 ? '#f59e0b' : '#22c55e' }}>
                            {kpi.edit_rate}%
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span style={{ color: t.text4 }}>Approval rate:</span>
                          <span className="font-medium" style={{ color: kpi.approval_rate > 80 ? '#22c55e' : kpi.approval_rate > 50 ? '#f59e0b' : '#ef4444' }}>
                            {kpi.approval_rate}%
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span style={{ color: t.text4 }}>Sends:</span>
                          <span className="font-medium" style={{ color: t.text2 }}>{kpi.total_sends}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span style={{ color: t.text4 }}>Total actions:</span>
                          <span className="font-medium" style={{ color: t.text2 }}>{kpi.total_actions}</span>
                        </div>
                      </div>
                    )}

                    {/* Stats */}
                    <div className="flex flex-wrap gap-4 text-[12px]" style={{ color: t.text3 }}>
                      {detail.conversations_email != null && <span>Email: {detail.conversations_email}</span>}
                      {detail.conversations_linkedin != null && <span>LinkedIn: {detail.conversations_linkedin}</span>}
                      {detail.qualified_count != null && <span>Qualified: {detail.qualified_count}</span>}
                      {detail.tokens_used != null && <span>Tokens: {detail.tokens_used?.toLocaleString()}</span>}
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

                    {/* Template Diff */}
                    {beforeTemplate && afterTemplate && beforeTemplate !== afterTemplate && (
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <FileText className="w-3 h-3" style={{ color: t.text4 }} />
                          <span className="text-[11px] font-medium uppercase" style={{ color: t.text4 }}>Template Changes</span>
                        </div>
                        <TextDiff
                          oldText={beforeTemplate}
                          newText={afterTemplate}
                          isDark={isDark}
                          maxHeight="300px"
                        />
                      </div>
                    )}

                    {/* Why These Changes */}
                    {templateChanges.length > 0 && (
                      <div>
                        <div className="text-[11px] font-medium uppercase mb-1.5" style={{ color: t.text4 }}>Why These Changes</div>
                        <div className="space-y-2">
                          {templateChanges.map((tc: TemplateChange, i: number) => (
                            <div
                              key={i}
                              className="p-2.5 rounded-lg text-[12px]"
                              style={{ background: isDark ? '#1e1e1e' : '#f8f8f8' }}
                            >
                              <div className="font-medium" style={{ color: t.text2 }}>{tc.what}</div>
                              <div className="mt-0.5" style={{ color: t.text3 }}>Why: {tc.why}</div>
                              {tc.evidence && (
                                <div className="mt-0.5 italic" style={{ color: t.text5 }}>Evidence: {tc.evidence}</div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Edit Patterns */}
                    {editPatterns.length > 0 && (
                      <div>
                        <div className="text-[11px] font-medium uppercase mb-1.5" style={{ color: t.text4 }}>Edit Patterns</div>
                        <div className="space-y-1.5">
                          {editPatterns.map((ep: EditPattern, i: number) => (
                            <div
                              key={i}
                              className="flex items-start gap-3 p-2 rounded text-[12px]"
                              style={{ background: isDark ? '#1e1e1e' : '#f8f8f8' }}
                            >
                              <div className="flex-1" style={{ color: t.text2 }}>{ep.pattern}</div>
                              <span className="text-[10px] px-1.5 py-0.5 rounded shrink-0" style={{ background: isDark ? '#2d2d2d' : '#e5e5e5', color: t.text4 }}>
                                {ep.frequency}
                              </span>
                            </div>
                          ))}
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

                    {/* Corrections Used (collapsible) */}
                    {correctionAnalysis.length > 0 && (
                      <div>
                        <button
                          onClick={() => setShowCorrections(!showCorrections)}
                          className="flex items-center gap-1.5 text-[11px] font-medium uppercase hover:opacity-80"
                          style={{ color: t.text4 }}
                        >
                          {showCorrections ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                          Corrections Analysis ({correctionAnalysis.length})
                        </button>
                        {showCorrections && (
                          <div className="mt-1.5 space-y-1.5">
                            {correctionAnalysis.map((ca, i) => (
                              <div
                                key={i}
                                className="p-2 rounded text-[11px]"
                                style={{ background: isDark ? '#1e1e1e' : '#f8f8f8' }}
                              >
                                <div className="flex items-center gap-2">
                                  <span
                                    className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                                    style={{
                                      background: ca.action === 'EDITED' ? 'rgba(245,158,11,0.15)' :
                                        ca.action === 'APPROVED' ? 'rgba(34,197,94,0.15)' :
                                        'rgba(239,68,68,0.15)',
                                      color: ca.action === 'EDITED' ? '#f59e0b' :
                                        ca.action === 'APPROVED' ? '#22c55e' : '#ef4444',
                                    }}
                                  >
                                    {ca.action}
                                  </span>
                                  <span style={{ color: t.text3 }}>{ca.key_changes}</span>
                                </div>
                                {ca.learning_applied && (
                                  <div className="mt-0.5" style={{ color: t.text5 }}>Applied: {ca.learning_applied}</div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Full AI Prompt (collapsible) */}
                    {detail.corrections_snapshot?.prompt_sent && (
                      <div>
                        <button
                          onClick={() => setShowPrompt(!showPrompt)}
                          className="flex items-center gap-1.5 text-[11px] font-medium uppercase hover:opacity-80"
                          style={{ color: t.text4 }}
                        >
                          {showPrompt ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                          <Eye className="w-3 h-3" />
                          Full AI Prompt
                        </button>
                        {showPrompt && (
                          <pre
                            className="mt-1.5 text-[11px] p-3 rounded whitespace-pre-wrap max-h-[400px] overflow-y-auto"
                            style={{ background: isDark ? '#1e1e1e' : '#f8f8f8', color: t.text4 }}
                          >
                            {detail.corrections_snapshot.prompt_sent}
                          </pre>
                        )}
                      </div>
                    )}

                    {/* Error */}
                    {detail.error_message && (
                      <div className="text-[12px] p-2 rounded" style={{ background: t.errorBg, color: t.errorText, border: `1px solid ${t.errorBorder}` }}>
                        {detail.error_message}
                      </div>
                    )}

                    {/* Legacy: Before/After raw JSON for old logs */}
                    {!afterTemplate && detail.before_snapshot && detail.after_snapshot && (
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
                  </>
                ) : null}
              </div>
            )}
          </div>
        );
      })}

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
