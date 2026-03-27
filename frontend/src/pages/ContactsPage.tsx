import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
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
  Search, Download, Trash2, RefreshCw,
  Plus, X, FolderOpen, Target, Mail, Loader2, Upload, AlertCircle, Check,
  FileSpreadsheet, ExternalLink, Send,
  Sparkles, ChevronRight, ChevronDown, Users, FileText, Columns3, TrendingUp
} from 'lucide-react';
import { contactsApi, type Contact, type ContactStats, type FilterOptions, type Project, type AISDRProject, type ImportResult, type EnrichResult } from '../api';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { ContactDetailModal } from '../components/ContactDetailModal';
import { CRMSpotlight } from '../components/CRMSpotlight';
import { SectionErrorBoundary } from '../components/ErrorBoundary';
import { useToast } from '../components/Toast';
import { ContactsFilterContext, CampaignColumnFilter, StatusColumnFilter, DateColumnFilter, SegmentColumnFilter, SourceColumnFilter, RepliedColumnFilter, GeoColumnFilter, ReplyCategoryColumnFilter } from '../components/filters';
import { cn, formatNumber, getErrorMessage } from '../lib/utils';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { useAppStore } from '../store/appStore';

// Status configuration — sales funnel
const STATUS_CONFIG: Record<string, { dot: string; label: string }> = {
  new:                 { dot: '#9ca3af', label: 'New' },
  sent:                { dot: '#6b7280', label: 'Sent' },
  replied:             { dot: '#3b82f6', label: 'Replied' },
  unsubscribed:        { dot: '#f87171', label: 'Unsubscribed' },
  calendly_sent:       { dot: '#fb923c', label: 'Calendly Sent' },
  negotiating_meeting: { dot: '#f97316', label: 'Negotiating Meeting' },
  meeting_booked:      { dot: '#f97316', label: 'Meeting Booked' },
  scheduled:           { dot: '#f97316', label: 'Scheduled' },
  meeting_held:        { dot: '#22c55e', label: 'Meeting Held' },
  meeting_no_show:     { dot: '#ef4444', label: 'Meeting No Show' },
  meeting_rescheduled: { dot: '#f59e0b', label: 'Meeting Rescheduled' },
  qualified:           { dot: '#10b981', label: 'Qualified' },
  not_qualified:       { dot: '#4b5563', label: 'Not Qualified' },
};

// Reply Type configuration — reply intent
const REPLY_CATEGORY_CONFIG: Record<string, { dot: string; label: string }> = {
  meeting_request: { dot: '#22c55e', label: 'Meeting Request' },
  interested:      { dot: '#3b82f6', label: 'Interested' },
  question:        { dot: '#6366f1', label: 'Question' },
  not_interested:  { dot: '#9ca3af', label: 'Not Interested' },
  out_of_office:   { dot: '#fbbf24', label: 'Out of Office' },
  wrong_person:    { dot: '#f87171', label: 'Wrong Person' },
  unsubscribe:     { dot: '#fb923c', label: 'Unsubscribe' },
  other:           { dot: '#a78bfa', label: 'Other' },
};

export function ContactsPage() {
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const gridRef = useRef<AgGridReact>(null);
  const [, setGridApi] = useState<GridApi | null>(null);
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  // Data
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [stats, setStats] = useState<ContactStats | null>(null);
  const [filterOptions, setFilterOptions] = useState<FilterOptions | null>(null);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  // Filters — compact command-bar style (initialized from URL params)
  const [search, setSearch] = useState(searchParams.get('search') || '');
  const [debouncedSearch, setDebouncedSearch] = useState(searchParams.get('search') || '');
  const [statusFilters, setStatusFilters] = useState<string[]>(
    searchParams.get('status')?.split(',').filter(Boolean) || []
  );
  const [sourceFilter, setSourceFilter] = useState<string | null>(searchParams.get('source'));
  const [segmentFilters, setSegmentFilters] = useState<string[]>(
    searchParams.get('segment')?.split(',').filter(Boolean) || []
  );
  const [geoFilter, setGeoFilter] = useState<string | null>(searchParams.get('geo'));
  const [campaignFilters, setCampaignFilters] = useState<string[]>(
    searchParams.get('campaign')?.split(',').filter(Boolean) || []
  );
  const [campaignIdFilter, setCampaignIdFilter] = useState<string | null>(searchParams.get('campaign_id'));
  const [campaigns, setCampaigns] = useState<Array<{name: string, source: string}>>([]);
  const [followupFilter, setFollowupFilter] = useState<boolean | null>(
    searchParams.get('followup') === 'true' ? true : null
  );
  const [repliedFilter, setRepliedFilter] = useState<boolean | null>(
    searchParams.get('replied') === 'true' ? true : null
  );
  const [createdAfter, setCreatedAfter] = useState<string | null>(searchParams.get('after'));
  const [createdBefore, setCreatedBefore] = useState<string | null>(searchParams.get('before'));
  const [domainFilter, _setDomainFilter] = useState<string | null>(searchParams.get('domain'));
  const [suitableForFilter, _setSuitableForFilter] = useState<string | null>(searchParams.get('suitable_for'));
  const [sourceIdFilter, _setSourceIdFilter] = useState<string | null>(searchParams.get('source_id'));
  const [replyCategoryFilters, setReplyCategoryFilters] = useState<string[]>(
    searchParams.get('reply_category')?.split(',').filter(Boolean) || []
  );
  const [replySince] = useState<string | null>(searchParams.get('reply_since'));

  // Contact Detail Modal
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [showContactModal, setShowContactModal] = useState(false);
  const [initialCampaignKey, setInitialCampaignKey] = useState<string | null>(null);

  // Project view — URL project_id is highest priority, then global navbar
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const currentProject = useAppStore(s => s.currentProject);
  const urlProjectRef = useRef(searchParams.get('project_id'));

  // Reply processing mode
  const [replyMode, setReplyMode] = useState(false);
  const [replyContactIndex, setReplyContactIndex] = useState(0);
  const [processedContacts, setProcessedContacts] = useState<Set<number>>(new Set());

  // Column visibility
  const DEFAULT_HIDDEN_COLUMNS = ['Project', 'Suitable For', 'Segment', 'Status', 'Replied', 'Reply Type'];
  const HIDDEN_COLS_VERSION = 2; // bump to reset user prefs when defaults change
  const [hiddenColumns, setHiddenColumns] = useState<string[]>(() => {
    try {
      const ver = localStorage.getItem('crm:hiddenColumnsVer');
      if (ver && Number(ver) >= HIDDEN_COLS_VERSION) {
        const stored = localStorage.getItem('crm:hiddenColumns');
        return stored ? JSON.parse(stored) : DEFAULT_HIDDEN_COLUMNS;
      }
      // Version mismatch — reset to new defaults
      localStorage.setItem('crm:hiddenColumnsVer', String(HIDDEN_COLS_VERSION));
      localStorage.setItem('crm:hiddenColumns', JSON.stringify(DEFAULT_HIDDEN_COLUMNS));
      return DEFAULT_HIDDEN_COLUMNS;
    } catch { return DEFAULT_HIDDEN_COLUMNS; }
  });
  const [showColumnPicker, setShowColumnPicker] = useState(false);
  const columnPickerRef = useRef<HTMLDivElement>(null);

  const toggleColumnVisibility = useCallback((headerName: string) => {
    setHiddenColumns(prev => {
      const next = prev.includes(headerName)
        ? prev.filter(n => n !== headerName)
        : [...prev, headerName];
      localStorage.setItem('crm:hiddenColumns', JSON.stringify(next));
      localStorage.setItem('crm:hiddenColumnsVer', String(HIDDEN_COLS_VERSION));
      return next;
    });
  }, []);

  // Close column picker on outside click or Escape
  useEffect(() => {
    if (!showColumnPicker) return;
    const handleClick = (e: MouseEvent) => {
      if (columnPickerRef.current && !columnPickerRef.current.contains(e.target as Node)) {
        setShowColumnPicker(false);
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setShowColumnPicker(false);
    };
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleKey);
    };
  }, [showColumnPicker]);

  // Tasks (kept for future use)

  // Pagination & Sorting
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  // Selection
  const [selectedContacts, setSelectedContacts] = useState<Contact[]>([]);

  // Modals
  const [showAddModal, setShowAddModal] = useState(false);
  const [showProjectModal, setShowProjectModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showEnrichModal, setShowEnrichModal] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);

  // Dialogs
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({ isOpen: false, title: '', message: '', onConfirm: () => {} });

  // Debounce search + clear AG Grid column filters to avoid client/server conflict
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
      if (search && gridRef.current?.api) {
        gridRef.current.api.setFilterModel(null);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Sync filters → URL. Start from current URL params to preserve any we don't manage.
  const isFirstSync = useRef(true);
  useEffect(() => {
    // On first render, preserve all original URL params — don't overwrite
    const params = isFirstSync.current
      ? new URLSearchParams(searchParams)
      : new URLSearchParams();
    isFirstSync.current = false;

    // Managed params: set or delete based on current state
    // urlProjectRef preserves project_id from URL until loadProjects resolves
    const managed: Record<string, string | null> = {
      project_id: activeProject ? String(activeProject.id) : (urlProjectRef.current || null),
      search: debouncedSearch || null,
      status: statusFilters.length ? statusFilters.join(',') : null,
      source: sourceFilter,
      segment: segmentFilters.length ? segmentFilters.join(',') : null,
      geo: geoFilter,
      campaign: (!activeProject && campaignFilters.length) ? campaignFilters.join(',') : null,
      campaign_id: (!activeProject && campaignIdFilter) ? campaignIdFilter : null,
      replied: repliedFilter ? 'true' : null,
      followup: followupFilter ? 'true' : null,
      after: createdAfter,
      before: createdBefore,
      domain: domainFilter,
      suitable_for: suitableForFilter,
      reply_category: replyCategoryFilters.length ? replyCategoryFilters.join(',') : null,
      reply_since: replySince,
      source_id: sourceIdFilter,
    };
    for (const [key, value] of Object.entries(managed)) {
      if (value) {
        params.set(key, value);
      } else if (!isFirstSync.current) {
        params.delete(key);
      }
    }
    // Preserve contact_id for deep-link
    const existingContactId = searchParams.get('contact_id');
    if (existingContactId) params.set('contact_id', existingContactId);

    setSearchParams(params, { replace: true });
  }, [activeProject, debouncedSearch, statusFilters, sourceFilter, segmentFilters, geoFilter, campaignFilters, campaignIdFilter, repliedFilter, followupFilter, createdAfter, createdBefore, domainFilter, suitableForFilter, replyCategoryFilters, replySince, sourceIdFilter]);

  // Sync CRM project from global navbar project selector (only when URL doesn't specify one)
  useEffect(() => {
    if (currentProject && !urlProjectRef.current) {
      selectProject(currentProject);
    }
  }, [currentProject]);

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

  const resetPage = useCallback(() => setPage(1), []);
  const toggleCampaign = useCallback((name: string) => {
    setCampaignFilters(prev => prev.includes(name) ? prev.filter(n => n !== name) : [...prev, name]);
    setPage(1);
  }, []);
  const toggleStatus = useCallback((status: string) => {
    setStatusFilters(prev => prev.includes(status) ? prev.filter(s => s !== status) : [...prev, status]);
    setPage(1);
  }, []);
  const toggleSegment = useCallback((segment: string) => {
    setSegmentFilters(prev => prev.includes(segment) ? prev.filter(s => s !== segment) : [...prev, segment]);
    setPage(1);
  }, []);
  const toggleReplyCategory = useCallback((cat: string) => {
    setReplyCategoryFilters(prev => prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat]);
    setPage(1);
  }, []);

  // Build filter params (shared between load and loadMore)
  const buildFilterParams = useCallback(() => ({
    page_size: pageSize,
    sort_by: sortBy,
    sort_order: sortOrder,
    search: debouncedSearch || undefined,
    status: statusFilters.length > 0 ? statusFilters.join(',') : undefined,
    source: sourceFilter || undefined,
    segment: segmentFilters.length > 0 ? segmentFilters.join(',') : undefined,
    geo: geoFilter || undefined,
    campaign: (campaignFilters.length > 0 && segmentFilters.length === 0) ? campaignFilters.join(',') : undefined,
    campaign_id: campaignIdFilter || undefined,
    has_replied: replyMode ? true : (repliedFilter ?? undefined),
    needs_followup: followupFilter ?? undefined,
    project_id: activeProject?.id ?? (urlProjectRef.current ? parseInt(urlProjectRef.current) : undefined),
    created_after: createdAfter || undefined,
    created_before: createdBefore || undefined,
    domain: domainFilter || undefined,
    suitable_for: suitableForFilter || undefined,
    reply_category: replyCategoryFilters.length > 0 ? replyCategoryFilters.join(',') : undefined,
    reply_since: replySince || undefined,
    source_id: sourceIdFilter || undefined,
  }), [pageSize, sortBy, sortOrder, debouncedSearch, statusFilters, sourceFilter, segmentFilters, geoFilter, campaignFilters, campaignIdFilter, repliedFilter, followupFilter, replyMode, activeProject, createdAfter, createdBefore, domainFilter, suitableForFilter, replyCategoryFilters, replySince, sourceIdFilter]);

  // Load first page (resets list)
  const loadContacts = useCallback(async () => {
    setIsLoading(true);
    setPage(1);
    try {
      const response = await contactsApi.list({ ...buildFilterParams(), page: 1 });
      setContacts(response.contacts);
      setTotal(response.total);
      setHasMore(response.contacts.length >= pageSize);
    } catch (err) {
      console.error('Failed to load contacts:', err);
      toast.error('Failed to load contacts', getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [buildFilterParams, pageSize, toast]);

  // Load more (append to list)
  const loadMore = useCallback(async () => {
    if (isLoadingMore || !hasMore) return;
    setIsLoadingMore(true);
    const nextPage = page + 1;
    try {
      const response = await contactsApi.list({ ...buildFilterParams(), page: nextPage });
      if (response.contacts.length > 0) {
        setContacts(prev => [...prev, ...response.contacts]);
        setPage(nextPage);
        setHasMore(response.contacts.length >= pageSize);
      } else {
        setHasMore(false);
      }
    } catch (err) {
      console.error('Failed to load more:', err);
    } finally {
      setIsLoadingMore(false);
    }
  }, [isLoadingMore, hasMore, page, buildFilterParams, pageSize]);

  // Reload when filters/sort change
  useEffect(() => {
    loadContacts();
  }, [loadContacts]);

  // Contact deep-link: ?contact_id=123&campaign=channel::name opens modal automatically
  const deepLinkHandled = useRef(false);
  const deepLinkRetries = useRef(0);
  useEffect(() => {
    const contactIdParam = searchParams.get('contact_id');
    if (!contactIdParam || deepLinkHandled.current) return;
    const id = parseInt(contactIdParam);
    if (isNaN(id)) return;
    deepLinkHandled.current = true;
    // Read campaign key for pre-selection in modal (format: "channel::campaign_name")
    const campaignParam = searchParams.get('campaign');
    setInitialCampaignKey(campaignParam);
    // Fetch basic contact — the modal will load history internally via /contacts/{id}/history
    fetch(`/api/contacts/${id}/`).then(r => {
      if (!r.ok) throw new Error(`${r.status}`);
      return r.json();
    }).then((contact: Contact) => {
      setSelectedContact(contact);
      setShowContactModal(true);
    }).catch(() => {
      deepLinkRetries.current += 1;
      if (deepLinkRetries.current < 2) {
        deepLinkHandled.current = false; // one more retry
      } else {
        // Give up — remove contact_id from URL
        const p = new URLSearchParams(searchParams);
        p.delete('contact_id');
        p.delete('campaign');
        setSearchParams(p, { replace: true });
      }
    });
  }, [searchParams]);

  useEffect(() => {
    loadStats();
    loadFilterOptions();
    loadProjects();
  }, []);

  // Reload stats when project changes
  useEffect(() => {
    loadStats(activeProject?.id ?? null);
  }, [activeProject?.id]);

  const campaignsLoadedRef = useRef(false);
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
  const ensureCampaignsLoaded = useCallback(() => {
    if (campaignsLoadedRef.current) return;
    campaignsLoadedRef.current = true;
    loadCampaigns();
  }, []);

  const statsRequestRef = useRef(0);
  const loadStats = async (projectId?: number | null) => {
    const requestId = ++statsRequestRef.current;
    try {
      const pid = projectId !== undefined ? projectId : activeProject?.id;
      const data = await contactsApi.getStats(pid);
      // Only update if this is still the latest request (prevents race condition)
      if (requestId === statsRequestRef.current) {
        setStats(data);
      }
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
      // Auto-select project from URL param (highest priority — overrides global store)
      const urlProjectId = searchParams.get('project_id');
      if (urlProjectId) {
        const proj = data.find((p: Project) => p.id === parseInt(urlProjectId));
        if (proj) {
          selectProject(proj);
        }
      }
    } catch (err) {
      console.error('Failed to load projects:', err);
      toast.error('Failed to load projects', getErrorMessage(err));
    }
  };

  // Handle status change from inline dropdown
  const handleStatusChange = useCallback(async (contactId: number, newStatus: string) => {
    try {
      await contactsApi.updateStatus(contactId, newStatus);
      // Update local state to avoid full reload
      setContacts(prev => prev.map(c =>
        c.id === contactId ? { ...c, status: newStatus } : c
      ));
      toast.success('Status Updated', `${STATUS_CONFIG[newStatus]?.label || newStatus}`);
    } catch (err) {
      toast.error('Error', getErrorMessage(err));
    }
  }, [toast]);

  // AG Grid Column Definitions — with column-embedded filters
  const columnDefs = useMemo<ColDef[]>(() => [
    {
      width: 40,
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
      width: 145,
      sortable: true,
      filter: StatusColumnFilter,
      cellRenderer: (params: { value: string; data: Contact }) => {
        const currentStatus = params.value || '';
        return (
          <select
            value={currentStatus}
            onChange={(e) => {
              e.stopPropagation();
              if (params.data?.id && e.target.value !== currentStatus) {
                handleStatusChange(params.data.id, e.target.value);
              }
            }}
            onClick={(e) => e.stopPropagation()}
            className="w-full bg-transparent border-0 text-xs cursor-pointer focus:outline-none focus:ring-0 p-0 appearance-none"
            style={{
              color: isDark ? '#aaa' : '#555',
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239ca3af' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E")`,
              backgroundRepeat: 'no-repeat',
              backgroundPosition: 'right 0 center',
              paddingRight: '16px',
            }}
          >
            <option value="" style={{ color: '#888' }}>—</option>
            {Object.entries(STATUS_CONFIG).map(([key, val]) => (
              <option key={key} value={key} style={{ color: val.dot }}>
                {val.label}
              </option>
            ))}
          </select>
        );
      },
    },
    {
      headerName: 'Replied',
      width: 90,
      sortable: false,
      filter: RepliedColumnFilter,
      valueGetter: (params) => {
        const c = params.data as Contact;
        if (c?.needs_followup) return 'Follow-up';
        if (c?.has_replied) return 'Replied';
        return '';
      },
      cellRenderer: (params: { value: string }) => {
        if (params.value === 'Follow-up') return <span className="text-xs" style={{ color: isDark ? '#d97706' : '#d97706' }}>Follow-up</span>;
        if (params.value === 'Replied') return <span className="text-xs" style={{ color: isDark ? '#4ade80' : '#16a34a' }}>Replied</span>;
        return <span className="text-xs" style={{ color: t.text6 }}>—</span>;
      },
    },
    {
      field: 'latest_reply_category',
      headerName: 'Reply Type',
      width: 130,
      sortable: false,
      filter: ReplyCategoryColumnFilter,
      cellRenderer: (params: { value: string }) => {
        const cfg = REPLY_CATEGORY_CONFIG[params.value];
        return cfg ? (
          <span className="inline-flex items-center gap-1.5 text-xs" style={{ color: isDark ? '#aaa' : '#555' }}>
            <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: cfg.dot }} />
            {cfg.label}
          </span>
        ) : <span className="text-xs" style={{ color: t.text6 }}>—</span>;
      },
    },
    {
      field: 'status_external',
      headerName: 'Client Status',
      width: 130,
      sortable: true,
      cellRenderer: (params: { value: string }) => {
        if (!params.value) return <span className="text-xs" style={{ color: t.text6 }}>—</span>;
        return <span className="text-xs font-medium" style={{ color: isDark ? '#93c5fd' : '#2563eb' }}>{params.value}</span>;
      },
    },
    {
      field: 'email',
      headerName: 'Email',
      sortable: true,
      flex: 1.5,
      minWidth: 160,
    },
    {
      headerName: 'Name',
      sortable: true,
      flex: 1,
      minWidth: 120,
      valueGetter: (params) => {
        const c = params.data as Contact;
        return `${c?.first_name || ''} ${c?.last_name || ''}`.trim() || '-';
      },
    },
    {
      field: 'company_name',
      headerName: 'Company',
      sortable: true,
      flex: 1,
      minWidth: 110,
    },
    {
      field: 'job_title',
      headerName: 'Title',
      sortable: true,
      flex: 1,
      minWidth: 100,
    },
    {
      headerName: 'Campaign',
      filter: CampaignColumnFilter,
      sortable: true,
      flex: 1,
      minWidth: 120,
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
      filter: SourceColumnFilter,
      sortable: true,
      width: 80,
      cellRenderer: (params: { value: string }) => {
        const label = params.value === 'smartlead' ? 'Email' : params.value === 'getsales' ? 'LinkedIn' : (params.value || '-');
        return <span className="text-xs">{label}</span>;
      },
    },
    {
      field: 'segment',
      headerName: 'Segment',
      filter: SegmentColumnFilter,
      sortable: true,
      width: 100,
      valueFormatter: (params: ValueFormatterParams) => params.value || '-',
    },
    {
      field: 'geo',
      headerName: 'Geo',
      filter: GeoColumnFilter,
      sortable: true,
      width: 70,
      valueFormatter: (params: ValueFormatterParams) => params.value || '-',
    },
    {
      field: 'suitable_for',
      headerName: 'Suitable For',
      sortable: false,
      width: 120,
      cellRenderer: (params: { value: string[] }) => {
        if (!params.value || params.value.length === 0) return <span className="text-xs text-gray-400">—</span>;
        return (
          <span className="inline-flex items-center gap-1 flex-wrap">
            {params.value.map((p: string) => (
              <span key={p} className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-100 text-emerald-700">{p}</span>
            ))}
          </span>
        );
      },
    },
    {
      field: 'location',
      headerName: 'Location',
      sortable: true,
      width: 110,
      valueFormatter: (params: ValueFormatterParams) => params.value || '-',
    },
    {
      field: 'domain',
      headerName: 'Website',
      sortable: true,
      width: 140,
      cellRenderer: (params: { value: string }) => {
        if (!params.value) return '-';
        const url = params.value.startsWith('http') ? params.value : `https://${params.value}`;
        return (
          <a href={url} target="_blank" rel="noopener noreferrer"
            className="text-blue-500 hover:text-blue-700 underline text-xs truncate block"
            title={params.value}>
            {params.value}
          </a>
        );
      },
    },
    {
      field: 'linkedin_url',
      headerName: 'LinkedIn',
      sortable: false,
      minWidth: 180,
      flex: 1,
      cellRenderer: (params: { value: string }) => {
        if (!params.value) return '-';
        // Extract /in/slug from full URL for display
        const slug = params.value.replace(/\/$/, '').split('/in/').pop() || params.value;
        return (
          <a href={params.value} target="_blank" rel="noopener noreferrer"
            className="text-blue-500 hover:text-blue-700 underline text-xs truncate block"
            title={params.value}>
            linkedin.com/in/{slug}
          </a>
        );
      },
    },
    {
      field: 'created_at',
      headerName: 'Added',
      sortable: true,
      width: 88,
      filter: DateColumnFilter,
      valueFormatter: (params: ValueFormatterParams) => {
        if (!params.value) return '-';
        return new Date(params.value).toLocaleDateString();
      },
    },
    {
      field: 'project_name',
      headerName: 'Project',
      sortable: true,
      width: 110,
      valueFormatter: (params: ValueFormatterParams) => params.value || '-',
    },
  ], [isDark, t, handleStatusChange, replyMode, processedContacts]);

  // System columns excluded from toggle list
  const SYSTEM_COLUMNS = new Set([undefined, 'Done']);
  const toggleableColumns = useMemo(() =>
    columnDefs.filter(c => c.headerName && !SYSTEM_COLUMNS.has(c.headerName)).map(c => c.headerName!),
    [columnDefs]
  );

  // Filter columns through visibility set + auto-hide Project when project is selected
  const visibleColumnDefs = useMemo(() => {
    const effectiveHidden = new Set(hiddenColumns);
    if (activeProject) effectiveHidden.add('Project');
    return columnDefs.filter(c => !c.headerName || !effectiveHidden.has(c.headerName));
  }, [columnDefs, hiddenColumns, activeProject]);

  // Default column settings
  const defaultColDef = useMemo<ColDef>(() => ({
    resizable: true,
    suppressMovable: false,
    filter: 'agTextColumnFilter',
    floatingFilter: false,
    filterParams: { debounceMs: 300 },
    cellStyle: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
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

  // Infinite scroll: load more when scrolled near bottom
  const onBodyScrollEnd = useCallback(() => {
    const grid = gridRef.current;
    if (!grid || !hasMore || isLoadingMore) return;
    const api = grid.api;
    if (!api) return;
    const lastRow = api.getLastDisplayedRowIndex();
    const totalRows = contacts.length;
    if (lastRow >= totalRows - 10) {
      loadMore();
    }
  }, [hasMore, isLoadingMore, contacts.length, loadMore]);

  // Build current filter object for exports
  const buildExportFilters = useCallback(() => {
    const filters: Record<string, any> = {};
    if (selectedContacts.length > 0) {
      filters.contact_ids = selectedContacts.map(c => c.id);
    } else {
      if (activeProject?.id) filters.project_id = activeProject.id;
      if (campaignFilters.length > 0) filters.campaign = campaignFilters.join(',');
      if (campaignIdFilter) filters.campaign_id = campaignIdFilter;
      if (statusFilters.length > 0) filters.status = statusFilters.join(',');
      if (sourceFilter) filters.source = sourceFilter;
      if (segmentFilters.length > 0) filters.segment = segmentFilters.join(',');
      if (geoFilter) filters.geo = geoFilter;
      if (debouncedSearch) filters.search = debouncedSearch;
      if (repliedFilter !== null) filters.has_replied = repliedFilter;
      if (createdAfter) filters.created_after = createdAfter;
      if (createdBefore) filters.created_before = createdBefore;
      if (suitableForFilter) filters.suitable_for = suitableForFilter;
      if (replyCategoryFilters.length > 0) filters.reply_category = replyCategoryFilters.join(',');
    }
    return filters;
  }, [selectedContacts, activeProject, campaignFilters, statusFilters, sourceFilter, segmentFilters, geoFilter, debouncedSearch, repliedFilter, createdAfter, createdBefore, suitableForFilter, replyCategoryFilters]);

  // Export states
  const [isExportingSheet, setIsExportingSheet] = useState(false);

  // Actions
  const handleExportCsv = async () => {
    try {
      const filters = buildExportFilters();
      const blob = await contactsApi.exportCsv(filters);

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

  const handleExportGoogleSheet = async () => {
    setIsExportingSheet(true);
    try {
      const filters = buildExportFilters();
      const result = await contactsApi.exportGoogleSheet(filters);
      toast.success(
        `Exported ${result.rows} contacts`,
        'Google Sheet created — opening in new tab'
      );
      window.open(result.url, '_blank');
    } catch (err) {
      console.error('Failed to export to Google Sheet:', err);
      toast.error('Google Sheet export failed', getErrorMessage(err));
    } finally {
      setIsExportingSheet(false);
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

  // CRM Spotlight
  const [showCRMSpotlight, setShowCRMSpotlight] = useState(false);

  // Cmd+K on CRM page opens CRM Spotlight (only when project is selected)
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        if (!activeProject) return; // need a project context
        e.preventDefault();
        e.stopPropagation();
        setShowCRMSpotlight(prev => !prev);
      }
    }
    document.addEventListener('keydown', handleKeyDown, true); // capture phase to beat Layout
    return () => document.removeEventListener('keydown', handleKeyDown, true);
  }, [activeProject]);

  const spotlightFilters = useMemo(() => ({
    has_replied: repliedFilter ?? true,
    reply_category: replyCategoryFilters.length > 0
      ? replyCategoryFilters.join(',')
      : 'interested,meeting_request,question,other',
    segment: segmentFilters.length > 0 ? segmentFilters.join(',') : undefined,
    geo: geoFilter || undefined,
    status: statusFilters.length > 0 ? statusFilters.join(',') : undefined,
    campaign: campaignFilters.length > 0 ? campaignFilters.join(',') : undefined,
    campaign_id: campaignIdFilter || undefined,
    search: debouncedSearch || undefined,
    created_after: createdAfter || undefined,
    created_before: createdBefore || undefined,
    reply_since: replySince || undefined,
  }), [repliedFilter, replyCategoryFilters, segmentFilters, geoFilter, statusFilters, campaignFilters, campaignIdFilter, debouncedSearch, createdAfter, createdBefore, replySince]);

  const [isPushingToSmartlead, setIsPushingToSmartlead] = useState(false);
  const [smartleadCampaignUrl, setSmartleadCampaignUrl] = useState<string | null>(null);

  const handlePushToSmartlead = async () => {
    if (selectedContacts.length === 0) return;
    setIsPushingToSmartlead(true);
    setSmartleadCampaignUrl(null);
    try {
      // If user selected all visible and there's a source_id filter, push ALL matching via server-side filter
      const allVisibleSelected = selectedContacts.length >= contacts.length;
      const useFilterPush = allVisibleSelected && sourceIdFilter;
      const result = useFilterPush
        ? await contactsApi.pushToSmartlead([], undefined, { source_id: sourceIdFilter, project_id: activeProject?.id })
        : await contactsApi.pushToSmartlead(selectedContacts.map(c => c.id));
      setSmartleadCampaignUrl(result.campaign_url);
      toast.success(
        `Campaign created: ${result.campaign_name}`,
        `${result.leads_added} leads added`
      );
      setSelectedContacts([]);
      loadContacts();
    } catch (err) {
      console.error('Failed to push to SmartLead:', err);
      toast.error('SmartLead push failed', getErrorMessage(err));
    } finally {
      setIsPushingToSmartlead(false);
    }
  };

  const handleRefresh = () => {
    loadContacts();
    loadStats();
    loadFilterOptions();
  };


  // Select a project — clears URL ref so sync effect uses activeProject from here on
  const selectProject = (project: Project | null) => {
    urlProjectRef.current = null;
    setActiveProject(project);
    setReplyMode(false);
    setPage(1);
    // project_id filter is sufficient — don't auto-set campaign filters
    // (auto-setting excluded contacts added via calendly, manual import, etc.)
    setCampaignFilters([]);
  };



  // Reply contacts (contacts with replies, not yet processed)
  const replyContacts = useMemo(() => {
    if (!replyMode) return [];
    return contacts.filter(c => !!c.last_reply_at && !processedContacts.has(c.id));
  }, [contacts, replyMode, processedContacts]);

  // totalPages removed — using infinite scroll

  const setDateRange = useCallback((after: string | null, before: string | null) => {
    setCreatedAfter(after);
    setCreatedBefore(before);
    setPage(1);
  }, []);

  const filterCtx = useMemo(() => ({
    campaignFilters,
    setCampaignFilters: (names: string[]) => { setCampaignFilters(names); setPage(1); },
    toggleCampaign,
    campaignIdFilter,
    setCampaignIdFilter: (id: string | null) => { setCampaignIdFilter(id); setPage(1); },
    statusFilters,
    setStatusFilters: (statuses: string[]) => { setStatusFilters(statuses); setPage(1); },
    toggleStatus,
    segmentFilters,
    setSegmentFilters: (segs: string[]) => { setSegmentFilters(segs); setPage(1); },
    toggleSegment,
    sourceFilter,
    setSourceFilter: (s: string | null) => { setSourceFilter(s); setPage(1); },
    geoFilter,
    setGeoFilter: (s: string | null) => { setGeoFilter(s); setPage(1); },
    repliedFilter,
    setRepliedFilter: (v: boolean | null) => { setRepliedFilter(v); setPage(1); },
    followupFilter,
    setFollowupFilter: (v: boolean | null) => { setFollowupFilter(v); setPage(1); },
    campaigns,
    ensureCampaignsLoaded,
    stats,
    filterOptions,
    resetPage,
    createdAfter,
    createdBefore,
    setDateRange,
    replyCategoryFilters,
    setReplyCategoryFilters: (cats: string[]) => { setReplyCategoryFilters(cats); setPage(1); },
    toggleReplyCategory,
  }), [campaignFilters, toggleCampaign, campaignIdFilter, statusFilters, toggleStatus, segmentFilters, toggleSegment, geoFilter, sourceFilter, repliedFilter, followupFilter, campaigns, ensureCampaignsLoaded, stats, filterOptions, resetPage, createdAfter, createdBefore, setDateRange, replyCategoryFilters, toggleReplyCategory]);

  return (
    <ContactsFilterContext.Provider value={filterCtx}>
    <div className="h-full flex flex-col" style={{ background: t.pageBg }}>
      {/* Command bar — minimal */}
      <div className="px-5 py-2" style={{ borderBottom: `1px solid ${isDark ? '#2a2a2a' : '#eee'}` }}>
        <div className="flex items-center gap-2.5">
          <span className="text-xs shrink-0 tabular-nums" style={{ color: t.text5 }}>{formatNumber(total)}</span>

          {/* Search */}
          <div className="relative flex-1 max-w-xs ml-auto">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: t.text5 }} />
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 rounded-md text-xs focus:outline-none focus:ring-1 transition-colors"
              style={{ background: isDark ? '#2a2a2a' : '#f5f5f5', border: 'none', color: t.text1, boxShadow: 'none' }}
            />
          </div>

          {/* Actions — icon-only */}
          <div className="flex items-center gap-0.5">
            <button onClick={handleRefresh} className="p-1.5 rounded-md transition-colors hover:opacity-70" style={{ color: t.text4 }} title="Refresh">
              <RefreshCw className={cn("w-3.5 h-3.5", isLoading && "animate-spin")} />
            </button>
            <button onClick={() => setShowAddModal(true)} className="p-1.5 rounded-md transition-colors hover:opacity-70" style={{ color: t.text4 }} title="Add">
              <Plus className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => setShowImportModal(true)} className="p-1.5 rounded-md transition-colors hover:opacity-70" style={{ color: t.text4 }} title="Import">
              <Upload className="w-3.5 h-3.5" />
            </button>
            <button onClick={handleExportCsv} className="p-1.5 rounded-md transition-colors hover:opacity-70" style={{ color: t.text4 }} title="Export CSV">
              <Download className="w-3.5 h-3.5" />
            </button>
            <button onClick={() => setShowEnrichModal(true)} className="p-1.5 rounded-md transition-colors hover:opacity-70" style={{ color: t.text4 }} title="Enrich from CSV">
              <Sparkles className="w-3.5 h-3.5" />
            </button>
            {activeProject && (
              <button
                onClick={() => setShowCRMSpotlight(true)}
                className="flex items-center gap-1 px-1.5 py-1 rounded-md transition-colors hover:opacity-70 text-[11px]"
                style={{ color: '#3b82f6' }}
                title="CRM Spotlight — analyze warm contacts (Cmd+K)"
              >
                <TrendingUp className="w-3.5 h-3.5" />
                <span>Spotlight</span>
              </button>
            )}
            <button
              onClick={handleExportGoogleSheet}
              disabled={isExportingSheet}
              className="p-1.5 rounded-md transition-colors hover:opacity-70 disabled:opacity-30"
              style={{ color: t.text4 }}
              title="Export to Google Sheet"
            >
              {isExportingSheet
                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                : <FileSpreadsheet className="w-3.5 h-3.5" />}
            </button>
            <div className="relative" ref={columnPickerRef}>
              <button
                onClick={() => setShowColumnPicker(v => !v)}
                className="flex items-center gap-1 px-1.5 py-1 rounded-md transition-colors hover:opacity-70 text-[11px]"
                style={{ color: t.text4 }}
                title="Toggle columns"
              >
                <Columns3 className="w-3.5 h-3.5" />
                <span>Columns</span>
              </button>
              {showColumnPicker && (
                <div
                  className="absolute right-0 top-full mt-1 z-50 rounded-lg shadow-lg py-1 min-w-[160px]"
                  style={{ background: isDark ? '#1e1e1e' : '#fff', border: `1px solid ${isDark ? '#333' : '#e5e5e5'}` }}
                >
                  {toggleableColumns.map(name => {
                    const isHidden = hiddenColumns.includes(name) || (name === 'Project' && !!activeProject);
                    const isAutoHidden = name === 'Project' && !!activeProject;
                    return (
                      <button
                        key={name}
                        onClick={() => !isAutoHidden && toggleColumnVisibility(name)}
                        className="w-full text-left px-3 py-1 flex items-center gap-2 text-xs transition-colors"
                        style={{
                          color: isAutoHidden ? (isDark ? '#555' : '#bbb') : (isDark ? '#ccc' : '#444'),
                          cursor: isAutoHidden ? 'default' : 'pointer',
                        }}
                        onMouseEnter={e => { if (!isAutoHidden) (e.currentTarget.style.background = isDark ? '#2a2a2a' : '#f5f5f5'); }}
                        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                      >
                        <span className={cn(
                          "w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                          !isHidden ? (isDark ? "bg-indigo-500 border-indigo-500" : "bg-indigo-600 border-indigo-600") : (isDark ? "border-neutral-600" : "border-neutral-300")
                        )}>
                          {!isHidden && <Check className="w-2.5 h-2.5 text-white" />}
                        </span>
                        {name}
                        {isAutoHidden && <span className="text-[10px] ml-auto" style={{ color: isDark ? '#555' : '#bbb' }}>auto</span>}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            {selectedContacts.length > 0 && (
              <>
                <button
                  onClick={handlePushToSmartlead}
                  disabled={isPushingToSmartlead}
                  className="flex items-center gap-1 px-2 py-1 rounded-md transition-colors text-[11px] hover:opacity-80 disabled:opacity-40"
                  style={{ color: '#3b82f6' }}
                  title="Create SmartLead draft campaign"
                >
                  {isPushingToSmartlead
                    ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    : <Send className="w-3.5 h-3.5" />}
                  <span>SmartLead ({selectedContacts.length >= contacts.length && sourceIdFilter && total > selectedContacts.length ? total : selectedContacts.length})</span>
                </button>
                <button onClick={handleDeleteSelected} className="p-1.5 rounded-md transition-colors text-red-400 hover:text-red-300" title="Delete Selected">
                  <Trash2 className="w-3.5 h-3.5" />
                  <span className="ml-0.5 text-[10px]">{selectedContacts.length}</span>
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* SmartLead campaign link banner */}
      {smartleadCampaignUrl && (
        <div className="mx-5 mt-1.5 mb-0.5 flex items-center gap-2 px-3 py-1.5 rounded-md text-xs"
          style={{ background: isDark ? '#1a2332' : '#eff6ff', border: `1px solid ${isDark ? '#1e3a5f' : '#bfdbfe'}` }}>
          <Send className="w-3.5 h-3.5 shrink-0" style={{ color: '#3b82f6' }} />
          <span style={{ color: isDark ? '#93c5fd' : '#1d4ed8' }}>Draft campaign created</span>
          <a
            href={smartleadCampaignUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 hover:underline font-medium"
            style={{ color: '#3b82f6' }}
          >
            Open in SmartLead <ExternalLink className="w-3 h-3" />
          </a>
          <button onClick={() => setSmartleadCampaignUrl(null)} className="ml-auto p-0.5 rounded hover:opacity-70" style={{ color: isDark ? '#64748b' : '#94a3b8' }}>
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* AG Grid */}
      <div className="flex-1 px-3 pt-1 pb-0">
        <SectionErrorBoundary>
          <div className={`${isDark ? 'ag-theme-alpine-dark' : 'ag-theme-alpine'} h-full w-full`}>
            <AgGridReact
              ref={gridRef}
              theme={AG_GRID_THEME}
              onRowClicked={(event) => {
                const target = event.event?.target as HTMLElement | undefined;
                if (target && (target.tagName === 'SELECT' || target.tagName === 'OPTION' || target.closest?.('select'))) {
                  return;
                }
                if (event.data) {
                  setSelectedContact(event.data);
                  setShowContactModal(true);
                }
              }}
              rowData={contacts}
              columnDefs={visibleColumnDefs}
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
              onBodyScrollEnd={onBodyScrollEnd}
              animateRows={false}
              suppressCellFocus={true}
              enableCellTextSelection={true}
              getRowId={(params) => String(params.data.id)}
              overlayLoadingTemplate='<span style="color:#888;font-size:12px">Loading...</span>'
              overlayNoRowsTemplate='<span style="color:#888;font-size:12px">No contacts</span>'
            />
          </div>
        </SectionErrorBoundary>
      </div>

      {/* Infinite scroll status */}
      {isLoadingMore && (
        <div className="flex items-center justify-center py-1.5" style={{ color: t.text5 }}>
          <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
          <span className="text-[11px]">Loading more...</span>
        </div>
      )}
      {!hasMore && contacts.length > 0 && (
        <div className="text-center py-1" style={{ color: t.text6 }}>
          <span className="text-[10px]">{formatNumber(contacts.length)} of {formatNumber(total)}</span>
        </div>
      )}

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

      {/* Enrich Modal */}
      {showEnrichModal && (
        <EnrichContactsModal
          projects={projects}
          activeProjectId={activeProject?.id ?? null}
          onClose={() => setShowEnrichModal(false)}
          onSuccess={() => {
            setShowEnrichModal(false);
            loadContacts();
            loadStats();
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

      {/* CRM Spotlight */}
      <CRMSpotlight
        open={showCRMSpotlight}
        onClose={() => setShowCRMSpotlight(false)}
        projectId={activeProject?.id || null}
        projectName={activeProject?.name || null}
        filters={spotlightFilters}
        contactCount={total}
      />

      {/* Contact Detail Modal */}
      <SectionErrorBoundary>
        <ContactDetailModal
          contact={selectedContact}
          isOpen={showContactModal}
          initialCampaignKey={initialCampaignKey}
          initialTab={searchParams.get('tab') as 'details' | 'conversation' | 'source' || undefined}
          onClose={() => {
            setShowContactModal(false);
            setSelectedContact(null);
            setInitialCampaignKey(null);
            const p = new URLSearchParams(searchParams);
            p.delete('contact_id');
            p.delete('campaign');
            setSearchParams(p, { replace: true });
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
  const { isDark } = useTheme();
  const t = themeColors(isDark);
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
      <div className="relative rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col" style={{ background: t.cardBg }}>
        <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: `1px solid ${t.cardBorder}` }}>
          <h2 className="text-lg font-semibold" style={{ color: t.text1 }}>Add Contact</h2>
          <button onClick={onClose} className="p-2 rounded-lg" style={{ color: t.text3 }}>
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-auto p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Email *</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="input w-full"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Status</label>
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
              <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>First Name</label>
              <input
                type="text"
                value={formData.first_name}
                onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Last Name</label>
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
              <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Company</label>
              <input
                type="text"
                value={formData.company_name}
                onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Job Title</label>
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
              <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Project</label>
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
              <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Segment</label>
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
              <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Phone</label>
              <input
                type="text"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="input w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Location</label>
              <input
                type="text"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                className="input w-full"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>LinkedIn URL</label>
            <input
              type="url"
              value={formData.linkedin_url}
              onChange={(e) => setFormData({ ...formData, linkedin_url: e.target.value })}
              className="input w-full"
              placeholder="https://linkedin.com/in/..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Notes</label>
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

        <div className="px-6 py-4 flex gap-3" style={{ borderTop: `1px solid ${t.cardBorder}` }}>
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

  const { isDark } = useTheme();
  const t = themeColors(isDark);

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative rounded-2xl shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col" style={{ background: t.cardBg }}>
        <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: `1px solid ${t.cardBorder}` }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-100 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold" style={{ color: t.text1 }}>AI SDR Dashboard</h2>
              <p className="text-sm" style={{ color: t.text3 }}>Generate TAM, GTM plans, and pitch templates per project</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg" style={{ color: t.text3 }}>
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-hidden flex">
          {/* Left panel - Projects list */}
          <div className="w-1/3 overflow-auto" style={{ borderRight: `1px solid ${t.cardBorder}` }}>
            <div className="p-4" style={{ borderBottom: `1px solid ${t.cardBorder}` }}>
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
                <div className="text-center py-8 text-sm" style={{ color: t.text3 }}>
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
                        : (isDark ? "hover:bg-neutral-800" : "hover:bg-neutral-50")
                    )}
                    onClick={() => loadProjectAISDR(project.id)}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-sm truncate">{project.name}</div>
                      <div className="text-xs" style={{ color: t.text3 }}>{project.contact_count} contacts</div>
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

        <div className="px-6 py-4" style={{ borderTop: `1px solid ${t.cardBorder}` }}>
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
  const { isDark } = useTheme();
  const t = themeColors(isDark);
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
      <div className="relative rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col" style={{ background: t.cardBg }}>
        <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: `1px solid ${t.cardBorder}` }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-100 flex items-center justify-center">
              <Upload className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold" style={{ color: t.text1 }}>Import Contacts</h2>
              <p className="text-sm" style={{ color: t.text3 }}>Upload a CSV file with contact data</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg" style={{ color: t.text3 }}>
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
                  : (isDark ? "border-neutral-700 hover:border-indigo-500" : "border-neutral-200 hover:border-indigo-300 hover:bg-indigo-50/30")
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
                  <Upload className="w-10 h-10 mx-auto mb-3" style={{ color: t.text4 }} />
                  <p className="text-sm mb-1" style={{ color: t.text2 }}>Click to select a CSV file</p>
                  <p className="text-xs" style={{ color: t.text4 }}>or drag and drop</p>
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
              <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>
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
              <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>
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
              <p className="text-xs mt-1" style={{ color: t.text3 }}>
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
              <label htmlFor="skipDuplicates" className="text-sm" style={{ color: t.text2 }}>
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

        <div className="px-6 py-4 flex gap-3" style={{ borderTop: `1px solid ${t.cardBorder}` }}>
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


/* ─── Enrich Contacts Modal ─── */
function EnrichContactsModal({
  projects,
  activeProjectId,
  onClose,
  onSuccess,
}: {
  projects: Project[];
  activeProjectId: number | null;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [projectId, setProjectId] = useState<number | undefined>(activeProjectId || undefined);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<EnrichResult | null>(null);
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

  const handleEnrich = async () => {
    if (!file) {
      setError('Please select a file');
      return;
    }

    setIsUploading(true);
    setError(null);
    setResult(null);

    try {
      const enrichResult = await contactsApi.enrichCsv(file, {
        project_id: projectId,
      });
      setResult(enrichResult);

      if (enrichResult.enriched > 0) {
        toast.success('Enrichment complete', `${enrichResult.enriched} contacts enriched`);
        setTimeout(() => onSuccess(), 2000);
      } else if (enrichResult.not_found > 0) {
        toast.warning('No matches', `${enrichResult.not_found} emails not found in CRM`);
      } else {
        toast.info('Nothing to enrich', 'All matched contacts already have complete data');
      }
    } catch (err: unknown) {
      const message = getErrorMessage(err);
      setError(message);
      toast.error('Enrich failed', message);
    } finally {
      setIsUploading(false);
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col" style={{ background: t.cardBg }}>
        <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: `1px solid ${t.cardBorder}` }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-purple-100 flex items-center justify-center">
              <Sparkles className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold" style={{ color: t.text1 }}>Enrich Contacts</h2>
              <p className="text-sm" style={{ color: t.text3 }}>Fill missing data from CSV (match by email)</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg" style={{ color: t.text3 }}>
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-6 space-y-6">
          {/* File Upload */}
          <div
            className={cn(
              "border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer",
              file
                ? "border-green-300 bg-green-50"
                : (isDark ? "border-neutral-700 hover:border-purple-500" : "border-neutral-200 hover:border-purple-300 hover:bg-purple-50/30")
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
                <Sparkles className="w-10 h-10 mx-auto mb-3" style={{ color: t.text4 }} />
                <p className="text-sm mb-1" style={{ color: t.text2 }}>Click to select a CSV file</p>
                <p className="text-xs" style={{ color: t.text4 }}>Must have an email column + data columns (name, title, company...)</p>
              </>
            )}
          </div>

          {/* Project filter */}
          <div>
            <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>
              Match within Project (optional)
            </label>
            <select
              value={projectId || ''}
              onChange={(e) => setProjectId(e.target.value ? Number(e.target.value) : undefined)}
              className="input w-full"
            >
              <option value="">All projects</option>
              {projects.map(p => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <p className="text-xs mt-1" style={{ color: t.text3 }}>
              Only enrich contacts in selected project, or all if empty
            </p>
          </div>

          {/* Info */}
          <div className="text-xs p-3 rounded-xl" style={{ background: isDark ? '#1a1a2e' : '#f0f0ff', color: t.text3 }}>
            Only fills empty fields. Existing data is never overwritten.
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2 p-4 rounded-xl bg-red-50 text-red-700">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="text-sm">{error}</div>
            </div>
          )}

          {/* Results */}
          {result && (
            <div className={cn(
              "p-4 rounded-xl",
              result.enriched > 0 ? "bg-green-50" : "bg-amber-50"
            )}>
              <div className="flex items-center gap-2 mb-3">
                {result.enriched > 0 ? (
                  <Check className="w-5 h-5 text-green-600" />
                ) : (
                  <AlertCircle className="w-5 h-5 text-amber-600" />
                )}
                <span className={cn(
                  "font-medium",
                  result.enriched > 0 ? "text-green-700" : "text-amber-700"
                )}>
                  Enrichment {result.enriched > 0 ? 'Complete' : 'Results'}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-4 mb-3">
                <div className="text-center p-2 bg-white rounded-lg">
                  <div className="text-lg font-semibold text-green-600">{result.enriched}</div>
                  <div className="text-xs text-neutral-500">Enriched</div>
                </div>
                <div className="text-center p-2 bg-white rounded-lg">
                  <div className="text-lg font-semibold text-amber-600">{result.skipped}</div>
                  <div className="text-xs text-neutral-500">Already full</div>
                </div>
                <div className="text-center p-2 bg-white rounded-lg">
                  <div className="text-lg font-semibold text-neutral-500">{result.not_found}</div>
                  <div className="text-xs text-neutral-500">Not found</div>
                </div>
              </div>

              {result.errors.length > 0 && (
                <div className="mt-2 text-xs text-red-600 space-y-1">
                  {result.errors.map((e, i) => <div key={i}>{e}</div>)}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 flex gap-3" style={{ borderTop: `1px solid ${t.cardBorder}` }}>
          <button onClick={onClose} className="btn btn-secondary flex-1">
            {result ? 'Close' : 'Cancel'}
          </button>
          {!result && (
            <button
              onClick={handleEnrich}
              disabled={!file || isUploading}
              className="btn btn-primary flex-1"
            >
              {isUploading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Enriching...</>
              ) : (
                <><Sparkles className="w-4 h-4" /> Enrich Contacts</>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
