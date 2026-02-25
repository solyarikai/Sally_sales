import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Pencil, Check, X, Search, Trash2,
  MessageCircle, Loader2, Unlink, FolderOpen, Zap, FileSpreadsheet, RefreshCw,
  Activity, Radio, Clock, AlertTriangle, CheckCircle2, XCircle,
} from 'lucide-react';
import { contactsApi, type Project, type SheetSyncConfig, type ProjectMonitoring } from '../api/contacts';
import { useTheme } from '../hooks/useTheme';
import { useAppStore } from '../store/appStore';
import { cn } from '../lib/utils';

interface CampaignOption {
  name: string;
  source: string;
}

export function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const projectId = Number(id);
  const { isDark } = useTheme();
  const { setCurrentProject } = useAppStore();

  const [project, setProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [allCampaigns, setAllCampaigns] = useState<CampaignOption[]>([]);

  // Edit name
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState('');
  const [savingName, setSavingName] = useState(false);

  // Campaign picker
  const [campaignSearch, setCampaignSearch] = useState('');
  const [showCampaignDropdown, setShowCampaignDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Webhook toggle
  const [togglingWebhooks, setTogglingWebhooks] = useState(false);

  // Delete
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // Monitoring
  const [monitoring, setMonitoring] = useState<ProjectMonitoring | null>(null);
  const [monitoringLoading, setMonitoringLoading] = useState(false);

  const loadMonitoring = useCallback(async () => {
    if (!projectId) return;
    setMonitoringLoading(true);
    try {
      const data = await contactsApi.getProjectMonitoring(projectId);
      setMonitoring(data);
    } catch { /* silently fail */ }
    setMonitoringLoading(false);
  }, [projectId]);

  const loadProject = useCallback(async () => {
    if (!projectId) return;
    try {
      const data = await contactsApi.getProject(projectId);
      setProject(data);
      setNameValue(data.name);
    } catch {
      navigate('/projects');
    } finally {
      setIsLoading(false);
    }
  }, [projectId, navigate]);

  const loadCampaigns = useCallback(async () => {
    try {
      const resp = await fetch('/api/contacts/campaigns');
      const data = await resp.json();
      setAllCampaigns(data.campaigns || []);
    } catch {}
  }, []);

  useEffect(() => {
    loadProject();
    loadCampaigns();
    loadMonitoring();
  }, [loadProject, loadCampaigns, loadMonitoring]);

  // Sync loaded project to the global store (project selector in header)
  useEffect(() => {
    if (project) {
      setCurrentProject(project as any);
    }
  }, [project, setCurrentProject]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowCampaignDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSaveName = async () => {
    if (!project || !nameValue.trim()) return;
    setSavingName(true);
    try {
      const updated = await contactsApi.updateProject(project.id, { name: nameValue.trim() });
      setProject(updated);
      setEditingName(false);
    } catch {}
    setSavingName(false);
  };

  const handleAddCampaign = async (name: string) => {
    if (!project) return;
    const filters = [...(project.campaign_filters || []), name];
    try {
      const updated = await contactsApi.updateProject(project.id, { campaign_filters: filters });
      setProject(updated);
      setCampaignSearch('');
    } catch {}
  };

  const handleRemoveCampaign = async (name: string) => {
    if (!project) return;
    const filters = (project.campaign_filters || []).filter(c => c !== name);
    try {
      const updated = await contactsApi.updateProject(project.id, { campaign_filters: filters });
      setProject(updated);
    } catch {}
  };

  const handleDelete = async () => {
    if (!project) return;
    try {
      await contactsApi.deleteProject(project.id);
      navigate('/projects');
    } catch {}
  };

  const handleToggleWebhooks = async () => {
    if (!project) return;
    setTogglingWebhooks(true);
    try {
      const updated = await contactsApi.updateProject(project.id, {
        webhooks_enabled: !project.webhooks_enabled,
      });
      setProject(updated);
    } catch {}
    setTogglingWebhooks(false);
  };

  const getSource = (campaignName: string): string => {
    const match = allCampaigns.find(c => c.name === campaignName);
    if (match) return match.source;
    // Campaign not in contacts yet — if no SmartLead campaign has this name, assume GetSales
    const inSmartlead = allCampaigns.some(c => c.source === 'smartlead' && c.name === campaignName);
    return inSmartlead ? 'smartlead' : 'getsales';
  };

  const filteredCampaigns = allCampaigns
    .filter(c => c.name.toLowerCase().includes(campaignSearch.toLowerCase()))
    .filter(c => !(project?.campaign_filters || []).includes(c.name))
    .slice(0, 30);

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className={cn("text-center py-20", isDark ? "text-[#858585]" : "text-neutral-400")} data-testid="project-loading">Loading project...</div>
      </div>
    );
  }

  if (!project) return null;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Back + Header */}
      <div>
        <Link
          to="/projects"
          className={cn("inline-flex items-center gap-1.5 text-sm mb-4 transition-colors", isDark ? "text-[#858585] hover:text-[#d4d4d4]" : "text-neutral-500 hover:text-neutral-900")}
        >
          <ArrowLeft className="w-4 h-4" />
          All Projects
        </Link>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center", isDark ? "bg-violet-900/30" : "bg-violet-50")}>
              <FolderOpen className={cn("w-5 h-5", isDark ? "text-violet-400" : "text-violet-600")} />
            </div>
            {editingName ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={nameValue}
                  onChange={e => setNameValue(e.target.value)}
                  autoFocus
                  onKeyDown={e => { if (e.key === 'Enter') handleSaveName(); if (e.key === 'Escape') setEditingName(false); }}
                  className={cn(
                    "text-2xl font-bold px-2 py-1 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500/20",
                    isDark ? "bg-[#3c3c3c] border border-[#505050] text-[#d4d4d4]" : "border border-neutral-300 text-neutral-900"
                  )}
                />
                <button onClick={handleSaveName} disabled={savingName} className="p-1 text-green-600 hover:text-green-700">
                  <Check className="w-5 h-5" />
                </button>
                <button onClick={() => { setEditingName(false); setNameValue(project.name); }} className={cn("p-1", isDark ? "text-[#6e6e6e] hover:text-[#b0b0b0]" : "text-neutral-400 hover:text-neutral-600")}>
                  <X className="w-5 h-5" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h1 className={cn("text-2xl font-bold", isDark ? "text-[#d4d4d4]" : "text-neutral-900")} data-testid="project-name">{project.name}</h1>
                <button onClick={() => setEditingName(true)} className={cn("p-1 transition-colors", isDark ? "text-[#6e6e6e] hover:text-[#d4d4d4]" : "text-neutral-400 hover:text-neutral-700")}>
                  <Pencil className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>

          {showDeleteConfirm ? (
            <div className="flex items-center gap-2">
              <button onClick={handleDelete} className="px-3 py-1.5 bg-red-500 text-white rounded-lg text-sm font-medium">
                Confirm Delete
              </button>
              <button onClick={() => setShowDeleteConfirm(false)} className={cn("px-3 py-1.5 text-sm", isDark ? "text-[#858585]" : "text-neutral-500")}>
                Cancel
              </button>
            </div>
          ) : (
            <button onClick={() => setShowDeleteConfirm(true)} className={cn("p-2 transition-colors", isDark ? "text-[#6e6e6e] hover:text-red-400" : "text-neutral-400 hover:text-red-500")} title="Delete project">
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Campaigns Section */}
      <div className={cn("rounded-xl p-5 border", isDark ? "bg-[#252526] border-[#333]" : "bg-white border-neutral-200")} data-testid="campaigns-section">
        <div className="flex items-center justify-between mb-4">
          <h2 className={cn("text-sm font-semibold", isDark ? "text-[#d4d4d4]" : "text-neutral-900")}>
            Campaigns ({(project.campaign_filters || []).length})
          </h2>
        </div>

        {/* Campaign list with source badges */}
        {(project.campaign_filters || []).length > 0 ? (
          <div className="flex flex-wrap gap-2 mb-4" data-testid="campaign-list">
            {(project.campaign_filters || []).map(name => {
              const source = getSource(name);
              return (
                <span
                  key={name}
                  data-testid="campaign-badge"
                  className={cn(
                    "inline-flex items-center gap-1.5 pl-2 pr-1 py-1 rounded-lg text-sm group border",
                    isDark ? "bg-[#2d2d2d] border-[#3c3c3c]" : "bg-neutral-50 border-neutral-200"
                  )}
                >
                  <span className={`text-[10px] font-bold px-1 py-0.5 rounded ${
                    source === 'smartlead' ? 'bg-blue-100 text-blue-700' :
                    source === 'getsales' ? 'bg-green-100 text-green-700' :
                    isDark ? 'bg-[#3c3c3c] text-[#858585]' : 'bg-neutral-100 text-neutral-500'
                  }`}>
                    {source === 'smartlead' ? 'SL' : source === 'getsales' ? 'GS' : '?'}
                  </span>
                  <span className={cn(isDark ? "text-[#b0b0b0]" : "text-neutral-700")}>{name}</span>
                  <button
                    onClick={() => handleRemoveCampaign(name)}
                    className={cn("p-0.5 transition-colors opacity-0 group-hover:opacity-100", isDark ? "text-[#6e6e6e] hover:text-red-400" : "text-neutral-300 hover:text-red-500")}
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </span>
              );
            })}
          </div>
        ) : (
          <p className={cn("text-sm mb-4", isDark ? "text-[#6e6e6e]" : "text-neutral-400")}>No campaigns linked yet. Add campaigns below.</p>
        )}

        {/* Add campaign search */}
        <div className="relative" ref={dropdownRef}>
          <div className="relative">
            <Search className={cn("absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4", isDark ? "text-[#6e6e6e]" : "text-neutral-400")} />
            <input
              type="text"
              value={campaignSearch}
              onChange={e => setCampaignSearch(e.target.value)}
              onFocus={() => setShowCampaignDropdown(true)}
              placeholder="Search campaigns to add..."
              className={cn(
                "w-full pl-9 pr-3 py-2 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/20",
                isDark
                  ? "bg-[#3c3c3c] border border-transparent text-[#d4d4d4] placeholder-[#6e6e6e] focus:border-[#505050]"
                  : "border border-neutral-300 text-neutral-900 focus:border-violet-300"
              )}
            />
          </div>
          {showCampaignDropdown && (campaignSearch || filteredCampaigns.length > 0) && (
            <div className={cn("absolute top-full left-0 right-0 mt-1 rounded-lg shadow-lg z-50 max-h-56 overflow-y-auto border", isDark ? "bg-[#252526] border-[#3c3c3c]" : "bg-white border-neutral-200")}>
              {filteredCampaigns.length === 0 ? (
                <div className={cn("px-3 py-2 text-xs", isDark ? "text-[#6e6e6e]" : "text-neutral-500")}>No matching campaigns</div>
              ) : (
                filteredCampaigns.map(c => (
                  <button
                    key={c.name}
                    onClick={() => { handleAddCampaign(c.name); setShowCampaignDropdown(false); }}
                    className={cn("w-full px-3 py-2 text-left text-sm flex items-center gap-2", isDark ? "hover:bg-[#2d2d2d] text-[#b0b0b0]" : "hover:bg-neutral-50 text-neutral-700")}
                  >
                    <span className={`text-[10px] font-bold px-1 py-0.5 rounded ${
                      c.source === 'smartlead' ? 'bg-blue-100 text-blue-700' :
                      c.source === 'getsales' ? 'bg-green-100 text-green-700' :
                      isDark ? 'bg-[#3c3c3c] text-[#858585]' : 'bg-neutral-100 text-neutral-500'
                    }`}>
                      {c.source === 'smartlead' ? 'SL' : c.source === 'getsales' ? 'GS' : '?'}
                    </span>
                    <span className="truncate">{c.name}</span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* Webhook Tracking Section */}
      <div className={cn("rounded-xl p-5 border", isDark ? "bg-[#252526] border-[#333]" : "bg-white border-neutral-200")}>
        <div className="flex items-center justify-between">
          <h2 className={cn("text-sm font-semibold flex items-center gap-2", isDark ? "text-[#d4d4d4]" : "text-neutral-900")}>
            <Zap className="w-4 h-4" />
            Webhook Tracking
          </h2>
          <div className="flex items-center gap-3">
            <span className={cn(
              "text-xs font-medium px-2 py-0.5 rounded-full",
              project.webhooks_enabled !== false
                ? "bg-green-100 text-green-700"
                : "bg-red-100 text-red-700"
            )}>
              {project.webhooks_enabled !== false ? "Enabled" : "Disabled"}
            </span>
            <button
              onClick={handleToggleWebhooks}
              disabled={togglingWebhooks}
              className={cn(
                "text-xs px-3 py-1.5 rounded-lg font-medium transition-colors",
                project.webhooks_enabled !== false
                  ? isDark ? "bg-red-900/30 text-red-400 hover:bg-red-900/50" : "bg-red-50 text-red-600 hover:bg-red-100"
                  : isDark ? "bg-green-900/30 text-green-400 hover:bg-green-900/50" : "bg-green-50 text-green-600 hover:bg-green-100"
              )}
            >
              {togglingWebhooks ? <Loader2 className="w-3 h-3 animate-spin" /> : project.webhooks_enabled !== false ? "Disable" : "Enable"}
            </button>
          </div>
        </div>
        <p className={cn("text-xs mt-2", isDark ? "text-[#6e6e6e]" : "text-neutral-400")}>
          Controls SmartLead webhook registration, reply polling, and event processing for this project's campaigns.
        </p>
      </div>

      {/* Data Monitoring Section */}
      <MonitoringSection monitoring={monitoring} loading={monitoringLoading} onRefresh={loadMonitoring} isDark={isDark} />

      {/* Telegram Section */}
      <div className={cn("rounded-xl p-5 border", isDark ? "bg-[#252526] border-[#333]" : "bg-white border-neutral-200")}>
        <h2 className={cn("text-sm font-semibold mb-3 flex items-center gap-2", isDark ? "text-[#d4d4d4]" : "text-neutral-900")}>
          <MessageCircle className="w-4 h-4" />
          Telegram Notifications
        </h2>
        <TelegramConnect projectId={project.id} onUpdate={loadProject} isDark={isDark} />
      </div>

      {/* Google Sheet Sync Section */}
      <SheetSyncSection project={project} onUpdate={loadProject} isDark={isDark} />
    </div>
  );
}


/* Data Monitoring section */
function MonitoringSection({ monitoring, loading, onRefresh, isDark }: { monitoring: ProjectMonitoring | null; loading: boolean; onRefresh: () => void; isDark: boolean }) {
  const timeAgo = (iso: string | null) => {
    if (!iso) return 'never';
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return `${Math.round(diff)}s ago`;
    if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
    return `${Math.round(diff / 86400)}d ago`;
  };

  const StatusDot = ({ ok }: { ok: boolean }) => (
    <span className={cn("inline-block w-2 h-2 rounded-full", ok ? "bg-green-500" : "bg-red-500")} />
  );

  const taskStatusIcon = (status: string) => {
    if (status === 'running') return <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />;
    if (status === 'dead') return <XCircle className="w-3.5 h-3.5 text-red-500" />;
    return <Clock className="w-3.5 h-3.5 text-yellow-500" />;
  };

  return (
    <div className={cn("rounded-xl p-5 border", isDark ? "bg-[#252526] border-[#333]" : "bg-white border-neutral-200")}>
      <div className="flex items-center justify-between mb-4">
        <h2 className={cn("text-sm font-semibold flex items-center gap-2", isDark ? "text-[#d4d4d4]" : "text-neutral-900")}>
          <Activity className="w-4 h-4" />
          Data Monitoring
        </h2>
        <button
          onClick={onRefresh}
          disabled={loading}
          className={cn("p-1.5 rounded-lg transition-colors", isDark ? "hover:bg-[#3c3c3c] text-[#858585]" : "hover:bg-neutral-100 text-neutral-400")}
        >
          <RefreshCw className={cn("w-4 h-4", loading && "animate-spin")} />
        </button>
      </div>

      {!monitoring ? (
        <div className={cn("text-xs text-center py-4", isDark ? "text-[#6e6e6e]" : "text-neutral-400")}>
          {loading ? 'Loading monitoring data...' : 'No monitoring data available'}
        </div>
      ) : (
        <div className="space-y-4">
          {/* Health Overview */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className={cn("rounded-lg p-3 border", isDark ? "bg-[#1e1e1e] border-[#333]" : "bg-neutral-50 border-neutral-100")}>
              <div className={cn("text-[10px] uppercase tracking-wider mb-1", isDark ? "text-[#6e6e6e]" : "text-neutral-400")}>Webhooks</div>
              <div className="flex items-center gap-1.5">
                <StatusDot ok={monitoring.webhooks.healthy} />
                <span className={cn("text-sm font-semibold", isDark ? "text-[#d4d4d4]" : "text-neutral-900")}>
                  {monitoring.webhooks.healthy ? 'Healthy' : 'Unhealthy'}
                </span>
              </div>
              <div className={cn("text-[10px] mt-1", isDark ? "text-[#6e6e6e]" : "text-neutral-400")}>
                Last: {timeAgo(monitoring.webhooks.last_received)}
              </div>
            </div>

            <div className={cn("rounded-lg p-3 border", isDark ? "bg-[#1e1e1e] border-[#333]" : "bg-neutral-50 border-neutral-100")}>
              <div className={cn("text-[10px] uppercase tracking-wider mb-1", isDark ? "text-[#6e6e6e]" : "text-neutral-400")}>Replies 24h</div>
              <div className={cn("text-sm font-semibold", isDark ? "text-[#d4d4d4]" : "text-neutral-900")}>
                {monitoring.reply_stats.replies_24h}
              </div>
              <div className={cn("text-[10px] mt-1", isDark ? "text-[#6e6e6e]" : "text-neutral-400")}>
                7d: {monitoring.reply_stats.replies_7d}
              </div>
            </div>

            <div className={cn("rounded-lg p-3 border", isDark ? "bg-[#1e1e1e] border-[#333]" : "bg-neutral-50 border-neutral-100")}>
              <div className={cn("text-[10px] uppercase tracking-wider mb-1", isDark ? "text-[#6e6e6e]" : "text-neutral-400")}>Contacts</div>
              <div className={cn("text-sm font-semibold", isDark ? "text-[#d4d4d4]" : "text-neutral-900")}>
                {monitoring.reply_stats.total_contacts.toLocaleString()}
              </div>
              <div className={cn("text-[10px] mt-1", isDark ? "text-[#6e6e6e]" : "text-neutral-400")}>
                Replied: {monitoring.reply_stats.total_replied.toLocaleString()}
              </div>
            </div>

            <div className={cn("rounded-lg p-3 border", isDark ? "bg-[#1e1e1e] border-[#333]" : "bg-neutral-50 border-neutral-100")}>
              <div className={cn("text-[10px] uppercase tracking-wider mb-1", isDark ? "text-[#6e6e6e]" : "text-neutral-400")}>Failed Events</div>
              <div className="flex items-center gap-1.5">
                {monitoring.reply_stats.failed_events_24h > 0 && <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />}
                <span className={cn("text-sm font-semibold", isDark ? "text-[#d4d4d4]" : "text-neutral-900")}>
                  {monitoring.reply_stats.failed_events_24h}
                </span>
              </div>
              <div className={cn("text-[10px] mt-1", isDark ? "text-[#6e6e6e]" : "text-neutral-400")}>in last 24h</div>
            </div>
          </div>

          {/* Polling Intervals */}
          <div>
            <h3 className={cn("text-xs font-semibold mb-2 flex items-center gap-1.5", isDark ? "text-[#b0b0b0]" : "text-neutral-600")}>
              <Radio className="w-3.5 h-3.5" />
              Polling & Sync Intervals
            </h3>
            <div className={cn("rounded-lg border overflow-hidden", isDark ? "border-[#333]" : "border-neutral-200")}>
              <table className="w-full text-xs">
                <thead>
                  <tr className={cn(isDark ? "bg-[#1e1e1e] text-[#858585]" : "bg-neutral-50 text-neutral-500")}>
                    <th className="text-left px-3 py-1.5 font-medium">Task</th>
                    <th className="text-left px-3 py-1.5 font-medium">Interval</th>
                    <th className="text-left px-3 py-1.5 font-medium">Last Run</th>
                    <th className="text-center px-3 py-1.5 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {monitoring.polling.intervals.map((p, i) => {
                    const taskKey = p.task.toLowerCase().replace(/\s+/g, '_');
                    const health = monitoring.scheduler.task_health[taskKey] || monitoring.scheduler.task_health[taskKey.replace('_polling', '_check')] || 'unknown';
                    return (
                      <tr key={i} className={cn("border-t", isDark ? "border-[#333]" : "border-neutral-100")}>
                        <td className={cn("px-3 py-1.5 font-medium", isDark ? "text-[#d4d4d4]" : "text-neutral-700")}>{p.task}</td>
                        <td className={cn("px-3 py-1.5", isDark ? "text-[#b0b0b0]" : "text-neutral-600")}>
                          <span className={cn("px-1.5 py-0.5 rounded text-[10px] font-mono", isDark ? "bg-[#2d2d2d]" : "bg-neutral-100")}>
                            {p.interval}
                          </span>
                        </td>
                        <td className={cn("px-3 py-1.5", isDark ? "text-[#858585]" : "text-neutral-400")}>{timeAgo(p.last_run)}</td>
                        <td className="px-3 py-1.5 text-center">{taskStatusIcon(health)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className={cn("flex gap-4 mt-2 text-[10px]", isDark ? "text-[#6e6e6e]" : "text-neutral-400")}>
              <span>Reply checks: {monitoring.polling.reply_checks_count}</span>
              <span>Full syncs: {monitoring.polling.sync_count}</span>
            </div>
          </div>

          {/* Scheduler Tasks Health */}
          <div>
            <h3 className={cn("text-xs font-semibold mb-2 flex items-center gap-1.5", isDark ? "text-[#b0b0b0]" : "text-neutral-600")}>
              <Zap className="w-3.5 h-3.5" />
              Scheduler Tasks
            </h3>
            <div className="flex flex-wrap gap-2">
              {Object.entries(monitoring.scheduler.task_health).map(([task, status]) => (
                <span
                  key={task}
                  className={cn(
                    "inline-flex items-center gap-1.5 px-2 py-1 rounded-md text-[11px] border",
                    status === 'running'
                      ? isDark ? "bg-green-900/20 border-green-800/30 text-green-400" : "bg-green-50 border-green-200 text-green-700"
                      : status === 'dead'
                        ? isDark ? "bg-red-900/20 border-red-800/30 text-red-400" : "bg-red-50 border-red-200 text-red-700"
                        : isDark ? "bg-yellow-900/20 border-yellow-800/30 text-yellow-400" : "bg-yellow-50 border-yellow-200 text-yellow-700"
                  )}
                >
                  {taskStatusIcon(status)}
                  {task.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          </div>

          {/* Campaign Stats */}
          {monitoring.campaigns.length > 0 && (
            <div>
              <h3 className={cn("text-xs font-semibold mb-2", isDark ? "text-[#b0b0b0]" : "text-neutral-600")}>
                Campaign Tracking ({monitoring.campaigns.length})
              </h3>
              <div className={cn("rounded-lg border overflow-hidden", isDark ? "border-[#333]" : "border-neutral-200")}>
                <table className="w-full text-xs">
                  <thead>
                    <tr className={cn(isDark ? "bg-[#1e1e1e] text-[#858585]" : "bg-neutral-50 text-neutral-500")}>
                      <th className="text-left px-3 py-1.5 font-medium">Campaign</th>
                      <th className="text-center px-3 py-1.5 font-medium">Platform</th>
                      <th className="text-center px-3 py-1.5 font-medium">Status</th>
                      <th className="text-right px-3 py-1.5 font-medium">Contacts</th>
                      <th className="text-right px-3 py-1.5 font-medium">Replied</th>
                    </tr>
                  </thead>
                  <tbody>
                    {monitoring.campaigns.map((c, i) => (
                      <tr key={i} className={cn("border-t", isDark ? "border-[#333]" : "border-neutral-100")}>
                        <td className={cn("px-3 py-1.5 max-w-[240px] truncate font-medium", isDark ? "text-[#d4d4d4]" : "text-neutral-700")} title={c.name}>{c.name}</td>
                        <td className="px-3 py-1.5 text-center">
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                            c.platform === 'smartlead' ? 'bg-blue-100 text-blue-700' :
                            c.platform === 'getsales' ? 'bg-green-100 text-green-700' :
                            isDark ? 'bg-[#3c3c3c] text-[#858585]' : 'bg-neutral-100 text-neutral-500'
                          }`}>
                            {c.platform === 'smartlead' ? 'SL' : c.platform === 'getsales' ? 'GS' : c.platform}
                          </span>
                        </td>
                        <td className="px-3 py-1.5 text-center">
                          <span className={cn(
                            "text-[10px] px-1.5 py-0.5 rounded",
                            c.status === 'active' || c.status === 'STARTED' || c.status === 'in_progress'
                              ? 'bg-green-100 text-green-700'
                              : c.status === 'completed' || c.status === 'COMPLETED' || c.status === 'finished'
                                ? isDark ? 'bg-[#3c3c3c] text-[#858585]' : 'bg-neutral-100 text-neutral-500'
                                : 'bg-yellow-100 text-yellow-700'
                          )}>
                            {c.status}
                          </span>
                        </td>
                        <td className={cn("px-3 py-1.5 text-right tabular-nums", isDark ? "text-[#b0b0b0]" : "text-neutral-600")}>{c.contacts.toLocaleString()}</td>
                        <td className={cn("px-3 py-1.5 text-right tabular-nums", isDark ? "text-[#b0b0b0]" : "text-neutral-600")}>{c.replied.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}


/* Google Sheet Sync section */
function SheetSyncSection({ project, onUpdate, isDark }: { project: Project; onUpdate: () => void; isDark: boolean }) {
  const config = project.sheet_sync_config;
  const [sheetUrl, setSheetUrl] = useState('');
  const [leadsTab, setLeadsTab] = useState('Leads');
  const [repliesTab, setRepliesTab] = useState('Replies');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<Record<string, any> | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<Record<string, any> | null>(null);
  const [toggling, setToggling] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (config) {
      setSheetUrl(config.sheet_id ? `https://docs.google.com/spreadsheets/d/${config.sheet_id}` : '');
      setLeadsTab(config.leads_tab || 'Leads');
      setRepliesTab(config.replies_tab || 'Replies');
    }
  }, [config]);

  const parseSheetId = (url: string): string => {
    const match = url.match(/\/d\/([a-zA-Z0-9_-]+)/);
    return match ? match[1] : url.trim();
  };

  const handleSaveConfig = async () => {
    setSaving(true);
    try {
      const sheetId = parseSheetId(sheetUrl);
      if (!sheetId) return;
      const newConfig: SheetSyncConfig = {
        enabled: config?.enabled || false,
        sheet_id: sheetId,
        leads_tab: leadsTab,
        replies_tab: repliesTab,
        ...(config?.last_replies_sync_at ? { last_replies_sync_at: config.last_replies_sync_at } : {}),
        ...(config?.last_leads_push_at ? { last_leads_push_at: config.last_leads_push_at } : {}),
        ...(config?.last_qualification_poll_at ? { last_qualification_poll_at: config.last_qualification_poll_at } : {}),
        replies_synced_count: config?.replies_synced_count || 0,
        leads_pushed_count: config?.leads_pushed_count || 0,
      };
      await contactsApi.updateProject(project.id, { sheet_sync_config: newConfig });
      onUpdate();
    } catch {}
    setSaving(false);
  };

  const handleToggleEnabled = async () => {
    if (!config?.sheet_id) return;
    setToggling(true);
    try {
      const newConfig = { ...config, enabled: !config.enabled };
      await contactsApi.updateProject(project.id, { sheet_sync_config: newConfig });
      onUpdate();
    } catch {}
    setToggling(false);
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const result = await contactsApi.testSheetConnection(project.id);
      setTestResult(result);
    } catch (e: any) {
      setTestResult({ success: false, error: e?.response?.data?.detail || 'Connection failed' });
    }
    setTesting(false);
  };

  const handleSync = async (type: 'all' | 'replies' | 'leads' | 'qualification') => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const result = await contactsApi.triggerSheetSync(project.id, type);
      setSyncResult(result);
      onUpdate();
    } catch (e: any) {
      setSyncResult({ error: e?.response?.data?.detail || 'Sync failed' });
    }
    setSyncing(false);
  };

  const formatTime = (iso?: string | null) => {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleString();
    } catch { return iso; }
  };

  return (
    <div className={cn("rounded-xl p-5 border", isDark ? "bg-[#252526] border-[#333]" : "bg-white border-neutral-200")}>
      <div className="flex items-center justify-between mb-4">
        <h2 className={cn("text-sm font-semibold flex items-center gap-2", isDark ? "text-[#d4d4d4]" : "text-neutral-900")}>
          <FileSpreadsheet className="w-4 h-4" />
          Google Sheet Sync
        </h2>
        {config?.sheet_id && (
          <div className="flex items-center gap-3">
            <span className={cn(
              "text-xs font-medium px-2 py-0.5 rounded-full",
              config.enabled
                ? "bg-green-100 text-green-700"
                : "bg-neutral-100 text-neutral-500"
            )}>
              {config.enabled ? "Enabled" : "Disabled"}
            </span>
            <button
              onClick={handleToggleEnabled}
              disabled={toggling}
              className={cn(
                "text-xs px-3 py-1.5 rounded-lg font-medium transition-colors",
                config.enabled
                  ? isDark ? "bg-red-900/30 text-red-400 hover:bg-red-900/50" : "bg-red-50 text-red-600 hover:bg-red-100"
                  : isDark ? "bg-green-900/30 text-green-400 hover:bg-green-900/50" : "bg-green-50 text-green-600 hover:bg-green-100"
              )}
            >
              {toggling ? <Loader2 className="w-3 h-3 animate-spin" /> : config.enabled ? "Disable" : "Enable"}
            </button>
          </div>
        )}
      </div>

      {/* Sheet URL input */}
      <div className="space-y-3">
        <div>
          <label className={cn("text-xs font-medium block mb-1", isDark ? "text-[#858585]" : "text-neutral-500")}>
            Google Sheet URL or ID
          </label>
          <input
            type="text"
            value={sheetUrl}
            onChange={e => setSheetUrl(e.target.value)}
            placeholder="https://docs.google.com/spreadsheets/d/..."
            className={cn(
              "w-full px-3 py-2 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/20",
              isDark
                ? "bg-[#3c3c3c] border border-transparent text-[#d4d4d4] placeholder-[#6e6e6e] focus:border-[#505050]"
                : "border border-neutral-300 text-neutral-900 focus:border-violet-300"
            )}
          />
        </div>

        <div className="flex gap-3">
          <div className="flex-1">
            <label className={cn("text-xs font-medium block mb-1", isDark ? "text-[#858585]" : "text-neutral-500")}>
              Leads Tab
            </label>
            <input
              type="text"
              value={leadsTab}
              onChange={e => setLeadsTab(e.target.value)}
              className={cn(
                "w-full px-3 py-2 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/20",
                isDark
                  ? "bg-[#3c3c3c] border border-transparent text-[#d4d4d4] focus:border-[#505050]"
                  : "border border-neutral-300 text-neutral-900 focus:border-violet-300"
              )}
            />
          </div>
          <div className="flex-1">
            <label className={cn("text-xs font-medium block mb-1", isDark ? "text-[#858585]" : "text-neutral-500")}>
              Replies Tab
            </label>
            <input
              type="text"
              value={repliesTab}
              onChange={e => setRepliesTab(e.target.value)}
              className={cn(
                "w-full px-3 py-2 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/20",
                isDark
                  ? "bg-[#3c3c3c] border border-transparent text-[#d4d4d4] focus:border-[#505050]"
                  : "border border-neutral-300 text-neutral-900 focus:border-violet-300"
              )}
            />
          </div>
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleSaveConfig}
            disabled={saving || !sheetUrl.trim()}
            className={cn(
              "text-xs px-3 py-1.5 rounded-lg font-medium transition-colors",
              isDark ? "bg-violet-900/30 text-violet-400 hover:bg-violet-900/50" : "bg-violet-50 text-violet-600 hover:bg-violet-100"
            )}
          >
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : "Save Config"}
          </button>
          {config?.sheet_id && (
            <button
              onClick={handleTest}
              disabled={testing}
              className={cn(
                "text-xs px-3 py-1.5 rounded-lg font-medium transition-colors",
                isDark ? "bg-blue-900/30 text-blue-400 hover:bg-blue-900/50" : "bg-blue-50 text-blue-600 hover:bg-blue-100"
              )}
            >
              {testing ? <Loader2 className="w-3 h-3 animate-spin" /> : "Test Connection"}
            </button>
          )}
        </div>

        {/* Test result */}
        {testResult && (
          <div className={cn(
            "text-xs p-3 rounded-lg",
            testResult.success
              ? isDark ? "bg-green-900/20 text-green-400" : "bg-green-50 text-green-700"
              : isDark ? "bg-red-900/20 text-red-400" : "bg-red-50 text-red-700"
          )}>
            {testResult.success ? (
              <div className="space-y-1">
                <div className="font-medium">Connected: {testResult.sheet_title}</div>
                {testResult.tabs?.map((t: any) => (
                  <div key={t.name}>
                    Tab "{t.name}" — {t.row_count} rows
                    {t.name === leadsTab && (testResult.leads_tab_found ? ' ✓' : ' ✗')}
                    {t.name === repliesTab && (testResult.replies_tab_found ? ' ✓' : ' ✗')}
                  </div>
                ))}
              </div>
            ) : (
              <div>{testResult.error || 'Connection failed'}</div>
            )}
          </div>
        )}

        {/* Sync status + manual trigger */}
        {config?.sheet_id && (
          <div className={cn("border-t pt-3 mt-3 space-y-2", isDark ? "border-[#333]" : "border-neutral-200")}>
            <div className={cn("text-xs space-y-1", isDark ? "text-[#858585]" : "text-neutral-500")}>
              <div>Replies synced: {config.replies_synced_count || 0} — last: {formatTime(config.last_replies_sync_at)}</div>
              <div>Leads pushed: {config.leads_pushed_count || 0} — last: {formatTime(config.last_leads_push_at)}</div>
              <div>Qualification poll: {formatTime(config.last_qualification_poll_at)}</div>
              {config.last_error && (
                <div className={cn("text-xs mt-1", isDark ? "text-red-400" : "text-red-600")}>
                  Error: {config.last_error} ({formatTime(config.last_error_at)})
                </div>
              )}
            </div>

            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => handleSync('all')}
                disabled={syncing}
                className={cn(
                  "text-xs px-3 py-1.5 rounded-lg font-medium transition-colors flex items-center gap-1",
                  isDark ? "bg-violet-900/30 text-violet-400 hover:bg-violet-900/50" : "bg-violet-50 text-violet-600 hover:bg-violet-100"
                )}
              >
                {syncing ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                Sync All
              </button>
              <button
                onClick={() => handleSync('replies')}
                disabled={syncing}
                className={cn(
                  "text-xs px-2.5 py-1.5 rounded-lg transition-colors",
                  isDark ? "text-[#858585] hover:text-[#d4d4d4] hover:bg-[#333]" : "text-neutral-500 hover:text-neutral-700 hover:bg-neutral-100"
                )}
              >
                Replies
              </button>
              <button
                onClick={() => handleSync('leads')}
                disabled={syncing}
                className={cn(
                  "text-xs px-2.5 py-1.5 rounded-lg transition-colors",
                  isDark ? "text-[#858585] hover:text-[#d4d4d4] hover:bg-[#333]" : "text-neutral-500 hover:text-neutral-700 hover:bg-neutral-100"
                )}
              >
                Leads
              </button>
              <button
                onClick={() => handleSync('qualification')}
                disabled={syncing}
                className={cn(
                  "text-xs px-2.5 py-1.5 rounded-lg transition-colors",
                  isDark ? "text-[#858585] hover:text-[#d4d4d4] hover:bg-[#333]" : "text-neutral-500 hover:text-neutral-700 hover:bg-neutral-100"
                )}
              >
                Qualification
              </button>
            </div>

            {/* Sync result */}
            {syncResult && (
              <div className={cn(
                "text-xs p-2 rounded-lg",
                syncResult.error
                  ? isDark ? "bg-red-900/20 text-red-400" : "bg-red-50 text-red-700"
                  : isDark ? "bg-green-900/20 text-green-400" : "bg-green-50 text-green-700"
              )}>
                {syncResult.error ? syncResult.error : (
                  <pre className="whitespace-pre-wrap">{JSON.stringify(syncResult.results, null, 2)}</pre>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}


/* One-click Telegram connect component */
function TelegramConnect({ projectId, onUpdate, isDark }: { projectId: number; onUpdate: () => void; isDark: boolean }) {
  const [status, setStatus] = useState<'idle' | 'waiting' | 'connected'>('idle');
  const [firstName, setFirstName] = useState('');
  const [username, setUsername] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;
    contactsApi.getTelegramStatus(projectId).then(data => {
      if (cancelled) return;
      if (data.connected) {
        setStatus('connected');
        setFirstName(data.first_name || '');
        setUsername(data.username || '');
      }
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [projectId]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  const handleConnect = () => {
    window.open(`https://t.me/ImpecableBot?start=project_${projectId}`, '_blank');
    setStatus('waiting');
    pollRef.current = setInterval(async () => {
      try {
        const data = await contactsApi.getTelegramStatus(projectId);
        if (data.connected) {
          setStatus('connected');
          setFirstName(data.first_name || '');
          setUsername(data.username || '');
          if (pollRef.current) clearInterval(pollRef.current);
          if (timeoutRef.current) clearTimeout(timeoutRef.current);
          onUpdate();
        }
      } catch {}
    }, 2000);
    timeoutRef.current = setTimeout(() => {
      if (pollRef.current) clearInterval(pollRef.current);
      setStatus(prev => prev === 'waiting' ? 'idle' : prev);
    }, 60000);
  };

  const handleDisconnect = async () => {
    try {
      await contactsApi.disconnectTelegram(projectId);
      setStatus('idle');
      setFirstName('');
      setUsername('');
      onUpdate();
    } catch {}
  };

  if (status === 'connected') {
    return (
      <div className={cn("flex items-center justify-between py-2 px-3 rounded-lg", isDark ? "bg-green-900/20" : "bg-green-50")}>
        <div className={cn("flex items-center gap-2 text-sm", isDark ? "text-green-400" : "text-green-700")}>
          <Check className="w-4 h-4" />
          <span>Connected{firstName ? ` as ${firstName}` : ''}{username ? ` (@${username})` : ''}</span>
        </div>
        <button onClick={handleDisconnect} className={cn("flex items-center gap-1 text-xs transition-colors", isDark ? "text-[#6e6e6e] hover:text-red-400" : "text-neutral-400 hover:text-red-500")}>
          <Unlink className="w-3.5 h-3.5" />
          Disconnect
        </button>
      </div>
    );
  }

  if (status === 'waiting') {
    return (
      <div className={cn("flex items-center gap-3 py-2 px-3 rounded-lg", isDark ? "bg-blue-900/20" : "bg-blue-50")}>
        <Loader2 className={cn("w-4 h-4 animate-spin", isDark ? "text-blue-400" : "text-blue-600")} />
        <div className={cn("text-sm", isDark ? "text-blue-300" : "text-blue-700")}>Tap <b>Start</b> in Telegram to connect...</div>
        <button onClick={() => { if (pollRef.current) clearInterval(pollRef.current); if (timeoutRef.current) clearTimeout(timeoutRef.current); setStatus('idle'); }} className={cn("ml-auto text-xs", isDark ? "text-[#6e6e6e] hover:text-[#b0b0b0]" : "text-neutral-400 hover:text-neutral-600")}>
          Cancel
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <button onClick={handleConnect} className={cn("flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors", isDark ? "bg-blue-900/20 text-blue-400 hover:bg-blue-900/30" : "bg-blue-50 text-blue-700 hover:bg-blue-100")}>
        <MessageCircle className="w-4 h-4" />
        Connect Telegram
      </button>
      <span className={cn("text-xs", isDark ? "text-[#6e6e6e]" : "text-neutral-400")}>Get reply notifications in Telegram</span>
    </div>
  );
}
