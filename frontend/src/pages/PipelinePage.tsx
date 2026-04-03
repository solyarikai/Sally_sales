import { useState, useEffect, useCallback, useMemo, useRef } from 'react';

import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import type {
  ColDef,
  GridReadyEvent,
  SelectionChangedEvent,
  GridApi,
  SortChangedEvent,
  ICellRendererParams,
} from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

const AG_GRID_THEME = "legacy";
ModuleRegistry.registerModules([AllCommunityModule]);

import {
  Layers, Target, Mail, Download, Globe, FileSpreadsheet,
  Loader2, AlertCircle, CheckCircle2, XCircle, Search,
  ExternalLink, Zap, UserPlus, ChevronDown,
  X, Settings2, DollarSign,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useAppStore } from '../store/appStore';
import {
  pipelineApi,
  type DiscoveredCompany,
  type DiscoveredCompanyDetail,
  type PipelineStats,
  type AutoEnrichConfig,
  type ExtractedContact,
  type PipelineEventItem,
} from '../api/pipeline';
import { PipelineFilterContext } from '../components/filters/PipelineFilterContext';
import { PipelineStatusColumnFilter } from '../components/filters/PipelineStatusColumnFilter';
import { PipelineTargetColumnFilter } from '../components/filters/PipelineTargetColumnFilter';

const statusColors: Record<string, string> = {
  new: 'bg-blue-100 text-blue-800',
  scraped: 'bg-cyan-100 text-cyan-800',
  analyzed: 'bg-yellow-100 text-yellow-800',
  contacts_extracted: 'bg-purple-100 text-purple-800',
  enriched: 'bg-green-100 text-green-800',
  exported: 'bg-emerald-100 text-emerald-800',
  rejected: 'bg-red-100 text-red-800',
};

const statusLabels: Record<string, string> = {
  new: 'New',
  scraped: 'Scraped',
  analyzed: 'Analyzed',
  contacts_extracted: 'Contacts',
  enriched: 'Enriched',
  exported: 'Exported',
  rejected: 'Rejected',
};

export function PipelinePage() {
  const gridRef = useRef<AgGridReact>(null);
  const [gridApi, setGridApi] = useState<GridApi | null>(null);
  const { currentCompany, currentProject } = useAppStore();
  const projectId = currentProject?.id;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [companies, setCompanies] = useState<DiscoveredCompany[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [stats, setStats] = useState<PipelineStats | null>(null);
  const [statusFilters, setStatusFilters] = useState<string[]>([]);
  const [targetFilter, setTargetFilter] = useState<'all' | 'targets' | 'non-targets'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Sort
  const [sortBy, setSortBy] = useState<string | undefined>(undefined);
  const [sortOrder, setSortOrder] = useState<string>('desc');

  // Selection (derived from ag-Grid)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Detail modal
  const [detailId, setDetailId] = useState<number | null>(null);
  const [detail, setDetail] = useState<DiscoveredCompanyDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Action state
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Auto-enrich config
  const [autoEnrichConfig, setAutoEnrichConfig] = useState<AutoEnrichConfig | null>(null);
  const [showAutoEnrich, setShowAutoEnrich] = useState(false);

  // Apollo settings popover
  const [showApolloSettings, setShowApolloSettings] = useState(false);
  const [apolloTitles, setApolloTitles] = useState<string[]>(['CEO', 'Founder', 'Managing Director', 'Owner']);
  const [apolloMaxPeople, setApolloMaxPeople] = useState(5);
  const [apolloMaxCredits, setApolloMaxCredits] = useState(50);
  const [apolloTitleInput, setApolloTitleInput] = useState('');
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  // Reset page when project changes
  useEffect(() => { setPage(1); }, [projectId]);

  // Load auto-enrich config when project changes (needs currentCompany for X-Company-ID header)
  useEffect(() => {
    if (projectId && currentCompany) {
      pipelineApi.getAutoEnrichConfig(projectId).then(setAutoEnrichConfig).catch(() => setAutoEnrichConfig(null));
    } else {
      setAutoEnrichConfig(null);
    }
  }, [projectId, currentCompany]);

  const saveAutoEnrichConfig = async (config: AutoEnrichConfig) => {
    if (!projectId) return;
    setAutoEnrichConfig(config);
    try {
      await pipelineApi.updateAutoEnrichConfig(projectId, config);
    } catch {
      // silent
    }
  };

  // Derive is_target param from targetFilter
  const isTargetParam = targetFilter === 'targets' ? true : targetFilter === 'non-targets' ? false : undefined;

  const loadData = useCallback(async () => {
    if (!currentCompany || !projectId) {
      setCompanies([]);
      setTotal(0);
      setStats(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [companiesData, statsData] = await Promise.all([
        pipelineApi.listDiscoveredCompanies({
          project_id: projectId,
          status: statusFilters.length === 1 ? statusFilters[0] : undefined,
          is_target: isTargetParam,
          search: searchQuery || undefined,
          sort_by: sortBy,
          sort_order: sortOrder,
          page,
          page_size: 50,
        }),
        pipelineApi.getStats(projectId),
      ]);
      setCompanies(companiesData.items);
      setTotal(companiesData.total);
      setStats(statsData);
    } catch (err: any) {
      setError(err.userMessage || 'Failed to load pipeline data');
    } finally {
      setLoading(false);
    }
  }, [projectId, statusFilters, isTargetParam, searchQuery, sortBy, sortOrder, page, currentCompany]);

  useEffect(() => { loadData(); }, [loadData]);

  // Load detail when modal opens
  useEffect(() => {
    if (detailId) {
      setDetailLoading(true);
      pipelineApi.getDiscoveredCompany(detailId)
        .then(setDetail)
        .catch(() => setDetail(null))
        .finally(() => setDetailLoading(false));
    } else {
      setDetail(null);
    }
  }, [detailId]);

  const selectedCompanyIds = Array.from(selectedIds);

  // Filter context for column filters
  const filterCtx = useMemo(() => ({
    statusFilters,
    setStatusFilters,
    toggleStatus: (s: string) => {
      setStatusFilters(prev =>
        prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]
      );
    },
    targetFilter,
    setTargetFilter,
    stats,
    resetPage: () => setPage(1),
  }), [statusFilters, targetFilter, stats]);

  // ag-Grid sort handler
  const onSortChanged = useCallback((e: SortChangedEvent) => {
    const cols = e.api.getColumnState();
    const sorted = cols.find(c => c.sort);
    if (sorted) {
      setSortBy(sorted.colId);
      setSortOrder(sorted.sort || 'desc');
    } else {
      setSortBy(undefined);
      setSortOrder('desc');
    }
    setPage(1);
  }, []);

  // ag-Grid selection handler
  const onSelectionChanged = useCallback((e: SelectionChangedEvent) => {
    const rows = e.api.getSelectedRows() as DiscoveredCompany[];
    setSelectedIds(new Set(rows.map(r => r.id)));
  }, []);

  const onGridReady = useCallback((e: GridReadyEvent) => {
    setGridApi(e.api);
  }, []);

  // ========== Column Definitions ==========
  const columnDefs = useMemo<ColDef<DiscoveredCompany>[]>(() => [
    {
      headerCheckboxSelection: true,
      checkboxSelection: true,
      width: 48,
      pinned: 'left',
      suppressMovable: true,
      sortable: false,
      filter: false,
      resizable: false,
    },
    {
      headerName: 'Domain',
      field: 'domain',
      flex: 2,
      sortable: true,
      filter: false,
      cellRenderer: (params: ICellRendererParams<DiscoveredCompany>) => {
        const c = params.data;
        if (!c) return null;
        return (
          <div className="flex items-center gap-2 cursor-pointer" onClick={() => setDetailId(c.id)}>
            <span className="text-sm font-medium text-neutral-900">{c.domain}</span>
            {c.url && (
              <a href={c.url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}>
                <ExternalLink className="w-3.5 h-3.5 text-neutral-400 hover:text-blue-500" />
              </a>
            )}
          </div>
        );
      },
    },
    {
      headerName: 'Company',
      field: 'name',
      flex: 2,
      sortable: true,
      filter: false,
      cellRenderer: (params: ICellRendererParams<DiscoveredCompany>) => {
        const c = params.data;
        if (!c) return null;
        const info = c.company_info || {};
        return (
          <span className="text-sm text-neutral-600 cursor-pointer" onClick={() => setDetailId(c.id)}>
            {c.name || info.name || '-'}
          </span>
        );
      },
    },
    {
      headerName: 'Status',
      field: 'status',
      width: 130,
      sortable: true,
      filter: PipelineStatusColumnFilter,
      cellRenderer: (params: ICellRendererParams<DiscoveredCompany>) => {
        const c = params.data;
        if (!c) return null;
        // If status is contacts_extracted but no contacts were found, display as "Analyzed" instead
        const displayStatus = (c.status === 'contacts_extracted' && (c.contacts_count || 0) === 0)
          ? 'analyzed'
          : c.status;
        return (
          <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', statusColors[displayStatus] || 'bg-gray-100 text-gray-700')}>
            {statusLabels[displayStatus] || displayStatus}
          </span>
        );
      },
    },
    {
      headerName: 'Target',
      field: 'is_target',
      width: 90,
      sortable: true,
      filter: PipelineTargetColumnFilter,
      cellRenderer: (params: ICellRendererParams<DiscoveredCompany>) => {
        const c = params.data;
        if (!c) return null;
        return c.is_target
          ? <CheckCircle2 className="w-4 h-4 text-green-600 mx-auto" />
          : <XCircle className="w-4 h-4 text-neutral-300 mx-auto" />;
      },
      cellStyle: { display: 'flex', alignItems: 'center', justifyContent: 'center' } as Record<string, string>,
    },
    {
      headerName: 'Confidence',
      field: 'confidence',
      width: 110,
      sortable: true,
      filter: false,
      cellRenderer: (params: ICellRendererParams<DiscoveredCompany>) => {
        const c = params.data;
        if (!c) return null;
        const val = c.confidence || 0;
        const color = val >= 0.8 ? 'text-green-700' : val >= 0.5 ? 'text-yellow-700' : 'text-neutral-400';
        return (
          <span className={cn('font-medium text-sm', color)}>
            {c.confidence ? `${(c.confidence * 100).toFixed(0)}%` : '-'}
          </span>
        );
      },
      cellStyle: { textAlign: 'right' },
    },
    {
      headerName: 'Contacts',
      field: 'contacts_count',
      width: 100,
      sortable: true,
      filter: false,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (params) => String(params.value || 0),
    },
    {
      headerName: 'Apollo',
      field: 'apollo_people_count',
      width: 90,
      sortable: true,
      filter: false,
      cellStyle: { textAlign: 'right' },
      valueFormatter: (params) => String(params.value || 0),
    },
  ], []);

  const defaultColDef = useMemo<ColDef>(() => ({
    suppressMovable: true,
    resizable: true,
  }), []);

  const getRowClass = useCallback((params: any) => {
    const data = params.data as DiscoveredCompany | undefined;
    if (!data) return '';
    if (data.is_target) return 'pipeline-row-target';
    return '';
  }, []);

  // ========== Actions ==========

  const handleExtractContacts = async () => {
    if (selectedCompanyIds.length === 0) return;
    setActionLoading('extract');
    try {
      const result = await pipelineApi.extractContacts(selectedCompanyIds);
      alert(`Extracted ${result.contacts_found} contacts from ${result.processed} companies`);
      setSelectedIds(new Set());
      gridApi?.deselectAll();
      loadData();
    } catch (err: any) {
      alert(err.userMessage || 'Extraction failed');
    } finally {
      setActionLoading(null);
    }
  };

  const handleEnrichApollo = async () => {
    if (selectedCompanyIds.length === 0) return;
    setShowApolloSettings(false);
    setActionLoading('apollo');
    try {
      const result = await pipelineApi.enrichApollo(selectedCompanyIds, {
        maxPeople: apolloMaxPeople,
        titles: apolloTitles,
        maxCredits: apolloMaxCredits,
      });
      alert(
        `Apollo: ${result.people_found} people from ${result.processed} companies\n` +
        `Credits used: ${result.credits_used}` +
        (result.skipped ? ` | Skipped: ${result.skipped} (already enriched)` : '')
      );
      setSelectedIds(new Set());
      gridApi?.deselectAll();
      loadData();
    } catch (err: any) {
      alert(err.userMessage || 'Apollo enrichment failed');
    } finally {
      setActionLoading(null);
    }
  };

  const handlePromoteToCrm = async () => {
    setActionLoading('promote');
    try {
      const contactIds: number[] = [];
      for (const id of selectedCompanyIds) {
        const d = await pipelineApi.getDiscoveredCompany(id);
        contactIds.push(...d.extracted_contacts.filter(ec => !ec.contact_id).map(ec => ec.id));
      }

      if (contactIds.length === 0) {
        alert('No unpromoted contacts found. Extract contacts first.');
        setActionLoading(null);
        return;
      }

      const result = await pipelineApi.promoteToCrm(contactIds, projectId);
      alert(`Promoted ${result.promoted} contacts to CRM (${result.skipped} skipped)`);
      setSelectedIds(new Set());
      gridApi?.deselectAll();
      loadData();
    } catch (err: any) {
      alert(err.userMessage || 'CRM promotion failed');
    } finally {
      setActionLoading(null);
    }
  };

  const buildFilename = (suffix: string) => {
    const projName = currentProject?.name || 'all';
    const ts = new Date().toISOString().slice(0, 16).replace('T', '_').replace(':', '-');
    return `${projName}_${suffix}_${ts}.csv`;
  };

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportCsv = async (emailOnly: boolean, phoneOnly: boolean) => {
    setExportLoading(true);
    setShowExportMenu(false);
    try {
      const blob = await pipelineApi.exportContactsCsv(projectId, emailOnly, phoneOnly);
      const suffix = emailOnly ? 'email_contacts' : phoneOnly ? 'phone_contacts' : 'all_contacts';
      downloadBlob(blob, buildFilename(suffix));
    } catch (err: any) {
      alert(err.userMessage || 'CSV export failed');
    } finally {
      setExportLoading(false);
    }
  };

  const handleExportSheet = async (emailOnly: boolean, phoneOnly: boolean) => {
    setExportLoading(true);
    setShowExportMenu(false);
    try {
      const result = await pipelineApi.exportContactsSheet(projectId, emailOnly, phoneOnly);
      window.open(result.url, '_blank');
    } catch (err: any) {
      alert(err.response?.data?.detail || err.userMessage || 'Google Sheets export failed');
    } finally {
      setExportLoading(false);
    }
  };

  const handleReject = async () => {
    if (selectedCompanyIds.length === 0) return;
    setActionLoading('reject');
    try {
      await pipelineApi.updateStatus(selectedCompanyIds, 'rejected');
      setSelectedIds(new Set());
      gridApi?.deselectAll();
      loadData();
    } catch (err: any) {
      alert(err.userMessage || 'Status update failed');
    } finally {
      setActionLoading(null);
    }
  };

  if (!currentCompany) {
    return (
      <div className="p-6 max-w-[1400px] mx-auto">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-blue-700 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          Select a company to view the pipeline
        </div>
      </div>
    );
  }

  if (!projectId) {
    return (
      <div className="p-6 max-w-[1400px] mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-neutral-900">Pipeline</h1>
            <p className="text-neutral-500 text-sm mt-1">Manage discovered companies through the outreach pipeline</p>
          </div>
        </div>
        <div className="flex flex-col items-center justify-center min-h-[300px] text-neutral-400">
          <Layers className="w-12 h-12 mb-3 opacity-40" />
          <p className="text-lg font-medium">Select a project to view pipeline</p>
          <p className="text-sm mt-1">Choose a project from the selector in the top-left corner</p>
        </div>
      </div>
    );
  }

  if (loading && companies.length === 0) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <Loader2 className="w-6 h-6 animate-spin text-neutral-400" />
      </div>
    );
  }

  return (
    <PipelineFilterContext.Provider value={filterCtx}>
      <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-neutral-900">Pipeline</h1>
            <p className="text-neutral-500 text-sm mt-1">Manage discovered companies through the outreach pipeline</p>
          </div>
          <div className="relative">
            <button
              onClick={() => setShowExportMenu(!showExportMenu)}
              disabled={exportLoading}
              className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {exportLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
              Export
              <ChevronDown className="w-3.5 h-3.5" />
            </button>
            {showExportMenu && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowExportMenu(false)} />
                <div className="absolute right-0 top-full mt-1 z-20 w-64 bg-white rounded-lg shadow-lg border border-neutral-200 py-1">
                  <div className="px-3 py-1.5 text-xs font-medium text-neutral-400 uppercase">CSV Download</div>
                  <button onClick={() => handleExportCsv(true, false)} className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 flex items-center gap-2">
                    <Mail className="w-4 h-4 text-blue-500" /> Contacts with Email
                  </button>
                  <button onClick={() => handleExportCsv(false, true)} className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 flex items-center gap-2">
                    <Globe className="w-4 h-4 text-green-500" /> Contacts with Phone
                  </button>
                  <button onClick={() => handleExportCsv(false, false)} className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 flex items-center gap-2">
                    <Download className="w-4 h-4 text-neutral-400" /> All Contacts
                  </button>
                  <div className="border-t border-neutral-100 my-1" />
                  <div className="px-3 py-1.5 text-xs font-medium text-neutral-400 uppercase">Google Sheets</div>
                  <button onClick={() => handleExportSheet(true, false)} className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 flex items-center gap-2">
                    <FileSpreadsheet className="w-4 h-4 text-green-600" /> Contacts with Email
                  </button>
                  <button onClick={() => handleExportSheet(false, true)} className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 flex items-center gap-2">
                    <FileSpreadsheet className="w-4 h-4 text-green-600" /> Contacts with Phone
                  </button>
                  <button onClick={() => handleExportSheet(false, false)} className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 flex items-center gap-2">
                    <FileSpreadsheet className="w-4 h-4 text-green-600" /> All Contacts
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span className="flex-1">{error}</span>
            <button onClick={() => setError(null)} className="p-0.5 hover:bg-red-100 rounded">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Stats cards */}
        {stats && (
          <div className="grid grid-cols-5 gap-3">
            <PipelineStatCard label="Discovered" value={stats.total_discovered} icon={Layers} />
            <PipelineStatCard label="Targets" value={stats.targets} icon={Target} color="green" />
            <PipelineStatCard label="Contacts Extracted" value={stats.contacts_extracted} icon={Mail} color="purple" />
            <PipelineStatCard label="Enriched" value={stats.enriched} icon={Zap} color="blue" />
            <PipelineStatCard label="Exported" value={stats.exported} icon={CheckCircle2} color="emerald" />
          </div>
        )}

        {/* Spending cards — shown when a project is selected */}
        {stats?.spending && projectId && (
          <div className="bg-white rounded-xl border border-neutral-200 p-4">
            <div className="flex items-center gap-2 mb-3">
              <DollarSign className="w-4 h-4 text-neutral-400" />
              <span className="text-sm font-medium text-neutral-700">Project Spending</span>
            </div>
            <div className="grid grid-cols-7 gap-4 text-sm">
              <div>
                <span className="text-neutral-500 text-xs">Yandex</span>
                <div className="font-medium">${stats.spending.yandex_cost.toFixed(2)}</div>
              </div>
              <div>
                <span className="text-neutral-500 text-xs">Google</span>
                <div className="font-medium">${(stats.spending.google_cost ?? 0).toFixed(2)}</div>
              </div>
              <div>
                <span className="text-neutral-500 text-xs">Gemini</span>
                <div className="font-medium">${(stats.spending.gemini_cost_estimate ?? 0).toFixed(2)}</div>
              </div>
              <div>
                <span className="text-neutral-500 text-xs">OpenAI</span>
                <div className="font-medium">${stats.spending.openai_cost_estimate.toFixed(2)}</div>
              </div>
              <div>
                <span className="text-neutral-500 text-xs">Crona</span>
                <div className="font-medium">${stats.spending.crona_cost.toFixed(2)}</div>
              </div>
              <div>
                <span className="text-neutral-500 text-xs">Apollo ({stats.spending.apollo_credits_used} credits)</span>
                <div className="font-medium">${stats.spending.apollo_cost_estimate.toFixed(2)}</div>
              </div>
              <div>
                <span className="text-neutral-500 text-xs font-medium">Total</span>
                <div className="font-bold text-neutral-900">${stats.spending.total_estimate.toFixed(2)}</div>
              </div>
            </div>
          </div>
        )}

        {/* Contact breakdown */}
        {stats && (stats.apollo_contacts > 0 || stats.website_contacts > 0) && (
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-white rounded-xl border border-neutral-200 p-4">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-orange-500" />
                <span className="text-sm font-medium text-neutral-700">Apollo Enrichment</span>
                <span className="ml-auto text-xs text-neutral-400">{stats.apollo_contacts} contacts</span>
              </div>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <div className="text-xl font-bold text-neutral-900">{stats.apollo_contacts.toLocaleString()}</div>
                  <div className="text-xs text-neutral-500">contacts</div>
                </div>
                <div>
                  <div className="text-xl font-bold text-blue-600">{stats.apollo_with_email.toLocaleString()}</div>
                  <div className="text-xs text-neutral-500">with email</div>
                </div>
                <div>
                  <div className="text-xl font-bold text-sky-600">{stats.apollo_with_linkedin.toLocaleString()}</div>
                  <div className="text-xs text-neutral-500">with LinkedIn</div>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-xl border border-neutral-200 p-4">
              <div className="flex items-center gap-2 mb-2">
                <Globe className="w-4 h-4 text-purple-500" />
                <span className="text-sm font-medium text-neutral-700">Website Scraping</span>
              </div>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <div className="text-xl font-bold text-neutral-900">{stats.website_contacts.toLocaleString()}</div>
                  <div className="text-xs text-neutral-500">contacts</div>
                </div>
                <div>
                  <div className="text-xl font-bold text-blue-600">{stats.website_with_email.toLocaleString()}</div>
                  <div className="text-xs text-neutral-500">with email</div>
                </div>
                <div>
                  <div className="text-xl font-bold text-green-600">{stats.website_with_phone.toLocaleString()}</div>
                  <div className="text-xs text-neutral-500">with phone</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Auto-enrich config — shown when a project is selected */}
        {projectId && autoEnrichConfig && (
          <div className="bg-white rounded-xl border border-neutral-200 p-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <Zap className="w-4 h-4 text-purple-500" />
                <span className="text-sm font-medium text-neutral-700">Auto-Enrichment</span>
              </div>
              <button
                onClick={() => setShowAutoEnrich(!showAutoEnrich)}
                className="text-xs text-neutral-400 hover:text-neutral-600"
              >
                {showAutoEnrich ? 'Hide' : 'Configure'}
              </button>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoEnrichConfig.auto_extract}
                  onChange={e => saveAutoEnrichConfig({ ...autoEnrichConfig, auto_extract: e.target.checked })}
                  className="rounded"
                />
                <span className="text-neutral-600">Auto-extract contacts from targets</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoEnrichConfig.auto_apollo}
                  onChange={e => saveAutoEnrichConfig({ ...autoEnrichConfig, auto_apollo: e.target.checked })}
                  className="rounded"
                />
                <span className="text-neutral-600">Auto Apollo enrich</span>
              </label>
            </div>
            {showAutoEnrich && (
              <div className="mt-3 pt-3 border-t border-neutral-100 grid grid-cols-3 gap-3 text-sm">
                <div>
                  <label className="text-xs text-neutral-500 block mb-1">Apollo Titles</label>
                  <input
                    type="text"
                    value={autoEnrichConfig.apollo_titles.join(', ')}
                    onChange={e => saveAutoEnrichConfig({
                      ...autoEnrichConfig,
                      apollo_titles: e.target.value.split(',').map(s => s.trim()).filter(Boolean),
                    })}
                    className="w-full px-2 py-1 text-xs rounded border border-neutral-200"
                    placeholder="CEO, Founder, CTO"
                  />
                </div>
                <div>
                  <label className="text-xs text-neutral-500 block mb-1">Max people/company</label>
                  <input
                    type="number"
                    min={1} max={25}
                    value={autoEnrichConfig.apollo_max_people}
                    onChange={e => saveAutoEnrichConfig({ ...autoEnrichConfig, apollo_max_people: parseInt(e.target.value) || 5 })}
                    className="w-full px-2 py-1 text-xs rounded border border-neutral-200"
                  />
                </div>
                <div>
                  <label className="text-xs text-neutral-500 block mb-1">Max credits</label>
                  <input
                    type="number"
                    min={1}
                    value={autoEnrichConfig.apollo_max_credits}
                    onChange={e => saveAutoEnrichConfig({ ...autoEnrichConfig, apollo_max_credits: parseInt(e.target.value) || 50 })}
                    className="w-full px-2 py-1 text-xs rounded border border-neutral-200"
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Top bar: Search + Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          {/* Search */}
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => { setSearchQuery(e.target.value); setPage(1); }}
              placeholder="Search domain or name..."
              className="w-full pl-9 pr-3 py-1.5 text-sm rounded-lg border border-neutral-200 bg-white"
            />
          </div>

          {/* Active filters summary */}
          {statusFilters.length > 0 && (
            <span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-1 rounded-lg">
              {statusFilters.length} status filter{statusFilters.length > 1 ? 's' : ''}
            </span>
          )}
          {targetFilter !== 'all' && (
            <span className="text-xs bg-green-50 text-green-700 px-2 py-1 rounded-lg">
              {targetFilter === 'targets' ? 'Targets only' : 'Non-targets only'}
            </span>
          )}

          <span className="text-sm text-neutral-400 ml-auto">{total} companies</span>
        </div>

        {/* Bulk action toolbar */}
        {selectedIds.size > 0 && (
          <div className="bg-black text-white rounded-xl px-4 py-3 flex items-center gap-3">
            <span className="text-sm font-medium">{selectedIds.size} selected</span>
            <div className="w-px h-5 bg-white/20" />
            <button
              onClick={handleExtractContacts}
              disabled={!!actionLoading}
              className="flex items-center gap-1.5 px-3 py-1 text-sm rounded-lg bg-white/10 hover:bg-white/20 disabled:opacity-50"
            >
              {actionLoading === 'extract' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Mail className="w-3.5 h-3.5" />}
              Extract Contacts
            </button>
            <div className="relative">
              <button
                onClick={() => setShowApolloSettings(!showApolloSettings)}
                disabled={!!actionLoading}
                className="flex items-center gap-1.5 px-3 py-1 text-sm rounded-lg bg-white/10 hover:bg-white/20 disabled:opacity-50"
              >
                {actionLoading === 'apollo' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
                Enrich Apollo
                <Settings2 className="w-3 h-3 opacity-50" />
              </button>
              {showApolloSettings && (
                <div className="absolute bottom-full left-0 mb-2 w-80 bg-white text-neutral-900 rounded-xl shadow-xl border border-neutral-200 p-4 z-50" onClick={e => e.stopPropagation()}>
                  <div className="text-sm font-semibold mb-3">Apollo Settings</div>

                  {/* Title filters */}
                  <div className="mb-3">
                    <label className="text-xs text-neutral-500 block mb-1">Role/Title Filters</label>
                    <div className="flex flex-wrap gap-1 mb-2">
                      {apolloTitles.map((t, i) => (
                        <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 bg-purple-50 text-purple-700 rounded text-xs">
                          {t}
                          <button onClick={() => setApolloTitles(prev => prev.filter((_, j) => j !== i))} className="hover:text-purple-900">
                            <X className="w-3 h-3" />
                          </button>
                        </span>
                      ))}
                      {apolloTitles.length === 0 && <span className="text-xs text-neutral-400">No filter (all roles)</span>}
                    </div>
                    <div className="flex gap-1">
                      <input
                        type="text"
                        value={apolloTitleInput}
                        onChange={e => setApolloTitleInput(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter' && apolloTitleInput.trim()) {
                            setApolloTitles(prev => [...prev, apolloTitleInput.trim()]);
                            setApolloTitleInput('');
                          }
                        }}
                        placeholder="Add role..."
                        className="flex-1 px-2 py-1 text-xs rounded border border-neutral-200 bg-white"
                      />
                      <button
                        onClick={() => {
                          if (apolloTitleInput.trim()) {
                            setApolloTitles(prev => [...prev, apolloTitleInput.trim()]);
                            setApolloTitleInput('');
                          }
                        }}
                        className="px-2 py-1 text-xs bg-neutral-100 rounded hover:bg-neutral-200"
                      >Add</button>
                    </div>
                  </div>

                  {/* Max people per company */}
                  <div className="mb-3">
                    <label className="text-xs text-neutral-500 block mb-1">Max people per company</label>
                    <input
                      type="number"
                      min={1} max={25}
                      value={apolloMaxPeople}
                      onChange={e => setApolloMaxPeople(parseInt(e.target.value) || 5)}
                      className="w-full px-2 py-1 text-xs rounded border border-neutral-200"
                    />
                  </div>

                  {/* Max credits */}
                  <div className="mb-3">
                    <label className="text-xs text-neutral-500 block mb-1">Max credits (1 credit = 1 domain lookup)</label>
                    <input
                      type="number"
                      min={1}
                      value={apolloMaxCredits}
                      onChange={e => setApolloMaxCredits(parseInt(e.target.value) || 50)}
                      className="w-full px-2 py-1 text-xs rounded border border-neutral-200"
                    />
                  </div>

                  {/* Summary */}
                  <div className="text-xs text-neutral-500 mb-3 bg-neutral-50 rounded-lg p-2">
                    Will search <strong>{Math.min(selectedIds.size, apolloMaxCredits)}</strong> domains,
                    up to <strong>{apolloMaxPeople}</strong> people each
                    {apolloTitles.length > 0 && <>, filtered by: <strong>{apolloTitles.join(', ')}</strong></>}
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={handleEnrichApollo}
                      className="flex-1 px-3 py-1.5 text-xs font-medium bg-purple-600 text-white rounded-lg hover:bg-purple-700"
                    >
                      Run Enrichment
                    </button>
                    <button
                      onClick={() => setShowApolloSettings(false)}
                      className="px-3 py-1.5 text-xs rounded-lg border border-neutral-200 hover:bg-neutral-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
            <button
              onClick={handlePromoteToCrm}
              disabled={!!actionLoading}
              className="flex items-center gap-1.5 px-3 py-1 text-sm rounded-lg bg-white/10 hover:bg-white/20 disabled:opacity-50"
            >
              {actionLoading === 'promote' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <UserPlus className="w-3.5 h-3.5" />}
              Promote to CRM
            </button>
            <button
              onClick={handleReject}
              disabled={!!actionLoading}
              className="flex items-center gap-1.5 px-3 py-1 text-sm rounded-lg bg-red-500/20 hover:bg-red-500/30 disabled:opacity-50"
            >
              {actionLoading === 'reject' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <XCircle className="w-3.5 h-3.5" />}
              Reject
            </button>
            <button
              onClick={() => { setSelectedIds(new Set()); gridApi?.deselectAll(); }}
              className="ml-auto p-1 hover:bg-white/10 rounded"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* ag-Grid Companies table */}
        <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
          <style>{`
            .pipeline-row-target { background-color: rgba(34, 197, 94, 0.05) !important; }
            .pipeline-row-target:hover { background-color: rgba(34, 197, 94, 0.1) !important; }
          `}</style>
          <div className="ag-theme-alpine" style={{ height: Math.min(600, Math.max(200, companies.length * 42 + 48)) }}>
            <AgGridReact
              ref={gridRef}
              theme={AG_GRID_THEME}
              rowData={companies}
              columnDefs={columnDefs}
              defaultColDef={defaultColDef}
              rowSelection="multiple"
              suppressRowClickSelection={true}
              onGridReady={onGridReady}
              onSelectionChanged={onSelectionChanged}
              onSortChanged={onSortChanged}
              getRowId={(params) => String(params.data.id)}
              getRowClass={getRowClass}
              rowHeight={42}
              headerHeight={42}
              animateRows={false}
              suppressCellFocus={true}
              noRowsOverlayComponent={() => (
                <div className="text-neutral-400 py-12">
                  No discovered companies yet. Run a project search first.
                </div>
              )}
            />
          </div>
        </div>

        {/* Pagination */}
        {total > 50 && (
          <div className="flex justify-center gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 text-sm rounded-lg border border-neutral-200 disabled:opacity-40 hover:bg-neutral-50"
            >
              Previous
            </button>
            <span className="px-3 py-1.5 text-sm text-neutral-500">
              Page {page} of {Math.ceil(total / 50)}
            </span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={page >= Math.ceil(total / 50)}
              className="px-3 py-1.5 text-sm rounded-lg border border-neutral-200 disabled:opacity-40 hover:bg-neutral-50"
            >
              Next
            </button>
          </div>
        )}

        {/* Detail Modal */}
        {detailId && (
          <DetailModal
            detail={detail}
            loading={detailLoading}
            onClose={() => setDetailId(null)}
          />
        )}
      </div>
    </PipelineFilterContext.Provider>
  );
}

// ============ Detail Modal ============

function DetailModal({
  detail,
  loading,
  onClose,
}: {
  detail: DiscoveredCompanyDetail | null;
  loading: boolean;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<'info' | 'contacts' | 'events'>('info');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-neutral-200 flex items-center justify-between">
          <div>
            {detail ? (
              <>
                <h2 className="text-lg font-bold text-neutral-900">{detail.domain}</h2>
                <p className="text-sm text-neutral-500">{detail.name || detail.company_info?.name || 'Unknown company'}</p>
              </>
            ) : (
              <h2 className="text-lg font-bold text-neutral-900">Loading...</h2>
            )}
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-neutral-100 rounded-lg">
            <X className="w-5 h-5 text-neutral-500" />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-neutral-400" />
          </div>
        ) : detail ? (
          <>
            {/* Tabs */}
            <div className="flex gap-1 px-6 border-b border-neutral-200">
              {(['info', 'contacts', 'events'] as const).map(t => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={cn(
                    'px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors capitalize',
                    tab === t ? 'border-black text-neutral-900' : 'border-transparent text-neutral-500 hover:text-neutral-700'
                  )}
                >
                  {t === 'contacts' ? `Contacts (${detail.extracted_contacts.length})` :
                   t === 'events' ? `Events (${detail.events.length})` : 'Info'}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-auto p-6">
              {tab === 'info' && <InfoTab detail={detail} />}
              {tab === 'contacts' && <ContactsTab contacts={detail.extracted_contacts} />}
              {tab === 'events' && <EventsTab events={detail.events} />}
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

function InfoTab({ detail }: { detail: DiscoveredCompanyDetail }) {
  const info = detail.company_info || {};
  return (
    <div className="space-y-4 text-sm">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <span className="text-neutral-500">Domain</span>
          <div className="font-medium">{detail.domain}</div>
        </div>
        <div>
          <span className="text-neutral-500">Status</span>
          <div>
            {(() => {
              const ds = (detail.status === 'contacts_extracted' && (detail.contacts_count || 0) === 0)
                ? 'analyzed' : detail.status;
              return (
                <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', statusColors[ds] || 'bg-gray-100')}>
                  {statusLabels[ds] || ds}
                </span>
              );
            })()}
          </div>
        </div>
        <div>
          <span className="text-neutral-500">Target</span>
          <div className="font-medium">{detail.is_target ? 'Yes' : 'No'} {detail.confidence ? `(${(detail.confidence * 100).toFixed(0)}%)` : ''}</div>
        </div>
        <div>
          <span className="text-neutral-500">Industry</span>
          <div className="font-medium">{info.industry || '-'}</div>
        </div>
      </div>
      {detail.reasoning && (
        <div>
          <span className="text-neutral-500 block mb-1">GPT Reasoning</span>
          <p className="text-neutral-700 bg-neutral-50 rounded-lg p-3">{detail.reasoning}</p>
        </div>
      )}
      {info.description && (
        <div>
          <span className="text-neutral-500 block mb-1">Description</span>
          <p className="text-neutral-700">{info.description}</p>
        </div>
      )}
      {info.services && info.services.length > 0 && (
        <div>
          <span className="text-neutral-500 block mb-1">Services</span>
          <div className="flex flex-wrap gap-1">
            {info.services.map((s: string, i: number) => (
              <span key={i} className="px-2 py-0.5 bg-neutral-100 rounded text-xs">{s}</span>
            ))}
          </div>
        </div>
      )}
      {info.location && (
        <div>
          <span className="text-neutral-500">Location</span>
          <div className="font-medium">{info.location}</div>
        </div>
      )}
      {detail.emails_found && detail.emails_found.length > 0 && (
        <div>
          <span className="text-neutral-500 block mb-1">Emails Found</span>
          <div className="flex flex-wrap gap-1">
            {detail.emails_found.map((e, i) => (
              <span key={i} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">{e}</span>
            ))}
          </div>
        </div>
      )}
      {detail.phones_found && detail.phones_found.length > 0 && (
        <div>
          <span className="text-neutral-500 block mb-1">Phones Found</span>
          <div className="flex flex-wrap gap-1">
            {detail.phones_found.map((p, i) => (
              <span key={i} className="px-2 py-0.5 bg-green-50 text-green-700 rounded text-xs">{p}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ContactsTab({ contacts }: { contacts: ExtractedContact[] }) {
  if (contacts.length === 0) {
    return <p className="text-neutral-400 text-center py-8">No contacts extracted yet</p>;
  }

  return (
    <div className="space-y-3">
      {contacts.map(c => (
        <div key={c.id} className="border border-neutral-200 rounded-lg p-3 text-sm">
          <div className="flex items-center gap-2 mb-1">
            {c.first_name || c.last_name ? (
              <span className="font-medium text-neutral-900">{[c.first_name, c.last_name].filter(Boolean).join(' ')}</span>
            ) : (
              <span className="text-neutral-400">Unknown name</span>
            )}
            <span className={cn(
              'px-1.5 py-0.5 rounded text-xs',
              c.source === 'apollo' ? 'bg-purple-50 text-purple-700' : 'bg-blue-50 text-blue-700'
            )}>
              {c.source === 'apollo' ? 'Apollo' : 'Website'}
            </span>
            {c.is_verified && <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />}
            {c.contact_id && <span className="text-xs text-green-600 bg-green-50 px-1.5 py-0.5 rounded">In CRM</span>}
          </div>
          <div className="text-neutral-600 space-y-0.5">
            {c.email && <div className="flex items-center gap-1"><Mail className="w-3 h-3" /> {c.email}</div>}
            {c.job_title && <div className="text-neutral-500">{c.job_title}</div>}
            {c.phone && <div className="text-neutral-500">{c.phone}</div>}
            {c.linkedin_url && (
              <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline text-xs">LinkedIn</a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function EventsTab({ events }: { events: PipelineEventItem[] }) {
  if (events.length === 0) {
    return <p className="text-neutral-400 text-center py-8">No events yet</p>;
  }

  return (
    <div className="space-y-2">
      {events.map(e => (
        <div key={e.id} className="flex items-start gap-3 text-sm">
          <div className="w-2 h-2 rounded-full bg-neutral-300 mt-1.5 flex-shrink-0" />
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium text-neutral-700">{e.event_type.replace(/_/g, ' ')}</span>
              <span className="text-xs text-neutral-400">
                {e.created_at ? new Date(e.created_at).toLocaleString('ru-RU') : ''}
              </span>
            </div>
            {e.error_message && <div className="text-red-600 text-xs mt-0.5">{e.error_message}</div>}
            {e.detail && (
              <div className="text-neutral-500 text-xs mt-0.5">
                {Object.entries(e.detail).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(', ')}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ============ Helpers ============

function PipelineStatCard({ label, value, icon: Icon, color }: { label: string; value: number; icon: any; color?: string }) {
  const colorMap: Record<string, string> = {
    green: 'text-green-600',
    purple: 'text-purple-600',
    blue: 'text-blue-600',
    emerald: 'text-emerald-600',
  };

  return (
    <div className="bg-white rounded-xl border border-neutral-200 p-4">
      <div className="flex items-center gap-2 mb-1">
        <Icon className={cn('w-4 h-4', color ? colorMap[color] : 'text-neutral-400')} />
        <span className="text-xs text-neutral-500">{label}</span>
      </div>
      <div className="text-2xl font-bold text-neutral-900">{value.toLocaleString()}</div>
    </div>
  );
}
