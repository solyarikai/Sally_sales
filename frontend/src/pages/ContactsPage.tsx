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
  Plus, X, FolderOpen, Sparkles, FileText, Target, Mail, Loader2, ChevronRight, ChevronDown, Upload, AlertCircle, Check,
  MessageSquare, ListTodo, Save, Edit3, ChevronLeft
} from 'lucide-react';
import { contactsApi, type Contact, type ContactStats, type FilterOptions, type Project, type AISDRProject, type ImportResult, type OperatorTask } from '../api';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { ContactDetailModal } from '../components/ContactDetailModal';
import { SectionErrorBoundary } from '../components/ErrorBoundary';
import { useToast } from '../components/Toast';
import { ContactsFilterContext, CampaignColumnFilter, StatusColumnFilter, DateColumnFilter } from '../components/filters';
import { cn, formatNumber, getErrorMessage } from '../lib/utils';

// Status configuration — proper lead statuses (no "replied" — that's a flag, not a status)
const STATUS_CONFIG: Record<string, { dot: string; label: string; colors: string }> = {
  touched:           { dot: 'bg-blue-500',    label: 'Touched',         colors: 'bg-blue-100 text-blue-700' },
  warm:              { dot: 'bg-amber-500',   label: 'Warm',            colors: 'bg-amber-100 text-amber-700' },
  not_interested:    { dot: 'bg-gray-400',    label: 'Not Interested',  colors: 'bg-gray-100 text-gray-600' },
  wrong_person:      { dot: 'bg-red-400',     label: 'Wrong Person',    colors: 'bg-red-100 text-red-600' },
  out_of_office:     { dot: 'bg-yellow-400',  label: 'OOO',             colors: 'bg-yellow-100 text-yellow-700' },
  other:             { dot: 'bg-purple-400',  label: 'Other',           colors: 'bg-purple-100 text-purple-600' },
  qualified:         { dot: 'bg-emerald-500', label: 'Qualified',       colors: 'bg-emerald-100 text-emerald-700' },
  customer:          { dot: 'bg-emerald-600', label: 'Customer',        colors: 'bg-emerald-100 text-emerald-700' },
  lost:              { dot: 'bg-red-500',     label: 'Lost',            colors: 'bg-red-100 text-red-600' },
};

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

  // Filters — compact command-bar style
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [statusFilters, setStatusFilters] = useState<string[]>([]);
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
  const [campaignFilters, setCampaignFilters] = useState<string[]>([]);
  const [campaignSearch, setCampaignSearch] = useState('');
  const [campaignDropdownOpen, setCampaignDropdownOpen] = useState(false);
  const campaignRef = useRef<HTMLDivElement>(null);
  const [campaigns, setCampaigns] = useState<Array<{name: string, source: string}>>([]);
  const [followupFilter, setFollowupFilter] = useState<boolean | null>(null);
  const [repliedFilter, setRepliedFilter] = useState<boolean | null>(null);
  const [createdAfter, setCreatedAfter] = useState<string | null>(null);
  const [createdBefore, setCreatedBefore] = useState<string | null>(null);

  // Contact Detail Modal
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [showContactModal, setShowContactModal] = useState(false);

  // Project view
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [projectDropdownOpen, setProjectDropdownOpen] = useState(false);
  const projectRef = useRef<HTMLDivElement>(null);
  const [showSaveProjectForm, setShowSaveProjectForm] = useState(false);
  const [newProjectName, setNewProjectName] = useState('');
  const [editingProject, setEditingProject] = useState(false);
  const [editProjectName, setEditProjectName] = useState('');
  const [editCampaignFilters, setEditCampaignFilters] = useState<string[]>([]);

  // Reply processing mode
  const [replyMode, setReplyMode] = useState(false);
  const [replyContactIndex, setReplyContactIndex] = useState(0);
  const [processedContacts, setProcessedContacts] = useState<Set<number>>(new Set());

  // Tasks
  const [showTasksPanel, setShowTasksPanel] = useState(false);
  const [tasks, setTasks] = useState<OperatorTask[]>([]);
  const [tasksLoading, setTasksLoading] = useState(false);

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

  // Close dropdowns on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (campaignRef.current && !campaignRef.current.contains(e.target as Node)) {
        setCampaignDropdownOpen(false);
      }
      if (projectRef.current && !projectRef.current.contains(e.target as Node)) {
        setProjectDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Load processed contacts from localStorage
  useEffect(() => {
    if (activeProject) {
      const key = `project:${activeProject.id}:processed`;
      try {
        const stored = localStorage.getItem(key);
        if (stored) setProcessedContacts(new Set(JSON.parse(stored)));
        else setProcessedContacts(new Set());
      } catch { setProcessedContacts(new Set()); }
    } else {
      setProcessedContacts(new Set());
    }
  }, [activeProject]);

  // Save processed contacts to localStorage
  const markProcessed = useCallback((contactId: number) => {
    setProcessedContacts(prev => {
      const next = new Set(prev);
      next.add(contactId);
      if (activeProject) {
        localStorage.setItem(`project:${activeProject.id}:processed`, JSON.stringify([...next]));
      }
      return next;
    });
  }, [activeProject]);

  // Load tasks for active project
  const loadTasks = useCallback(async () => {
    if (!activeProject) return;
    setTasksLoading(true);
    try {
      const data = await contactsApi.listTasks({ project_id: activeProject.id });
      setTasks(data.tasks);
    } catch (err) {
      console.error('Failed to load tasks:', err);
    } finally {
      setTasksLoading(false);
    }
  }, [activeProject]);

  // Filtered campaigns for autocomplete
  const filteredCampaigns = useMemo(() => {
    if (!campaignSearch) return campaigns.slice(0, 100);
    const q = campaignSearch.toLowerCase();
    // Prioritize prefix matches
    const prefix = campaigns.filter(c => c.name.toLowerCase().startsWith(q));
    const contains = campaigns.filter(c => !c.name.toLowerCase().startsWith(q) && c.name.toLowerCase().includes(q));
    return [...prefix, ...contains].slice(0, 100);
  }, [campaigns, campaignSearch]);

  const resetPage = useCallback(() => setPage(1), []);
  const toggleCampaign = useCallback((name: string) => {
    setCampaignFilters(prev => prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]);
    setPage(1);
  }, []);
  const toggleStatus = useCallback((status: string) => {
    setStatusFilters(prev => prev.includes(status) ? prev.filter(s => s !== status) : [...prev, status]);
    setPage(1);
  }, []);

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
        status: statusFilters.length > 0 ? statusFilters.join(',') : undefined,
        source: sourceFilter || undefined,
        campaign: (!activeProject && campaignFilters.length > 0) ? campaignFilters.join(',') : undefined,
        has_replied: replyMode ? true : (repliedFilter ?? undefined),
        needs_followup: followupFilter ?? undefined,
        project_id: activeProject?.id,
        created_after: createdAfter || undefined,
        created_before: createdBefore || undefined,
      });

      setContacts(response.contacts);
      setTotal(response.total);
    } catch (err) {
      console.error('Failed to load contacts:', err);
      toast.error('Failed to load contacts', getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, sortBy, sortOrder, debouncedSearch, statusFilters, sourceFilter, campaignFilters, repliedFilter, followupFilter, replyMode, activeProject, createdAfter, createdBefore, toast]);

  useEffect(() => {
    loadContacts();
  }, [loadContacts]);

  useEffect(() => {
    loadStats();
    loadFilterOptions();
    loadProjects();
    loadCampaigns();
  }, []);

  const loadCampaigns = async () => {
    try {
      const response = await fetch('/api/contacts/campaigns');
      if (response.ok) {
        const data = await response.json();
        setCampaigns(data.campaigns || []);
      }
    } catch (err) {
      console.error('Failed to load campaigns:', err);
    }
  };

  const loadStats = async () => {
    try {
      const data = await contactsApi.getStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  };

  const loadFilterOptions = async () => {
    try {
      const data = await contactsApi.getFilterOptions();
      setFilterOptions(data);
    } catch (err) {
      console.error('Failed to load filter options:', err);
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
      filter: false,
    },
    ...(replyMode ? [{
      headerName: 'Done',
      width: 60,
      pinned: 'left' as const,
      filter: false,
      sortable: false,
      cellRenderer: (params: { data: Contact }) => {
        const done = processedContacts.has(params.data?.id);
        return (
          <span className={cn("inline-flex items-center justify-center w-5 h-5 rounded", done ? "bg-green-100 text-green-600" : "bg-gray-100 text-gray-300")}>
            <Check className="w-3.5 h-3.5" />
          </span>
        );
      },
    }] : []),
    {
      field: 'status',
      headerName: 'Status',
      width: 120,
      sortable: true,
      filter: StatusColumnFilter,
      cellRenderer: (params: { value: string }) => {
        const cfg = STATUS_CONFIG[params.value];
        return cfg ? (
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.colors}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
            {cfg.label}
          </span>
        ) : <span className="text-xs text-gray-400">—</span>;
      },
    },
    {
      field: 'email',
      headerName: 'Email',
      filter: 'agTextColumnFilter',
      sortable: true,
      flex: 2,
      minWidth: 180,
    },
    {
      headerName: 'Name',
      filter: 'agTextColumnFilter',
      sortable: true,
      flex: 1.5,
      minWidth: 140,
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
      flex: 1.5,
      minWidth: 130,
    },
    {
      field: 'job_title',
      headerName: 'Title',
      filter: 'agTextColumnFilter',
      sortable: true,
      flex: 1,
      minWidth: 120,
    },
    {
      headerName: 'Campaign',
      filter: CampaignColumnFilter,
      sortable: true,
      flex: 1.5,
      minWidth: 140,
      valueGetter: (params) => {
        const c = params.data as Contact;
        if (!c?.campaigns || c.campaigns.length === 0) return '';
        return c.campaigns.map(camp => camp.name).join(', ');
      },
      cellRenderer: (params: { value: string; data: Contact }) => {
        const camps = params.data?.campaigns;
        if (!camps || camps.length === 0) return <span className="text-xs text-gray-400">—</span>;
        const first = camps[0];
        return (
          <span className="inline-flex items-center gap-1 text-xs">
            <span className={cn(
              "shrink-0 w-1.5 h-1.5 rounded-full",
              first.source === 'smartlead' ? "bg-blue-500" : "bg-amber-500"
            )} />
            <span className="truncate">{first.name}</span>
            {camps.length > 1 && (
              <span className="shrink-0 text-[10px] text-neutral-400">+{camps.length - 1}</span>
            )}
          </span>
        );
      },
    },
    {
      field: 'source',
      headerName: 'Source',
      filter: 'agTextColumnFilter',
      sortable: true,
      width: 90,
      cellRenderer: (params: { value: string }) => {
        const label = params.value === 'smartlead' ? 'Email' : params.value === 'getsales' ? 'LinkedIn' : (params.value || '-');
        return <span className="text-xs">{label}</span>;
      },
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
      field: 'location',
      headerName: 'Location',
      filter: 'agTextColumnFilter',
      sortable: true,
      width: 130,
      valueFormatter: (params: ValueFormatterParams) => params.value || '-',
    },
    {
      field: 'created_at',
      headerName: 'Added',
      sortable: true,
      width: 95,
      filter: DateColumnFilter,
      valueFormatter: (params: ValueFormatterParams) => {
        if (!params.value) return '-';
        return new Date(params.value).toLocaleDateString();
      },
    },
    {
      field: 'project_name',
      headerName: 'Project',
      filter: 'agTextColumnFilter',
      sortable: true,
      width: 130,
      valueFormatter: (params: ValueFormatterParams) => params.value || '-',
    },
  ], []);

  // Default column settings
  const defaultColDef = useMemo<ColDef>(() => ({
    resizable: true,
    suppressMovable: false,
    filter: 'agTextColumnFilter',
    floatingFilter: false,
    filterParams: { debounceMs: 300 },
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
      },
    });
  };

  const handleRefresh = () => {
    loadContacts();
    loadStats();
    loadFilterOptions();
  };

  const clearFilters = () => {
    setStatusFilters([]);
    setSourceFilter(null);
    setCampaignFilters([]);
    setFollowupFilter(null);
    setRepliedFilter(null);
    setCreatedAfter(null);
    setCreatedBefore(null);
    setSearch('');
    setReplyMode(false);
    gridRef.current?.api?.setFilterModel(null);
  };

  // Select a project
  const selectProject = (project: Project | null) => {
    setActiveProject(project);
    setProjectDropdownOpen(false);
    setReplyMode(false);
    setShowTasksPanel(false);
    setPage(1);
    if (project?.campaign_filters && project.campaign_filters.length > 0) {
      setCampaignFilters(project.campaign_filters);
    }
  };

  // Save current campaign filter as project
  const handleSaveAsProject = async () => {
    if (!newProjectName.trim() || campaignFilters.length === 0) return;
    try {
      const created = await contactsApi.createProject({
        name: newProjectName.trim(),
        campaign_filters: campaignFilters,
      });
      await loadProjects();
      selectProject(created);
      setShowSaveProjectForm(false);
      setNewProjectName('');
      toast.success('Project created', `"${created.name}" saved with campaign filter`);
    } catch (err) {
      toast.error('Failed to create project', getErrorMessage(err));
    }
  };

  // Update project filters
  const handleUpdateProject = async () => {
    if (!activeProject) return;
    try {
      const updated = await contactsApi.updateProject(activeProject.id, {
        name: editProjectName.trim() || activeProject.name,
        campaign_filters: editCampaignFilters,
      });
      setActiveProject({ ...activeProject, ...updated, campaign_filters: editCampaignFilters });
      setEditingProject(false);
      await loadProjects();
      toast.success('Project updated');
    } catch (err) {
      toast.error('Failed to update project', getErrorMessage(err));
    }
  };

  // Reply contacts (contacts with replies, not yet processed)
  const replyContacts = useMemo(() => {
    if (!replyMode) return [];
    return contacts.filter(c => c.has_replied && !processedContacts.has(c.id));
  }, [contacts, replyMode, processedContacts]);

  const hasActiveFilters = statusFilters.length > 0 || sourceFilter || campaignFilters.length > 0 || followupFilter !== null || repliedFilter !== null || createdAfter || createdBefore || search || replyMode;
  const totalPages = Math.ceil(total / pageSize);

  const setDateRange = useCallback((after: string | null, before: string | null) => {
    setCreatedAfter(after);
    setCreatedBefore(before);
    setPage(1);
  }, []);

  const filterCtx = useMemo(() => ({
    campaignFilters,
    setCampaignFilters: (names: string[]) => { setCampaignFilters(names); setPage(1); },
    toggleCampaign,
    statusFilters,
    setStatusFilters: (statuses: string[]) => { setStatusFilters(statuses); setPage(1); },
    toggleStatus,
    campaigns,
    stats,
    resetPage,
    createdAfter,
    createdBefore,
    setDateRange,
  }), [campaignFilters, toggleCampaign, statusFilters, toggleStatus, campaigns, stats, resetPage, createdAfter, createdBefore, setDateRange]);

  return (
    <ContactsFilterContext.Provider value={filterCtx}>
    <div className="h-full flex flex-col bg-neutral-50">
      {/* Command bar — single row */}
      <div className="bg-white border-b border-neutral-200 px-5 py-2.5">
        <div className="flex items-center gap-2">
          {/* Title / Project name + count */}
          {activeProject ? (
            <>
              <button onClick={() => { selectProject(null); clearFilters(); }} className="p-1 hover:bg-neutral-100 rounded" title="Back to all contacts">
                <ChevronLeft className="w-4 h-4 text-neutral-500" />
              </button>
              {editingProject ? (
                <div className="flex items-center gap-1.5 shrink-0">
                  <input
                    value={editProjectName}
                    onChange={(e) => setEditProjectName(e.target.value)}
                    className="text-sm font-semibold border border-indigo-300 rounded px-2 py-0.5 w-40"
                    autoFocus
                  />
                  <button onClick={handleUpdateProject} className="p-1 hover:bg-green-100 rounded text-green-600"><Check className="w-3.5 h-3.5" /></button>
                  <button onClick={() => setEditingProject(false)} className="p-1 hover:bg-neutral-100 rounded text-neutral-500"><X className="w-3.5 h-3.5" /></button>
                </div>
              ) : (
                <button
                  onClick={() => { setEditingProject(true); setEditProjectName(activeProject.name); setEditCampaignFilters(activeProject.campaign_filters || []); }}
                  className="text-base font-semibold text-indigo-700 hover:text-indigo-900 flex items-center gap-1 shrink-0"
                >
                  {activeProject.name}
                  <Edit3 className="w-3 h-3 text-indigo-400" />
                </button>
              )}
            </>
          ) : (
            <h1 className="text-base font-semibold text-neutral-900 shrink-0">CRM Contacts</h1>
          )}
          <span className="text-sm text-neutral-400 font-medium shrink-0">{formatNumber(total)}</span>

          {/* Project selector */}
          <div className="relative shrink-0" ref={projectRef}>
            <button
              onClick={() => setProjectDropdownOpen(!projectDropdownOpen)}
              className={cn(
                "inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all",
                activeProject
                  ? "bg-indigo-50 text-indigo-700 border-indigo-200"
                  : "bg-white text-gray-600 border-neutral-200 hover:border-indigo-400"
              )}
            >
              <FolderOpen className="w-3 h-3" />
              {activeProject ? 'Switch' : 'Projects'}
            </button>
            {projectDropdownOpen && (
              <div className="absolute top-full left-0 mt-1 w-56 bg-white rounded-xl shadow-lg border border-neutral-200 z-50 overflow-hidden">
                <div className="max-h-48 overflow-auto">
                  {projects.length === 0 ? (
                    <div className="px-3 py-4 text-xs text-neutral-400 text-center">No projects yet</div>
                  ) : (
                    projects.map(p => (
                      <button
                        key={p.id}
                        onClick={() => selectProject(p)}
                        className={cn(
                          "w-full text-left px-3 py-2 text-xs hover:bg-indigo-50 flex items-center justify-between",
                          activeProject?.id === p.id && "bg-indigo-50 text-indigo-700"
                        )}
                      >
                        <span className="truncate">{p.name}</span>
                        <span className="text-neutral-400 text-[10px]">{p.contact_count}</span>
                      </button>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Reply mode button (only inside a project) */}
          {activeProject && (
            <button
              onClick={() => { setReplyMode(!replyMode); setPage(1); }}
              className={cn(
                "inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all shrink-0",
                replyMode
                  ? "bg-purple-500 text-white border-purple-500"
                  : "bg-white text-purple-600 border-purple-200 hover:border-purple-400"
              )}
            >
              <MessageSquare className="w-3 h-3" />
              Reply
            </button>
          )}

          {/* Tasks button (only inside a project) */}
          {activeProject && (
            <button
              onClick={() => { setShowTasksPanel(!showTasksPanel); if (!showTasksPanel) loadTasks(); }}
              className={cn(
                "inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all shrink-0",
                showTasksPanel
                  ? "bg-amber-500 text-white border-amber-500"
                  : "bg-white text-amber-600 border-amber-200 hover:border-amber-400"
              )}
            >
              <ListTodo className="w-3 h-3" />
              Tasks
            </button>
          )}

          {/* Search */}
          <div className="relative flex-1 max-w-xs ml-2">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input
              type="text"
              placeholder="Search contacts..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 rounded-lg border border-neutral-200 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
            />
          </div>

          {/* Replied */}
          <button
            onClick={() => { setRepliedFilter(repliedFilter === true ? null : true); setPage(1); }}
            className={cn(
              "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all shrink-0",
              repliedFilter === true
                ? "bg-green-500 text-white border-green-500"
                : "bg-white text-green-600 border-green-200 hover:border-green-400"
            )}
          >
            Replied
            {stats && (stats.by_status?.replied || 0) > 0 && (
              <span className={cn(
                "px-1.5 py-0.5 rounded-full text-[10px] font-bold",
                repliedFilter === true
                  ? "bg-green-400 text-white"
                  : "bg-green-100 text-green-600"
              )}>
                {stats.by_status?.replied || 0}
              </span>
            )}
          </button>

          {/* Follow-up */}
          <button
            onClick={() => { setFollowupFilter(followupFilter === true ? null : true); setPage(1); }}
            className={cn(
              "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all shrink-0",
              followupFilter === true
                ? "bg-orange-500 text-white border-orange-500"
                : "bg-white text-gray-600 border-gray-300 hover:border-orange-400"
            )}
          >
            Follow-up
          </button>

          {/* Campaign filter — compact counter + dropdown */}
          <div className="relative shrink-0" ref={campaignRef}>
            <button
              onClick={() => { setCampaignDropdownOpen(!campaignDropdownOpen); setCampaignSearch(''); }}
              className={cn(
                "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all",
                campaignFilters.length > 0
                  ? "border-indigo-400 bg-indigo-500 text-white"
                  : "border-neutral-200 bg-white text-gray-600 hover:border-indigo-400"
              )}
            >
              <Search className="w-3 h-3" />
              {campaignFilters.length > 0
                ? `${campaignFilters.length} campaign${campaignFilters.length > 1 ? 's' : ''}`
                : 'Campaigns'}
            </button>
            {campaignDropdownOpen && (
              <div className="absolute top-full left-0 mt-1 w-80 bg-white rounded-xl shadow-lg border border-neutral-200 z-50 overflow-hidden">
                {/* Search */}
                <div className="p-2 border-b border-neutral-100">
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400" />
                    <input
                      type="text"
                      placeholder="Search campaigns..."
                      value={campaignSearch}
                      onChange={(e) => setCampaignSearch(e.target.value)}
                      className="w-full pl-8 pr-3 py-1.5 rounded-lg border border-neutral-200 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      autoFocus
                    />
                  </div>
                </div>
                {/* Selected campaigns summary */}
                {campaignFilters.length > 0 && !campaignSearch && (
                  <div className="px-3 py-2 border-b border-neutral-100 bg-indigo-50/50">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] font-medium text-indigo-600 uppercase tracking-wide">Selected ({campaignFilters.length})</span>
                      <button onClick={() => { setCampaignFilters([]); setPage(1); }} className="text-[10px] text-red-500 hover:text-red-600">Clear all</button>
                    </div>
                    <div className="flex flex-wrap gap-1 max-h-20 overflow-auto">
                      {campaignFilters.map(name => (
                        <button
                          key={name}
                          onClick={() => toggleCampaign(name)}
                          className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-100 text-indigo-700 hover:bg-indigo-200 max-w-[200px]"
                        >
                          <span className="truncate">{name}</span>
                          <X className="w-2.5 h-2.5 shrink-0" />
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {/* Campaign list */}
                <div className="max-h-64 overflow-auto">
                  {filteredCampaigns.length === 0 ? (
                    <div className="px-3 py-4 text-xs text-neutral-400 text-center">No campaigns found</div>
                  ) : (
                    filteredCampaigns.map((c, i) => {
                      const isSelected = campaignFilters.includes(c.name);
                      return (
                        <button
                          key={i}
                          onClick={() => toggleCampaign(c.name)}
                          className={cn(
                            "w-full text-left px-3 py-1.5 text-xs flex items-center gap-2 transition-colors",
                            isSelected ? "bg-indigo-50 text-indigo-700" : "hover:bg-neutral-50"
                          )}
                        >
                          <span className={cn(
                            "w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                            isSelected ? "bg-indigo-500 border-indigo-500" : "border-neutral-300"
                          )}>
                            {isSelected && <Check className="w-2.5 h-2.5 text-white" />}
                          </span>
                          <span className={cn(
                            "shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium",
                            c.source === 'smartlead' ? "bg-blue-100 text-blue-600" : "bg-amber-100 text-amber-600"
                          )}>
                            {c.source === 'smartlead' ? 'Email' : 'LI'}
                          </span>
                          <span className="truncate">{c.name}</span>
                        </button>
                      );
                    })
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Save as Project (when campaign filters active and no project) */}
          {campaignFilters.length > 0 && !activeProject && !showSaveProjectForm && (
            <button
              onClick={() => { setShowSaveProjectForm(true); setNewProjectName(campaignFilters[0]); }}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium border border-green-200 bg-white text-green-600 hover:border-green-400 transition-all shrink-0"
            >
              <Save className="w-3 h-3" />
              Save as Project
            </button>
          )}
          {showSaveProjectForm && (
            <div className="inline-flex items-center gap-1 shrink-0">
              <input
                value={newProjectName}
                onChange={(e) => setNewProjectName(e.target.value)}
                placeholder="Project name"
                className="text-xs border border-green-300 rounded px-2 py-1.5 w-36 focus:outline-none focus:ring-1 focus:ring-green-400"
                autoFocus
                onKeyDown={(e) => { if (e.key === 'Enter') handleSaveAsProject(); if (e.key === 'Escape') setShowSaveProjectForm(false); }}
              />
              <button onClick={handleSaveAsProject} className="p-1.5 rounded-lg bg-green-500 text-white hover:bg-green-600"><Check className="w-3 h-3" /></button>
              <button onClick={() => setShowSaveProjectForm(false)} className="p-1.5 rounded-lg hover:bg-neutral-100"><X className="w-3 h-3 text-neutral-500" /></button>
            </div>
          )}

          {/* Reset filters */}
          <button
            onClick={clearFilters}
            disabled={!hasActiveFilters}
            className={cn(
              "inline-flex items-center gap-1 px-2 py-1.5 rounded-lg text-xs font-medium border transition-all shrink-0",
              hasActiveFilters
                ? "text-red-500 hover:bg-red-50 border-red-200"
                : "text-neutral-300 border-neutral-200 cursor-not-allowed"
            )}
          >
            <X className="w-3 h-3" />
            Reset
          </button>

          {/* Separator */}
          <span className="w-px h-5 bg-neutral-200 mx-0.5" />

          {/* Actions */}
          <button onClick={handleRefresh} className="p-1.5 rounded-lg hover:bg-neutral-100 transition-colors" title="Refresh">
            <RefreshCw className={cn("w-4 h-4 text-neutral-500", isLoading && "animate-spin")} />
          </button>
          <button onClick={() => setShowAddModal(true)} className="p-1.5 rounded-lg hover:bg-neutral-100 transition-colors" title="Add Contact">
            <Plus className="w-4 h-4 text-neutral-500" />
          </button>
          <button onClick={() => setShowImportModal(true)} className="p-1.5 rounded-lg hover:bg-neutral-100 transition-colors" title="Import">
            <Upload className="w-4 h-4 text-neutral-500" />
          </button>
          <button onClick={handleExportCsv} className="p-1.5 rounded-lg hover:bg-neutral-100 transition-colors" title="Export CSV">
            <Download className="w-4 h-4 text-neutral-500" />
          </button>
          {selectedContacts.length > 0 && (
            <button onClick={handleDeleteSelected} className="p-1.5 rounded-lg hover:bg-red-50 transition-colors text-red-500" title="Delete Selected">
              <Trash2 className="w-4 h-4" />
              <span className="ml-0.5 text-xs">{selectedContacts.length}</span>
            </button>
          )}
        </div>
      </div>

      {/* AG Grid */}
      <div className="flex-1 px-4 pt-2 pb-1">
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
                checkboxes: true,
              }}
              onGridReady={onGridReady}
              onSelectionChanged={onSelectionChanged}
              onSortChanged={onSortChanged}
              animateRows={true}
              suppressCellFocus={true}
              enableCellTextSelection={true}
              getRowId={(params) => String(params.data.id)}
              overlayLoadingTemplate='<span class="text-neutral-500">Loading contacts...</span>'
              overlayNoRowsTemplate='<span class="text-neutral-500">No contacts found</span>'
            />
          </div>
        </SectionErrorBoundary>
      </div>

      {/* Tasks panel (slide-out below grid) */}
      {showTasksPanel && activeProject && (
        <div className="bg-white border-t border-amber-200 px-5 py-3 max-h-48 overflow-auto">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-amber-700 flex items-center gap-1.5">
              <ListTodo className="w-4 h-4" />
              Tasks — {activeProject.name}
            </h3>
            <button onClick={() => setShowTasksPanel(false)} className="p-1 hover:bg-neutral-100 rounded"><X className="w-3.5 h-3.5 text-neutral-400" /></button>
          </div>
          {tasksLoading ? (
            <div className="text-xs text-neutral-400 py-2">Loading tasks...</div>
          ) : tasks.length === 0 ? (
            <div className="text-xs text-neutral-400 py-2">No tasks for this project</div>
          ) : (
            <div className="space-y-1">
              {tasks.map(task => (
                <div key={task.id} className={cn("flex items-center gap-3 px-3 py-2 rounded-lg text-xs", task.status === 'done' ? "bg-green-50 text-green-600" : task.status === 'skipped' ? "bg-gray-50 text-gray-400" : "bg-amber-50")}>
                  <span className="flex-1 font-medium">{task.title}</span>
                  <span className="text-neutral-400 shrink-0">{new Date(task.due_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                  {task.status === 'pending' && (
                    <div className="flex gap-1">
                      <button
                        onClick={async () => { await contactsApi.updateTask(task.id, { status: 'done' }); loadTasks(); }}
                        className="px-2 py-0.5 rounded bg-green-500 text-white hover:bg-green-600"
                      >Done</button>
                      <button
                        onClick={async () => { await contactsApi.updateTask(task.id, { status: 'skipped' }); loadTasks(); }}
                        className="px-2 py-0.5 rounded bg-gray-200 text-gray-600 hover:bg-gray-300"
                      >Skip</button>
                    </div>
                  )}
                  {task.status !== 'pending' && (
                    <span className={cn("px-2 py-0.5 rounded text-[10px] font-medium", task.status === 'done' ? "bg-green-100 text-green-600" : "bg-gray-100 text-gray-400")}>{task.status}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Pagination — compact */}
      <div className="bg-white border-t border-neutral-200 px-5 py-2 flex items-center justify-between">
        <div className="text-xs text-neutral-500">
          {((page - 1) * pageSize) + 1}-{Math.min(page * pageSize, total)} of {formatNumber(total)}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setPage(1)}
            disabled={page === 1}
            className="px-2 py-1 text-xs rounded border border-neutral-200 bg-white hover:bg-neutral-50 disabled:opacity-40"
          >
            First
          </button>
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-2 py-1 text-xs rounded border border-neutral-200 bg-white hover:bg-neutral-50 disabled:opacity-40"
          >
            Prev
          </button>
          <span className="text-xs text-neutral-500 px-2">
            {page}/{totalPages || 1}
          </span>
          <button
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages || totalPages === 0}
            className="px-2 py-1 text-xs rounded border border-neutral-200 bg-white hover:bg-neutral-50 disabled:opacity-40"
          >
            Next
          </button>
          <button
            onClick={() => setPage(totalPages)}
            disabled={page === totalPages || totalPages === 0}
            className="px-2 py-1 text-xs rounded border border-neutral-200 bg-white hover:bg-neutral-50 disabled:opacity-40"
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
      <SectionErrorBoundary>
        <ContactDetailModal
          contact={selectedContact}
          isOpen={showContactModal}
          onClose={() => {
            setShowContactModal(false);
            setSelectedContact(null);
          }}
          replyMode={replyMode}
          contactList={replyMode ? replyContacts : contacts}
          currentIndex={replyMode ? replyContactIndex : contacts.findIndex(c => c.id === selectedContact?.id)}
          onNavigate={(index: number) => {
            const list = replyMode ? replyContacts : contacts;
            if (index >= 0 && index < list.length) {
              setSelectedContact(list[index]);
              if (replyMode) setReplyContactIndex(index);
            }
          }}
          onMarkProcessed={(contactId: number) => {
            markProcessed(contactId);
          }}
        />
      </SectionErrorBoundary>
    </div>
    </ContactsFilterContext.Provider>
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
    status: '',
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
                <option value="">No Status</option>
                {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
                  <option key={key} value={key}>{cfg.label}</option>
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
