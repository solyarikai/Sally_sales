import { useState, useEffect, useCallback } from 'react';
import { Shield, Check, AlertTriangle, Loader2, ChevronRight, Plus, Minus, Info, Clock } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { useAppStore } from '../store/appStore';
import { godPanelApi } from '../api/godPanel';
import type { GodPanelCampaign, ProjectRules, GodPanelStats, CampaignAuditLogEntry } from '../api/godPanel';

type Tab = 'campaigns' | 'rules' | 'analytics';

// ─── Resolution method badge ────────────────────────────────
function ResolutionBadge({ method, isDark }: { method?: string; isDark: boolean }) {
  if (!method) return <span className="text-[11px]" style={{ color: isDark ? '#6e6e6e' : '#999' }}>—</span>;

  const styles: Record<string, { bg: string; bgDark: string; text: string; textDark: string }> = {
    exact_match: { bg: '#dcfce7', bgDark: '#052e16', text: '#166534', textDark: '#4ade80' },
    prefix_match: { bg: '#dbeafe', bgDark: '#172554', text: '#1e40af', textDark: '#93c5fd' },
    sender_match: { bg: '#fef3c7', bgDark: '#422006', text: '#92400e', textDark: '#fcd34d' },
    db_fallback: { bg: '#e0e7ff', bgDark: '#1e1b4b', text: '#3730a3', textDark: '#a5b4fc' },
    manual: { bg: '#f3e8ff', bgDark: '#3b0764', text: '#6b21a8', textDark: '#c084fc' },
    auto_discovery: { bg: '#cffafe', bgDark: '#083344', text: '#155e75', textDark: '#67e8f9' },
    seed: { bg: '#e0e7ff', bgDark: '#1e1b4b', text: '#3730a3', textDark: '#a5b4fc' },
    rule_feedback: { bg: '#dbeafe', bgDark: '#172554', text: '#1e40af', textDark: '#93c5fd' },
    unresolved: { bg: '#fee2e2', bgDark: '#450a0a', text: '#991b1b', textDark: '#fca5a5' },
  };

  const s = styles[method] || styles.unresolved;
  return (
    <span
      className="px-1.5 py-0.5 rounded text-[11px] font-medium"
      style={{ backgroundColor: isDark ? s.bgDark : s.bg, color: isDark ? s.textDark : s.text }}
    >
      {method.replace('_', ' ')}
    </span>
  );
}

// ─── Platform badge ─────────────────────────────────────────
function PlatformBadge({ platform, isDark }: { platform: string; isDark: boolean }) {
  const isGetSales = platform === 'getsales';
  return (
    <span
      className="px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wide"
      style={{
        backgroundColor: isDark
          ? (isGetSales ? '#172554' : '#1e1b4b')
          : (isGetSales ? '#dbeafe' : '#e0e7ff'),
        color: isDark
          ? (isGetSales ? '#93c5fd' : '#a5b4fc')
          : (isGetSales ? '#1e40af' : '#3730a3'),
      }}
    >
      {platform === 'getsales' ? 'LinkedIn' : 'Email'}
    </span>
  );
}

// ─── Stat card ──────────────────────────────────────────────
function StatCard({ label, value, sub, t }: {
  label: string; value: string | number; sub?: string; t: ReturnType<typeof themeColors>;
}) {
  return (
    <div
      className="rounded-lg p-4 border"
      style={{ backgroundColor: t.cardBg, borderColor: t.cardBorder }}
    >
      <div className="text-[11px] font-medium uppercase tracking-wide mb-1" style={{ color: t.text4 }}>{label}</div>
      <div className="text-2xl font-semibold" style={{ color: t.text1 }}>{value}</div>
      {sub && <div className="text-[11px] mt-0.5" style={{ color: t.text5 }}>{sub}</div>}
    </div>
  );
}

// ─── Assign dialog ──────────────────────────────────────────
function AssignDialog({ campaign, projects, isDark, t, onAssign, onClose }: {
  campaign: GodPanelCampaign;
  projects: { id: number; name: string }[];
  isDark: boolean;
  t: ReturnType<typeof themeColors>;
  onAssign: (campaignId: number, projectId: number) => void;
  onClose: () => void;
}) {
  const [search, setSearch] = useState('');
  const filtered = projects.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/40" />
      <div
        className="relative w-[380px] rounded-lg border shadow-xl p-4"
        style={{ backgroundColor: t.cardBg, borderColor: t.cardBorder }}
        onClick={e => e.stopPropagation()}
      >
        <div className="text-[13px] font-medium mb-1" style={{ color: t.text1 }}>
          Assign campaign to project
        </div>
        <div className="text-[12px] mb-3" style={{ color: t.text4 }}>
          {campaign.name}
        </div>
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search projects..."
          autoFocus
          className="w-full px-2.5 py-1.5 rounded text-[12px] mb-2 border-none focus:outline-none"
          style={{ backgroundColor: t.inputBg, color: t.text1 }}
        />
        <div className="max-h-60 overflow-y-auto space-y-0.5">
          {filtered.map(p => (
            <button
              key={p.id}
              onClick={() => onAssign(campaign.id, p.id)}
              className="w-full text-left px-2.5 py-1.5 rounded text-[12px] transition-colors"
              style={{ color: t.text2 }}
              onMouseEnter={e => (e.currentTarget.style.backgroundColor = isDark ? '#2d2d2d' : '#f0f0f0')}
              onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              {p.name}
            </button>
          ))}
          {filtered.length === 0 && (
            <div className="px-2.5 py-2 text-[11px]" style={{ color: t.text5 }}>No projects found</div>
          )}
        </div>
        <button
          onClick={onClose}
          className="mt-3 w-full py-1.5 rounded text-[12px] font-medium transition-colors"
          style={{ backgroundColor: isDark ? '#2d2d2d' : '#e8e8e8', color: t.text2 }}
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

// ─── Campaigns tab ──────────────────────────────────────────
function CampaignsTab({ isDark, t }: { isDark: boolean; t: ReturnType<typeof themeColors> }) {
  const [campaigns, setCampaigns] = useState<GodPanelCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'unresolved' | 'getsales' | 'smartlead'>('all');
  const [assignTarget, setAssignTarget] = useState<GodPanelCampaign | null>(null);
  const { projects } = useAppStore();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (filter === 'unresolved') params.unresolved = true;
      if (filter === 'getsales') params.platform = 'getsales';
      if (filter === 'smartlead') params.platform = 'smartlead';
      const data = await godPanelApi.listCampaigns(params);
      setCampaigns(data);
    } catch (e) {
      console.error('Failed to load campaigns', e);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const handleAssign = async (campaignId: number, projectId: number) => {
    try {
      await godPanelApi.assignCampaign(campaignId, projectId);
      setAssignTarget(null);
      load();
    } catch (e) {
      console.error('Failed to assign', e);
    }
  };

  const handleAcknowledge = async (id: number) => {
    try {
      await godPanelApi.acknowledgeCampaign(id);
      setCampaigns(prev => prev.map(c => c.id === id ? { ...c, acknowledged: true } : c));
    } catch (e) {
      console.error('Failed to acknowledge', e);
    }
  };

  const unresolved = campaigns.filter(c => !c.project_id);

  return (
    <div>
      {/* Unresolved banner */}
      {unresolved.length > 0 && (
        <div
          className="rounded-lg px-4 py-2.5 mb-4 flex items-center gap-2"
          style={{ backgroundColor: isDark ? '#450a0a' : '#fee2e2', borderColor: isDark ? '#5a3030' : '#fca5a5' }}
        >
          <AlertTriangle className="w-4 h-4 flex-shrink-0" style={{ color: isDark ? '#fca5a5' : '#991b1b' }} />
          <span className="text-[13px] font-medium" style={{ color: isDark ? '#fca5a5' : '#991b1b' }}>
            {unresolved.length} unresolved campaign{unresolved.length > 1 ? 's' : ''} — replies may be missing project routing
          </span>
        </div>
      )}

      {/* Filter chips */}
      <div className="flex gap-1.5 mb-4">
        {(['all', 'unresolved', 'getsales', 'smartlead'] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className="px-2.5 py-1 rounded text-[12px] font-medium transition-colors"
            style={{
              backgroundColor: filter === f ? (isDark ? '#37373d' : '#e8e8e8') : 'transparent',
              color: filter === f ? t.text1 : t.text4,
            }}
          >
            {f === 'all' ? 'All' : f === 'unresolved' ? `Unresolved (${unresolved.length})` : f === 'getsales' ? 'LinkedIn' : 'Email'}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin" style={{ color: t.text4 }} /></div>
      ) : campaigns.length === 0 ? (
        <div className="text-center py-12 text-[13px]" style={{ color: t.text4 }}>No campaigns found</div>
      ) : (
        <div className="rounded-lg border overflow-hidden" style={{ borderColor: t.cardBorder }}>
          {/* Header */}
          <div
            className="grid grid-cols-[1fr_80px_140px_120px_100px_70px_50px] gap-2 px-3 py-2 text-[11px] font-medium uppercase tracking-wide border-b"
            style={{ backgroundColor: isDark ? '#1e1e1e' : '#f8f8f8', borderColor: t.cardBorder, color: t.text5 }}
          >
            <span>Campaign</span>
            <span>Platform</span>
            <span>Project</span>
            <span>Resolution</span>
            <span>First seen</span>
            <span>Replies</span>
            <span></span>
          </div>
          {/* Rows */}
          {campaigns.map(c => (
            <div
              key={c.id}
              className="grid grid-cols-[1fr_80px_140px_120px_100px_70px_50px] gap-2 px-3 py-2 border-b items-center"
              style={{ borderColor: t.cardBorder, backgroundColor: !c.project_id ? (isDark ? '#2a1515' : '#fff5f5') : t.cardBg }}
            >
              <div className="min-w-0">
                <div className="text-[13px] truncate" style={{ color: t.text1 }}>{c.name}</div>
                {c.external_id && (
                  <div className="text-[10px] truncate" style={{ color: t.text5 }}>{c.external_id}</div>
                )}
              </div>
              <PlatformBadge platform={c.platform} isDark={isDark} />
              <div className="text-[12px] truncate" style={{ color: c.project_name ? t.text2 : (isDark ? '#fca5a5' : '#991b1b') }}>
                {c.project_name || (
                  <button
                    onClick={() => setAssignTarget(c)}
                    className="underline decoration-dotted"
                    style={{ color: isDark ? '#fca5a5' : '#991b1b' }}
                  >
                    assign
                  </button>
                )}
              </div>
              <ResolutionBadge method={c.resolution_method} isDark={isDark} />
              <div className="text-[11px]" style={{ color: t.text4 }}>
                {c.first_seen_at ? new Date(c.first_seen_at).toLocaleDateString() : '—'}
              </div>
              <div className="text-[12px] tabular-nums" style={{ color: t.text3 }}>{c.replied_count}</div>
              <div>
                {!c.acknowledged && (
                  <button
                    onClick={() => handleAcknowledge(c.id)}
                    className="p-1 rounded transition-colors"
                    style={{ color: t.text4 }}
                    onMouseEnter={e => (e.currentTarget.style.color = isDark ? '#4ade80' : '#16a34a')}
                    onMouseLeave={e => (e.currentTarget.style.color = t.text4)}
                    title="Mark as reviewed"
                  >
                    <Check className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {assignTarget && (
        <AssignDialog
          campaign={assignTarget}
          projects={projects}
          isDark={isDark}
          t={t}
          onAssign={handleAssign}
          onClose={() => setAssignTarget(null)}
        />
      )}
    </div>
  );
}

// ─── Rules tab ──────────────────────────────────────────────
function RulesTab({ isDark, t }: { isDark: boolean; t: ReturnType<typeof themeColors> }) {
  const { projects } = useAppStore();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [rules, setRules] = useState<ProjectRules | null>(null);
  const [logs, setLogs] = useState<CampaignAuditLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAllLogs, setShowAllLogs] = useState(false);

  const loadRules = useCallback(async (id: number) => {
    setLoading(true);
    setShowAllLogs(false);
    try {
      const [data, logData] = await Promise.all([
        godPanelApi.getProjectRules(id),
        godPanelApi.getCampaignLogs(id),
      ]);
      setRules(data);
      setLogs(logData);
    } catch (e) {
      console.error('Failed to load rules', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) loadRules(selectedId);
  }, [selectedId, loadRules]);

  const sourceBadge = (source: string) => {
    const styles: Record<string, { bg: string; text: string }> = {
      auto_discovery: { bg: isDark ? '#052e16' : '#dcfce7', text: isDark ? '#4ade80' : '#166534' },
      manual: { bg: isDark ? '#3b0764' : '#f3e8ff', text: isDark ? '#c084fc' : '#6b21a8' },
      ai_feedback: { bg: isDark ? '#172554' : '#dbeafe', text: isDark ? '#93c5fd' : '#1e40af' },
    };
    const s = styles[source] || { bg: isDark ? '#333' : '#f5f5f5', text: isDark ? '#858585' : '#666' };
    return (
      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded" style={{ backgroundColor: s.bg, color: s.text }}>
        {source === 'auto_discovery' ? 'Auto' : source === 'ai_feedback' ? 'AI' : source === 'manual' ? 'Manual' : source}
      </span>
    );
  };

  const displayLogs = showAllLogs ? logs : logs.slice(0, 8);

  return (
    <div className="flex gap-4 min-h-[400px]">
      {/* Project sidebar */}
      <div
        className="w-52 rounded-lg border overflow-hidden flex-shrink-0"
        style={{ borderColor: t.cardBorder, backgroundColor: t.cardBg }}
      >
        <div className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide border-b"
          style={{ color: t.text5, borderColor: t.cardBorder }}
        >
          Projects
        </div>
        <div className="max-h-[500px] overflow-y-auto">
          {projects.map(p => (
            <button
              key={p.id}
              onClick={() => setSelectedId(p.id)}
              className="w-full px-3 py-1.5 text-left text-[13px] flex items-center justify-between transition-colors"
              style={{
                backgroundColor: selectedId === p.id ? (isDark ? '#37373d' : '#e8e8e8') : 'transparent',
                color: selectedId === p.id ? t.text1 : t.text3,
              }}
            >
              <span className="truncate">{p.name}</span>
              {selectedId === p.id && <ChevronRight className="w-3 h-3 flex-shrink-0" />}
            </button>
          ))}
        </div>
      </div>

      {/* Rules panel */}
      <div className="flex-1 rounded-lg border p-4" style={{ borderColor: t.cardBorder, backgroundColor: t.cardBg }}>
        {!selectedId ? (
          <div className="text-[13px] py-12 text-center" style={{ color: t.text4 }}>Select a project to view assignment rules</div>
        ) : loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin" style={{ color: t.text4 }} /></div>
        ) : rules ? (
          <div className="space-y-6">
            {/* Rules section */}
            <div>
              <div className="text-[15px] font-medium mb-4" style={{ color: t.text1 }}>{rules.project_name}</div>
              <div className="space-y-2">
                {rules.rules.map((rule, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <div className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ backgroundColor: t.text4 }} />
                    <div className="text-[13px]" style={{ color: t.text2 }}>{rule}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Assignment History section */}
            {logs.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <Clock className="w-3.5 h-3.5" style={{ color: t.text4 }} />
                  <span className="text-[13px] font-medium" style={{ color: t.text3 }}>
                    Assignment History
                  </span>
                  <span className="text-[11px] px-1.5 py-0.5 rounded" style={{ backgroundColor: isDark ? '#333' : '#f0f0f0', color: t.text5 }}>
                    {logs.length}
                  </span>
                </div>
                <div className="space-y-1">
                  {displayLogs.map(log => (
                    <div key={log.id} className="flex items-center gap-2 px-2.5 py-1.5 rounded text-[12px]"
                      style={{ backgroundColor: isDark ? '#1e1e1e' : '#f9f9f9' }}
                    >
                      {log.action === 'add' ? (
                        <Plus className="w-3 h-3 flex-shrink-0" style={{ color: '#22c55e' }} />
                      ) : log.action === 'remove' ? (
                        <Minus className="w-3 h-3 flex-shrink-0" style={{ color: '#ef4444' }} />
                      ) : (
                        <Info className="w-3 h-3 flex-shrink-0" style={{ color: t.text4 }} />
                      )}
                      <span className="truncate flex-1" style={{ color: t.text2 }}>{log.campaign_name || '(no campaign)'}</span>
                      {sourceBadge(log.source)}
                      <span className="text-[11px] flex-shrink-0" style={{ color: t.text5 }}>
                        {log.created_at ? new Date(log.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : ''}
                      </span>
                    </div>
                  ))}
                </div>
                {logs.length > 8 && (
                  <button
                    onClick={() => setShowAllLogs(prev => !prev)}
                    className="text-[12px] mt-2 px-2"
                    style={{ color: isDark ? '#6e9eff' : '#3b82f6' }}
                  >
                    {showAllLogs ? 'Show less' : `Show all ${logs.length} entries`}
                  </button>
                )}
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

// ─── Analytics tab ──────────────────────────────────────────
function AnalyticsTab({ t }: { isDark?: boolean; t: ReturnType<typeof themeColors> }) {
  const [stats, setStats] = useState<GodPanelStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    godPanelApi.getStats().then(setStats).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex justify-center py-12"><Loader2 className="w-5 h-5 animate-spin" style={{ color: t.text4 }} /></div>;
  if (!stats) return null;

  return (
    <div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard label="Total campaigns" value={stats.total_campaigns} t={t} />
        <StatCard label="Email campaigns" value={stats.smartlead_campaigns} sub="SmartLead" t={t} />
        <StatCard label="LinkedIn campaigns" value={stats.getsales_campaigns} sub="GetSales" t={t} />
        <StatCard
          label="Assignment rate"
          value={`${stats.assignment_rate}%`}
          sub={`${stats.unresolved_count} unresolved`}
          t={t}
        />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Replies (7d)" value={stats.reply_volume_7d} t={t} />
        <StatCard label="Replies (30d)" value={stats.reply_volume_30d} t={t} />
        <StatCard label="Unacknowledged" value={stats.unacknowledged_count} t={t} />
        <StatCard
          label="Newest campaign"
          value={stats.newest_campaign || '—'}
          sub={stats.newest_campaign_at ? new Date(stats.newest_campaign_at).toLocaleDateString() : undefined}
          t={t}
        />
      </div>
    </div>
  );
}

// ─── Main page ──────────────────────────────────────────────
export function GodPanelPage() {
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const [tab, setTab] = useState<Tab>('campaigns');

  const tabs: { key: Tab; label: string }[] = [
    { key: 'campaigns', label: 'Campaigns' },
    { key: 'rules', label: 'Rules' },
    { key: 'analytics', label: 'Analytics' },
  ];

  return (
    <div className="h-full overflow-auto" style={{ backgroundColor: t.pageBg }}>
      <div className="max-w-6xl mx-auto px-6 py-5">
        {/* Header */}
        <div className="flex items-center gap-2.5 mb-5">
          <Shield className="w-5 h-5" style={{ color: t.text3 }} />
          <h1 className="text-[17px] font-semibold" style={{ color: t.text1 }}>God Panel</h1>
        </div>

        {/* Tab bar */}
        <div className="flex gap-1 mb-5 border-b" style={{ borderColor: t.cardBorder }}>
          {tabs.map(tb => (
            <button
              key={tb.key}
              onClick={() => setTab(tb.key)}
              className="px-3 py-1.5 text-[13px] font-medium transition-colors border-b-2 -mb-px"
              style={{
                borderColor: tab === tb.key ? t.text1 : 'transparent',
                color: tab === tb.key ? t.text1 : t.text4,
              }}
            >
              {tb.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {tab === 'campaigns' && <CampaignsTab isDark={isDark} t={t} />}
        {tab === 'rules' && <RulesTab isDark={isDark} t={t} />}
        {tab === 'analytics' && <AnalyticsTab isDark={isDark} t={t} />}
      </div>
    </div>
  );
}
