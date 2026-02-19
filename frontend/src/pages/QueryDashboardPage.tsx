import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import type { ColDef, GridReadyEvent, SortChangedEvent } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import { Search, RefreshCw, X, Loader2, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight, ChevronDown, ChevronUp } from 'lucide-react';
import { useToast } from '../components/Toast';
import { cn, formatNumber, getErrorMessage } from '../lib/utils';
import { useAppStore } from '../store/appStore';
import { contactsApi } from '../api/contacts';
import { queryDashboardApi } from '../api/queryDashboard';
import type { QueryRecord, QuerySummaryResponse, FilterOptionsResponse, GeoHierarchyResponse, SegmentSaturation } from '../api/queryDashboard';
import { QueryDashboardFilterContext } from '../components/filters/QueryDashboardFilterContext';
import type { QueryDashboardFilterState } from '../components/filters/QueryDashboardFilterContext';
import { QuerySegmentColumnFilter } from '../components/filters/QuerySegmentColumnFilter';
import { QueryGeoColumnFilter } from '../components/filters/QueryGeoColumnFilter';
import { QuerySourceColumnFilter } from '../components/filters/QuerySourceColumnFilter';
import { QueryStatusColumnFilter } from '../components/filters/QueryStatusColumnFilter';
import { QueryLanguageColumnFilter } from '../components/filters/QueryLanguageColumnFilter';
import { QuerySaturatedColumnFilter } from '../components/filters/QuerySaturatedColumnFilter';
import { QueryRangeColumnFilter } from '../components/filters/QueryRangeColumnFilter';
import { QueryDateColumnFilter } from '../components/filters/QueryDateColumnFilter';

const AG_GRID_THEME = 'legacy';
ModuleRegistry.registerModules([AllCommunityModule]);

// ── Helpers ──────────────────────────────────────────────────

function parseCommaSeparated(val: string | null): string[] {
  return val ? val.split(',').filter(Boolean) : [];
}

function parseBool(val: string | null): boolean | null {
  if (val === 'true') return true;
  if (val === 'false') return false;
  return null;
}

function parseIntOrNull(val: string | null): number | null {
  if (!val) return null;
  const n = parseInt(val, 10);
  return isNaN(n) ? null : n;
}

// ── StatusBadge ──────────────────────────────────────────────

const STATUS_CONFIG: Record<string, { label: string; dot: string; colors: string }> = {
  pending: { label: 'Pending', dot: 'bg-amber-500', colors: 'bg-amber-100 text-amber-700 border-amber-300' },
  done: { label: 'Done', dot: 'bg-green-500', colors: 'bg-green-100 text-green-700 border-green-300' },
  failed: { label: 'Failed', dot: 'bg-red-500', colors: 'bg-red-100 text-red-600 border-red-300' },
};

// ── Saturation Panel ─────────────────────────────────────────

function SaturationTable({ title, data, onClickRow }: { title: string; data: SegmentSaturation[]; onClickRow: (key: string) => void }) {
  if (data.length === 0) return null;
  return (
    <div className="flex-1 min-w-[300px]">
      <div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-1.5">{title}</div>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-neutral-400">
            <th className="text-left py-1 font-medium">Key</th>
            <th className="text-right py-1 font-medium">Queries</th>
            <th className="text-right py-1 font-medium">Saturated</th>
            <th className="text-right py-1 font-medium">Rate</th>
            <th className="text-right py-1 font-medium">Domains</th>
            <th className="text-right py-1 font-medium">Targets</th>
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr key={row.key} onClick={() => onClickRow(row.key)}
              className="hover:bg-neutral-100 cursor-pointer transition-colors border-t border-neutral-100">
              <td className="py-1.5 font-medium text-neutral-700">{row.key.replace(/_/g, ' ')}</td>
              <td className="py-1.5 text-right text-neutral-600">{formatNumber(row.total)}</td>
              <td className="py-1.5 text-right text-neutral-600">{formatNumber(row.saturated)}</td>
              <td className="py-1.5 text-right">
                <span className={cn('font-medium', row.saturation_rate > 80 ? 'text-red-600' : row.saturation_rate > 50 ? 'text-amber-600' : 'text-green-600')}>
                  {row.saturation_rate.toFixed(1)}%
                </span>
              </td>
              <td className="py-1.5 text-right text-neutral-600">{formatNumber(row.total_domains)}</td>
              <td className="py-1.5 text-right text-neutral-600">{formatNumber(row.total_targets)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────

export function QueryDashboardPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { currentProject, setCurrentProject } = useAppStore();

  // ── Filter state (initialized from URL) ────────────────────
  const [search, setSearch] = useState(searchParams.get('q') || '');
  const [debouncedSearch, setDebouncedSearch] = useState(searchParams.get('q') || '');
  const [segmentFilters, setSegmentFilters] = useState<string[]>(parseCommaSeparated(searchParams.get('segment')));
  const [geoFilters, setGeoFilters] = useState<string[]>(parseCommaSeparated(searchParams.get('geo')));
  const [sourceFilters, setSourceFilters] = useState<string[]>(parseCommaSeparated(searchParams.get('source')));
  const [statusFilters, setStatusFilters] = useState<string[]>(parseCommaSeparated(searchParams.get('status')));
  const [languageFilters, setLanguageFilters] = useState<string[]>(parseCommaSeparated(searchParams.get('language')));
  const [saturatedFilter, setSaturatedFilter] = useState<boolean | null>(parseBool(searchParams.get('is_saturated')));
  const [domainsMin, setDomainsMin] = useState<number | null>(parseIntOrNull(searchParams.get('domains_min')));
  const [domainsMax, setDomainsMax] = useState<number | null>(parseIntOrNull(searchParams.get('domains_max')));
  const [targetsMin, setTargetsMin] = useState<number | null>(parseIntOrNull(searchParams.get('targets_min')));
  const [targetsMax, setTargetsMax] = useState<number | null>(parseIntOrNull(searchParams.get('targets_max')));
  const [dateFrom, setDateFrom] = useState<string | null>(searchParams.get('date_from'));
  const [dateTo, setDateTo] = useState<string | null>(searchParams.get('date_to'));

  // ── Pagination & sorting ───────────────────────────────────
  const [page, setPage] = useState(parseInt(searchParams.get('page') || '1', 10));
  const [pageSize] = useState(50);
  const [sortBy, setSortBy] = useState(searchParams.get('sort_by') || 'created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>((searchParams.get('sort_order') as 'asc' | 'desc') || 'desc');

  // ── Data ───────────────────────────────────────────────────
  const [queries, setQueries] = useState<QueryRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<QuerySummaryResponse | null>(null);
  const [filterOptions, setFilterOptions] = useState<FilterOptionsResponse | null>(null);
  const [geoHierarchy, setGeoHierarchy] = useState<GeoHierarchyResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [showSaturationPanel, setShowSaturationPanel] = useState(false);

  // ── Auto-select project from URL param ────────────────────
  useEffect(() => {
    const urlProjectId = searchParams.get('project_id');
    if (urlProjectId && !currentProject) {
      const pid = parseInt(urlProjectId, 10);
      if (!isNaN(pid)) {
        contactsApi.listProjectsLite().then((projects) => {
          const match = projects.find(p => p.id === pid);
          if (match) setCurrentProject(match as any);
        }).catch(() => {});
      }
    }
  }, [searchParams, currentProject, setCurrentProject]);

  // ── Debounce search ────────────────────────────────────────
  useEffect(() => {
    const timer = setTimeout(() => { setDebouncedSearch(search); setPage(1); }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // ── URL sync ───────────────────────────────────────────────
  const isFirstSync = useRef(true);
  useEffect(() => {
    const params = isFirstSync.current ? new URLSearchParams(searchParams) : new URLSearchParams();
    isFirstSync.current = false;

    const managed: Record<string, string | null> = {
      project_id: currentProject ? String(currentProject.id) : null,
      q: debouncedSearch || null,
      segment: segmentFilters.length ? segmentFilters.join(',') : null,
      geo: geoFilters.length ? geoFilters.join(',') : null,
      source: sourceFilters.length ? sourceFilters.join(',') : null,
      status: statusFilters.length ? statusFilters.join(',') : null,
      language: languageFilters.length ? languageFilters.join(',') : null,
      is_saturated: saturatedFilter !== null ? String(saturatedFilter) : null,
      domains_min: domainsMin !== null ? String(domainsMin) : null,
      domains_max: domainsMax !== null ? String(domainsMax) : null,
      targets_min: targetsMin !== null ? String(targetsMin) : null,
      targets_max: targetsMax !== null ? String(targetsMax) : null,
      date_from: dateFrom,
      date_to: dateTo,
      sort_by: sortBy !== 'created_at' ? sortBy : null,
      sort_order: sortOrder !== 'desc' ? sortOrder : null,
      page: page > 1 ? String(page) : null,
    };

    for (const [key, value] of Object.entries(managed)) {
      if (value) params.set(key, value);
      else params.delete(key);
    }

    setSearchParams(params, { replace: true });
  }, [currentProject, debouncedSearch, segmentFilters, geoFilters, sourceFilters, statusFilters, languageFilters, saturatedFilter, domainsMin, domainsMax, targetsMin, targetsMax, dateFrom, dateTo, sortBy, sortOrder, page]);

  // ── Active project ID ──────────────────────────────────────
  const projectId = currentProject?.id;

  // ── Load filter options + geo hierarchy (once per project) ─
  useEffect(() => {
    if (!projectId) return;
    queryDashboardApi.getFilterOptions(projectId).then(setFilterOptions).catch(() => {});
    queryDashboardApi.getGeoHierarchy().then(setGeoHierarchy).catch(() => {});
  }, [projectId]);

  // ── Build filter params ────────────────────────────────────
  const filterParams = useMemo(() => {
    if (!projectId) return null;
    const p: Record<string, unknown> = { project_id: projectId };
    if (debouncedSearch) p.q = debouncedSearch;
    if (segmentFilters.length) p.segment = segmentFilters.join(',');
    if (geoFilters.length) p.geo = geoFilters.join(',');
    if (sourceFilters.length) p.source = sourceFilters.join(',');
    if (statusFilters.length) p.status = statusFilters.join(',');
    if (languageFilters.length) p.language = languageFilters.join(',');
    if (saturatedFilter !== null) p.is_saturated = saturatedFilter;
    if (domainsMin !== null) p.domains_min = domainsMin;
    if (domainsMax !== null) p.domains_max = domainsMax;
    if (targetsMin !== null) p.targets_min = targetsMin;
    if (targetsMax !== null) p.targets_max = targetsMax;
    if (dateFrom) p.date_from = dateFrom;
    if (dateTo) p.date_to = dateTo;
    return p;
  }, [projectId, debouncedSearch, segmentFilters, geoFilters, sourceFilters, statusFilters, languageFilters, saturatedFilter, domainsMin, domainsMax, targetsMin, targetsMax, dateFrom, dateTo]);

  // ── Load queries ───────────────────────────────────────────
  const loadQueries = useCallback(async () => {
    if (!filterParams) return;
    setIsLoading(true);
    try {
      const response = await queryDashboardApi.listQueries({
        ...(filterParams as any),
        sort_by: sortBy,
        sort_order: sortOrder,
        page,
        page_size: pageSize,
      });
      setQueries(response.data);
      setTotal(response.total);
    } catch (err) {
      console.error('Failed to load queries:', err);
      toast.error('Failed to load queries', getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [filterParams, sortBy, sortOrder, page, pageSize, toast]);

  useEffect(() => { loadQueries(); }, [loadQueries]);

  // ── Load summary ───────────────────────────────────────────
  const loadSummary = useCallback(async () => {
    if (!filterParams) return;
    try {
      const s = await queryDashboardApi.getSummary(filterParams as any);
      setSummary(s);
    } catch (err) {
      console.error('Failed to load summary:', err);
    }
  }, [filterParams]);

  useEffect(() => { loadSummary(); }, [loadSummary]);

  // ── Toggle helpers ─────────────────────────────────────────
  const toggleItem = (arr: string[], item: string) =>
    arr.includes(item) ? arr.filter(x => x !== item) : [...arr, item];

  const resetPage = useCallback(() => setPage(1), []);

  // ── Filter context ─────────────────────────────────────────
  const filterCtx = useMemo<QueryDashboardFilterState>(() => ({
    segmentFilters,
    setSegmentFilters: (v) => { setSegmentFilters(v); setPage(1); },
    toggleSegment: (v) => { setSegmentFilters(prev => toggleItem(prev, v)); setPage(1); },
    geoFilters,
    setGeoFilters: (v) => { setGeoFilters(v); setPage(1); },
    toggleGeo: (v) => { setGeoFilters(prev => toggleItem(prev, v)); setPage(1); },
    sourceFilters,
    setSourceFilters: (v) => { setSourceFilters(v); setPage(1); },
    toggleSource: (v) => { setSourceFilters(prev => toggleItem(prev, v)); setPage(1); },
    statusFilters,
    setStatusFilters: (v) => { setStatusFilters(v); setPage(1); },
    toggleStatus: (v) => { setStatusFilters(prev => toggleItem(prev, v)); setPage(1); },
    languageFilters,
    setLanguageFilters: (v) => { setLanguageFilters(v); setPage(1); },
    toggleLanguage: (v) => { setLanguageFilters(prev => toggleItem(prev, v)); setPage(1); },
    saturatedFilter,
    setSaturatedFilter: (v) => { setSaturatedFilter(v); setPage(1); },
    domainsMin,
    domainsMax,
    setDomainsRange: (min, max) => { setDomainsMin(min); setDomainsMax(max); setPage(1); },
    targetsMin,
    targetsMax,
    setTargetsRange: (min, max) => { setTargetsMin(min); setTargetsMax(max); setPage(1); },
    dateFrom,
    dateTo,
    setDateRange: (from, to) => { setDateFrom(from); setDateTo(to); setPage(1); },
    filterOptions,
    geoHierarchy,
    resetPage,
  }), [segmentFilters, geoFilters, sourceFilters, statusFilters, languageFilters, saturatedFilter, domainsMin, domainsMax, targetsMin, targetsMax, dateFrom, dateTo, filterOptions, geoHierarchy, resetPage]);

  // ── AG Grid sort handler ───────────────────────────────────
  const onSortChanged = useCallback((event: SortChangedEvent) => {
    const sortModel = event.api.getColumnState().find(c => c.sort);
    if (sortModel) {
      setSortBy(sortModel.colId || 'created_at');
      setSortOrder(sortModel.sort as 'asc' | 'desc');
    }
  }, []);

  const onGridReady = useCallback((_params: GridReadyEvent) => {}, []);

  // ── Navigate to CRM contacts with query context ────────────
  const openContactsForQuery = useCallback((row: QueryRecord, _mode: 'domains' | 'targets') => {
    const params = new URLSearchParams();
    if (row.segment) params.set('segment', row.segment);
    if (row.geo) params.set('geo', row.geo);
    // Map search engine to contact source
    const sourceMap: Record<string, string> = {
      google_serp: 'pipeline',
      yandex_api: 'pipeline',
      apollo_org: 'pipeline',
      clay: 'pipeline',
    };
    const contactSource = sourceMap[row.source];
    if (contactSource) params.set('source', contactSource);
    if (currentProject) params.set('project_id', String(currentProject.id));
    navigate(`/contacts?${params.toString()}`);
  }, [navigate, currentProject]);

  // ── Column definitions ─────────────────────────────────────
  const columnDefs = useMemo<ColDef[]>(() => [
    {
      field: 'query_text',
      headerName: 'Query',
      flex: 3,
      minWidth: 250,
      sortable: true,
      cellRenderer: (params: { data: QueryRecord }) => {
        if (!params.data) return null;
        return (
          <span className={cn(params.data.is_saturated && 'line-through text-neutral-400')}>
            {params.data.query_text}
          </span>
        );
      },
    },
    {
      field: 'segment',
      headerName: 'Segment',
      width: 130,
      sortable: false,
      filter: QuerySegmentColumnFilter,
      cellRenderer: (params: { value: string | null }) =>
        params.value ? <span className="text-xs">{params.value.replace(/_/g, ' ')}</span> : <span className="text-neutral-400">—</span>,
    },
    {
      field: 'geo',
      headerName: 'Geo',
      width: 120,
      sortable: false,
      filter: QueryGeoColumnFilter,
      cellRenderer: (params: { value: string | null }) =>
        params.value ? <span className="text-xs">{params.value.replace(/_/g, ' ')}</span> : <span className="text-neutral-400">—</span>,
    },
    {
      field: 'language',
      headerName: 'Lang',
      width: 70,
      sortable: false,
      filter: QueryLanguageColumnFilter,
      cellRenderer: (params: { value: string | null }) =>
        params.value ? <span className="text-xs font-medium uppercase">{params.value}</span> : <span className="text-neutral-400">—</span>,
    },
    {
      field: 'source',
      headerName: 'Source',
      width: 110,
      sortable: false,
      filter: QuerySourceColumnFilter,
      cellRenderer: (params: { value: string }) => {
        const labels: Record<string, string> = { google_serp: 'Google', yandex_api: 'Yandex', apollo_org: 'Apollo', clay: 'Clay' };
        return <span className="text-xs">{labels[params.value] || params.value}</span>;
      },
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 100,
      sortable: false,
      filter: QueryStatusColumnFilter,
      cellRenderer: (params: { value: string }) => {
        const cfg = STATUS_CONFIG[params.value];
        if (!cfg) return <span className="text-xs text-neutral-400">{params.value}</span>;
        return (
          <span className={cn('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border', cfg.colors)}>
            <span className={cn('w-1.5 h-1.5 rounded-full', cfg.dot)} />
            {cfg.label}
          </span>
        );
      },
    },
    {
      field: 'domains_found',
      headerName: 'Domains',
      width: 90,
      sortable: true,
      filter: QueryRangeColumnFilter,
      filterParams: { rangeField: 'domains' },
      cellRenderer: (params: { value: number; data: QueryRecord }) =>
        params.value > 0 ? (
          <button onClick={() => openContactsForQuery(params.data, 'domains')}
            className="text-xs font-medium text-blue-600 hover:text-blue-800 hover:underline cursor-pointer" title="View contacts from these domains">
            {params.value}
          </button>
        ) : <span className="text-xs text-neutral-400">0</span>,
    },
    {
      field: 'targets_found',
      headerName: 'Targets',
      width: 85,
      sortable: true,
      filter: QueryRangeColumnFilter,
      filterParams: { rangeField: 'targets' },
      cellRenderer: (params: { value: number; data: QueryRecord }) =>
        params.value > 0 ? (
          <button onClick={() => openContactsForQuery(params.data, 'targets')}
            className="text-xs font-medium text-green-600 hover:text-green-800 hover:underline cursor-pointer" title="View target contacts">
            {params.value}
          </button>
        ) : <span className="text-xs text-neutral-400">0</span>,
    },
    {
      field: 'effectiveness_score',
      headerName: 'Score',
      width: 75,
      sortable: true,
      cellRenderer: (params: { value: number | null }) =>
        params.value !== null && params.value !== undefined
          ? <span className="text-xs font-medium">{(params.value * 100).toFixed(0)}%</span>
          : <span className="text-neutral-400">—</span>,
    },
    {
      field: 'is_saturated',
      headerName: 'Sat.',
      width: 70,
      sortable: false,
      filter: QuerySaturatedColumnFilter,
      cellRenderer: (params: { value: boolean }) =>
        params.value
          ? <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-gray-200 text-[10px] text-gray-600 font-medium">SAT</span>
          : null,
    },
    {
      field: 'estimated_cost_usd',
      headerName: 'Cost',
      width: 70,
      sortable: false,
      cellRenderer: (params: { value: number }) =>
        <span className="text-xs text-neutral-500">${params.value.toFixed(4)}</span>,
    },
    {
      field: 'created_at',
      headerName: 'Created',
      width: 140,
      sortable: true,
      filter: QueryDateColumnFilter,
      cellRenderer: (params: { value: string | null }) => {
        if (!params.value) return <span className="text-neutral-400">—</span>;
        const d = new Date(params.value);
        return <span className="text-xs text-neutral-500">{d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} {d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}</span>;
      },
    },
    {
      field: 'job_id',
      headerName: 'Job',
      width: 65,
      sortable: false,
      cellRenderer: (params: { value: number }) =>
        <span className="text-xs text-neutral-400">#{params.value}</span>,
    },
  ], []);

  const defaultColDef = useMemo<ColDef>(() => ({
    resizable: true,
    suppressMovable: false,
    floatingFilter: false,
  }), []);

  // ── Row class for saturated ────────────────────────────────
  const getRowClass = useCallback((params: { data: QueryRecord | undefined }) => {
    if (params.data?.is_saturated) return 'bg-neutral-50 opacity-60';
    return '';
  }, []);

  // ── Pagination ─────────────────────────────────────────────
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const hasFilters = segmentFilters.length > 0 || geoFilters.length > 0 || sourceFilters.length > 0
    || statusFilters.length > 0 || languageFilters.length > 0 || saturatedFilter !== null
    || domainsMin !== null || domainsMax !== null || targetsMin !== null || targetsMax !== null
    || dateFrom !== null || dateTo !== null || debouncedSearch !== '';

  const clearAllFilters = () => {
    setSearch(''); setDebouncedSearch('');
    setSegmentFilters([]); setGeoFilters([]); setSourceFilters([]); setStatusFilters([]); setLanguageFilters([]);
    setSaturatedFilter(null); setDomainsMin(null); setDomainsMax(null); setTargetsMin(null); setTargetsMax(null);
    setDateFrom(null); setDateTo(null);
    setPage(1);
  };

  // ── No project state ───────────────────────────────────────
  if (!projectId) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center text-neutral-400">
          <div className="text-lg font-medium mb-1">Select a project</div>
          <div className="text-sm">Choose a project from the top bar to view query data</div>
        </div>
      </div>
    );
  }

  return (
    <QueryDashboardFilterContext.Provider value={filterCtx}>
      <div className="h-full flex flex-col bg-neutral-50">
        {/* ── Command bar ─────────────────────────────────── */}
        <div className="bg-white border-b border-neutral-200 px-5 py-2.5">
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-semibold text-neutral-700 whitespace-nowrap">Query Dashboard</h1>
            <span className="text-xs text-neutral-400">{formatNumber(total)} queries</span>

            <div className="relative flex-1 max-w-xs">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search query text..."
                className="w-full pl-8 pr-3 py-1.5 rounded-lg border border-neutral-200 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 focus:border-indigo-400"
              />
              {search && (
                <button onClick={() => { setSearch(''); setDebouncedSearch(''); }} className="absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 hover:text-neutral-600">
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>

            {hasFilters && (
              <button onClick={clearAllFilters}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium text-red-600 bg-red-50 border border-red-200 hover:bg-red-100 transition-colors shrink-0">
                <X className="w-3 h-3" /> Clear filters
              </button>
            )}

            <div className="flex-1" />

            <button onClick={() => { loadQueries(); loadSummary(); }}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-neutral-600 bg-white border border-neutral-200 hover:border-neutral-400 transition-colors shrink-0">
              <RefreshCw className={cn('w-3 h-3', isLoading && 'animate-spin')} /> Refresh
            </button>
          </div>
        </div>

        {/* ── Summary Metrics Bar ─────────────────────────── */}
        {summary && (
          <div className="bg-white border-b border-neutral-200 px-5 py-3">
            <div className="flex items-center gap-4 flex-wrap">
              <MetricCard label="Queries" value={formatNumber(summary.total_queries)} />
              <MetricCard label="Done" value={formatNumber(summary.done_queries)} color="text-green-600" />
              <MetricCard label="Domains" value={formatNumber(summary.total_domains)} color="text-blue-600" />
              <MetricCard label="Targets" value={formatNumber(summary.total_targets)} color="text-emerald-600" />
              <MetricCard label="Est. Cost" value={`$${summary.total_cost_usd.toFixed(2)}`} color="text-amber-600" />
              <MetricCard label="Saturation" value={`${summary.saturation_rate.toFixed(1)}%`}
                color={summary.saturation_rate > 80 ? 'text-red-600' : summary.saturation_rate > 50 ? 'text-amber-600' : 'text-green-600'} />
              {summary.avg_effectiveness !== null && (
                <MetricCard label="Avg Score" value={`${(summary.avg_effectiveness * 100).toFixed(0)}%`} color="text-indigo-600" />
              )}

              <div className="flex-1" />
              <button onClick={() => setShowSaturationPanel(!showSaturationPanel)}
                className="inline-flex items-center gap-1 text-xs text-neutral-500 hover:text-neutral-700 transition-colors">
                {showSaturationPanel ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                Saturation breakdown
              </button>
            </div>

            {/* ── Saturation Panel (collapsible) ──────── */}
            {showSaturationPanel && (
              <div className="mt-3 pt-3 border-t border-neutral-100 flex gap-6 flex-wrap">
                <SaturationTable title="By Segment" data={summary.by_segment}
                  onClickRow={(key) => { setSegmentFilters([key]); setPage(1); }} />
                <SaturationTable title="By Geo" data={summary.by_geo}
                  onClickRow={(key) => { setGeoFilters([key]); setPage(1); }} />
                <SaturationTable title="By Source" data={summary.by_source}
                  onClickRow={(key) => { setSourceFilters([key]); setPage(1); }} />
              </div>
            )}
          </div>
        )}

        {/* ── AG Grid ─────────────────────────────────────── */}
        <div className="flex-1 px-5 py-3">
          <div className={cn('ag-theme-alpine w-full h-full')} style={{ minHeight: 400 }}>
            {isLoading && queries.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="w-6 h-6 animate-spin text-neutral-400" />
              </div>
            ) : (
              <AgGridReact
                theme={AG_GRID_THEME}
                rowData={queries}
                columnDefs={columnDefs}
                defaultColDef={defaultColDef}
                onGridReady={onGridReady}
                onSortChanged={onSortChanged}
                getRowClass={getRowClass}
                domLayout="autoHeight"
                suppressCellFocus
                animateRows={false}
                getRowId={(params) => String(params.data.query_id)}
                overlayNoRowsTemplate='<span class="text-neutral-400 text-sm">No queries found</span>'
              />
            )}
          </div>
        </div>

        {/* ── Pagination ──────────────────────────────────── */}
        <div className="bg-white border-t border-neutral-200 px-5 py-2.5 flex items-center justify-between">
          <span className="text-xs text-neutral-500">
            {total > 0 ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)} of ${formatNumber(total)}` : 'No results'}
          </span>
          <div className="flex items-center gap-1">
            <button onClick={() => setPage(1)} disabled={page <= 1}
              className="p-1.5 rounded hover:bg-neutral-100 disabled:opacity-30 disabled:hover:bg-transparent transition-colors">
              <ChevronsLeft className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
              className="p-1.5 rounded hover:bg-neutral-100 disabled:opacity-30 disabled:hover:bg-transparent transition-colors">
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <span className="text-xs text-neutral-600 px-2">Page {page} of {totalPages}</span>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
              className="p-1.5 rounded hover:bg-neutral-100 disabled:opacity-30 disabled:hover:bg-transparent transition-colors">
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => setPage(totalPages)} disabled={page >= totalPages}
              className="p-1.5 rounded hover:bg-neutral-100 disabled:opacity-30 disabled:hover:bg-transparent transition-colors">
              <ChevronsRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </QueryDashboardFilterContext.Provider>
  );
}

// ── MetricCard ────────────────────────────────────────────────

function MetricCard({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] text-neutral-400 uppercase tracking-wider">{label}</span>
      <span className={cn('text-sm font-semibold', color || 'text-neutral-700')}>{value}</span>
    </div>
  );
}
