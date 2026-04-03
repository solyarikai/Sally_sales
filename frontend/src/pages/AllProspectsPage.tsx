import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import type { 
  ColDef, 
  GridReadyEvent,
  SelectionChangedEvent,
  GridApi,
  SortChangedEvent,
  ValueFormatterParams
} from 'ag-grid-community';
// Use legacy themes
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

// For AG Grid v35+, we need to set theme to "legacy"
const AG_GRID_THEME = "legacy";

// Register AG Grid modules
ModuleRegistry.registerModules([AllCommunityModule]);

import { 
  Users, Search, Download, Trash2, RefreshCw, 
  Mail, Linkedin, Send, Copy, X, Tag, FileText, 
  ExternalLink, Building2, Briefcase, MapPin, Clock,
  Settings2, Upload, Eye, Save, Check
} from 'lucide-react';
import { prospectsApi, type Prospect, type ProspectStats, type ProspectActivity } from '../api';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { cn, formatNumber } from '../lib/utils';

export function AllProspectsPage() {
  const gridRef = useRef<AgGridReact>(null);
  const [, setGridApi] = useState<GridApi | null>(null);
  
  // Data
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [stats, setStats] = useState<ProspectStats | null>(null);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  
  // Filters & Search
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [quickFilter, setQuickFilter] = useState<string | null>(null);
  
  // Pagination & Sorting
  const [page, setPage] = useState(1);
  const [pageSize] = useState(100);
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  
  // Selection
  const [selectedProspects, setSelectedProspects] = useState<Prospect[]>([]);
  
  // Detail panel
  const [selectedProspect, setSelectedProspect] = useState<Prospect | null>(null);
  const [activities, setActivities] = useState<ProspectActivity[]>([]);
  const [loadingActivities, setLoadingActivities] = useState(false);
  
  // Dialogs
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({ isOpen: false, title: '', message: '', onConfirm: () => {} });
  
  // Import modal
  const [showImportModal, setShowImportModal] = useState(false);
  
  // Stats config - which stats to show
  const [visibleStats, setVisibleStats] = useState<string[]>(() => {
    const saved = localStorage.getItem('prospects_visible_stats');
    return saved ? JSON.parse(saved) : ['total', 'new', 'interested', 'call_done'];
  });
  const [showStatsConfig, setShowStatsConfig] = useState(false);
  const statsConfigRef = useRef<HTMLDivElement>(null);
  
  // Close stats config on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (statsConfigRef.current && !statsConfigRef.current.contains(event.target as Node)) {
        setShowStatsConfig(false);
      }
    };
    if (showStatsConfig) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showStatsConfig]);
  
  // Saved views
  const [savedViews, setSavedViews] = useState<Array<{
    id: string;
    name: string;
    filters: { quickFilter: string | null; search: string };
  }>>(() => {
    const saved = localStorage.getItem('prospects_saved_views');
    return saved ? JSON.parse(saved) : [];
  });
  const [showSaveViewModal, setShowSaveViewModal] = useState(false);
  const [newViewName, setNewViewName] = useState('');

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Load data
  const loadProspects = useCallback(async () => {
    setIsLoading(true);
    try {
      const filters: any = {};
      if (quickFilter === 'new') filters.status = 'new';
      if (quickFilter === 'contacted') filters.status = 'contacted';
      if (quickFilter === 'interested') filters.status = 'interested';
      if (quickFilter === 'not_sent_email') filters.sent_to_email = false;
      if (quickFilter === 'not_sent_linkedin') filters.sent_to_linkedin = false;

      const response = await prospectsApi.getProspects({
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
        search: debouncedSearch || undefined,
        ...filters
      });
      
      setProspects(response.prospects);
      setTotal(response.total);
    } catch (err) {
      console.error('Failed to load prospects:', err);
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, sortBy, sortOrder, debouncedSearch, quickFilter]);

  useEffect(() => {
    loadProspects();
  }, [loadProspects]);

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const data = await prospectsApi.getStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  };

  // Load activities when prospect selected
  useEffect(() => {
    if (selectedProspect) {
      loadActivities(selectedProspect.id);
    }
  }, [selectedProspect?.id]);

  const loadActivities = async (prospectId: number) => {
    setLoadingActivities(true);
    try {
      const data = await prospectsApi.getActivities(prospectId, 50);
      setActivities(data);
    } catch (err) {
      console.error('Failed to load activities:', err);
    } finally {
      setLoadingActivities(false);
    }
  };

  // AG Grid Column Definitions
  const columnDefs = useMemo<ColDef[]>(() => [
    {
      width: 50,
      pinned: 'left',
      lockPosition: true,
      suppressHeaderMenuButton: true,
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      sortable: true,
    },
    {
      field: 'email',
      headerName: 'Email',
      filter: 'agTextColumnFilter',
      sortable: true,
      width: 200,
    },
    {
      field: 'full_name',
      headerName: 'Name',
      filter: 'agTextColumnFilter',
      sortable: true,
      width: 200,
      wrapText: true,
      autoHeight: false,
      valueGetter: (params) => {
        const p = params.data as Prospect;
        return p?.full_name || `${p?.first_name || ''} ${p?.last_name || ''}`.trim() || '-';
      },
      cellStyle: {
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis'
      }
    },
    {
      field: 'company_name',
      headerName: 'Company',
      filter: 'agTextColumnFilter',
      sortable: true,
      width: 200,
      wrapText: true,
      autoHeight: false,
      cellStyle: {
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis'
      }
    },
    {
      field: 'job_title',
      headerName: 'Title',
      filter: 'agTextColumnFilter',
      sortable: true,
      width: 250,
      wrapText: true,
      autoHeight: false,
      cellStyle: {
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis'
      }
    },
    {
      field: 'segment_name',
      headerName: 'Segment',
      filter: 'agTextColumnFilter',
      sortable: true,
      width: 130,
      valueFormatter: (params: ValueFormatterParams) => params.value || '-',
    },
    {
      field: 'sent_to_email',
      headerName: '📧',
      headerTooltip: 'Sent to Email',
      width: 55,
      valueGetter: (params) => params.data?.sent_to_email ? '✓' : '-',
    },
    {
      field: 'sent_to_linkedin',
      headerName: '💼',
      headerTooltip: 'Sent to LinkedIn',
      width: 55,
      valueGetter: (params) => params.data?.sent_to_linkedin ? '✓' : '-',
    },
    {
      field: 'linkedin_url',
      headerName: 'LinkedIn',
      width: 150,
      filter: 'agTextColumnFilter',
      valueFormatter: (params: ValueFormatterParams) => params.value ? 'Link' : '-',
    },
    {
      field: 'phone',
      headerName: 'Phone',
      filter: 'agTextColumnFilter',
      width: 130,
      valueGetter: (params) => {
        const phone = params.data?.phone;
        // Filter out error messages
        if (!phone || phone.startsWith('[Not found') || phone.startsWith('[Error')) return '-';
        return phone;
      },
    },
    {
      field: 'location',
      headerName: 'Location',
      filter: 'agTextColumnFilter',
      width: 140,
      valueGetter: (params) => {
        const p = params.data as Prospect;
        return p?.location || p?.city || p?.country || '-';
      }
    },
    {
      field: 'tags',
      headerName: 'Tags',
      width: 130,
      valueFormatter: (params: ValueFormatterParams) => {
        const tags = params.value as string[];
        if (!tags || tags.length === 0) return '-';
        return tags.join(', ');
      }
    },
    {
      field: 'created_at',
      headerName: 'Added',
      sortable: true,
      width: 100,
      valueFormatter: (params: ValueFormatterParams) => {
        if (!params.value) return '-';
        return new Date(params.value).toLocaleDateString();
      }
    },
  ], []);

  // Default column settings
  const defaultColDef = useMemo<ColDef>(() => ({
    resizable: true,
    suppressMovable: false,
  }), []);

  // Grid events
  const onGridReady = useCallback((params: GridReadyEvent) => {
    setGridApi(params.api);
  }, []);

  const onSelectionChanged = useCallback((event: SelectionChangedEvent) => {
    const selected = event.api.getSelectedRows() as Prospect[];
    setSelectedProspects(selected);
  }, []);

  const onSortChanged = useCallback((event: SortChangedEvent) => {
    const sortModel = event.api.getColumnState().find(c => c.sort);
    if (sortModel) {
      setSortBy(sortModel.colId || 'created_at');
      setSortOrder(sortModel.sort as 'asc' | 'desc');
    }
  }, []);

  const onRowClicked = useCallback((event: any) => {
    if (event.data) {
      setSelectedProspect(event.data as Prospect);
    }
  }, []);

  // Actions
  const handleExportCsv = async () => {
    try {
      const ids = selectedProspects.length > 0 ? selectedProspects.map(p => p.id) : undefined;
      const blob = await prospectsApi.exportCsv(ids);
      
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'prospects.csv';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (err) {
      console.error('Failed to export:', err);
    }
  };

  const handleCopyToClipboard = async () => {
    try {
      const ids = selectedProspects.length > 0 ? selectedProspects.map(p => p.id) : undefined;
      const result = await prospectsApi.exportClipboard(ids);
      
      const tsv = result.data.map(row => row.join('\t')).join('\n');
      await navigator.clipboard.writeText(tsv);
      alert(`Copied ${result.row_count} prospects to clipboard!\n\nPaste directly into Google Sheets or Excel.`);
    } catch (err) {
      console.error('Failed to copy:', err);
      alert('Failed to copy to clipboard');
    }
  };

  const handleDeleteSelected = () => {
    if (selectedProspects.length === 0) return;
    
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Prospects',
      message: `Are you sure you want to delete ${selectedProspects.length} prospect(s)? This cannot be undone.`,
      onConfirm: async () => {
        try {
          await prospectsApi.deleteProspects(selectedProspects.map(p => p.id));
          setSelectedProspects([]);
          loadProspects();
          loadStats();
        } catch (err) {
          console.error('Failed to delete:', err);
        }
        setConfirmDialog(prev => ({ ...prev, isOpen: false }));
      }
    });
  };

  const handleRefresh = () => {
    loadProspects();
    loadStats();
  };

  // Quick filters
  const quickFilters = [
    { id: null, label: 'All' },
    { id: 'new', label: 'New' },
    { id: 'contacted', label: 'Contacted' },
    { id: 'interested', label: 'Interested' },
    { id: 'not_sent_email', label: 'Not Emailed' },
    { id: 'not_sent_linkedin', label: 'Not LI' },
  ];

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="h-full flex flex-col bg-neutral-50">
      {/* Header */}
      <div className="bg-white border-b border-neutral-200 px-6 py-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
              <Users className="w-5 h-5 text-violet-600" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-neutral-900">All Prospects</h1>
              <p className="text-sm text-neutral-500">
                {formatNumber(total)} prospects in your database
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button onClick={handleRefresh} className="btn btn-secondary btn-sm">
              <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
            </button>
            <button onClick={() => setShowImportModal(true)} className="btn btn-primary">
              <Upload className="w-4 h-4" />
              Import
            </button>
            <button onClick={handleCopyToClipboard} className="btn btn-secondary" title="Copy to clipboard for Google Sheets">
              <Copy className="w-4 h-4" />
              Copy
            </button>
            <button onClick={handleExportCsv} className="btn btn-secondary">
              <Download className="w-4 h-4" />
              Export
            </button>
            {selectedProspects.length > 0 && (
              <button onClick={handleDeleteSelected} className="btn btn-secondary text-red-600 hover:bg-red-50">
                <Trash2 className="w-4 h-4" />
                ({selectedProspects.length})
              </button>
            )}
          </div>
        </div>

        {/* Stats - Configurable */}
        {stats && (
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2 flex-wrap flex-1">
              {visibleStats.includes('total') && (
                <StatCard label="Total" value={formatNumber(stats.total_prospects)} />
              )}
              {visibleStats.includes('new') && (
                <StatCard label="New" value={formatNumber(stats.status_new)} color="gray" />
              )}
              {visibleStats.includes('contacted') && (
                <StatCard label="Contacted" value={formatNumber(stats.status_contacted)} color="blue" />
              )}
              {visibleStats.includes('interested') && (
                <StatCard label="Interested" value={formatNumber(stats.status_interested)} color="green" />
              )}
              {visibleStats.includes('call_done') && (
                <StatCard label="Call Done" value={formatNumber(stats.call_done)} color="purple" icon="📞" />
              )}
              {visibleStats.includes('not_interested') && (
                <StatCard label="Not Interested" value={formatNumber(stats.status_not_interested)} color="orange" />
              )}
              {visibleStats.includes('sent_email') && (
                <StatCard label="Email Sent" value={formatNumber(stats.sent_to_email)} />
              )}
              {visibleStats.includes('sent_linkedin') && (
                <StatCard label="LI Sent" value={formatNumber(stats.sent_to_linkedin)} />
              )}
              {visibleStats.includes('recent') && (
                <StatCard label="This Week" value={formatNumber(stats.recent_additions)} />
              )}
            </div>
            <div className="relative" ref={statsConfigRef}>
              <button
                onClick={() => setShowStatsConfig(!showStatsConfig)}
                className="p-2 hover:bg-neutral-100 rounded-lg text-neutral-400 hover:text-neutral-600"
                title="Configure stats"
              >
                <Settings2 className="w-4 h-4" />
              </button>
              {showStatsConfig && (
                <div className="absolute right-0 top-full mt-1 bg-white border border-neutral-200 rounded-xl shadow-lg p-3 z-50 w-48">
                  <div className="text-xs font-semibold text-neutral-500 uppercase mb-2">Show Stats</div>
                  {[
                    { id: 'total', label: 'Total' },
                    { id: 'new', label: 'New' },
                    { id: 'contacted', label: 'Contacted' },
                    { id: 'interested', label: 'Interested' },
                    { id: 'call_done', label: 'Call Done 📞' },
                    { id: 'not_interested', label: 'Not Interested' },
                    { id: 'sent_email', label: 'Email Sent' },
                    { id: 'sent_linkedin', label: 'LinkedIn Sent' },
                    { id: 'recent', label: 'This Week' },
                  ].map(stat => (
                    <label key={stat.id} className="flex items-center gap-2 py-1 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={visibleStats.includes(stat.id)}
                        onChange={(e) => {
                          const newStats = e.target.checked
                            ? [...visibleStats, stat.id]
                            : visibleStats.filter(s => s !== stat.id);
                          setVisibleStats(newStats);
                          localStorage.setItem('prospects_visible_stats', JSON.stringify(newStats));
                        }}
                        className="rounded"
                      />
                      <span className="text-sm">{stat.label}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Search & Filters */}
        <div className="flex items-center gap-3">
          {/* Saved Views Dropdown */}
          <div className="relative">
            <select
              value=""
              onChange={(e) => {
                const view = savedViews.find(v => v.id === e.target.value);
                if (view) {
                  setQuickFilter(view.filters.quickFilter);
                  setSearch(view.filters.search);
                }
              }}
              className="input pr-8 text-sm min-w-[120px]"
            >
              <option value="">Views</option>
              {savedViews.map(view => (
                <option key={view.id} value={view.id}>{view.name}</option>
              ))}
            </select>
            <Eye className="w-4 h-4 absolute right-2 top-1/2 -translate-y-1/2 text-neutral-400 pointer-events-none" />
          </div>
          
          {/* Save current view */}
          <button
            onClick={() => setShowSaveViewModal(true)}
            className="btn btn-secondary btn-sm"
            title="Save current view"
          >
            <Save className="w-4 h-4" />
          </button>

          <div className="relative flex-1 max-w-sm">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input pl-9 w-full text-sm"
            />
          </div>
          
          <div className="flex items-center gap-1 border-l border-neutral-200 pl-3">
            {quickFilters.map(filter => (
              <button
                key={filter.id || 'all'}
                onClick={() => setQuickFilter(filter.id)}
                className={cn(
                  "px-2.5 py-1 rounded-md text-xs font-medium transition-all",
                  quickFilter === filter.id
                    ? "bg-neutral-900 text-white"
                    : "text-neutral-600 hover:bg-neutral-100"
                )}
              >
                {filter.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* AG Grid */}
      <div className="flex-1 p-4">
        <div className="ag-theme-alpine h-full w-full rounded-xl overflow-hidden border border-neutral-200">
          <AgGridReact
            ref={gridRef}
            theme={AG_GRID_THEME}
            rowData={prospects}
            columnDefs={columnDefs}
            defaultColDef={defaultColDef}
            rowSelection={{
              mode: 'multiRow',
              enableClickSelection: false,
              headerCheckbox: true,
              checkboxes: true
            }}
            onGridReady={onGridReady}
            onSelectionChanged={onSelectionChanged}
            onSortChanged={onSortChanged}
            onRowClicked={onRowClicked}
            animateRows={true}
            rowHeight={48}
            headerHeight={48}
            suppressCellFocus={true}
            enableCellTextSelection={true}
            getRowId={(params) => String(params.data.id)}
            overlayLoadingTemplate='<span class="text-neutral-500">Loading prospects...</span>'
            overlayNoRowsTemplate='<span class="text-neutral-500">No prospects found</span>'
          />
        </div>
      </div>

      {/* Pagination */}
      <div className="bg-white border-t border-neutral-200 px-6 py-3 flex items-center justify-between">
        <div className="text-sm text-neutral-500">
          Showing {((page - 1) * pageSize) + 1} - {Math.min(page * pageSize, total)} of {formatNumber(total)}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage(1)}
            disabled={page === 1}
            className="btn btn-secondary btn-sm"
          >
            First
          </button>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="btn btn-secondary btn-sm"
          >
            Prev
          </button>
          <span className="text-sm text-neutral-600 px-3">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="btn btn-secondary btn-sm"
          >
            Next
          </button>
          <button
            onClick={() => setPage(totalPages)}
            disabled={page === totalPages}
            className="btn btn-secondary btn-sm"
          >
            Last
          </button>
        </div>
      </div>

      {/* Prospect Detail Panel */}
      {selectedProspect && (
        <ProspectDetailPanel
          prospect={selectedProspect}
          activities={activities}
          loadingActivities={loadingActivities}
          onClose={() => setSelectedProspect(null)}
          onUpdate={(updated) => {
            setSelectedProspect(updated);
            loadProspects();
          }}
          onDelete={() => {
            prospectsApi.deleteProspect(selectedProspect.id).then(() => {
              setSelectedProspect(null);
              loadProspects();
              loadStats();
            });
          }}
        />
      )}

      {/* Confirm Dialog */}
      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        title={confirmDialog.title}
        message={confirmDialog.message}
        onConfirm={confirmDialog.onConfirm}
        onCancel={() => setConfirmDialog(prev => ({ ...prev, isOpen: false }))}
      />

      {/* Save View Modal */}
      {showSaveViewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={() => setShowSaveViewModal(false)} />
          <div className="relative bg-white rounded-2xl shadow-xl p-6 w-full max-w-sm">
            <h3 className="text-lg font-semibold mb-4">Save Current View</h3>
            <input
              type="text"
              placeholder="View name..."
              value={newViewName}
              onChange={(e) => setNewViewName(e.target.value)}
              className="input w-full mb-4"
              autoFocus
            />
            <div className="flex gap-2">
              <button
                onClick={() => setShowSaveViewModal(false)}
                className="btn btn-secondary flex-1"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  if (newViewName.trim()) {
                    const newView = {
                      id: Date.now().toString(),
                      name: newViewName.trim(),
                      filters: { quickFilter, search }
                    };
                    const newViews = [...savedViews, newView];
                    setSavedViews(newViews);
                    localStorage.setItem('prospects_saved_views', JSON.stringify(newViews));
                    setNewViewName('');
                    setShowSaveViewModal(false);
                  }
                }}
                className="btn btn-primary flex-1"
                disabled={!newViewName.trim()}
              >
                <Save className="w-4 h-4" />
                Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Import Modal */}
      {showImportModal && (
        <ImportProspectsModal
          onClose={() => setShowImportModal(false)}
          onSuccess={() => {
            setShowImportModal(false);
            loadProspects();
            loadStats();
          }}
        />
      )}
    </div>
  );
}

// Stat card component
function StatCard({ label, value, color, icon }: { label: string; value: string; color?: string; icon?: string }) {
  const colorClasses: Record<string, string> = {
    gray: 'bg-gray-50 border-gray-200',
    blue: 'bg-blue-50 border-blue-200',
    green: 'bg-emerald-50 border-emerald-200',
    purple: 'bg-purple-50 border-purple-200',
    orange: 'bg-orange-50 border-orange-200',
    red: 'bg-red-50 border-red-200',
  };
  
  return (
    <div className={cn(
      "rounded-lg px-3 py-2 border",
      color ? colorClasses[color] || 'bg-neutral-50 border-neutral-100' : 'bg-neutral-50 border-neutral-100'
    )}>
      <div className="flex items-center gap-2">
        {icon && <span className="text-lg">{icon}</span>}
        <div className="text-lg font-semibold text-neutral-900">{value}</div>
      </div>
      <div className="text-xs text-neutral-500">{label}</div>
    </div>
  );
}

// Prospect detail panel
interface ProspectDetailPanelProps {
  prospect: Prospect;
  activities: ProspectActivity[];
  loadingActivities: boolean;
  onClose: () => void;
  onUpdate: (prospect: Prospect) => void;
  onDelete: () => void;
}

function ProspectDetailPanel({ 
  prospect, 
  activities, 
  loadingActivities,
  onClose, 
  onUpdate, 
  onDelete 
}: ProspectDetailPanelProps) {
  const [notes, setNotes] = useState(prospect.notes || '');
  const [tags, setTags] = useState<string[]>(prospect.tags || []);
  const [newTag, setNewTag] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);

  useEffect(() => {
    setNotes(prospect.notes || '');
    setTags(prospect.tags || []);
  }, [prospect.id]);

  const handleSaveNotes = async () => {
    setSavingNotes(true);
    try {
      const updated = await prospectsApi.updateNotes(prospect.id, notes);
      onUpdate(updated);
    } catch (err) {
      console.error('Failed to save notes:', err);
    } finally {
      setSavingNotes(false);
    }
  };

  const handleAddTag = async () => {
    if (!newTag.trim()) return;
    const newTags = [...tags, newTag.trim()];
    setTags(newTags);
    setNewTag('');
    try {
      const updated = await prospectsApi.updateTags(prospect.id, newTags);
      onUpdate(updated);
    } catch (err) {
      console.error('Failed to add tag:', err);
    }
  };

  const handleRemoveTag = async (tagToRemove: string) => {
    const newTags = tags.filter(t => t !== tagToRemove);
    setTags(newTags);
    try {
      const updated = await prospectsApi.updateTags(prospect.id, newTags);
      onUpdate(updated);
    } catch (err) {
      console.error('Failed to remove tag:', err);
    }
  };

  const activityIcon = (type: string) => {
    switch (type) {
      case 'added': return <Users className="w-4 h-4 text-emerald-500" />;
      case 'sent_instantly': return <Send className="w-4 h-4 text-blue-500" />;
      case 'updated': return <RefreshCw className="w-4 h-4 text-amber-500" />;
      case 'tagged': return <Tag className="w-4 h-4 text-violet-500" />;
      case 'note_added': return <FileText className="w-4 h-4 text-neutral-500" />;
      default: return <Clock className="w-4 h-4 text-neutral-400" />;
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 w-[500px] bg-white shadow-2xl border-l border-neutral-200 z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200">
        <h2 className="text-lg font-semibold">Prospect Details</h2>
        <button onClick={onClose} className="p-2 hover:bg-neutral-100 rounded-lg">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-auto p-6 space-y-6">
        {/* Name & Title */}
        <div>
          <h3 className="text-xl font-semibold text-neutral-900">
            {prospect.full_name || `${prospect.first_name || ''} ${prospect.last_name || ''}`.trim() || 'Unknown'}
          </h3>
          {prospect.job_title && (
            <p className="text-neutral-600 flex items-center gap-2 mt-1">
              <Briefcase className="w-4 h-4" />
              {prospect.job_title}
            </p>
          )}
          {prospect.company_name && (
            <p className="text-neutral-600 flex items-center gap-2 mt-1">
              <Building2 className="w-4 h-4" />
              {prospect.company_name}
              {prospect.company_domain && (
                <span className="text-neutral-400 text-sm">({prospect.company_domain})</span>
              )}
            </p>
          )}
        </div>

        {/* Status badges */}
        <div className="flex flex-wrap gap-2">
          {prospect.sent_to_email && (
            <span className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm flex items-center gap-1">
              <Send className="w-3 h-3" />
              Sent to {prospect.email_tool || 'Email'}
              {prospect.email_campaign_name && (
                <span className="text-blue-500">• {prospect.email_campaign_name}</span>
              )}
            </span>
          )}
          {prospect.sent_to_linkedin && (
            <span className="px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm flex items-center gap-1">
              <Send className="w-3 h-3" />
              Sent to LinkedIn
            </span>
          )}
        </div>

        {/* Contact Info */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">Contact</h4>
          
          {prospect.email && (
            <div className="flex items-center gap-3 p-3 bg-neutral-50 rounded-lg">
              <Mail className="w-4 h-4 text-neutral-400" />
              <a href={`mailto:${prospect.email}`} className="text-sm text-blue-600 hover:underline">
                {prospect.email}
              </a>
            </div>
          )}
          
          {prospect.linkedin_url && (
            <div className="flex items-center gap-3 p-3 bg-neutral-50 rounded-lg">
              <Linkedin className="w-4 h-4 text-neutral-400" />
              <a 
                href={prospect.linkedin_url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-sm text-blue-600 hover:underline flex items-center gap-1"
              >
                LinkedIn Profile
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          )}

          {prospect.phone && (
            <div className="flex items-center gap-3 p-3 bg-neutral-50 rounded-lg">
              <span className="text-neutral-400 text-sm">📞</span>
              <span className="text-sm">{prospect.phone}</span>
            </div>
          )}

          {(prospect.location || prospect.city || prospect.country) && (
            <div className="flex items-center gap-3 p-3 bg-neutral-50 rounded-lg">
              <MapPin className="w-4 h-4 text-neutral-400" />
              <span className="text-sm">
                {[prospect.city, prospect.location, prospect.country].filter(Boolean).join(', ')}
              </span>
            </div>
          )}
        </div>

        {/* Tags */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">Tags</h4>
          <div className="flex flex-wrap gap-2">
            {tags.map((tag, i) => (
              <span 
                key={i} 
                className="px-2 py-1 bg-violet-100 text-violet-700 rounded-lg text-sm flex items-center gap-1"
              >
                {tag}
                <button 
                  onClick={() => handleRemoveTag(tag)}
                  className="hover:text-violet-900"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
            <div className="flex items-center gap-1">
              <input
                type="text"
                value={newTag}
                onChange={(e) => setNewTag(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddTag()}
                placeholder="Add tag..."
                className="px-2 py-1 text-sm border border-neutral-200 rounded-lg w-24"
              />
              <button onClick={handleAddTag} className="btn btn-sm btn-secondary">
                <Tag className="w-3 h-3" />
              </button>
            </div>
          </div>
        </div>

        {/* Notes */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">Notes</h4>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add notes about this prospect..."
            rows={4}
            className="input w-full resize-none"
          />
          <button
            onClick={handleSaveNotes}
            disabled={savingNotes || notes === prospect.notes}
            className="btn btn-sm btn-secondary"
          >
            {savingNotes ? 'Saving...' : 'Save Notes'}
          </button>
        </div>

        {/* Custom Fields */}
        {prospect.custom_fields && Object.keys(prospect.custom_fields).length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">
              Custom Fields ({Object.keys(prospect.custom_fields).length})
            </h4>
            <div className="space-y-2">
              {Object.entries(prospect.custom_fields).map(([key, value]) => (
                <div key={key} className="p-3 bg-neutral-50 rounded-lg">
                  <div className="text-xs text-neutral-500">{key}</div>
                  <div className="text-sm font-medium break-words">{String(value)}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Activity Timeline */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">
            Activity ({activities.length})
          </h4>
          {loadingActivities ? (
            <div className="flex items-center justify-center py-4">
              <RefreshCw className="w-4 h-4 animate-spin text-neutral-400" />
            </div>
          ) : activities.length === 0 ? (
            <p className="text-sm text-neutral-400 italic">No activity recorded</p>
          ) : (
            <div className="space-y-2">
              {activities.map((activity) => (
                <div key={activity.id} className="flex items-start gap-3 p-3 bg-neutral-50 rounded-lg">
                  {activityIcon(activity.activity_type)}
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium">{activity.description || activity.activity_type}</div>
                    <div className="text-xs text-neutral-500">
                      {new Date(activity.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Sources */}
        {prospect.sources && prospect.sources.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">
              Sources ({prospect.sources.length})
            </h4>
            <div className="space-y-2">
              {prospect.sources.map((source, i) => (
                <div key={i} className="p-3 bg-neutral-50 rounded-lg">
                  <div className="text-sm font-medium">{source.dataset_name}</div>
                  <div className="text-xs text-neutral-500">
                    Added {new Date(source.added_at).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="p-4 border-t border-neutral-200">
        <button
          onClick={onDelete}
          className="btn btn-secondary text-red-600 hover:bg-red-50 w-full"
        >
          <Trash2 className="w-4 h-4" />
          Delete Prospect
        </button>
      </div>
    </div>
  );
}


// Import Prospects Modal
interface ImportProspectsModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

function ImportProspectsModal({ onClose, onSuccess }: ImportProspectsModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [step, setStep] = useState<'upload' | 'mapping' | 'done'>('upload');
  const [columns, setColumns] = useState<string[]>([]);
  const [sampleData, setSampleData] = useState<Record<string, any>[]>([]);
  const [mappings, setMappings] = useState<Array<{source: string, target: string}>>([]);
  const [result, setResult] = useState<{new: number, updated: number} | null>(null);
  const [error, setError] = useState<string | null>(null);

  const coreFields = [
    { name: 'email', label: 'Email' },
    { name: 'linkedin_url', label: 'LinkedIn URL' },
    { name: 'first_name', label: 'First Name' },
    { name: 'last_name', label: 'Last Name' },
    { name: 'full_name', label: 'Full Name' },
    { name: 'company_name', label: 'Company Name' },
    { name: 'company_domain', label: 'Company Domain' },
    { name: 'job_title', label: 'Job Title' },
    { name: 'phone', label: 'Phone' },
    { name: 'location', label: 'Location' },
    { name: 'country', label: 'Country' },
    { name: 'city', label: 'City' },
    { name: 'industry', label: 'Industry' },
    { name: 'website', label: 'Website' },
  ];

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;
    
    setFile(selectedFile);
    setError(null);
    
    // Parse CSV to get columns and sample data
    try {
      const text = await selectedFile.text();
      const lines = text.split('\n').filter(l => l.trim());
      if (lines.length === 0) {
        setError('Empty file');
        return;
      }
      
      const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
      setColumns(headers);
      
      // Get sample data (first 5 rows)
      const samples: Record<string, any>[] = [];
      for (let i = 1; i < Math.min(6, lines.length); i++) {
        const values = lines[i].split(',').map(v => v.trim().replace(/"/g, ''));
        const row: Record<string, any> = {};
        headers.forEach((h, idx) => {
          row[h] = values[idx] || '';
        });
        samples.push(row);
      }
      setSampleData(samples);
      
      // Auto-map columns using simple matching
      const autoMappings = headers.map(col => {
        const colLower = col.toLowerCase().replace(/[_\s-]/g, '');
        let target = 'custom';
        
        for (const field of coreFields) {
          const fieldLower = field.name.toLowerCase().replace(/[_\s-]/g, '');
          const labelLower = field.label.toLowerCase().replace(/[_\s-]/g, '');
          if (colLower.includes(fieldLower) || colLower.includes(labelLower) || 
              fieldLower.includes(colLower) || labelLower.includes(colLower)) {
            target = field.name;
            break;
          }
        }
        
        // Check sample data for email pattern
        if (target === 'custom' && samples.length > 0) {
          const sampleValue = samples[0][col];
          if (sampleValue && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(sampleValue)) {
            target = 'email';
          } else if (sampleValue && sampleValue.includes('linkedin.com')) {
            target = 'linkedin_url';
          }
        }
        
        return { source: col, target };
      });
      
      setMappings(autoMappings);
      setStep('mapping');
    } catch (err) {
      setError('Failed to parse CSV file');
    }
  };

  const handleImport = async () => {
    if (!file || mappings.length === 0) return;
    
    setIsUploading(true);
    setError(null);
    
    try {
      const text = await file.text();
      const lines = text.split('\n').filter(l => l.trim());
      const headers = lines[0].split(',').map(h => h.trim().replace(/"/g, ''));
      
      // Build rows data
      const rows: Record<string, any>[] = [];
      for (let i = 1; i < lines.length; i++) {
        const values = lines[i].split(',').map(v => v.trim().replace(/"/g, ''));
        const rowData: Record<string, any> = {};
        
        headers.forEach((header, idx) => {
          rowData[header] = values[idx] || '';
        });
        
        rows.push(rowData);
      }
      
      // Build field mappings for API
      const fieldMappings = mappings
        .filter(m => m.target !== 'skip')
        .map(m => ({
          source_column: m.source,
          target_field: m.target,
          custom_field_name: m.target === 'custom' ? m.source : undefined,
        }));
      
      // Call direct import API
      const response = await fetch('/api/prospects/import-direct', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows, field_mappings: fieldMappings })
      });
      
      if (!response.ok) {
        throw new Error('Import failed');
      }
      
      const result = await response.json();
      setResult({ new: result.new_prospects, updated: result.updated_prospects });
      setStep('done');
      
    } catch (err: any) {
      setError(err.message || 'Import failed');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
              <Upload className="w-5 h-5 text-violet-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">Import Prospects</h2>
              <p className="text-sm text-neutral-500">
                {step === 'upload' && 'Upload a CSV file'}
                {step === 'mapping' && 'Review field mapping'}
                {step === 'done' && 'Import complete'}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-neutral-100 rounded-lg">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {step === 'upload' && (
            <div className="flex flex-col items-center justify-center py-12">
              <input
                type="file"
                accept=".csv"
                onChange={handleFileSelect}
                className="hidden"
                id="csv-upload"
              />
              <label
                htmlFor="csv-upload"
                className="flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-neutral-300 rounded-2xl cursor-pointer hover:border-violet-400 hover:bg-violet-50/50 transition-all"
              >
                <Upload className="w-10 h-10 text-neutral-400 mb-3" />
                <span className="text-neutral-600 font-medium">Click to upload CSV</span>
                <span className="text-sm text-neutral-400 mt-1">or drag and drop</span>
              </label>
              {error && (
                <p className="text-red-500 text-sm mt-4">{error}</p>
              )}
            </div>
          )}

          {step === 'mapping' && (
            <div className="space-y-4">
              <div className="text-sm text-neutral-600 mb-4">
                {file?.name} • {columns.length} columns detected
              </div>
              
              <div className="space-y-2 max-h-[400px] overflow-auto">
                {mappings.map((mapping, idx) => (
                  <div key={mapping.source} className="flex items-center gap-3 p-3 bg-neutral-50 rounded-xl">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{mapping.source}</div>
                      {sampleData[0] && (
                        <div className="text-xs text-neutral-400 truncate">
                          e.g. {sampleData[0][mapping.source] || '-'}
                        </div>
                      )}
                    </div>
                    <span className="text-neutral-400">→</span>
                    <select
                      value={mapping.target}
                      onChange={(e) => {
                        const newMappings = [...mappings];
                        newMappings[idx].target = e.target.value;
                        setMappings(newMappings);
                      }}
                      className="input text-sm w-40"
                    >
                      <option value="skip">Skip</option>
                      <optgroup label="Standard Fields">
                        {coreFields.map(f => (
                          <option key={f.name} value={f.name}>{f.label}</option>
                        ))}
                      </optgroup>
                      <option value="custom">Custom Field</option>
                    </select>
                  </div>
                ))}
              </div>

              {error && (
                <p className="text-red-500 text-sm">{error}</p>
              )}
            </div>
          )}

          {step === 'done' && result && (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mb-4">
                <Check className="w-8 h-8 text-emerald-600" />
              </div>
              <h3 className="text-xl font-semibold mb-2">Import Successful!</h3>
              <div className="flex gap-8 text-center mt-4">
                <div>
                  <div className="text-3xl font-bold text-violet-600">{result.new}</div>
                  <div className="text-sm text-neutral-500">New prospects</div>
                </div>
                <div>
                  <div className="text-3xl font-bold text-amber-600">{result.updated}</div>
                  <div className="text-sm text-neutral-500">Updated</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-neutral-200 flex gap-3">
          {step === 'upload' && (
            <button onClick={onClose} className="btn btn-secondary flex-1">
              Cancel
            </button>
          )}
          {step === 'mapping' && (
            <>
              <button onClick={() => setStep('upload')} className="btn btn-secondary flex-1">
                Back
              </button>
              <button
                onClick={handleImport}
                disabled={isUploading}
                className="btn btn-primary flex-1"
              >
                {isUploading ? 'Importing...' : `Import ${columns.length > 0 ? sampleData.length : 0}+ Prospects`}
              </button>
            </>
          )}
          {step === 'done' && (
            <button onClick={onSuccess} className="btn btn-primary flex-1">
              Done
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
