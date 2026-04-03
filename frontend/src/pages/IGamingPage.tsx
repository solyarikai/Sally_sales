import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { ModuleRegistry, AllCommunityModule } from 'ag-grid-community';
import type { ColDef, GridApi, SortChangedEvent, CellValueChangedEvent } from 'ag-grid-community';
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';
import {
  Users, Building2, UserSearch, Upload, Search, RefreshCw,
  Trash2, Tag, ChevronLeft, ChevronRight,
  Database, Mail, Linkedin, Globe, Merge, X, Plus, Play, Sparkles, Loader2,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { useToast } from '../components/Toast';
import { igamingApi } from '../api/igaming';
import type {
  IGamingContact, IGamingCompany, IGamingEmployee, IGamingImport,
  IGamingStats, FilterOption, ImportUploadResponse, AIColumn,
} from '../api/igaming';

ModuleRegistry.registerModules([AllCommunityModule]);
const AG_GRID_THEME = 'legacy';

type Tab = 'contacts' | 'companies' | 'employees' | 'import';

// ── Business type labels ──────────────────────────────────────────────
const BUSINESS_TYPE_LABELS: Record<string, { label: string; color: string }> = {
  operator: { label: 'Operator', color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' },
  affiliate: { label: 'Affiliate', color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  supplier: { label: 'Supplier', color: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' },
  platform: { label: 'Platform', color: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' },
  payment: { label: 'Payment', color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' },
  marketing: { label: 'Marketing', color: 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400' },
  professional_services: { label: 'Pro Services', color: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400' },
  media: { label: 'Media', color: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400' },
  regulator: { label: 'Regulator', color: 'bg-gray-100 text-gray-700 dark:bg-gray-700/30 dark:text-gray-400' },
  other: { label: 'Other', color: 'bg-neutral-100 text-neutral-600 dark:bg-neutral-700/30 dark:text-neutral-400' },
};

// ── Column mapping for import ─────────────────────────────────────────
const MODEL_FIELDS = [
  { value: '', label: '— Skip —' },
  { value: 'source_id', label: 'Source ID' },
  { value: 'first_name', label: 'First Name' },
  { value: 'last_name', label: 'Last Name' },
  { value: 'email', label: 'Email' },
  { value: 'phone', label: 'Phone' },
  { value: 'linkedin_url', label: 'LinkedIn' },
  { value: 'job_title', label: 'Job Title' },
  { value: 'organization_name', label: 'Company' },
  { value: 'website_url', label: 'Website' },
  { value: 'business_type_raw', label: 'Business Type' },
  { value: 'bio', label: 'Bio' },
  { value: 'other_contact', label: 'Other Contact' },
  { value: 'sector', label: 'Sector' },
  { value: 'regions', label: 'Regions' },
  { value: 'new_regions_targeting', label: 'New Regions' },
  { value: 'channel', label: 'Channel' },
  { value: 'products_services', label: 'Products/Services' },
];

// Auto-detect mapping by CSV column name
const AUTO_MAP: Record<string, string> = {
  id: 'source_id',
  firstName: 'first_name',
  first_name: 'first_name',
  'First Name': 'first_name',
  lastName: 'last_name',
  last_name: 'last_name',
  'Last Name': 'last_name',
  email: 'email',
  Email: 'email',
  Phone: 'phone',
  phone: 'phone',
  linkedin: 'linkedin_url',
  LinkedIn: 'linkedin_url',
  linkedin_url: 'linkedin_url',
  jobTitle: 'job_title',
  job_title: 'job_title',
  'Job Title': 'job_title',
  organization: 'organization_name',
  Organization: 'organization_name',
  company: 'organization_name',
  Company: 'organization_name',
  websiteUrl: 'website_url',
  website: 'website_url',
  Website: 'website_url',
  typeOfBusiness: 'business_type_raw',
  type_of_business: 'business_type_raw',
  'Type of Business': 'business_type_raw',
  bio: 'bio',
  Bio: 'bio',
  'Other contact': 'other_contact',
  sector: 'sector',
  Sector: 'sector',
  regionsOfOperation: 'regions',
  newRegionsTargeting: 'new_regions_targeting',
  channelOfOperation: 'channel',
  productsServicesOffering: 'products_services',
};

// ══════════════════════════════════════════════════════════════════════
// Main Page Component
// ══════════════════════════════════════════════════════════════════════

export function IGamingPage() {
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const toastCtx = useToast();
  const toast = useCallback((msg: string, type: 'success' | 'error' | 'info' = 'info') => {
    toastCtx[type](msg);
  }, [toastCtx]);

  const [tab, setTab] = useState<Tab>('contacts');
  const [stats, setStats] = useState<IGamingStats | null>(null);
  const [isLoadingStats, setIsLoadingStats] = useState(true);

  // Load stats
  useEffect(() => {
    igamingApi.getStats().then(setStats).catch(() => {}).finally(() => setIsLoadingStats(false));
  }, [tab]);

  const tabs: { key: Tab; label: string; icon: any; count?: number }[] = [
    { key: 'contacts', label: 'Contacts', icon: Users, count: stats?.total_contacts },
    { key: 'companies', label: 'Companies', icon: Building2, count: stats?.total_companies },
    { key: 'employees', label: 'Employees', icon: UserSearch, count: stats?.total_employees },
    { key: 'import', label: 'Import', icon: Upload },
  ];

  return (
    <div className="h-full flex flex-col" style={{ background: t.pageBg }}>
      {/* Header */}
      <div className="flex-shrink-0 px-5 pt-4 pb-2">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Database size={20} style={{ color: t.text2 }} />
            <h1 className="text-lg font-semibold" style={{ color: t.text1 }}>iGaming Database</h1>
            {stats && (
              <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: t.badgeBg, color: t.badgeText }}>
                {stats.total_contacts.toLocaleString()} contacts
              </span>
            )}
          </div>
        </div>

        {/* Stats cards */}
        {stats && !isLoadingStats && (
          <div className="grid grid-cols-6 gap-2 mb-3">
            {[
              { label: 'Contacts', value: stats.total_contacts, icon: Users },
              { label: 'Companies', value: stats.total_companies, icon: Building2 },
              { label: 'With Email', value: stats.contacts_with_email, icon: Mail },
              { label: 'With LinkedIn', value: stats.contacts_with_linkedin, icon: Linkedin },
              { label: 'With Website', value: stats.companies_with_website, icon: Globe },
              { label: 'Employees', value: stats.total_employees, icon: UserSearch },
            ].map(({ label, value, icon: Icon }) => (
              <div key={label} className="px-3 py-2 rounded-lg border" style={{ background: t.cardBg, borderColor: t.cardBorder }}>
                <div className="flex items-center gap-1.5">
                  <Icon size={13} style={{ color: t.text4 }} />
                  <span className="text-[11px]" style={{ color: t.text4 }}>{label}</span>
                </div>
                <div className="text-base font-semibold mt-0.5" style={{ color: t.text1 }}>
                  {value.toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Tab bar */}
        <div className="flex gap-1 border-b" style={{ borderColor: t.divider }}>
          {tabs.map(({ key, label, icon: Icon, count }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
                tab === key
                  ? 'border-current'
                  : 'border-transparent hover:border-gray-300'
              )}
              style={{ color: tab === key ? t.text1 : t.text4 }}
            >
              <Icon size={15} />
              {label}
              {count !== undefined && (
                <span className="text-[10px] px-1.5 py-0 rounded-full ml-0.5"
                  style={{ background: t.badgeBg, color: t.badgeText }}>
                  {count.toLocaleString()}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 min-h-0">
        {tab === 'contacts' && <ContactsTab isDark={isDark} t={t} toast={toast} onStatsChange={() => igamingApi.getStats().then(setStats)} />}
        {tab === 'companies' && <CompaniesTab isDark={isDark} t={t} toast={toast} />}
        {tab === 'employees' && <EmployeesTab isDark={isDark} t={t} toast={toast} />}
        {tab === 'import' && <ImportTab isDark={isDark} t={t} toast={toast} onImportDone={() => { setTab('contacts'); igamingApi.getStats().then(setStats); }} />}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Contacts Tab
// ══════════════════════════════════════════════════════════════════════

function ContactsTab({ isDark, t, toast, onStatsChange }: { isDark: boolean; t: any; toast: any; onStatsChange: () => void }) {
  const gridRef = useRef<AgGridReact>(null);
  const [gridApi, setGridApi] = useState<GridApi | null>(null);

  const [contacts, setContacts] = useState<IGamingContact[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(100);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [businessType, setBusinessType] = useState('');
  const [conference, setConference] = useState('');
  const [hasEmail, setHasEmail] = useState<string>('');
  const [sortBy, setSortBy] = useState('created_at');
  const [sortOrder, setSortOrder] = useState('desc');
  const [selected, setSelected] = useState<IGamingContact[]>([]);
  const [showAIColumn, setShowAIColumn] = useState(false);

  // Filter options
  const [conferences, setConferences] = useState<FilterOption[]>([]);
  const [businessTypes, setBusinessTypes] = useState<FilterOption[]>([]);

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => { setDebouncedSearch(search); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [search]);

  // Load filter options
  useEffect(() => {
    igamingApi.getConferences().then(setConferences).catch(() => {});
    igamingApi.getBusinessTypes().then(setBusinessTypes).catch(() => {});
  }, []);

  // Load contacts
  const loadContacts = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: Record<string, any> = {
        page, page_size: pageSize, sort_by: sortBy, sort_order: sortOrder,
      };
      if (debouncedSearch) params.search = debouncedSearch;
      if (businessType) params.business_type = businessType;
      if (conference) params.source_conference = conference;
      if (hasEmail === 'yes') params.has_email = true;
      if (hasEmail === 'no') params.has_email = false;

      const data = await igamingApi.listContacts(params);
      setContacts(data.contacts || []);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch {
      toast('Failed to load contacts');
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize, debouncedSearch, businessType, conference, hasEmail, sortBy, sortOrder, toast]);

  useEffect(() => { loadContacts(); }, [loadContacts]);

  // Inline edit
  const onCellValueChanged = useCallback(async (e: CellValueChangedEvent) => {
    const contact = e.data as IGamingContact;
    const field = e.colDef.field!;
    try {
      await igamingApi.updateContact(contact.id, { [field]: e.newValue });
    } catch {
      toast('Failed to save');
      e.api.undoCellEditing();
    }
  }, [toast]);

  // Sort
  const onSortChanged = useCallback((e: SortChangedEvent) => {
    const cols = e.api.getColumnState();
    const sorted = cols.find(c => c.sort);
    if (sorted) {
      setSortBy(sorted.colId || 'created_at');
      setSortOrder(sorted.sort || 'desc');
    }
    setPage(1);
  }, []);

  // Selection
  const onSelectionChanged = useCallback(() => {
    if (!gridApi) return;
    setSelected(gridApi.getSelectedRows() as IGamingContact[]);
  }, [gridApi]);

  // Batch actions
  const handleBatchDelete = useCallback(async () => {
    if (!selected.length) return;
    if (!confirm(`Delete ${selected.length} contacts?`)) return;
    try {
      await igamingApi.batchDeleteContacts(selected.map(c => c.id));
      toast(`Deleted ${selected.length} contacts`);
      loadContacts();
      onStatsChange();
    } catch { toast('Failed to delete'); }
  }, [selected, loadContacts, toast, onStatsChange]);

  const handleBatchTag = useCallback(async () => {
    if (!selected.length) return;
    const tag = prompt('Enter tag:');
    if (!tag) return;
    try {
      await igamingApi.batchTagContacts(selected.map(c => c.id), tag);
      toast(`Tagged ${selected.length} contacts`);
      loadContacts();
    } catch { toast('Failed to tag'); }
  }, [selected, loadContacts, toast]);

  // Autofill
  const handleAutofill = useCallback(async () => {
    try {
      const res = await igamingApi.runAutofill();
      toast(`Autofill: ${res.contacts_website_updated} websites, ${res.contacts_type_updated} types updated`);
      loadContacts();
    } catch { toast('Autofill failed'); }
  }, [loadContacts, toast]);

  // Columns
  const columnDefs = useMemo<ColDef[]>(() => [
    {
      headerCheckboxSelection: true,
      checkboxSelection: true,
      width: 40,
      pinned: 'left',
      suppressSizeToFit: true,
      resizable: false,
      sortable: false,
    },
    { field: 'first_name', headerName: 'First Name', width: 120, editable: true, sortable: true },
    { field: 'last_name', headerName: 'Last Name', width: 120, editable: true, sortable: true },
    { field: 'email', headerName: 'Email', width: 200, editable: true, sortable: true },
    { field: 'linkedin_url', headerName: 'LinkedIn', width: 160, editable: true },
    { field: 'job_title', headerName: 'Title', width: 160, editable: true, sortable: true },
    { field: 'organization_name', headerName: 'Company', width: 160, editable: true, sortable: true },
    { field: 'website_url', headerName: 'Website', width: 140, editable: true },
    {
      field: 'business_type', headerName: 'Type', width: 130, sortable: true, editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: {
        values: ['operator', 'affiliate', 'supplier', 'platform', 'payment', 'marketing', 'professional_services', 'media', 'regulator', 'other'],
      },
      cellRenderer: (p: any) => {
        const info = BUSINESS_TYPE_LABELS[p.value] || BUSINESS_TYPE_LABELS.other;
        return <span className={`${info.color} px-1.5 py-0.5 rounded text-[11px] font-medium`}>{info.label}</span>;
      },
    },
    { field: 'sector', headerName: 'Sector', width: 130, sortable: true, editable: true },
    {
      field: 'regions', headerName: 'Regions', width: 150,
      valueFormatter: (p: any) => (p.value || []).join(', '),
    },
    { field: 'source_conference', headerName: 'Conference', width: 110, sortable: true },
    {
      field: 'tags', headerName: 'Tags', width: 120,
      valueFormatter: (p: any) => (p.value || []).join(', '),
    },
    { field: 'bio', headerName: 'Bio', width: 200, editable: true },
    { field: 'phone', headerName: 'Phone', width: 120, editable: true },
    { field: 'notes', headerName: 'Notes', width: 200, editable: true },
  ], []);

  return (
    <div className="h-full flex flex-col px-5 pb-3">
      {/* Toolbar */}
      <div className="flex items-center gap-2 py-2 flex-shrink-0">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: t.text5 }} />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search name, email, company..."
            className="w-full pl-8 pr-3 py-1.5 text-sm rounded-md border outline-none"
            style={{ background: t.inputBg, borderColor: t.inputBorder, color: t.text1 }}
          />
        </div>

        <select value={businessType} onChange={e => { setBusinessType(e.target.value); setPage(1); }}
          className="text-sm px-2 py-1.5 rounded-md border outline-none"
          style={{ background: t.inputBg, borderColor: t.inputBorder, color: t.text1 }}>
          <option value="">All Types</option>
          {businessTypes.map(bt => (
            <option key={bt.value} value={bt.value}>
              {BUSINESS_TYPE_LABELS[bt.value]?.label || bt.value} ({bt.count})
            </option>
          ))}
        </select>

        <select value={conference} onChange={e => { setConference(e.target.value); setPage(1); }}
          className="text-sm px-2 py-1.5 rounded-md border outline-none"
          style={{ background: t.inputBg, borderColor: t.inputBorder, color: t.text1 }}>
          <option value="">All Conferences</option>
          {conferences.map(c => (
            <option key={c.value} value={c.value}>{c.value} ({c.count})</option>
          ))}
        </select>

        <select value={hasEmail} onChange={e => { setHasEmail(e.target.value); setPage(1); }}
          className="text-sm px-2 py-1.5 rounded-md border outline-none"
          style={{ background: t.inputBg, borderColor: t.inputBorder, color: t.text1 }}>
          <option value="">Email: Any</option>
          <option value="yes">Has Email</option>
          <option value="no">No Email</option>
        </select>

        <button onClick={handleAutofill} className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md border hover:opacity-80"
          style={{ borderColor: t.cardBorder, color: t.text3 }}>
          <RefreshCw size={12} /> Autofill
        </button>

        <button onClick={() => setShowAIColumn(true)} className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md border hover:opacity-80"
          style={{ borderColor: t.cardBorder, color: t.text3 }}>
          <Sparkles size={12} /> AI Column
        </button>
      </div>

      {/* Batch actions bar */}
      {selected.length > 0 && (
        <div className="flex items-center gap-2 py-1.5 px-3 rounded-md mb-1 flex-shrink-0"
          style={{ background: isDark ? '#1e3a5f' : '#eff6ff', border: '1px solid', borderColor: isDark ? '#2563eb' : '#93c5fd' }}>
          <span className="text-xs font-medium" style={{ color: t.text1 }}>{selected.length} selected</span>
          <button onClick={handleBatchTag} className="flex items-center gap-1 text-xs px-2 py-1 rounded border hover:opacity-80"
            style={{ borderColor: t.cardBorder, color: t.text2 }}>
            <Tag size={11} /> Tag
          </button>
          <button onClick={handleBatchDelete} className="flex items-center gap-1 text-xs px-2 py-1 rounded border hover:opacity-80 text-red-500"
            style={{ borderColor: t.cardBorder }}>
            <Trash2 size={11} /> Delete
          </button>
          <button onClick={() => { gridApi?.deselectAll(); setSelected([]); }}
            className="ml-auto text-xs px-2 py-1 rounded hover:opacity-80"
            style={{ color: t.text4 }}>
            <X size={12} />
          </button>
        </div>
      )}

      {/* Grid */}
      <div className={cn('flex-1 min-h-0', isDark ? 'ag-theme-alpine-dark' : 'ag-theme-alpine')}>
        <AgGridReact
          ref={gridRef}
          theme={AG_GRID_THEME}
          onGridReady={e => setGridApi(e.api)}
          columnDefs={columnDefs}
          rowData={contacts}
          rowSelection="multiple"
          suppressRowClickSelection
          onSelectionChanged={onSelectionChanged}
          onSortChanged={onSortChanged}
          onCellValueChanged={onCellValueChanged}
          loading={isLoading}
          animateRows={false}
          headerHeight={32}
          rowHeight={32}
          defaultColDef={{ resizable: true, filter: false, suppressMovable: true, singleClickEdit: true }}
        />
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between pt-2 flex-shrink-0">
        <span className="text-xs" style={{ color: t.text4 }}>
          {total.toLocaleString()} contacts — page {page}/{totalPages}
        </span>
        <div className="flex items-center gap-1">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
            className="p-1 rounded hover:opacity-70 disabled:opacity-30" style={{ color: t.text3 }}>
            <ChevronLeft size={16} />
          </button>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
            className="p-1 rounded hover:opacity-70 disabled:opacity-30" style={{ color: t.text3 }}>
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      {/* AI Column Modal */}
      {showAIColumn && (
        <AIColumnModal
          isDark={isDark} t={t} toast={toast}
          target="contact"
          onClose={() => setShowAIColumn(false)}
        />
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Companies Tab
// ══════════════════════════════════════════════════════════════════════

function CompaniesTab({ isDark, t, toast }: { isDark: boolean; t: any; toast: any }) {
  const gridRef = useRef<AgGridReact>(null);
  const [gridApi, setGridApi] = useState<GridApi | null>(null);

  const [companies, setCompanies] = useState<IGamingCompany[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(100);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);

  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [businessType, setBusinessType] = useState('');
  const [hasWebsite, setHasWebsite] = useState<string>('yes'); // default: only with website
  const [sortBy, setSortBy] = useState('contacts_count');
  const [sortOrder, setSortOrder] = useState('desc');
  const [selected, setSelected] = useState<IGamingCompany[]>([]);
  const [businessTypes, setBusinessTypes] = useState<FilterOption[]>([]);
  const [showEmployeeSearch, setShowEmployeeSearch] = useState(false);
  const [showAIColumn, setShowAIColumn] = useState(false);
  const [isFindingWebsites, setIsFindingWebsites] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => { setDebouncedSearch(search); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    igamingApi.getBusinessTypes().then(setBusinessTypes).catch(() => {});
  }, []);

  const loadCompanies = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: Record<string, any> = {
        page, page_size: pageSize, sort_by: sortBy, sort_order: sortOrder,
      };
      if (debouncedSearch) params.search = debouncedSearch;
      if (businessType) params.business_type = businessType;
      if (hasWebsite === 'yes') params.has_website = true;
      if (hasWebsite === 'no') params.has_website = false;

      const data = await igamingApi.listCompanies(params);
      setCompanies(data.companies || []);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch { toast('Failed to load companies'); }
    finally { setIsLoading(false); }
  }, [page, pageSize, debouncedSearch, businessType, hasWebsite, sortBy, sortOrder, toast]);

  useEffect(() => { loadCompanies(); }, [loadCompanies]);

  const onCellValueChanged = useCallback(async (e: CellValueChangedEvent) => {
    const company = e.data as IGamingCompany;
    const field = e.colDef.field!;
    try { await igamingApi.updateCompany(company.id, { [field]: e.newValue }); }
    catch { toast('Failed to save'); e.api.undoCellEditing(); }
  }, [toast]);

  const onSortChanged = useCallback((e: SortChangedEvent) => {
    const cols = e.api.getColumnState();
    const sorted = cols.find(c => c.sort);
    if (sorted) { setSortBy(sorted.colId || 'contacts_count'); setSortOrder(sorted.sort || 'desc'); }
    setPage(1);
  }, []);

  const handleMerge = useCallback(async () => {
    if (selected.length !== 2) { toast('Select exactly 2 companies to merge'); return; }
    const [a, b] = selected;
    if (!confirm(`Merge "${a.name}" INTO "${b.name}"? All contacts/employees will move to "${b.name}".`)) return;
    try {
      const res = await igamingApi.mergeCompanies(a.id, b.id);
      toast(`Merged: ${res.contacts_moved} contacts moved`);
      loadCompanies();
    } catch { toast('Merge failed'); }
  }, [selected, loadCompanies, toast]);

  const handleFindWebsites = useCallback(async () => {
    const ids = selected.length > 0 ? selected.filter(c => !c.website).map(c => c.id) : undefined;
    const count = ids ? ids.length : 'all';
    const limit = ids ? ids.length : 100;
    if (!confirm(`Find websites for ${count} companies without site via Yandex + AI?\nThis may take ~${limit} seconds.`)) return;
    setIsFindingWebsites(true);
    try {
      const res = await igamingApi.findWebsites({ company_ids: ids, limit });
      toast(`Found ${res.found} websites out of ${res.total} companies`);
      loadCompanies();
    } catch (e: any) {
      toast(e?.userMessage || 'Website search failed');
    } finally {
      setIsFindingWebsites(false);
    }
  }, [selected, loadCompanies, toast]);

  const columnDefs = useMemo<ColDef[]>(() => [
    { headerCheckboxSelection: true, checkboxSelection: true, width: 40, pinned: 'left', suppressSizeToFit: true, resizable: false, sortable: false },
    { field: 'name', headerName: 'Company', width: 200, editable: true, sortable: true },
    { field: 'website', headerName: 'Website', width: 180, sortable: true, editable: true },
    {
      field: 'business_type', headerName: 'Type', width: 130, sortable: true, editable: true,
      cellEditor: 'agSelectCellEditor',
      cellEditorParams: {
        values: ['operator', 'affiliate', 'supplier', 'platform', 'payment', 'marketing', 'professional_services', 'media', 'regulator', 'other'],
      },
      cellRenderer: (p: any) => {
        const info = BUSINESS_TYPE_LABELS[p.value] || BUSINESS_TYPE_LABELS.other;
        return <span className={`${info.color} px-1.5 py-0.5 rounded text-[11px] font-medium`}>{info.label}</span>;
      },
    },
    { field: 'description', headerName: 'Description', width: 250, editable: true },
    { field: 'sector', headerName: 'Sector', width: 130, sortable: true, editable: true },
    { field: 'contacts_count', headerName: 'Contacts', width: 90, sortable: true },
    { field: 'employees_count', headerName: 'Employees', width: 90, sortable: true },
    {
      field: 'regions', headerName: 'Regions', width: 150,
      valueFormatter: (p: any) => (p.value || []).join(', '),
    },
    { field: 'headquarters', headerName: 'HQ', width: 120, editable: true },
    {
      field: 'name_aliases', headerName: 'Aliases', width: 150,
      valueFormatter: (p: any) => (p.value || []).join(', '),
    },
  ], []);

  return (
    <div className="h-full flex flex-col px-5 pb-3">
      <div className="flex items-center gap-2 py-2 flex-shrink-0">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: t.text5 }} />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search company..."
            className="w-full pl-8 pr-3 py-1.5 text-sm rounded-md border outline-none"
            style={{ background: t.inputBg, borderColor: t.inputBorder, color: t.text1 }} />
        </div>
        <select value={businessType} onChange={e => { setBusinessType(e.target.value); setPage(1); }}
          className="text-sm px-2 py-1.5 rounded-md border outline-none"
          style={{ background: t.inputBg, borderColor: t.inputBorder, color: t.text1 }}>
          <option value="">All Types</option>
          {businessTypes.map(bt => (
            <option key={bt.value} value={bt.value}>{BUSINESS_TYPE_LABELS[bt.value]?.label || bt.value} ({bt.count})</option>
          ))}
        </select>
        <select value={hasWebsite} onChange={e => { setHasWebsite(e.target.value); setPage(1); }}
          className="text-sm px-2 py-1.5 rounded-md border outline-none"
          style={{ background: t.inputBg, borderColor: t.inputBorder, color: t.text1 }}>
          <option value="">Website: Any</option>
          <option value="yes">Has Website</option>
          <option value="no">No Website</option>
        </select>

        <button onClick={() => setShowAIColumn(true)} className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md border hover:opacity-80"
          style={{ borderColor: t.cardBorder, color: t.text3 }}>
          <Sparkles size={12} /> AI Column
        </button>

        <button onClick={handleFindWebsites} disabled={isFindingWebsites}
          className="flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-md border hover:opacity-80"
          style={{ borderColor: t.cardBorder, color: t.text3 }}>
          {isFindingWebsites ? <><Loader2 size={12} className="animate-spin" /> Finding...</> : <><Globe size={12} /> Find Websites</>}
        </button>
      </div>

      {selected.length > 0 && (
        <div className="flex items-center gap-2 py-1.5 px-3 rounded-md mb-1 flex-shrink-0"
          style={{ background: isDark ? '#1e3a5f' : '#eff6ff', border: '1px solid', borderColor: isDark ? '#2563eb' : '#93c5fd' }}>
          <span className="text-xs font-medium" style={{ color: t.text1 }}>{selected.length} selected</span>
          <button onClick={() => setShowEmployeeSearch(true)} className="flex items-center gap-1 text-xs px-2 py-1 rounded border hover:opacity-80"
              style={{ borderColor: t.cardBorder, color: t.text2 }}>
              <UserSearch size={11} /> Find Employees
          </button>
          {selected.length === 2 && (
            <button onClick={handleMerge} className="flex items-center gap-1 text-xs px-2 py-1 rounded border hover:opacity-80"
              style={{ borderColor: t.cardBorder, color: t.text2 }}>
              <Merge size={11} /> Merge
            </button>
          )}
          <button onClick={() => { gridApi?.deselectAll(); setSelected([]); }}
            className="ml-auto text-xs px-2 py-1 rounded hover:opacity-80" style={{ color: t.text4 }}>
            <X size={12} />
          </button>
        </div>
      )}

      <div className={cn('flex-1 min-h-0', isDark ? 'ag-theme-alpine-dark' : 'ag-theme-alpine')}>
        <AgGridReact
          ref={gridRef} theme={AG_GRID_THEME}
          onGridReady={e => setGridApi(e.api)}
          columnDefs={columnDefs} rowData={companies}
          rowSelection="multiple" suppressRowClickSelection
          onSelectionChanged={() => gridApi && setSelected(gridApi.getSelectedRows())}
          onSortChanged={onSortChanged}
          onCellValueChanged={onCellValueChanged}
          loading={isLoading} animateRows={false}
          headerHeight={32} rowHeight={32}
          defaultColDef={{ resizable: true, filter: false, suppressMovable: true, singleClickEdit: true }}
        />
      </div>

      <div className="flex items-center justify-between pt-2 flex-shrink-0">
        <span className="text-xs" style={{ color: t.text4 }}>{total.toLocaleString()} companies — page {page}/{totalPages}</span>
        <div className="flex items-center gap-1">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
            className="p-1 rounded hover:opacity-70 disabled:opacity-30" style={{ color: t.text3 }}><ChevronLeft size={16} /></button>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
            className="p-1 rounded hover:opacity-70 disabled:opacity-30" style={{ color: t.text3 }}><ChevronRight size={16} /></button>
        </div>
      </div>

      {/* Employee Search Modal */}
      {showEmployeeSearch && (
        <EmployeeSearchModal
          isDark={isDark} t={t} toast={toast}
          companyIds={selected.map(c => c.id)}
          companyNames={selected.map(c => c.name)}
          onClose={() => setShowEmployeeSearch(false)}
          onDone={() => { setShowEmployeeSearch(false); loadCompanies(); }}
        />
      )}

      {/* AI Column Modal */}
      {showAIColumn && (
        <AIColumnModal
          isDark={isDark} t={t} toast={toast}
          target="company"
          onClose={() => setShowAIColumn(false)}
        />
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Employees Tab
// ══════════════════════════════════════════════════════════════════════

function EmployeesTab({ isDark, t, toast }: { isDark: boolean; t: any; toast: any }) {
  const gridRef = useRef<AgGridReact>(null);
  const [employees, setEmployees] = useState<IGamingEmployee[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  useEffect(() => {
    const t = setTimeout(() => { setDebouncedSearch(search); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const loadEmployees = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: Record<string, any> = { page, page_size: 100, sort_by: 'created_at', sort_order: 'desc' };
      if (debouncedSearch) params.search = debouncedSearch;
      const data = await igamingApi.listEmployees(params);
      setEmployees(data.employees || []);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch { toast('Failed to load employees'); }
    finally { setIsLoading(false); }
  }, [page, debouncedSearch, toast]);

  useEffect(() => { loadEmployees(); }, [loadEmployees]);

  const columnDefs = useMemo<ColDef[]>(() => [
    { field: 'full_name', headerName: 'Name', width: 180, sortable: true },
    { field: 'job_title', headerName: 'Title', width: 200, sortable: true },
    {
      field: 'email', headerName: 'Email', width: 220,
      cellRenderer: (p: any) => {
        if (!p.value) return null;
        return <a href={`mailto:${p.value}`} className="text-blue-500 underline text-xs">{p.value}</a>;
      },
    },
    {
      field: 'linkedin_url', headerName: 'LI', width: 40,
      cellRenderer: (p: any) => {
        if (!p.value) return null;
        return <a href={p.value} target="_blank" rel="noopener noreferrer" className="text-[#0077b5] font-bold">in</a>;
      },
    },
    { field: 'company_name', headerName: 'Company', width: 180, sortable: true },
    {
      field: 'company_website', headerName: 'Website', width: 150,
      cellRenderer: (p: any) => {
        if (!p.value) return null;
        return <a href={`https://${p.value}`} target="_blank" rel="noopener noreferrer" className="text-blue-500 text-xs">{p.value}</a>;
      },
    },
    { field: 'source', headerName: 'Source', width: 80, sortable: true },
    { field: 'phone', headerName: 'Phone', width: 120 },
  ], []);

  return (
    <div className="h-full flex flex-col px-5 pb-3">
      <div className="flex items-center gap-2 py-2 flex-shrink-0">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: t.text5 }} />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search employees..."
            className="w-full pl-8 pr-3 py-1.5 text-sm rounded-md border outline-none"
            style={{ background: t.inputBg, borderColor: t.inputBorder, color: t.text1 }} />
        </div>
      </div>

      <div className={cn('flex-1 min-h-0', isDark ? 'ag-theme-alpine-dark' : 'ag-theme-alpine')}>
        <AgGridReact ref={gridRef} theme={AG_GRID_THEME}
          columnDefs={columnDefs} rowData={employees}
          loading={isLoading} animateRows={false}
          headerHeight={32} rowHeight={32}
          defaultColDef={{ resizable: true, filter: false, suppressMovable: true }} />
      </div>

      <div className="flex items-center justify-between pt-2 flex-shrink-0">
        <span className="text-xs" style={{ color: t.text4 }}>{total.toLocaleString()} employees — page {page}/{totalPages}</span>
        <div className="flex items-center gap-1">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
            className="p-1 rounded hover:opacity-70 disabled:opacity-30" style={{ color: t.text3 }}><ChevronLeft size={16} /></button>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
            className="p-1 rounded hover:opacity-70 disabled:opacity-30" style={{ color: t.text3 }}><ChevronRight size={16} /></button>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Import Tab
// ══════════════════════════════════════════════════════════════════════

function ImportTab({ isDark: _isDark, t, toast, onImportDone }: { isDark: boolean; t: any; toast: any; onImportDone: () => void }) {
  void _isDark;
  const [step, setStep] = useState<'upload' | 'mapping' | 'importing' | 'done'>('upload');
  const [uploadResult, setUploadResult] = useState<ImportUploadResponse | null>(null);
  const [columnMapping, setColumnMapping] = useState<Record<string, string>>({});
  const [sourceConference, setSourceConference] = useState('');
  const [importResult, setImportResult] = useState<IGamingImport | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [imports, setImports] = useState<IGamingImport[]>([]);
  const [updateExisting, setUpdateExisting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load past imports
  useEffect(() => {
    igamingApi.listImports().then(setImports).catch(() => {});
  }, []);

  const handleUpload = useCallback(async (file: File) => {
    setIsUploading(true);
    try {
      const result = await igamingApi.uploadFile(file);
      setUploadResult(result);

      // Auto-map columns
      const mapping: Record<string, string> = {};
      for (const col of result.columns) {
        if (AUTO_MAP[col]) {
          mapping[col] = AUTO_MAP[col];
        }
      }
      setColumnMapping(mapping);
      setStep('mapping');
    } catch {
      toast('Upload failed');
    } finally {
      setIsUploading(false);
    }
  }, [toast]);

  const handleStartImport = useCallback(async () => {
    if (!uploadResult) return;
    // Filter out empty mappings
    const validMapping: Record<string, string> = {};
    for (const [csvCol, modelField] of Object.entries(columnMapping)) {
      if (modelField) validMapping[csvCol] = modelField;
    }

    setStep('importing');
    try {
      const result = await igamingApi.startImport({
        file_id: uploadResult.file_id,
        column_mapping: validMapping,
        source_conference: sourceConference || undefined,
        update_existing: updateExisting,
      });
      setImportResult(result);
      setStep('done');
      toast(`Imported ${result.rows_imported} contacts, ${result.companies_created} companies`);
    } catch {
      toast('Import failed');
      setStep('mapping');
    }
  }, [uploadResult, columnMapping, sourceConference, updateExisting, toast]);

  return (
    <div className="h-full overflow-auto px-5 py-4">
      <div className="max-w-3xl mx-auto">
        {/* Upload step */}
        {step === 'upload' && (
          <div>
            <div
              onClick={() => fileInputRef.current?.click()}
              onDragOver={e => e.preventDefault()}
              onDrop={e => {
                e.preventDefault();
                const file = e.dataTransfer.files[0];
                if (file) handleUpload(file);
              }}
              className="border-2 border-dashed rounded-xl p-12 text-center cursor-pointer hover:opacity-80 transition-opacity"
              style={{ borderColor: t.cardBorder, background: t.cardBg }}
            >
              <Upload size={36} className="mx-auto mb-3" style={{ color: t.text4 }} />
              <p className="text-sm font-medium" style={{ color: t.text2 }}>
                {isUploading ? 'Uploading...' : 'Drop CSV file here or click to browse'}
              </p>
              <p className="text-xs mt-1" style={{ color: t.text5 }}>
                Supports CSV files up to 100MB
              </p>
              <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden"
                onChange={e => { const file = e.target.files?.[0]; if (file) handleUpload(file); }} />
            </div>

            {/* Past imports */}
            {imports.length > 0 && (
              <div className="mt-6">
                <h3 className="text-sm font-medium mb-2" style={{ color: t.text2 }}>Recent Imports</h3>
                <div className="space-y-1">
                  {imports.map(imp => (
                    <div key={imp.id} className="flex items-center justify-between px-3 py-2 rounded-md border text-xs"
                      style={{ background: t.cardBg, borderColor: t.cardBorder }}>
                      <span style={{ color: t.text1 }}>{imp.filename}</span>
                      <div className="flex items-center gap-3" style={{ color: t.text4 }}>
                        {imp.source_conference && <span>{imp.source_conference}</span>}
                        <span>{imp.rows_imported} imported</span>
                        <span>{imp.companies_created} companies</span>
                        <span className={cn('px-1.5 py-0.5 rounded text-[10px]',
                          imp.status === 'completed' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                        )}>{imp.status}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Mapping step */}
        {step === 'mapping' && uploadResult && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-medium" style={{ color: t.text1 }}>
                  Column Mapping — {uploadResult.filename}
                </h3>
                <p className="text-xs mt-0.5" style={{ color: t.text4 }}>
                  {uploadResult.rows_preview.toLocaleString()} rows detected
                </p>
              </div>
              <div className="flex items-center gap-2">
                <input
                  value={sourceConference}
                  onChange={e => setSourceConference(e.target.value)}
                  placeholder="Conference name (e.g. SIGMA 2025)"
                  className="text-sm px-3 py-1.5 rounded-md border outline-none w-56"
                  style={{ background: t.inputBg, borderColor: t.inputBorder, color: t.text1 }}
                />
                <label className="flex items-center gap-1.5 text-xs cursor-pointer select-none" style={{ color: t.text3 }}>
                  <input
                    type="checkbox"
                    checked={updateExisting}
                    onChange={e => setUpdateExisting(e.target.checked)}
                    className="rounded border-gray-300"
                  />
                  Update existing
                </label>
                <button onClick={() => setStep('upload')} className="text-xs px-3 py-1.5 rounded-md border"
                  style={{ borderColor: t.cardBorder, color: t.text3 }}>Back</button>
                <button onClick={handleStartImport}
                  className="text-xs px-4 py-1.5 rounded-md font-medium"
                  style={{ background: t.btnPrimaryBg, color: t.btnPrimaryText }}>
                  Start Import
                </button>
              </div>
            </div>

            {/* Mapping table */}
            <div className="border rounded-lg overflow-hidden" style={{ borderColor: t.cardBorder }}>
              <table className="w-full text-xs">
                <thead>
                  <tr style={{ background: t.headerBg }}>
                    <th className="text-left px-3 py-2 font-medium" style={{ color: t.text3 }}>CSV Column</th>
                    <th className="text-left px-3 py-2 font-medium" style={{ color: t.text3 }}>Map to</th>
                    <th className="text-left px-3 py-2 font-medium" style={{ color: t.text3 }}>Sample</th>
                  </tr>
                </thead>
                <tbody>
                  {uploadResult.columns.map(col => (
                    <tr key={col} className="border-t" style={{ borderColor: t.divider }}>
                      <td className="px-3 py-1.5 font-mono" style={{ color: t.text1 }}>{col}</td>
                      <td className="px-3 py-1.5">
                        <select
                          value={columnMapping[col] || ''}
                          onChange={e => setColumnMapping(prev => ({ ...prev, [col]: e.target.value }))}
                          className="text-xs px-2 py-1 rounded border outline-none w-full"
                          style={{ background: t.inputBg, borderColor: t.inputBorder, color: t.text1 }}
                        >
                          {MODEL_FIELDS.map(f => (
                            <option key={f.value} value={f.value}>{f.label}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-1.5 truncate max-w-[200px]" style={{ color: t.text4 }}>
                        {uploadResult.preview[0]?.[col] || ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Preview rows */}
            {uploadResult.preview.length > 1 && (
              <div className="mt-4">
                <h4 className="text-xs font-medium mb-2" style={{ color: t.text3 }}>Preview (first {uploadResult.preview.length} rows)</h4>
                <div className="border rounded-lg overflow-x-auto" style={{ borderColor: t.cardBorder }}>
                  <table className="w-full text-[11px]">
                    <thead>
                      <tr style={{ background: t.headerBg }}>
                        {uploadResult.columns.map(c => (
                          <th key={c} className="text-left px-2 py-1.5 font-medium whitespace-nowrap" style={{ color: t.text4 }}>{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {uploadResult.preview.slice(0, 5).map((row, i) => (
                        <tr key={i} className="border-t" style={{ borderColor: t.divider }}>
                          {uploadResult!.columns.map(c => (
                            <td key={c} className="px-2 py-1 truncate max-w-[150px]" style={{ color: t.text2 }}>
                              {row[c] || ''}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Importing step */}
        {step === 'importing' && (
          <div className="text-center py-16">
            <RefreshCw size={32} className="mx-auto mb-3 animate-spin" style={{ color: t.text4 }} />
            <p className="text-sm" style={{ color: t.text2 }}>Importing contacts...</p>
            <p className="text-xs mt-1" style={{ color: t.text5 }}>This may take a few minutes for large files</p>
          </div>
        )}

        {/* Done step */}
        {step === 'done' && importResult && (
          <div className="text-center py-12">
            <div className="text-4xl mb-3">✓</div>
            <h3 className="text-base font-medium mb-4" style={{ color: t.text1 }}>Import Complete</h3>
            <div className="grid grid-cols-4 gap-3 max-w-md mx-auto mb-6">
              {[
                { label: 'Imported', value: importResult.rows_imported },
                { label: 'Updated', value: importResult.rows_updated },
                { label: 'Skipped', value: importResult.rows_skipped },
                { label: 'Companies', value: importResult.companies_created },
              ].map(({ label, value }) => (
                <div key={label} className="px-3 py-2 rounded-lg border" style={{ background: t.cardBg, borderColor: t.cardBorder }}>
                  <div className="text-lg font-semibold" style={{ color: t.text1 }}>{value.toLocaleString()}</div>
                  <div className="text-[11px]" style={{ color: t.text4 }}>{label}</div>
                </div>
              ))}
            </div>
            <div className="flex justify-center gap-2">
              <button onClick={() => { setStep('upload'); setUploadResult(null); setImportResult(null); }}
                className="text-xs px-4 py-1.5 rounded-md border" style={{ borderColor: t.cardBorder, color: t.text3 }}>
                Import Another
              </button>
              <button onClick={onImportDone}
                className="text-xs px-4 py-1.5 rounded-md font-medium"
                style={{ background: t.btnPrimaryBg, color: t.btnPrimaryText }}>
                View Contacts
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Employee Search Modal
// ══════════════════════════════════════════════════════════════════════

function EmployeeSearchModal({
  isDark: _isDark, t, toast, companyIds, companyNames, onClose, onDone,
}: {
  isDark: boolean; t: any; toast: any;
  companyIds: number[]; companyNames: string[];
  onClose: () => void; onDone: () => void;
}) {
  const [titles, setTitles] = useState('CEO, CTO, Head of Payments, VP Business Development');
  const [limit] = useState(5);
  const [clayWebhook, setClayWebhook] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [result, setResult] = useState<any>(null);

  const handleSearch = useCallback(async () => {
    if (!clayWebhook.trim()) { toast('Enter your Clay table webhook URL'); return; }
    setIsSearching(true);
    try {
      const titleList = titles.split(',').map(t => t.trim()).filter(Boolean);
      const res = await igamingApi.searchEmployees({
        company_ids: companyIds,
        titles: titleList,
        limit_per_company: limit,
        source: 'clay',
        clay_webhook_url: clayWebhook.trim(),
      });
      setResult(res);
      toast(`Pushed ${res.pushed} domains to Clay`);
    } catch (e: any) {
      toast(e?.userMessage || 'Employee search failed');
    } finally {
      setIsSearching(false);
    }
  }, [companyIds, titles, limit, clayWebhook, toast]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="rounded-xl border shadow-lg w-full max-w-lg p-5" onClick={e => e.stopPropagation()}
        style={{ background: t.cardBg, borderColor: t.cardBorder }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold flex items-center gap-2" style={{ color: t.text1 }}>
            <UserSearch size={16} /> Find Employees
          </h3>
          <button onClick={onClose} className="p-1 rounded hover:opacity-70" style={{ color: t.text4 }}><X size={16} /></button>
        </div>

        <div className="text-xs mb-3" style={{ color: t.text4 }}>
          Searching in {companyIds.length} companies: {companyNames.slice(0, 3).join(', ')}
          {companyNames.length > 3 && ` +${companyNames.length - 3} more`}
        </div>

        {!result ? (
          <>
            <label className="block text-xs font-medium mb-1" style={{ color: t.text2 }}>Job Titles (comma-separated)</label>
            <textarea value={titles} onChange={e => setTitles(e.target.value)} rows={3}
              className="w-full text-sm px-3 py-2 rounded-md border outline-none mb-3"
              style={{ background: t.inputBg, borderColor: t.inputBorder, color: t.text1 }}
              placeholder="CEO, CTO, Head of Payments, VP Business Development" />

            <label className="block text-xs font-medium mb-1" style={{ color: t.text2 }}>Clay Table Webhook URL</label>
            <input value={clayWebhook} onChange={e => setClayWebhook(e.target.value)}
              placeholder="https://api.clay.com/v1/tables/.../webhooks/..."
              className="w-full text-sm px-3 py-2 rounded-md border outline-none mb-3"
              style={{ background: t.inputBg, borderColor: t.inputBorder, color: t.text1 }} />
            <p className="text-[10px] mb-3" style={{ color: t.text5 }}>
              Create a Clay table with People Enrichment, copy the webhook URL from Settings → Webhooks
            </p>

            <div className="flex justify-end gap-2">
              <button onClick={onClose} className="text-xs px-3 py-1.5 rounded-md border" style={{ borderColor: t.cardBorder, color: t.text3 }}>Cancel</button>
              <button onClick={handleSearch} disabled={isSearching}
                className="text-xs px-4 py-1.5 rounded-md font-medium flex items-center gap-1.5"
                style={{ background: t.btnPrimaryBg, color: t.btnPrimaryText }}>
                {isSearching ? <><Loader2 size={12} className="animate-spin" /> Searching...</> : <><Play size={12} /> Search</>}
              </button>
            </div>
          </>
        ) : (
          <div>
            <div className="grid grid-cols-3 gap-3 mb-4">
              {[
                { label: 'Domains Pushed', value: result.pushed ?? result.processed ?? 0 },
                { label: 'Total', value: result.total ?? 0 },
                { label: 'Errors', value: result.errors ?? 0 },
              ].map(({ label, value }) => (
                <div key={label} className="px-3 py-2 rounded-lg border text-center" style={{ background: t.pageBg, borderColor: t.cardBorder }}>
                  <div className="text-lg font-semibold" style={{ color: t.text1 }}>{value}</div>
                  <div className="text-[10px]" style={{ color: t.text4 }}>{label}</div>
                </div>
              ))}
            </div>
            <div className="flex justify-end">
              <button onClick={onDone} className="text-xs px-4 py-1.5 rounded-md font-medium"
                style={{ background: t.btnPrimaryBg, color: t.btnPrimaryText }}>Done</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// AI Column Modal
// ══════════════════════════════════════════════════════════════════════

const AI_MODELS = [
  { value: 'gemini-2.5-flash', label: 'Gemini 2.5 Flash (fast, cheap)' },
  { value: 'gemini-2.5-pro', label: 'Gemini 2.5 Pro' },
  { value: 'gpt-4o-mini', label: 'GPT-4o Mini (cheap)' },
  { value: 'gpt-4o', label: 'GPT-4o' },
];

function AIColumnModal({
  isDark: _isDark, t, toast, target, onClose,
}: {
  isDark: boolean; t: any; toast: any;
  target: string; onClose: () => void;
}) {
  void _isDark;
  const [name, setName] = useState('');
  const [promptTemplate, setPromptTemplate] = useState('');
  const [model, setModel] = useState('gemini-2.5-flash');
  const [columns, setColumns] = useState<AIColumn[]>([]);
  const [isCreating, setIsCreating] = useState(false);
  const [runningId, setRunningId] = useState<number | null>(null);

  useEffect(() => {
    igamingApi.listAIColumns().then(setColumns).catch(() => {});
  }, []);

  const handleCreate = useCallback(async () => {
    if (!name.trim() || !promptTemplate.trim()) { toast('Name and prompt are required'); return; }
    setIsCreating(true);
    try {
      const col = await igamingApi.createAIColumn({
        name: name.trim(), target, prompt_template: promptTemplate.trim(), model,
      });
      setColumns(prev => [col, ...prev]);
      setName(''); setPromptTemplate('');
      toast(`AI column "${col.name}" created`);
    } catch { toast('Failed to create'); }
    finally { setIsCreating(false); }
  }, [name, promptTemplate, model, target, toast]);

  const handleRun = useCallback(async (colId: number) => {
    setRunningId(colId);
    try {
      const res = await igamingApi.runAIColumn(colId);
      toast(`Processed ${res.processed}/${res.total} rows, ${res.errors} errors`);
      igamingApi.listAIColumns().then(setColumns).catch(() => {});
    } catch (e: any) { toast(e?.userMessage || 'Run failed'); }
    finally { setRunningId(null); }
  }, [toast]);

  const handleDelete = useCallback(async (colId: number) => {
    if (!confirm('Delete this AI column?')) return;
    try {
      await igamingApi.deleteAIColumn(colId);
      setColumns(prev => prev.filter(c => c.id !== colId));
    } catch { toast('Failed to delete'); }
  }, [toast]);

  const placeholders = target === 'company'
    ? '{name}, {website}, {business_type}, {description}, {sector}, {regions}'
    : '{first_name}, {last_name}, {organization_name}, {website_url}, {job_title}, {bio}, {sector}';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="rounded-xl border shadow-lg w-full max-w-2xl p-5 max-h-[80vh] overflow-auto" onClick={e => e.stopPropagation()}
        style={{ background: t.cardBg, borderColor: t.cardBorder }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold flex items-center gap-2" style={{ color: t.text1 }}>
            <Sparkles size={16} /> AI Enrichment Columns
          </h3>
          <button onClick={onClose} className="p-1 rounded hover:opacity-70" style={{ color: t.text4 }}><X size={16} /></button>
        </div>

        {/* Create new */}
        <div className="border rounded-lg p-3 mb-4" style={{ borderColor: t.cardBorder }}>
          <div className="flex items-center gap-2 mb-2">
            <input value={name} onChange={e => setName(e.target.value)} placeholder="Column name"
              className="flex-1 text-sm px-3 py-1.5 rounded-md border outline-none"
              style={{ background: t.inputBg, borderColor: t.inputBorder, color: t.text1 }} />
            <select value={model} onChange={e => setModel(e.target.value)}
              className="text-xs px-2 py-1.5 rounded-md border outline-none"
              style={{ background: t.inputBg, borderColor: t.inputBorder, color: t.text1 }}>
              {AI_MODELS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
          <textarea value={promptTemplate} onChange={e => setPromptTemplate(e.target.value)} rows={3}
            placeholder={`Prompt template. Use placeholders: ${placeholders}`}
            className="w-full text-sm px-3 py-2 rounded-md border outline-none mb-2"
            style={{ background: t.inputBg, borderColor: t.inputBorder, color: t.text1 }} />
          <div className="flex items-center justify-between">
            <span className="text-[10px]" style={{ color: t.text5 }}>Placeholders: {placeholders}</span>
            <button onClick={handleCreate} disabled={isCreating}
              className="text-xs px-3 py-1.5 rounded-md font-medium flex items-center gap-1"
              style={{ background: t.btnPrimaryBg, color: t.btnPrimaryText }}>
              <Plus size={12} /> Create
            </button>
          </div>
        </div>

        {/* Existing columns */}
        {columns.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-medium" style={{ color: t.text3 }}>Existing Columns</h4>
            {columns.map(col => (
              <div key={col.id} className="flex items-center justify-between px-3 py-2 rounded-md border"
                style={{ borderColor: t.cardBorder, background: t.pageBg }}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium" style={{ color: t.text1 }}>{col.name}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: t.badgeBg, color: t.badgeText }}>{col.model}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: t.badgeBg, color: t.badgeText }}>{col.target}</span>
                    {col.status !== 'idle' && (
                      <span className={cn('text-[10px] px-1.5 py-0.5 rounded',
                        col.status === 'completed' ? 'bg-green-100 text-green-700' :
                        col.status === 'running' ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'
                      )}>{col.status} ({col.rows_processed}/{col.rows_total})</span>
                    )}
                  </div>
                  <div className="text-[10px] mt-0.5 truncate" style={{ color: t.text5 }}>{col.prompt_template}</div>
                </div>
                <div className="flex items-center gap-1 ml-2">
                  <button onClick={() => handleRun(col.id)} disabled={runningId === col.id}
                    className="p-1 rounded hover:opacity-70" style={{ color: t.text3 }}>
                    {runningId === col.id ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
                  </button>
                  <button onClick={() => handleDelete(col.id)}
                    className="p-1 rounded hover:opacity-70 text-red-400"><Trash2 size={14} /></button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
