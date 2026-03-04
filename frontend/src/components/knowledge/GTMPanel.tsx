import { useState, useEffect } from 'react';
import { Loader2, RefreshCw, Target, TrendingUp } from 'lucide-react';
import type { ThemeTokens } from '../../lib/themeColors';
import { contactsApi } from '../../api/contacts';
import type { AISDRProject } from '../../api/contacts';

interface Props {
  projectId: number;
  isDark: boolean;
  t: ThemeTokens;
}

interface GTMSegment {
  segment: string;
  size: number;
  characteristics?: string[];
  apollo_query?: string;
  priority?: number;
}

function parseGTMPlan(raw?: string): { segments: GTMSegment[]; rawText: string } {
  if (!raw) return { segments: [], rawText: '' };
  // Try parsing as JSON first
  try {
    const parsed = JSON.parse(raw);
    if (parsed.segments && Array.isArray(parsed.segments)) {
      return { segments: parsed.segments, rawText: '' };
    }
    if (Array.isArray(parsed)) {
      return { segments: parsed, rawText: '' };
    }
  } catch {
    // Not JSON — return as raw text
  }
  return { segments: [], rawText: raw };
}

export function GTMPanel({ projectId, isDark, t }: Props) {
  const [project, setProject] = useState<AISDRProject | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    loadProject();
  }, [projectId]);

  async function loadProject() {
    setLoading(true);
    try {
      const data = await contactsApi.getProjectAISDR(projectId);
      setProject(data);
    } catch (e) {
      console.error('Failed to load project GTM data:', e);
    } finally {
      setLoading(false);
    }
  }

  async function handleGenerate() {
    setGenerating(true);
    try {
      const result = await contactsApi.generateGTM(projectId);
      setProject(prev => prev ? { ...prev, gtm_plan: result.gtm_plan } : null);
    } catch (e) {
      console.error('Failed to generate GTM:', e);
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

  const { segments, rawText } = parseGTMPlan(project?.gtm_plan);
  const hasContent = segments.length > 0 || rawText;

  if (!hasContent) {
    return (
      <div className="flex flex-col items-center justify-center py-20 px-6">
        <Target className="w-12 h-12 mb-4 opacity-30" style={{ color: t.text4 }} />
        <p className="text-[14px] mb-1" style={{ color: t.text2 }}>No GTM strategy yet</p>
        <p className="text-[13px] mb-6" style={{ color: t.text4 }}>
          Click Generate to analyze qualified leads and create a go-to-market plan
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
            <><TrendingUp className="w-4 h-4" /> Generate GTM Strategy</>
          )}
        </button>
      </div>
    );
  }

  // Sort segments by priority (descending)
  const sortedSegments = [...segments].sort((a, b) => (b.priority ?? 0) - (a.priority ?? 0));

  return (
    <div className="p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-[14px] font-semibold" style={{ color: t.text1 }}>
          Go-To-Market Strategy
        </h3>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors"
          style={{
            background: isDark ? '#2d2d2d' : '#f0f0f0',
            color: t.text2,
          }}
        >
          {generating ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <RefreshCw className="w-3.5 h-3.5" />
          )}
          Regenerate
        </button>
      </div>

      {/* Segment cards */}
      {sortedSegments.length > 0 ? (
        <div className="grid gap-3">
          {sortedSegments.map((seg, i) => (
            <div
              key={i}
              className="rounded-xl p-4"
              style={{ background: t.cardBg, border: `1px solid ${t.cardBorder}` }}
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-[13px] font-semibold" style={{ color: t.text1 }}>
                  {seg.segment}
                </h4>
                <div className="flex items-center gap-2">
                  {seg.priority != null && (
                    <span
                      className="px-2 py-0.5 rounded text-[11px] font-medium"
                      style={{
                        background: isDark ? '#1e3a5f' : '#dbeafe',
                        color: isDark ? '#93c5fd' : '#1d4ed8',
                      }}
                    >
                      Priority {seg.priority}
                    </span>
                  )}
                  <span
                    className="px-2 py-0.5 rounded text-[11px] font-medium"
                    style={{
                      background: isDark ? '#1a2e1a' : '#dcfce7',
                      color: isDark ? '#86efac' : '#16a34a',
                    }}
                  >
                    {seg.size} leads
                  </span>
                </div>
              </div>

              {seg.characteristics && seg.characteristics.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {seg.characteristics.map((ch, j) => (
                    <span
                      key={j}
                      className="px-2 py-0.5 rounded text-[12px]"
                      style={{ background: isDark ? '#2d2d2d' : '#f0f0f0', color: t.text2 }}
                    >
                      {ch}
                    </span>
                  ))}
                </div>
              )}

              {seg.apollo_query && (
                <div className="mt-2">
                  <span className="text-[11px] font-medium uppercase tracking-wide" style={{ color: t.text4 }}>
                    Apollo Query
                  </span>
                  <p
                    className="text-[12px] mt-1 p-2 rounded-lg font-mono"
                    style={{ background: isDark ? '#1a1a1a' : '#f5f5f5', color: t.text3 }}
                  >
                    {seg.apollo_query}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      ) : rawText ? (
        <div
          className="rounded-xl p-4 whitespace-pre-wrap text-[13px]"
          style={{ background: t.cardBg, border: `1px solid ${t.cardBorder}`, color: t.text2 }}
        >
          {rawText}
        </div>
      ) : null}
    </div>
  );
}
