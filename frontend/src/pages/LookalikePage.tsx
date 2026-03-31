import { useState, useEffect, useCallback } from 'react';
import {
  Target, Play, Loader2, RefreshCw, ExternalLink,
  BarChart3, Users, Globe, Zap, Search as SearchIcon,
  ChevronDown, ChevronRight, CheckCircle2, FileSpreadsheet,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useAppStore } from '../store/appStore';
import { api } from '../api/client';

// ============ Types ============

interface Cluster {
  id: number;
  project_id: number;
  name: string;
  business_model: string;
  offer_fit: string[];
  search_strategy: any;
  qualified_lead_count: number;
  apollo_companies_found: number;
  yandex_targets_found: number;
  google_targets_found: number;
  total_lookalikes: number;
  is_active: boolean;
  created_at: string;
  members?: ClusterMember[];
  runs?: Run[];
}

interface ClusterMember {
  id: number;
  contact_id: number;
  company_name: string;
  domain: string;
  name: string;
  job_title: string;
  business_model_description: string;
  offer_fit: string[];
  website_scraped: boolean;
}

interface Run {
  id: number;
  cluster_id: number;
  status: string;
  current_phase: string | null;
  apollo_job_id: number | null;
  yandex_job_id: number | null;
  google_job_id: number | null;
  stats: any;
  total_lookalikes_found: number;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

interface SearchResultItem {
  id: number;
  domain: string;
  company_name: string;
  company_description: string;
  cluster_id: number;
  is_target: boolean;
  confidence: number;
  reasoning: string;
  scores: any;
  matched_segment: string;
  analyzed_at: string | null;
}

interface Dashboard {
  project_id: number;
  total_clusters: number;
  total_qualified_leads: number;
  total_lookalikes: number;
  clusters: Array<{
    id: number;
    name: string;
    business_model: string;
    offer_fit: string[];
    qualified_leads: number;
    apollo_found: number;
    yandex_found: number;
    google_found: number;
    total_lookalikes: number;
    has_strategy: boolean;
  }>;
}

type TabId = 'clusters' | 'results' | 'dashboard';

const statusColors: Record<string, string> = {
  COMPLETED: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  RUNNING: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  PENDING: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
  FAILED: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  PAUSED: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400',
};

const offerColors: Record<string, string> = {
  pay_gate: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
  payout: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  otc: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
};

const segmentColors: Record<string, string> = {
  crypto: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
  other_hnwi: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-400',
  investment: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400',
  migration: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900/30 dark:text-cyan-400',
  legal: 'bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-400',
};

// ============ Main Page ============

export function LookalikePage() {
  const { currentProject } = useAppStore();
  const [activeTab, setActiveTab] = useState<TabId>('clusters');

  if (!currentProject) {
    return (
      <div className="p-6 text-center text-gray-500 dark:text-gray-400">
        Select a project to view TAM analysis
      </div>
    );
  }

  const tabs: { id: TabId; label: string; icon: any }[] = [
    { id: 'clusters', label: 'Clusters', icon: Users },
    { id: 'results', label: 'Results', icon: Target },
    { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
  ];

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          TAM / Lookalike Analysis
        </h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
              activeTab === id
                ? 'border-blue-500 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
            )}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'clusters' && <ClustersTab projectId={currentProject.id} />}
      {activeTab === 'results' && <ResultsTab projectId={currentProject.id} />}
      {activeTab === 'dashboard' && <DashboardTab projectId={currentProject.id} />}
    </div>
  );
}

// ============ Clusters Tab ============

function ClustersTab({ projectId }: { projectId: number }) {
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [runningClusters, setRunningClusters] = useState<Set<number>>(new Set());

  const loadClusters = useCallback(async () => {
    try {
      setLoading(true);
      const resp = await api.get(`/lookalike/projects/${projectId}/clusters`);
      setClusters(resp.data);
    } catch (err) {
      console.error('Failed to load clusters:', err);
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { loadClusters(); }, [loadClusters]);

  const handleAnalyze = async () => {
    try {
      setAnalyzing(true);
      await api.post(`/lookalike/projects/${projectId}/analyze`);
      await loadClusters();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleRunSearch = async (clusterId: number) => {
    try {
      setRunningClusters(prev => new Set(prev).add(clusterId));
      await api.post(`/lookalike/clusters/${clusterId}/run`);
      const interval = setInterval(async () => { await loadClusters(); }, 5000);
      setTimeout(() => clearInterval(interval), 120000);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Search failed');
      setRunningClusters(prev => {
        const next = new Set(prev);
        next.delete(clusterId);
        return next;
      });
    }
  };

  const [runningAll, setRunningAll] = useState(false);
  const handleRunAll = async () => {
    try {
      setRunningAll(true);
      const resp = await api.post(`/lookalike/projects/${projectId}/run-all`, {
        budget_apollo_credits: 500,
        budget_yandex_queries: 0,
        budget_google_queries: 0,
      });
      // Mark all eligible clusters as running
      for (const r of resp.data.runs || []) {
        setRunningClusters(prev => new Set(prev).add(r.cluster_id));
      }
      const interval = setInterval(async () => { await loadClusters(); }, 10000);
      setTimeout(() => { clearInterval(interval); setRunningAll(false); }, 300000);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Run all failed');
      setRunningAll(false);
    }
  };

  const handleExpandCluster = async (clusterId: number) => {
    if (expandedId === clusterId) { setExpandedId(null); return; }
    try {
      const resp = await api.get(`/lookalike/clusters/${clusterId}`);
      const idx = clusters.findIndex(c => c.id === clusterId);
      if (idx >= 0) {
        const updated = [...clusters];
        updated[idx] = { ...updated[idx], members: resp.data.members, runs: resp.data.runs };
        setClusters(updated);
      }
      setExpandedId(clusterId);
    } catch (err) {
      console.error('Failed to load cluster detail:', err);
    }
  };

  if (loading) {
    return <div className="flex justify-center p-8"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button
          onClick={handleAnalyze}
          disabled={analyzing}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
        >
          {analyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
          {analyzing ? 'Analyzing...' : clusters.length > 0 ? 'Re-analyze' : 'Analyze Qualified Leads'}
        </button>
        {clusters.length > 0 && (
          <>
            <button
              onClick={handleRunAll}
              disabled={runningAll || runningClusters.size > 0}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              {runningAll ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              {runningAll ? 'Running...' : 'Run All Clusters (Apollo)'}
            </button>
            <button onClick={loadClusters} className="p-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
              <RefreshCw className="w-4 h-4" />
            </button>
          </>
        )}
      </div>

      {clusters.length === 0 ? (
        <div className="p-8 text-center text-gray-500 dark:text-gray-400 border border-dashed border-gray-300 dark:border-gray-600 rounded-lg">
          <Users className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No clusters yet. Click "Analyze Qualified Leads" to start.</p>
          <p className="text-xs mt-1">This will scrape websites, analyze business models, and group leads into clusters.</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {clusters.map(cluster => (
            <ClusterCard
              key={cluster.id}
              cluster={cluster}
              isExpanded={expandedId === cluster.id}
              isRunning={runningClusters.has(cluster.id)}
              onToggle={() => handleExpandCluster(cluster.id)}
              onRunSearch={() => handleRunSearch(cluster.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ============ Cluster Card ============

function ClusterCard({
  cluster, isExpanded, isRunning, onToggle, onRunSearch,
}: {
  cluster: Cluster;
  isExpanded: boolean;
  isRunning: boolean;
  onToggle: () => void;
  onRunSearch: () => void;
}) {
  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
      <div
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50"
        onClick={onToggle}
      >
        <div className="flex items-center gap-3 flex-1 min-w-0">
          {isExpanded ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
          <div className="min-w-0">
            <h3 className="font-medium text-gray-900 dark:text-gray-100 truncate">{cluster.name}</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">{cluster.business_model}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 mx-4">
          {(cluster.offer_fit || []).map(offer => (
            <span key={offer} className={cn('px-2 py-0.5 text-xs rounded-full', offerColors[offer] || 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300')}>
              {offer}
            </span>
          ))}
        </div>

        <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400 shrink-0">
          <div className="text-center">
            <div className="font-medium text-gray-900 dark:text-gray-100">{cluster.qualified_lead_count}</div>
            <div>leads</div>
          </div>
          <div className="text-center">
            <div className="font-medium text-gray-900 dark:text-gray-100">{cluster.total_lookalikes}</div>
            <div>lookalikes</div>
          </div>
          <button
            onClick={(e) => { e.stopPropagation(); onRunSearch(); }}
            disabled={isRunning || !cluster.search_strategy}
            className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-green-600 rounded hover:bg-green-700 disabled:opacity-50"
          >
            {isRunning ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
            Run Search
          </button>
        </div>
      </div>

      {isExpanded && (
        <div className="border-t border-gray-200 dark:border-gray-700 p-4 bg-gray-50/50 dark:bg-gray-800/30 space-y-4">
          {cluster.search_strategy && (
            <div className="grid grid-cols-3 gap-4 text-xs">
              <div>
                <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">Apollo Keywords</h4>
                <div className="flex flex-wrap gap-1">
                  {(cluster.search_strategy.apollo_keywords || []).map((k: string, i: number) => (
                    <span key={i} className="px-1.5 py-0.5 bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded text-gray-600 dark:text-gray-300">{k}</span>
                  ))}
                </div>
                {cluster.search_strategy.apollo_locations && (
                  <div className="mt-2">
                    <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">Locations</h4>
                    <div className="text-gray-500 dark:text-gray-400">
                      {cluster.search_strategy.apollo_locations.join(', ')}
                    </div>
                  </div>
                )}
              </div>
              <div>
                <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">Yandex Queries ({(cluster.search_strategy.yandex_queries || []).length})</h4>
                <ul className="text-gray-500 dark:text-gray-400 space-y-0.5 max-h-32 overflow-y-auto">
                  {(cluster.search_strategy.yandex_queries || []).map((q: string, i: number) => (
                    <li key={i} className="truncate">{q}</li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="font-medium text-gray-700 dark:text-gray-300 mb-1">Google Queries ({(cluster.search_strategy.google_queries || []).length})</h4>
                <ul className="text-gray-500 dark:text-gray-400 space-y-0.5 max-h-32 overflow-y-auto">
                  {(cluster.search_strategy.google_queries || []).map((q: string, i: number) => (
                    <li key={i} className="truncate">{q}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          <div className="flex gap-6 text-xs">
            <div className="flex items-center gap-1">
              <Zap className="w-3 h-3 text-purple-500" />
              <span className="text-gray-500 dark:text-gray-400">Apollo:</span>
              <span className="font-medium text-gray-900 dark:text-gray-100">{cluster.apollo_companies_found}</span>
            </div>
            <div className="flex items-center gap-1">
              <Globe className="w-3 h-3 text-orange-500" />
              <span className="text-gray-500 dark:text-gray-400">Yandex:</span>
              <span className="font-medium text-gray-900 dark:text-gray-100">{cluster.yandex_targets_found}</span>
            </div>
            <div className="flex items-center gap-1">
              <SearchIcon className="w-3 h-3 text-blue-500" />
              <span className="text-gray-500 dark:text-gray-400">Google:</span>
              <span className="font-medium text-gray-900 dark:text-gray-100">{cluster.google_targets_found}</span>
            </div>
          </div>

          {cluster.members && cluster.members.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">
                Qualified Leads ({cluster.members.length})
              </h4>
              <div className="grid grid-cols-2 gap-2">
                {cluster.members.map(m => (
                  <div key={m.id} className="flex items-center gap-2 p-2 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 text-xs">
                    <div className="min-w-0 flex-1">
                      <div className="font-medium text-gray-900 dark:text-gray-100 truncate">{m.company_name || m.domain}</div>
                      <div className="text-gray-500 dark:text-gray-400 truncate">{m.name} — {m.job_title}</div>
                      {m.business_model_description && (
                        <div className="text-gray-400 dark:text-gray-500 truncate mt-0.5 italic">{m.business_model_description}</div>
                      )}
                    </div>
                    {m.website_scraped && <CheckCircle2 className="w-3 h-3 text-green-500 shrink-0" />}
                  </div>
                ))}
              </div>
            </div>
          )}

          {cluster.runs && cluster.runs.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-gray-700 dark:text-gray-300 mb-2">Search Runs</h4>
              <div className="space-y-1">
                {cluster.runs.map(run => (
                  <div key={run.id} className="flex items-center gap-3 p-2 bg-white dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700 text-xs">
                    <span className={cn('px-2 py-0.5 rounded-full', statusColors[run.status] || 'bg-gray-100 text-gray-600')}>
                      {run.status}
                    </span>
                    {run.current_phase && <span className="text-gray-500 dark:text-gray-400">Phase: {run.current_phase}</span>}
                    <span className="font-medium text-gray-900 dark:text-gray-100">{run.total_lookalikes_found} lookalikes</span>
                    {run.error_message && <span className="text-red-500 truncate">{run.error_message}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============ Results Tab ============

function ResultsTab({ projectId }: { projectId: number }) {
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [clusterFilter, setClusterFilter] = useState<number | null>(null);
  const [clusters, setClusters] = useState<Cluster[]>([]);

  useEffect(() => {
    api.get(`/lookalike/projects/${projectId}/clusters`).then(r => setClusters(r.data)).catch(() => {});
  }, [projectId]);

  useEffect(() => {
    setLoading(true);
    const params: any = { limit: 500 };
    if (clusterFilter) params.cluster_id = clusterFilter;
    api.get(`/lookalike/projects/${projectId}/results`, { params })
      .then(r => { setResults(r.data.results); setTotal(r.data.total); })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [projectId, clusterFilter]);

  const handleExport = async () => {
    try {
      setExporting(true);
      const params: any = {};
      if (clusterFilter) params.cluster_id = clusterFilter;
      const resp = await api.post(`/lookalike/projects/${projectId}/export`, null, { params });
      if (resp.data.sheet_url) {
        window.open(resp.data.sheet_url, '_blank');
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  if (loading) {
    return <div className="flex justify-center p-8"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>;
  }

  return (
    <div className="space-y-3">
      {/* Filter bar */}
      <div className="flex items-center gap-3">
        <select
          value={clusterFilter ?? ''}
          onChange={e => setClusterFilter(e.target.value ? parseInt(e.target.value) : null)}
          className="px-3 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100"
        >
          <option value="">All clusters</option>
          {clusters.map(c => (
            <option key={c.id} value={c.id}>{c.name} ({c.total_lookalikes})</option>
          ))}
        </select>
        <span className="text-sm text-gray-500 dark:text-gray-400">{total} targets</span>
        <div className="flex-1" />
        {results.length > 0 && (
          <button
            onClick={handleExport}
            disabled={exporting}
            className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 dark:text-gray-200 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 disabled:opacity-50"
          >
            {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileSpreadsheet className="w-4 h-4" />}
            Export to Google Sheets
          </button>
        )}
      </div>

      {/* Results grouped by cluster */}
      {results.length === 0 ? (
        <div className="p-8 text-center text-gray-500 dark:text-gray-400">No results yet. Run a cluster search first.</div>
      ) : (() => {
        // Group results by cluster
        const grouped: Record<number, { name: string; results: SearchResultItem[] }> = {};
        for (const r of results) {
          if (!grouped[r.cluster_id]) {
            grouped[r.cluster_id] = {
              name: clusters.find(c => c.id === r.cluster_id)?.name || `Cluster #${r.cluster_id}`,
              results: [],
            };
          }
          grouped[r.cluster_id].results.push(r);
        }
        const clusterIds = Object.keys(grouped).map(Number);
        // If filtering by cluster, don't group — just show flat
        const showGrouped = !clusterFilter && clusterIds.length > 1;

        return (
          <div className="space-y-6">
            {(showGrouped ? clusterIds : [clusterFilter || clusterIds[0]]).map(cid => {
              const group = grouped[cid];
              if (!group) return null;
              return (
                <div key={cid}>
                  {showGrouped && (
                    <div className="flex items-center gap-2 mb-2 pb-1 border-b border-gray-200 dark:border-gray-700">
                      <div className="w-3 h-3 rounded-full bg-blue-500" />
                      <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100">{group.name}</h3>
                      <span className="text-xs text-gray-500 dark:text-gray-400">({group.results.length} targets)</span>
                    </div>
                  )}
                  <div className="space-y-2">
                    {group.results.map(r => {
                      const scores = r.scores || {};
                      return (
                        <div key={r.id} className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 bg-white dark:bg-gray-800/50 hover:border-gray-300 dark:hover:border-gray-600 transition-colors">
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 flex-wrap">
                                <a
                                  href={`https://${r.domain}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1"
                                >
                                  {r.domain} <ExternalLink className="w-3 h-3" />
                                </a>
                                <span className="px-2 py-0.5 text-[10px] rounded-full font-medium bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
                                  {group.name.length > 40 ? group.name.slice(0, 40) + '...' : group.name}
                                </span>
                                {r.matched_segment && (
                                  <span className={cn('px-1.5 py-0.5 text-[10px] rounded-full font-medium', segmentColors[r.matched_segment] || 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300')}>
                                    {r.matched_segment}
                                  </span>
                                )}
                              </div>
                              <div className="text-sm font-medium text-gray-900 dark:text-gray-100 mt-0.5">
                                {r.company_name}
                              </div>
                              {r.company_description && (
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 line-clamp-2">
                                  {r.company_description}
                                </p>
                              )}
                              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                                {r.reasoning}
                              </p>
                            </div>

                            <div className="shrink-0 text-right space-y-1">
                              <div className={cn(
                                'text-lg font-bold',
                                r.confidence >= 0.7 ? 'text-green-600' : r.confidence >= 0.4 ? 'text-yellow-600' : 'text-red-600'
                              )}>
                                {(r.confidence * 100).toFixed(0)}%
                              </div>
                              {Object.keys(scores).length > 0 && (
                                <div className="flex flex-col gap-0.5 mt-1">
                                  {Object.entries(scores).map(([key, val]) => (
                                    <div key={key} className="flex items-center gap-1 text-[10px]">
                                      <span className="text-gray-400 dark:text-gray-500 w-16 text-left truncate">{key.replace('_match', '').replace('_', ' ')}</span>
                                      <div className="w-12 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                        <div
                                          className={cn('h-full rounded-full', (val as number) >= 0.7 ? 'bg-green-500' : (val as number) >= 0.4 ? 'bg-yellow-500' : 'bg-red-500')}
                                          style={{ width: `${(val as number) * 100}%` }}
                                        />
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        );
      })()}
    </div>
  );
}

// ============ Dashboard Tab ============

function DashboardTab({ projectId }: { projectId: number }) {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get(`/lookalike/projects/${projectId}/dashboard`)
      .then(r => setDashboard(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return <div className="flex justify-center p-8"><Loader2 className="w-6 h-6 animate-spin text-gray-400" /></div>;
  }

  if (!dashboard) {
    return <div className="p-8 text-center text-gray-500 dark:text-gray-400">No data available</div>;
  }

  const maxLookalikes = Math.max(...dashboard.clusters.map(c => c.total_lookalikes), 1);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <div className="p-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
          <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">{dashboard.total_clusters}</div>
          <div className="text-sm text-gray-500 dark:text-gray-400">Clusters</div>
        </div>
        <div className="p-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
          <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">{dashboard.total_qualified_leads}</div>
          <div className="text-sm text-gray-500 dark:text-gray-400">Qualified Leads</div>
        </div>
        <div className="p-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg">
          <div className="text-2xl font-bold text-green-600">{dashboard.total_lookalikes}</div>
          <div className="text-sm text-gray-500 dark:text-gray-400">Total Lookalikes</div>
        </div>
      </div>

      <div className="space-y-3">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">Lookalikes by Cluster</h3>
        {dashboard.clusters.map(c => (
          <div key={c.id} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-900 dark:text-gray-100 truncate max-w-md">{c.name}</span>
              <span className="font-medium text-gray-900 dark:text-gray-100">{c.total_lookalikes}</span>
            </div>
            <div className="h-4 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden flex">
              {c.apollo_found > 0 && (
                <div className="bg-purple-500 h-full" style={{ width: `${(c.apollo_found / maxLookalikes) * 100}%` }} title={`Apollo: ${c.apollo_found}`} />
              )}
              {c.yandex_found > 0 && (
                <div className="bg-orange-500 h-full" style={{ width: `${(c.yandex_found / maxLookalikes) * 100}%` }} title={`Yandex: ${c.yandex_found}`} />
              )}
              {c.google_found > 0 && (
                <div className="bg-blue-500 h-full" style={{ width: `${(c.google_found / maxLookalikes) * 100}%` }} title={`Google: ${c.google_found}`} />
              )}
            </div>
            <div className="flex gap-4 text-xs text-gray-500 dark:text-gray-400">
              <span>{c.qualified_leads} leads</span>
              <span className="text-purple-600">Apollo: {c.apollo_found}</span>
              <span className="text-orange-600">Yandex: {c.yandex_found}</span>
              <span className="text-blue-600">Google: {c.google_found}</span>
              <span className="flex gap-1">
                {(c.offer_fit || []).map(o => (
                  <span key={o} className={cn('px-1.5 py-0 rounded', offerColors[o] || 'bg-gray-100 text-gray-600')}>{o}</span>
                ))}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="flex gap-4 text-xs text-gray-500 dark:text-gray-400 pt-2 border-t border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-1"><div className="w-3 h-3 bg-purple-500 rounded" /> Apollo (free)</div>
        <div className="flex items-center gap-1"><div className="w-3 h-3 bg-orange-500 rounded" /> Yandex (cheap)</div>
        <div className="flex items-center gap-1"><div className="w-3 h-3 bg-blue-500 rounded" /> Google (expensive)</div>
      </div>
    </div>
  );
}
