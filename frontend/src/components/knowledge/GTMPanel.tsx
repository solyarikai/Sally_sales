import { useState, useEffect, useCallback } from 'react';
import { Loader2, Target, TrendingUp, Sparkles, AlertTriangle, ArrowRight, Calendar, Zap, Languages } from 'lucide-react';
import type { ThemeTokens } from '../../lib/themeColors';
import { contactsApi } from '../../api/contacts';
import type { GTMData } from '../../api/contacts';

interface Props {
  projectId: number;
  isDark: boolean;
  t: ThemeTokens;
  logId?: number;
}

/* eslint-disable @typescript-eslint/no-explicit-any */

/** Replace literal \\n sequences with real newlines */
function cleanText(s: string): string {
  return s.replace(/\\n/g, '\n').replace(/\\t/g, '\t');
}

/** Detect if text is likely Spanish */
function isSpanish(s: string): boolean {
  if (!s || s.length < 10) return false;
  const markers = /[¿¡ñáéíóú]|(\b(hola|gracias|interés|reunión|semana|podemos|cómo|también|estamos|tenemos|quería|favor|buenos días|clientes|empresa|propuesta|interesados|resultado)\b)/i;
  return markers.test(s);
}

/** Lightweight translation cache — avoids re-translating same text */
const translationCache = new Map<string, string>();

/** Inline translated text component — shows Spanish original + English translation */
function TranslatableText({ text, isDark, t, showTranslation, className, style }: {
  text: string;
  isDark: boolean;
  t: ThemeTokens;
  showTranslation: boolean;
  className?: string;
  style?: React.CSSProperties;
}) {
  const [translation, setTranslation] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const cleaned = cleanText(text);
  const needsTranslation = showTranslation && isSpanish(cleaned);

  useEffect(() => {
    if (!needsTranslation) { setTranslation(null); return; }
    const cached = translationCache.get(cleaned);
    if (cached) { setTranslation(cached); return; }

    let cancelled = false;
    setLoading(true);
    translateText(cleaned).then(result => {
      if (!cancelled && result) {
        translationCache.set(cleaned, result);
        setTranslation(result);
      }
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [cleaned, needsTranslation]);

  return (
    <span>
      <span className={className} style={{ ...style, whiteSpace: 'pre-line' }}>{cleaned}</span>
      {needsTranslation && translation && (
        <span className="block mt-0.5 text-[10px] italic" style={{ color: isDark ? '#93c5fd' : '#6366f1', whiteSpace: 'pre-line' }}>
          EN: {translation}
        </span>
      )}
      {needsTranslation && loading && (
        <span className="inline-flex items-center gap-1 ml-1 text-[9px]" style={{ color: t.text4 }}>
          <Loader2 className="w-2.5 h-2.5 animate-spin" />
        </span>
      )}
    </span>
  );
}

/** Translate via backend — uses the project's knowledge chat as a lightweight translator */
async function translateText(text: string): Promise<string | null> {
  try {
    const resp = await fetch('/api/contacts/translate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Company-ID': '1' },
      body: JSON.stringify({ text, target_lang: 'en' }),
    });
    if (!resp.ok) return fallbackTranslate(text);
    const data = await resp.json();
    return data.translated || null;
  } catch {
    return fallbackTranslate(text);
  }
}

/** Fallback: basic word-level translation for common Spanish sales phrases */
function fallbackTranslate(text: string): string | null {
  const dict: Record<string, string> = {
    'hola': 'hello', 'gracias': 'thank you', 'por tu interés': 'for your interest',
    'reunión': 'meeting', 'agendar': 'schedule', 'semana': 'week',
    'no estamos interesados': "we're not interested", 'no nos interesa': "we're not interested",
    'me interesa': "I'm interested", 'cuéntame': 'tell me', 'cómo funciona': 'how it works',
    'podemos': 'we can', 'clientes': 'clients', 'nuevos': 'new',
    'por favor': 'please', 'propuesta': 'proposal', 'empresa': 'company',
    'resultado': 'result', 'influencers': 'influencers', 'precio fijo': 'fixed price',
    'costo por acción': 'cost per action', 'pago por resultado': 'pay per result',
    'ya no trabajo': "I no longer work", 'disculpa': 'sorry', 'buenos días': 'good morning',
    'quería': 'I wanted', 'también': 'also', '¿cuánto': 'how much',
    'esta dirección de correo electrónico': 'this email address',
    'ya no está habilitada': 'is no longer active',
    'envíame la propuesta': 'send me the proposal',
    'agendé la reunión': 'I scheduled the meeting',
    'te parece': 'what do you think', 'nos juntamos': "let's meet",
    'un gusto saludarte': 'nice to greet you', 'me puedes agendar': 'can you schedule me',
    'estoy disponible': "I'm available", 'no puedo': "I can't",
    'no usamos ni nos interesan los influencer': "we don't use and aren't interested in influencers",
    'honestamente me perdiste con el primer mensaje': 'honestly you lost me with the first message',
    'tirarle siglas': 'throw acronyms', '¿qué es un modelo cpa': 'what is a CPA model',
    'de dónde nace esta conversación': 'where does this conversation come from',
    'de dnd nace esta conversacion': 'where does this conversation come from',
    'le informamos que': 'we inform you that',
  };
  let result = text;
  let changed = false;
  for (const [es, en] of Object.entries(dict)) {
    const regex = new RegExp(es.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    if (regex.test(result)) { changed = true; }
    result = result.replace(regex, en);
  }
  return changed ? result : null;
}

function parseStrategy(raw?: string | null): any | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (parsed.segments && Array.isArray(parsed.segments)) return parsed;
    if (Array.isArray(parsed)) return { segments: parsed };
  } catch { /* not JSON */ }
  return null;
}

const VERDICT_COLORS: Record<string, { bg: string; bgDark: string; text: string; textDark: string }> = {
  'SCALE UP': { bg: '#dcfce7', bgDark: '#0a2e1a', text: '#16a34a', textDark: '#4ade80' },
  'MAINTAIN': { bg: '#dbeafe', bgDark: '#1e3a5f', text: '#2563eb', textDark: '#93c5fd' },
  'PIVOT':    { bg: '#fef3c7', bgDark: '#422006', text: '#d97706', textDark: '#fbbf24' },
  'PAUSE':    { bg: '#fed7aa', bgDark: '#431407', text: '#ea580c', textDark: '#fb923c' },
  'DROP':     { bg: '#fecaca', bgDark: '#450a0a', text: '#dc2626', textDark: '#f87171' },
};

const SEVERITY_COLORS: Record<string, { bg: string; bgDark: string; text: string; textDark: string }> = {
  'CRITICAL': { bg: '#fecaca', bgDark: '#450a0a', text: '#dc2626', textDark: '#f87171' },
  'HIGH':     { bg: '#fed7aa', bgDark: '#431407', text: '#ea580c', textDark: '#fb923c' },
  'MEDIUM':   { bg: '#fef3c7', bgDark: '#422006', text: '#d97706', textDark: '#fbbf24' },
  'LOW':      { bg: '#e0e7ff', bgDark: '#1e1b4b', text: '#4f46e5', textDark: '#a5b4fc' },
};

export function GTMPanel({ projectId, isDark, t, logId }: Props) {
  const [data, setData] = useState<GTMData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logStrategy, setLogStrategy] = useState<string | null>(null);
  const [logMeta, setLogMeta] = useState<{ trigger: string; cost: string; tokens: string; model?: string } | null>(null);
  const [showTranslations, setShowTranslations] = useState(false);
  const toggleTranslations = useCallback(() => setShowTranslations(p => !p), []);

  useEffect(() => { loadData(); }, [projectId]);

  useEffect(() => {
    if (logId) {
      loadLogStrategy(logId);
    } else {
      setLogStrategy(null);
      setLogMeta(null);
    }
  }, [logId, projectId]);

  async function loadLogStrategy(id: number) {
    try {
      const res = await contactsApi.getGTMStrategyLogDetail(projectId, id);
      setLogStrategy(res.strategy_json);
      setLogMeta({
        trigger: res.trigger,
        cost: res.cost_usd || '?',
        tokens: `${(((res.input_tokens || 0) + (res.output_tokens || 0)) / 1000).toFixed(1)}k`,
      });
    } catch { /* fallback */ }
  }

  async function loadData() {
    setLoading(true); setError(null);
    try { setData(await contactsApi.getGTMData(projectId)); }
    catch (e: any) { setError(e?.response?.data?.detail || 'Failed to load'); }
    finally { setLoading(false); }
  }

  async function handleGenerate() {
    setGenerating(true);
    try {
      const result = await contactsApi.generateGTM(projectId);
      if (result.gtm_plan) setData(prev => prev ? { ...prev, gtm_plan: result.gtm_plan! } : null);
      else await loadData();
    } catch (e: any) { setError(e?.response?.data?.detail || 'Generation failed'); }
    finally { setGenerating(false); }
  }

  if (loading) return <div className="flex items-center justify-center py-20"><Loader2 className="w-5 h-5 animate-spin" style={{ color: t.text4 }} /></div>;
  if (error && !data) return <div className="flex flex-col items-center justify-center py-20 px-6"><p className="text-[13px] mb-4" style={{ color: '#ef4444' }}>{error}</p><button onClick={loadData} className="text-[13px] underline" style={{ color: t.text3 }}>Retry</button></div>;
  if (!data) return null;

  const plan = parseStrategy(logStrategy || data.gtm_plan);

  function verdictBadge(verdict: string) {
    const v = VERDICT_COLORS[verdict] || VERDICT_COLORS['MAINTAIN'];
    return (
      <span className="px-2 py-0.5 rounded-md text-[11px] font-bold uppercase tracking-wide"
        style={{ background: isDark ? v.bgDark : v.bg, color: isDark ? v.textDark : v.text }}>
        {verdict}
      </span>
    );
  }

  function severityBadge(severity: string) {
    const s = SEVERITY_COLORS[severity] || SEVERITY_COLORS['MEDIUM'];
    return (
      <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase"
        style={{ background: isDark ? s.bgDark : s.bg, color: isDark ? s.textDark : s.text }}>
        {severity}
      </span>
    );
  }

  function metricPill(label: string, value: string | number, highlight?: boolean) {
    return (
      <div className="text-center px-2 py-1 rounded" style={{ background: isDark ? '#1a1a1a' : '#f5f5f5' }}>
        <div className="text-[11px] font-mono font-bold" style={{ color: highlight ? (isDark ? '#4ade80' : '#16a34a') : t.text1 }}>{value}</div>
        <div className="text-[9px] uppercase tracking-wider" style={{ color: t.text4 }}>{label}</div>
      </div>
    );
  }

  return (
    <div className="p-5 space-y-6 max-w-[1000px]">
      {/* Log banner */}
      {logMeta && logStrategy && (
        <div className="rounded-lg px-4 py-2.5" style={{ background: isDark ? '#1a2332' : '#eff6ff', border: `1px solid ${isDark ? '#1e3a5f' : '#bfdbfe'}` }}>
          <span className="text-[12px] font-medium" style={{ color: isDark ? '#93c5fd' : '#1d4ed8' }}>
            Viewing {logMeta.trigger} analysis · Opus 4.6 · ${logMeta.cost} · {logMeta.tokens} tokens
          </span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-[15px] font-semibold" style={{ color: t.text1 }}>Go-To-Market Strategy</h3>
          <p className="text-[12px] mt-0.5" style={{ color: t.text4 }}>{data.total_contacts.toLocaleString()} contacts across campaigns</p>
        </div>
        <div className="flex items-center gap-2">
          {plan && (
            <button onClick={toggleTranslations}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors cursor-pointer"
              style={{
                background: showTranslations ? (isDark ? '#1e3a5f' : '#dbeafe') : (isDark ? '#2d2d2d' : '#f0f0f0'),
                color: showTranslations ? (isDark ? '#93c5fd' : '#1d4ed8') : t.text3,
              }}>
              <Languages className="w-3.5 h-3.5" />
              {showTranslations ? 'EN On' : 'Translate'}
            </button>
          )}
          <button onClick={handleGenerate} disabled={generating}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-colors cursor-pointer"
            style={{ background: isDark ? '#2d2d2d' : '#f0f0f0', color: t.text2 }}>
            {generating ? <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Generating (Opus 4.6)...</> : <><Sparkles className="w-3.5 h-3.5" /> {plan ? 'Regenerate' : 'Generate'} Strategy</>}
          </button>
        </div>
      </div>

      {error && <div className="rounded-lg px-3 py-2 text-[12px]" style={{ background: isDark ? '#3b1c1c' : '#fef2f2', color: '#ef4444' }}>{error}</div>}

      {plan ? (
        <>
          {/* Executive Summary */}
          {plan.executive_summary && (
            <div className="rounded-xl p-4" style={{ background: isDark ? '#1a2332' : '#f0f4ff', border: `1px solid ${isDark ? '#1e3a5f' : '#c7d2fe'}` }}>
              <h4 className="text-[11px] font-bold uppercase tracking-wider mb-2" style={{ color: isDark ? '#93c5fd' : '#4f46e5' }}>Executive Summary</h4>
              {typeof plan.executive_summary === 'string' ? (
                <p className="text-[13px] leading-relaxed" style={{ color: t.text1 }}>{plan.executive_summary}</p>
              ) : (
                <div className="space-y-2">
                  {plan.executive_summary.key_insight && (
                    <p className="text-[13px] leading-relaxed" style={{ color: t.text1 }}>{plan.executive_summary.key_insight}</p>
                  )}
                  <div className="flex flex-wrap gap-2 mt-2">
                    {plan.executive_summary.total_replies != null && metricPill('Replies', plan.executive_summary.total_replies)}
                    {plan.executive_summary.total_meetings != null && metricPill('Meetings', plan.executive_summary.total_meetings, true)}
                    {plan.executive_summary.conversion_rate && metricPill('Conv Rate', plan.executive_summary.conversion_rate, true)}
                  </div>
                  {plan.executive_summary.biggest_problem && (
                    <div className="rounded-lg p-2.5 mt-1" style={{ background: isDark ? '#450a0a' : '#fef2f2' }}>
                      <div className="text-[10px] font-bold uppercase mb-1" style={{ color: isDark ? '#f87171' : '#dc2626' }}>Biggest Problem</div>
                      <p className="text-[12px]" style={{ color: t.text2 }}>{plan.executive_summary.biggest_problem}</p>
                    </div>
                  )}
                  {plan.executive_summary.immediate_action && (
                    <div className="rounded-lg p-2.5" style={{ background: isDark ? '#0a2e1a' : '#f0fdf4' }}>
                      <div className="text-[10px] font-bold uppercase mb-1" style={{ color: isDark ? '#4ade80' : '#16a34a' }}>Immediate Action</div>
                      <p className="text-[12px]" style={{ color: t.text2 }}>{plan.executive_summary.immediate_action}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* KPI Targets */}
          {plan.kpi_targets && (
            <div className="rounded-xl p-4" style={{ background: isDark ? '#111' : '#f9fafb', border: `1px solid ${t.cardBorder}` }}>
              <h4 className="text-[11px] font-bold uppercase tracking-wider mb-3" style={{ color: t.text3 }}>
                <TrendingUp className="w-3.5 h-3.5 inline mr-1.5" />KPI Targets
              </h4>
              <div className="grid grid-cols-5 gap-2">
                {['week_1', 'week_2', 'week_3', 'week_4', 'thirty_day_total'].map((wk) => {
                  const d = plan.kpi_targets[wk];
                  if (!d) return null;
                  const isTotal = wk === 'thirty_day_total';
                  return (
                    <div key={wk} className="rounded-lg p-2.5 text-center" style={{ background: isTotal ? (isDark ? '#0a2e1a' : '#dcfce7') : (isDark ? '#1a1a1a' : '#f5f5f5') }}>
                      <div className="text-[10px] font-bold uppercase" style={{ color: isTotal ? (isDark ? '#4ade80' : '#16a34a') : t.text4 }}>
                        {isTotal ? '30-Day Total' : wk.replace('_', ' ')}
                      </div>
                      <div className="text-[16px] font-bold mt-0.5" style={{ color: isTotal ? (isDark ? '#4ade80' : '#16a34a') : t.text1 }}>
                        {d.meetings_booked ?? d.meetings ?? '—'}
                      </div>
                      <div className="text-[10px]" style={{ color: t.text4 }}>meetings</div>
                      {d.focus && <p className="text-[9px] mt-1 leading-tight" style={{ color: t.text3 }}>{d.focus}</p>}
                      {d.expected_deals && <p className="text-[10px] mt-1" style={{ color: t.text3 }}>{d.expected_deals} deals</p>}
                      {d.revenue_target && <p className="text-[10px] font-medium" style={{ color: isDark ? '#4ade80' : '#16a34a' }}>{d.revenue_target}</p>}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Segment Cards */}
          <div className="space-y-4">
            {plan.segments?.map((seg: any, i: number) => {
              const segName = seg.segment || seg.name;
              const confidence = seg.confidence || seg.metrics?.confidence;
              return (
              <div key={i} className="rounded-xl overflow-hidden" style={{ background: t.cardBg, border: `1px solid ${t.cardBorder}` }}>
                {/* Segment header */}
                <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: `1px solid ${t.cardBorder}` }}>
                  <div className="flex items-center gap-2.5">
                    <span className="w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-bold"
                      style={{ background: isDark ? '#1e3a5f' : '#dbeafe', color: isDark ? '#93c5fd' : '#1d4ed8' }}>
                      {seg.priority ?? i + 1}
                    </span>
                    <h5 className="text-[14px] font-semibold" style={{ color: t.text1 }}>{segName}</h5>
                    {seg.verdict && verdictBadge(seg.verdict)}
                    {confidence && <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: isDark ? '#1a1a1a' : '#f0f0f0', color: t.text4 }}>{confidence}</span>}
                  </div>
                </div>

                <div className="px-4 py-3 space-y-3">
                  {/* Metrics row — flexible: works with both full and minimal metric shapes */}
                  {seg.metrics && (
                    <div className="flex flex-wrap gap-2">
                      {seg.metrics.contacts != null && metricPill('Contacts', seg.metrics.contacts?.toLocaleString())}
                      {(seg.metrics.replies ?? seg.metrics.total_replies) != null && metricPill('Replies', seg.metrics.replies ?? seg.metrics.total_replies)}
                      {seg.metrics.meetings != null && metricPill('Meetings', seg.metrics.meetings, true)}
                      {seg.metrics.positive != null && metricPill('Positive', seg.metrics.positive, true)}
                      {seg.metrics.conversion_rate && metricPill('Conv Rate', seg.metrics.conversion_rate, true)}
                      {seg.metrics.reply_rate_pct != null && metricPill('Reply %', `${seg.metrics.reply_rate_pct}%`)}
                      {seg.metrics.meeting_rate_pct != null && metricPill('Meeting %', `${seg.metrics.meeting_rate_pct}%`, seg.metrics.meeting_rate_pct > 10)}
                      {seg.metrics.wrong_person_pct > 0 && metricPill('Wrong %', `${seg.metrics.wrong_person_pct}%`)}
                    </div>
                  )}

                  {/* Diagnosis */}
                  {seg.diagnosis && (
                    <p className="text-[12px] leading-relaxed" style={{ color: t.text2 }}>{seg.diagnosis}</p>
                  )}

                  {/* Winning/Losing patterns */}
                  {(seg.winning_patterns?.length > 0 || seg.losing_patterns?.length > 0) && (
                    <div className="grid grid-cols-2 gap-2">
                      {seg.winning_patterns?.length > 0 && (
                        <div className="rounded-lg p-2.5" style={{ background: isDark ? '#0a2e1a' : '#f0fdf4' }}>
                          <div className="text-[10px] font-bold uppercase mb-1" style={{ color: isDark ? '#4ade80' : '#16a34a' }}>Winning Patterns</div>
                          {seg.winning_patterns.slice(0, 3).map((p: string, pi: number) => (
                            <div key={pi} className="mb-1">
                              <TranslatableText text={`"${String(p).slice(0, 200)}"`} isDark={isDark} t={t} showTranslation={showTranslations}
                                className="text-[11px] italic leading-relaxed" style={{ color: t.text3 }} />
                            </div>
                          ))}
                        </div>
                      )}
                      {seg.losing_patterns?.length > 0 && (
                        <div className="rounded-lg p-2.5" style={{ background: isDark ? '#450a0a' : '#fef2f2' }}>
                          <div className="text-[10px] font-bold uppercase mb-1" style={{ color: isDark ? '#f87171' : '#dc2626' }}>Losing Patterns</div>
                          {seg.losing_patterns.slice(0, 3).map((p: string, pi: number) => (
                            <div key={pi} className="mb-1">
                              <TranslatableText text={`"${String(p).slice(0, 200)}"`} isDark={isDark} t={t} showTranslation={showTranslations}
                                className="text-[11px] italic leading-relaxed" style={{ color: t.text3 }} />
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {/* This Week Actions — handles both string[] and object[] */}
                  {seg.this_week_actions?.length > 0 && (
                    <div>
                      <div className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: t.text4 }}>This Week Actions</div>
                      <div className="space-y-1.5">
                        {seg.this_week_actions.map((a: any, j: number) => (
                          <div key={j} className="rounded-lg p-2.5" style={{ background: isDark ? '#1a1a1a' : '#fafafa' }}>
                            {typeof a === 'string' ? (
                              <div className="flex items-start gap-2">
                                <Zap className="w-3 h-3 shrink-0 mt-0.5" style={{ color: isDark ? '#fbbf24' : '#d97706' }} />
                                <p className="text-[11px]" style={{ color: t.text2 }}>{a}</p>
                              </div>
                            ) : (
                              <>
                                <div className="flex items-center gap-1.5 mb-1">
                                  <span className="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase"
                                    style={{ background: isDark ? '#422006' : '#fef3c7', color: isDark ? '#fbbf24' : '#d97706' }}>
                                    {a.action}
                                  </span>
                                  <span className="text-[11px] font-medium" style={{ color: t.text1 }}>{a.what}</span>
                                </div>
                                {a.from && a.to && (
                                  <div className="flex items-start gap-1.5 text-[11px]" style={{ color: t.text3 }}>
                                    <span className="line-through opacity-60" style={{ whiteSpace: 'pre-line' }}>{cleanText(a.from?.slice(0, 120))}</span>
                                    <ArrowRight className="w-3 h-3 shrink-0 mt-0.5" style={{ color: isDark ? '#4ade80' : '#16a34a' }} />
                                    <TranslatableText text={a.to?.slice(0, 150)} isDark={isDark} t={t} showTranslation={showTranslations}
                                      className="font-medium" style={{ color: isDark ? '#4ade80' : '#16a34a' }} />
                                  </div>
                                )}
                                {a.why && <p className="text-[10px] mt-1 italic" style={{ color: t.text4 }}>{a.why}</p>}
                              </>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Targeting Fix — handles both string and object */}
                  {seg.targeting_fix && (
                    <div className="rounded-lg p-2.5" style={{ background: isDark ? '#1e1b4b' : '#eef2ff', border: `1px solid ${isDark ? '#312e81' : '#c7d2fe'}` }}>
                      <div className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: isDark ? '#a5b4fc' : '#4f46e5' }}>
                        <Target className="w-3 h-3 inline mr-1" />Targeting Fix
                      </div>
                      {typeof seg.targeting_fix === 'string' ? (
                        <p className="text-[11px]" style={{ color: t.text2 }}>{seg.targeting_fix}</p>
                      ) : (
                        <>
                          {seg.targeting_fix.current_problem && <p className="text-[11px] mb-1" style={{ color: t.text2 }}>{seg.targeting_fix.current_problem}</p>}
                          {seg.targeting_fix.target_titles && (
                            <div className="flex flex-wrap gap-1 mt-1">
                              <span className="text-[10px]" style={{ color: t.text4 }}>Target:</span>
                              {seg.targeting_fix.target_titles.map((tt: string) => (
                                <span key={tt} className="px-1.5 py-0.5 rounded text-[10px]" style={{ background: isDark ? '#0a2e1a' : '#dcfce7', color: isDark ? '#4ade80' : '#16a34a' }}>{tt}</span>
                              ))}
                            </div>
                          )}
                          {seg.targeting_fix.avoid_titles && (
                            <div className="flex flex-wrap gap-1 mt-1">
                              <span className="text-[10px]" style={{ color: t.text4 }}>Avoid:</span>
                              {seg.targeting_fix.avoid_titles.map((at: string) => (
                                <span key={at} className="px-1.5 py-0.5 rounded text-[10px]" style={{ background: isDark ? '#450a0a' : '#fecaca', color: isDark ? '#f87171' : '#dc2626' }}>{at}</span>
                              ))}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}

                  {/* Email Template */}
                  {seg.email_template && (
                    <div className="rounded-lg p-2.5" style={{ background: isDark ? '#1a1a1a' : '#f9fafb', border: `1px solid ${t.cardBorder}` }}>
                      <div className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: t.text4 }}>Email Template</div>
                      {seg.email_template.subject && (
                        <div className="mb-1">
                          <TranslatableText text={`Subject: ${seg.email_template.subject}`} isDark={isDark} t={t} showTranslation={showTranslations}
                            className="text-[11px] font-medium" style={{ color: t.text1 }} />
                        </div>
                      )}
                      {seg.email_template.opening && (
                        <div className="mb-1">
                          <TranslatableText text={seg.email_template.opening} isDark={isDark} t={t} showTranslation={showTranslations}
                            className="text-[11px]" style={{ color: t.text2 }} />
                        </div>
                      )}
                      {seg.email_template.cta && (
                        <div>
                          <TranslatableText text={seg.email_template.cta} isDark={isDark} t={t} showTranslation={showTranslations}
                            className="text-[11px] font-medium italic" style={{ color: isDark ? '#93c5fd' : '#2563eb' }} />
                        </div>
                      )}
                    </div>
                  )}

                  {/* Channel + Volume */}
                  {(seg.channel_recommendation || seg.monthly_volume_target) && (
                    <div className="flex items-center gap-3 text-[11px]" style={{ color: t.text3 }}>
                      {seg.channel_recommendation && <span>Channel: <strong>{seg.channel_recommendation}</strong></span>}
                      {seg.monthly_volume_target && <span>Volume: <strong>{seg.monthly_volume_target}/mo</strong></span>}
                    </div>
                  )}
                </div>
              </div>
              );
            })}
          </div>

          {/* Critical Bottlenecks */}
          {plan.critical_bottlenecks?.length > 0 && (
            <section>
              <h4 className="text-[12px] font-bold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: t.text3 }}>
                <AlertTriangle className="w-4 h-4" /> Critical Bottlenecks
              </h4>
              <div className="space-y-2">
                {plan.critical_bottlenecks.map((b: any, i: number) => (
                  <div key={i} className="rounded-lg p-3" style={{ background: isDark ? '#1a1a1a' : '#fafafa', border: `1px solid ${t.cardBorder}` }}>
                    {b.severity && <div className="mb-1">{severityBadge(b.severity)}</div>}
                    <p className="text-[12px] font-medium" style={{ color: t.text1 }}>{b.issue || b.bottleneck}</p>
                    {b.impact && (
                      <div className="mt-0.5">
                        <TranslatableText text={b.impact} isDark={isDark} t={t} showTranslation={showTranslations}
                          className="text-[11px]" style={{ color: t.text3 }} />
                      </div>
                    )}
                    {b.fix && (
                      <div className="flex items-start gap-1.5 mt-1">
                        <ArrowRight className="w-3 h-3 shrink-0 mt-0.5" style={{ color: isDark ? '#4ade80' : '#16a34a' }} />
                        <p className="text-[11px] font-medium" style={{ color: isDark ? '#4ade80' : '#16a34a' }}>{cleanText(b.fix)}</p>
                      </div>
                    )}
                    {b.evidence && (
                      <div className="mt-1">
                        <TranslatableText text={`"${b.evidence?.slice(0, 150)}"`} isDark={isDark} t={t} showTranslation={showTranslations}
                          className="text-[10px] italic truncate" style={{ color: t.text4 }} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Messaging Rules */}
          {plan.messaging_rules?.length > 0 && (
            <section>
              <h4 className="text-[12px] font-bold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: t.text3 }}>
                <Zap className="w-4 h-4" /> Messaging Rules
              </h4>
              <div className="space-y-2">
                {plan.messaging_rules.map((r: any, i: number) => (
                  <div key={i} className="rounded-lg px-3 py-2.5" style={{ background: isDark ? '#1a1a1a' : '#fafafa', border: `1px solid ${t.cardBorder}` }}>
                    <p className="text-[12px] font-medium" style={{ color: t.text1 }}>{cleanText(r.rule)}</p>
                    {r.why && (
                      <div className="mt-1">
                        <TranslatableText text={r.why} isDark={isDark} t={t} showTranslation={showTranslations}
                          className="text-[11px] italic" style={{ color: t.text3 }} />
                      </div>
                    )}
                    {r.instead && (
                      <div className="flex items-start gap-1.5 mt-1">
                        <ArrowRight className="w-3 h-3 shrink-0 mt-0.5" style={{ color: isDark ? '#4ade80' : '#16a34a' }} />
                        <TranslatableText text={r.instead} isDark={isDark} t={t} showTranslation={showTranslations}
                          className="text-[11px] font-medium" style={{ color: isDark ? '#4ade80' : '#16a34a' }} />
                      </div>
                    )}
                    {r.description && <p className="text-[11px] mt-0.5" style={{ color: t.text2 }}>{r.description}</p>}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* 30-Day Plan — handles both dict {week_1,...} and array formats */}
          {plan.thirty_day_plan && (
            <section>
              <h4 className="text-[12px] font-bold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: t.text3 }}>
                <Calendar className="w-4 h-4" /> 30-Day Plan
              </h4>
              <div className="grid grid-cols-4 gap-2">
                {(Array.isArray(plan.thirty_day_plan) ? plan.thirty_day_plan : ['week_1', 'week_2', 'week_3', 'week_4'].map(k => ({ _key: k, ...plan.thirty_day_plan[k] }))).map((w: any, i: number) => (
                  <div key={i} className="rounded-lg p-3" style={{ background: isDark ? '#1a1a1a' : '#fafafa', border: `1px solid ${t.cardBorder}` }}>
                    <div className="text-[11px] font-bold mb-1.5" style={{ color: t.text1 }}>
                      {w._key ? w._key.replace('_', ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()) : `Week ${w.week ?? i + 1}`}
                    </div>
                    {w.focus && <p className="text-[10px] font-medium mb-1" style={{ color: isDark ? '#93c5fd' : '#2563eb' }}>{w.focus}</p>}
                    {w.priority && <span className="px-1 py-0.5 rounded text-[9px] font-bold mb-1 inline-block" style={{ background: isDark ? '#1e3a5f' : '#dbeafe', color: isDark ? '#93c5fd' : '#2563eb' }}>{w.priority}</span>}
                    {w.actions && (Array.isArray(w.actions) ? w.actions : []).map((a: any, j: number) => (
                      <div key={j} className="flex items-start gap-1.5 mb-1">
                        <span className="text-[10px] mt-0.5" style={{ color: t.text4 }}>•</span>
                        <p className="text-[10px]" style={{ color: t.text2 }}>{typeof a === 'string' ? a : a.task?.slice(0, 100)}</p>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* New Segments to Test */}
          {plan.new_segments_to_test?.length > 0 && (
            <section>
              <h4 className="text-[12px] font-bold uppercase tracking-wider mb-3 flex items-center gap-2" style={{ color: t.text3 }}>
                <Target className="w-4 h-4" /> New Segments to Test
              </h4>
              <div className="grid grid-cols-3 gap-2">
                {plan.new_segments_to_test.map((s: any, i: number) => (
                  <div key={i} className="rounded-lg p-3" style={{ background: isDark ? '#1a1a1a' : '#fafafa', border: `1px solid ${t.cardBorder}` }}>
                    <p className="text-[12px] font-semibold mb-1" style={{ color: t.text1 }}>{s.segment}</p>
                    <p className="text-[10px] mb-1" style={{ color: t.text3 }}>{(s.rationale || s.why)?.slice(0, 150)}</p>
                    {(s.week_1_goal || s.initial_volume) && (
                      <p className="text-[10px] font-mono" style={{ color: isDark ? '#93c5fd' : '#2563eb' }}>{s.week_1_goal || `${s.initial_volume} leads`}</p>
                    )}
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      ) : (
        <div className="flex flex-col items-center justify-center py-12 px-6">
          <Sparkles className="w-10 h-10 mb-3 opacity-30" style={{ color: t.text4 }} />
          <p className="text-[13px] mb-1" style={{ color: t.text2 }}>No AI strategy generated yet</p>
          <p className="text-[12px] mb-4" style={{ color: t.text4 }}>Click Generate to create a strategy with Opus 4.6</p>
          <button onClick={handleGenerate} disabled={generating}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-medium text-white transition-colors"
            style={{ background: t.btnPrimaryBg }}>
            {generating ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</> : <><Sparkles className="w-4 h-4" /> Generate GTM Strategy</>}
          </button>
        </div>
      )}
    </div>
  );
}
