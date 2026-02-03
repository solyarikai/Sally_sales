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
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

const AG_GRID_THEME = "legacy";
ModuleRegistry.registerModules([AllCommunityModule]);

import { 
  Users, Search, Download, Trash2, RefreshCw, 
  Plus, X, FolderOpen, Sparkles, FileText, Target, Mail, Loader2, ChevronRight, ChevronDown, Upload, AlertCircle, Check
} from 'lucide-react';
import { contactsApi, type Contact, type ContactStats, type FilterOptions, type Project, type AISDRProject, type ImportResult } from '../api';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { ContactDetailModal } from '../components/ContactDetailModal';
import { SectionErrorBoundary } from '../components/ErrorBoundary';
import { useToast } from '../components/Toast';
import { cn, formatNumber, getErrorMessage } from '../lib/utils';

export function ContactsPage() {
  const gridRef = useRef<AgGridReact>(null);
  const [, setGridApi] = useState<GridApi | null>(null);
  const toast = useToast();
  
  // Data
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [stats, setStats] = useState<ContactStats | null>(null);
  const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(null);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  
  // Filters
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [projectFilter, setProjectFilter] = useState<number | null>(null);
  const [segmentFilter, setSegmentFilter] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
  const [repliedFilter, setRepliedFilter] = useState<boolean | null>(null);
  const [smartleadFilter, setSmartleadFilter] = useState<boolean | null>(null);
  const [getsalesFilter, setGetsalesFilter] = useState<boolean | null>(null);
  
  // Contact Detail Modal
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [showContactModal, setShowContactModal] = useState(false);
  
  // Pagination & Sorting
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  
  // Selection
  const [selectedContacts, setSelectedContacts] = useState<Contact[]>([]);
  
  // Modals
  const [showAddModal, setShowAddModal] = useState(false);
  const [showProjectModal, setShowProjectModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  
  // Dialogs
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({ isOpen: false, title: '', message: '', onConfirm: () => {} });

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Load data
  const loadContacts = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await contactsApi.list({
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
        search: debouncedSearch || undefined,
        project_id: projectFilter || undefined,
        segment: segmentFilter || undefined,
        status: statusFilter || undefined,
        source: sourceFilter || undefined,
        has_replied: repliedFilter ?? undefined,
        has_smartlead: smartleadFilter ?? undefined,
        has_getsales: getsalesFilter ?? undefined,
      });
      
      setContacts(response.contacts);
      setTotal(response.total);
    } catch (err) {
      console.error('Failed to load contacts:', err);
      toast.error('Failed to load contacts', getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, sortBy, sortOrder, debouncedSearch, projectFilter, segmentFilter, statusFilter, sourceFilter, repliedFilter, smartleadFilter, getsalesFilter, toast]);

  useEffect(() => {
    loadContacts();
  }, [loadContacts]);

  useEffect(() => {
    loadStats();
    loadFilterOptions();
    loadProjects();
  }, []);

  const loadStats = async () => {
    try {
      const data = await contactsApi.getStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
      // Silent fail - stats are not critical
    }
  };

  const loadFilterOptions = async () => {
    try {
      const data = await contactsApi.getFilterOptions();
      setFilterOptions(data);
    } catch (err) {
      console.error('Failed to load filter options:', err);
      // Silent fail - filter options are not critical
    }
  };

  const loadProjects = async () => {
    try {
      const data = await contactsApi.listProjects();
      setProjects(data);
    } catch (err) {
      console.error('Failed to load projects:', err);
      toast.error('Failed to load projects', getErrorMessage(err));
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
      width: 110,
      sortable: true,
      cellRenderer: (params: any) => {
        const status = params.value as string;
        const colors: Record<string, string> = {
          lead: 'bg-gray-100 text-gray-700',
          contacted: 'bg-blue-100 text-blue-700',
          replied: 'bg-green-100 text-green-700',
          qualified: 'bg-purple-100 text-purple-700',
          customer: 'bg-emerald-100 text-emerald-700',
          lost: 'bg-red-100 text-red-700',
        };
        return `<span class="px-2 py-0.5 rounded text-xs font-medium ${colors[status] || 'bg-gray-100'}">${status}</span>`;
      }
    },
    {
      field: 'email',
      headerName: 'Email',
      filter: 'agTextColumnFilter',
      sortable: true,
      width: 220,
    },
    {
      headerName: 'Name',
      filter: 'agTextColumnFilter',
      sortable: true,
      width: 180,
      valueGetter: (params) => {
        const c = params.data as Contact;
        return `${c?.first_name || ''} ${c?.last_name || ''}`.trim() || '-';
      },
    },
    {
      field: 'company_name',
      headerName: 'Company',
      filter: 'agTextColumnFilter',
      sortable: true,
      width: 180,
    },
    {
      field: 'job_title',
      headerName: 'Title',
      filter: 'agTextColumnFilter',
      sortable: true,
      width: 180,
    },
    {
      field: 'segment',
      headerName: 'Segment',
      filter: 'agTextColumnFilter',
      sortable: true,
      width: 120,
      valueFormatter: (params: ValueFormatterParams) => params.value || '-',
    },
    {
      field: 'project_name',
      headerName: 'Project',
      filter: 'agTextColumnFilter',
      sortable: true,
      width: 130,
      valueFormatter: (params: ValueFormatterParams) => params.value || '-',
    },
    {
      field: 'source',
      headerName: 'Source',
      sortable: true,
      width: 100,
    },
    {
      field: 'location',
      headerName: 'Location',
      filter: 'agTextColumnFilter',
      width: 140,
      valueFormatter: (params: ValueFormatterParams) => params.value || '-',
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
    const selected = event.api.getSelectedRows() as Contact[];
    setSelectedContacts(selected);
  }, []);

  const onSortChanged = useCallback((event: SortChangedEvent) => {
    const sortModel = event.api.getColumnState().find(c => c.sort);
    if (sortModel) {
      setSortBy(sortModel.colId || 'created_at');
      setSortOrder(sortModel.sort as 'asc' | 'desc');
    }
  }, []);

  // Actions
  const handleExportCsv = async () => {
    try {
      const ids = selectedContacts.length > 0 ? selectedContacts.map(c => c.id) : undefined;
      const blob = await contactsApi.exportCsv(ids);
      
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'contacts.csv';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
      toast.success('Export complete', 'CSV file downloaded');
    } catch (err) {
      console.error('Failed to export:', err);
      toast.error('Export failed', getErrorMessage(err));
    }
  };

  const handleDeleteSelected = () => {
    if (selectedContacts.length === 0) return;
    
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Contacts',
      message: `Are you sure you want to delete ${selectedContacts.length} contact(s)? This cannot be undone.`,
      onConfirm: async () => {
        try {
          await contactsApi.deleteMany(selectedContacts.map(c => c.id));
          toast.success('Contacts deleted', `${selectedContacts.length} contact(s) removed`);
          setSelectedContacts([]);
          loadContacts();
          loadStats();
        } catch (err) {
          console.error('Failed to delete:', err);
          toast.error('Delete failed', getErrorMessage(err));
        }
        setConfirmDialog(prev => ({ ...prev, isOpen: false }));
      }
    });
  };

  const handleRefresh = () => {
    loadContacts();
    loadStats();
    loadFilterOptions();
  };

  const clearFilters = () => {
    setProjectFilter(null);
    setSegmentFilter(null);
    setStatusFilter(null);
    setSourceFilter(null);
    setSearch('');
  };

  const hasActiveFilters = projectFilter || segmentFilter || statusFilter || sourceFilter || repliedFilter !== null || smartleadFilter !== null || getsalesFilter !== null || search;
  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="h-full flex flex-col bg-neutral-50">
      {/* Header */}
      <div className="bg-white border-b border-neutral-200 px-6 py-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center">
              <Users className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-neutral-900">CRM Contacts</h1>
              <p className="text-sm text-neutral-500">
                {formatNumber(total)} contacts in your database
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button onClick={handleRefresh} className="btn btn-secondary btn-sm">
              <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
            </button>
            <button onClick={() => setShowProjectModal(true)} className="btn btn-secondary">
              <FolderOpen className="w-4 h-4" />
              Projects
            </button>
            <button onClick={() => setShowAddModal(true)} className="btn btn-primary">
              <Plus className="w-4 h-4" />
              Add Contact
            </button>
            <button onClick={() => setShowImportModal(true)} className="btn btn-secondary">
              <Upload className="w-4 h-4" />
              Import
            </button>
            <button onClick={handleExportCsv} className="btn btn-secondary">
              <Download className="w-4 h-4" />
              Export
            </button>
            {selectedContacts.length > 0 && (
              <button onClick={handleDeleteSelected} className="btn btn-secondary text-red-600 hover:bg-red-50">
                <Trash2 className="w-4 h-4" />
                ({selectedContacts.length})
              </button>
            )}
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="flex items-center gap-2 flex-wrap mb-4">
            <StatCard label="Total" value={formatNumber(stats.total)} />
            {Object.entries(stats.by_status || {}).slice(0, 5).map(([status, count]) => (
              <StatCard 
                key={status} 
                label={status} 
                value={formatNumber(count)} 
                color={status === 'qualified' ? 'purple' : status === 'replied' ? 'green' : status === 'contacted' ? 'blue' : 'gray'}
              />
            ))}
          </div>
        )}

        {/* Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 max-w-xs">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input
              type="text"
              placeholder="Search contacts..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input pl-9 w-full text-sm"
            />
          </div>
          
          {filterOptions && (
            <>
              <select
                value={projectFilter || ''}
                onChange={(e) => setProjectFilter(e.target.value ? Number(e.target.value) : null)}
                className="input text-sm min-w-[140px]"
              >
                <option value="">All Projects</option>
                {(filterOptions.projects || []).map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>

              <select
                value={segmentFilter || ''}
                onChange={(e) => setSegmentFilter(e.target.value || null)}
                className="input text-sm min-w-[130px]"
              >
                <option value="">All Segments</option>
                {(filterOptions.segments || []).map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>

              <select
                value={statusFilter || ''}
                onChange={(e) => setStatusFilter(e.target.value || null)}
                className="input text-sm min-w-[120px]"
              >
                <option value="">All Statuses</option>
                {(filterOptions.statuses || []).map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>

              <select
                value={sourceFilter || ''}
                onChange={(e) => setSourceFilter(e.target.value || null)}
                className="input text-sm min-w-[110px]"
              >
                <option value="">All Sources</option>
                {(filterOptions.sources || []).map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </>
          )}

          {/* Replied Filter */}
          <select
            className="px-3 py-2 border rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={repliedFilter === null ? '' : repliedFilter ? 'true' : 'false'}
            onChange={(e) => {
              const val = e.target.value;
              setRepliedFilter(val === '' ? null : val === 'true');
            }}
          >
            <option value="">All Contacts</option>
            <option value="true">Replied Only</option>
            <option value="false">Not Replied</option>
          </select>

          {/* Smartlead History Filter */}
          <select
            className="px-3 py-2 border rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-500"
            value={smartleadFilter === null ? '' : smartleadFilter ? 'true' : 'false'}
            onChange={(e) => {
              const val = e.target.value;
              setSmartleadFilter(val === '' ? null : val === 'true');
            }}
          >
            <option value="">Smartlead: All</option>
            <option value="true">In Smartlead</option>
            <option value="false">Not in Smartlead</option>
          </select>

          {/* GetSales History Filter */}
          <select
            className="px-3 py-2 border rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={getsalesFilter === null ? '' : getsalesFilter ? 'true' : 'false'}
            onChange={(e) => {
              const val = e.target.value;
              setGetsalesFilter(val === '' ? null : val === 'true');
            }}
          >
            <option value="">GetSales: All</option>
            <option value="true">In GetSales</option>
            <option value="false">Not in GetSales</option>
          </select>

          {hasActiveFilters && (
            <button onClick={clearFilters} className="btn btn-secondary btn-sm text-red-600">
              <X className="w-4 h-4" />
              Clear
            </button>
          )}
        </div>
      </div>

      {/* AG Grid */}
      <div className="flex-1 p-4">
        <SectionErrorBoundary>
        <div className="ag-theme-alpine h-full w-full rounded-xl overflow-hidden border border-neutral-200">
          <AgGridReact
            ref={gridRef}
            theme={AG_GRID_THEME}
            onRowClicked={(event) => {
              if (event.data) {
                setSelectedContact(event.data);
                setShowContactModal(true);
              }
            }}
            rowData={contacts}
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
            animateRows={true}
            rowHeight={44}
            headerHeight={44}
            suppressCellFocus={true}
            enableCellTextSelection={true}
            getRowId={(params) => String(params.data.id)}
            overlayLoadingTemplate='<span class="text-neutral-500">Loading contacts...</span>'
            overlayNoRowsTemplate='<span class="text-neutral-500">No contacts found</span>'
          />
        </div>
        </SectionErrorBoundary>
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
            Page {page} of {totalPages || 1}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages || totalPages === 0}
            className="btn btn-secondary btn-sm"
          >
            Next
          </button>
          <button
            onClick={() => setPage(totalPages)}
            disabled={page === totalPages || totalPages === 0}
            className="btn btn-secondary btn-sm"
          >
            Last
          </button>
        </div>
      </div>

      {/* Add Contact Modal */}
      {showAddModal && (
        <AddContactModal
          projects={projects}
          filterOptions={filterOptions}
          onClose={() => setShowAddModal(false)}
          onSuccess={() => {
            setShowAddModal(false);
            loadContacts();
            loadStats();
          }}
        />
      )}

      {/* Projects Modal */}
      {showProjectModal && (
        <ProjectsModal
          projects={projects}
          onClose={() => setShowProjectModal(false)}
          onUpdate={loadProjects}
        />
      )}

      {/* Import Modal */}
      {showImportModal && (
        <ImportContactsModal
          projects={projects}
          filterOptions={filterOptions}
          onClose={() => setShowImportModal(false)}
          onSuccess={() => {
            setShowImportModal(false);
            loadContacts();
            loadStats();
            loadFilterOptions();
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

      {/* Contact Detail Modal */}
      <ContactDetailModal
        contact={selectedContact}
        isOpen={showContactModal}
        onClose={() => {
          setShowContactModal(false);
          setSelectedContact(null);
        }}
      />
    </div>
  );
}

// Stat card component
function StatCard({ label, value, color }: { label: string; value: string; color?: string }) {
  const colorClasses: Record<string, string> = {
    gray: 'bg-gray-50 border-gray-200',
    blue: 'bg-blue-50 border-blue-200',
    green: 'bg-emerald-50 border-emerald-200',
    purple: 'bg-purple-50 border-purple-200',
  };
  
  return (
    <div className={cn(
      "rounded-lg px-3 py-2 border",
      color ? colorClasses[color] || 'bg-neutral-50 border-neutral-100' : 'bg-neutral-50 border-neutral-100'
    )}>
      <div className="text-lg font-semibold text-neutral-900">{value}</div>
      <div className="text-xs text-neutral-500 capitalize">{label}</div>
    </div>
  );
}

// Add Contact Modal
function AddContactModal({ 
  projects, 
  filterOptions,
  onClose, 
  onSuccess 
}: { 
  projects: Project[];
  filterOptions: FilterOptions | null;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const toast = useToast();
  const [formData, setFormData] = useState({
    email: '',
    first_name: '',
    last_name: '',
    company_name: '',
    job_title: '',
    segment: '',
    project_id: '',
    status: 'lead',
    source: 'manual',
    phone: '',
    linkedin_url: '',
    location: '',
    notes: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.email) {
      setError('Email is required');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await contactsApi.create({
        ...formData,
        project_id: formData.project_id ? Number(formData.project_id) : undefined,
      });
      toast.success('Contact created', `${formData.email} added successfully`);
      onSuccess();
    } catch (err: unknown) {
      const message = getErrorMessage(err);
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200">
          <h2 className="text-lg font-semibold">Add Contact</h2>
          <button onClick={onClose} className="p-2 hover:bg-neutral-100 rounded-lg">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-auto p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Email *</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="input w-full"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Status</label>
              <select
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                className="input w-full"
              >
                {filterOptions?.statuses.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">First Name</label>
              <input
                type="text"
                value={formData.first_name}
                onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Last Name</label>
              <input
                type="text"
                value={formData.last_name}
                onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                className="input w-full"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Company</label>
              <input
                type="text"
                value={formData.company_name}
                onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Job Title</label>
              <input
                type="text"
                value={formData.job_title}
                onChange={(e) => setFormData({ ...formData, job_title: e.target.value })}
                className="input w-full"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Project</label>
              <select
                value={formData.project_id}
                onChange={(e) => setFormData({ ...formData, project_id: e.target.value })}
                className="input w-full"
              >
                <option value="">No Project</option>
                {projects.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Segment</label>
              <select
                value={formData.segment}
                onChange={(e) => setFormData({ ...formData, segment: e.target.value })}
                className="input w-full"
              >
                <option value="">Select Segment</option>
                {filterOptions?.segments.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Phone</label>
              <input
                type="text"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Location</label>
              <input
                type="text"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                className="input w-full"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">LinkedIn URL</label>
            <input
              type="url"
              value={formData.linkedin_url}
              onChange={(e) => setFormData({ ...formData, linkedin_url: e.target.value })}
              className="input w-full"
              placeholder="https://linkedin.com/in/..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">Notes</label>
            <textarea
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              className="input w-full"
              rows={3}
            />
          </div>

          {error && (
            <div className="text-red-500 text-sm">{error}</div>
          )}
        </form>

        <div className="px-6 py-4 border-t border-neutral-200 flex gap-3">
          <button onClick={onClose} className="btn btn-secondary flex-1">
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="btn btn-primary flex-1"
          >
            {isSubmitting ? 'Creating...' : 'Add Contact'}
          </button>
        </div>
      </div>
    </div>
  );
}

// Projects Modal with AI SDR Dashboard
function ProjectsModal({ 
  projects, 
  onClose, 
  onUpdate 
}: { 
  projects: Project[];
  onClose: () => void;
  onUpdate: () => void;
}) {
  const toast = useToast();
  const [newProjectName, setNewProjectName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [selectedProject, setSelectedProject] = useState<AISDRProject | null>(null);
  const [isLoadingProject, setIsLoadingProject] = useState(false);
  const [isGenerating, setIsGenerating] = useState<string | null>(null);
  const [expandedSection, setExpandedSection] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);

  const handleCreate = async () => {
    if (!newProjectName.trim()) return;

    setIsCreating(true);
    try {
      await contactsApi.createProject({ name: newProjectName.trim() });
      toast.success('Project created', `"${newProjectName}" is ready to use`);
      setNewProjectName('');
      onUpdate();
    } catch (err) {
      console.error('Failed to create project:', err);
      toast.error('Failed to create project', getErrorMessage(err));
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async (id: number) => {
    setConfirmDeleteId(id);
  };

  const confirmDelete = async () => {
    if (!confirmDeleteId) return;
    
    try {
      await contactsApi.deleteProject(confirmDeleteId);
      toast.success('Project deleted', 'Contacts remain but are no longer assigned');
      if (selectedProject?.id === confirmDeleteId) {
        setSelectedProject(null);
      }
      onUpdate();
    } catch (err) {
      console.error('Failed to delete project:', err);
      toast.error('Failed to delete project', getErrorMessage(err));
    } finally {
      setConfirmDeleteId(null);
    }
  };

  const loadProjectAISDR = async (projectId: number) => {
    setIsLoadingProject(true);
    try {
      const data = await contactsApi.getProjectAISDR(projectId);
      setSelectedProject(data);
    } catch (err) {
      console.error('Failed to load project AI SDR:', err);
      toast.error('Failed to load project', getErrorMessage(err));
    } finally {
      setIsLoadingProject(false);
    }
  };

  const handleGenerateTAM = async () => {
    if (!selectedProject) return;
    setIsGenerating('tam');
    try {
      const result = await contactsApi.generateTAM(selectedProject.id);
      setSelectedProject(prev => prev ? { ...prev, tam_analysis: result.tam_analysis } : null);
      toast.success('TAM Analysis generated', 'Market analysis is ready');
    } catch (err: unknown) {
      toast.error('Failed to generate TAM', getErrorMessage(err));
    } finally {
      setIsGenerating(null);
    }
  };

  const handleGenerateGTM = async () => {
    if (!selectedProject) return;
    setIsGenerating('gtm');
    try {
      const result = await contactsApi.generateGTM(selectedProject.id);
      setSelectedProject(prev => prev ? { ...prev, gtm_plan: result.gtm_plan } : null);
      toast.success('GTM Plan generated', 'Go-to-market strategy is ready');
    } catch (err: unknown) {
      toast.error('Failed to generate GTM plan', getErrorMessage(err));
    } finally {
      setIsGenerating(null);
    }
  };

  const handleGeneratePitches = async () => {
    if (!selectedProject) return;
    setIsGenerating('pitches');
    try {
      const result = await contactsApi.generatePitches(selectedProject.id);
      setSelectedProject(prev => prev ? { ...prev, pitch_templates: result.pitch_templates } : null);
      toast.success('Pitch templates generated', 'Email templates are ready');
    } catch (err: unknown) {
      toast.error('Failed to generate pitches', getErrorMessage(err));
    } finally {
      setIsGenerating(null);
    }
  };

  const handleGenerateAll = async () => {
    if (!selectedProject) return;
    setIsGenerating('all');
    try {
      const result = await contactsApi.generateAllAISDR(selectedProject.id);
      setSelectedProject(prev => prev ? { 
        ...prev, 
        tam_analysis: result.tam_analysis,
        gtm_plan: result.gtm_plan,
        pitch_templates: result.pitch_templates,
      } : null);
      toast.success('AI SDR content generated', 'TAM, GTM, and pitches are ready');
    } catch (err: unknown) {
      toast.error('Failed to generate AI SDR content', getErrorMessage(err));
    } finally {
      setIsGenerating(null);
    }
  };

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-100 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">AI SDR Dashboard</h2>
              <p className="text-sm text-neutral-500">Generate TAM, GTM plans, and pitch templates per project</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-neutral-100 rounded-lg">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-hidden flex">
          {/* Left panel - Projects list */}
          <div className="w-1/3 border-r border-neutral-200 overflow-auto">
            <div className="p-4 border-b border-neutral-200">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  placeholder="New project..."
                  className="input flex-1 text-sm"
                  onKeyPress={(e) => e.key === 'Enter' && handleCreate()}
                />
                <button
                  onClick={handleCreate}
                  disabled={isCreating || !newProjectName.trim()}
                  className="btn btn-primary btn-sm"
                >
                  <Plus className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="p-2">
              {projects.length === 0 ? (
                <div className="text-center py-8 text-neutral-500 text-sm">
                  No projects yet
                </div>
              ) : (
                projects.map(project => (
                  <div 
                    key={project.id} 
                    className={cn(
                      "flex items-center justify-between p-3 rounded-xl cursor-pointer transition-colors mb-1",
                      selectedProject?.id === project.id 
                        ? "bg-purple-50 border border-purple-200" 
                        : "hover:bg-neutral-50"
                    )}
                    onClick={() => loadProjectAISDR(project.id)}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm truncate">{project.name}</div>
                      <div className="text-xs text-neutral-500">{project.contact_count} contacts</div>
                    </div>
                    <div className="flex items-center gap-1">
                      {confirmDeleteId === project.id ? (
                        <>
                          <button
                            onClick={(e) => { e.stopPropagation(); confirmDelete(); }}
                            className="p-1.5 text-white bg-red-500 hover:bg-red-600 rounded-lg text-xs font-medium"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(null); }}
                            className="p-1.5 text-neutral-500 hover:bg-neutral-100 rounded-lg"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleDelete(project.id); }}
                            className="p-1.5 text-red-500 hover:bg-red-50 rounded-lg"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                          <ChevronRight className="w-4 h-4 text-neutral-400" />
                        </>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Right panel - AI SDR Content */}
          <div className="flex-1 overflow-auto">
            {isLoadingProject ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="w-6 h-6 animate-spin text-purple-600" />
              </div>
            ) : selectedProject ? (
              <div className="p-6">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h3 className="text-lg font-semibold">{selectedProject.name}</h3>
                    <p className="text-sm text-neutral-500">{selectedProject.contact_count} contacts in project</p>
                  </div>
                  <button
                    onClick={handleGenerateAll}
                    disabled={isGenerating !== null || selectedProject.contact_count === 0}
                    className="btn btn-primary"
                  >
                    {isGenerating === 'all' ? (
                      <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
                    ) : (
                      <><Sparkles className="w-4 h-4" /> Generate All</>
                    )}
                  </button>
                </div>

                {selectedProject.contact_count === 0 ? (
                  <div className="text-center py-12 text-neutral-500">
                    <Users className="w-12 h-12 mx-auto mb-3 opacity-50" />
                    <p>Add contacts to this project first</p>
                    <p className="text-sm mt-1">AI SDR needs contact data to generate insights</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* TAM Analysis */}
                    <AISDRSection
                      title="TAM Analysis"
                      subtitle="Total Addressable Market"
                      icon={<Target className="w-4 h-4" />}
                      content={selectedProject.tam_analysis}
                      isGenerating={isGenerating === 'tam'}
                      isExpanded={expandedSection === 'tam'}
                      onToggle={() => toggleSection('tam')}
                      onGenerate={handleGenerateTAM}
                      disabled={isGenerating !== null}
                    />

                    {/* GTM Plan */}
                    <AISDRSection
                      title="GTM Plan"
                      subtitle="Go-To-Market Strategy"
                      icon={<FileText className="w-4 h-4" />}
                      content={selectedProject.gtm_plan}
                      isGenerating={isGenerating === 'gtm'}
                      isExpanded={expandedSection === 'gtm'}
                      onToggle={() => toggleSection('gtm')}
                      onGenerate={handleGenerateGTM}
                      disabled={isGenerating !== null}
                    />

                    {/* Pitch Templates */}
                    <AISDRSection
                      title="Pitch Templates"
                      subtitle="Email Templates"
                      icon={<Mail className="w-4 h-4" />}
                      content={selectedProject.pitch_templates}
                      isGenerating={isGenerating === 'pitches'}
                      isExpanded={expandedSection === 'pitches'}
                      onToggle={() => toggleSection('pitches')}
                      onGenerate={handleGeneratePitches}
                      disabled={isGenerating !== null}
                    />
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-neutral-500">
                <div className="text-center">
                  <FolderOpen className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>Select a project to view AI SDR content</p>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="px-6 py-4 border-t border-neutral-200">
          <button onClick={onClose} className="btn btn-secondary w-full">
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

// AI SDR Section Component
function AISDRSection({
  title,
  subtitle,
  icon,
  content,
  isGenerating,
  isExpanded,
  onToggle,
  onGenerate,
  disabled,
}: {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  content?: string;
  isGenerating: boolean;
  isExpanded: boolean;
  onToggle: () => void;
  onGenerate: () => void;
  disabled: boolean;
}) {
  return (
    <div className="border border-neutral-200 rounded-xl overflow-hidden">
      <div 
        className="flex items-center justify-between p-4 bg-neutral-50 cursor-pointer"
        onClick={onToggle}
      >
        <div className="flex items-center gap-3">
          <div className={cn(
            "w-8 h-8 rounded-lg flex items-center justify-center",
            content ? "bg-green-100 text-green-600" : "bg-neutral-100 text-neutral-500"
          )}>
            {icon}
          </div>
          <div>
            <div className="font-medium text-sm">{title}</div>
            <div className="text-xs text-neutral-500">{subtitle}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {content ? (
            <span className="text-xs text-green-600 bg-green-50 px-2 py-1 rounded">Generated</span>
          ) : (
            <button
              onClick={(e) => { e.stopPropagation(); onGenerate(); }}
              disabled={disabled}
              className="btn btn-secondary btn-sm"
            >
              {isGenerating ? (
                <><Loader2 className="w-3 h-3 animate-spin" /> Generating</>
              ) : (
                <><Sparkles className="w-3 h-3" /> Generate</>
              )}
            </button>
          )}
          {content && (
            isExpanded ? <ChevronDown className="w-4 h-4 text-neutral-400" /> : <ChevronRight className="w-4 h-4 text-neutral-400" />
          )}
        </div>
      </div>
      {isExpanded && content && (
        <div className="p-4 border-t border-neutral-200 bg-white">
          <div className="prose prose-sm max-w-none whitespace-pre-wrap text-neutral-700">
            {content}
          </div>
          <div className="mt-4 flex justify-end">
            <button
              onClick={onGenerate}
              disabled={disabled}
              className="btn btn-secondary btn-sm"
            >
              {isGenerating ? (
                <><Loader2 className="w-3 h-3 animate-spin" /> Regenerating</>
              ) : (
                <><RefreshCw className="w-3 h-3" /> Regenerate</>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Import Contacts Modal
function ImportContactsModal({
  projects,
  filterOptions,
  onClose,
  onSuccess,
}: {
  projects: Project[];
  filterOptions: FilterOptions | null;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [projectId, setProjectId] = useState<number | undefined>(undefined);
  const [segment, setSegment] = useState<string>('');
  const [skipDuplicates, setSkipDuplicates] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (!selectedFile.name.toLowerCase().endsWith('.csv')) {
        setError('Please select a CSV file');
        return;
      }
      setFile(selectedFile);
      setError(null);
      setResult(null);
    }
  };

  const handleDownloadTemplate = async () => {
    try {
      const blob = await contactsApi.getImportTemplate();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'contacts_import_template.csv';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (err) {
      console.error('Failed to download template:', err);
      toast.error('Download failed', getErrorMessage(err));
    }
  };

  const handleImport = async () => {
    if (!file) {
      setError('Please select a file');
      return;
    }

    setIsUploading(true);
    setError(null);
    setResult(null);

    try {
      const importResult = await contactsApi.importCsv(file, {
        project_id: projectId,
        segment: segment || undefined,
        skip_duplicates: skipDuplicates,
      });
      setResult(importResult);
      
      if (importResult.created > 0) {
        toast.success('Import successful', `${importResult.created} contacts imported`);
        // Auto-close after successful import with delay
        setTimeout(() => {
          onSuccess();
        }, 2000);
      } else if (importResult.skipped > 0) {
        toast.warning('No new contacts', `${importResult.skipped} duplicates skipped`);
      }
    } catch (err: unknown) {
      const message = getErrorMessage(err);
      setError(message);
      toast.error('Import failed', message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center">
              <Upload className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">Import Contacts</h2>
              <p className="text-sm text-neutral-500">Upload a CSV file with contact data</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-neutral-100 rounded-lg">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-6 space-y-6">
          {/* File Upload Area */}
          <div>
            <div 
              className={cn(
                "border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer",
                file 
                  ? "border-green-300 bg-green-50" 
                  : "border-neutral-200 hover:border-indigo-300 hover:bg-indigo-50/30"
              )}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileChange}
                className="hidden"
              />
              
              {file ? (
                <div className="flex items-center justify-center gap-3">
                  <Check className="w-6 h-6 text-green-600" />
                  <div className="text-left">
                    <p className="font-medium text-green-700">{file.name}</p>
                    <p className="text-sm text-green-600">{(file.size / 1024).toFixed(1)} KB</p>
                  </div>
                </div>
              ) : (
                <>
                  <Upload className="w-10 h-10 text-neutral-400 mx-auto mb-3" />
                  <p className="text-sm text-neutral-600 mb-1">Click to select a CSV file</p>
                  <p className="text-xs text-neutral-400">or drag and drop</p>
                </>
              )}
            </div>
            
            <button 
              onClick={handleDownloadTemplate}
              className="mt-2 text-sm text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
            >
              <Download className="w-3 h-3" />
              Download CSV template
            </button>
          </div>

          {/* Import Options */}
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">
                Assign to Project (optional)
              </label>
              <select
                value={projectId || ''}
                onChange={(e) => setProjectId(e.target.value ? Number(e.target.value) : undefined)}
                className="input w-full"
              >
                <option value="">No project</option>
                {projects.map(p => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">
                Assign Segment (optional)
              </label>
              <select
                value={segment}
                onChange={(e) => setSegment(e.target.value)}
                className="input w-full"
              >
                <option value="">Keep from CSV / None</option>
                {filterOptions?.segments.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <p className="text-xs text-neutral-500 mt-1">
                This will override the segment column in CSV
              </p>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="skipDuplicates"
                checked={skipDuplicates}
                onChange={(e) => setSkipDuplicates(e.target.checked)}
                className="rounded border-neutral-300"
              />
              <label htmlFor="skipDuplicates" className="text-sm text-neutral-700">
                Skip duplicate emails (recommended)
              </label>
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <div className="flex items-start gap-2 p-4 rounded-xl bg-red-50 text-red-700">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="text-sm">{error}</div>
            </div>
          )}

          {/* Results Display */}
          {result && (
            <div className={cn(
              "p-4 rounded-xl",
              result.created > 0 ? "bg-green-50" : "bg-amber-50"
            )}>
              <div className="flex items-center gap-2 mb-3">
                {result.created > 0 ? (
                  <Check className="w-5 h-5 text-green-600" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-amber-600" />
                )}
                <span className={cn(
                  "font-medium",
                  result.created > 0 ? "text-green-700" : "text-amber-700"
                )}>
                  Import {result.created > 0 ? 'Complete' : 'Results'}
                </span>
              </div>
              
              <div className="grid grid-cols-3 gap-4 mb-3">
                <div className="text-center p-2 bg-white rounded-lg">
                  <div className="text-lg font-semibold text-green-600">{result.created}</div>
                  <div className="text-xs text-neutral-500">Created</div>
                </div>
                <div className="text-center p-2 bg-white rounded-lg">
                  <div className="text-lg font-semibold text-amber-600">{result.skipped}</div>
                  <div className="text-xs text-neutral-500">Skipped</div>
                </div>
                <div className="text-center p-2 bg-white rounded-lg">
                  <div className="text-lg font-semibold text-red-600">{result.errors.length}</div>
                  <div className="text-xs text-neutral-500">Errors</div>
                </div>
              </div>

              {result.sample_created.length > 0 && (
                <div className="text-xs text-neutral-600">
                  <span className="font-medium">Sample imported:</span>{' '}
                  {result.sample_created.slice(0, 3).join(', ')}
                  {result.sample_created.length > 3 && '...'}
                </div>
              )}

              {result.errors.length > 0 && (
                <div className="mt-3 p-2 bg-red-50 rounded-lg text-xs text-red-600 max-h-24 overflow-auto">
                  {result.errors.slice(0, 5).map((errMsg: string, i: number) => (
                    <div key={i}>{errMsg}</div>
                  ))}
                  {result.errors.length > 5 && (
                    <div className="mt-1 font-medium">...and {result.errors.length - 5} more errors</div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="px-6 py-4 border-t border-neutral-200 flex gap-3">
          <button onClick={onClose} className="btn btn-secondary flex-1">
            {result?.created ? 'Close' : 'Cancel'}
          </button>
          {!result?.created && (
            <button
              onClick={handleImport}
              disabled={!file || isUploading}
              className="btn btn-primary flex-1"
            >
              {isUploading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Importing...</>
              ) : (
                <><Upload className="w-4 h-4" /> Import Contacts</>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
