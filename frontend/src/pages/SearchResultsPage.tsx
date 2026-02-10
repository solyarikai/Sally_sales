import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useVirtualizer } from '@tanstack/react-virtual';
import {
  Target, Download, FileSpreadsheet, ArrowLeft,
  Loader2, AlertCircle, CheckCircle2, XCircle,
  ChevronDown, ChevronRight, ExternalLink, DollarSign,
  BarChart3, Globe, Mail, MessageSquare,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useAppStore } from '../store/appStore';
import {
  projectSearchApi,
  type SearchJobFullDetail,
  type SearchHistoryItem,
  type SearchResultItem,
  type QueryItem,
  type DomainCampaignsMap,
  type DomainCampaignInfo,
} from '../api/dataSearch';

const statusColors: Record<string, string> = {
  completed: 'bg-green-100 text-green-800',
  running: 'bg-blue-100 text-blue-800',
  pending: 'bg-yellow-100 text-yellow-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
};

export function SearchResultsPage() {
  const { jobId } = useParams<{ jobId: string }>();

  if (jobId) {
    return <JobDetailView jobId={parseInt(jobId)} />;
  }

  return <JobHistoryView />;
}

// ============ Job History List View ============

function JobHistoryView() {
  const navigate = useNavigate();
  const { currentCompany } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<{ items: SearchHistoryItem[]; total: number } | null>(null);
  const [page, setPage] = useState(1);
  const [exportingTargets, setExportingTargets] = useState(false);

  const handleExportTargets = async () => {
    const projectId = data?.items?.[0]?.project_id;
    if (!projectId) return;
    setExportingTargets(true);
    try {
      const { sheet_url } = await projectSearchApi.exportToGoogleSheet(projectId, {
        targets_only: true,
        exclude_contacted: true,
      });
      window.open(sheet_url, '_blank');
    } catch (err: any) {
      alert(err.userMessage || 'Export failed');
    } finally {
      setExportingTargets(false);
    }
  };

  const load = useCallback(async () => {
    if (!currentCompany) return;
    setLoading(true);
    setError(null);
    try {
      const result = await projectSearchApi.getSearchHistory(page, 20);
      setData(result);
    } catch (err: any) {
      setError(err.userMessage || 'Failed to load search history');
    } finally {
      setLoading(false);
    }
  }, [page, currentCompany]);

  useEffect(() => { load(); }, [load]);

  if (!currentCompany) {
    return (
      <div className="p-6 max-w-[1400px] mx-auto">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-blue-700 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          Select a company to view search results
        </div>
      </div>
    );
  }

  const items = data?.items || [];
  const total = data?.total || 0;

  // Stats
  const totalJobs = total;
  const totalDomains = items.reduce((s, j) => s + (j.domains_found || 0), 0);
  const totalTargets = items.reduce((s, j) => s + (j.targets_found || 0), 0);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <Loader2 className="w-6 h-6 animate-spin text-neutral-400" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Search Results</h1>
          <p className="text-neutral-500 text-sm mt-1">View search job history, results, and spending</p>
        </div>
        {data?.items?.[0]?.project_id && (
          <button
            onClick={handleExportTargets}
            disabled={exportingTargets}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
          >
            {exportingTargets ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileSpreadsheet className="w-4 h-4" />}
            Export Targets
          </button>
        )}
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4" /> {error}
        </div>
      )}

      {/* Stats cards */}
      <div className="grid grid-cols-3 gap-4">
        <StatCard icon={BarChart3} label="Total Jobs" value={totalJobs} />
        <StatCard icon={Globe} label="Domains Found" value={totalDomains} />
        <StatCard icon={Target} label="Targets Found" value={totalTargets} color="green" />
      </div>

      {/* Jobs table */}
      <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-neutral-100 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Project</th>
              <th className="px-4 py-3">Engine</th>
              <th className="px-4 py-3 text-right">Queries</th>
              <th className="px-4 py-3 text-right">Domains</th>
              <th className="px-4 py-3 text-right">Targets</th>
              <th className="px-4 py-3 text-right">Results</th>
              <th className="px-4 py-3">Date</th>
            </tr>
          </thead>
          <tbody>
            {items.map((job) => (
              <tr
                key={job.id}
                onClick={() => navigate(`/search-results/${job.id}`)}
                className="border-b border-neutral-50 hover:bg-neutral-50 cursor-pointer transition-colors"
              >
                <td className="px-4 py-3">
                  <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', statusColors[job.status] || 'bg-gray-100 text-gray-700')}>
                    {job.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-neutral-900 font-medium">
                  {job.project_name || '-'}
                </td>
                <td className="px-4 py-3 text-sm text-neutral-600">
                  {job.search_engine === 'yandex_api' ? 'Yandex' : 'Google'}
                </td>
                <td className="px-4 py-3 text-sm text-neutral-600 text-right">
                  {job.queries_completed}/{job.queries_total}
                </td>
                <td className="px-4 py-3 text-sm text-neutral-600 text-right">
                  {job.domains_found}
                  {job.domains_new > 0 && <span className="text-green-600 ml-1">(+{job.domains_new})</span>}
                </td>
                <td className="px-4 py-3 text-sm text-right">
                  <span className={job.targets_found > 0 ? 'text-green-700 font-medium' : 'text-neutral-400'}>
                    {job.targets_found}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-neutral-600 text-right">
                  {job.results_total}
                </td>
                <td className="px-4 py-3 text-sm text-neutral-500">
                  {job.created_at ? new Date(job.created_at).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'}
                </td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-12 text-center text-neutral-400">
                  No search jobs found. Run a project search from the Data Search page.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 20 && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1.5 text-sm rounded-lg border border-neutral-200 disabled:opacity-40 hover:bg-neutral-50"
          >
            Previous
          </button>
          <span className="px-3 py-1.5 text-sm text-neutral-500">
            Page {page} of {Math.ceil(total / 20)}
          </span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={page >= Math.ceil(total / 20)}
            className="px-3 py-1.5 text-sm rounded-lg border border-neutral-200 disabled:opacity-40 hover:bg-neutral-50"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

// ============ Job Detail View (virtualized) ============

const RESULTS_PAGE_SIZE = 100;
const QUERIES_PAGE_SIZE = 100;

function JobDetailView({ jobId }: { jobId: number }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<SearchJobFullDetail | null>(null);
  const [tab, setTab] = useState<'results' | 'queries'>('results');
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [exportingSheet, setExportingSheet] = useState(false);
  const [downloadingCsv, setDownloadingCsv] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);

  // Results page cache
  const [resultPages, setResultPages] = useState<Map<number, SearchResultItem[]>>(new Map());
  const [totalResults, setTotalResults] = useState(0);
  const [loadingResultPages, setLoadingResultPages] = useState<Set<number>>(new Set());

  // Queries page cache
  const [queryPages, setQueryPages] = useState<Map<number, QueryItem[]>>(new Map());
  const [totalQueries, setTotalQueries] = useState(0);
  const [loadingQueryPages, setLoadingQueryPages] = useState<Set<number>>(new Set());

  // Domain campaigns — loaded progressively
  const [domainCampaigns, setDomainCampaigns] = useState<DomainCampaignsMap>({});
  const campaignFetchedRef = useRef<Set<string>>(new Set());
  const campaignTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Virtual scroll refs
  const resultsParentRef = useRef<HTMLDivElement>(null);
  const queriesParentRef = useRef<HTMLDivElement>(null);

  // Resolve a result by absolute index from page cache
  const getResultByIndex = useCallback((index: number): SearchResultItem | null => {
    const pageNum = Math.floor(index / RESULTS_PAGE_SIZE) + 1;
    const pageItems = resultPages.get(pageNum);
    if (!pageItems) return null;
    return pageItems[index % RESULTS_PAGE_SIZE] ?? null;
  }, [resultPages]);

  // Resolve a query by absolute index from page cache
  const getQueryByIndex = useCallback((index: number): QueryItem | null => {
    const pageNum = Math.floor(index / QUERIES_PAGE_SIZE) + 1;
    const pageItems = queryPages.get(pageNum);
    if (!pageItems) return null;
    return pageItems[index % QUERIES_PAGE_SIZE] ?? null;
  }, [queryPages]);

  // Fetch a results page if not cached
  const fetchResultPage = useCallback(async (pageNum: number, projectId: number) => {
    if (resultPages.has(pageNum) || loadingResultPages.has(pageNum)) return;
    setLoadingResultPages(prev => new Set(prev).add(pageNum));
    try {
      const data = await projectSearchApi.getProjectResults(projectId, {
        jobId: jobId,
        page: pageNum,
        pageSize: RESULTS_PAGE_SIZE,
      });
      setResultPages(prev => new Map(prev).set(pageNum, data.items));
      setTotalResults(data.total);
    } catch (err) {
      console.error(`Failed to load results page ${pageNum}:`, err);
    } finally {
      setLoadingResultPages(prev => {
        const s = new Set(prev);
        s.delete(pageNum);
        return s;
      });
    }
  }, [resultPages, loadingResultPages, jobId]);

  // Fetch a queries page if not cached
  const fetchQueryPage = useCallback(async (pageNum: number) => {
    if (queryPages.has(pageNum) || loadingQueryPages.has(pageNum)) return;
    setLoadingQueryPages(prev => new Set(prev).add(pageNum));
    try {
      const data = await projectSearchApi.getJobQueries(jobId, pageNum, QUERIES_PAGE_SIZE);
      setQueryPages(prev => new Map(prev).set(pageNum, data.items));
      setTotalQueries(data.total);
    } catch (err) {
      console.error(`Failed to load queries page ${pageNum}:`, err);
    } finally {
      setLoadingQueryPages(prev => {
        const s = new Set(prev);
        s.delete(pageNum);
        return s;
      });
    }
  }, [queryPages, loadingQueryPages, jobId]);

  // Results virtualizer
  const resultsVirtualizer = useVirtualizer({
    count: totalResults,
    getScrollElement: () => resultsParentRef.current,
    estimateSize: () => 44,
    overscan: 20,
  });

  // Queries virtualizer
  const queriesVirtualizer = useVirtualizer({
    count: totalQueries,
    getScrollElement: () => queriesParentRef.current,
    estimateSize: () => 40,
    overscan: 20,
  });

  // Load job + stats + first page on mount
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      setResultPages(new Map());
      setQueryPages(new Map());
      setDomainCampaigns({});
      campaignFetchedRef.current = new Set();
      try {
        // Parallel: job full + stats (if project-based we'll get stats)
        const jobData = await projectSearchApi.getJobFull(jobId);
        if (cancelled) return;
        setJob(jobData);

        // Load first page of results and queries in parallel
        const promises: Promise<void>[] = [];
        if (jobData.project_id) {
          promises.push(
            projectSearchApi.getProjectResults(jobData.project_id, {
              jobId: jobId,
              page: 1,
              pageSize: RESULTS_PAGE_SIZE,
            }).then(data => {
              if (cancelled) return;
              setResultPages(new Map([[1, data.items]]));
              setTotalResults(data.total);
            })
          );
          promises.push(
            projectSearchApi.getProjectResultsStats(jobData.project_id, jobId).then(stats => {
              if (cancelled) return;
              setTotalResults(stats.total);
            })
          );
        }
        promises.push(
          projectSearchApi.getJobQueries(jobId, 1, QUERIES_PAGE_SIZE).then(data => {
            if (cancelled) return;
            setQueryPages(new Map([[1, data.items]]));
            setTotalQueries(data.total);
          })
        );
        await Promise.all(promises);
      } catch (err: any) {
        if (!cancelled) setError(err.userMessage || 'Failed to load job details');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [jobId]);

  // Fetch results pages for visible virtual items
  useEffect(() => {
    if (!job?.project_id || totalResults === 0) return;
    const visibleItems = resultsVirtualizer.getVirtualItems();
    if (visibleItems.length === 0) return;

    const neededPages = new Set<number>();
    for (const item of visibleItems) {
      neededPages.add(Math.floor(item.index / RESULTS_PAGE_SIZE) + 1);
    }
    for (const pageNum of neededPages) {
      fetchResultPage(pageNum, job.project_id);
    }
  }, [resultsVirtualizer.getVirtualItems(), job?.project_id, totalResults, fetchResultPage]);

  // Fetch query pages for visible virtual items
  useEffect(() => {
    if (totalQueries === 0) return;
    const visibleItems = queriesVirtualizer.getVirtualItems();
    if (visibleItems.length === 0) return;

    const neededPages = new Set<number>();
    for (const item of visibleItems) {
      neededPages.add(Math.floor(item.index / QUERIES_PAGE_SIZE) + 1);
    }
    for (const pageNum of neededPages) {
      fetchQueryPage(pageNum);
    }
  }, [queriesVirtualizer.getVirtualItems(), totalQueries, fetchQueryPage]);

  // Viewport-driven domain campaign loading (debounced 200ms)
  useEffect(() => {
    if (tab !== 'results' || totalResults === 0) return;
    if (campaignTimerRef.current) clearTimeout(campaignTimerRef.current);

    campaignTimerRef.current = setTimeout(() => {
      const visibleItems = resultsVirtualizer.getVirtualItems();
      const domainsToFetch: string[] = [];

      for (const vItem of visibleItems) {
        const r = getResultByIndex(vItem.index);
        if (!r?.domain) continue;
        const d = r.domain.toLowerCase();
        if (!campaignFetchedRef.current.has(d)) {
          domainsToFetch.push(d);
          campaignFetchedRef.current.add(d);
        }
      }

      if (domainsToFetch.length > 0) {
        projectSearchApi.getDomainCampaigns(domainsToFetch).then(campaigns => {
          setDomainCampaigns(prev => ({ ...prev, ...campaigns }));
        }).catch(err => {
          console.error('Failed to load domain campaigns:', err);
          // Remove from fetched so they can be retried
          for (const d of domainsToFetch) campaignFetchedRef.current.delete(d);
        });
      }
    }, 200);

    return () => {
      if (campaignTimerRef.current) clearTimeout(campaignTimerRef.current);
    };
  }, [resultsVirtualizer.getVirtualItems(), tab, totalResults, getResultByIndex]);

  // Recalculate virtual sizes when expanded rows change
  useEffect(() => {
    resultsVirtualizer.measure();
  }, [expandedRows]);

  const handleExportSheet = async (options?: { targets_only?: boolean; exclude_contacted?: boolean }) => {
    if (!job?.project_id) return;
    setExportingSheet(true);
    setShowExportMenu(false);
    try {
      const { sheet_url } = await projectSearchApi.exportToGoogleSheet(job.project_id, options);
      window.open(sheet_url, '_blank');
    } catch (err: any) {
      alert(err.userMessage || 'Export failed');
    } finally {
      setExportingSheet(false);
    }
  };

  const handleDownloadCsv = async () => {
    setDownloadingCsv(true);
    try {
      const blob = await projectSearchApi.downloadJobCsv(jobId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `search_job_${jobId}_results.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(err.userMessage || 'Download failed');
    } finally {
      setDownloadingCsv(false);
    }
  };

  const toggleRow = (id: number) => {
    setExpandedRows(prev => {
      const s = new Set(prev);
      s.has(id) ? s.delete(id) : s.add(id);
      return s;
    });
  };

  if (loading && !job) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <Loader2 className="w-6 h-6 animate-spin text-neutral-400" />
      </div>
    );
  }

  if (error && !job) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 flex items-center gap-2">
          <AlertCircle className="w-5 h-5" /> {error}
        </div>
      </div>
    );
  }

  if (!job) return null;

  const duration = job.started_at && job.completed_at
    ? Math.round((new Date(job.completed_at).getTime() - new Date(job.started_at).getTime()) / 1000)
    : null;

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
      {/* Back + Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/search-results')} className="p-1.5 hover:bg-neutral-100 rounded-lg transition-colors">
          <ArrowLeft className="w-5 h-5 text-neutral-600" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-neutral-900">Job #{job.id}</h1>
            <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', statusColors[job.status] || 'bg-gray-100 text-gray-700')}>
              {job.status}
            </span>
          </div>
          <p className="text-neutral-500 text-sm mt-0.5">
            {job.project_name && <span className="font-medium text-neutral-700">{job.project_name}</span>}
            {job.created_at && <span> &middot; {new Date(job.created_at).toLocaleString('ru-RU')}</span>}
            {duration && <span> &middot; {formatDuration(duration)}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <button
              onClick={() => setShowExportMenu(v => !v)}
              disabled={exportingSheet || !job.project_id}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-neutral-200 hover:bg-neutral-50 disabled:opacity-40"
            >
              {exportingSheet ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileSpreadsheet className="w-4 h-4" />}
              Google Sheet
              <ChevronDown className="w-3 h-3" />
            </button>
            {showExportMenu && (
              <div className="absolute right-0 top-full mt-1 w-56 bg-white rounded-lg shadow-lg border border-neutral-200 py-1 z-50">
                <button onClick={() => handleExportSheet()} className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50">
                  All Results
                </button>
                <button onClick={() => handleExportSheet({ targets_only: true })} className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50">
                  <span className="flex items-center gap-2"><Target className="w-3.5 h-3.5 text-green-600" /> Targets Only</span>
                </button>
                <button onClick={() => handleExportSheet({ targets_only: true, exclude_contacted: true })} className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 font-medium text-green-700">
                  <span className="flex items-center gap-2"><Target className="w-3.5 h-3.5" /> Fresh Targets (no overlap)</span>
                </button>
              </div>
            )}
          </div>
          <button
            onClick={handleDownloadCsv}
            disabled={downloadingCsv}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-neutral-200 hover:bg-neutral-50 disabled:opacity-40"
          >
            {downloadingCsv ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            CSV
          </button>
        </div>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-6 gap-3">
        <MiniStat label="Queries" value={`${job.queries_completed}/${job.queries_total}`} />
        <MiniStat label="Domains Found" value={job.domains_found} />
        <MiniStat label="New Domains" value={job.domains_new} color="green" />
        <MiniStat label="Targets" value={job.targets_found} color="green" />
        <MiniStat label="Analyzed" value={job.results_total} />
        <MiniStat label="Avg Confidence" value={job.avg_confidence ? `${(job.avg_confidence * 100).toFixed(0)}%` : '-'} />
      </div>

      {/* Spending panel */}
      <div className="bg-white rounded-xl border border-neutral-200 p-4">
        <h3 className="text-sm font-medium text-neutral-700 mb-3 flex items-center gap-2">
          <DollarSign className="w-4 h-4" /> Resource Spending
        </h3>
        <div className="grid grid-cols-4 gap-6">
          <div>
            <div className="text-xs text-neutral-500">Yandex API</div>
            <div className="text-lg font-semibold text-neutral-900">${job.yandex_cost.toFixed(4)}</div>
            <div className="text-xs text-neutral-400">{(job.queries_total || 0) * 3} requests</div>
          </div>
          <div>
            <div className="text-xs text-neutral-500">OpenAI (GPT-4o-mini)</div>
            <div className="text-lg font-semibold text-neutral-900">${job.openai_cost_estimate.toFixed(4)}</div>
            <div className="text-xs text-neutral-400">{(job.openai_tokens_used || 0).toLocaleString()} tokens</div>
          </div>
          <div>
            <div className="text-xs text-neutral-500">Crona (Scraping)</div>
            <div className="text-lg font-semibold text-neutral-900">${(job.crona_cost || 0).toFixed(4)}</div>
            <div className="text-xs text-neutral-400">{(job.crona_credits_used || 0).toLocaleString()} credits</div>
          </div>
          <div>
            <div className="text-xs text-neutral-500">Total Estimate</div>
            <div className="text-lg font-bold text-neutral-900">${job.total_cost_estimate.toFixed(4)}</div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-neutral-200">
        <button
          onClick={() => setTab('results')}
          className={cn(
            'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
            tab === 'results' ? 'border-black text-neutral-900' : 'border-transparent text-neutral-500 hover:text-neutral-700'
          )}
        >
          Results ({totalResults.toLocaleString()})
        </button>
        <button
          onClick={() => setTab('queries')}
          className={cn(
            'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
            tab === 'queries' ? 'border-black text-neutral-900' : 'border-transparent text-neutral-500 hover:text-neutral-700'
          )}
        >
          Queries ({totalQueries.toLocaleString()})
        </button>
      </div>

      {/* Results tab — virtual scroll */}
      {tab === 'results' && (
        <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
          {/* Fixed header */}
          <table className="w-full">
            <thead>
              <tr className="border-b border-neutral-100 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                <th className="px-4 py-3 w-8"></th>
                <th className="px-4 py-3">Domain</th>
                <th className="px-4 py-3">Company</th>
                <th className="px-4 py-3 text-center">Target</th>
                <th className="px-4 py-3 text-right">Confidence</th>
                <th className="px-4 py-3">Outreach</th>
                <th className="px-4 py-3">Industry</th>
                <th className="px-4 py-3">Source Query</th>
              </tr>
            </thead>
          </table>
          {/* Scrollable virtual body */}
          <div
            ref={resultsParentRef}
            className="overflow-auto"
            style={{ maxHeight: 'calc(100vh - 480px)', minHeight: '300px' }}
          >
            <div style={{ height: `${resultsVirtualizer.getTotalSize()}px`, width: '100%', position: 'relative' }}>
              {resultsVirtualizer.getVirtualItems().map((virtualRow) => {
                const r = getResultByIndex(virtualRow.index);
                if (!r) {
                  // Skeleton row
                  return (
                    <div
                      key={`skeleton-${virtualRow.index}`}
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: '44px',
                        transform: `translateY(${virtualRow.start}px)`,
                      }}
                      className="flex items-center px-4 border-b border-neutral-50"
                    >
                      <div className="w-full flex gap-4">
                        <div className="h-3 w-6 bg-neutral-100 rounded animate-pulse" />
                        <div className="h-3 w-32 bg-neutral-100 rounded animate-pulse" />
                        <div className="h-3 w-24 bg-neutral-100 rounded animate-pulse" />
                        <div className="h-3 w-8 bg-neutral-100 rounded animate-pulse" />
                        <div className="h-3 w-12 bg-neutral-100 rounded animate-pulse" />
                      </div>
                    </div>
                  );
                }

                const isExpanded = expandedRows.has(r.id);
                const info = r.company_info || {};
                const campaign = domainCampaigns[r.domain?.toLowerCase()];

                return (
                  <div
                    key={r.id}
                    data-index={virtualRow.index}
                    ref={resultsVirtualizer.measureElement}
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                  >
                    {/* Main row */}
                    <div
                      onClick={() => toggleRow(r.id)}
                      className={cn(
                        'flex items-center border-b border-neutral-50 cursor-pointer transition-colors',
                        r.is_target ? 'bg-green-50/50 hover:bg-green-50' : 'hover:bg-neutral-50'
                      )}
                      style={{ minHeight: '44px' }}
                    >
                      <div className="px-4 py-2.5 w-8 flex-shrink-0">
                        {isExpanded ? <ChevronDown className="w-4 h-4 text-neutral-400" /> : <ChevronRight className="w-4 h-4 text-neutral-400" />}
                      </div>
                      <div className="px-4 py-2.5 flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-neutral-900 truncate">{r.domain}</span>
                          {r.url && (
                            <a href={r.url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}>
                              <ExternalLink className="w-3.5 h-3.5 text-neutral-400 hover:text-blue-500 flex-shrink-0" />
                            </a>
                          )}
                        </div>
                      </div>
                      <div className="px-4 py-2.5 w-[140px] flex-shrink-0 text-sm text-neutral-600 truncate">{info.name || '-'}</div>
                      <div className="px-4 py-2.5 w-[70px] flex-shrink-0 text-center">
                        {r.is_target ? (
                          <CheckCircle2 className="w-4 h-4 text-green-600 mx-auto" />
                        ) : (
                          <XCircle className="w-4 h-4 text-neutral-300 mx-auto" />
                        )}
                      </div>
                      <div className="px-4 py-2.5 w-[90px] flex-shrink-0 text-sm text-right">
                        <span className={cn(
                          'font-medium',
                          (r.confidence || 0) >= 0.8 ? 'text-green-700' :
                          (r.confidence || 0) >= 0.5 ? 'text-yellow-700' : 'text-neutral-400'
                        )}>
                          {r.confidence ? `${(r.confidence * 100).toFixed(0)}%` : '-'}
                        </span>
                      </div>
                      <div className="px-4 py-2.5 w-[200px] flex-shrink-0">
                        {campaign ? (
                          <CampaignBadge campaign={campaign} />
                        ) : (
                          <span className="text-xs text-neutral-300">-</span>
                        )}
                      </div>
                      <div className="px-4 py-2.5 w-[120px] flex-shrink-0 text-sm text-neutral-500 truncate">{info.industry || '-'}</div>
                      <div className="px-4 py-2.5 w-[200px] flex-shrink-0 text-sm text-neutral-400 truncate" title={r.source_query_text || ''}>
                        {r.source_query_text
                          ? (r.source_query_text.length > 50 ? r.source_query_text.slice(0, 48) + '...' : r.source_query_text)
                          : '-'}
                      </div>
                    </div>
                    {/* Expanded detail */}
                    {isExpanded && (
                      <div className="border-b border-neutral-100 bg-neutral-50/50 px-8 py-4">
                        <div className="space-y-3 text-sm">
                          {r.reasoning && (
                            <div><span className="font-medium text-neutral-700">Reasoning:</span> <span className="text-neutral-600">{r.reasoning}</span></div>
                          )}
                          {info.description && (
                            <div><span className="font-medium text-neutral-700">Description:</span> <span className="text-neutral-600">{info.description}</span></div>
                          )}
                          {info.services && info.services.length > 0 && (
                            <div>
                              <span className="font-medium text-neutral-700">Services:</span>{' '}
                              {info.services.map((s, i) => (
                                <span key={i} className="inline-block px-2 py-0.5 bg-neutral-100 rounded text-xs mr-1 mb-1">{s}</span>
                              ))}
                            </div>
                          )}
                          {info.location && (
                            <div><span className="font-medium text-neutral-700">Location:</span> <span className="text-neutral-600">{info.location}</span></div>
                          )}
                          {r.source_query_text && (
                            <div><span className="font-medium text-neutral-700">Source Query:</span> <span className="text-neutral-600 italic">{r.source_query_text}</span></div>
                          )}
                          {campaign && <OutreachDetail campaign={campaign} />}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            {totalResults === 0 && !loading && (
              <div className="px-4 py-12 text-center text-neutral-400">
                No results yet
              </div>
            )}
          </div>
        </div>
      )}

      {/* Queries tab — virtual scroll */}
      {tab === 'queries' && (
        <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-neutral-100 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                <th className="px-4 py-3">Query</th>
                <th className="px-4 py-3 text-center w-[100px]">Status</th>
                <th className="px-4 py-3 text-right w-[120px]">Domains Found</th>
              </tr>
            </thead>
          </table>
          <div
            ref={queriesParentRef}
            className="overflow-auto"
            style={{ maxHeight: 'calc(100vh - 480px)', minHeight: '300px' }}
          >
            <div style={{ height: `${queriesVirtualizer.getTotalSize()}px`, width: '100%', position: 'relative' }}>
              {queriesVirtualizer.getVirtualItems().map((virtualRow) => {
                const q = getQueryByIndex(virtualRow.index);
                if (!q) {
                  return (
                    <div
                      key={`qskel-${virtualRow.index}`}
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: '40px',
                        transform: `translateY(${virtualRow.start}px)`,
                      }}
                      className="flex items-center px-4 border-b border-neutral-50"
                    >
                      <div className="h-3 w-64 bg-neutral-100 rounded animate-pulse" />
                    </div>
                  );
                }
                return (
                  <div
                    key={q.id}
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      height: '40px',
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                    className="flex items-center border-b border-neutral-50"
                  >
                    <div className="px-4 py-2.5 flex-1 text-sm text-neutral-900 truncate">{q.query_text}</div>
                    <div className="px-4 py-2.5 w-[100px] text-center">
                      <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', statusColors[q.status] || 'bg-gray-100 text-gray-700')}>
                        {q.status}
                      </span>
                    </div>
                    <div className="px-4 py-2.5 w-[120px] text-sm text-neutral-600 text-right">{q.domains_found}</div>
                  </div>
                );
              })}
            </div>
            {totalQueries === 0 && !loading && (
              <div className="px-4 py-12 text-center text-neutral-400">
                No queries
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ============ Campaign Badge + Outreach Detail ============

function CampaignBadge({ campaign }: { campaign: DomainCampaignInfo }) {
  const mainCampaign = campaign.campaigns[0];
  const label = mainCampaign?.name
    ? (mainCampaign.name.length > 20 ? mainCampaign.name.slice(0, 18) + '...' : mainCampaign.name)
    : 'Contacted';
  const isEmailMatch = campaign.match_type === 'email_domain';

  return (
    <span className={cn(
      'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium max-w-[200px] truncate',
      campaign.has_replies
        ? 'bg-green-100 text-green-700 ring-1 ring-green-300 animate-pulse'
        : 'bg-orange-100 text-orange-700'
    )}>
      {isEmailMatch
        ? <Mail className="w-3 h-3 flex-shrink-0" />
        : <Globe className="w-3 h-3 flex-shrink-0" />
      }
      <span className="truncate">{label}</span>
      {campaign.contacts_count > 1 && (
        <span className="text-[10px] opacity-70">({campaign.contacts_count})</span>
      )}
      <span className={cn(
        'px-1 py-px rounded text-[9px] font-bold uppercase flex-shrink-0',
        isEmailMatch ? 'bg-orange-200/60 text-orange-800' : 'bg-blue-200/60 text-blue-800'
      )}>
        {isEmailMatch ? '@' : 'www'}
      </span>
    </span>
  );
}

function OutreachDetail({ campaign }: { campaign: DomainCampaignInfo }) {
  const isEmailMatch = campaign.match_type === 'email_domain';

  return (
    <div className={cn(
      'mt-2 p-3 border rounded-lg',
      isEmailMatch ? 'bg-orange-50/50 border-orange-100' : 'bg-blue-50/50 border-blue-100'
    )}>
      <div className="flex items-center gap-2 mb-2">
        <MessageSquare className="w-4 h-4 text-orange-600" />
        <span className="font-medium text-neutral-700">Outreach Status</span>
        <span className={cn(
          'px-1.5 py-0.5 rounded text-[10px] font-semibold',
          isEmailMatch ? 'bg-orange-100 text-orange-700' : 'bg-blue-100 text-blue-700'
        )}>
          {isEmailMatch ? '@ email domain match' : 'www website domain match'}
        </span>
        {campaign.has_replies && (
          <span className="px-1.5 py-0.5 bg-green-100 text-green-700 rounded text-[10px] font-semibold">HAS REPLIES</span>
        )}
      </div>

      {/* Campaigns */}
      <div className="flex flex-wrap gap-1.5 mb-2">
        {campaign.campaigns.map((c, i) => (
          <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 bg-white border border-neutral-200 rounded text-xs">
            {c.source === 'getsales' ? 'LI' : <Mail className="w-3 h-3" />}
            <span className="font-medium">{c.name}</span>
            {c.status && <span className="text-neutral-400">{c.status}</span>}
          </span>
        ))}
      </div>

      {/* First contacted */}
      {campaign.first_contacted_at && (
        <div className="text-xs text-neutral-500 mb-2">
          First contacted: {new Date(campaign.first_contacted_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
        </div>
      )}

      {/* Contact list */}
      <div className="space-y-1">
        {campaign.contacts.map((c) => (
          <div key={c.id} className="flex items-center gap-2 text-xs">
            <Link
              to={`/contacts/${c.id}`}
              onClick={(e) => e.stopPropagation()}
              className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
            >
              {c.name || c.email || `Contact #${c.id}`}
            </Link>
            {c.email && <span className="text-neutral-400">{c.email}</span>}
            {c.match_type && (
              <span className={cn(
                'px-1 py-px rounded text-[9px] font-bold',
                c.match_type === 'email_domain' ? 'bg-orange-100 text-orange-600' : 'bg-blue-100 text-blue-600'
              )}>
                {c.match_type === 'email_domain' ? '@' : 'www'}
              </span>
            )}
            <span className={cn(
              'px-1.5 py-0.5 rounded text-[10px] font-medium',
              c.has_replied ? 'bg-green-100 text-green-700' : 'bg-neutral-100 text-neutral-500'
            )}>
              {c.has_replied ? 'replied' : c.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============ Helper Components ============

function StatCard({ icon: Icon, label, value, color }: { icon: any; label: string; value: number | string; color?: string }) {
  return (
    <div className="bg-white rounded-xl border border-neutral-200 p-4">
      <div className="flex items-center gap-2 mb-1">
        <Icon className={cn('w-4 h-4', color === 'green' ? 'text-green-600' : 'text-neutral-400')} />
        <span className="text-xs text-neutral-500">{label}</span>
      </div>
      <div className={cn('text-2xl font-bold', color === 'green' ? 'text-green-700' : 'text-neutral-900')}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
    </div>
  );
}

function MiniStat({ label, value, color }: { label: string; value: number | string; color?: string }) {
  return (
    <div className="bg-white rounded-lg border border-neutral-200 p-3">
      <div className="text-xs text-neutral-500 mb-0.5">{label}</div>
      <div className={cn('text-lg font-semibold', color === 'green' ? 'text-green-700' : 'text-neutral-900')}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
    </div>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins < 60) return `${mins}m ${secs}s`;
  const hours = Math.floor(mins / 60);
  return `${hours}h ${mins % 60}m`;
}
