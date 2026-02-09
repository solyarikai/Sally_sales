import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Target, Search, Download, FileSpreadsheet, ArrowLeft,
  Loader2, AlertCircle, Clock, CheckCircle2, XCircle,
  ChevronDown, ChevronRight, ExternalLink, DollarSign,
  BarChart3, Globe, Zap,
} from 'lucide-react';
import { cn } from '../lib/utils';
import {
  projectSearchApi,
  type SearchJobFullDetail,
  type SearchHistoryItem,
  type SearchResultItem,
  type SearchQueryResponse,
} from '../api/dataSearch';

// Extend SearchQueryResponse if not exported
interface QueryItem {
  id: number;
  query_text: string;
  status: string;
  domains_found: number;
  pages_scraped?: number;
}

const statusColors: Record<string, string> = {
  completed: 'bg-green-100 text-green-800',
  running: 'bg-blue-100 text-blue-800',
  pending: 'bg-yellow-100 text-yellow-800',
  failed: 'bg-red-100 text-red-800',
  cancelled: 'bg-gray-100 text-gray-800',
};

export function SearchResultsPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();

  if (jobId) {
    return <JobDetailView jobId={parseInt(jobId)} />;
  }

  return <JobHistoryView />;
}

// ============ Job History List View ============

function JobHistoryView() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<{ items: SearchHistoryItem[]; total: number } | null>(null);
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
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
  }, [page]);

  useEffect(() => { load(); }, [load]);

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

// ============ Job Detail View ============

function JobDetailView({ jobId }: { jobId: number }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<SearchJobFullDetail | null>(null);
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [queries, setQueries] = useState<QueryItem[]>([]);
  const [tab, setTab] = useState<'results' | 'queries'>('results');
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [exportingSheet, setExportingSheet] = useState(false);
  const [downloadingCsv, setDownloadingCsv] = useState(false);

  useEffect(() => {
    loadJob();
  }, [jobId]);

  const loadJob = async () => {
    setLoading(true);
    setError(null);
    try {
      const [jobData, jobDetail] = await Promise.all([
        projectSearchApi.getJobFull(jobId),
        projectSearchApi.getSearchJobStatus(jobId),
      ]);
      setJob(jobData);
      setQueries(jobDetail.queries || []);

      // Load results if project-based
      if (jobData.project_id) {
        const resultData = await projectSearchApi.getProjectResults(jobData.project_id);
        // Filter to only this job's results
        const jobResults = resultData.filter(r => r.search_job_id === jobId);
        setResults(jobResults.length > 0 ? jobResults : resultData);
      }
    } catch (err: any) {
      setError(err.userMessage || 'Failed to load job details');
    } finally {
      setLoading(false);
    }
  };

  const handleExportSheet = async () => {
    if (!job?.project_id) return;
    setExportingSheet(true);
    try {
      const { sheet_url } = await projectSearchApi.exportToGoogleSheet(job.project_id);
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
          <button
            onClick={handleExportSheet}
            disabled={exportingSheet || !job.project_id}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg border border-neutral-200 hover:bg-neutral-50 disabled:opacity-40"
          >
            {exportingSheet ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileSpreadsheet className="w-4 h-4" />}
            Google Sheet
          </button>
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
        <div className="grid grid-cols-3 gap-6">
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
          Results ({results.length})
        </button>
        <button
          onClick={() => setTab('queries')}
          className={cn(
            'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
            tab === 'queries' ? 'border-black text-neutral-900' : 'border-transparent text-neutral-500 hover:text-neutral-700'
          )}
        >
          Queries ({queries.length})
        </button>
      </div>

      {/* Tab content */}
      {tab === 'results' && (
        <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-neutral-100 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                <th className="px-4 py-3 w-8"></th>
                <th className="px-4 py-3">Domain</th>
                <th className="px-4 py-3">Company</th>
                <th className="px-4 py-3 text-center">Target</th>
                <th className="px-4 py-3 text-right">Confidence</th>
                <th className="px-4 py-3">Industry</th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => {
                const isExpanded = expandedRows.has(r.id);
                const info = r.company_info || {};
                return (
                  <>
                    <tr
                      key={r.id}
                      onClick={() => toggleRow(r.id)}
                      className={cn(
                        'border-b border-neutral-50 cursor-pointer transition-colors',
                        r.is_target ? 'bg-green-50/50 hover:bg-green-50' : 'hover:bg-neutral-50'
                      )}
                    >
                      <td className="px-4 py-2.5">
                        {isExpanded ? <ChevronDown className="w-4 h-4 text-neutral-400" /> : <ChevronRight className="w-4 h-4 text-neutral-400" />}
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-neutral-900">{r.domain}</span>
                          {r.url && (
                            <a href={r.url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}>
                              <ExternalLink className="w-3.5 h-3.5 text-neutral-400 hover:text-blue-500" />
                            </a>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-sm text-neutral-600">{info.name || '-'}</td>
                      <td className="px-4 py-2.5 text-center">
                        {r.is_target ? (
                          <CheckCircle2 className="w-4 h-4 text-green-600 mx-auto" />
                        ) : (
                          <XCircle className="w-4 h-4 text-neutral-300 mx-auto" />
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-sm text-right">
                        <span className={cn(
                          'font-medium',
                          (r.confidence || 0) >= 0.8 ? 'text-green-700' :
                          (r.confidence || 0) >= 0.5 ? 'text-yellow-700' : 'text-neutral-400'
                        )}>
                          {r.confidence ? `${(r.confidence * 100).toFixed(0)}%` : '-'}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-sm text-neutral-500">{info.industry || '-'}</td>
                    </tr>
                    {isExpanded && (
                      <tr key={`${r.id}-detail`} className="border-b border-neutral-100 bg-neutral-50/50">
                        <td colSpan={6} className="px-8 py-4">
                          <div className="space-y-2 text-sm">
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
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
              {results.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-neutral-400">
                    No results yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'queries' && (
        <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-neutral-100 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                <th className="px-4 py-3">Query</th>
                <th className="px-4 py-3 text-center">Status</th>
                <th className="px-4 py-3 text-right">Domains Found</th>
              </tr>
            </thead>
            <tbody>
              {queries.map((q) => (
                <tr key={q.id} className="border-b border-neutral-50">
                  <td className="px-4 py-2.5 text-sm text-neutral-900">{q.query_text}</td>
                  <td className="px-4 py-2.5 text-center">
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', statusColors[q.status] || 'bg-gray-100 text-gray-700')}>
                      {q.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-sm text-neutral-600 text-right">{q.domains_found}</td>
                </tr>
              ))}
              {queries.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-4 py-12 text-center text-neutral-400">
                    No queries
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
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
