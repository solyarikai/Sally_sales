import { useState, useEffect, useRef } from 'react';
import { FileText, Play, Loader2, AlertTriangle, CheckCircle } from 'lucide-react';
import type { TemplatesResponse, AnalyzeStatusResponse } from '../../api/learning';
import { getLearningTemplates, triggerLearning, getLearningStatus } from '../../api/learning';
import type { ThemeTokens } from '../../lib/themeColors';
import { useToast } from '../Toast';

interface Props {
  projectId: number;
  isDark: boolean;
  t: ThemeTokens;
  onLearningComplete?: () => void;
}

export function TemplatesPanel({ projectId, isDark, t, onLearningComplete }: Props) {
  const [data, setData] = useState<TemplatesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [learningLogId, setLearningLogId] = useState<number | null>(null);
  const [learningStatus, setLearningStatus] = useState<AnalyzeStatusResponse | null>(null);
  const [maxConvos, setMaxConvos] = useState(100);
  const pollRef = useRef<number | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    loadTemplates();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [projectId]);

  async function loadTemplates() {
    setLoading(true);
    try {
      const result = await getLearningTemplates(projectId);
      setData(result);
    } catch (e) {
      console.error('Failed to load templates:', e);
    } finally {
      setLoading(false);
    }
  }

  async function handleLearn(forceAll = false) {
    try {
      const result = await triggerLearning(projectId, maxConvos, forceAll);
      setLearningLogId(result.learning_log_id);
      setLearningStatus({ id: result.learning_log_id, status: 'processing', change_summary: null, conversations_analyzed: null, error_message: null });
      startPolling(result.learning_log_id);
    } catch (e) {
      toast('Failed to start learning', 'error');
    }
  }

  function startPolling(logId: number) {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = window.setInterval(async () => {
      try {
        const status = await getLearningStatus(projectId, logId);
        setLearningStatus(status);
        if (status.status !== 'processing') {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          if (status.status === 'completed') {
            toast('Learning cycle completed', 'success');
            loadTemplates();
            onLearningComplete?.();
          } else if (status.status === 'failed') {
            toast(status.error_message || 'Learning failed', 'error');
          }
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }, 3000);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-5 h-5 animate-spin" style={{ color: t.text4 }} />
      </div>
    );
  }

  const activeTemplate = data?.templates.find(tmpl => tmpl.id === data?.active_template_id);
  const isLearning = learningStatus?.status === 'processing';

  return (
    <div className="p-5 space-y-5">
      {/* Learn controls */}
      <div
        className="rounded-lg border p-4"
        style={{ background: t.cardBg, borderColor: t.cardBorder }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Play className="w-4 h-4" style={{ color: t.text3 }} />
          <span className="text-[14px] font-medium" style={{ color: t.text1 }}>Learn from Conversations</span>
        </div>
        <p className="text-[12px] mb-3" style={{ color: t.text4 }}>
          Analyze real conversations and operator corrections to improve the reply template and ICP targeting.
        </p>
        <div className="flex items-center gap-3">
          <select
            value={maxConvos}
            onChange={(e) => setMaxConvos(Number(e.target.value))}
            disabled={isLearning}
            className="px-2 py-1.5 rounded text-[13px] border-none focus:outline-none"
            style={{ background: t.inputBg, color: t.text1 }}
          >
            <option value={100}>100 conversations</option>
            <option value={200}>200 conversations</option>
            <option value={300}>300 conversations</option>
          </select>
          <button
            onClick={() => handleLearn(false)}
            disabled={isLearning}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[13px] font-medium transition-colors"
            style={{
              background: isLearning ? t.badgeBg : t.btnPrimaryBg,
              color: isLearning ? t.text4 : t.btnPrimaryText,
              cursor: isLearning ? 'not-allowed' : 'pointer',
            }}
          >
            {isLearning ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Learning...
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" />
                Start Learning
              </>
            )}
          </button>
        </div>

        {/* Insufficient data warning */}
        {learningStatus?.status === 'insufficient_data' && (
          <div
            className="mt-3 flex items-start gap-2 p-3 rounded text-[12px]"
            style={{ background: isDark ? '#3a3020' : '#fef9c3', color: t.warnText }}
          >
            <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <div>
              <p>{learningStatus.change_summary}</p>
              <button
                onClick={() => handleLearn(true)}
                className="mt-2 underline font-medium"
              >
                Process all conversations anyway
              </button>
            </div>
          </div>
        )}

        {/* Completed status */}
        {learningStatus?.status === 'completed' && (
          <div
            className="mt-3 flex items-center gap-2 p-3 rounded text-[12px]"
            style={{ background: isDark ? '#203020' : '#f0fdf4', color: isDark ? '#86efac' : '#16a34a' }}
          >
            <CheckCircle className="w-4 h-4" />
            <span>{learningStatus.change_summary}</span>
          </div>
        )}
      </div>

      {/* Active template */}
      {activeTemplate ? (
        <div
          className="rounded-lg border p-4"
          style={{ background: t.cardBg, borderColor: t.cardBorder }}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4" style={{ color: t.text3 }} />
              <span className="text-[14px] font-medium" style={{ color: t.text1 }}>Active Template</span>
            </div>
            <div className="flex items-center gap-2 text-[11px]" style={{ color: t.text4 }}>
              <span>v{activeTemplate.version}</span>
              <span className="w-px h-3" style={{ background: t.divider }} />
              <span>{activeTemplate.usage_count} uses</span>
              {activeTemplate.last_used_at && (
                <>
                  <span className="w-px h-3" style={{ background: t.divider }} />
                  <span>Last: {new Date(activeTemplate.last_used_at).toLocaleDateString()}</span>
                </>
              )}
            </div>
          </div>
          <div className="text-[13px] font-medium mb-2" style={{ color: t.text2 }}>{activeTemplate.name}</div>
          <pre
            className="text-[12px] whitespace-pre-wrap rounded p-3 max-h-[400px] overflow-y-auto"
            style={{ background: isDark ? '#1e1e1e' : '#f8f8f8', color: t.text3, border: `1px solid ${t.divider}` }}
          >
            {activeTemplate.prompt_text}
          </pre>
        </div>
      ) : (
        <div
          className="rounded-lg border p-4 flex flex-col items-center justify-center py-10"
          style={{ background: t.cardBg, borderColor: t.cardBorder, color: t.text4 }}
        >
          <FileText className="w-8 h-8 mb-2 opacity-40" />
          <p className="text-[13px]">No template assigned to this project</p>
          <p className="text-[11px] mt-1" style={{ color: t.text5 }}>
            Run a learning cycle to auto-generate one
          </p>
        </div>
      )}

      {/* Category breakdown */}
      {data?.category_stats && Object.keys(data.category_stats).length > 0 && (
        <div
          className="rounded-lg border p-4"
          style={{ background: t.cardBg, borderColor: t.cardBorder }}
        >
          <div className="text-[13px] font-medium mb-2" style={{ color: t.text2 }}>
            Correction Categories
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(data.category_stats).map(([cat, count]) => (
              <span
                key={cat}
                className="inline-flex items-center gap-1.5 px-2 py-1 rounded text-[12px]"
                style={{ background: isDark ? '#2d2d2d' : '#f0f0f0', color: t.text2 }}
              >
                <span className="font-medium">{cat}</span>
                <span style={{ color: t.text4 }}>{count}</span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
