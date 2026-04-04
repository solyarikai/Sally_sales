import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import {
  Users, Send, Shield, Plus, Search, Trash2,
  Globe, Loader2, Play, Pause, Filter, ArrowUpDown, ArrowUp, ArrowDown,
  X, Upload, Edit3, ChevronDown, BookOpen, Check, Minus, Download, RefreshCw,
  MessageCircle, Info, FileText, MoreVertical, AlertTriangle, Tag, EyeOff, ShieldAlert, Link2, Square,
  LayoutGrid, Bot, Phone, Settings, PanelLeft, Paperclip, Image, File as FileIcon,
  BarChart3, ChevronUp, ChevronRight, FolderOpen,
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { cn } from '../lib/utils';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { useToast } from '../components/Toast';
import { telegramOutreachApi } from '../api/telegramOutreach';
import { useAppStore } from '../store/appStore';
import { contactsApi } from '../api/contacts';
import type {
  TgAccount, TgAccountTag, TgProxyGroup, TgProxy, TgCampaign,
} from '../api/telegramOutreach';

type Tab = 'accounts' | 'campaigns' | 'proxies' | 'parser' | 'crm' | 'pipeline' | 'custom_fields' | 'blacklist' | 'inbox' | 'info';

const TAB_ROUTES: Record<Tab, string> = {
  inbox: '/outreach/inbox',
  campaigns: '/outreach/campaigns',
  accounts: '/outreach/accounts',
  crm: '/outreach/crm/leads',
  pipeline: '/outreach/crm/pipeline',
  custom_fields: '/outreach/crm/custom-fields',
  parser: '/outreach/tools/parser',
  proxies: '/outreach/tools/proxies',
  blacklist: '/outreach/tools/blacklist',
  info: '/outreach/settings',
};

function pathToTab(pathname: string): Tab {
  if (pathname.startsWith('/outreach/crm/leads')) return 'crm';
  if (pathname.startsWith('/outreach/crm/custom-fields')) return 'custom_fields';
  if (pathname.startsWith('/outreach/crm/pipeline')) return 'pipeline';
  if (pathname.startsWith('/outreach/tools/parser')) return 'parser';
  if (pathname.startsWith('/outreach/tools/proxies')) return 'proxies';
  if (pathname.startsWith('/outreach/tools/blacklist')) return 'blacklist';
  if (pathname.startsWith('/outreach/inbox')) return 'inbox';
  if (pathname.startsWith('/outreach/campaigns')) return 'campaigns';
  if (pathname.startsWith('/outreach/accounts')) return 'accounts';
  if (pathname.startsWith('/outreach/settings')) return 'info';
  return 'campaigns';
}

// ── Helpers ───────────────────────────────────────────────────────────

/** Country flag as small image (emoji flags don't render on Windows). Uses flagcdn.com SVGs. */
function CountryFlag({ code }: { code: string }) {
  const lower = code.toLowerCase();
  return (
    <img
      src={`https://flagcdn.com/w40/${lower}.png`}
      srcSet={`https://flagcdn.com/w80/${lower}.png 2x`}
      alt={code}
      title={code}
      className="inline-block"
      style={{ width: 20, height: 14, objectFit: 'cover', borderRadius: 2 }}
      onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; (e.currentTarget.nextSibling as HTMLElement)?.style.removeProperty('display'); }}
    />
  );
}

// ── Design tokens ─────────────────────────────────────────────────────

const A = {
  blue: '#4F6BF0', blueHover: '#4360D9', blueBg: '#EEF1FE',
  teal: '#0D9488', tealBg: '#ECFDF5',
  rose: '#E05D6F', roseBg: '#FFF1F2',
  bg: '#FAFAF8', surface: '#FFFFFF', border: '#E8E6E3',
  text1: '#1A1A1A', text2: '#6B6B6B', text3: '#9CA3AF',
};

// ── Custom Checkbox ──────────────────────────────────────────────────

function Tick({ checked, indeterminate, onChange, className }: {
  checked: boolean; indeterminate?: boolean; onChange: () => void; className?: string;
}) {
  return (
    <button onClick={e => { e.stopPropagation(); onChange(); }}
      className={cn('w-[18px] h-[18px] rounded-[4px] border flex items-center justify-center transition-all',
        checked || indeterminate
          ? `bg-[${A.blue}] border-[${A.blue}]`
          : 'bg-white border-[#D1D5DB] hover:border-[#9CA3AF]',
        className
      )}
      style={checked || indeterminate ? { background: A.blue, borderColor: A.blue } : undefined}
    >
      {checked && <Check className="w-3 h-3 text-white" strokeWidth={3} />}
      {indeterminate && !checked && <Minus className="w-3 h-3 text-white" strokeWidth={3} />}
    </button>
  );
}

// ── Sortable Header ──────────────────────────────────────────────────

// ── Custom styled select (replaces native <select>) ─────────────────
function StyledSelect({ value, onChange, options, placeholder, className: cls, renderOption, renderSelected }: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  placeholder?: string;
  className?: string;
  renderOption?: (opt: { value: string; label: string }, isSelected: boolean) => React.ReactNode;
  renderSelected?: (opt: { value: string; label: string }) => React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [openUp, setOpenUp] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [open]);
  const selected = options.find(o => o.value === value);
  const handleOpen = () => {
    if (!open && ref.current) {
      const rect = ref.current.getBoundingClientRect();
      setOpenUp(rect.bottom + 248 > window.innerHeight);
    }
    setOpen(!open);
  };
  return (
    <div ref={ref} style={{ position: 'relative' }} className={cls}>
      <button onClick={handleOpen} type="button"
        className="w-full h-8 flex items-center justify-between gap-1 px-2.5 rounded-lg text-xs truncate outline-none"
        style={{ border: `1px solid ${A.border}`, background: A.surface, color: selected ? A.text1 : A.text3, cursor: 'pointer' }}>
        <span className="truncate">{selected ? (renderSelected ? renderSelected(selected) : selected.label) : (placeholder || 'Select...')}</span>
        <ChevronDown className="w-3 h-3 flex-shrink-0" style={{ color: A.text3 }} />
      </button>
      {open && (
        <div style={{ position: 'absolute', ...(openUp ? { bottom: '100%', marginBottom: 4 } : { top: '100%', marginTop: 4 }), left: 0, right: 0, borderRadius: 10, border: `1px solid ${A.border}`, background: A.surface, boxShadow: '0 4px 12px rgba(0,0,0,0.08)', zIndex: 50, padding: '4px 0', maxHeight: 240, overflowY: 'auto' }}>
          {placeholder && (
            <button onClick={() => { onChange(''); setOpen(false); }}
              className="w-full text-left px-3 py-1.5 text-xs"
              style={{ color: A.text3, background: value === '' ? A.blueBg : 'transparent', border: 'none', cursor: 'pointer' }}
              onMouseEnter={e => { if (value !== '') e.currentTarget.style.background = '#F5F5F0'; }}
              onMouseLeave={e => { if (value !== '') e.currentTarget.style.background = ''; }}>
              {placeholder}
            </button>
          )}
          {options.map(o => (
            <button key={o.value} onClick={() => { onChange(o.value); setOpen(false); }}
              className={`w-full text-left px-3 ${renderOption ? 'py-2' : 'py-1.5'} text-xs`}
              style={{ color: value === o.value ? A.blue : A.text1, background: value === o.value ? A.blueBg : 'transparent', border: 'none', cursor: 'pointer' }}
              onMouseEnter={e => { if (value !== o.value) e.currentTarget.style.background = '#F5F5F0'; }}
              onMouseLeave={e => { if (value !== o.value) e.currentTarget.style.background = ''; }}>
              {renderOption ? renderOption(o, value === o.value) : o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SortHead({ label, column, current, dir, onSort, className }: {
  label: string; column: string; current: string | null; dir: 'asc' | 'desc';
  onSort: (col: string) => void; className?: string;
}) {
  const active = current === column;
  return (
    <th className={cn('text-left px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wider cursor-pointer select-none group', className)}
        style={{ color: active ? A.text1 : A.text3 }}
        onClick={() => onSort(column)}>
      <span className="inline-flex items-center gap-1">
        {label}
        {active
          ? (dir === 'asc' ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />)
          : <ArrowUpDown className="w-3 h-3 opacity-0 group-hover:opacity-40 transition-opacity" />}
      </span>
    </th>
  );
}

// ── Status badges ─────────────────────────────────────────────────────

const ACCOUNT_STATUS_STYLES: Record<string, { bg: string; color: string }> = {
  active: { bg: A.tealBg, color: A.teal },
  paused: { bg: '#FFFBEB', color: '#D97706' },
  spamblocked: { bg: A.roseBg, color: A.rose },
  banned: { bg: '#450A0A', color: '#FCA5A5' },
  dead: { bg: '#F3F4F6', color: '#6B7280' },
  frozen: { bg: '#EFF6FF', color: '#2563EB' },
};

// Campaign status colors now handled inline in CampaignsTab

function StatusBadge({ status }: { status: string }) {
  const s = ACCOUNT_STATUS_STYLES[status];
  return (
    <span className="px-2 py-0.5 rounded-full text-xs font-medium" style={{
      background: s?.bg || '#F3F4F6',
      color: s?.color || '#6B7280',
    }}>
      {status}
    </span>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Main Page
// ══════════════════════════════════════════════════════════════════════

export function TelegramOutreachPage() {
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const toastCtx = useToast();
  const toast = useCallback((msg: string, type: 'success' | 'error' | 'info' = 'info') => {
    toastCtx[type](msg);
  }, [toastCtx]);

  const navigate = useNavigate();
  const location = useLocation();
  const tab: Tab = pathToTab(location.pathname);
  const setTab = useCallback((t: Tab) => navigate(TAB_ROUTES[t]), [navigate]);
  const [workerRunning, setWorkerRunning] = useState(false);

  // Poll worker status
  useEffect(() => {
    const check = async () => {
      try {
        const { running } = await telegramOutreachApi.getWorkerStatus();
        setWorkerRunning(running);
      } catch { /* server may not be reachable */ }
    };
    check();
    const interval = setInterval(check, 10000);
    return () => clearInterval(interval);
  }, []);

  // ── Project selector ───────────────────────────────────────────────
  const { projects, currentProject, setCurrentProject, setProjects } = useAppStore();
  const [showProjectDropdown, setShowProjectDropdown] = useState(false);
  const [projectSearch, setProjectSearch] = useState('');
  const projectDropdownRef = useRef<HTMLDivElement>(null);

  // Load projects if not already loaded
  useEffect(() => {
    if (projects.length === 0) {
      contactsApi.listProjectsLite().then(ps => setProjects(ps as any)).catch(() => {});
    }
  }, [projects.length, setProjects]);

  // Close project dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (projectDropdownRef.current && !projectDropdownRef.current.contains(e.target as Node)) {
        setShowProjectDropdown(false);
        setProjectSearch('');
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // ── Sidebar state ──────────────────────────────────────────────────
  const [collapsed, setCollapsed] = useState(false);
  const [openSections, setOpenSections] = useState<Record<string, boolean>>({
    leads: true, outreach: true, tools: true,
  });
  const toggleSection = (key: string) =>
    setOpenSections(prev => ({ ...prev, [key]: !prev[key] }));

  type SItem = { key: Tab | null; label: string; icon: typeof Users; disabled?: boolean };
  const sections: { key: string; label: string; icon: typeof Users; items: SItem[] }[] = [
    {
      key: 'leads', label: 'Leads', icon: Users,
      items: [
        { key: 'crm', label: 'All Leads', icon: Users },
        { key: 'pipeline', label: 'Pipeline', icon: LayoutGrid },
        { key: 'custom_fields', label: 'Custom Properties', icon: Settings },
      ],
    },
    {
      key: 'outreach', label: 'Outreach', icon: Send,
      items: [
        { key: 'inbox', label: 'Inbox', icon: MessageCircle },
        { key: 'campaigns', label: 'Campaigns', icon: Send },
        { key: 'accounts', label: 'Accounts', icon: Users },
        { key: null, label: 'AI Bot', icon: Bot, disabled: true },
      ],
    },
    {
      key: 'tools', label: 'Tools', icon: Search,
      items: [
        { key: 'parser', label: 'Group Parser', icon: Search },
        { key: 'proxies', label: 'Proxies', icon: Shield },
        { key: 'blacklist', label: 'Blacklist', icon: ShieldAlert },
        { key: null, label: 'Phone Converter', icon: Phone, disabled: true },
      ],
    },
  ];

  return (
    <div className="flex h-full" style={{ background: A.bg }}>
      {/* ── Sidebar ─────────────────────────────────────────────────── */}
      <aside
        className="flex flex-col h-full shrink-0 transition-[width] duration-200 select-none"
        style={{ width: collapsed ? 56 : 220, background: A.surface, borderRight: `1px solid ${A.border}` }}
      >
        {/* Header */}
        <div className="flex items-center h-12 px-3 gap-2" style={{ borderBottom: `1px solid ${A.border}` }}>
          {!collapsed && (
            <span className="text-sm font-semibold truncate flex-1" style={{ color: A.text1 }}>TG Outreach</span>
          )}
          <button
            onClick={() => setCollapsed(c => !c)}
            className="p-1.5 rounded-md transition-colors shrink-0"
            style={{ color: A.text3 }}
            onMouseEnter={e => (e.currentTarget.style.background = '#F3F3F1')}
            onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            <PanelLeft className="w-4 h-4" style={collapsed ? { transform: 'scaleX(-1)' } : undefined} />
          </button>
        </div>

        {/* Project Selector */}
        {!collapsed && projects.length > 0 && (
          <div className="relative px-2 pt-2" ref={projectDropdownRef}>
            <button
              onClick={() => { setShowProjectDropdown(!showProjectDropdown); setProjectSearch(''); }}
              className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-[13px] transition-colors"
              style={{
                background: currentProject ? A.blueBg : '#F3F3F1',
                color: currentProject ? A.blue : A.text2,
                border: `1px solid ${currentProject ? A.blue + '30' : A.border}`,
              }}
              onMouseEnter={e => { if (!currentProject) e.currentTarget.style.background = '#EDEDEB'; }}
              onMouseLeave={e => { if (!currentProject) e.currentTarget.style.background = '#F3F3F1'; }}
            >
              <FolderOpen className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate flex-1 text-left">
                {currentProject ? currentProject.name : 'All Projects'}
              </span>
              <ChevronDown className="w-3 h-3 shrink-0" style={{
                transform: showProjectDropdown ? 'rotate(180deg)' : undefined,
                transition: 'transform 150ms',
              }} />
            </button>

            {showProjectDropdown && (
              <div className="absolute left-2 right-2 top-full mt-1 rounded-md shadow-xl z-50 py-0.5"
                style={{ background: A.surface, border: `1px solid ${A.border}` }}>
                <div className="px-1.5 py-1.5">
                  <input
                    type="text"
                    value={projectSearch}
                    onChange={e => setProjectSearch(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Escape') { setShowProjectDropdown(false); setProjectSearch(''); }
                    }}
                    placeholder="Search..."
                    autoFocus
                    className="w-full px-2 py-1 text-[12px] rounded border-none focus:outline-none"
                    style={{ background: '#F3F3F1', color: A.text1 }}
                  />
                </div>
                <div className="max-h-48 overflow-y-auto py-0.5">
                  <button
                    onClick={() => { setCurrentProject(null); setShowProjectDropdown(false); setProjectSearch(''); }}
                    className="w-full px-3 py-1.5 text-left text-[13px] transition-colors"
                    style={{
                      color: !currentProject ? A.blue : A.text2,
                      background: !currentProject ? A.blueBg : 'transparent',
                      fontWeight: !currentProject ? 600 : 400,
                    }}
                    onMouseEnter={e => { if (currentProject) e.currentTarget.style.background = '#F3F3F1'; }}
                    onMouseLeave={e => { if (currentProject) e.currentTarget.style.background = 'transparent'; }}
                  >
                    All Projects
                  </button>
                  {projects
                    .filter(p => !projectSearch || p.name.toLowerCase().includes(projectSearch.toLowerCase()))
                    .map(p => (
                      <button
                        key={p.id}
                        onClick={() => { setCurrentProject(p); setShowProjectDropdown(false); setProjectSearch(''); }}
                        className="w-full px-3 py-1.5 text-left text-[13px] truncate transition-colors"
                        style={{
                          color: currentProject?.id === p.id ? A.blue : A.text2,
                          background: currentProject?.id === p.id ? A.blueBg : 'transparent',
                          fontWeight: currentProject?.id === p.id ? 600 : 400,
                        }}
                        onMouseEnter={e => { if (currentProject?.id !== p.id) e.currentTarget.style.background = '#F3F3F1'; }}
                        onMouseLeave={e => { if (currentProject?.id !== p.id) e.currentTarget.style.background = 'transparent'; }}
                      >
                        {p.name}
                      </button>
                    ))
                  }
                </div>
              </div>
            )}
          </div>
        )}
        {collapsed && projects.length > 0 && (
          <div className="px-2 pt-2">
            <button
              onClick={() => { setCollapsed(false); setTimeout(() => setShowProjectDropdown(true), 200); }}
              className="w-full flex items-center justify-center py-2 rounded-md transition-colors"
              style={{ color: currentProject ? A.blue : A.text3 }}
              onMouseEnter={e => (e.currentTarget.style.background = '#F3F3F1')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              title={currentProject ? currentProject.name : 'All Projects'}
            >
              <FolderOpen className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Sections */}
        <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-1">
          {sections.map((sec, si) => (
            <div key={sec.key}>
              {collapsed && si > 0 && <div className="my-2 mx-1" style={{ borderTop: `1px solid ${A.border}` }} />}

              {!collapsed && (
                <button
                  onClick={() => toggleSection(sec.key)}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md text-[11px] font-semibold uppercase tracking-wider"
                  style={{ color: A.text3 }}
                >
                  <ChevronDown
                    className="w-3 h-3 transition-transform duration-150"
                    style={{ transform: openSections[sec.key] ? undefined : 'rotate(-90deg)' }}
                  />
                  <span>{sec.label}</span>
                </button>
              )}

              {(collapsed || openSections[sec.key]) && sec.items.map(item => {
                const active = tab === item.key;
                return (
                  <button
                    key={item.label}
                    onClick={() => item.key && !item.disabled && setTab(item.key)}
                    disabled={item.disabled || !item.key}
                    className={cn(
                      'w-full flex items-center gap-2.5 rounded-md text-[13px] transition-colors',
                      collapsed ? 'justify-center px-0 py-2' : 'px-3 py-1.5',
                    )}
                    style={{
                      color: item.disabled ? A.text3 : active ? A.blue : A.text2,
                      background: active ? A.blueBg : 'transparent',
                      cursor: item.disabled ? 'default' : 'pointer',
                      opacity: item.disabled ? 0.5 : 1,
                    }}
                    onMouseEnter={e => { if (!item.disabled && !active) e.currentTarget.style.background = '#F3F3F1'; }}
                    onMouseLeave={e => { if (!item.disabled && !active) e.currentTarget.style.background = 'transparent'; }}
                    title={collapsed ? item.label : item.disabled ? 'Coming soon' : undefined}
                  >
                    <item.icon className="w-4 h-4 shrink-0" />
                    {!collapsed && <span className="truncate">{item.label}</span>}
                    {!collapsed && item.disabled && (
                      <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full"
                        style={{ background: '#F3F4F6', color: A.text3 }}>Soon</span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Bottom: Settings + Worker */}
        <div className="px-2 py-2" style={{ borderTop: `1px solid ${A.border}` }}>
          <button
            onClick={() => setTab('info')}
            className={cn(
              'w-full flex items-center gap-2.5 rounded-md text-[13px] transition-colors',
              collapsed ? 'justify-center px-0 py-2' : 'px-3 py-1.5',
            )}
            style={{
              color: tab === 'info' ? A.blue : A.text2,
              background: tab === 'info' ? A.blueBg : 'transparent',
            }}
            onMouseEnter={e => { if (tab !== 'info') e.currentTarget.style.background = '#F3F3F1'; }}
            onMouseLeave={e => { if (tab !== 'info') e.currentTarget.style.background = 'transparent'; }}
            title={collapsed ? 'Settings' : undefined}
          >
            <Settings className="w-4 h-4 shrink-0" />
            {!collapsed && <span>Settings</span>}
          </button>

          <div className="flex items-center gap-2 px-3 py-1.5 mt-1"
            title={workerRunning ? 'Worker Active' : 'Worker Offline'}>
            <span className={cn('w-2 h-2 rounded-full shrink-0',
              workerRunning ? 'bg-green-500 animate-pulse' : 'bg-red-500')} />
            {!collapsed && (
              <span className={cn('text-[11px] font-medium',
                workerRunning ? 'text-green-600' : 'text-red-500')}>
                {workerRunning ? 'Worker Active' : 'Worker Offline'}
              </span>
            )}
          </div>
        </div>
      </aside>

      {/* ── Main content ────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-auto p-6">
          {tab === 'accounts' && <AccountsTab t={t} toast={toast} />}
          {tab === 'campaigns' && <CampaignsTab t={t} toast={toast} />}
          {tab === 'proxies' && <ProxiesTab t={t} toast={toast} />}
          {tab === 'parser' && <ParserTab t={t} toast={toast} />}
          {tab === 'crm' && <CrmTab t={t} toast={toast} />}
          {tab === 'pipeline' && <PipelineTab toast={toast} />}
          {tab === 'blacklist' && <BlacklistTab toast={toast} />}
          {tab === 'inbox' && <InboxTab toast={toast} />}
          {tab === 'custom_fields' && <CustomFieldsTab toast={toast} />}
          {tab === 'info' && <InfoTab t={t} toast={toast} />}
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Accounts Tab
// ══════════════════════════════════════════════════════════════════════

function AccountsTab({ t, toast }: { t: any; toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) {
  const { isDark } = useTheme();
  const currentProject = useAppStore(s => s.currentProject);
  const [accounts, setAccounts] = useState<TgAccount[]>([]);
  const [_tags, setTags] = useState<TgAccountTag[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [showFilters, setShowFilters] = useState(false);
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const addMenuRef = useRef<HTMLDivElement>(null);

  // Modal states
  const [showAddModal, setShowAddModal] = useState(false);
  const [showAddByPhoneModal, setShowAddByPhoneModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [editingAccount, setEditingAccount] = useState<TgAccount | null>(null);

  // Overview analytics
  const [overviewData, setOverviewData] = useState<any>(null);
  const [overviewRange, setOverviewRange] = useState<'7d' | '30d'>('7d');
  const [showOverview, setShowOverview] = useState(true);

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { page, page_size: 50 };
      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      if (currentProject?.id) params.project_id = currentProject.id;
      const data = await telegramOutreachApi.listAccounts(params);
      setAccounts(data.items);
      setTotal(data.total);
    } catch {
      toast('Failed to load accounts', 'error');
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, currentProject?.id, toast]);

  const loadTags = useCallback(async () => {
    try { setTags(await telegramOutreachApi.listTags()); } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadAccounts(); }, [loadAccounts]);
  useEffect(() => { loadTags(); }, [loadTags]);
  useEffect(() => {
    telegramOutreachApi.getAccountsAnalyticsOverview()
      .then(d => setOverviewData(d))
      .catch(() => setOverviewData(null));
  }, []);

  // Close add menu on click outside
  useEffect(() => {
    const h = (e: MouseEvent) => { if (addMenuRef.current && !addMenuRef.current.contains(e.target as Node)) setShowAddMenu(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  };
  const toggleAll = () => {
    setSelectedIds(selectedIds.size === accounts.length ? new Set() : new Set(accounts.map(a => a.id)));
  };

  const handleSort = (col: string) => {
    if (sortCol === col) {
      if (sortDir === 'asc') setSortDir('desc');
      else { setSortCol(null); setSortDir('asc'); }
    } else { setSortCol(col); setSortDir('asc'); }
  };

  const sorted = [...accounts].sort((a, b) => {
    if (!sortCol) return 0;
    const m = sortDir === 'asc' ? 1 : -1;
    const get = (acc: TgAccount) => {
      switch (sortCol) {
        case 'name': return [acc.first_name, acc.last_name].filter(Boolean).join(' ').toLowerCase();
        case 'phone': return acc.phone;
        case 'username': return acc.username || '';
        case 'status': return acc.status;
        case 'age': return acc.telegram_created_at || acc.session_created_at || '';
        case 'sent': return acc.messages_sent_today;
        default: return '';
      }
    };
    const va = get(a), vb = get(b);
    if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * m;
    return String(va).localeCompare(String(vb)) * m;
  });

  const totalPages = Math.ceil(total / 50);
  const activeCount = accounts.filter(a => a.status === 'active').length;
  const spamCount = accounts.filter(a => a.status === 'spamblocked').length;
  const isAllSelected = selectedIds.size === accounts.length && accounts.length > 0;
  const isPartial = selectedIds.size > 0 && selectedIds.size < accounts.length;

  return (
    <div className="space-y-3">
      {/* Toolbar — stats + search + actions in one row */}
      <div className="flex items-center gap-3">
        {/* Inline stats */}
        <div className="flex items-center gap-4 text-[13px]">
          <span style={{ color: A.text1 }}><b>{total}</b> <span style={{ color: A.text3 }}>accounts</span></span>
          <span className="w-px h-4" style={{ background: A.border }} />
          <span style={{ color: A.teal }}><b>{activeCount}</b> active</span>
          {spamCount > 0 && <>
            <span className="w-px h-4" style={{ background: A.border }} />
            <span style={{ color: A.rose }}><b>{spamCount}</b> spam</span>
          </>}
        </div>

        <div className="flex-1" />

        {/* Filter toggle */}
        <button onClick={() => setShowFilters(!showFilters)}
          className={cn('p-2 rounded-lg border transition-colors', showFilters || statusFilter ? 'border-[#4F6BF0]/40 bg-[#EEF1FE]' : 'border-[#E8E6E3] hover:bg-[#F5F5F0]')}
          style={showFilters || statusFilter ? { color: A.blue } : { color: A.text3 }}>
          <Filter className="w-4 h-4" />
        </button>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: A.text3 }} />
          <input type="text" placeholder="Search..." value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            className="pl-8 pr-3 py-[7px] rounded-lg border text-[13px] w-52 outline-none focus:border-[#4F6BF0]/50 transition-colors"
            style={{ borderColor: A.border, background: A.surface, color: A.text1 }} />
        </div>

        {/* Add dropdown */}
        <div className="relative" ref={addMenuRef}>
          <button onClick={() => setShowAddMenu(!showAddMenu)}
            className="flex items-center gap-1.5 px-3.5 py-[7px] rounded-lg text-[13px] font-medium text-white transition-colors"
            style={{ background: A.blue }}>
            <Plus className="w-4 h-4" /> Add <ChevronDown className="w-3.5 h-3.5 ml-0.5 opacity-70" />
          </button>
          {showAddMenu && (
            <div className="absolute right-0 top-full mt-1 w-48 rounded-lg border shadow-lg z-50 py-1"
              style={{ background: A.surface, borderColor: A.border }}>
              <button onClick={() => { setShowAddMenu(false); setShowAddByPhoneModal(true); }}
                className="w-full text-left px-3 py-2 text-[13px] hover:bg-[#F5F5F0] transition-colors font-medium"
                style={{ color: A.text1 }}>
                <Phone className="w-3.5 h-3.5 inline mr-2 opacity-50" />Add by Phone
              </button>
              <button onClick={() => { setShowAddMenu(false); setShowAddModal(true); }}
                className="w-full text-left px-3 py-2 text-[13px] hover:bg-[#F5F5F0] transition-colors"
                style={{ color: A.text2 }}>
                <Plus className="w-3.5 h-3.5 inline mr-2 opacity-50" />Manual Entry
              </button>
              <button onClick={() => { setShowAddMenu(false); setShowImportModal(true); }}
                className="w-full text-left px-3 py-2 text-[13px] hover:bg-[#F5F5F0] transition-colors"
                style={{ color: A.text2 }}>
                <Upload className="w-3.5 h-3.5 inline mr-2 opacity-50" />Bulk Import
              </button>
              <div className="border-t my-1" style={{ borderColor: A.border }} />
              <a href={telegramOutreachApi.exportAccountsURL()}
                className="block px-3 py-2 text-[13px] hover:bg-[#F5F5F0] transition-colors"
                style={{ color: A.text2 }}>
                <Download className="w-3.5 h-3.5 inline mr-2 opacity-50" />Export CSV
              </a>
            </div>
          )}
        </div>
      </div>

      {/* Filter bar (collapsible) */}
      {showFilters && (
        <div className="flex items-center gap-1.5 pl-1">
          {[
            { key: '', label: 'All' },
            { key: 'active', label: 'Active' },
            { key: 'spamblocked', label: 'Spamblocked' },
            { key: 'banned', label: 'Banned' },
            { key: 'paused', label: 'Paused' },
            { key: 'dead', label: 'Dead' },
            { key: 'frozen', label: 'Frozen' },
          ].map(f => (
            <button key={f.key}
              onClick={() => { setStatusFilter(f.key); setPage(1); }}
              className="px-3 py-1 rounded-full text-[12px] font-medium transition-all"
              style={{
                background: statusFilter === f.key ? A.blueBg : 'transparent',
                color: statusFilter === f.key ? A.blue : A.text3,
                border: `1px solid ${statusFilter === f.key ? A.blue + '30' : A.border}`,
              }}>
              {f.label}
            </button>
          ))}
          {statusFilter && (
            <button onClick={() => { setStatusFilter(''); setPage(1); }}
              className="ml-1 text-[11px] underline" style={{ color: A.text3 }}>Clear</button>
          )}
        </div>
      )}

      {/* Bulk actions bar — floating at bottom center */}
      {selectedIds.size > 0 && (
        <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40 w-[calc(100%-8rem)] max-w-[1200px]" style={{ filter: 'drop-shadow(0 8px 24px rgba(0,0,0,0.15))' }}>
          <BulkActionsBar
            selectedIds={selectedIds}
            t={t}
            toast={toast}
            onDone={() => { setSelectedIds(new Set()); loadAccounts(); }}
          />
        </div>
      )}

      {/* Overview Analytics Dashboard */}
      {overviewData && (
        <div className="rounded-xl border overflow-hidden" style={{ borderColor: A.border, background: A.surface }}>
          <button
            onClick={() => setShowOverview(!showOverview)}
            className="w-full flex items-center justify-between px-4 py-2.5 text-left transition-colors hover:bg-black/[0.02]"
            style={{ borderBottom: showOverview ? `1px solid ${A.border}` : 'none' }}>
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4" style={{ color: A.blue }} />
              <span className="text-[13px] font-semibold" style={{ color: A.text1 }}>Analytics Overview</span>
            </div>
            {showOverview ? <ChevronUp className="w-4 h-4" style={{ color: A.text3 }} /> : <ChevronDown className="w-4 h-4" style={{ color: A.text3 }} />}
          </button>
          {showOverview && (() => {
            const sent = overviewRange === '7d' ? overviewData.sent_7d : overviewData.sent_30d;
            const replies = overviewRange === '7d' ? overviewData.replies_7d : overviewData.replies_30d;
            const errors = overviewRange === '7d' ? overviewData.errors_7d : overviewData.errors_30d;
            const replyRate = sent > 0 ? ((replies / sent) * 100).toFixed(1) : '0.0';
            const cutoff = new Date();
            cutoff.setDate(cutoff.getDate() - (overviewRange === '7d' ? 7 : 30));
            const chartData = (overviewData.daily || []).filter((d: any) => new Date(d.date) >= cutoff);
            return (
              <div className="p-4 space-y-4">
                {/* Range toggle + metrics row */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-6">
                    <div className="text-center">
                      <div className="text-2xl font-bold" style={{ color: A.blue, fontVariantNumeric: 'tabular-nums' }}>{sent}</div>
                      <div className="text-[10px] font-medium uppercase tracking-wider" style={{ color: A.text3 }}>Unique Sent</div>
                    </div>
                    <div className="w-px h-10" style={{ background: A.border }} />
                    <div className="text-center">
                      <div className="text-2xl font-bold" style={{ color: '#22C55E', fontVariantNumeric: 'tabular-nums' }}>{replies}</div>
                      <div className="text-[10px] font-medium uppercase tracking-wider" style={{ color: A.text3 }}>Unique Replies</div>
                    </div>
                    <div className="w-px h-10" style={{ background: A.border }} />
                    <div className="text-center">
                      <div className="text-2xl font-bold" style={{ color: '#EF4444', fontVariantNumeric: 'tabular-nums' }}>{errors}</div>
                      <div className="text-[10px] font-medium uppercase tracking-wider" style={{ color: A.text3 }}>Spamblock</div>
                    </div>
                    <div className="w-px h-10" style={{ background: A.border }} />
                    <div className="text-center">
                      <div className="text-2xl font-bold" style={{ color: A.text1, fontVariantNumeric: 'tabular-nums' }}>{replyRate}%</div>
                      <div className="text-[10px] font-medium uppercase tracking-wider" style={{ color: A.text3 }}>Reply Rate</div>
                    </div>
                  </div>
                  <div className="flex rounded-lg overflow-hidden border" style={{ borderColor: A.border }}>
                    {(['7d', '30d'] as const).map(r => (
                      <button key={r} onClick={() => setOverviewRange(r)}
                        className="px-4 py-1.5 text-[12px] font-medium transition-colors"
                        style={{
                          background: overviewRange === r ? A.blue : 'transparent',
                          color: overviewRange === r ? '#fff' : A.text3,
                          cursor: 'pointer', border: 'none',
                        }}>
                        {r === '7d' ? '7 days' : '30 days'}
                      </button>
                    ))}
                  </div>
                </div>
                {/* Chart */}
                {chartData.length > 0 && (
                  <ResponsiveContainer width="100%" height={overviewRange === '7d' ? 140 : 180}>
                    <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                      <XAxis dataKey="date" tick={{ fontSize: 10, fill: A.text3 }} tickFormatter={(v: string) => { const d = new Date(v); return `${d.getDate()}/${d.getMonth()+1}`; }} interval="preserveStartEnd" />
                      <YAxis tick={{ fontSize: 10, fill: A.text3 }} allowDecimals={false} />
                      <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8, border: `1px solid ${A.border}`, background: A.surface }} />
                      <Area type="monotone" dataKey="sent" stroke={A.blue} fill={A.blueBg} strokeWidth={1.5} name="Sent" />
                      <Area type="monotone" dataKey="replies" stroke="#22C55E" fill="#DCFCE7" strokeWidth={1.5} name="Replies" />
                      <Area type="monotone" dataKey="spamblocked" stroke="#EF4444" fill="#FEE2E2" strokeWidth={1.5} name="Spamblock" />
                    </AreaChart>
                  </ResponsiveContainer>
                )}
                {chartData.length === 0 && (
                  <div className="text-center py-6 text-[12px]" style={{ color: A.text3 }}>No sending data yet</div>
                )}
              </div>
            );
          })()}
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="w-6 h-6 animate-spin" style={{ color: A.text3 }} />
        </div>
      ) : accounts.length === 0 ? (
        <div className="text-center py-20 rounded-xl border" style={{ borderColor: A.border }}>
          <Users className="w-10 h-10 mx-auto mb-3" style={{ color: A.text3 }} />
          <p className="text-[13px]" style={{ color: A.text3 }}>No accounts yet</p>
        </div>
      ) : (
        <div className="rounded-xl border overflow-hidden" style={{ borderColor: A.border, background: A.surface }}>
          <table className="w-full text-[13px]">
            <thead>
              <tr style={{ background: '#F8F8F6', borderBottom: '1px solid ' + A.border }}>
                <th className="w-10 px-3 py-3">
                  <Tick checked={isAllSelected} indeterminate={isPartial} onChange={toggleAll} />
                </th>
                <th className="w-8 text-center px-1 py-3 text-[11px] font-semibold uppercase tracking-wider" style={{ color: A.text3 }}>#</th>
                <SortHead label="Name" column="name" current={sortCol} dir={sortDir} onSort={handleSort} className="w-[200px]" />
                <SortHead label="Phone" column="phone" current={sortCol} dir={sortDir} onSort={handleSort} className="w-[140px]" />
                <th className="w-[50px] text-center px-1 py-3 text-[11px] font-semibold uppercase tracking-wider" style={{ color: A.text3 }}>Geo</th>
                <SortHead label="Username" column="username" current={sortCol} dir={sortDir} onSort={handleSort} className="w-[180px]" />
                <SortHead label="Status" column="status" current={sortCol} dir={sortDir} onSort={handleSort} className="w-[90px]" />
                <SortHead label="Age" column="age" current={sortCol} dir={sortDir} onSort={handleSort} className="w-[70px]" />
                <SortHead label="Sent" column="sent" current={sortCol} dir={sortDir} onSort={handleSort} className="w-[70px]" />
                <th className="w-8 px-1 py-3" />
              </tr>
            </thead>
            <tbody>
              {sorted.map((acc, idx) => {
                const name = [acc.first_name, acc.last_name].filter(Boolean).join(' ');
                const initials = (acc.first_name?.[0] || '') + (acc.last_name?.[0] || '') || acc.phone.slice(-2);
                const hue = (parseInt(acc.phone.slice(-4), 10) || 0) % 360;
                const isSelected = selectedIds.has(acc.id);
                const effLimit = acc.effective_daily_limit ?? acc.daily_message_limit;
                const atLimit = acc.messages_sent_today >= effLimit;
                return (
                  <tr key={acc.id}
                      onClick={() => setEditingAccount(acc)}
                      className="cursor-pointer transition-colors"
                      style={{
                        borderBottom: `1px solid ${A.border}`,
                        background: isSelected ? A.blueBg : undefined,
                      }}
                      onMouseEnter={e => { if (!isSelected) (e.currentTarget.style.background = isDark ? '#2a2a2a' : '#F8F8F5'); }}
                      onMouseLeave={e => { if (!isSelected) (e.currentTarget.style.background = ''); }}>
                    <td className="px-3 py-2.5" onClick={e => e.stopPropagation()}>
                      <Tick checked={isSelected} onChange={() => toggleSelect(acc.id)} />
                    </td>
                    <td className="text-center px-1 py-2.5 text-[12px] tabular-nums" style={{ color: A.text3 }}>
                      {(page - 1) * 50 + idx + 1}
                    </td>
                    {/* Name + Avatar */}
                    <td className="px-2 py-2.5">
                      <div className="flex items-center gap-2 min-w-0">
                        <div className="w-7 h-7 rounded-full flex-shrink-0 overflow-hidden text-[10px]"
                             style={{ backgroundColor: `hsl(${hue}, 45%, 60%)`, cursor: 'pointer' }}
                             onMouseEnter={e => {
                               const rect = e.currentTarget.getBoundingClientRect();
                               const el = document.getElementById('avatar-zoom-portal');
                               if (el) {
                                 const img = el.querySelector('img') as HTMLImageElement;
                                 if (img) img.src = `/api/telegram-outreach/accounts/${acc.id}/avatar`;
                                 el.style.top = `${rect.top - 148}px`;
                                 el.style.left = `${rect.left + rect.width / 2 - 70}px`;
                                 el.style.display = 'block';
                               }
                             }}
                             onMouseLeave={() => {
                               const el = document.getElementById('avatar-zoom-portal');
                               if (el) el.style.display = 'none';
                             }}>
                          <img src={`/api/telegram-outreach/accounts/${acc.id}/avatar`} alt=""
                               className="w-full h-full object-cover"
                               onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />
                          <span className="w-full h-full flex items-center justify-center text-white text-[11px] font-semibold">
                            {initials.toUpperCase()}
                          </span>
                        </div>
                        <span className="truncate font-medium text-[13px]" style={{ color: A.text1 }}>
                          {name || <span style={{ color: A.text3 }}>No name</span>}
                        </span>
                      </div>
                    </td>
                    <td className="px-2 py-2.5 text-[12px] whitespace-nowrap cursor-pointer"
                        style={{ color: A.text2, fontVariantNumeric: 'tabular-nums' }}
                        onClick={e => { e.stopPropagation(); navigator.clipboard.writeText(acc.phone); toast('Copied', 'info'); }}
                        title="Click to copy">{acc.phone}</td>
                    <td className="px-1 py-2.5 text-center" title={acc.country_code || ''}>
                      {acc.country_code ? <CountryFlag code={acc.country_code} /> : <span className="text-[12px]" style={{ color: A.text3 }}>--</span>}
                    </td>
                    <td className="px-3 py-2.5 text-[12px] truncate" style={{ color: A.text2, maxWidth: 120 }}>
                      {acc.username ? `@${acc.username}` : <span style={{ color: A.text3 }}>--</span>}
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      <div className="flex flex-col gap-0.5">
                        <div className="flex items-center gap-1.5">
                          <StatusBadge status={acc.status} />
                          {acc.spamblock_type !== 'none' && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium" style={{ background: A.roseBg, color: A.rose }}>
                              {acc.spamblock_type}
                            </span>
                          )}
                        </div>
                        {acc.spamblock_type === 'temporary' && acc.spamblock_end && (
                          <span className="text-[10px]" style={{ color: A.rose }}>
                            until {new Date(acc.spamblock_end).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-2 py-2.5 text-[12px] whitespace-nowrap" style={{ color: A.text3 }}>
                      {(acc.session_created_at || acc.telegram_created_at) ? (() => {
                        const fmt = (iso: string) => { const d = new Date(iso); return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' }); };
                        const ageFmt = (iso: string) => { const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000); return days >= 365 ? `${Math.floor(days / 365)}y ${Math.floor((days % 365) / 30)}m` : days >= 30 ? `${Math.floor(days / 30)}m ${days % 30}d` : `${days}d`; };
                        const sessionDate = acc.session_created_at;
                        const tgDate = acc.telegram_created_at;
                        const primaryDate = tgDate || sessionDate!;
                        const lines: string[] = [];
                        if (sessionDate) lines.push(`Сессия: ${fmt(sessionDate)} (${ageFmt(sessionDate)})`);
                        if (tgDate) lines.push(`TG аккаунт: ~${fmt(tgDate)} (${ageFmt(tgDate)})`);
                        return (
                          <span className="age-tooltip-wrap" style={{ cursor: 'default', position: 'relative', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                            {ageFmt(primaryDate)}
                            <span className="age-tooltip">{lines.join('\n')}</span>
                          </span>
                        );
                      })() : '--'}
                    </td>
                    <td className="px-2 py-2.5 text-[12px] whitespace-nowrap tabular-nums">
                      <span style={{ color: atLimit ? A.rose : A.text1, fontWeight: atLimit ? 600 : 400 }}>{acc.messages_sent_today}</span>
                      <span style={{ color: A.text3 }}>/{effLimit}</span>
                      {acc.is_premium && <span className="tip" style={{ color: '#7C3AED', fontSize: 10, marginLeft: 3, fontWeight: 600 }} data-tip="Premium account — higher daily limits">⭐PRO</span>}
                      {acc.skip_warmup ? <span className="tip" style={{ color: '#059669', fontSize: 10, marginLeft: 3 }} data-tip="Warm-up skipped (manual override)">SKIP</span>
                        : acc.warmup_day != null ? <span className="tip" style={{ color: '#d97706', fontSize: 10, marginLeft: 3 }} data-tip={`Warm-up: day ${acc.warmup_day}, limit ${effLimit} msgs/day`}>WU·D{acc.warmup_day}</span> : null}
                      {!acc.skip_warmup && acc.is_young_session && <span className="tip" style={{ color: '#dc2626', fontSize: 10, marginLeft: 3, fontWeight: 600 }} data-tip="Young session (<7 days) — reduced limits & slower sending">YOUNG</span>}
                      {acc.warmup_active && acc.warmup_progress && (
                        acc.warmup_progress.phase === 'maintenance'
                          ? <span className="tip" style={{ color: '#0891b2', fontSize: 10, marginLeft: 3, fontWeight: 600 }} data-tip={`Maintenance mode (day ${acc.warmup_progress.day}): 1-2 reactions/day to keep account healthy`}>✓MT</span>
                          : <span className="tip" style={{ color: '#059669', fontSize: 10, marginLeft: 3, fontWeight: 600 }} data-tip={`Active warm-up: day ${acc.warmup_progress.day}/${acc.warmup_progress.total_days}, ${acc.warmup_actions_done || 0} actions done`}>🔥D{acc.warmup_progress.day}</span>
                      )}
                    </td>
                    <td className="px-1 py-2.5" onClick={e => e.stopPropagation()}>
                      <button onClick={() => setEditingAccount(acc)}
                        className="p-1.5 rounded-md transition-colors hover:bg-[#F0F0ED]">
                        <Edit3 className="w-3.5 h-3.5" style={{ color: A.text3 }} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-1">
          <span className="text-[13px]" style={{ color: A.text3 }}>{total} total</span>
          <div className="flex items-center gap-1">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
              className="px-3 py-1.5 rounded-lg border text-[13px] font-medium transition-colors disabled:opacity-30"
              style={{ borderColor: A.border, color: A.text1 }}>Prev</button>
            <span className="px-3 py-1.5 text-[13px] tabular-nums" style={{ color: A.text2 }}>{page}/{totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
              className="px-3 py-1.5 rounded-lg border text-[13px] font-medium transition-colors disabled:opacity-30"
              style={{ borderColor: A.border, color: A.text1 }}>Next</button>
          </div>
        </div>
      )}

      {/* Modals */}
      {showAddByPhoneModal && (
        <AddByPhoneModal t={t} toast={toast} isDark={isDark}
                         onClose={() => setShowAddByPhoneModal(false)}
                         onSaved={() => { setShowAddByPhoneModal(false); loadAccounts(); }} />
      )}
      {showAddModal && (
        <AddAccountModal t={t} toast={toast} isDark={isDark}
                         onClose={() => setShowAddModal(false)}
                         onSaved={() => { setShowAddModal(false); loadAccounts(); }} />
      )}
      {editingAccount && (
        <EditAccountModal t={t} toast={toast} isDark={isDark}
                          account={editingAccount}
                          onClose={() => setEditingAccount(null)}
                          onSaved={() => { setEditingAccount(null); loadAccounts(); }}
                          onDeleted={() => { setEditingAccount(null); loadAccounts(); }} />
      )}

      {/* Avatar zoom portal */}
      <div id="avatar-zoom-portal" style={{
        display: 'none', position: 'fixed', zIndex: 9999, pointerEvents: 'none',
        width: 140, height: 140, borderRadius: '50%',
        border: '3px solid #fff', boxShadow: '0 8px 30px rgba(0,0,0,0.3)',
        overflow: 'hidden', background: '#e5e7eb',
      }}>
        <img src="" alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }}
             onError={e => { (e.currentTarget.parentElement as HTMLElement).style.display = 'none'; }} />
      </div>

      {/* Import TeleRaptor Modal */}
      {showImportModal && (
        <ImportTeleRaptorModal t={t} toast={toast} isDark={isDark}
                               onClose={() => setShowImportModal(false)}
                               onImported={() => { setShowImportModal(false); loadAccounts(); }} />
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Campaigns Tab
// ══════════════════════════════════════════════════════════════════════

function CampaignsTab({ t: _t, toast }: { t: any; toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) { void _t;
  const navigate = useNavigate();
  const currentProject = useAppStore(s => s.currentProject);
  const [campaigns, setCampaigns] = useState<TgCampaign[]>([]);
  const [loading, setLoading] = useState(true);

  const loadCampaigns = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (currentProject?.id) params.project_id = currentProject.id;
      const data = await telegramOutreachApi.listCampaigns(params);
      setCampaigns(data.items);
    } catch {
      toast('Failed to load campaigns', 'error');
    } finally {
      setLoading(false);
    }
  }, [currentProject?.id, toast]);

  useEffect(() => { loadCampaigns(); }, [loadCampaigns]);

  const [menuOpen, setMenuOpen] = useState<number | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<TgCampaign | null>(null);
  const [tagEditor, setTagEditor] = useState<{ campaign: TgCampaign; tags: string[]; search: string; allTags: string[]; dropdownOpen: boolean } | null>(null);
  const tagInputRef = useRef<HTMLInputElement>(null);

  const openTagEditor = useCallback(async (c: TgCampaign) => {
    const allTags = await telegramOutreachApi.listCampaignTags().catch(() => [] as string[]);
    setTagEditor({ campaign: c, tags: [...(c.tags || [])], search: '', allTags, dropdownOpen: false });
    setTimeout(() => tagInputRef.current?.focus(), 50);
  }, []);

  // Close menu on outside click
  useEffect(() => {
    if (menuOpen === null) return;
    const handler = () => setMenuOpen(null);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [menuOpen]);

  const handleCreate = async () => {
    try {
      const created = await telegramOutreachApi.createCampaign({ name: 'New Campaign', project_id: currentProject?.id });
      toast('Campaign created', 'success');
      navigate(`/outreach/campaigns/${created.id}`);
    } catch {
      toast('Failed to create campaign', 'error');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await telegramOutreachApi.deleteCampaign(id);
      toast('Campaign deleted', 'success');
      setDeleteConfirm(null);
      loadCampaigns();
    } catch {
      toast('Failed to delete campaign', 'error');
    }
  };

  const handleToggle = async (campaign: TgCampaign) => {
    try {
      if (campaign.status === 'active') {
        await telegramOutreachApi.pauseCampaign(campaign.id);
        toast('Campaign paused', 'info');
      } else {
        await telegramOutreachApi.startCampaign(campaign.id);
        toast('Campaign started', 'success');
      }
      loadCampaigns();
    } catch (e: any) {
      toast(e?.response?.data?.detail || 'Action failed', 'error');
    }
  };

  const statusBadge = (status: string) => {
    const map: Record<string, { bg: string; color: string; label: string }> = {
      active: { bg: A.tealBg, color: A.teal, label: 'Active' },
      paused: { bg: '#FFFBEB', color: '#D97706', label: 'Paused' },
      draft: { bg: '#F3F4F6', color: '#6B7280', label: 'Draft' },
      completed: { bg: A.blueBg, color: A.blue, label: 'Completed' },
    };
    const s = map[status] || { bg: '#F3F4F6', color: '#6B7280', label: status };
    return (
      <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: 9999, fontSize: 11, fontWeight: 600, lineHeight: '18px', background: s.bg, color: s.color }}>{s.label}</span>
    );
  };

  const progressBar = (c: TgCampaign) => {
    const pct = c.total_recipients > 0 ? Math.min(100, Math.round((c.total_messages_sent / c.total_recipients) * 100)) : 0;
    const barColor = c.status === 'completed' ? A.blue : A.teal;
    return (
      <div>
        <span style={{ fontSize: 12, color: A.text1, fontWeight: 500 }}>{pct}%</span>
        <div style={{ marginTop: 4, height: 4, borderRadius: 2, background: A.border, width: '100%' }}>
          <div style={{ height: 4, borderRadius: 2, background: barColor, width: `${pct}%`, transition: 'width 0.3s' }} />
        </div>
      </div>
    );
  };

  const thStyle = (extra?: React.CSSProperties): React.CSSProperties => ({
    textAlign: 'left' as const, padding: '10px 12px', fontSize: 11, fontWeight: 600,
    textTransform: 'uppercase' as const, letterSpacing: '0.05em', color: A.text3, ...extra,
  });

  return (
    <div>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <span style={{ fontSize: 14, fontWeight: 500, color: A.text2 }}>
          {campaigns.length} campaign{campaigns.length !== 1 ? 's' : ''}
        </span>
        <button
          onClick={handleCreate}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8, background: A.blue, color: '#FFF', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer' }}
          onMouseEnter={e => { e.currentTarget.style.background = A.blueHover; }}
          onMouseLeave={e => { e.currentTarget.style.background = A.blue; }}
        >
          <Plus className="w-4 h-4" />
          New Campaign
        </button>
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '48px 0' }}>
          <Loader2 className="w-6 h-6 animate-spin" style={{ color: A.text3 }} />
        </div>
      ) : campaigns.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '48px 0', borderRadius: 10, border: `1px solid ${A.border}`, background: A.surface }}>
          <Send className="w-10 h-10 mx-auto mb-3" style={{ color: A.text3 }} />
          <p style={{ fontSize: 13, color: A.text3 }}>No campaigns yet. Create your first campaign to start outreach.</p>
        </div>
      ) : (
        <div style={{ borderRadius: 10, border: `1px solid ${A.border}`, overflow: 'hidden', background: A.surface }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ background: '#F8F8F6' }}>
                <th style={thStyle({ textAlign: 'left', padding: '10px 16px' })}>Name</th>
                <th style={thStyle()}>Status</th>
                <th style={thStyle()}>Tags</th>
                <th style={thStyle({ minWidth: 100 })}>Progress</th>
                <th style={thStyle({ textAlign: 'right' })}>Sent</th>
                <th style={thStyle({ textAlign: 'right' })}>Today</th>
                <th style={thStyle({ textAlign: 'right' })}>Replies</th>
                <th style={thStyle({ textAlign: 'right' })}>Accounts</th>
                <th style={thStyle({ textAlign: 'center' })}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map(c => (
                <tr
                  key={c.id}
                  style={{ borderTop: `1px solid ${A.border}`, cursor: 'pointer' }}
                  onClick={() => navigate(`/outreach/campaigns/${c.id}`)}
                  onMouseEnter={e => { e.currentTarget.style.background = '#F8F8F5'; }}
                  onMouseLeave={e => { e.currentTarget.style.background = ''; }}
                >
                  <td style={{ padding: '12px 16px', fontWeight: 500, color: A.text1, maxWidth: 260 }}>
                    <div className="flex items-center gap-1.5">
                      <span className="truncate">{c.name}</span>
                      {c.campaign_type === 'dynamic' && (
                        <span className="shrink-0 px-1.5 py-0.5 rounded text-[10px] font-semibold"
                          style={{ background: '#F3E8FF', color: '#7C3AED' }}>Dynamic</span>
                      )}
                    </div>
                  </td>
                  <td style={{ padding: '12px 12px' }}>{statusBadge(c.status)}</td>
                  <td className="px-3 py-3" onClick={e => e.stopPropagation()}>
                    <div className="flex items-center gap-1 flex-wrap">
                      {(c.tags || []).map((tag: string) => (
                        <span key={tag} className="px-2 py-0.5 rounded-full text-[11px] font-medium"
                          style={{ background: A.blueBg, color: A.blue }}>{tag}</span>
                      ))}
                      <button onClick={(e) => {
                        e.stopPropagation();
                        openTagEditor(c);
                      }} className="w-5 h-5 rounded-full flex items-center justify-center hover:bg-[#F0F0ED]" style={{ color: A.text3 }}>
                        <Plus className="w-3 h-3" />
                      </button>
                    </div>
                  </td>
                  <td style={{ padding: '12px 12px', minWidth: 100 }}>{progressBar(c)}</td>
                  <td style={{ padding: '12px 12px', textAlign: 'right', fontSize: 12, color: A.text1, fontVariantNumeric: 'tabular-nums' }}>{c.total_messages_sent}</td>
                  <td style={{ padding: '12px 12px', textAlign: 'right', fontSize: 12, color: A.text1, fontVariantNumeric: 'tabular-nums' }}>{c.messages_sent_today}</td>
                  <td style={{ padding: '12px 12px', textAlign: 'right', fontSize: 12, color: c.replies_count > 0 ? A.text1 : A.text3, fontVariantNumeric: 'tabular-nums' }}>{c.replies_count}</td>
                  <td style={{ padding: '12px 12px', textAlign: 'right', fontSize: 12, color: A.text2, fontVariantNumeric: 'tabular-nums' }}>{c.accounts_count}</td>
                  <td style={{ padding: '12px 12px', textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      <button
                        onClick={() => handleToggle(c)}
                        title={c.status === 'active' ? 'Pause' : 'Start'}
                        style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, borderRadius: 6, border: `1px solid ${A.border}`, background: 'transparent', cursor: 'pointer' }}
                        onMouseEnter={e => { e.currentTarget.style.background = '#F3F4F6'; }}
                        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                      >
                        {c.status === 'active'
                          ? <Pause className="w-3.5 h-3.5" style={{ color: '#D97706' }} />
                          : <Play className="w-3.5 h-3.5" style={{ color: A.teal }} />}
                      </button>
                      {/* 3-dot menu */}
                      <div style={{ position: 'relative' }}>
                        <button
                          onClick={() => setMenuOpen(menuOpen === c.id ? null : c.id)}
                          style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, borderRadius: 6, border: `1px solid ${A.border}`, background: 'transparent', cursor: 'pointer' }}
                          onMouseEnter={e => { e.currentTarget.style.background = '#F3F4F6'; }}
                          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                        >
                          <MoreVertical className="w-3.5 h-3.5" style={{ color: A.text3 }} />
                        </button>
                        {menuOpen === c.id && (
                          <div style={{ position: 'absolute', right: 0, top: '100%', marginTop: 4, width: 160, borderRadius: 10, border: `1px solid ${A.border}`, background: A.surface, boxShadow: '0 4px 12px rgba(0,0,0,0.08)', zIndex: 50, padding: '4px 0' }}>
                            <button onClick={() => {
                              setMenuOpen(null);
                              openTagEditor(c);
                            }} style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '8px 12px', fontSize: 13, color: A.text1, background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left' }}
                              onMouseEnter={e => { e.currentTarget.style.background = '#F5F5F0'; }}
                              onMouseLeave={e => { e.currentTarget.style.background = ''; }}>
                              <Tag className="w-3.5 h-3.5" /> Set Tag
                            </button>
                            <button onClick={() => { setMenuOpen(null); setDeleteConfirm(c); }}
                              style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '8px 12px', fontSize: 13, color: A.rose, background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left' }}
                              onMouseEnter={e => { e.currentTarget.style.background = A.roseBg; }}
                              onMouseLeave={e => { e.currentTarget.style.background = ''; }}>
                              <Trash2 className="w-3.5 h-3.5" /> Delete
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.4)' }} onClick={() => setDeleteConfirm(null)} />
          <div style={{ position: 'relative', zIndex: 10, width: 400, borderRadius: 16, background: A.surface, padding: 24, boxShadow: '0 20px 60px rgba(0,0,0,0.15)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
              <div style={{ padding: 8, borderRadius: 9999, background: A.roseBg }}>
                <AlertTriangle className="w-5 h-5" style={{ color: A.rose }} />
              </div>
              <h3 style={{ fontSize: 18, fontWeight: 600, color: A.text1 }}>Delete Campaign</h3>
            </div>
            <p style={{ fontSize: 14, color: A.text2, marginBottom: 24 }}>
              Are you sure you want to delete <b>"{deleteConfirm.name}"</b>? This cannot be undone.
            </p>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button onClick={() => setDeleteConfirm(null)}
                style={{ padding: '8px 16px', borderRadius: 8, border: `1px solid ${A.border}`, background: A.surface, fontSize: 13, fontWeight: 500, color: A.text1, cursor: 'pointer' }}>
                Cancel
              </button>
              <button onClick={() => handleDelete(deleteConfirm.id)}
                style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: A.rose, color: '#FFF', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tag Editor Modal */}
      {tagEditor && (() => {
        const { campaign, tags, search, allTags, dropdownOpen } = tagEditor;
        const searchLower = search.toLowerCase().trim();
        const suggestions = allTags.filter(t => !tags.includes(t) && t.toLowerCase().includes(searchLower));
        const canCreate = searchLower.length > 0 && !tags.some(t => t.toLowerCase() === searchLower) && !allTags.some(t => t.toLowerCase() === searchLower);
        const showDropdown = dropdownOpen && (suggestions.length > 0 || canCreate);

        const addTag = (tag: string) => {
          const trimmed = tag.trim();
          if (!trimmed || tags.some(t => t.toLowerCase() === trimmed.toLowerCase())) return;
          setTagEditor({ ...tagEditor, tags: [...tags, trimmed], search: '', dropdownOpen: false });
          setTimeout(() => tagInputRef.current?.focus(), 20);
        };
        const removeTag = (tag: string) => {
          setTagEditor({ ...tagEditor, tags: tags.filter(t => t !== tag) });
        };
        const handleSave = () => {
          telegramOutreachApi.updateCampaignTags(campaign.id, tags).then(() => { loadCampaigns(); setTagEditor(null); toast('Tags updated', 'success'); });
        };

        return (
          <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.4)' }} onClick={() => setTagEditor(null)} />
            <div style={{ position: 'relative', zIndex: 10, width: 400, borderRadius: 16, background: A.surface, padding: 24, boxShadow: '0 20px 60px rgba(0,0,0,0.15)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
                <Tag className="w-5 h-5" style={{ color: A.blue }} />
                <h3 style={{ fontSize: 16, fontWeight: 600, color: A.text1 }}>Set Tags</h3>
              </div>
              <p style={{ fontSize: 13, color: A.text3, marginBottom: 12 }}>
                Campaign: <b style={{ color: A.text1 }}>{campaign.name}</b>
              </p>

              {/* Current tags as pills */}
              {tags.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
                  {tags.map(tag => (
                    <span key={tag} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 10px', borderRadius: 9999, background: A.blueBg, color: A.blue, fontSize: 12, fontWeight: 500 }}>
                      {tag}
                      <button onClick={() => removeTag(tag)} style={{ display: 'inline-flex', background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: A.blue, opacity: 0.6 }}
                        onMouseEnter={e => { e.currentTarget.style.opacity = '1'; }} onMouseLeave={e => { e.currentTarget.style.opacity = '0.6'; }}>
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}

              {/* Search input with dropdown */}
              <div style={{ position: 'relative' }}>
                <input
                  ref={tagInputRef}
                  value={search}
                  onChange={e => setTagEditor({ ...tagEditor, search: e.target.value, dropdownOpen: true })}
                  onFocus={() => setTagEditor({ ...tagEditor, dropdownOpen: true })}
                  placeholder={tags.length > 0 ? 'Add another tag...' : 'Search or create tags...'}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none focus:ring-2 focus:ring-[#4F6BF0]/20"
                  style={{ border: `1px solid ${A.border}`, color: A.text1 }}
                  onKeyDown={e => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      if (searchLower) addTag(search);
                    } else if (e.key === 'Backspace' && !search && tags.length > 0) {
                      removeTag(tags[tags.length - 1]);
                    } else if (e.key === 'Escape') {
                      setTagEditor({ ...tagEditor, dropdownOpen: false });
                    }
                  }}
                />
                {showDropdown && (
                  <div style={{ position: 'absolute', left: 0, right: 0, top: '100%', marginTop: 4, maxHeight: 180, overflowY: 'auto', borderRadius: 10, border: `1px solid ${A.border}`, background: A.surface, boxShadow: '0 4px 12px rgba(0,0,0,0.08)', zIndex: 60, padding: '4px 0' }}>
                    {suggestions.map(tag => (
                      <button key={tag} onClick={() => addTag(tag)}
                        style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '7px 12px', fontSize: 13, color: A.text1, background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left' }}
                        onMouseEnter={e => { e.currentTarget.style.background = '#F5F5F0'; }}
                        onMouseLeave={e => { e.currentTarget.style.background = ''; }}>
                        <Tag className="w-3 h-3" style={{ color: A.text3 }} /> {tag}
                      </button>
                    ))}
                    {canCreate && (
                      <button onClick={() => addTag(search)}
                        style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '7px 12px', fontSize: 13, color: A.blue, background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', fontWeight: 500 }}
                        onMouseEnter={e => { e.currentTarget.style.background = A.blueBg; }}
                        onMouseLeave={e => { e.currentTarget.style.background = ''; }}>
                        <Plus className="w-3 h-3" /> Create "{search.trim()}"
                      </button>
                    )}
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 16 }}>
                <button onClick={() => setTagEditor(null)}
                  style={{ padding: '8px 16px', borderRadius: 8, border: `1px solid ${A.border}`, background: A.surface, fontSize: 13, fontWeight: 500, color: A.text1, cursor: 'pointer' }}>
                  Cancel
                </button>
                <button onClick={handleSave}
                  style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: A.blue, color: '#FFF', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
                  Save
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Proxies Tab
// ══════════════════════════════════════════════════════════════════════

function ProxiesTab({ t: _t, toast }: { t: any; toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) { void _t;
  const [groups, setGroups] = useState<TgProxyGroup[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<TgProxyGroup | null>(null);
  const [proxies, setProxies] = useState<TgProxy[]>([]);
  const [loading, setLoading] = useState(true);
  const [proxyText, setProxyText] = useState('');
  const [showAddGroup, setShowAddGroup] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');
  const [newGroupCountry, setNewGroupCountry] = useState('');
  const [checking, setChecking] = useState(false);
  const [checkResults, setCheckResults] = useState<Record<number, { alive: boolean; latency_ms: number | null; error: string | null }>>({});

  const loadGroups = useCallback(async () => {
    setLoading(true);
    try {
      const data = await telegramOutreachApi.listProxyGroups();
      setGroups(data);
      if (data.length > 0 && !selectedGroup) {
        setSelectedGroup(data[0]);
      }
    } catch {
      toast('Failed to load proxy groups', 'error');
    } finally {
      setLoading(false);
    }
  }, [toast]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadProxies = useCallback(async () => {
    if (!selectedGroup) { setProxies([]); return; }
    try {
      const data = await telegramOutreachApi.listProxies(selectedGroup.id);
      setProxies(data);
    } catch {
      toast('Failed to load proxies', 'error');
    }
  }, [selectedGroup, toast]);

  useEffect(() => { loadGroups(); }, [loadGroups]);
  useEffect(() => { loadProxies(); }, [loadProxies]);

  const handleCreateGroup = async () => {
    if (!newGroupName.trim()) return;
    try {
      const group = await telegramOutreachApi.createProxyGroup({
        name: newGroupName.trim(),
        country: newGroupCountry.trim() || undefined,
      });
      toast('Group created', 'success');
      setShowAddGroup(false);
      setNewGroupName('');
      setNewGroupCountry('');
      loadGroups();
      setSelectedGroup(group);
    } catch {
      toast('Failed to create group', 'error');
    }
  };

  const handleDeleteGroup = async (id: number) => {
    try {
      await telegramOutreachApi.deleteProxyGroup(id);
      toast('Group deleted', 'success');
      if (selectedGroup?.id === id) setSelectedGroup(null);
      loadGroups();
    } catch {
      toast('Failed to delete group', 'error');
    }
  };

  const handleAddProxies = async () => {
    if (!selectedGroup || !proxyText.trim()) return;
    try {
      const added = await telegramOutreachApi.addProxiesBulk(selectedGroup.id, proxyText.trim());
      toast(`${added.length} proxies added`, 'success');
      setProxyText('');
      loadProxies();
      loadGroups();
    } catch {
      toast('Failed to add proxies', 'error');
    }
  };

  const handleDeleteProxy = async (id: number) => {
    try {
      await telegramOutreachApi.deleteProxy(id);
      loadProxies();
      loadGroups();
    } catch {
      toast('Failed to delete proxy', 'error');
    }
  };

  return (
    <div className="flex gap-6 h-[calc(100vh-240px)]">
      {/* Left: Groups */}
      <div className="w-72 flex-shrink-0 rounded-lg border flex flex-col" style={{ borderColor: A.border }}>
        <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: A.border }}>
          <h3 className="text-sm font-medium" style={{ color: A.text1 }}>Proxy Groups</h3>
          <button onClick={() => setShowAddGroup(true)} className="p-1 hover:bg-[#F5F5F0] rounded" title="New group">
            <Plus className="w-4 h-4" style={{ color: A.text3 }} />
          </button>
        </div>

        {showAddGroup && (
          <div className="px-4 py-3 border-b space-y-2" style={{ borderColor: A.border }}>
            <input type="text" placeholder="Group name" value={newGroupName}
                   onChange={e => setNewGroupName(e.target.value)}
                   className="w-full px-3 py-1.5 rounded border text-sm" style={{ borderColor: A.border, background: A.surface, color: A.text1 }} />
            <input type="text" placeholder="Country (optional)" value={newGroupCountry}
                   onChange={e => setNewGroupCountry(e.target.value)}
                   className="w-full px-3 py-1.5 rounded border text-sm" style={{ borderColor: A.border, background: A.surface, color: A.text1 }} />
            <div className="flex gap-2">
              <button onClick={handleCreateGroup}
                      className="px-3 py-1 text-white rounded text-xs font-medium" style={{ background: A.blue }}>
                Create
              </button>
              <button onClick={() => setShowAddGroup(false)}
                      className="px-3 py-1 rounded border text-xs" style={{ borderColor: A.border, color: A.text1 }}>
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin" style={{ color: A.text3 }} />
            </div>
          ) : groups.length === 0 ? (
            <p className="text-center py-8 text-sm" style={{ color: A.text3 }}>No groups yet</p>
          ) : groups.map(g => (
            <div key={g.id}
                 onClick={() => setSelectedGroup(g)}
                 className={cn(
                   'px-4 py-3 cursor-pointer border-b flex items-center justify-between',
                   selectedGroup?.id === g.id
                     ? ''
                     : 'hover:bg-[#F5F5F0]',
                 )}
                 style={{
                   borderColor: A.border,
                   ...(selectedGroup?.id === g.id ? { background: A.blueBg } : {}),
                 }}>
              <div>
                <div className="text-sm font-medium" style={{ color: A.text1 }}>{g.name}</div>
                <div className="text-xs" style={{ color: A.text3 }}>
                  {g.country ? `${g.country} · ` : ''}{g.proxies_count} proxies
                </div>
              </div>
              <button onClick={e => { e.stopPropagation(); handleDeleteGroup(g.id); }}
                      className="p-1 hover:bg-red-50 rounded opacity-0 group-hover:opacity-100">
                <Trash2 className="w-3.5 h-3.5" style={{ color: A.rose }} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Right: Proxies in selected group */}
      <div className="flex-1 flex flex-col gap-4">
        {selectedGroup ? (
          <>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-medium" style={{ color: A.text1 }}>
                {selectedGroup.name} — {proxies.length} proxies
              </h3>
              <div className="flex items-center gap-2">
                <button onClick={async () => {
                          setChecking(true); setCheckResults({});
                          try {
                            const res = await telegramOutreachApi.checkProxyGroup(selectedGroup.id, false);
                            const map: typeof checkResults = {};
                            res.results.forEach(r => { map[r.proxy_id] = { alive: r.alive, latency_ms: r.latency_ms, error: r.error }; });
                            setCheckResults(map);
                            toast(`${res.alive} alive, ${res.dead} dead out of ${res.total}`, res.dead > 0 ? 'error' : 'success');
                          } catch { toast('Check failed', 'error'); }
                          finally { setChecking(false); }
                        }}
                        disabled={checking || proxies.length === 0}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium hover:bg-[#F5F5F0] disabled:opacity-50"
                        style={{ borderColor: A.border, color: A.text1 }}>
                  {checking ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                  Check All
                </button>
                <button onClick={async () => {
                          if (!confirm('Check all proxies and DELETE non-working ones?')) return;
                          setChecking(true); setCheckResults({});
                          try {
                            const res = await telegramOutreachApi.checkProxyGroup(selectedGroup.id, true);
                            const map: typeof checkResults = {};
                            res.results.forEach(r => { map[r.proxy_id] = { alive: r.alive, latency_ms: r.latency_ms, error: r.error }; });
                            setCheckResults(map);
                            toast(`${res.alive} alive, ${res.deleted} deleted`, res.deleted > 0 ? 'info' : 'success');
                            if (res.deleted > 0) { loadProxies(); loadGroups(); }
                          } catch { toast('Check failed', 'error'); }
                          finally { setChecking(false); }
                        }}
                        disabled={checking || proxies.length === 0}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium hover:opacity-80 disabled:opacity-50"
                        style={{ background: A.roseBg, color: A.rose }}>
                  {checking ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                  Check & Clean
                </button>
              </div>
            </div>

            {/* Add proxies */}
            <div className="flex gap-2">
              <textarea
                rows={3}
                placeholder="Paste proxies (one per line): ip:port:user:pass or user:pass@ip:port"
                value={proxyText}
                onChange={e => setProxyText(e.target.value)}
                className="flex-1 px-3 py-2 rounded-lg border text-sm font-mono"
                style={{ borderColor: A.border, background: A.surface, color: A.text1 }}
              />
              <button onClick={handleAddProxies} disabled={!proxyText.trim()}
                      className="px-4 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50 self-end"
                      style={{ background: A.blue }}>
                Add
              </button>
            </div>

            {/* Proxy list */}
            <div className="rounded-lg border overflow-hidden flex-1" style={{ borderColor: A.border }}>
              <table className="w-full text-sm">
                <thead className="border-b" style={{ borderColor: A.border, background: '#F9F9F7' }}>
                  <tr>
                    <th className="text-left px-3 py-2 font-medium" style={{ color: A.text3 }}>Host</th>
                    <th className="text-left px-3 py-2 font-medium" style={{ color: A.text3 }}>Port</th>
                    <th className="text-left px-3 py-2 font-medium" style={{ color: A.text3 }}>User</th>
                    <th className="text-left px-3 py-2 font-medium" style={{ color: A.text3 }}>Protocol</th>
                    <th className="text-left px-3 py-2 font-medium" style={{ color: A.text3 }}>Status</th>
                    <th className="w-10" />
                  </tr>
                </thead>
                <tbody>
                  {proxies.length === 0 ? (
                    <tr><td colSpan={6} className="text-center py-8" style={{ color: A.text3 }}>No proxies in this group</td></tr>
                  ) : proxies.map(p => (
                    <tr key={p.id} className="border-b" style={{ borderColor: A.border }}>
                      <td className="px-3 py-2 text-[13px]" style={{ color: A.text1, fontVariantNumeric: 'tabular-nums' }}>{p.host}</td>
                      <td className="px-3 py-2 text-[13px]" style={{ color: A.text1, fontVariantNumeric: 'tabular-nums' }}>{p.port}</td>
                      <td className="px-3 py-2 text-xs" style={{ color: A.text3 }}>{p.username || '—'}</td>
                      <td className="px-3 py-2 text-xs" style={{ color: A.text3 }}>{p.protocol}</td>
                      <td className="px-3 py-2">
                        {checkResults[p.id] ? (
                          <span className={cn('px-1.5 py-0.5 rounded text-xs',
                            checkResults[p.id].alive
                              ? 'bg-green-100 text-green-700'
                              : 'bg-red-100 text-red-600'
                          )}>
                            {checkResults[p.id].alive
                              ? `alive ${checkResults[p.id].latency_ms}ms`
                              : `dead`}
                          </span>
                        ) : (
                          <span className={cn('px-1.5 py-0.5 rounded text-xs', p.is_active ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600')}>
                            {p.is_active ? 'active' : 'inactive'}
                          </span>
                        )}
                        {checkResults[p.id] && !checkResults[p.id].alive && checkResults[p.id].error && (
                          <span className="ml-1 text-xs" style={{ color: A.rose }} title={checkResults[p.id].error!}>
                            ({checkResults[p.id].error!.substring(0, 20)})
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <button onClick={() => handleDeleteProxy(p.id)} className="p-1 hover:bg-red-50 rounded">
                          <Trash2 className="w-3.5 h-3.5" style={{ color: A.rose }} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <div className="flex items-center justify-center h-full" style={{ color: A.text3 }}>
            <div className="text-center">
              <Globe className="w-10 h-10 mx-auto mb-3 opacity-50" />
              <p className="text-sm">Select a proxy group or create a new one</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════
// Modal Backdrop
// ══════════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════════
// App Version Panel (inline in BulkActionsBar)
// ══════════════════════════════════════════════════════════════════════

function AppVersionPanel({ ids, loading, run, inputCls, inputStyle }: {
  ids: number[]; loading: boolean;
  run: (label: string, fn: () => Promise<any>) => void;
  inputCls: string; inputStyle: React.CSSProperties;
}) {
  const [latestVersion, setLatestVersion] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const [customVersion, setCustomVersion] = useState('');
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    telegramOutreachApi.getLatestAppVersion().then(data => {
      setLatestVersion(data.latest_version);
      setCheckedAt(data.checked_at);
    }).catch(() => {});
  }, []);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const data = await telegramOutreachApi.refreshAppVersion();
      setLatestVersion(data.latest_version);
      setCheckedAt(new Date().toISOString());
    } catch { /* ignore */ }
    finally { setRefreshing(false); }
  };

  const targetVersion = customVersion || latestVersion || '';

  return (
    <div className="flex flex-col gap-2 pt-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium" style={{ color: A.text3 }}>Latest TG Desktop:</span>
        <span className="text-xs font-semibold" style={{ color: latestVersion ? A.teal : A.rose }}>
          {latestVersion || 'unknown'}
        </span>
        {checkedAt && (
          <span className="text-[10px]" style={{ color: A.text3 }}>
            (checked {new Date(checkedAt).toLocaleDateString()})
          </span>
        )}
        <button onClick={handleRefresh} disabled={refreshing}
                className="text-[11px] px-2 py-0.5 rounded" style={{ background: A.surface, border: `1px solid ${A.border}`, color: A.text2, cursor: 'pointer' }}>
          {refreshing ? '...' : 'Refresh'}
        </button>
      </div>
      <div className="flex items-center gap-2">
        <input type="text" value={customVersion} onChange={e => setCustomVersion(e.target.value)}
               placeholder={latestVersion || 'e.g. 6.7.1 x64'} className={cn(inputCls, 'w-40')} style={inputStyle} />
        <button onClick={() => run(`App version → ${targetVersion}`, () => telegramOutreachApi.bulkUpdateAppVersion(ids, customVersion || undefined))}
                disabled={loading || !targetVersion}
                className="px-3 py-1 text-white rounded-md text-[12px] font-medium" style={{ background: A.blue }}>
          Apply to {ids.length}
        </button>
        <button onClick={() => run(`App version → ${targetVersion} (all)`, () => telegramOutreachApi.updateAllAppVersion(customVersion || undefined))}
                disabled={loading || !targetVersion}
                className="px-3 py-1 rounded-md text-[12px] font-medium" style={{ background: A.teal, color: '#fff' }}>
          Apply to ALL
        </button>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Bulk Actions Bar
// ══════════════════════════════════════════════════════════════════════

function BulkActionsBar({ selectedIds, t, toast, onDone }: {
  selectedIds: Set<number>; t: any; toast: any; onDone: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [activePanel, setActivePanel] = useState<string | null>(null);
  // Panel values
  const [limitValue, setLimitValue] = useState('10');
  const [bioValue, setBioValue] = useState('');
  const [twoFaValue, setTwoFaValue] = useState('');
  const [langCode, setLangCode] = useState('pt');
  const [sysLangCode, setSysLangCode] = useState('pt-PT');
  const [proxyGroupId, setProxyGroupId] = useState<number | ''>('');
  const [proxyDropdownOpen, setProxyDropdownOpen] = useState(false);
  const [proxyGroups, setProxyGroups] = useState<TgProxyGroup[]>([]);
  const [nameCategory, setNameCategory] = useState('male_en');
  const photoInputRef = useRef<HTMLInputElement>(null);
  const [photoFiles, setPhotoFiles] = useState<File[]>([]);
  // Staggered operation progress
  const [staggeredTask, setStaggeredTask] = useState<{ taskId: string; operation: string; total: number; completed: number; synced: number; errors: string[]; status: string; currentPhone: string | null; nextDelay: number } | null>(null);
  const staggeredPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const ids = Array.from(selectedIds);

  // Cleanup poll on unmount
  useEffect(() => { return () => { if (staggeredPollRef.current) clearInterval(staggeredPollRef.current); }; }, []);

  useEffect(() => {
    telegramOutreachApi.listProxyGroups().then(setProxyGroups).catch(() => {});
  }, []);

  const run = async (label: string, fn: () => Promise<any>) => {
    setLoading(true);
    try {
      await fn();
      toast(`${label} — ${ids.length} accounts`, 'success');
      setActivePanel(null);
      onDone();
    } catch { toast(`Failed: ${label}`, 'error'); }
    finally { setLoading(false); }
  };

  const _STAGGER_AVG = 75; // avg delay seconds for time estimation

  /** Run a profile-changing operation that returns task_id for staggered TG sync */
  const runStaggered = async (label: string, fn: () => Promise<any>) => {
    const estMinutes = Math.ceil(ids.length * (_STAGGER_AVG) / 60);
    if (!window.confirm(
      `⚠ Profile change: "${label}" for ${ids.length} accounts.\n\n` +
      `To avoid bans, Telegram sync will run with 30-120s delays between accounts.\n` +
      `Estimated time: ~${estMinutes} min.\n\nDB changes apply immediately. Continue?`
    )) return;
    setLoading(true);
    try {
      const res = await fn();
      const taskId = res?.task_id;
      if (taskId) {
        setStaggeredTask({ taskId, operation: label, total: ids.length, completed: 0, synced: 0, errors: [], status: 'running', currentPhone: null, nextDelay: 0 });
        setActivePanel(null);
        // Start polling
        if (staggeredPollRef.current) clearInterval(staggeredPollRef.current);
        staggeredPollRef.current = setInterval(async () => {
          try {
            const p = await telegramOutreachApi.bulkOpProgress(taskId);
            setStaggeredTask(prev => prev ? { ...prev, completed: p.completed, synced: p.synced, errors: p.errors || [], status: p.status, currentPhone: p.current_phone, nextDelay: p.next_delay || 0 } : null);
            if (p.status === 'completed') {
              if (staggeredPollRef.current) clearInterval(staggeredPollRef.current);
              staggeredPollRef.current = null;
              toast(`${label} — synced ${p.synced}/${p.total} to Telegram` + (p.errors?.length ? ` (${p.errors.length} errors)` : ''), p.errors?.length ? 'warning' : 'success');
              setTimeout(() => setStaggeredTask(null), 5000);
              onDone();
            }
          } catch { /* ignore poll errors */ }
        }, 3000);
        toast(`${label} — DB updated. TG sync running in background...`, 'info');
      } else {
        toast(`${label} — ${ids.length} accounts`, 'success');
        setActivePanel(null);
        onDone();
      }
    } catch { toast(`Failed: ${label}`, 'error'); }
    finally { setLoading(false); }
  };

  const btnCls = 'flex items-center gap-1.5 px-2.5 py-[5px] rounded-md border text-[12px] font-medium transition-colors disabled:opacity-40';
  const btnStyle = { borderColor: A.border, color: A.text1, background: A.surface };
  const inputCls = 'px-2.5 py-1.5 rounded-lg text-[12px] outline-none focus:ring-2 focus:ring-[#4F6BF0]/20';
  const inputStyle = { border: `1px solid ${A.border}`, background: A.surface, color: A.text1 };

  const [showActionsPopup, setShowActionsPopup] = useState(false);
  const menuItemCls = 'w-full text-left px-4 py-2 text-[13px] flex items-center gap-2.5 transition-colors';

  return (
    <div className="rounded-xl px-5 py-3" style={{ background: A.blueBg, border: `1px solid ${A.blue}30` }}>
      <div className="flex items-center gap-2">
        <span className="text-[12px] font-semibold" style={{ color: A.blue }}>{selectedIds.size} selected</span>
        <button onClick={onDone} className="text-[11px] underline" style={{ color: A.text3 }}>Deselect</button>

        <div className="flex-1" />

        {/* Alive + Spam quick buttons */}
        <button onClick={async () => {
          setLoading(true);
          try {
            const res = await telegramOutreachApi.bulkCheckAlive(ids);
            const parts = [`✓ ${res.alive ?? 0} alive`];
            if (res.frozen) parts.push(`⚠ ${res.frozen} frozen`);
            if (res.banned) parts.push(`✕ ${res.banned} banned`);
            if (res.dead) parts.push(`☠ ${res.dead} dead`);
            if (res.errors) parts.push(`⚡ ${res.errors} errors`);
            toast(parts.join(' · '), res.alive === res.total ? 'success' : 'warning');
            onDone();
          } catch { toast('Alive check failed', 'error'); }
          finally { setLoading(false); }
        }}
                disabled={loading} className={btnCls} style={{ ...btnStyle, color: A.teal, borderColor: A.teal + '40' }}>
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />} Alive?
        </button>
        <button onClick={() => run('Spamblock checked', () => telegramOutreachApi.bulkCheck(ids))}
                disabled={loading} className={btnCls} style={{ ...btnStyle, color: '#D97706', borderColor: '#D9770640' }}>
          <Shield className="w-3 h-3" /> Spam?
        </button>

        {/* Delete */}
        <button onClick={() => setConfirmDelete(true)} disabled={loading}
                className="flex items-center gap-1.5 px-2.5 py-[5px] rounded-md text-[12px] font-medium"
                style={{ background: A.roseBg, color: A.rose }}>
          <Trash2 className="w-3 h-3" /> Delete
        </button>

        {/* Actions button → popup */}
        <button onClick={() => setShowActionsPopup(true)}
                className="flex items-center gap-1.5 px-4 py-[5px] rounded-md text-[12px] font-semibold text-white"
                style={{ background: A.blue, cursor: 'pointer' }}>
          Actions...
        </button>
      </div>

      {/* Actions popup modal — portaled to body to escape stacking context */}
      {showActionsPopup && createPortal(
        <ModalBackdrop onClose={() => setShowActionsPopup(false)}>
          <div className="w-[340px] rounded-xl border shadow-xl" style={{ borderColor: A.border, background: A.surface }}>
            <div className="px-4 py-3 flex items-center justify-between" style={{ borderBottom: `1px solid ${A.border}` }}>
              <span className="text-sm font-semibold" style={{ color: A.text1 }}>Actions for {ids.length} accounts</span>
              <button onClick={() => setShowActionsPopup(false)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
                <X className="w-4 h-4" style={{ color: A.text3 }} />
              </button>
            </div>

            {/* Profile section */}
            <div className="px-2 py-1.5">
              <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider" style={{ color: A.text3 }}>Profile</div>
              <button onClick={() => { setShowActionsPopup(false); setActivePanel('names'); }} className={menuItemCls} style={{ color: A.text1 }} onMouseEnter={e => e.currentTarget.style.background = '#F5F5F0'} onMouseLeave={e => e.currentTarget.style.background = ''}>
                <Users className="w-3.5 h-3.5" style={{ color: A.text3 }} /> Set Names
              </button>
              <button onClick={() => { setShowActionsPopup(false); setActivePanel('bio'); }} className={menuItemCls} style={{ color: A.text1 }} onMouseEnter={e => e.currentTarget.style.background = '#F5F5F0'} onMouseLeave={e => e.currentTarget.style.background = ''}>
                <Edit3 className="w-3.5 h-3.5" style={{ color: A.text3 }} /> Set Bio
              </button>
              <button onClick={() => { setShowActionsPopup(false); setActivePanel('photo'); }} className={menuItemCls} style={{ color: A.text1 }} onMouseEnter={e => e.currentTarget.style.background = '#F5F5F0'} onMouseLeave={e => e.currentTarget.style.background = ''}>
                <Upload className="w-3.5 h-3.5" style={{ color: A.text3 }} /> Set Photo
              </button>
            </div>

            <div style={{ height: 1, background: A.border, margin: '0 8px' }} />

            {/* Technical section */}
            <div className="px-2 py-1.5">
              <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider" style={{ color: A.text3 }}>Technical</div>
              <button onClick={() => { setShowActionsPopup(false); setActivePanel('device'); }} className={menuItemCls} style={{ color: A.text1 }} onMouseEnter={e => e.currentTarget.style.background = '#F5F5F0'} onMouseLeave={e => e.currentTarget.style.background = ''}>
                <Globe className="w-3.5 h-3.5" style={{ color: A.text3 }} /> Device Settings
              </button>
              <button onClick={() => { setShowActionsPopup(false); setActivePanel('appversion'); }} className={menuItemCls} style={{ color: A.text1 }} onMouseEnter={e => e.currentTarget.style.background = '#F5F5F0'} onMouseLeave={e => e.currentTarget.style.background = ''}>
                <RefreshCw className="w-3.5 h-3.5" style={{ color: A.teal }} /> Update App Version
              </button>
              <button onClick={() => { setShowActionsPopup(false); setActivePanel('limit'); }} className={menuItemCls} style={{ color: A.text1 }} onMouseEnter={e => e.currentTarget.style.background = '#F5F5F0'} onMouseLeave={e => e.currentTarget.style.background = ''}>
                <Minus className="w-3.5 h-3.5" style={{ color: A.text3 }} /> Daily Limit
              </button>
              <button onClick={() => { setShowActionsPopup(false); setActivePanel('warmup-settings'); }} className={menuItemCls} style={{ color: A.text1 }} onMouseEnter={e => e.currentTarget.style.background = '#F5F5F0'} onMouseLeave={e => e.currentTarget.style.background = ''}>
                <Play className="w-3.5 h-3.5" style={{ color: '#059669' }} /> Warm-up
              </button>
              <button onClick={() => { setShowActionsPopup(false); setActivePanel('2fa'); }} className={menuItemCls} style={{ color: A.text1 }} onMouseEnter={e => e.currentTarget.style.background = '#F5F5F0'} onMouseLeave={e => e.currentTarget.style.background = ''}>
                <Shield className="w-3.5 h-3.5" style={{ color: A.text3 }} /> Change 2FA
              </button>
              <button onClick={() => { setShowActionsPopup(false); setActivePanel('lang'); }} className={menuItemCls} style={{ color: A.text1 }} onMouseEnter={e => e.currentTarget.style.background = '#F5F5F0'} onMouseLeave={e => e.currentTarget.style.background = ''}>
                <Globe className="w-3.5 h-3.5" style={{ color: A.text3 }} /> Language
              </button>
              <button onClick={() => { setShowActionsPopup(false); setActivePanel('proxy'); }} className={menuItemCls} style={{ color: A.text1 }} onMouseEnter={e => e.currentTarget.style.background = '#F5F5F0'} onMouseLeave={e => e.currentTarget.style.background = ''}>
                <Shield className="w-3.5 h-3.5" style={{ color: A.text3 }} /> Proxy
              </button>
              <button onClick={() => { setShowActionsPopup(false); setActivePanel('privacy'); }} className={menuItemCls} style={{ color: A.text1 }} onMouseEnter={e => e.currentTarget.style.background = '#F5F5F0'} onMouseLeave={e => e.currentTarget.style.background = ''}>
                <Filter className="w-3.5 h-3.5" style={{ color: A.text3 }} /> Privacy
              </button>
            </div>

            <div style={{ height: 1, background: A.border, margin: '0 8px' }} />

            {/* Session section */}
            <div className="px-2 py-1.5">
              <div className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider" style={{ color: A.text3 }}>Session</div>
              <button onClick={() => { setShowActionsPopup(false); run('Re-authorized', () => telegramOutreachApi.bulkReauthorize(ids)); }} className={menuItemCls} style={{ color: A.text1 }} onMouseEnter={e => e.currentTarget.style.background = '#F5F5F0'} onMouseLeave={e => e.currentTarget.style.background = ''}>
                <RefreshCw className="w-3.5 h-3.5" style={{ color: A.text3 }} /> Re-Authorize
              </button>
              <button onClick={() => { setShowActionsPopup(false); runStaggered('Revoke Sessions', () => telegramOutreachApi.bulkRevokeSessions(ids)); }} className={menuItemCls} style={{ color: A.text1 }} onMouseEnter={e => e.currentTarget.style.background = '#F5F5F0'} onMouseLeave={e => e.currentTarget.style.background = ''}>
                <X className="w-3.5 h-3.5" style={{ color: A.text3 }} /> Revoke Sessions
              </button>
              <button onClick={() => { setShowActionsPopup(false); run('Cleaned', () => telegramOutreachApi.bulkClean(ids, { delete_dialogs: true, delete_contacts: true })); }} className={menuItemCls} style={{ color: A.text1 }} onMouseEnter={e => e.currentTarget.style.background = '#F5F5F0'} onMouseLeave={e => e.currentTarget.style.background = ''}>
                <Trash2 className="w-3.5 h-3.5" style={{ color: A.text3 }} /> Clean Dialogs
              </button>
            </div>
          </div>
        </ModalBackdrop>,
        document.body
      )}
        {confirmDelete && createPortal(
          <ConfirmModal message={`Delete ${ids.length} accounts?`}
            onConfirm={async () => {
              setConfirmDelete(false); setLoading(true);
              try { for (const id of ids) await telegramOutreachApi.deleteAccount(id);
                    toast(`${ids.length} deleted`, 'success'); onDone();
              } catch { toast('Delete failed', 'error'); } finally { setLoading(false); }
            }}
            onCancel={() => setConfirmDelete(false)} />,
          document.body
        )}

      {/* Expandable panels */}
      {activePanel === 'names' && (
        <div className="flex items-center gap-2 pt-1">
          <span className={cn('text-xs', t.text3)}>Names:</span>
          <select value={nameCategory} onChange={e => setNameCategory(e.target.value)} className={inputCls} style={inputStyle}>
            <option value="male_en">Male (English)</option>
            <option value="female_en">Female (English)</option>
            <option value="male_pt">Male (Portuguese)</option>
            <option value="female_pt">Female (Portuguese)</option>
            <option value="male_ru">Male (Russian)</option>
            <option value="female_ru">Female (Russian)</option>
          </select>
          <button onClick={() => runStaggered('Set Names', () => telegramOutreachApi.bulkRandomizeNames(ids, nameCategory))}
                  disabled={loading} className="px-3 py-1 text-white rounded-md text-[12px] font-medium" style={{ background: A.blue }}>
            {loading ? 'Working...' : `Apply to ${ids.length}`}
          </button>
        </div>
      )}
      {activePanel === 'limit' && (
        <div className="flex items-center gap-2 pt-1">
          <span className={cn('text-xs', t.text3)}>Daily limit:</span>
          <input type="number" value={limitValue} onChange={e => setLimitValue(e.target.value)} className={cn(inputCls, 'w-20')} />
          <button onClick={() => run('Limit set', () => telegramOutreachApi.bulkSetLimit(ids, Number(limitValue)))}
                  disabled={loading} className="px-3 py-1 text-white rounded-md text-[12px] font-medium" style={{ background: A.blue }}>Apply</button>
        </div>
      )}
      {activePanel === 'bio' && (
        <div className="flex items-center gap-2 pt-1">
          <span className={cn('text-xs', t.text3)}>Bio:</span>
          <input type="text" value={bioValue} onChange={e => setBioValue(e.target.value)}
                 placeholder="BDM at Company" className={cn(inputCls, 'flex-1')} />
          <button onClick={() => runStaggered('Set Bio', () => telegramOutreachApi.bulkSetBio(ids, bioValue))}
                  disabled={loading || !bioValue} className="px-3 py-1 text-white rounded-md text-[12px] font-medium" style={{ background: A.blue }}>Apply</button>
        </div>
      )}
      {activePanel === '2fa' && (
        <div className="flex items-center gap-2 pt-1">
          <span className={cn('text-xs', t.text3)}>2FA password:</span>
          <input type="text" value={twoFaValue} onChange={e => setTwoFaValue(e.target.value)}
                 className={cn(inputCls, 'w-40')} />
          <button onClick={() => runStaggered('Change 2FA', () => telegramOutreachApi.bulkSet2FA(ids, twoFaValue))}
                  disabled={loading || !twoFaValue} className="px-3 py-1 text-white rounded-md text-[12px] font-medium" style={{ background: A.blue }}>Apply</button>
        </div>
      )}
      {activePanel === 'lang' && (
        <div className="flex items-center gap-2 pt-1">
          <span className={cn('text-xs', t.text3)}>Lang:</span>
          <select value={langCode} onChange={e => setLangCode(e.target.value)} className={inputCls} style={inputStyle}>
            {['en','pt','es','de','fr','it','nl','ru'].map(l => <option key={l}>{l}</option>)}
          </select>
          <select value={sysLangCode} onChange={e => setSysLangCode(e.target.value)} className={inputCls} style={inputStyle}>
            {['en-US','pt-PT','es-ES','de-DE','fr-FR','it-IT','nl-NL','ru-RU'].map(l => <option key={l}>{l}</option>)}
          </select>
          <button onClick={() => run('Language set', () => telegramOutreachApi.bulkUpdateParams(ids, { lang_code: langCode, system_lang_code: sysLangCode }))}
                  disabled={loading} className="px-3 py-1 text-white rounded-md text-[12px] font-medium" style={{ background: A.blue }}>Apply</button>
        </div>
      )}
      {activePanel === 'appversion' && <AppVersionPanel ids={ids} loading={loading} run={run} inputCls={inputCls} inputStyle={inputStyle} />}
      {activePanel === 'photo' && (
        <div className="pt-2">
          <div
            onClick={() => photoInputRef.current?.click()}
            onDragOver={e => { e.preventDefault(); e.currentTarget.style.borderColor = A.blue; }}
            onDragLeave={e => { e.preventDefault(); e.currentTarget.style.borderColor = A.border; }}
            onDrop={e => { e.preventDefault(); e.currentTarget.style.borderColor = A.border;
              if (e.dataTransfer.files.length) setPhotoFiles(prev => [...prev, ...Array.from(e.dataTransfer.files)]); }}
            style={{ border: `2px dashed ${A.border}`, borderRadius: 10, padding: '16px 20px', textAlign: 'center', cursor: 'pointer', transition: 'border-color 0.2s' }}>
            <Upload className="w-6 h-6 mx-auto mb-1" style={{ color: A.text3 }} />
            <p style={{ fontSize: 12, color: A.text1, fontWeight: 500 }}>
              {photoFiles.length > 0 ? `${photoFiles.length} photo(s) selected` : 'Click or drag photos here'}
            </p>
            <p style={{ fontSize: 11, color: A.text3, marginTop: 2 }}>Photos will be distributed randomly across {ids.length} accounts</p>
          </div>
          <input ref={photoInputRef} type="file" accept="image/*" multiple className="hidden"
                 onChange={e => { if (e.target.files) setPhotoFiles(prev => [...prev, ...Array.from(e.target.files!)]); e.target.value = ''; }} />
          {photoFiles.length > 0 && (
            <div className="flex items-center gap-2 mt-2">
              <button onClick={() => { runStaggered('Set Photo', () => telegramOutreachApi.bulkSetPhoto(ids, photoFiles).then(res => { setPhotoFiles([]); return res; })); }} disabled={loading} className="px-3 py-1.5 rounded-lg text-[12px] font-medium text-white disabled:opacity-40" style={{ background: A.blue }}>
                {loading ? 'Uploading...' : `Apply ${photoFiles.length} photo(s)`}
              </button>
              <button onClick={() => setPhotoFiles([])} style={{ fontSize: 12, color: A.text3, background: 'none', border: 'none', cursor: 'pointer' }}>Clear</button>
            </div>
          )}
        </div>
      )}
      {activePanel === 'device' && (
        <div className="flex items-center gap-2 pt-1">
          <span style={{ fontSize: 12, color: A.text3 }}>Device:</span>
          <button onClick={() => run('Device randomized', () => telegramOutreachApi.bulkRandomizeDevice(ids))}
                  disabled={loading}
                  className="px-3 py-1.5 rounded-lg text-[12px] font-medium disabled:opacity-40"
                  style={{ background: A.blue, color: '#fff' }}>
            {loading ? 'Working...' : 'Randomize'}
          </button>
          <span style={{ fontSize: 11, color: A.text3 }}>Assigns random model, version, app to {ids.length} account(s)</span>
        </div>
      )}
      {activePanel === 'proxy' && (() => {
        const selectedGroup = proxyGroups.find(g => g.id === proxyGroupId);
        return (
        <div className="flex items-center gap-2 pt-1">
          <span style={{ fontSize: 12, color: A.text3 }}>Proxy group:</span>
          <div style={{ position: 'relative' }}>
            <button onClick={e => { e.stopPropagation(); setProxyDropdownOpen(!proxyDropdownOpen); }}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px', borderRadius: 8, border: `1px solid ${A.border}`, background: A.surface, fontSize: 12, color: selectedGroup ? A.text1 : A.text3, cursor: 'pointer', minWidth: 160 }}>
              <span className="flex-1 text-left truncate">{selectedGroup ? `${selectedGroup.name} (${selectedGroup.proxies_count})` : 'Select group...'}</span>
              <ChevronDown className="w-3 h-3 flex-shrink-0" style={{ color: A.text3 }} />
            </button>
            {proxyDropdownOpen && (
              <div style={{ position: 'absolute', bottom: '100%', left: 0, marginBottom: 4, width: 220, borderRadius: 10, border: `1px solid ${A.border}`, background: A.surface, boxShadow: '0 4px 12px rgba(0,0,0,0.08)', zIndex: 50, padding: '4px 0', maxHeight: 200, overflowY: 'auto' }}>
                {proxyGroups.length === 0 ? (
                  <div style={{ padding: '8px 12px', fontSize: 12, color: A.text3 }}>No proxy groups</div>
                ) : proxyGroups.map(g => (
                  <button key={g.id} onClick={() => { setProxyGroupId(g.id); setProxyDropdownOpen(false); }}
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', padding: '7px 12px', fontSize: 12, color: proxyGroupId === g.id ? A.blue : A.text1, background: proxyGroupId === g.id ? A.blueBg : 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left' }}
                    onMouseEnter={e => { if (proxyGroupId !== g.id) e.currentTarget.style.background = '#F5F5F0'; }}
                    onMouseLeave={e => { if (proxyGroupId !== g.id) e.currentTarget.style.background = ''; }}>
                    <span>{g.name}</span>
                    <span style={{ color: A.text3, fontSize: 11 }}>{g.proxies_count}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <button onClick={() => { if (!proxyGroupId) return; run('Proxy assigned', () => telegramOutreachApi.bulkAssignProxy(ids, proxyGroupId as number)); }}
                  disabled={loading || !proxyGroupId}
                  className="px-3 py-1.5 text-white rounded-lg text-[12px] font-medium disabled:opacity-40"
                  style={{ background: A.blue }}>Apply</button>
        </div>
        );
      })()}
      {activePanel === 'privacy' && (
        <div className="flex items-center gap-2 pt-1 flex-wrap">
          <span className={cn('text-xs', t.text3)}>Privacy:</span>
          {[
            { key: 'last_online', label: 'Last Online' },
            { key: 'phone_visibility', label: 'Phone' },
            { key: 'profile_pic_visibility', label: 'Photo' },
            { key: 'private_messages', label: 'Messages' },
          ].map(p => (
            <select key={p.key} title={p.label}
                    className={cn(inputCls, 'w-auto')}
                    defaultValue=""
                    onChange={e => {
                      if (e.target.value) runStaggered(`Privacy: ${p.label}`, () => telegramOutreachApi.bulkUpdatePrivacy(ids, { [p.key]: e.target.value }));
                    }}>
              <option value="">{p.label}</option>
              <option value="everyone">Everyone</option>
              <option value="contacts">Contacts</option>
              <option value="nobody">Nobody</option>
            </select>
          ))}
        </div>
      )}
      {activePanel === 'warmup-settings' && (
        <div className="pt-2 pb-1 space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold" style={{ color: '#059669' }}>Warm-up Settings</span>
            <span title="Active warm-up simulates real user activity over 14 days: joins channels, adds reactions, exchanges messages. Gradual limit increases daily sending cap for new accounts.">
              <Info className="w-3 h-3 cursor-help" style={{ color: '#059669' }} />
            </span>
          </div>
          {/* Start / Stop */}
          <div className="flex items-center gap-2">
            <button onClick={() => run('Active warm-up started', () => telegramOutreachApi.bulkWarmup(ids, 'start'))}
                    disabled={loading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium text-white"
                    style={{ background: '#059669' }}>
              <Play className="w-3 h-3" /> Start Warm-up
            </button>
            <button onClick={() => run('Active warm-up stopped', () => telegramOutreachApi.bulkWarmup(ids, 'stop'))}
                    disabled={loading}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-medium"
                    style={{ background: A.roseBg, color: A.rose }}>
              <Square className="w-3 h-3" /> Stop Warm-up
            </button>
          </div>
          {/* Gradual limit increase toggle */}
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-1.5">
              <span className="text-xs" style={{ color: A.text1 }}>Gradual daily limit increase</span>
              <span title="Day 1 = 2 msgs, Day 2 = 4, Day 3 = 6, etc. Accounts under 7 days are capped at 5 msgs/day. Disabling removes all limits — use with caution on new sessions.">
                <Info className="w-3 h-3 cursor-help" style={{ color: A.text3 }} />
              </span>
            </div>
            <div className="flex gap-1.5">
              <button onClick={() => run('Gradual limit enabled', () => telegramOutreachApi.bulkSkipWarmup(ids, false))}
                      disabled={loading}
                      className="px-2.5 py-1 rounded text-[11px] font-medium"
                      style={{ background: '#ECFDF5', color: '#059669', border: '1px solid #BBF7D0' }}>
                Enable
              </button>
              <button onClick={() => { if (!window.confirm(`⚠ Disable gradual limit for ${ids.length} accounts?\nNew accounts without warm-up risk getting banned.`)) return; run('Gradual limit disabled', () => telegramOutreachApi.bulkSkipWarmup(ids, true)); }}
                      disabled={loading}
                      className="px-2.5 py-1 rounded text-[11px] font-medium"
                      style={{ background: A.roseBg, color: A.rose, border: `1px solid ${A.rose}30` }}>
                Disable
              </button>
            </div>
          </div>
          {/* Manage Channels */}
          <div style={{ height: 1, background: A.border }} />
          <WarmupChannelsPanel />
        </div>
      )}

      {/* Staggered operation progress banner */}
      {staggeredTask && (
        <div className="mt-2 rounded-lg px-4 py-2.5" style={{ background: staggeredTask.status === 'completed' ? '#F0FDF4' : '#FFFBEB', border: `1px solid ${staggeredTask.status === 'completed' ? '#BBF7D0' : '#FDE68A'}` }}>
          <div className="flex items-center gap-3">
            {staggeredTask.status === 'running' && <Loader2 className="w-4 h-4 animate-spin" style={{ color: '#D97706' }} />}
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="text-[12px] font-semibold" style={{ color: staggeredTask.status === 'completed' ? '#16A34A' : '#D97706' }}>
                  {staggeredTask.status === 'completed' ? 'Completed' : 'Syncing to Telegram...'}: {staggeredTask.operation}
                </span>
                <span className="text-[11px]" style={{ color: A.text3 }}>
                  {staggeredTask.completed}/{staggeredTask.total} accounts
                  {staggeredTask.synced > 0 && ` (${staggeredTask.synced} synced)`}
                  {staggeredTask.errors.length > 0 && ` · ${staggeredTask.errors.length} errors`}
                </span>
              </div>
              {staggeredTask.status === 'running' && staggeredTask.currentPhone && (
                <div className="text-[11px] mt-0.5" style={{ color: A.text3 }}>
                  Current: {staggeredTask.currentPhone}
                  {staggeredTask.nextDelay > 0 && ` · waiting ${staggeredTask.nextDelay}s before next...`}
                </div>
              )}
            </div>
            {/* Progress bar */}
            <div className="w-24 h-1.5 rounded-full" style={{ background: A.border }}>
              <div className="h-full rounded-full transition-all" style={{ width: `${staggeredTask.total > 0 ? (staggeredTask.completed / staggeredTask.total) * 100 : 0}%`, background: staggeredTask.status === 'completed' ? '#16A34A' : '#D97706' }} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


function WarmupChannelsPanel() {
  const toastCtx = useToast();
  const toast = useCallback((msg: string, type: 'success' | 'error' | 'info' = 'info') => {
    toastCtx[type](msg);
  }, [toastCtx]);
  const [channels, setChannels] = useState<{ id: number; url: string; title: string | null; is_active: boolean }[]>([]);
  const [newUrl, setNewUrl] = useState('');
  const [newTitle, setNewTitle] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await telegramOutreachApi.getWarmupChannels();
      setChannels(data);
    } catch { toast('Failed to load channels', 'error'); }
  }, [toast]);

  useEffect(() => { load(); }, [load]);

  const add = async () => {
    const url = newUrl.trim();
    if (!url) return;
    setLoading(true);
    try {
      await telegramOutreachApi.addWarmupChannel(url, newTitle.trim() || undefined);
      setNewUrl(''); setNewTitle('');
      await load();
      toast('Channel added', 'success');
    } catch { toast('Failed to add channel', 'error'); }
    setLoading(false);
  };

  const remove = async (id: number) => {
    try {
      await telegramOutreachApi.deleteWarmupChannel(id);
      setChannels(ch => ch.filter(c => c.id !== id));
      toast('Channel removed', 'success');
    } catch { toast('Failed to remove', 'error'); }
  };

  const toggle = async (id: number, active: boolean) => {
    try {
      await telegramOutreachApi.toggleWarmupChannel(id, active);
      setChannels(ch => ch.map(c => c.id === id ? { ...c, is_active: active } : c));
    } catch { toast('Failed to toggle', 'error'); }
  };

  const seed = async () => {
    setLoading(true);
    try {
      const r = await telegramOutreachApi.seedWarmupChannels();
      await load();
      toast(`Seeded ${r.added} channels`, 'success');
    } catch { toast('Failed to seed', 'error'); }
    setLoading(false);
  };

  const inputCls = 'rounded px-2 py-1 text-xs border outline-none';
  const inputStyle = { background: A.bg, color: A.text1, borderColor: A.border };

  return (
    <div className="pt-2 pb-1">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold" style={{ color: '#059669' }}>Warm-up Channels</span>
        <button onClick={seed} disabled={loading} className="text-[10px] px-2 py-0.5 rounded" style={{ background: A.border, color: A.text2 }}>
          Seed defaults
        </button>
      </div>
      {channels.length === 0 ? (
        <div className="text-xs py-2" style={{ color: A.text3 }}>No channels configured. Click "Seed defaults" to add recommended channels.</div>
      ) : (
        <div className="flex flex-col gap-1 mb-2">
          {channels.map(ch => (
            <div key={ch.id} className="flex items-center gap-2 px-2 py-1 rounded text-xs" style={{ background: A.bg, border: `1px solid ${A.border}` }}>
              <button onClick={() => toggle(ch.id, !ch.is_active)} className="w-4 h-4 flex items-center justify-center rounded" style={{ background: ch.is_active ? '#059669' : A.border }} title={ch.is_active ? 'Active' : 'Inactive'}>
                {ch.is_active && <Check className="w-3 h-3 text-white" />}
              </button>
              <span className="flex-1 truncate" style={{ color: ch.is_active ? A.text1 : A.text3 }}>
                {ch.url.startsWith('+') ? `t.me/${ch.url}` : `@${ch.url}`}
                {ch.title && <span style={{ color: A.text3 }}> — {ch.title}</span>}
              </span>
              <button onClick={() => remove(ch.id)} className="opacity-50 hover:opacity-100" title="Remove">
                <X className="w-3 h-3" style={{ color: '#dc2626' }} />
              </button>
            </div>
          ))}
        </div>
      )}
      <div className="flex items-center gap-1">
        <input value={newUrl} onChange={e => setNewUrl(e.target.value)} placeholder="Channel URL or @username" className={inputCls} style={{ ...inputStyle, flex: 1 }} onKeyDown={e => e.key === 'Enter' && add()} />
        <input value={newTitle} onChange={e => setNewTitle(e.target.value)} placeholder="Title (optional)" className={inputCls} style={{ ...inputStyle, width: 120 }} onKeyDown={e => e.key === 'Enter' && add()} />
        <button onClick={add} disabled={loading || !newUrl.trim()} className="px-2 py-1 rounded text-xs font-medium text-white" style={{ background: !newUrl.trim() ? A.border : '#059669' }}>
          <Plus className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}


function ModalBackdrop({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative z-10 max-h-[90vh] overflow-y-auto">
        {children}
      </div>
    </div>
  );
}

function ConfirmModal({ message, onConfirm, onCancel }: { message: string; onConfirm: () => void; onCancel: () => void }) {
  return (
    <ModalBackdrop onClose={onCancel}>
      <div className="w-[360px] rounded-xl border shadow-xl" style={{ borderColor: A.border, background: A.surface }}>
        <div className="px-5 py-4">
          <h3 className="text-sm font-semibold mb-1" style={{ color: A.text1 }}>Confirm</h3>
          <p className="text-xs" style={{ color: A.text2, lineHeight: '1.5' }}>{message}</p>
        </div>
        <div className="px-5 py-3 flex justify-end gap-2" style={{ borderTop: `1px solid ${A.border}` }}>
          <button onClick={onCancel}
            className="px-4 py-1.5 rounded-lg text-xs font-medium transition-colors"
            style={{ border: `1px solid ${A.border}`, color: A.text1, background: A.surface, cursor: 'pointer' }}
            onMouseEnter={e => { e.currentTarget.style.background = '#F3F4F6'; }}
            onMouseLeave={e => { e.currentTarget.style.background = A.surface; }}>
            Cancel
          </button>
          <button onClick={onConfirm}
            className="px-4 py-1.5 rounded-lg text-xs font-medium text-white transition-colors"
            style={{ background: '#E11D48', border: 'none', cursor: 'pointer' }}
            onMouseEnter={e => { e.currentTarget.style.background = '#BE123C'; }}
            onMouseLeave={e => { e.currentTarget.style.background = '#E11D48'; }}>
            Delete
          </button>
        </div>
      </div>
    </ModalBackdrop>
  );
}



// ══════════════════════════════════════════════════════════════════════
// Add by Phone Modal (multi-step auth wizard)
// ══════════════════════════════════════════════════════════════════════

const PHONE_COUNTRIES = [
  { code: '1', flag: '\u{1F1FA}\u{1F1F8}', name: 'United States' },
  { code: '44', flag: '\u{1F1EC}\u{1F1E7}', name: 'United Kingdom' },
  { code: '49', flag: '\u{1F1E9}\u{1F1EA}', name: 'Germany' },
  { code: '33', flag: '\u{1F1EB}\u{1F1F7}', name: 'France' },
  { code: '351', flag: '\u{1F1F5}\u{1F1F9}', name: 'Portugal' },
  { code: '34', flag: '\u{1F1EA}\u{1F1F8}', name: 'Spain' },
  { code: '39', flag: '\u{1F1EE}\u{1F1F9}', name: 'Italy' },
  { code: '31', flag: '\u{1F1F3}\u{1F1F1}', name: 'Netherlands' },
  { code: '47', flag: '\u{1F1F3}\u{1F1F4}', name: 'Norway' },
  { code: '46', flag: '\u{1F1F8}\u{1F1EA}', name: 'Sweden' },
  { code: '45', flag: '\u{1F1E9}\u{1F1F0}', name: 'Denmark' },
  { code: '358', flag: '\u{1F1EB}\u{1F1EE}', name: 'Finland' },
  { code: '7', flag: '\u{1F1F7}\u{1F1FA}', name: 'Russia' },
  { code: '380', flag: '\u{1F1FA}\u{1F1E6}', name: 'Ukraine' },
  { code: '375', flag: '\u{1F1E7}\u{1F1FE}', name: 'Belarus' },
  { code: '48', flag: '\u{1F1F5}\u{1F1F1}', name: 'Poland' },
  { code: '420', flag: '\u{1F1E8}\u{1F1FF}', name: 'Czechia' },
  { code: '43', flag: '\u{1F1E6}\u{1F1F9}', name: 'Austria' },
  { code: '41', flag: '\u{1F1E8}\u{1F1ED}', name: 'Switzerland' },
  { code: '90', flag: '\u{1F1F9}\u{1F1F7}', name: 'Turkey' },
  { code: '971', flag: '\u{1F1E6}\u{1F1EA}', name: 'UAE' },
  { code: '966', flag: '\u{1F1F8}\u{1F1E6}', name: 'Saudi Arabia' },
  { code: '91', flag: '\u{1F1EE}\u{1F1F3}', name: 'India' },
  { code: '86', flag: '\u{1F1E8}\u{1F1F3}', name: 'China' },
  { code: '82', flag: '\u{1F1F0}\u{1F1F7}', name: 'South Korea' },
  { code: '81', flag: '\u{1F1EF}\u{1F1F5}', name: 'Japan' },
  { code: '65', flag: '\u{1F1F8}\u{1F1EC}', name: 'Singapore' },
  { code: '60', flag: '\u{1F1F2}\u{1F1FE}', name: 'Malaysia' },
  { code: '62', flag: '\u{1F1EE}\u{1F1E9}', name: 'Indonesia' },
  { code: '55', flag: '\u{1F1E7}\u{1F1F7}', name: 'Brazil' },
  { code: '52', flag: '\u{1F1F2}\u{1F1FD}', name: 'Mexico' },
  { code: '234', flag: '\u{1F1F3}\u{1F1EC}', name: 'Nigeria' },
  { code: '27', flag: '\u{1F1FF}\u{1F1E6}', name: 'South Africa' },
  { code: '61', flag: '\u{1F1E6}\u{1F1FA}', name: 'Australia' },
  { code: '64', flag: '\u{1F1F3}\u{1F1FF}', name: 'New Zealand' },
  { code: '1', flag: '\u{1F1E8}\u{1F1E6}', name: 'Canada' },
  { code: '972', flag: '\u{1F1EE}\u{1F1F1}', name: 'Israel' },
  { code: '998', flag: '\u{1F1FA}\u{1F1FF}', name: 'Uzbekistan' },
  { code: '995', flag: '\u{1F1EC}\u{1F1EA}', name: 'Georgia' },
  { code: '374', flag: '\u{1F1E6}\u{1F1F2}', name: 'Armenia' },
  { code: '994', flag: '\u{1F1E6}\u{1F1FF}', name: 'Azerbaijan' },
  { code: '370', flag: '\u{1F1F1}\u{1F1F9}', name: 'Lithuania' },
  { code: '371', flag: '\u{1F1F1}\u{1F1FB}', name: 'Latvia' },
  { code: '372', flag: '\u{1F1EA}\u{1F1EA}', name: 'Estonia' },
  { code: '353', flag: '\u{1F1EE}\u{1F1EA}', name: 'Ireland' },
  { code: '32', flag: '\u{1F1E7}\u{1F1EA}', name: 'Belgium' },
  { code: '30', flag: '\u{1F1EC}\u{1F1F7}', name: 'Greece' },
  { code: '36', flag: '\u{1F1ED}\u{1F1FA}', name: 'Hungary' },
  { code: '40', flag: '\u{1F1F7}\u{1F1F4}', name: 'Romania' },
  { code: '359', flag: '\u{1F1E7}\u{1F1EC}', name: 'Bulgaria' },
  { code: '385', flag: '\u{1F1ED}\u{1F1F7}', name: 'Croatia' },
  { code: '381', flag: '\u{1F1F7}\u{1F1F8}', name: 'Serbia' },
  { code: '66', flag: '\u{1F1F9}\u{1F1ED}', name: 'Thailand' },
  { code: '63', flag: '\u{1F1F5}\u{1F1ED}', name: 'Philippines' },
  { code: '84', flag: '\u{1F1FB}\u{1F1F3}', name: 'Vietnam' },
  { code: '880', flag: '\u{1F1E7}\u{1F1E9}', name: 'Bangladesh' },
  { code: '92', flag: '\u{1F1F5}\u{1F1F0}', name: 'Pakistan' },
  { code: '20', flag: '\u{1F1EA}\u{1F1EC}', name: 'Egypt' },
  { code: '212', flag: '\u{1F1F2}\u{1F1E6}', name: 'Morocco' },
  { code: '254', flag: '\u{1F1F0}\u{1F1EA}', name: 'Kenya' },
  { code: '57', flag: '\u{1F1E8}\u{1F1F4}', name: 'Colombia' },
  { code: '54', flag: '\u{1F1E6}\u{1F1F7}', name: 'Argentina' },
  { code: '56', flag: '\u{1F1E8}\u{1F1F1}', name: 'Chile' },
  { code: '51', flag: '\u{1F1F5}\u{1F1EA}', name: 'Peru' },
];

function detectCountryFromDigits(digits: string): { country: typeof PHONE_COUNTRIES[number]; rest: string } | null {
  // Try longest codes first (3 digits, then 2, then 1)
  for (const len of [3, 2, 1]) {
    if (digits.length < len) continue;
    const prefix = digits.slice(0, len);
    const match = PHONE_COUNTRIES.find(c => c.code === prefix);
    if (match) return { country: match, rest: digits.slice(len) };
  }
  return null;
}

function AddByPhoneModal({ t, toast, isDark, onClose, onSaved }: {
  t: any; toast: any; isDark: boolean; onClose: () => void; onSaved: () => void;
}) {
  const [step, setStep] = useState<'phone' | 'code' | '2fa' | 'done'>('phone');
  const [phone, setPhone] = useState('');
  const [selectedCountry, setSelectedCountry] = useState(PHONE_COUNTRIES[0]);
  const [showCountryDD, setShowCountryDD] = useState(false);
  const [countrySearch, setCountrySearch] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [accountId, setAccountId] = useState<number | null>(null);
  const [deviceModel, setDeviceModel] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const codeRef = useRef<HTMLInputElement>(null);
  const phoneRef = useRef<HTMLInputElement>(null);
  const countryDDRef = useRef<HTMLDivElement>(null);
  const countrySearchRef = useRef<HTMLInputElement>(null);

  const fullNumber = selectedCountry.code + phone.replace(/[^0-9]/g, '');

  const inputCls = cn('w-full px-3 py-2.5 rounded-lg border text-sm transition-colors', t.cardBg, t.text1,
    'border-gray-200 dark:border-gray-700 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 outline-none');
  const labelCls = cn('block text-xs font-medium mb-1.5', t.text3);

  // Close country dropdown on outside click
  useEffect(() => {
    if (!showCountryDD) return;
    const handler = (e: MouseEvent) => {
      if (countryDDRef.current && !countryDDRef.current.contains(e.target as Node)) setShowCountryDD(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showCountryDD]);

  // Focus search when dropdown opens
  useEffect(() => {
    if (showCountryDD) setTimeout(() => countrySearchRef.current?.focus(), 50);
  }, [showCountryDD]);

  const handlePhoneInput = (val: string) => {
    const raw = val.replace(/[^0-9+]/g, '');
    // If pasted with + prefix, try to auto-detect country
    if (raw.startsWith('+') || (raw.length > 7 && phone.length === 0)) {
      const digits = raw.replace(/\D/g, '');
      const detected = detectCountryFromDigits(digits);
      if (detected) {
        setSelectedCountry(detected.country);
        setPhone(detected.rest);
        return;
      }
    }
    setPhone(raw.replace(/^\+/, ''));
  };

  const filteredCountries = countrySearch
    ? PHONE_COUNTRIES.filter(c => c.name.toLowerCase().includes(countrySearch.toLowerCase()) || c.code.includes(countrySearch))
    : PHONE_COUNTRIES;

  const handleSendCode = async () => {
    const cleaned = fullNumber.replace(/[^0-9]/g, '');
    if (!cleaned || cleaned.length < 7) { setError('Enter a valid phone number'); return; }
    setLoading(true); setError('');
    try {
      const res = await telegramOutreachApi.addByPhone(cleaned);
      setAccountId(res.account_id);
      setDeviceModel(res.device_model);
      if (res.status === 'already_authorized') {
        setStep('done');
        toast('Account authorized', 'success');
      } else {
        setStep('code');
        setTimeout(() => codeRef.current?.focus(), 100);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to send code');
    } finally { setLoading(false); }
  };

  const handleVerifyCode = async () => {
    if (!code.trim() || !accountId) return;
    setLoading(true); setError('');
    try {
      const res = await telegramOutreachApi.authVerifyCode(accountId, code.trim());
      if (res.status === 'authorized') {
        setStep('done');
        toast('Account authorized', 'success');
      } else if (res.status === '2fa_required') {
        setStep('2fa');
      } else if (res.status === 'error') {
        setError(res.detail || 'Verification failed');
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to verify code');
    } finally { setLoading(false); }
  };

  const handleVerify2FA = async () => {
    if (!password.trim() || !accountId) return;
    setLoading(true); setError('');
    try {
      const res = await telegramOutreachApi.authVerify2FA(accountId, password.trim());
      if (res.status === 'authorized') {
        setStep('done');
        toast('Account authorized', 'success');
      } else if (res.status === 'error') {
        setError(res.detail || '2FA verification failed');
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Wrong 2FA password');
    } finally { setLoading(false); }
  };

  const stepTitles = { phone: 'Add Account by Phone', code: 'Enter Verification Code', '2fa': 'Two-Factor Authentication', done: 'Account Added' };
  const stepNumber = { phone: 1, code: 2, '2fa': 3, done: step === 'done' ? 3 : 4 };

  return (
    <ModalBackdrop onClose={step === 'done' ? () => onSaved() : onClose}>
      <div className={cn('w-[440px] rounded-xl border shadow-xl', t.cardBorder, isDark ? 'bg-gray-900' : 'bg-white')}>
        {/* Header */}
        <div className={cn('flex items-center justify-between px-6 py-4 border-b', t.cardBorder)}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: '#059669' }}>
              {step === 'done'
                ? <Check className="w-4 h-4 text-white" />
                : <Phone className="w-4 h-4 text-white" />}
            </div>
            <div>
              <h2 className={cn('text-[15px] font-semibold', t.text1)}>{stepTitles[step]}</h2>
              {step !== 'done' && (
                <div className={cn('text-[11px]', t.text3)}>Step {stepNumber[step]} of 3</div>
              )}
            </div>
          </div>
          <button onClick={step === 'done' ? () => onSaved() : onClose}
            className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5">
          {step === 'phone' && (
            <div className="space-y-4">
              <div>
                <label className={labelCls}>Phone Number</label>
                <div className="flex items-stretch gap-0 relative">
                  {/* Country selector button */}
                  <div ref={countryDDRef} className="relative">
                    <button type="button"
                      onClick={() => { setShowCountryDD(!showCountryDD); setCountrySearch(''); }}
                      className={cn('flex items-center gap-1.5 px-3 py-2.5 rounded-l-lg border border-r-0 text-sm transition-colors h-full',
                        isDark ? 'bg-gray-800 border-gray-700 hover:bg-gray-750' : 'bg-gray-50 border-gray-200 hover:bg-gray-100',
                        showCountryDD && 'border-emerald-500 ring-2 ring-emerald-500/20')}>
                      <span className="text-base leading-none">{selectedCountry.flag}</span>
                      <span className={cn('text-sm font-medium', t.text1)}>+{selectedCountry.code}</span>
                      <ChevronDown className="w-3 h-3 opacity-40" />
                    </button>
                    {/* Country dropdown */}
                    {showCountryDD && (
                      <div className={cn('absolute top-full left-0 mt-1 w-64 rounded-lg border shadow-xl z-50 overflow-hidden',
                        t.cardBorder, isDark ? 'bg-gray-900' : 'bg-white')}>
                        <div className="p-2 border-b" style={{ borderColor: isDark ? '#374151' : '#E5E7EB' }}>
                          <input ref={countrySearchRef} value={countrySearch}
                            onChange={e => setCountrySearch(e.target.value)}
                            placeholder="Search country..."
                            className={cn('w-full px-2.5 py-1.5 rounded text-sm outline-none', t.cardBg, t.text1,
                              'border border-gray-200 dark:border-gray-700 focus:border-emerald-500')} />
                        </div>
                        <div className="max-h-52 overflow-y-auto">
                          {filteredCountries.map((c, i) => (
                            <button key={`${c.code}-${c.name}-${i}`} type="button"
                              onClick={() => { setSelectedCountry(c); setShowCountryDD(false); setTimeout(() => phoneRef.current?.focus(), 50); }}
                              className={cn('w-full flex items-center gap-2.5 px-3 py-2 text-sm transition-colors',
                                selectedCountry === c
                                  ? (isDark ? 'bg-emerald-900/30 text-emerald-400' : 'bg-emerald-50 text-emerald-700')
                                  : (isDark ? 'hover:bg-gray-800' : 'hover:bg-gray-50'))}>
                              <span className="text-base">{c.flag}</span>
                              <span className={cn('flex-1 text-left', t.text1)}>{c.name}</span>
                              <span className={cn('text-xs', t.text3)}>+{c.code}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  {/* Phone input */}
                  <input ref={phoneRef} value={phone}
                    onChange={e => handlePhoneInput(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSendCode()}
                    placeholder="Phone number"
                    className={cn('flex-1 px-3 py-2.5 rounded-r-lg border text-sm transition-colors outline-none',
                      t.cardBg, t.text1,
                      'border-gray-200 dark:border-gray-700 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20')}
                    autoFocus />
                </div>
                {/* Full number hint */}
                {phone.replace(/[^0-9]/g, '').length > 0 && (
                  <div className={cn('text-[11px] mt-1.5 font-medium')} style={{ color: '#059669' }}>
                    +{fullNumber}
                  </div>
                )}
                {phone.replace(/[^0-9]/g, '').length === 0 && (
                  <div className={cn('text-[11px] mt-1.5', t.text3)}>
                    Select country and enter phone number
                  </div>
                )}
              </div>
              <div className={cn('rounded-lg px-3 py-2.5 text-[12px]', t.text3)}
                style={{ background: isDark ? '#1E293B' : '#F8FAFC' }}>
                <Info className="w-3.5 h-3.5 inline mr-1.5 opacity-60" />
                A unique device fingerprint will be auto-generated. Telegram Desktop credentials are used for best compatibility.
              </div>
            </div>
          )}

          {step === 'code' && (
            <div className="space-y-4">
              <div className={cn('rounded-lg px-3 py-2.5 text-[12px]', t.text3)}
                style={{ background: isDark ? '#1E293B' : '#F0FDF4' }}>
                Code sent to <span className="font-medium" style={{ color: isDark ? '#86EFAC' : '#059669' }}>+{fullNumber}</span>
                {deviceModel && <span className="opacity-60"> (device: {deviceModel})</span>}
              </div>
              <div>
                <label className={labelCls}>Verification Code</label>
                <input ref={codeRef} value={code}
                  onChange={e => setCode(e.target.value.replace(/[^0-9]/g, ''))}
                  onKeyDown={e => e.key === 'Enter' && handleVerifyCode()}
                  placeholder="12345"
                  maxLength={6} className={cn(inputCls, 'text-center text-lg tracking-[0.3em] font-mono')} />
                <div className={cn('text-[11px] mt-1.5', t.text3)}>
                  Check your Telegram app or SMS for the code
                </div>
              </div>
            </div>
          )}

          {step === '2fa' && (
            <div className="space-y-4">
              <div className={cn('rounded-lg px-3 py-2.5 text-[12px]', t.text3)}
                style={{ background: isDark ? '#1E293B' : '#FFFBEB' }}>
                <Shield className="w-3.5 h-3.5 inline mr-1.5 opacity-60" />
                This account has two-factor authentication enabled
              </div>
              <div>
                <label className={labelCls}>2FA Password</label>
                <input value={password}
                  onChange={e => setPassword(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleVerify2FA()}
                  type="password" placeholder="Enter your cloud password"
                  className={inputCls} autoFocus />
              </div>
            </div>
          )}

          {step === 'done' && (
            <div className="text-center py-4 space-y-3">
              <div className="w-12 h-12 rounded-full mx-auto flex items-center justify-center" style={{ background: '#ECFDF5' }}>
                <Check className="w-6 h-6" style={{ color: '#059669' }} />
              </div>
              <div className={cn('text-sm font-medium', t.text1)}>Account successfully authorized</div>
              <div className={cn('text-xs', t.text3)}>
                +{fullNumber} is ready to use
                {deviceModel && <> with device fingerprint <span className="font-mono text-[11px]">{deviceModel}</span></>}
              </div>
            </div>
          )}

          {error && (
            <div className="mt-3 rounded-lg px-3 py-2 text-[12px] font-medium"
              style={{ background: '#FEF2F2', color: '#DC2626' }}>
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className={cn('flex items-center justify-between px-6 py-4 border-t', t.cardBorder)}>
          {/* Step dots */}
          <div className="flex items-center gap-1.5">
            {[1, 2, 3].map(s => (
              <div key={s} className="w-1.5 h-1.5 rounded-full transition-colors"
                style={{ background: s <= stepNumber[step] ? '#059669' : isDark ? '#374151' : '#E5E7EB' }} />
            ))}
          </div>
          <div className="flex items-center gap-2">
            {step !== 'done' && (
              <button onClick={onClose}
                className={cn('px-4 py-2 rounded-lg border text-sm', t.cardBorder, t.text1)}>Cancel</button>
            )}
            {step === 'phone' && (
              <button onClick={handleSendCode} disabled={loading || !phone.trim()}
                className="flex items-center gap-2 px-5 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50">
                {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                Send Code
              </button>
            )}
            {step === 'code' && (
              <button onClick={handleVerifyCode} disabled={loading || code.length < 4}
                className="flex items-center gap-2 px-5 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50">
                {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                Verify
              </button>
            )}
            {step === '2fa' && (
              <button onClick={handleVerify2FA} disabled={loading || !password.trim()}
                className="flex items-center gap-2 px-5 py-2 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50">
                {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                Verify
              </button>
            )}
            {step === 'done' && (
              <button onClick={onSaved}
                className="flex items-center gap-2 px-5 py-2 text-white rounded-lg text-sm font-medium"
                style={{ background: '#059669' }}>
                <Check className="w-4 h-4" /> Done
              </button>
            )}
          </div>
        </div>
      </div>
    </ModalBackdrop>
  );
}


// ══════════════════════════════════════════════════════════════════════
// Add Account Modal
// ══════════════════════════════════════════════════════════════════════

function AddAccountModal({ t, toast, isDark, onClose, onSaved }: {
  t: any; toast: any; isDark: boolean; onClose: () => void; onSaved: () => void;
}) {
  const [form, setForm] = useState({
    phone: '', username: '', first_name: '', last_name: '', bio: '',
    api_id: '', api_hash: '', device_model: 'Samsung SM-G998B', system_version: 'SDK 33',
    app_version: '10.6.2', lang_code: 'en', system_lang_code: 'en-US',
    two_fa_password: '', daily_message_limit: '5', is_premium: false,
  });
  const [saving, setSaving] = useState(false);

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));
  const inputCls = cn('w-full px-3 py-2 rounded-lg border text-sm', t.cardBorder, t.cardBg, t.text1);
  const labelCls = cn('block text-xs font-medium mb-1', t.text3);

  const handleSave = async () => {
    if (!form.phone.trim()) { toast('Phone is required', 'error'); return; }
    setSaving(true);
    try {
      const data: Record<string, any> = { ...form };
      data.api_id = data.api_id ? Number(data.api_id) : null;
      data.daily_message_limit = Number(data.daily_message_limit) || (data.is_premium ? 10 : 5);
      // Remove empty optional fields
      for (const k of ['username', 'first_name', 'last_name', 'bio', 'api_hash', 'two_fa_password']) {
        if (!data[k]) data[k] = null;
      }
      await telegramOutreachApi.createAccount(data);
      toast('Account created', 'success');
      onSaved();
    } catch (e: any) {
      toast(e?.response?.data?.detail || 'Failed to create account', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <ModalBackdrop onClose={onClose}>
      <div className={cn('w-[560px] rounded-xl border shadow-xl', t.cardBorder, isDark ? 'bg-gray-900' : 'bg-white')}>
        {/* Header */}
        <div className={cn('flex items-center justify-between px-6 py-4 border-b', t.cardBorder)}>
          <h2 className={cn('text-lg font-semibold', t.text1)}>Add Account</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-4 space-y-4">
          {/* Identity */}
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className={labelCls}>Phone *</label>
              <input value={form.phone} onChange={e => set('phone', e.target.value)}
                     placeholder="351920619583" className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>First Name</label>
              <input value={form.first_name} onChange={e => set('first_name', e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>Last Name</label>
              <input value={form.last_name} onChange={e => set('last_name', e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>Username</label>
              <input value={form.username} onChange={e => set('username', e.target.value)}
                     placeholder="without @" className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>Daily Message Limit</label>
              <input type="number" value={form.daily_message_limit}
                     onChange={e => set('daily_message_limit', e.target.value)} className={inputCls} />
            </div>
            <div className="col-span-2 rounded-lg px-3 py-2 border" style={{ borderColor: '#E5E7EB' }}>
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-medium" style={{ color: '#9CA3AF' }}>⭐ Premium</span>
                <span className="text-[10px]" style={{ color: '#9CA3AF' }}>Auto-detected after first check</span>
              </div>
            </div>
          </div>

          <div>
            <label className={labelCls}>Bio</label>
            <textarea value={form.bio} onChange={e => set('bio', e.target.value)}
                      rows={2} className={inputCls} />
          </div>

          {/* Technical */}
          <details className="group">
            <summary className={cn('text-xs font-semibold cursor-pointer select-none flex items-center gap-1', t.text3)}>
              <ChevronDown className="w-3.5 h-3.5 transition-transform group-open:rotate-180" />
              Technical Settings
            </summary>
            <div className="grid grid-cols-2 gap-3 mt-3">
              <div>
                <label className={labelCls}>API ID</label>
                <input value={form.api_id} onChange={e => set('api_id', e.target.value)}
                       placeholder="2040" className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>API Hash</label>
                <input value={form.api_hash} onChange={e => set('api_hash', e.target.value)} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>2FA Password</label>
                <input value={form.two_fa_password} onChange={e => set('two_fa_password', e.target.value)} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Device Model</label>
                <input value={form.device_model} onChange={e => set('device_model', e.target.value)} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>System Version</label>
                <input value={form.system_version} onChange={e => set('system_version', e.target.value)} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>App Version</label>
                <input value={form.app_version} onChange={e => set('app_version', e.target.value)} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Lang Code</label>
                <input value={form.lang_code} onChange={e => set('lang_code', e.target.value)} className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>System Lang Code</label>
                <input value={form.system_lang_code} onChange={e => set('system_lang_code', e.target.value)} className={inputCls} />
              </div>
            </div>
          </details>
        </div>

        {/* Footer */}
        <div className={cn('flex items-center justify-end gap-3 px-6 py-4 border-t', t.cardBorder)}>
          <button onClick={onClose}
                  className={cn('px-4 py-2 rounded-lg border text-sm', t.cardBorder, t.text1)}>Cancel</button>
          <button onClick={handleSave} disabled={saving}
                  className="flex items-center gap-2 px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            Create Account
          </button>
        </div>
      </div>
    </ModalBackdrop>
  );
}


// ══════════════════════════════════════════════════════════════════════
// Edit Account Modal
// ══════════════════════════════════════════════════════════════════════

function EditAccountModal({ t: _t, toast, isDark: _isDark, account, onClose, onSaved, onDeleted }: {
  t: any; toast: any; isDark: boolean; account: TgAccount;
  onClose: () => void; onSaved: () => void; onDeleted: () => void;
}) {
  void _t; void _isDark;
  const [form, setForm] = useState({
    username: account.username || '',
    first_name: account.first_name || '',
    last_name: account.last_name || '',
    bio: account.bio || '',
    status: account.status,
    daily_message_limit: String(account.daily_message_limit),
    is_premium: account.is_premium ? 'true' : 'false',
    device_model: account.device_model || '',
    system_version: account.system_version || '',
    app_version: account.app_version || '',
    lang_code: account.lang_code || '',
    system_lang_code: account.system_lang_code || '',
    skip_warmup: account.skip_warmup ? 'true' : 'false',
  });
  const [saving, setSaving] = useState(false);

  // Warmup status state
  const [warmupStatus, setWarmupStatus] = useState<{
    warmup_active: boolean; warmup_day: number | null; total_days: number;
    warmup_started_at: string | null; actions_done: number; actions_today: number;
    recent_actions: { action_type: string; detail: string | null; success: boolean; performed_at: string }[];
  } | null>(null);
  const [showWarmupDebug, setShowWarmupDebug] = useState(false);
  const [warmupLogs, setWarmupLogs] = useState<{ action_type: string; detail: string | null; success: boolean; error_message: string | null; performed_at: string | null }[]>([]);
  const [warmupExpanded, setWarmupExpanded] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let cancelled = false;
    telegramOutreachApi.warmupStatus(account.id).then(data => { if (!cancelled) setWarmupStatus(data); }).catch(() => {});
    return () => { cancelled = true; };
  }, [account.id]);

  const refreshWarmupStatus = useCallback(() => {
    telegramOutreachApi.warmupStatus(account.id).then(setWarmupStatus).catch(() => {});
  }, [account.id]);

  // Username check state
  const [usernameStatus, setUsernameStatus] = useState<'idle' | 'checking' | 'available' | 'taken' | 'invalid' | 'error'>('idle');
  const usernameTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [showUsernamePrompt, setShowUsernamePrompt] = useState(false);
  const [usernameSuggestions, setUsernameSuggestions] = useState<string[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  const checkUsernameAvailability = useCallback(async (uname: string) => {
    if (!uname || uname.length < 5) {
      setUsernameStatus(uname ? 'invalid' : 'idle');
      return;
    }
    setUsernameStatus('checking');
    try {
      const res = await telegramOutreachApi.checkUsername(account.id, uname);
      if (res.status === 'ok') {
        setUsernameStatus(res.available ? 'available' : (res.reason === 'invalid' ? 'invalid' : 'taken'));
      } else {
        setUsernameStatus('error');
      }
    } catch {
      setUsernameStatus('error');
    }
  }, [account.id]);

  const handleUsernameChange = useCallback((value: string) => {
    const clean = value.toLowerCase().replace(/[^a-z0-9_]/g, '');
    setForm(f => ({ ...f, username: clean }));
    setUsernameStatus('idle');
    if (usernameTimerRef.current) clearTimeout(usernameTimerRef.current);
    if (clean && clean !== (account.username || '')) {
      usernameTimerRef.current = setTimeout(() => checkUsernameAvailability(clean), 700);
    }
  }, [account.username, checkUsernameAvailability]);

  const loadSuggestions = useCallback(async (fn: string, ln: string) => {
    setLoadingSuggestions(true);
    try {
      const res = await telegramOutreachApi.suggestUsernames(account.id, fn, ln);
      setUsernameSuggestions(res.suggestions || []);
    } catch {
      setUsernameSuggestions([]);
    } finally {
      setLoadingSuggestions(false);
    }
  }, [account.id]);

  // Telethon state
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState<Record<string, any> | null>(null);
  const [authStep, setAuthStep] = useState<'none' | 'code_sent' | '2fa_required'>('none');
  const [authCode, setAuthCode] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const sessionFileRef = useRef<HTMLInputElement>(null);

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const doSave = async (overrides?: Record<string, any>) => {
    setSaving(true);
    try {
      const data: Record<string, any> = { ...form, ...overrides };
      data.daily_message_limit = Number(data.daily_message_limit) || (account.is_premium ? 10 : 5);
      delete data.is_premium;  // auto-detected via Telethon, not manually editable
      delete data.skip_warmup; // replaced by warmup Start/Stop
      for (const k of ['username', 'first_name', 'last_name', 'bio']) {
        if (!data[k]) data[k] = null;
      }
      await telegramOutreachApi.updateAccount(account.id, data);
      toast('Account updated', 'success');
      onSaved();
    } catch (e: any) {
      toast(e?.response?.data?.detail || 'Failed to update account', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    const nameChanged =
      (form.first_name || '') !== (account.first_name || '') ||
      (form.last_name || '') !== (account.last_name || '');
    const usernameChanged = (form.username || '') !== (account.username || '');

    if (nameChanged && !usernameChanged && (form.first_name || form.last_name)) {
      setShowUsernamePrompt(true);
      loadSuggestions(form.first_name, form.last_name);
      return;
    }
    await doSave();
  };

  const [confirmDeleteAccount, setConfirmDeleteAccount] = useState(false);
  const handleDelete = async () => {
    setConfirmDeleteAccount(true);
  };
  const doDeleteAccount = async () => {
    setConfirmDeleteAccount(false);
    try {
      await telegramOutreachApi.deleteAccount(account.id);
      toast('Account deleted', 'success');
      onDeleted();
    } catch {
      toast('Failed to delete account', 'error');
    }
  };

  const panelInputCls = 'w-full px-3 py-2 rounded-lg text-sm' +
    ' border outline-none focus:ring-2 focus:ring-[#4F6BF0]/20 focus:border-[#4F6BF0]';
  const panelLabelCls = 'block text-xs font-medium mb-1';

  return (
    <div className="fixed inset-0 z-50 flex">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40 transition-opacity" onClick={onClose} />
      {/* Panel */}
      <div
        className="relative ml-auto h-full w-[480px] flex flex-col shadow-2xl overflow-hidden"
        style={{ background: A.surface, animation: 'slideInRight .2s ease-out' }}
      >
        {/* -- Header -- */}
        <div className="flex items-center justify-between px-6 py-5"
             style={{ borderBottom: `1px solid ${A.border}` }}>
          <div>
            <h2 className="text-lg font-semibold" style={{ color: A.text1 }}>Edit Account</h2>
            <p className="text-xs font-mono mt-0.5" style={{ color: A.text3 }}>{account.phone}</p>
          </div>
          <button onClick={onClose}
                  className="p-1.5 rounded-lg transition-colors hover:bg-[#F3F3F1]">
            <X className="w-5 h-5" style={{ color: A.text3 }} />
          </button>
        </div>

        {/* -- Scrollable body -- */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">

          {/* ---- Section: Profile ---- */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: A.text3 }}>Profile</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={panelLabelCls} style={{ color: A.text3 }}>First Name</label>
                <input value={form.first_name} onChange={e => set('first_name', e.target.value)}
                       className={panelInputCls}
                       style={{ background: A.surface, borderColor: A.border, color: A.text1 }} />
              </div>
              <div>
                <label className={panelLabelCls} style={{ color: A.text3 }}>Last Name</label>
                <input value={form.last_name} onChange={e => set('last_name', e.target.value)}
                       className={panelInputCls}
                       style={{ background: A.surface, borderColor: A.border, color: A.text1 }} />
              </div>
              <div>
                <label className={panelLabelCls} style={{ color: A.text3 }}>Username</label>
                <div className="relative">
                  <input value={form.username} onChange={e => handleUsernameChange(e.target.value)}
                         placeholder="username"
                         className={panelInputCls + ' pr-8'}
                         style={{
                           background: A.surface, color: A.text1,
                           borderColor: usernameStatus === 'available' ? '#22c55e'
                             : usernameStatus === 'taken' || usernameStatus === 'invalid' ? '#ef4444'
                             : A.border,
                         }} />
                  <span className="absolute right-2.5 top-1/2 -translate-y-1/2">
                    {usernameStatus === 'checking' && <Loader2 className="w-3.5 h-3.5 animate-spin" style={{ color: A.text3 }} />}
                    {usernameStatus === 'available' && <Check className="w-3.5 h-3.5 text-green-500" />}
                    {usernameStatus === 'taken' && <X className="w-3.5 h-3.5 text-red-500" />}
                    {usernameStatus === 'invalid' && <AlertTriangle className="w-3.5 h-3.5 text-red-500" />}
                  </span>
                </div>
                {usernameStatus === 'taken' && (
                  <p className="text-[10px] mt-0.5 text-red-500">Username is taken</p>
                )}
                {usernameStatus === 'invalid' && form.username && (
                  <p className="text-[10px] mt-0.5 text-red-500">Invalid (min 5 chars, a-z 0-9 _)</p>
                )}
              </div>
              <div>
                <label className={panelLabelCls} style={{ color: A.text3 }}>Status</label>
                <StyledSelect
                  value={form.status}
                  onChange={v => set('status', v)}
                  options={[
                    { value: 'active', label: 'Active' },
                    { value: 'paused', label: 'Paused' },
                    { value: 'spamblocked', label: 'Spamblocked' },
                    { value: 'banned', label: 'Banned' },
                    { value: 'dead', label: 'Dead' },
                    { value: 'frozen', label: 'Frozen' },
                  ]}
                  renderOption={(opt) => (
                    <span className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: (ACCOUNT_STATUS_STYLES[opt.value] || { color: '#6B7280' }).color }} />
                      {opt.label}
                    </span>
                  )}
                  renderSelected={opt => (
                    <span className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: (ACCOUNT_STATUS_STYLES[opt.value] || { color: '#6B7280' }).color }} />
                      {opt.label}
                    </span>
                  )}
                />
              </div>
            </div>
            <div className="mt-3">
              <label className={panelLabelCls} style={{ color: A.text3 }}>Bio</label>
              <textarea value={form.bio} onChange={e => set('bio', e.target.value)} rows={2}
                        className={panelInputCls}
                        style={{ background: A.surface, borderColor: A.border, color: A.text1 }} />
            </div>
          </section>

          {/* ---- Section: Technical ---- */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: A.text3 }}>Technical</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={panelLabelCls} style={{ color: A.text3 }}>Daily Limit</label>
                <input type="number" value={form.daily_message_limit}
                       onChange={e => set('daily_message_limit', e.target.value)}
                       className={panelInputCls}
                       style={{ background: A.surface, borderColor: A.border, color: A.text1 }} />
              </div>
              <div className="flex items-center justify-between col-span-2 rounded-lg px-3 py-2" style={{ background: account.is_premium ? '#F5F3FF' : A.bg, border: `1px solid ${account.is_premium ? '#C4B5FD' : A.border}` }}>
                <div>
                  <label className="text-xs font-medium" style={{ color: account.is_premium ? '#7C3AED' : A.text1 }}>
                    ⭐ Premium Account
                  </label>
                  <div className="text-[10px]" style={{ color: A.text3 }}>
                    {account.is_premium ? 'Higher limits: 10 msgs/day, young cap 10' : 'Standard: 5 msgs/day, young cap 5'}
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-medium" style={{
                  background: account.is_premium ? '#EDE9FE' : A.bg,
                  color: account.is_premium ? '#7C3AED' : A.text3,
                  border: `1px solid ${account.is_premium ? '#C4B5FD' : A.border}`
                }}>
                  {account.is_premium ? 'PRO' : 'Standard'} · auto
                </span>
              </div>
              {/* Active Warm-up — Enhanced */}
              {(() => {
                const ws = warmupStatus;
                const isActive = ws?.warmup_active ?? account.warmup_active;
                const day = ws?.warmup_day ?? account.warmup_progress?.day ?? null;
                const totalDays = ws?.total_days ?? 14;
                const pct = day != null ? Math.min(100, Math.round((day / totalDays) * 100)) : 0;
                const isMaintenance = isActive && day != null && day > totalDays;
                const isCompleted = !isActive && day != null && day >= totalDays;

                // Phase calculation
                let phaseName = 'Not started';
                let phaseDesc = 'Start warm-up to reduce ban risk';
                if (isMaintenance) {
                  phaseName = 'Maintenance';
                  phaseDesc = 'Warm-up complete. 1-2 reactions/day to keep account healthy.';
                } else if (isCompleted) {
                  phaseName = 'Completed';
                  phaseDesc = 'Warm-up finished. Maintenance actions continue.';
                } else if (isActive && day != null) {
                  if (day <= 3) { phaseName = 'Initial Phase'; phaseDesc = 'Subscribing to channels, light reactions'; }
                  else if (day <= 7) { phaseName = 'Growth Phase'; phaseDesc = 'Adding conversations, increasing activity'; }
                  else if (day <= 10) { phaseName = 'Active Phase'; phaseDesc = 'Full activity: channels, reactions, conversations'; }
                  else { phaseName = 'Final Phase'; phaseDesc = 'Peak activity, preparing for outreach'; }
                }

                // Next action estimate (worker ticks every 30 min, 9-22 Moscow UTC+3)
                let nextActionText = '';
                if (isActive) {
                  const now = new Date();
                  const mskHour = (now.getUTCHours() + 3) % 24;
                  if (mskHour >= 9 && mskHour < 22) {
                    const minsLeft = 30 - (now.getMinutes() % 30);
                    nextActionText = `~${minsLeft} min`;
                  } else {
                    nextActionText = mskHour >= 22 ? 'Tomorrow 9:00 MSK' : `Today ${9 - mskHour}h`;
                  }
                }

                return (
                  <div className="col-span-2 rounded-lg px-3 py-3 space-y-2" style={{ background: isActive ? '#F0FDF4' : isCompleted ? '#ECFDF5' : A.bg, border: `1px solid ${isActive ? '#BBF7D0' : isCompleted ? '#A7F3D0' : A.border}` }}>
                    {/* Header row */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <label className="text-xs font-medium" style={{ color: A.text1 }}>Account Warmup</label>
                        <span className="tip" data-tip="14-day program: joins channels, adds reactions, exchanges messages. Simulates real user activity to reduce ban risk.">
                          <Info className="w-3 h-3 cursor-help" style={{ color: '#059669' }} />
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        {(isActive || isCompleted || (ws && ws.actions_done > 0)) && (
                          <button type="button" onClick={() => { refreshWarmupStatus(); telegramOutreachApi.warmupLogs(account.id).then(setWarmupLogs).catch(() => {}); setShowWarmupDebug(true); }}
                            className="px-2 py-0.5 rounded text-[10px] font-medium transition-colors hover:bg-gray-100"
                            style={{ color: A.text3, border: `1px solid ${A.border}` }}>
                            Debug
                          </button>
                        )}
                        <button type="button"
                          onClick={async () => {
                            try {
                              if (isActive) {
                                await telegramOutreachApi.warmupStop(account.id);
                                toast('Active warm-up stopped', 'success');
                              } else {
                                await telegramOutreachApi.warmupStart(account.id);
                                toast('Active warm-up started', 'success');
                              }
                              refreshWarmupStatus();
                              onSaved();
                            } catch { toast('Failed to toggle warm-up', 'error'); }
                          }}
                          className="px-2.5 py-1 rounded-md text-[11px] font-medium text-white"
                          style={{ background: isActive ? '#dc2626' : '#059669' }}>
                          {isActive ? 'Stop' : 'Start'}
                        </button>
                      </div>
                    </div>

                    {/* Phase + description */}
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-semibold" style={{ color: isCompleted ? '#059669' : isActive ? '#065F46' : A.text2 }}>{phaseName}</span>
                        {isActive && day != null && <span className="text-[10px]" style={{ color: A.text3 }}>Day {day}/{totalDays}</span>}
                        {isActive && <span className="text-[10px]" style={{ color: A.text3 }}>{pct}%</span>}
                      </div>
                      <div className="text-[10px]" style={{ color: A.text3 }}>{phaseDesc}</div>
                    </div>

                    {/* Progress bar */}
                    {(isActive || isCompleted) && (
                      <div className="space-y-1">
                        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: '#D1FAE5' }}>
                          <div className="h-full rounded-full transition-all duration-500"
                               style={{ width: `${isCompleted ? 100 : pct}%`, background: isCompleted ? '#10B981' : '#059669' }} />
                        </div>
                        <div className="flex items-center justify-between text-[10px]" style={{ color: A.text3 }}>
                          <span>{ws ? `${ws.actions_done} total actions · ${ws.actions_today} today` : `${account.warmup_actions_done || 0} actions`}</span>
                          {nextActionText && <span>Next: {nextActionText}</span>}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}
              <div>
                <label className={panelLabelCls} style={{ color: A.text3 }}>Device Model</label>
                <input value={form.device_model} onChange={e => set('device_model', e.target.value)}
                       className={panelInputCls}
                       style={{ background: A.surface, borderColor: A.border, color: A.text1 }} />
              </div>
              <div>
                <label className={panelLabelCls} style={{ color: A.text3 }}>System Version</label>
                <input value={form.system_version} onChange={e => set('system_version', e.target.value)}
                       className={panelInputCls}
                       style={{ background: A.surface, borderColor: A.border, color: A.text1 }} />
              </div>
              <div>
                <label className={panelLabelCls} style={{ color: A.text3 }}>App Version</label>
                <input value={form.app_version} onChange={e => set('app_version', e.target.value)}
                       className={panelInputCls}
                       style={{ background: A.surface, borderColor: A.border, color: A.text1 }} />
              </div>
              <div>
                <label className={panelLabelCls} style={{ color: A.text3 }}>Lang Code</label>
                <input value={form.lang_code} onChange={e => set('lang_code', e.target.value)}
                       className={panelInputCls}
                       style={{ background: A.surface, borderColor: A.border, color: A.text1 }} />
              </div>
              <div>
                <label className={panelLabelCls} style={{ color: A.text3 }}>System Lang</label>
                <input value={form.system_lang_code} onChange={e => set('system_lang_code', e.target.value)}
                       className={panelInputCls}
                       style={{ background: A.surface, borderColor: A.border, color: A.text1 }} />
              </div>
            </div>
          </section>

          {/* ---- Section: Stats ---- */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: A.text3 }}>Stats</h3>
            <div className="rounded-lg p-3 grid grid-cols-3 gap-3 text-center mb-3"
                 style={{ background: A.bg, border: `1px solid ${A.border}` }}>
              <div>
                <div className="text-lg font-bold" style={{ color: A.text1 }}>{account.messages_sent_today}</div>
                <div className="text-xs" style={{ color: A.text3 }}>Sent Today</div>
              </div>
              <div>
                <div className="text-lg font-bold" style={{ color: A.text1 }}>{account.total_messages_sent}</div>
                <div className="text-xs" style={{ color: A.text3 }}>Total Sent</div>
              </div>
              <div>
                <div className="text-lg font-bold" style={{ color: A.text1 }}>{account.campaigns_count}</div>
                <div className="text-xs" style={{ color: A.text3 }}>Campaigns</div>
              </div>
            </div>
            <AccountAnalytics accountId={account.id} />
          </section>

          {/* ---- Section: Proxy ---- */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: A.text3 }}>Proxy</h3>
            <div className="rounded-lg p-3 space-y-2"
                 style={{ background: A.bg, border: `1px solid ${A.border}` }}>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium" style={{ color: A.text3 }}>Group</span>
                {account.proxy_group_name ? (
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full"
                        style={{ background: A.blueBg, color: A.blue }}>
                    {account.proxy_group_name}
                  </span>
                ) : (
                  <span className="text-xs" style={{ color: A.text3 }}>None</span>
                )}
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium" style={{ color: A.text3 }}>Assigned Proxy</span>
                {account.assigned_proxy_host ? (
                  <span className="text-xs font-mono font-medium px-2 py-0.5 rounded-full"
                        style={{ background: '#E8F5E9', color: '#2E7D32' }}>
                    {account.assigned_proxy_host}
                  </span>
                ) : account.proxy_group_name ? (
                  <span className="text-xs px-2 py-0.5 rounded-full"
                        style={{ background: '#FFF3E0', color: '#E65100' }}>
                    No free proxy
                  </span>
                ) : (
                  <span className="text-xs" style={{ color: A.text3 }}>None</span>
                )}
              </div>
            </div>
          </section>

          {/* ---- Section: Actions ---- */}
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: A.text3 }}>Actions</h3>
            <div className="rounded-lg p-4 space-y-3"
                 style={{ background: A.bg, border: `1px solid ${A.border}` }}>
              <div className="flex items-center gap-2 flex-wrap">
                {/* Upload Session */}
                <button onClick={() => sessionFileRef.current?.click()}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors hover:bg-[#F3F3F1]"
                        style={{ border: `1px solid ${A.border}`, color: A.text1 }}>
                  <Upload className="w-3 h-3" /> Upload .session
                </button>
                <input ref={sessionFileRef} type="file" accept=".session" className="hidden"
                       onChange={async e => {
                         const file = e.target.files?.[0];
                         if (!file) return;
                         try {
                           await telegramOutreachApi.uploadSession(account.id, file);
                           toast('Session uploaded', 'success');
                         } catch { toast('Failed to upload session', 'error'); }
                         e.target.value = '';
                       }} />

                {/* Check Account */}
                <button onClick={async () => {
                          setChecking(true); setCheckResult(null);
                          try {
                            const res = await telegramOutreachApi.checkAccount(account.id);
                            setCheckResult(res);
                            toast(res.authorized ? 'Account OK' : 'Account not authorized', res.authorized ? 'success' : 'error');
                          } catch (e: any) {
                            toast(e?.response?.data?.detail || 'Check failed', 'error');
                          } finally { setChecking(false); }
                        }}
                        disabled={checking}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                        style={{ border: `1px solid #D9770640`, color: '#D97706', cursor: checking ? 'wait' : 'pointer' }}
                        onMouseEnter={e => { e.currentTarget.style.background = '#FFFBEB'; }}
                        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}>
                  {checking ? <Loader2 className="w-3 h-3 animate-spin" /> : <Shield className="w-3 h-3" />}
                  Spam?
                </button>

                {/* Auth */}
                <button onClick={async () => {
                          setAuthLoading(true);
                          try {
                            const res = await telegramOutreachApi.authSendCode(account.id);
                            if (res.status === 'already_authorized') {
                              toast('Already authorized', 'success');
                            } else if (res.status === 'code_sent') {
                              setAuthStep('code_sent');
                              toast('Code sent to Telegram', 'info');
                            }
                          } catch (e: any) {
                            toast(e?.response?.data?.detail || 'Failed to send code', 'error');
                          } finally { setAuthLoading(false); }
                        }}
                        disabled={authLoading}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-white text-xs font-medium hover:opacity-90 disabled:opacity-50"
                        style={{ background: A.teal }}>
                  {authLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Shield className="w-3 h-3" />}
                  Authorize
                </button>

                {/* Update Profile on TG */}
                <button onClick={async () => {
                          try {
                            const res = await telegramOutreachApi.updateProfile(account.id, {
                              first_name: form.first_name || undefined,
                              last_name: form.last_name || undefined,
                              about: form.bio || undefined,
                              username: form.username || undefined,
                            });
                            toast(res.username_error ? `Profile updated, but: ${res.username_error}` : 'Profile synced to Telegram', 'success');
                          } catch (e: any) {
                            toast(e?.response?.data?.detail || 'Failed to update profile', 'error');
                          }
                        }}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors hover:bg-[#F3F3F1]"
                        style={{ border: `1px solid ${A.border}`, color: A.text1 }}>
                  <Edit3 className="w-3 h-3" /> Sync Profile to TG
                </button>

                {/* Conversion buttons */}
                <button onClick={async () => {
                          try {
                            await telegramOutreachApi.convertToTdata(account.id);
                            toast('Converted! Downloading...', 'success');
                            // Auto-download the ZIP
                            const url = telegramOutreachApi.downloadTdata(account.id);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `tdata_${account.phone}.zip`;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                          } catch (e: any) {
                            toast(e?.response?.data?.detail || 'Conversion failed', 'error');
                          }
                        }}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors hover:bg-[#F3F3F1]"
                        style={{ border: `1px solid ${A.border}`, color: A.text1 }}>
                  Session → TDATA
                </button>
                <button onClick={async () => {
                          try {
                            await telegramOutreachApi.convertFromTdata(account.id);
                            toast('Converted! Downloading .session...', 'success');
                            const url = telegramOutreachApi.downloadSession(account.id);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `${account.phone}.session`;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                          } catch (e: any) {
                            toast(e?.response?.data?.detail || 'Conversion failed', 'error');
                          }
                        }}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors hover:bg-[#F3F3F1]"
                        style={{ border: `1px solid ${A.border}`, color: A.text1 }}>
                  TDATA → Session
                </button>
              </div>

              {/* Auth code input */}
              {authStep === 'code_sent' && (
                <div className="flex items-center gap-2">
                  <input value={authCode} onChange={e => setAuthCode(e.target.value)}
                         placeholder="Enter code from Telegram"
                         className="flex-1 px-3 py-1.5 rounded-lg text-sm font-mono outline-none focus:ring-2 focus:ring-[#4F6BF0]/20"
                         style={{ background: A.surface, border: `1px solid ${A.border}`, color: A.text1 }} />
                  <button onClick={async () => {
                            setAuthLoading(true);
                            try {
                              const res = await telegramOutreachApi.authVerifyCode(account.id, authCode);
                              if (res.status === 'authorized') {
                                toast('Authorized!', 'success');
                                setAuthStep('none'); setAuthCode('');
                              } else if (res.status === '2fa_required') {
                                setAuthStep('2fa_required');
                                toast('2FA password required', 'info');
                              } else {
                                toast(res.detail || 'Verification failed', 'error');
                              }
                            } catch { toast('Verification failed', 'error'); }
                            finally { setAuthLoading(false); }
                          }}
                          disabled={authLoading || !authCode}
                          className="px-3 py-1.5 text-white rounded-lg text-xs font-medium hover:opacity-90 disabled:opacity-50"
                          style={{ background: A.blue }}>
                    {authLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Verify'}
                  </button>
                </div>
              )}

              {/* 2FA input */}
              {authStep === '2fa_required' && (
                <div className="flex items-center gap-2">
                  <input type="password" value={authPassword} onChange={e => setAuthPassword(e.target.value)}
                         placeholder="Enter 2FA password"
                         className="flex-1 px-3 py-1.5 rounded-lg text-sm outline-none focus:ring-2 focus:ring-[#4F6BF0]/20"
                         style={{ background: A.surface, border: `1px solid ${A.border}`, color: A.text1 }} />
                  <button onClick={async () => {
                            setAuthLoading(true);
                            try {
                              const res = await telegramOutreachApi.authVerify2FA(account.id, authPassword);
                              if (res.status === 'authorized') {
                                toast('Authorized!', 'success');
                                setAuthStep('none'); setAuthPassword('');
                              } else {
                                toast(res.detail || '2FA failed', 'error');
                              }
                            } catch { toast('2FA failed', 'error'); }
                            finally { setAuthLoading(false); }
                          }}
                          disabled={authLoading || !authPassword}
                          className="px-3 py-1.5 text-white rounded-lg text-xs font-medium hover:opacity-90 disabled:opacity-50"
                          style={{ background: A.blue }}>
                    {authLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Verify 2FA'}
                  </button>
                </div>
              )}

              {/* Check result */}
              {checkResult && (
                <div className="rounded-lg p-3 text-xs space-y-1"
                     style={{ background: A.bg }}>
                  <div className="flex gap-4">
                    <span>Connected: <b className={checkResult.connected ? 'text-green-500' : 'text-red-500'}>{checkResult.connected ? 'Yes' : 'No'}</b></span>
                    <span>Authorized: <b className={checkResult.authorized ? 'text-green-500' : 'text-red-500'}>{checkResult.authorized ? 'Yes' : 'No'}</b></span>
                    <span>Spamblock: <b className={checkResult.spamblock === 'none' ? 'text-green-500' : 'text-red-500'}>{checkResult.spamblock}</b></span>
                  </div>
                  {checkResult.error && <p className="text-red-500">Error: {checkResult.error}</p>}
                </div>
              )}
            </div>
          </section>
        </div>

        {/* -- Footer -- */}
        <div className="flex items-center justify-between px-6 py-4"
             style={{ borderTop: `1px solid ${A.border}` }}>
          <button onClick={handleDelete}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm transition-colors"
                  style={{ color: A.rose }}
                  onMouseEnter={e => (e.currentTarget.style.background = A.roseBg)}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
            <Trash2 className="w-3.5 h-3.5" /> Delete
          </button>
          <div className="flex items-center gap-3">
            <button onClick={onClose}
                    className="px-4 py-2 rounded-lg text-sm transition-colors hover:bg-[#F3F3F1]"
                    style={{ border: `1px solid ${A.border}`, color: A.text1 }}>Cancel</button>
            <button onClick={handleSave} disabled={saving}
                    className="flex items-center gap-2 px-5 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50 transition-colors"
                    style={{ background: A.blue }}
                    onMouseEnter={e => (e.currentTarget.style.background = A.blueHover)}
                    onMouseLeave={e => (e.currentTarget.style.background = A.blue)}>
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              Save
            </button>
          </div>
        </div>
        {confirmDeleteAccount && (
          <ConfirmModal message={`Delete account ${account.phone}?`}
            onConfirm={doDeleteAccount}
            onCancel={() => setConfirmDeleteAccount(false)} />
        )}
        {/* Username change prompt */}
        {showUsernamePrompt && (
          <div className="absolute inset-0 z-10 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.3)' }}>
            <div className="rounded-xl shadow-xl p-5 w-[360px]" style={{ background: A.surface, border: `1px solid ${A.border}` }}>
              <h3 className="text-sm font-semibold mb-1" style={{ color: A.text1 }}>Change username?</h3>
              <p className="text-xs mb-3" style={{ color: A.text3 }}>
                You changed the name to <b>{[form.first_name, form.last_name].filter(Boolean).join(' ')}</b>. Update the username to match?
              </p>

              {loadingSuggestions ? (
                <div className="flex items-center gap-2 py-3 justify-center text-xs" style={{ color: A.text3 }}>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" /> Finding available usernames...
                </div>
              ) : usernameSuggestions.length > 0 ? (
                <div className="space-y-1.5 mb-3">
                  {usernameSuggestions.map(s => (
                    <button key={s} onClick={() => {
                      setForm(f => ({ ...f, username: s }));
                      setUsernameStatus('available');
                      setShowUsernamePrompt(false);
                      doSave({ username: s });
                    }}
                      className="w-full text-left px-3 py-2 rounded-lg text-sm font-mono transition-colors hover:ring-1"
                      style={{ background: A.bg, color: A.text1, border: `1px solid ${A.border}` }}
                      onMouseEnter={e => (e.currentTarget.style.borderColor = A.blue)}
                      onMouseLeave={e => (e.currentTarget.style.borderColor = A.border)}>
                      @{s}
                    </button>
                  ))}
                </div>
              ) : (
                <p className="text-xs py-2 mb-3" style={{ color: A.text3 }}>No available usernames found. You can set one manually.</p>
              )}

              <div className="flex items-center gap-2">
                <button onClick={() => { setShowUsernamePrompt(false); doSave(); }}
                  className="flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors hover:bg-[#F3F3F1]"
                  style={{ border: `1px solid ${A.border}`, color: A.text1 }}>
                  Skip
                </button>
                <button onClick={() => setShowUsernamePrompt(false)}
                  className="flex-1 px-3 py-2 rounded-lg text-xs font-medium transition-colors hover:bg-[#F3F3F1]"
                  style={{ border: `1px solid ${A.border}`, color: A.text3 }}>
                  Set manually
                </button>
              </div>
            </div>
          </div>
        )}
        {/* Warmup Debug Modal */}
        {showWarmupDebug && warmupStatus && (() => {
          // Group actions by day
          type WuAction = { action_type: string; detail: string | null; success: boolean; performed_at: string | null };
          const allActions: WuAction[] = warmupLogs.length > 0 ? warmupLogs : warmupStatus.recent_actions;
          const grouped: Record<string, WuAction[]> = {};
          for (const a of allActions) {
            const d = a.performed_at ? new Date(a.performed_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }) : 'Unknown';
            (grouped[d] ??= []).push(a);
          }
          const days = Object.entries(grouped);
          const actionLabel = (t: string) => t === 'channel_join' ? 'Join Channel' : t === 'reaction' ? 'Add Reaction' : t === 'conversation' ? 'Conversation' : t;
          const actionColor = (t: string) => t === 'channel_join' ? '#2563EB' : t === 'reaction' ? '#D97706' : '#059669';

          return (
            <div className="absolute inset-0 z-10 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.35)' }}>
              <div className="rounded-xl shadow-xl w-[400px] max-h-[75vh] flex flex-col" style={{ background: A.surface, border: `1px solid ${A.border}` }}>
                <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: `1px solid ${A.border}` }}>
                  <div>
                    <h3 className="text-sm font-semibold" style={{ color: A.text1 }}>Warmup Sessions Debug</h3>
                    <p className="text-[10px]" style={{ color: A.text3 }}>
                      Day {warmupStatus.warmup_day ?? '—'}/{warmupStatus.total_days} · {warmupStatus.actions_done} total · {warmupStatus.actions_today} today
                    </p>
                  </div>
                  <button onClick={() => setShowWarmupDebug(false)} className="p-1 rounded hover:bg-gray-100">
                    <X className="w-4 h-4" style={{ color: A.text3 }} />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
                  {days.length === 0 && <p className="text-xs text-center py-4" style={{ color: A.text3 }}>No warmup actions recorded yet.</p>}
                  {days.map(([dayLabel, actions]) => (
                    <div key={dayLabel}>
                      <button type="button" onClick={() => setWarmupExpanded(p => ({ ...p, [dayLabel]: !p[dayLabel] }))}
                        className="flex items-center justify-between w-full text-left px-2 py-1.5 rounded-md hover:bg-gray-50 transition-colors">
                        <span className="text-[11px] font-semibold" style={{ color: A.text1 }}>{dayLabel}</span>
                        <span className="flex items-center gap-1.5">
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: A.bg, color: A.text3 }}>{actions.length} actions</span>
                          <ChevronDown className="w-3 h-3 transition-transform" style={{ color: A.text3, transform: warmupExpanded[dayLabel] ? 'rotate(180deg)' : 'rotate(0)' }} />
                        </span>
                      </button>
                      {warmupExpanded[dayLabel] && (
                        <div className="mt-1 ml-2 space-y-1">
                          {actions.map((a, i) => (
                            <div key={i} className="flex items-start gap-2 px-2 py-1.5 rounded-md text-[10px]" style={{ background: A.bg }}>
                              <span className="shrink-0 mt-0.5 w-1.5 h-1.5 rounded-full" style={{ background: a.success ? actionColor(a.action_type) : '#EF4444' }} />
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-1.5">
                                  <span className="font-medium" style={{ color: actionColor(a.action_type) }}>{actionLabel(a.action_type)}</span>
                                  <span style={{ color: A.text3 }}>{a.performed_at ? new Date(a.performed_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) : ''}</span>
                                  {!a.success && <span className="text-red-500 font-medium">FAILED</span>}
                                </div>
                                {a.detail && <div className="truncate" style={{ color: A.text3 }}>{a.detail}</div>}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          );
        })()}
      </div>

      {/* Keyframe for slide-in animation */}
      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); }
          to   { transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════
// Import TeleRaptor Modal
// ══════════════════════════════════════════════════════════════════════

function ImportTeleRaptorModal({ t, toast, isDark, onClose, onImported }: {
  t: any; toast: any; isDark: boolean; onClose: () => void; onImported: () => void;
}) {
  const [format, setFormat] = useState<'bundle' | 'json' | 'paste'>('bundle');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [jsonText, setJsonText] = useState('');
  const [parsedAccounts, setParsedAccounts] = useState<Record<string, any>[]>([]);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fileAccept = format === 'bundle' ? '.json,.session,.zip' : '.json';

  const handleFilesSelected = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const arr = Array.from(files);
    setSelectedFiles(arr);

    // Parse JSON files for preview
    const accounts: Record<string, any>[] = [];
    const sessionCount = arr.filter(f => f.name.endsWith('.session')).length;
    const zipCount = arr.filter(f => f.name.endsWith('.zip')).length;

    for (const file of arr) {
      if (!file.name.endsWith('.json')) continue;
      try {
        const text = await file.text();
        const data = JSON.parse(text);
        if (Array.isArray(data)) accounts.push(...data);
        else if (data.phone) accounts.push(data);
      } catch { /* skip */ }
    }
    setParsedAccounts(accounts);
    if (accounts.length > 0 || sessionCount > 0 || zipCount > 0) {
      toast(`${accounts.length} JSON, ${sessionCount} session, ${zipCount} ZIP files selected`, 'info');
    }
  };

  const handleParse = () => {
    try {
      const data = JSON.parse(jsonText);
      if (Array.isArray(data)) setParsedAccounts(data);
      else if (data.phone) setParsedAccounts([data]);
      else toast('Invalid JSON', 'error');
    } catch { toast('Invalid JSON', 'error'); }
  };

  const handleImport = async () => {
    setImporting(true);
    try {
      if (format === 'paste') {
        if (parsedAccounts.length === 0) return;
        const res = await telegramOutreachApi.importTeleRaptor(parsedAccounts);
        setResult(res);
        toast(`${res.added} accounts imported`, res.added > 0 ? 'success' : 'info');
      } else {
        // Bundle import (JSON + Session + ZIP)
        if (selectedFiles.length === 0) return;
        const res = await telegramOutreachApi.importBundle(selectedFiles);
        setResult(res);
        const msg = [`${res.added} added`, `${res.sessions_saved} sessions saved`];
        if (res.skipped) msg.push(`${res.skipped} skipped`);
        toast(msg.join(', '), res.added > 0 ? 'success' : 'info');
      }
    } catch (e: any) {
      const data = e?.response?.data;
      const detail = typeof data === 'string' ? data
        : data?.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))
        : e?.message || 'Unknown error';
      toast(`Import failed: ${detail}`, 'error');
    } finally { setImporting(false); }
  };

  const jsonCount = selectedFiles.filter(f => f.name.endsWith('.json')).length;
  const sessionCount = selectedFiles.filter(f => f.name.endsWith('.session')).length;
  const zipCount = selectedFiles.filter(f => f.name.endsWith('.zip')).length;
  const canImport = format === 'paste' ? parsedAccounts.length > 0 : selectedFiles.length > 0;

  return (
    <ModalBackdrop onClose={onClose}>
      <div className={cn('w-[640px] rounded-xl border shadow-xl', t.cardBorder, isDark ? 'bg-gray-900' : 'bg-white')}>
        <div className={cn('flex items-center justify-between px-6 py-4 border-b', t.cardBorder)}>
          <div>
            <h2 className={cn('text-lg font-semibold', t.text1)}>Import Accounts</h2>
            <p className={cn('text-xs mt-0.5', t.text3)}>JSON + Session pairs, ZIP archives, or paste JSON</p>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        <div className="px-6 py-4 space-y-4">
          {/* Format tabs */}
          <div className="flex gap-2">
            {[
              { key: 'bundle' as const, label: 'JSON + Session', desc: 'Auto-pairs by phone' },
              { key: 'json' as const, label: 'JSON Only', desc: 'Metadata only' },
              { key: 'paste' as const, label: 'Paste JSON', desc: 'Manual input' },
            ].map(f => (
              <button key={f.key}
                      onClick={() => { setFormat(f.key); setSelectedFiles([]); setParsedAccounts([]); setResult(null); }}
                      className={cn('px-3 py-1.5 rounded-lg text-xs font-medium',
                        format === f.key ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400' : t.text3)}>
                {f.label}
              </button>
            ))}
          </div>

          {format !== 'paste' ? (
            <div>
              <div onClick={() => fileInputRef.current?.click()}
                   onDragOver={e => { e.preventDefault(); e.stopPropagation(); e.currentTarget.classList.add('border-indigo-400'); }}
                   onDragLeave={e => { e.preventDefault(); e.currentTarget.classList.remove('border-indigo-400'); }}
                   onDrop={e => {
                     e.preventDefault(); e.stopPropagation();
                     e.currentTarget.classList.remove('border-indigo-400');
                     if (e.dataTransfer.files.length > 0) handleFilesSelected(e.dataTransfer.files);
                   }}
                   className={cn('border-2 border-dashed rounded-xl p-6 text-center cursor-pointer hover:border-indigo-400 transition-colors', t.cardBorder)}>
                <Upload className={cn('w-8 h-8 mx-auto mb-2', t.text3)} />
                <p className={cn('text-sm font-medium', t.text1)}>
                  {selectedFiles.length > 0
                    ? `${selectedFiles.length} files selected`
                    : format === 'bundle' ? 'Drop or click to select .json + .session files' : 'Drop or click to select .json files'}
                </p>
                <p className={cn('text-xs mt-1', t.text3)}>
                  {format === 'bundle'
                    ? 'Auto-matched by phone (e.g. 351920619583.json + .session). Also accepts .zip'
                    : 'TeleRaptor account JSON files'}
                </p>
              </div>
              <input ref={fileInputRef} type="file" accept={fileAccept} multiple className="hidden"
                     onChange={e => { handleFilesSelected(e.target.files); e.target.value = ''; }} />

              {selectedFiles.length > 0 && (
                <div className={cn('mt-2 flex gap-3 text-xs', t.text3)}>
                  {jsonCount > 0 && <span className="px-2 py-0.5 rounded bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">{jsonCount} .json</span>}
                  {sessionCount > 0 && <span className="px-2 py-0.5 rounded bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">{sessionCount} .session</span>}
                  {zipCount > 0 && <span className="px-2 py-0.5 rounded bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">{zipCount} .zip</span>}
                  <span>{selectedFiles.length} files total</span>
                </div>
              )}
            </div>
          ) : (
            <div>
              <textarea rows={6} value={jsonText}
                        onChange={e => setJsonText(e.target.value)}
                        placeholder='[{"phone":"351920619583","app_id":2040,...}]'
                        className={cn('w-full px-3 py-2 rounded-lg border text-xs font-mono', t.cardBorder, t.cardBg, t.text1)} />
              <button onClick={handleParse}
                      className="mt-2 px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-medium hover:bg-indigo-700">
                Parse
              </button>
            </div>
          )}

          {/* Preview */}
          {parsedAccounts.length > 0 && !result && (
            <div className={cn('rounded-lg border overflow-auto max-h-44', t.cardBorder)}>
              <table className="w-full text-xs">
                <thead className={cn('border-b sticky top-0', t.cardBorder, isDark ? 'bg-gray-800' : 'bg-gray-50')}>
                  <tr>
                    <th className={cn('text-left px-2 py-1.5 font-medium', t.text3)}>Phone</th>
                    <th className={cn('text-left px-2 py-1.5 font-medium', t.text3)}>Name</th>
                    <th className={cn('text-left px-2 py-1.5 font-medium', t.text3)}>Username</th>
                    <th className={cn('text-left px-2 py-1.5 font-medium', t.text3)}>Spamblock</th>
                  </tr>
                </thead>
                <tbody>
                  {parsedAccounts.slice(0, 15).map((a, i) => (
                    <tr key={i} className={cn('border-b', t.cardBorder)}>
                      <td className={cn('px-2 py-1 font-mono', t.text1)}>{a.phone}</td>
                      <td className={cn('px-2 py-1', t.text1)}>{[a.first_name, a.last_name].filter(Boolean).join(' ') || '—'}</td>
                      <td className={cn('px-2 py-1', t.text3)}>{a.username ? `@${a.username}` : '—'}</td>
                      <td className="px-2 py-1">
                        <span className={cn('px-1 py-0.5 rounded text-xs',
                          a.spamblock === 'no' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-red-100 text-red-600 dark:bg-red-900/20 dark:text-red-400')}>
                          {a.spamblock || '?'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Result */}
          {result && (
            <div className={cn('rounded-lg border p-4 space-y-2', t.cardBorder)}>
              <p className={cn('text-sm font-medium', t.text1)}>Import complete!</p>
              <div className="flex gap-4 text-sm flex-wrap">
                <span className="text-green-600 font-medium">{result.added} added</span>
                {result.sessions_saved > 0 && <span className="text-blue-600">{result.sessions_saved} sessions</span>}
                {result.skipped > 0 && <span className={t.text3}>{result.skipped} skipped</span>}
              </div>
            </div>
          )}
        </div>

        <div className={cn('flex items-center justify-end gap-3 px-6 py-4 border-t', t.cardBorder)}>
          {result ? (
            <button onClick={onImported}
                    className="px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">
              Done
            </button>
          ) : (
            <>
              <button onClick={onClose}
                      className={cn('px-4 py-2 rounded-lg border text-sm', t.cardBorder, t.text1)}>Cancel</button>
              <button onClick={handleImport} disabled={importing || !canImport}
                      className="flex items-center gap-2 px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
                {importing && <Loader2 className="w-4 h-4 animate-spin" />}
                Import
              </button>
            </>
          )}
        </div>
      </div>
    </ModalBackdrop>
  );
}


// ══════════════════════════════════════════════════════════════════════
// Parser Tab
// ══════════════════════════════════════════════════════════════════════

function ParserTab({ t: _t, toast }: { t: any; toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) { void _t;
  const [groupInput, setGroupInput] = useState('');
  const [accountId, setAccountId] = useState<number | ''>('');
  const [accounts, setAccounts] = useState<TgAccount[]>([]);
  const [members, setMembers] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [campaigns, setCampaigns] = useState<TgCampaign[]>([]);
  const [targetCampaignId, setTargetCampaignId] = useState<number | ''>('');

  useEffect(() => {
    telegramOutreachApi.listAccounts({ page_size: 200, status: 'active' }).then(d => setAccounts(d.items)).catch(() => {});
    telegramOutreachApi.listCampaigns().then(d => setCampaigns(d.items)).catch(() => {});
  }, []);

  const handleScrape = async () => {
    if (!groupInput || !accountId) { toast('Enter group and select account', 'error'); return; }
    setLoading(true);
    try {
      const res = await telegramOutreachApi.scrapeGroup(groupInput.replace('@', ''), accountId as number);
      setMembers(res.members);
      toast(`Found ${res.filtered} members (${res.total_found} total)`, 'success');
    } catch (e: any) {
      toast(e?.response?.data?.detail || 'Scrape failed', 'error');
    } finally { setLoading(false); }
  };

  const handleAddToCampaign = async () => {
    if (!targetCampaignId || members.length === 0) return;
    try {
      const res = await telegramOutreachApi.addParsedToCampaign(targetCampaignId as number, members);
      toast(`${res.added} added to campaign (${res.total} total)`, 'success');
    } catch { toast('Failed', 'error'); }
  };

  const inputStyle = { borderColor: A.border, background: A.surface, color: A.text1 };

  return (
    <div className="max-w-4xl space-y-4">
      <div className="rounded-lg border p-5" style={{ borderColor: A.border }}>
        <h3 className="text-sm font-semibold mb-4" style={{ color: A.text1 }}>Scrape Group Members</h3>
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-xs font-medium mb-1" style={{ color: A.text3 }}>Group/Channel</label>
            <input value={groupInput} onChange={e => setGroupInput(e.target.value)}
                   placeholder="@group_username or t.me/group" className="px-3 py-2 rounded-lg border text-sm w-full" style={inputStyle} />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: A.text3 }}>Account</label>
            <select value={accountId} onChange={e => setAccountId(e.target.value ? Number(e.target.value) : '')}
                    className="px-3 py-2 rounded-lg border text-sm" style={inputStyle}>
              <option value="">Select...</option>
              {accounts.map(a => <option key={a.id} value={a.id}>{a.phone} {a.first_name || ''}</option>)}
            </select>
          </div>
          <button onClick={handleScrape} disabled={loading}
                  className="px-4 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50"
                  style={{ background: A.blue }}>
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Scrape'}
          </button>
        </div>
      </div>

      {members.length > 0 && (
        <div className="rounded-lg border p-5" style={{ borderColor: A.border }}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold" style={{ color: A.text1 }}>{members.length} members found</h3>
            <div className="flex items-center gap-2">
              <select value={targetCampaignId}
                      onChange={e => setTargetCampaignId(e.target.value ? Number(e.target.value) : '')}
                      className="px-3 py-2 rounded-lg border text-sm" style={inputStyle}>
                <option value="">Add to campaign...</option>
                {campaigns.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <button onClick={handleAddToCampaign} disabled={!targetCampaignId}
                      className="px-3 py-2 text-white rounded-lg text-sm font-medium disabled:opacity-50"
                      style={{ background: A.teal }}>
                Add All
              </button>
            </div>
          </div>
          <div className="rounded-lg border overflow-auto max-h-80" style={{ borderColor: A.border }}>
            <table className="w-full text-xs">
              <thead className="border-b sticky top-0" style={{ borderColor: A.border, background: '#F9F9F7' }}>
                <tr>
                  <th className="text-left px-3 py-2 font-medium" style={{ color: A.text3 }}>Username</th>
                  <th className="text-left px-3 py-2 font-medium" style={{ color: A.text3 }}>Name</th>
                  <th className="text-left px-3 py-2 font-medium" style={{ color: A.text3 }}>Premium</th>
                  <th className="text-left px-3 py-2 font-medium" style={{ color: A.text3 }}>Photo</th>
                </tr>
              </thead>
              <tbody>
                {members.map((m: any, i: number) => (
                  <tr key={i} className="border-b" style={{ borderColor: A.border }}>
                    <td className="px-3 py-1.5 font-mono" style={{ color: A.text1 }}>@{m.username}</td>
                    <td className="px-3 py-1.5" style={{ color: A.text1 }}>{[m.first_name, m.last_name].filter(Boolean).join(' ')}</td>
                    <td className="px-3 py-1.5">{m.is_premium ? '⭐' : ''}</td>
                    <td className="px-3 py-1.5">{m.has_photo ? '📷' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════
// CRM Tab
// ══════════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════════
// Custom Fields Tab (Custom Properties)
// ══════════════════════════════════════════════════════════════════════

const FIELD_TYPES = [
  { value: 'text', label: 'Text' },
  { value: 'number', label: 'Number' },
  { value: 'select', label: 'Select' },
  { value: 'multi_select', label: 'Multi-Select' },
  { value: 'date', label: 'Date' },
  { value: 'url', label: 'URL' },
];

function CustomFieldsTab({ toast }: { toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) {
  const [fields, setFields] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editingField, setEditingField] = useState<any>(null);
  const [formName, setFormName] = useState('');
  const [formType, setFormType] = useState('text');
  const [formOptions, setFormOptions] = useState('');
  const [saving, setSaving] = useState(false);

  const loadFields = useCallback(async () => {
    try {
      const data = await telegramOutreachApi.listCustomFields();
      setFields(data);
    } catch { toast('Failed to load custom fields', 'error'); }
    setLoading(false);
  }, [toast]);

  useEffect(() => { loadFields(); }, [loadFields]);

  const openCreate = () => {
    setEditingField(null);
    setFormName('');
    setFormType('text');
    setFormOptions('');
    setShowCreate(true);
  };

  const openEdit = (f: any) => {
    setEditingField(f);
    setFormName(f.name);
    setFormType(f.field_type);
    setFormOptions((f.options_json || []).join('\n'));
    setShowCreate(true);
  };

  const handleSave = async () => {
    if (!formName.trim()) { toast('Name is required', 'error'); return; }
    setSaving(true);
    try {
      const options = (formType === 'select' || formType === 'multi_select')
        ? formOptions.split('\n').map(s => s.trim()).filter(Boolean)
        : [];
      if (editingField) {
        await telegramOutreachApi.updateCustomField(editingField.id, {
          name: formName.trim(),
          field_type: formType,
          options_json: options,
        });
        toast('Field updated', 'success');
      } else {
        await telegramOutreachApi.createCustomField({
          name: formName.trim(),
          field_type: formType,
          options_json: options,
        });
        toast('Field created', 'success');
      }
      setShowCreate(false);
      loadFields();
    } catch { toast('Failed to save field', 'error'); }
    setSaving(false);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this custom field and all its values?')) return;
    try {
      await telegramOutreachApi.deleteCustomField(id);
      toast('Field deleted', 'success');
      loadFields();
    } catch { toast('Failed to delete', 'error'); }
  };

  if (loading) return <div className="flex items-center justify-center py-20"><Loader2 className="w-6 h-6 animate-spin" style={{ color: A.text2 }} /></div>;

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold" style={{ color: A.text1 }}>Custom Properties</h2>
          <p className="text-sm mt-0.5" style={{ color: A.text2 }}>Define custom fields for your CRM contacts</p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium text-white"
          style={{ background: A.blue }}
        >
          <Plus className="w-4 h-4" /> Add Field
        </button>
      </div>

      {fields.length === 0 ? (
        <div className="text-center py-16 rounded-xl" style={{ background: A.surface, border: `1px solid ${A.border}` }}>
          <Settings className="w-10 h-10 mx-auto mb-3" style={{ color: A.text2 }} />
          <p className="text-sm font-medium" style={{ color: A.text1 }}>No custom fields yet</p>
          <p className="text-xs mt-1" style={{ color: A.text2 }}>Create fields to track custom data on your leads</p>
          <button onClick={openCreate} className="mt-4 px-4 py-1.5 rounded-lg text-sm font-medium text-white" style={{ background: A.blue }}>
            Create First Field
          </button>
        </div>
      ) : (
        <div className="rounded-xl overflow-hidden" style={{ border: `1px solid ${A.border}` }}>
          <table className="w-full text-sm" style={{ background: A.surface }}>
            <thead>
              <tr style={{ borderBottom: `1px solid ${A.border}` }}>
                <th className="text-left px-4 py-2.5 font-medium" style={{ color: A.text2 }}>Name</th>
                <th className="text-left px-4 py-2.5 font-medium" style={{ color: A.text2 }}>Type</th>
                <th className="text-left px-4 py-2.5 font-medium" style={{ color: A.text2 }}>Options</th>
                <th className="w-20 px-4 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {fields.map((f: any) => (
                <tr key={f.id} style={{ borderBottom: `1px solid ${A.border}` }} className="hover:opacity-80">
                  <td className="px-4 py-2.5 font-medium" style={{ color: A.text1 }}>{f.name}</td>
                  <td className="px-4 py-2.5">
                    <span className="px-2 py-0.5 rounded text-xs font-medium" style={{ background: A.blueBg, color: A.blue }}>
                      {FIELD_TYPES.find(t => t.value === f.field_type)?.label || f.field_type}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs" style={{ color: A.text2 }}>
                    {(f.options_json || []).length > 0 ? (f.options_json as string[]).join(', ') : '—'}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-1">
                      <button onClick={() => openEdit(f)} className="p-1 rounded hover:opacity-70" style={{ color: A.text2 }}>
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => handleDelete(f.id)} className="p-1 rounded hover:opacity-70" style={{ color: '#ef4444' }}>
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create / Edit Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.5)' }}>
          <div className="rounded-xl p-6 w-[420px] space-y-4" style={{ background: A.surface, border: `1px solid ${A.border}` }}>
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold" style={{ color: A.text1 }}>
                {editingField ? 'Edit Field' : 'New Custom Field'}
              </h3>
              <button onClick={() => setShowCreate(false)} className="p-1 rounded hover:opacity-70" style={{ color: A.text2 }}>
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="block text-xs font-medium mb-1" style={{ color: A.text2 }}>Field Name</label>
              <input
                value={formName}
                onChange={e => setFormName(e.target.value)}
                placeholder="e.g. Industry, Revenue, Website"
                className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                style={{ background: A.bg, border: `1px solid ${A.border}`, color: A.text1 }}
              />
            </div>

            <div>
              <label className="block text-xs font-medium mb-1" style={{ color: A.text2 }}>Field Type</label>
              <select
                value={formType}
                onChange={e => setFormType(e.target.value)}
                className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                style={{ background: A.bg, border: `1px solid ${A.border}`, color: A.text1 }}
              >
                {FIELD_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>

            {(formType === 'select' || formType === 'multi_select') && (
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: A.text2 }}>Options (one per line)</label>
                <textarea
                  value={formOptions}
                  onChange={e => setFormOptions(e.target.value)}
                  rows={4}
                  placeholder={"Option 1\nOption 2\nOption 3"}
                  className="w-full px-3 py-2 rounded-lg text-sm outline-none resize-none"
                  style={{ background: A.bg, border: `1px solid ${A.border}`, color: A.text1 }}
                />
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-1.5 rounded-lg text-sm"
                style={{ color: A.text2, border: `1px solid ${A.border}` }}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-1.5 rounded-lg text-sm font-medium text-white flex items-center gap-1.5"
                style={{ background: A.blue, opacity: saving ? 0.7 : 1 }}
              >
                {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                {editingField ? 'Save Changes' : 'Create Field'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════
// Info Tab
// ══════════════════════════════════════════════════════════════════════

function NotificationBotSection({ toast }: { toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) {
  const [botInfo, setBotInfo] = useState<{ bot_username: string | null; deep_link: string | null; subscribers_count: number } | null>(null);
  const [subs, setSubs] = useState<Array<{
    id: number; chat_id: string; username: string | null; first_name: string | null;
    notify_mode: string; daily_digest: boolean; digest_hour: number;
    campaign_ids: number[] | null; is_active: boolean; created_at: string | null;
  }>>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [info, list] = await Promise.all([
        telegramOutreachApi.getNotifBotInfo(),
        telegramOutreachApi.listNotifSubscribers(),
      ]);
      setBotInfo(info);
      setSubs(list);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleToggle = async (sub: typeof subs[0]) => {
    try {
      await telegramOutreachApi.updateNotifSubscriber(sub.id, { is_active: !sub.is_active });
      setSubs(prev => prev.map(s => s.id === sub.id ? { ...s, is_active: !s.is_active } : s));
      toast(sub.is_active ? 'Paused' : 'Activated', 'success');
    } catch { toast('Failed', 'error'); }
  };

  const handleModeChange = async (sub: typeof subs[0], mode: string) => {
    try {
      await telegramOutreachApi.updateNotifSubscriber(sub.id, { notify_mode: mode });
      setSubs(prev => prev.map(s => s.id === sub.id ? { ...s, notify_mode: mode } : s));
    } catch { toast('Failed', 'error'); }
  };

  const handleDigestToggle = async (sub: typeof subs[0]) => {
    try {
      await telegramOutreachApi.updateNotifSubscriber(sub.id, { daily_digest: !sub.daily_digest });
      setSubs(prev => prev.map(s => s.id === sub.id ? { ...s, daily_digest: !s.daily_digest } : s));
    } catch { toast('Failed', 'error'); }
  };

  const handleDelete = async (sub: typeof subs[0]) => {
    try {
      await telegramOutreachApi.deleteNotifSubscriber(sub.id);
      setSubs(prev => prev.filter(s => s.id !== sub.id));
      toast('Removed', 'success');
    } catch { toast('Failed', 'error'); }
  };

  const handleTest = async () => {
    try {
      const res = await telegramOutreachApi.sendTestNotification();
      toast(`Test sent to ${res.sent}/${res.total} subscribers`, 'success');
    } catch { toast('Failed to send test', 'error'); }
  };

  const sectionStyle: React.CSSProperties = { borderRadius: 12, border: `1px solid ${A.border}`, padding: 20, background: A.surface };
  const modeLabels: Record<string, string> = { all: 'All replies', interested: 'Interested only', new_only: 'First reply only' };

  if (loading) return <div className="text-center py-8 text-[13px]" style={{ color: A.text3 }}>Loading...</div>;

  return (
    <div className="space-y-3" style={sectionStyle}>
      <div className="flex items-center justify-between">
        <h2 className="text-[15px] font-semibold" style={{ color: A.text1 }}>Notification Bot</h2>
        <div className="flex gap-2">
          {botInfo?.deep_link && (
            <a href={botInfo.deep_link} target="_blank" rel="noreferrer"
              className="px-3 py-1.5 rounded-lg text-[12px] font-medium text-white"
              style={{ background: A.blue }}>
              Connect via Telegram
            </a>
          )}
          <button onClick={handleTest}
            className="px-3 py-1.5 rounded-lg text-[12px] font-medium border"
            style={{ borderColor: A.border, color: A.text2 }}>
            Send Test
          </button>
        </div>
      </div>

      <p className="text-[13px]" style={{ color: A.text2 }}>
        Get notified in Telegram when prospects reply to outreach campaigns. Reply directly to respond.
      </p>

      {botInfo?.bot_username && (
        <p className="text-[12px]" style={{ color: A.text3 }}>
          Bot: <b>@{botInfo.bot_username}</b> &middot; {botInfo.subscribers_count} subscriber{botInfo.subscribers_count !== 1 ? 's' : ''}
        </p>
      )}

      {subs.length === 0 ? (
        <p className="text-[13px] py-4 text-center" style={{ color: A.text3 }}>
          No subscribers yet. Click "Connect via Telegram" to start receiving notifications.
        </p>
      ) : (
        <div className="space-y-2 mt-2">
          {subs.map(sub => (
            <div key={sub.id} className="flex items-center gap-3 px-3 py-2.5 rounded-lg border"
              style={{ borderColor: A.border, opacity: sub.is_active ? 1 : 0.5 }}>
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-medium" style={{ color: A.text1 }}>
                  {sub.first_name || 'Unknown'} {sub.username ? `(@${sub.username})` : ''}
                </div>
                <div className="text-[11px] mt-0.5" style={{ color: A.text3 }}>
                  {modeLabels[sub.notify_mode] || sub.notify_mode}
                  {sub.daily_digest && ' · Digest ON'}
                  {!sub.is_active && ' · Paused'}
                </div>
              </div>
              <select value={sub.notify_mode} onChange={e => handleModeChange(sub, e.target.value)}
                className="text-[11px] px-2 py-1 rounded border bg-transparent"
                style={{ borderColor: A.border, color: A.text2 }}>
                <option value="all">All replies</option>
                <option value="interested">Interested only</option>
                <option value="new_only">First reply only</option>
              </select>
              <button onClick={() => handleDigestToggle(sub)}
                className="text-[11px] px-2 py-1 rounded border"
                style={{ borderColor: A.border, color: sub.daily_digest ? A.teal : A.text3, background: sub.daily_digest ? A.tealBg : 'transparent' }}>
                Digest
              </button>
              <button onClick={() => handleToggle(sub)}
                className="text-[11px] px-2 py-1 rounded border"
                style={{ borderColor: A.border, color: sub.is_active ? A.text2 : A.teal }}>
                {sub.is_active ? 'Pause' : 'Activate'}
              </button>
              <button onClick={() => handleDelete(sub)}
                className="text-[11px] px-1.5 py-1 rounded hover:bg-red-50">
                <Trash2 size={13} style={{ color: A.rose }} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function InfoTab({ t: _t, toast }: { t: any; toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) { void _t;
  const sectionStyle: React.CSSProperties = { borderRadius: 12, border: `1px solid ${A.border}`, padding: 20, background: A.surface };
  const sectionCls = 'space-y-3';
  const h2Cls = 'text-[15px] font-semibold';
  const h3Cls = 'text-[13px] font-semibold mt-3';
  const pCls = 'text-[13px] leading-relaxed';
  const liCls = 'text-[13px]';
  const codeCls = 'text-[12px] px-1.5 py-0.5 rounded';

  return (
    <div className="max-w-4xl mx-auto space-y-5" style={{ color: A.text2 }}>
      {/* ── Notification Bot ── */}
      <NotificationBotSection toast={toast} />

      {/* ── Accounts ── */}
      <div className={sectionCls} style={sectionStyle}>
        <h2 className={h2Cls} style={{ color: A.text1 }}>Accounts</h2>
        <p className={pCls}>Управление Telegram-аккаунтами для рассылки. Каждый аккаунт = отдельная Telethon-сессия.</p>

        <h3 className={h3Cls} style={{ color: A.text1 }}>Кнопки</h3>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}><b>Add</b> — добавить аккаунт вручную (phone + session string)</li>
          <li className={liCls}><b>Import</b> — массовый импорт из TeleRaptor JSON (session + proxy + device)</li>
          <li className={liCls}><b>Export CSV</b> — выгрузка всех аккаунтов в CSV</li>
          <li className={liCls}><b>Select All</b> — выделить все для bulk-операций</li>
          <li className={liCls}><b>Фильтры</b> (All / Active / Spam / Dead) — быстрая фильтрация по статусу</li>
        </ul>

        <h3 className={h3Cls} style={{ color: A.text1 }}>Bulk Actions (при выделении аккаунтов)</h3>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}><b>Randomize Names</b> — случайные имена по категории (мужские/женские, EN/PT/RU)</li>
          <li className={liCls}><b>Set Bio</b> — массовая установка описания профиля (напр. "BDM at Company")</li>
          <li className={liCls}><b>Set Photo</b> — загрузка аватарок (распределяются рандомно по аккаунтам)</li>
          <li className={liCls}><b>Randomize Device</b> — рандомные параметры устройства (model, version, app)</li>
          <li className={liCls}><b>Set Limit</b> — дневной лимит сообщений на аккаунт</li>
          <li className={liCls}><b>Set Language</b> — язык и системный язык аккаунта (для маскировки гео)</li>
          <li className={liCls}><b>Set 2FA</b> — установка пароля двухфакторной аутентификации</li>
          <li className={liCls}><b>Assign Proxy</b> — привязка к группе прокси (round-robin внутри группы)</li>
          <li className={liCls}><b>Авто-синк</b> — при изменении имени, био, фото — автоматически синхронизируется в Telegram</li>
          <li className={liCls}><b>Privacy</b> — настройки приватности (last online, phone, photo, messages)</li>
          <li className={liCls}><b>Re-Auth</b> — повторная авторизация сессии</li>
          <li className={liCls}><b>Revoke Sessions</b> — отзыв всех других сессий аккаунта</li>
          <li className={liCls}><b>Clean</b> — очистка диалогов и контактов аккаунта</li>
          <li className={liCls}><b>Alive?</b> — быстрая проверка что аккаунт живой (connect + authorized). Безопасно запускать часто. Также подтягивает telegram_user_id и возраст аккаунта</li>
          <li className={liCls}><b>Spam?</b> — полная проверка на спамблок через @SpamBot. НЕ запускать часто — вызывает подозрения у Telegram</li>
          <li className={liCls}><b>Delete</b> — удаление выбранных аккаунтов из системы</li>
        </ul>

        <h3 className={h3Cls} style={{ color: A.text1 }}>Статусы аккаунтов</h3>
        <ul className="space-y-1 list-disc list-inside">
          <li className={liCls}><span className={codeCls}>active</span> — рабочий, участвует в рассылке</li>
          <li className={liCls}><span className={codeCls}>paused</span> — на паузе, не отправляет</li>
          <li className={liCls}><span className={codeCls}>spamblocked</span> — получил спамблок от Telegram (temporary/permanent)</li>
          <li className={liCls}><span className={codeCls}>banned</span> — перманентный бан (Abuse Notifications / жалобы)</li>
          <li className={liCls}><span className={codeCls}>dead</span> — аккаунт мертв (удален, сессия невалидна)</li>
          <li className={liCls}><span className={codeCls}>frozen</span> — заморожен (нужна верификация)</li>
        </ul>

        <h3 className={h3Cls} style={{ color: A.text1 }}>Таблица аккаунтов</h3>
        <p className={pCls}>Аватар, телефон (клик = копировать), гео-флаг, username, статус, возраст сессии, отправлено сегодня/лимит, имя. Клик на строку = модалка редактирования.</p>
      </div>

      {/* ── Campaigns ── */}
      <div className={sectionCls} style={sectionStyle}>
        <h2 className={h2Cls} style={{ color: A.text1 }}>Campaigns</h2>
        <p className={pCls}>Создание и управление рассылочными кампаниями. Кампания = набор аккаунтов + последовательность сообщений + список получателей.</p>

        <h3 className={h3Cls} style={{ color: A.text1 }}>Кнопки</h3>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}><b>New Campaign</b> — создать новую кампанию (имя → переход на страницу настройки)</li>
          <li className={liCls}><b>Refresh</b> — обновить список кампаний</li>
        </ul>

        <h3 className={h3Cls} style={{ color: A.text1 }}>Карточка кампании</h3>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}><b>Play / Pause</b> — запуск или пауза рассылки</li>
          <li className={liCls}><b>Delete</b> — удалить кампанию</li>
          <li className={liCls}>Отображает: статус, кол-во аккаунтов, получателей, отправлено сегодня / всего</li>
        </ul>

        <h3 className={h3Cls} style={{ color: A.text1 }}>Внутри кампании (Campaign Detail)</h3>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}><b>Settings</b> — лимит/день, часы отправки, таймзона, задержки между сообщениями, порог спамблоков</li>
          <li className={liCls}><b>Sequence</b> — цепочка follow-up сообщений с задержками. Каждый шаг может иметь A/B варианты (spintax)</li>
          <li className={liCls}><b>Recipients</b> — список получателей (@username). Импорт из CSV / textarea. Статусы: pending → in_sequence → replied / completed / failed</li>
          <li className={liCls}><b>Messages</b> — лог отправленных сообщений с результатами (sent / failed / spamblocked)</li>
          <li className={liCls}><b>Replies</b> — входящие ответы от получателей</li>
          <li className={liCls}><b>AutoReply</b> — AI автоответчик (Gemini) для автоматических ответов на входящие</li>
          <li className={liCls}><b>Preview</b> — предпросмотр рендеринга сообщения с подстановкой переменных</li>
        </ul>

        <h3 className={h3Cls} style={{ color: A.text1 }}>Статусы кампании</h3>
        <ul className="space-y-1 list-disc list-inside">
          <li className={liCls}><span className={codeCls}>draft</span> — черновик, не отправляет</li>
          <li className={liCls}><span className={codeCls}>active</span> — рассылка идет (worker отправляет сообщения)</li>
          <li className={liCls}><span className={codeCls}>paused</span> — на паузе</li>
          <li className={liCls}><span className={codeCls}>completed</span> — все получатели обработаны</li>
        </ul>
      </div>

      {/* ── Proxies ── */}
      <div className={sectionCls} style={sectionStyle}>
        <h2 className={h2Cls} style={{ color: A.text1 }}>Proxies</h2>
        <p className={pCls}>Управление прокси-серверами для маскировки IP аккаунтов. Прокси группируются — аккаунты привязываются к группе.</p>

        <h3 className={h3Cls} style={{ color: A.text1 }}>Кнопки</h3>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}><b>Create Group</b> — создать группу прокси (имя, страна, описание)</li>
          <li className={liCls}><b>Add Proxy</b> — добавить прокси в группу (host:port, протокол, логин/пароль)</li>
          <li className={liCls}><b>Bulk Add</b> — массовый импорт прокси (формат: host:port:user:pass, по одному на строку)</li>
          <li className={liCls}><b>Health Check</b> — проверка работоспособности всех прокси в группе. Мертвые удаляются автоматически</li>
          <li className={liCls}><b>Delete</b> — удалить прокси или группу</li>
        </ul>

        <h3 className={h3Cls} style={{ color: A.text1 }}>Протоколы</h3>
        <ul className="space-y-1 list-disc list-inside">
          <li className={liCls}><span className={codeCls}>socks5</span> — основной, поддерживается Telethon нативно</li>
          <li className={liCls}><span className={codeCls}>http</span> — HTTP CONNECT proxy</li>
          <li className={liCls}><span className={codeCls}>mtproto</span> — MTProto proxy (Telegram-native)</li>
        </ul>
      </div>

      {/* ── Parser ── */}
      <div className={sectionCls} style={sectionStyle}>
        <h2 className={h2Cls} style={{ color: A.text1 }}>Parser</h2>
        <p className={pCls}>Парсинг аудитории из Telegram-чатов и групп для формирования базы получателей.</p>

        <h3 className={h3Cls} style={{ color: A.text1 }}>Возможности</h3>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}><b>Parse Group</b> — парсинг участников из Telegram-группы/чата по ссылке</li>
          <li className={liCls}><b>Export</b> — экспорт спарсенной аудитории в CSV для импорта в кампании</li>
          <li className={liCls}><b>Dedup</b> — дедупликация по username (исключение уже контактированных)</li>
        </ul>
      </div>

      {/* ── CRM ── */}
      <div className={sectionCls} style={sectionStyle}>
        <h2 className={h2Cls} style={{ color: A.text1 }}>CRM</h2>
        <p className={pCls}>Единая база контактов из всех Telegram-кампаний. Контакт создается автоматически при первой отправке сообщения.</p>

        <h3 className={h3Cls} style={{ color: A.text1 }}>Pipeline (воронка)</h3>
        <ul className="space-y-1 list-disc list-inside">
          <li className={liCls}><span className={codeCls}>cold</span> — новый контакт, еще не написали</li>
          <li className={liCls}><span className={codeCls}>contacted</span> — сообщение отправлено</li>
          <li className={liCls}><span className={codeCls}>replied</span> — получен ответ</li>
          <li className={liCls}><span className={codeCls}>qualified</span> — квалифицирован (подходит под ICP)</li>
          <li className={liCls}><span className={codeCls}>meeting_set</span> — встреча назначена</li>
          <li className={liCls}><span className={codeCls}>converted</span> — конвертирован в клиента</li>
          <li className={liCls}><span className={codeCls}>not_interested</span> — не заинтересован</li>
        </ul>

        <h3 className={h3Cls} style={{ color: A.text1 }}>Функции</h3>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}><b>Фильтр по статусу</b> — клик на карточку статуса = фильтрация таблицы</li>
          <li className={liCls}><b>Bulk Status</b> — массовое изменение статуса выбранных контактов</li>
          <li className={liCls}><b>Карточка контакта</b> — клик по строке: username, имя, компания, статус, история сообщений и ответов</li>
          <li className={liCls}><b>Sent / Replies</b> — сколько сообщений отправлено и получено ответов</li>
          <li className={liCls}><b>Campaigns</b> — в каких кампаниях участвовал контакт</li>
        </ul>
      </div>

      {/* ── Worker ── */}
      <div className={sectionCls} style={sectionStyle}>
        <h2 className={h2Cls} style={{ color: A.text1 }}>Sending Worker</h2>
        <p className={pCls}>Фоновый процесс, который выполняет рассылку. Индикатор статуса в правом верхнем углу (зеленый = работает).</p>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}>Отправляет сообщения по расписанию кампании (часы, таймзона, задержки)</li>
          <li className={liCls}>Round-robin по аккаунтам кампании</li>
          <li className={liCls}>Поддержка spintax: <span className={codeCls}>{'{'}Hi|Hello|Hey{'}'}</span> → рандомный вариант</li>
          <li className={liCls}>Переменные: <span className={codeCls}>{'{'}first_name{'}'}</span>, <span className={codeCls}>{'{'}username{'}'}</span>, <span className={codeCls}>{'{'}company{'}'}</span></li>
          <li className={liCls}>Автопауза при спамблоке (пропускает аккаунт, пишет лог)</li>
          <li className={liCls}>Авто-пересчет отправленных сегодня (daily_message_limit)</li>
        </ul>
      </div>

      {/* ── Reply Detection ── */}
      <div className={sectionCls} style={sectionStyle}>
        <h2 className={h2Cls} style={{ color: A.text1 }}>Reply Detection</h2>
        <p className={pCls}>Мониторинг входящих ответов от получателей кампаний.</p>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}>Фоновый процесс проверяет все аккаунты на новые входящие DM</li>
          <li className={liCls}>Ответы привязываются к получателю и кампании</li>
          <li className={liCls}>Статус получателя автоматически меняется на <span className={codeCls}>replied</span></li>
          <li className={liCls}>CRM-контакт обновляется: total_replies_received + 1, last_reply_at</li>
          <li className={liCls}>AI AutoReply (Gemini) может отвечать автоматически если настроен</li>
        </ul>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Inbox Tab
// ══════════════════════════════════════════════════════════════════════

function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '';
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  if (diffMs < 0) return 'just now';
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return 'just now';
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h`;
  const d = new Date(dateStr);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) return 'yesterday';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function AccountAnalytics({ accountId }: { accountId: number }) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState<'7d' | '30d'>('7d');
  useEffect(() => {
    setLoading(true);
    telegramOutreachApi.getAccountAnalytics(accountId)
      .then(d => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [accountId]);

  if (loading) return <div className="flex justify-center py-4"><Loader2 className="w-4 h-4 animate-spin" style={{ color: A.text3 }} /></div>;
  if (!data) return null;

  const sent = range === '7d' ? data.sent_7d : data.sent_30d;
  const replies = range === '7d' ? data.replies_7d : data.replies_30d;
  const errors = range === '7d' ? data.errors_7d : data.errors_30d;

  // Filter chart data by selected range
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - (range === '7d' ? 7 : 30));
  const chartData = (data.daily || []).filter((d: any) => new Date(d.date) >= cutoff);

  return (
    <div className="rounded-lg p-3 space-y-3" style={{ border: `1px solid ${A.border}` }}>
      {/* Toggle */}
      <div className="flex items-center justify-between">
        <p className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: A.text3 }}>Analytics</p>
        <div className="flex rounded-md overflow-hidden border" style={{ borderColor: A.border }}>
          {(['7d', '30d'] as const).map(r => (
            <button key={r} onClick={() => setRange(r)}
              className="px-3 py-1 text-[11px] font-medium transition-colors"
              style={{
                background: range === r ? A.blue : 'transparent',
                color: range === r ? '#fff' : A.text3,
                cursor: 'pointer', border: 'none',
              }}>
              {r === '7d' ? '7 days' : '30 days'}
            </button>
          ))}
        </div>
      </div>
      {/* Summary row */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-lg font-bold" style={{ color: A.blue, fontVariantNumeric: 'tabular-nums' }}>{sent}</div>
          <div className="text-[10px]" style={{ color: A.text3 }}>Sent</div>
        </div>
        <div>
          <div className="text-lg font-bold" style={{ color: '#22C55E', fontVariantNumeric: 'tabular-nums' }}>{replies}</div>
          <div className="text-[10px]" style={{ color: A.text3 }}>Replies</div>
        </div>
        <div>
          <div className="text-lg font-bold" style={{ color: '#EF4444', fontVariantNumeric: 'tabular-nums' }}>{errors}</div>
          <div className="text-[10px]" style={{ color: A.text3 }}>Spamblock</div>
        </div>
      </div>
      {/* Chart */}
      {chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={range === '7d' ? 100 : 140}>
          <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
            <XAxis dataKey="date" tick={{ fontSize: 9, fill: A.text3 }} tickFormatter={(v: string) => { const d = new Date(v); return `${d.getDate()}/${d.getMonth()+1}`; }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 9, fill: A.text3 }} allowDecimals={false} />
            <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8, border: `1px solid ${A.border}` }} />
            <Area type="monotone" dataKey="sent" stroke={A.blue} fill={A.blueBg} strokeWidth={1.5} name="Sent" />
            <Area type="monotone" dataKey="replies" stroke="#22C55E" fill="#DCFCE7" strokeWidth={1.5} name="Replies" />
            <Area type="monotone" dataKey="spamblocked" stroke="#EF4444" fill="#FEE2E2" strokeWidth={1.5} name="Spamblock" />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

const TAG_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  interested:         { bg: '#ECFDF5', text: '#0D9488', border: '#99F6E4' },
  info_requested:     { bg: '#FFFBEB', text: '#D97706', border: '#FDE68A' },
  not_interested:     { bg: '#FFF1F2', text: '#E05D6F', border: '#FECDD3' },
  meeting_set:        { bg: '#EFF6FF', text: '#2563EB', border: '#BFDBFE' },
};

function DialogAvatar({ name, peerId, accountId }: { name: string; peerId: number; accountId?: number }) {
  const initials = name?.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() || '?';
  const hue = (peerId || 0) % 360;
  const [imgError, setImgError] = useState(false);
  const photoUrl = accountId && peerId ? `/api/telegram-dm/accounts/${accountId}/peer-photo/${peerId}` : null;
  return (
    <div className="w-10 h-10 rounded-full flex-shrink-0 overflow-hidden flex items-center justify-center text-white text-xs font-semibold"
         style={{ backgroundColor: `hsl(${hue}, 45%, 55%)` }}>
      {photoUrl && !imgError ? (
        <img src={photoUrl} alt="" className="w-full h-full object-cover"
             onError={() => setImgError(true)} />
      ) : initials}
    </div>
  );
}

const DRAFT_PREFIX = 'inbox_draft_';
const DRAFT_TTL = 24 * 60 * 60 * 1000; // 24 hours

function InboxTab({ toast }: { toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) {
  const currentProject = useAppStore(s => s.currentProject);
  const [dialogs, setDialogs] = useState<any[]>([]);
  const [selectedDialog, setSelectedDialog] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [messageText, setMessageText] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [filterAccount, setFilterAccount] = useState<string>('');
  const [filterCampaign, setFilterCampaign] = useState<string>('');
  const [filterTag, setFilterTag] = useState<string>('');
  const [search, setSearch] = useState('');
  const [applied, setApplied] = useState(false);
  const [showCrmInfo, setShowCrmInfo] = useState(false);
  const [crmData, setCrmData] = useState<any>(null);
  const [crmLoading, setCrmLoading] = useState(false);
  const [crmCustomFields, setCrmCustomFields] = useState<any[]>([]);
  const [crmFieldDefs, setCrmFieldDefs] = useState<any[]>([]);
  const [peerStatus, setPeerStatus] = useState<any>(null);
  const [peerTyping, setPeerTyping] = useState(false);
  const [filterLeadStatus, setFilterLeadStatus] = useState<string>('');
  const [campaignTags, setCampaignTags] = useState<string[]>([]);
  const [accountTags, setAccountTags] = useState<{ id: number; name: string }[]>([]);
  const [filterAccountTag, setFilterAccountTag] = useState<string>('');
  const [showTemplates, setShowTemplates] = useState(false);
  // Context menu, reply, selection
  const [ctxMenu, setCtxMenu] = useState<{ x: number; y: number; msg: any } | null>(null);
  const [replyTo, setReplyTo] = useState<any>(null);
  const [editingMsg, setEditingMsg] = useState<any>(null);
  const [deleteModal, setDeleteModal] = useState<any>(null);
  const [selectMode, setSelectMode] = useState(false);
  const [selectedMsgs, setSelectedMsgs] = useState<Set<number>>(new Set());
  const [attachedFile, setAttachedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [customTemplates, setCustomTemplates] = useState<{ label: string; text: string }[]>(() => {
    try { return JSON.parse(localStorage.getItem('inbox_custom_templates') || '[]'); } catch { return []; }
  });
  const [showSaveTemplate, setShowSaveTemplate] = useState(false);
  const [forwardPopup, setForwardPopup] = useState<{ msgIds: number[] } | null>(null);
  const [forwardSearch, setForwardSearch] = useState('');
  const [forwardDialogs, setForwardDialogs] = useState<any[]>([]);
  const [showStatusDropdown, setShowStatusDropdown] = useState(false);
  const statusDropdownRef = useRef<HTMLDivElement>(null);
  const [showNotes, setShowNotes] = useState(false);
  const notesRef = useRef<HTMLDivElement>(null);
  const [dialogNotes, setDialogNotes] = useState<Record<number, string>>(() => {
    try {
      const raw = localStorage.getItem('inbox_dialog_notes');
      return raw ? JSON.parse(raw) : {};
    } catch { return {}; }
  });
  const [showNewChat, setShowNewChat] = useState(false);
  const [newChatUsername, setNewChatUsername] = useState('');
  const [newChatLoading, setNewChatLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const editorRef = useRef<HTMLDivElement>(null);
  const templateRef = useRef<HTMLDivElement>(null);
  const [linkPopup, setLinkPopup] = useState<{ url: string } | null>(null);
  const savedRangeRef = useRef<Range | null>(null);

  // Drafts: per-dialog text saved in localStorage with 24h TTL
  const [drafts, setDrafts] = useState<Record<number, string>>(() => {
    const d: Record<number, string> = {};
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key?.startsWith(DRAFT_PREFIX)) {
        try {
          const val = JSON.parse(localStorage.getItem(key) || '');
          if (Date.now() - val.ts <= DRAFT_TTL) {
            d[Number(key.slice(DRAFT_PREFIX.length))] = val.text;
          } else {
            localStorage.removeItem(key);
          }
        } catch {}
      }
    }
    return d;
  });

  const saveDraft = (dialogId: number) => {
    const text = editorRef.current?.textContent || '';
    const html = editorRef.current?.innerHTML || '';
    if (!text.trim()) {
      localStorage.removeItem(`${DRAFT_PREFIX}${dialogId}`);
      setDrafts(prev => { const n = { ...prev }; delete n[dialogId]; return n; });
      return;
    }
    localStorage.setItem(`${DRAFT_PREFIX}${dialogId}`, JSON.stringify({ text, html, ts: Date.now() }));
    setDrafts(prev => ({ ...prev, [dialogId]: text }));
  };

  const restoreDraft = (dialogId: number) => {
    try {
      const raw = localStorage.getItem(`${DRAFT_PREFIX}${dialogId}`);
      if (!raw) { setMessageText(''); if (editorRef.current) editorRef.current.innerHTML = ''; return; }
      const d = JSON.parse(raw);
      if (Date.now() - d.ts > DRAFT_TTL) {
        localStorage.removeItem(`${DRAFT_PREFIX}${dialogId}`);
        setDrafts(prev => { const n = { ...prev }; delete n[dialogId]; return n; });
        setMessageText(''); if (editorRef.current) editorRef.current.innerHTML = '';
        return;
      }
      setMessageText(d.text);
      if (editorRef.current) editorRef.current.innerHTML = d.html;
    } catch {
      setMessageText(''); if (editorRef.current) editorRef.current.innerHTML = '';
    }
  };

  const clearDraft = (dialogId: number) => {
    localStorage.removeItem(`${DRAFT_PREFIX}${dialogId}`);
    setDrafts(prev => { const n = { ...prev }; delete n[dialogId]; return n; });
  };

  const saveCustomTemplate = (label: string, text: string) => {
    const updated = [...customTemplates, { label, text }];
    setCustomTemplates(updated);
    localStorage.setItem('inbox_custom_templates', JSON.stringify(updated));
  };
  const deleteCustomTemplate = (idx: number) => {
    const updated = customTemplates.filter((_: any, i: number) => i !== idx);
    setCustomTemplates(updated);
    localStorage.setItem('inbox_custom_templates', JSON.stringify(updated));
  };

  const exitSelectMode = () => { setSelectMode(false); setSelectedMsgs(new Set()); };
  const handleBulkCopy = () => {
    const texts = messages.filter((m: any) => selectedMsgs.has(m.id)).map((m: any) => m.text || '').join('\n\n');
    navigator.clipboard.writeText(texts);
    toast(`Copied ${selectedMsgs.size} messages`, 'success');
    exitSelectMode();
  };
  const handleBulkDelete = async (revoke: boolean) => {
    if (!selectedDialog) return;
    for (const mid of selectedMsgs) {
      try { await telegramOutreachApi.deleteDialogMessage(selectedDialog.id, mid, revoke); } catch { /* skip */ }
    }
    toast(`Deleted ${selectedMsgs.size} messages`, 'success');
    exitSelectMode();
    const data = await telegramOutreachApi.getDialogMessages(selectedDialog.id, 30);
    setMessages(data.messages || data || []);
  };

  const REPLY_TEMPLATES = [
    { label: 'Greeting', text: 'Hi! Thanks for your response. How can I help?' },
    { label: 'Meeting', text: 'Would you be available for a quick call this week?' },
    { label: 'Info', text: "Sure, I'll send you more details shortly." },
    { label: 'Follow up', text: 'Just following up on my previous message. Any thoughts?' },
    { label: 'Not interested', text: 'No problem, thanks for letting me know!' },
  ];

  // Close context menu on click anywhere
  useEffect(() => {
    if (!ctxMenu) return;
    const h = () => setCtxMenu(null);
    document.addEventListener('click', h);
    return () => document.removeEventListener('click', h);
  }, [ctxMenu]);

  // Close templates popup on outside click
  useEffect(() => {
    if (!showTemplates) return;
    const handler = (e: MouseEvent) => {
      if (templateRef.current && !templateRef.current.contains(e.target as Node)) {
        setShowTemplates(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showTemplates]);

  // Close status dropdown on outside click
  useEffect(() => {
    if (!showStatusDropdown) return;
    const handler = (e: MouseEvent) => {
      if (statusDropdownRef.current && !statusDropdownRef.current.contains(e.target as Node)) {
        setShowStatusDropdown(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showStatusDropdown]);

  // Close notes popup on outside click
  useEffect(() => {
    if (!showNotes) return;
    const handler = (e: MouseEvent) => {
      if (notesRef.current && !notesRef.current.contains(e.target as Node)) {
        setShowNotes(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showNotes]);

  // Save notes to localStorage whenever they change
  const saveNote = useCallback((dialogId: number, text: string) => {
    setDialogNotes(prev => {
      const next = { ...prev, [dialogId]: text };
      if (!text.trim()) delete next[dialogId];
      localStorage.setItem('inbox_dialog_notes', JSON.stringify(next));
      return next;
    });
  }, []);

  // Load campaigns & accounts & campaign tags & account tags on mount
  useEffect(() => {
    (async () => {
      try {
        const [cRes, aRes, tags, aTags] = await Promise.all([
          telegramOutreachApi.listCampaigns(),
          telegramOutreachApi.listInboxAccounts(),
          telegramOutreachApi.listCampaignTags().catch(() => []),
          telegramOutreachApi.listTags().catch(() => []),
        ]);
        setCampaigns(cRes.items || []);
        setAccounts(aRes || []);
        setCampaignTags(tags || []);
        setAccountTags(aTags || []);
      } catch { /* ignore */ }
    })();
  }, []);

  // Filter accounts by selected campaign and account tag
  const filteredAccounts = useMemo(() => {
    let list = accounts;
    if (filterCampaign) {
      const cid = Number(filterCampaign);
      list = list.filter((a: any) => a.campaign_ids?.includes(cid));
    }
    if (filterAccountTag) {
      list = list.filter((a: any) => a.tag_names?.includes(filterAccountTag));
    }
    return list;
  }, [accounts, filterCampaign, filterAccountTag]);

  const accountMap = useMemo(() => {
    const m: Record<string, any> = {};
    for (const a of filteredAccounts) m[String(a.id)] = a;
    return m;
  }, [filteredAccounts]);

  const statusColors: Record<string, string> = { active: '#22c55e', paused: '#f59e0b', spamblocked: '#ef4444', frozen: '#3b82f6', banned: '#dc2626', dead: '#6b7280' };

  // Build filter params helper
  const buildFilterParams = useCallback(() => {
    const params: any = { page: 1, page_size: 100 };
    if (filterAccount) params.account_id = Number(filterAccount);
    if (filterCampaign) params.campaign_id = Number(filterCampaign);
    if (filterTag) params.campaign_tag = filterTag;
    if (filterLeadStatus) params.lead_status = filterLeadStatus;
    if (currentProject?.id) params.project_id = currentProject.id;
    return params;
  }, [filterAccount, filterCampaign, filterTag, filterLeadStatus, currentProject?.id]);

  // Silent refresh — re-fetch dialogs without loading spinner (for auto-polling)
  const silentRefresh = useCallback(async () => {
    try {
      const data = await telegramOutreachApi.listInboxDialogs(buildFilterParams());
      setDialogs(data.items || data || []);
    } catch { /* silent */ }
  }, [buildFilterParams]);

  // Apply handler — syncs from Telegram + loads dialogs
  const handleApply = useCallback(async () => {
    const hasFilter = filterAccount || filterCampaign || filterTag || filterLeadStatus || currentProject?.id;
    if (!hasFilter) {
      toast('Select at least one filter', 'error');
      return;
    }
    setApplied(true);
    setLoading(true);
    try {
      // Trigger sync in background (don't block on it)
      const aid = filterAccount ? Number(filterAccount) : undefined;
      telegramOutreachApi.triggerInboxSync(aid).then(() => {
        // After sync completes, silently refresh dialog list
        silentRefresh();
      }).catch(() => { /* sync failure is non-critical */ });
      // Immediately load cached dialogs
      const data = await telegramOutreachApi.listInboxDialogs(buildFilterParams());
      setDialogs(data.items || data || []);
    } catch {
      toast('Failed to load conversations', 'error');
    } finally {
      setLoading(false);
    }
  }, [filterAccount, filterCampaign, filterTag, filterLeadStatus, toast, buildFilterParams, silentRefresh]);

  // Auto-poll: refresh dialogs every 30s when filters are applied
  useEffect(() => {
    if (!applied) return;
    const interval = setInterval(silentRefresh, 30000);
    return () => clearInterval(interval);
  }, [applied, silentRefresh]);

  // New Chat handler
  const handleNewChat = async () => {
    const username = newChatUsername.trim().replace(/^@/, '');
    if (!username) return;
    if (!filterAccount) {
      toast('Select an account first', 'error');
      return;
    }
    setNewChatLoading(true);
    try {
      const data = await telegramOutreachApi.createNewChat(Number(filterAccount), username);
      // Add to dialogs list if new
      if (data.is_new) {
        setDialogs(prev => [data, ...prev]);
      }
      // Select the dialog
      setSelectedDialog(data);
      setShowNewChat(false);
      setNewChatUsername('');
      if (!data.is_new) {
        toast('Existing conversation opened', 'info');
      }
    } catch (e: any) {
      const detail = e?.response?.data?.detail || 'Failed to start chat';
      toast(detail, 'error');
    } finally {
      setNewChatLoading(false);
    }
  };

  // Load messages + peer status when dialog selected
  useEffect(() => {
    if (!selectedDialog) { setMessages([]); setPeerStatus(null); return; }
    let cancelled = false;
    setLoadingMessages(true);
    setPeerStatus(null);
    (async () => {
      try {
        const data = await telegramOutreachApi.getDialogMessages(selectedDialog.id, 30);
        if (!cancelled) {
          setMessages(data.messages || data || []);
          if (data.peer_status) setPeerStatus(data.peer_status);
        }
      } catch (e: any) {
        if (!cancelled) {
          setMessages([]);
          const status = e?.response?.status;
          const detail = e?.response?.data?.detail || 'Failed to load messages';
          if (status === 401) {
            toast('Session expired — re-authorize the account.', 'error');
          } else if (status === 503) {
            toast('Connection error — please try again.', 'error');
          } else {
            toast(detail, 'error');
          }
        }
      } finally {
        if (!cancelled) setLoadingMessages(false);
      }
    })();
    return () => { cancelled = true; };
  }, [selectedDialog]);

  // Poll typing status every 3s
  useEffect(() => {
    if (!selectedDialog) { setPeerTyping(false); return; }
    setPeerTyping(false);
    const interval = setInterval(async () => {
      try {
        const data = await telegramOutreachApi.getDialogTyping(selectedDialog.id);
        setPeerTyping(data.typing);
      } catch { setPeerTyping(false); }
    }, 3_000);
    return () => { clearInterval(interval); setPeerTyping(false); };
  }, [selectedDialog]);

  // Load CRM data when Info panel is opened
  useEffect(() => {
    if (!showCrmInfo || !selectedDialog) { setCrmData(null); setCrmCustomFields([]); return; }
    let cancelled = false;
    setCrmLoading(true);
    (async () => {
      try {
        const [data, fieldDefs] = await Promise.all([
          telegramOutreachApi.getDialogCrm(selectedDialog.id),
          telegramOutreachApi.listCustomFields(),
        ]);
        if (!cancelled) {
          setCrmData(data.contact);
          setCrmFieldDefs(fieldDefs);
          if (data.contact?.contact_id) {
            const vals = await telegramOutreachApi.getContactCustomFields(data.contact.contact_id);
            if (!cancelled) setCrmCustomFields(vals);
          }
        }
      } catch { if (!cancelled) { setCrmData(null); setCrmCustomFields([]); } }
      finally { if (!cancelled) setCrmLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [showCrmInfo, selectedDialog]);

  // Auto-scroll to bottom when messages load
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Restore draft when switching dialogs
  const prevDialogIdRef = useRef<number | null>(null);
  useEffect(() => {
    if (!selectedDialog) { prevDialogIdRef.current = null; return; }
    if (prevDialogIdRef.current === selectedDialog.id) return;
    prevDialogIdRef.current = selectedDialog.id;
    // Small delay to ensure editor is mounted
    requestAnimationFrame(() => restoreDraft(selectedDialog.id));
  }, [selectedDialog]);

  // ---- Rich-text editor helpers ----
  const editorToTelegramHtml = (node: Node): string => {
    if (node.nodeType === Node.TEXT_NODE) {
      return (node.textContent || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return '';
    const el = node as HTMLElement;
    const tag = el.tagName.toLowerCase();
    const ch = Array.from(el.childNodes).map(editorToTelegramHtml).join('');
    switch (tag) {
      case 'b': case 'strong': return `<b>${ch}</b>`;
      case 'i': case 'em': return `<i>${ch}</i>`;
      case 'u': return `<u>${ch}</u>`;
      case 's': case 'strike': case 'del': return `<s>${ch}</s>`;
      case 'code': return `<code>${ch}</code>`;
      case 'blockquote': return `<blockquote>${ch}</blockquote>`;
      case 'a': return `<a href="${(el.getAttribute('href') || '').replace(/"/g, '&quot;')}">${ch}</a>`;
      case 'span': return el.classList.contains('tg-spoiler') ? `<tg-spoiler>${ch}</tg-spoiler>` : ch;
      case 'br': return '\n';
      case 'div': return '\n' + ch;
      default: return ch;
    }
  };

  const wrapSelectionWith = (tag: string, attrs?: Record<string, string>) => {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return;
    const range = sel.getRangeAt(0);
    if (!editorRef.current?.contains(range.commonAncestorContainer)) return;
    // Toggle off: if already inside this tag, unwrap it
    let node: Node | null = range.commonAncestorContainer;
    while (node && node !== editorRef.current) {
      if (node.nodeType === Node.ELEMENT_NODE) {
        const wrap = node as HTMLElement;
        if (wrap.tagName.toLowerCase() === tag.toLowerCase()) {
          if (tag === 'span' && attrs?.class && !wrap.classList.contains(attrs.class)) {
            node = node.parentNode;
            continue;
          }
          const parent = wrap.parentNode!;
          while (wrap.firstChild) parent.insertBefore(wrap.firstChild, wrap);
          parent.removeChild(wrap);
          return;
        }
      }
      node = node.parentNode;
    }
    // Wrap
    const el = document.createElement(tag);
    if (attrs) Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
    try { range.surroundContents(el); } catch {
      const frag = range.extractContents(); el.appendChild(frag); range.insertNode(el);
    }
    sel.removeAllRanges();
    const nr = document.createRange(); nr.selectNodeContents(el); sel.addRange(nr);
  };

  const showLinkPopup = () => {
    const sel = window.getSelection();
    if (sel && sel.rangeCount > 0) {
      savedRangeRef.current = sel.getRangeAt(0).cloneRange();
      setLinkPopup({ url: '' });
    }
  };

  const applyLink = (url: string) => {
    if (!url || !savedRangeRef.current) { setLinkPopup(null); return; }
    editorRef.current?.focus();
    const sel = window.getSelection();
    if (sel) {
      sel.removeAllRanges();
      sel.addRange(savedRangeRef.current);
      document.execCommand('createLink', false, url);
    }
    savedRangeRef.current = null;
    setLinkPopup(null);
    setMessageText(editorRef.current?.textContent || '');
  };

  const applyFormat = (fmt: string, attrs?: Record<string, string>) => {
    editorRef.current?.focus();
    if (['bold', 'italic', 'underline', 'strikeThrough'].includes(fmt)) {
      document.execCommand(fmt);
    } else if (fmt === 'createLink') {
      showLinkPopup();
      return;
    } else {
      wrapSelectionWith(fmt, attrs);
    }
    setMessageText(editorRef.current?.textContent || '');
  };

  const handleEditorKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape' && editingMsg) { e.preventDefault(); setEditingMsg(null); const ed = editorRef.current; if (ed) ed.innerHTML = ''; setMessageText(''); return; }
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); return; }
    if (e.ctrlKey || e.metaKey) {
      if (e.shiftKey) {
        switch (e.key) {
          case 'X': case 'x': e.preventDefault(); document.execCommand('strikeThrough'); break;
          case '>': e.preventDefault(); wrapSelectionWith('blockquote'); break;
          case 'M': case 'm': e.preventDefault(); wrapSelectionWith('code'); break;
          case 'P': case 'p': e.preventDefault(); wrapSelectionWith('span', { class: 'tg-spoiler' }); break;
        }
      } else {
        switch (e.key.toLowerCase()) {
          case 'b': e.preventDefault(); document.execCommand('bold'); break;
          case 'i': e.preventDefault(); document.execCommand('italic'); break;
          case 'u': e.preventDefault(); document.execCommand('underline'); break;
          case 'k': e.preventDefault(); showLinkPopup(); break;
        }
      }
    }
  };

  const handleEditorPaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    document.execCommand('insertText', false, e.clipboardData.getData('text/plain'));
  };

  const setEditorContent = (text: string) => {
    setMessageText(text);
    if (editorRef.current) editorRef.current.textContent = text;
  };

  // Send handler (supports reply_to + formatting + edit mode)
  const handleSend = async () => {
    if (!selectedDialog || sending) return;
    const hasText = messageText.trim().length > 0;
    const hasFile = !!attachedFile;
    if (!hasText && !hasFile) return;
    setSending(true);
    try {
      const editor = editorRef.current;
      let text = messageText.trim();
      let parseMode: string | undefined;
      if (editor && text) {
        const html = Array.from(editor.childNodes).map(editorToTelegramHtml).join('').replace(/^\n+|\n+$/g, '');
        if (html !== text) { text = html; parseMode = 'html'; }
      }

      if (editingMsg) {
        await telegramOutreachApi.editDialogMessage(selectedDialog.id, editingMsg.id, text, parseMode);
        setEditingMsg(null);
      } else if (hasFile) {
        await telegramOutreachApi.sendDialogFile(selectedDialog.id, attachedFile!, {
          caption: text || undefined,
          parseMode,
          replyTo: replyTo?.id,
        });
        setAttachedFile(null);
      } else {
        await telegramOutreachApi.sendDialogMessage(selectedDialog.id, text, {
          parseMode,
          replyTo: replyTo?.id,
        });
      }

      if (editor) editor.innerHTML = '';
      setMessageText('');
      setReplyTo(null);
      clearDraft(selectedDialog.id);
      const data = await telegramOutreachApi.getDialogMessages(selectedDialog.id, 30);
      setMessages(data.messages || data || []);
      editorRef.current?.focus();
    } catch (e: any) {
      toast(e?.response?.data?.detail || (editingMsg ? 'Failed to edit' : 'Failed to send'), 'error');
    } finally {
      setSending(false);
    }
  };

  // Delete handler
  const handleDeleteMsg = async (msgId: number, revoke: boolean) => {
    if (!selectedDialog) return;
    setDeleteModal(null); // Close popup immediately
    try {
      await telegramOutreachApi.deleteDialogMessage(selectedDialog.id, msgId, revoke);
      const data = await telegramOutreachApi.getDialogMessages(selectedDialog.id, 30);
      setMessages(data.messages || data || []);
      toast('Message deleted', 'success');
    } catch (e: any) {
      toast(e?.response?.data?.detail || 'Delete failed', 'error');
    }
  };

  // React handler
  const handleReact = async (msgId: number, emoji: string) => {
    if (!selectedDialog) return;
    try {
      await telegramOutreachApi.reactDialogMessage(selectedDialog.id, msgId, emoji);
      setCtxMenu(null);
    } catch (e: any) {
      toast(e?.response?.data?.detail || 'Reaction failed', 'error');
    }
  };

  // Tag handler
  const handleTag = async (tag: string) => {
    if (!selectedDialog) return;
    // Toggle: if same tag, clear it
    const newTag = selectedDialog.tag === tag ? '' : tag;
    try {
      await telegramOutreachApi.tagDialog(selectedDialog.id, newTag);
      setSelectedDialog((prev: any) => prev ? { ...prev, tag: newTag || null } : prev);
      setDialogs(prev => prev.map(d =>
        d.id === selectedDialog.id ? { ...d, tag: newTag || null } : d
      ));
      toast(newTag ? `Tagged as ${newTag.replace('_', ' ')}` : 'Tag removed', 'success');
    } catch (e: any) {
      toast(e?.response?.data?.detail || 'Failed to tag', 'error');
    }
  };

  // Local search filter
  const filteredDialogs = search.trim()
    ? dialogs.filter(d => {
        const q = search.toLowerCase();
        return (d.peer_name || '').toLowerCase().includes(q)
          || (d.peer_username || '').toLowerCase().includes(q)
          || (d.name || '').toLowerCase().includes(q)
          || (d.username || '').toLowerCase().includes(q);
      })
    : dialogs;

  // selectCls removed — using StyledSelect component

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-end">
        <Link to="/inbox-v2" className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors" style={{ background: A.blueBg, color: A.blue }}>
          Try new Inbox (beta) <ChevronRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    <div className="flex rounded-xl overflow-hidden" style={{ background: A.surface, border: `1px solid ${A.border}`, height: 'calc(100vh - 250px)', minHeight: 500 }}>
      {/* ── Left panel: Dialog list ── */}
      <div className="flex flex-col" style={{ width: 320, flexShrink: 0, overflow: 'hidden', borderRight: `1px solid ${A.border}` }}>
        {/* Search */}
        <div className="px-3 pt-3 pb-1">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: A.text3 }} />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search by name or username..."
              className="w-full h-8 pl-8 pr-3 rounded-lg border text-xs outline-none"
              style={{ borderColor: A.border, color: A.text1, background: '#F9FAFB' }}
            />
          </div>
        </div>

        {/* Filters */}
        <div className="px-3 pb-3 flex flex-col gap-1.5" style={{ borderBottom: `1px solid ${A.border}` }}>
          {/* Row 1: Account dropdown (filtered by campaign & account tag) */}
          <StyledSelect
            value={filterAccount}
            onChange={setFilterAccount}
            placeholder="Account"
            options={filteredAccounts.map((a: any) => ({ value: String(a.id), label: [a.first_name, a.last_name].filter(Boolean).join(' ') || a.phone || `#${a.id}` }))}
            renderSelected={(opt) => {
              const a = accountMap[opt.value];
              if (!a) return opt.label;
              const name = [a.first_name, a.last_name].filter(Boolean).join(' ');
              const st = a.tg_status || 'active';
              return (
                <span className="flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: statusColors[st] || '#6b7280' }} />
                  <span className="truncate">{name || a.phone}{a.username ? ` @${a.username}` : ''}</span>
                </span>
              );
            }}
            renderOption={(opt, isSel) => {
              const a = accountMap[opt.value];
              if (!a) return opt.label;
              const name = [a.first_name, a.last_name].filter(Boolean).join(' ');
              const st = a.tg_status || 'active';
              return (
                <div className="flex items-start gap-2">
                  <span className="w-2 h-2 rounded-full flex-shrink-0 mt-1" style={{ background: statusColors[st] || '#6b7280' }} />
                  <div className="min-w-0">
                    <div className="font-medium truncate" style={{ color: isSel ? A.blue : A.text1 }}>{name || a.phone || `#${a.id}`}</div>
                    <div className="truncate" style={{ color: A.text3, fontSize: 10 }}>
                      {a.username ? `@${a.username}` : ''}{a.username && a.phone ? ' · ' : ''}{a.phone || ''}{st !== 'active' ? ` · ${st}` : ''}
                    </div>
                  </div>
                </div>
              );
            }}
          />
          {/* Row 2: Campaign + Account Tag */}
          <div className="flex gap-1.5">
            <StyledSelect
              value={filterCampaign}
              onChange={(v) => { setFilterCampaign(v); setFilterAccount(''); }}
              placeholder="Campaign"
              className="flex-1 min-w-0"
              options={campaigns.map((c: any) => ({ value: String(c.id), label: c.name }))}
            />
            {accountTags.length > 0 && (
              <StyledSelect
                value={filterAccountTag}
                onChange={(v) => { setFilterAccountTag(v); setFilterAccount(''); }}
                placeholder="Account Tag"
                className="flex-1 min-w-0"
                options={accountTags.map(t => ({ value: t.name, label: t.name }))}
              />
            )}
          </div>
          {/* Row 3: Lead Status + Campaign Tag */}
          <div className="flex gap-1.5">
            <StyledSelect
              value={filterLeadStatus}
              onChange={setFilterLeadStatus}
              placeholder="Lead Status"
              className="flex-1 min-w-0"
              options={[
                { value: 'cold', label: 'Cold' },
                { value: 'contacted', label: 'Contacted' },
                { value: 'replied', label: 'Replied' },
                { value: 'interested', label: 'Interested' },
                { value: 'qualified', label: 'Qualified' },
                { value: 'meeting_set', label: 'Meeting Set' },
                { value: 'not_interested', label: 'Not Interested' },
              ]}
            />
            {campaignTags.length > 0 && (
              <StyledSelect
                value={filterTag}
                onChange={setFilterTag}
                placeholder="Campaign Tag"
                className="flex-1 min-w-0"
                options={campaignTags.map(t => ({ value: t, label: t }))}
              />
            )}
          </div>
          {/* Row 4: Apply */}
          <div className="flex gap-1.5">
            <button
              onClick={handleApply}
              disabled={loading}
              className="h-8 px-3 rounded-lg text-xs font-semibold text-white transition-colors flex-shrink-0"
              style={{ background: A.blue, cursor: loading ? 'wait' : 'pointer' }}
              onMouseEnter={e => { e.currentTarget.style.background = A.blueHover; }}
              onMouseLeave={e => { e.currentTarget.style.background = A.blue; }}
            >
              {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Apply'}
            </button>
            {filterAccount && (
              <button
                onClick={() => setShowNewChat(true)}
                title="New Chat"
                className="h-8 px-2.5 rounded-lg flex items-center gap-1 border text-xs font-medium transition-colors flex-shrink-0"
                style={{ borderColor: A.border, background: A.surface, color: A.text1 }}
                onMouseEnter={e => { e.currentTarget.style.background = '#F3F4F6'; }}
                onMouseLeave={e => { e.currentTarget.style.background = A.surface; }}
              >
                <Plus className="w-3.5 h-3.5" /> Chat
              </button>
            )}
          </div>
        </div>

        {/* Dialog list */}
        <div className="flex-1 overflow-y-auto">
          {!applied ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 px-6">
              <Filter className="w-7 h-7" style={{ color: A.text3 }} />
              <span className="text-xs text-center" style={{ color: A.text3, lineHeight: '1.5' }}>
                Select account, campaign, or tag to load conversations
              </span>
            </div>
          ) : loading ? (
            <div className="flex items-center justify-center h-32">
              <Loader2 className="w-5 h-5 animate-spin" style={{ color: A.text3 }} />
            </div>
          ) : filteredDialogs.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 gap-1">
              <MessageCircle className="w-6 h-6" style={{ color: A.text3 }} />
              <span className="text-xs" style={{ color: A.text3 }}>
                {search.trim() ? 'No matches' : 'No conversations'}
              </span>
            </div>
          ) : (
            filteredDialogs.map((dialog: any) => {
              const isSelected = selectedDialog?.id === dialog.id;
              const dName = dialog.peer_name || dialog.name || dialog.peer_username || dialog.username || '';
              const dUsername = dialog.peer_username || dialog.username || '';
              const tagInfo = dialog.tag ? TAG_COLORS[dialog.tag] : null;
              return (
                <div
                  key={dialog.id}
                  onClick={() => {
                    // Save draft for current dialog before switching
                    if (selectedDialog && selectedDialog.id !== dialog.id) {
                      saveDraft(selectedDialog.id);
                    }
                    setSelectedDialog(dialog);
                    exitSelectMode();
                    setEditingMsg(null);
                    setShowStatusDropdown(false);
                    setShowNotes(false);
                    setShowTemplates(false);
                    // Clear unread dot locally + persist to DB
                    if (dialog.unread_count > 0) {
                      setDialogs(prev => prev.map(d => d.id === dialog.id ? { ...d, unread_count: 0 } : d));
                      // Best-effort: update DB
                      fetch(`/api/telegram-outreach/inbox/dialogs/${dialog.id}/read`, { method: 'POST' }).catch(() => {});
                    }
                  }}
                  className="px-3 py-2.5 cursor-pointer transition-colors flex gap-2.5 items-start"
                  style={{
                    background: isSelected ? A.blueBg : 'transparent',
                    borderBottom: `1px solid ${A.border}`,
                  }}
                  onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = '#F9FAFB'; }}
                  onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
                >
                  <DialogAvatar name={dName} peerId={dialog.peer_id || dialog.id || 0} accountId={filterAccount ? Number(filterAccount) : undefined} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold truncate" style={{ color: A.text1 }}>
                        {dName || `Dialog ${dialog.id}`}
                      </span>
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        {dialog.unread_count > 0 && (
                          <span className="w-2 h-2 rounded-full" style={{ background: A.blue }} />
                        )}
                        <span className="text-[10px]" style={{ color: A.text3 }}>
                          {formatRelativeTime(dialog.last_message_at || dialog.updated_at)}
                        </span>
                      </div>
                    </div>
                    {dUsername && (
                      <span className="text-[11px] block truncate" style={{ color: A.text3 }}>@{dUsername}</span>
                    )}
                    <div className="flex items-center gap-2 mt-0.5">
                      <p className="text-xs truncate flex-1" style={{ color: A.text2, lineHeight: '1.4' }}>
                        {drafts[dialog.id]
                          ? <><span style={{ color: '#EF4444', fontWeight: 500 }}>Черновик: </span>{drafts[dialog.id]}</>
                          : <>{dialog.last_message_outbound ? <span style={{ color: A.text3 }}>You: </span> : ''}{dialog.last_message_preview || dialog.last_message || dialog.last_message_text || 'No messages'}</>
                        }
                      </p>
                      {tagInfo && (
                        <span
                          className="text-[10px] font-medium px-1.5 py-0.5 rounded-full flex-shrink-0"
                          style={{ background: tagInfo.bg, color: tagInfo.text, border: `1px solid ${tagInfo.border}` }}
                        >
                          {dialog.tag.replace('_', ' ')}
                        </span>
                      )}
                    </div>
                    {dialog.campaign_name && (
                      <span className="text-[10px] mt-0.5 block" style={{ color: A.text3 }}>
                        {dialog.campaign_name}
                      </span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* ── Right panel: Chat view ── */}
      <div className="flex-1 flex flex-col" style={{ minWidth: 0 }}>
        {!selectedDialog ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <MessageCircle className="w-10 h-10 mx-auto mb-2" style={{ color: A.text3 }} />
              <p className="text-sm" style={{ color: A.text3 }}>
                {applied ? 'Select a conversation' : 'Apply filters to load conversations'}
              </p>
            </div>
          </div>
        ) : (
          <>
            {/* Chat header */}
            <div className="px-4 py-3 flex items-center gap-3" style={{ borderBottom: `1px solid ${A.border}` }}>
              <DialogAvatar
                name={selectedDialog.peer_name || selectedDialog.name || selectedDialog.peer_username || ''}
                peerId={selectedDialog.peer_id || selectedDialog.id || 0}
                accountId={filterAccount ? Number(filterAccount) : undefined}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold truncate" style={{ color: A.text1 }}>
                    {selectedDialog.peer_name || selectedDialog.name || `Dialog ${selectedDialog.id}`}
                  </p>
                  {peerTyping ? (
                    <span className="text-[10px] flex items-center gap-1 flex-shrink-0" style={{ color: '#22C55E' }}>
                      <span className="flex gap-0.5">
                        <span className="w-1 h-1 rounded-full animate-bounce" style={{ background: '#22C55E', animationDelay: '0ms' }} />
                        <span className="w-1 h-1 rounded-full animate-bounce" style={{ background: '#22C55E', animationDelay: '150ms' }} />
                        <span className="w-1 h-1 rounded-full animate-bounce" style={{ background: '#22C55E', animationDelay: '300ms' }} />
                      </span>
                      typing
                    </span>
                  ) : peerStatus && (
                    <span className="text-[10px] flex items-center gap-1 flex-shrink-0" style={{
                      color: peerStatus.status === 'online' ? '#22C55E'
                        : peerStatus.possibly_blocked ? '#EF4444'
                        : A.text3,
                    }}>
                      {peerStatus.status === 'online' ? (
                        <><span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: '#22C55E' }} /> online</>
                      ) : peerStatus.possibly_blocked ? (
                        <><ShieldAlert className="w-3 h-3" /> possibly blocked</>
                      ) : peerStatus.status === 'recently' ? (
                        'was recently online'
                      ) : peerStatus.status === 'within_week' ? (
                        'was online within a week'
                      ) : peerStatus.status === 'within_month' ? (
                        'was online within a month'
                      ) : peerStatus.status === 'offline' && peerStatus.last_seen ? (
                        `last seen ${new Date(peerStatus.last_seen).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}`
                      ) : null}
                    </span>
                  )}
                </div>
                <p className="text-[11px] truncate" style={{ color: A.text3 }}>
                  {[
                    selectedDialog.peer_username || selectedDialog.username ? `@${selectedDialog.peer_username || selectedDialog.username}` : null,
                    selectedDialog.campaign_name,
                    selectedDialog.account_phone,
                  ].filter(Boolean).join(' \u00B7 ')}
                </p>
              </div>
              {/* Status dropdown */}
              <div className="relative" ref={statusDropdownRef}>
                <button
                  onClick={() => setShowStatusDropdown(v => !v)}
                  className="h-8 px-2.5 rounded-lg flex items-center gap-1.5 border text-[11px] font-medium transition-colors"
                  style={{
                    borderColor: selectedDialog.tag && TAG_COLORS[selectedDialog.tag] ? TAG_COLORS[selectedDialog.tag].border : A.border,
                    background: selectedDialog.tag && TAG_COLORS[selectedDialog.tag] ? TAG_COLORS[selectedDialog.tag].bg : 'transparent',
                    color: selectedDialog.tag && TAG_COLORS[selectedDialog.tag] ? TAG_COLORS[selectedDialog.tag].text : A.text3,
                    cursor: 'pointer',
                  }}
                >
                  {selectedDialog.tag ? selectedDialog.tag.replace('_', ' ') : 'Status'}
                  <ChevronDown className="w-3 h-3" />
                </button>
                {showStatusDropdown && (
                  <div className="absolute right-0 top-full mt-1 w-44 rounded-xl shadow-lg border overflow-hidden" style={{ background: A.surface, borderColor: A.border, zIndex: 30 }}>
                    {([
                      { key: 'interested', label: 'Interested' },
                      { key: 'not_interested', label: 'Not Interested' },
                      { key: 'meeting_set', label: 'Meeting Set' },
                    ] as const).map(t => {
                      const isActive = selectedDialog.tag === t.key;
                      const tc = TAG_COLORS[t.key];
                      return (
                        <button
                          key={t.key}
                          onClick={() => { handleTag(t.key); setShowStatusDropdown(false); }}
                          className="w-full text-left px-3 py-2 text-[12px] flex items-center gap-2 transition-colors"
                          style={{ color: A.text1, background: isActive ? tc.bg : 'transparent' }}
                          onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = '#F3F4F6'; }}
                          onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = isActive ? tc.bg : 'transparent'; }}
                        >
                          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: tc.text }} />
                          <span className="flex-1">{t.label}</span>
                          {isActive && <Check className="w-3.5 h-3.5" style={{ color: tc.text }} />}
                        </button>
                      );
                    })}
                    {selectedDialog.tag && (
                      <>
                        <div style={{ height: 1, background: A.border }} />
                        <button
                          onClick={() => { handleTag(selectedDialog.tag); setShowStatusDropdown(false); }}
                          className="w-full text-left px-3 py-2 text-[12px] transition-colors"
                          style={{ color: A.text3 }}
                          onMouseEnter={e => { e.currentTarget.style.background = '#F3F4F6'; }}
                          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                        >
                          Clear status
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
              <button
                onClick={async () => {
                  try {
                    await telegramOutreachApi.markDialogUnread(selectedDialog.id);
                    setDialogs(prev => prev.map(d => d.id === selectedDialog.id ? { ...d, unread_count: 1 } : d));
                    toast('Marked as unread', 'success');
                  } catch {
                    toast('Failed to mark as unread', 'error');
                  }
                }}
                title="Mark as unread"
                className="w-8 h-8 rounded-lg flex items-center justify-center border transition-colors"
                style={{
                  borderColor: A.border,
                  background: 'transparent',
                  cursor: 'pointer',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = '#F3F4F6'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
              >
                <EyeOff className="w-4 h-4" style={{ color: A.text3 }} />
              </button>
              <button
                onClick={() => setShowCrmInfo(!showCrmInfo)}
                title="Contact info"
                className="w-8 h-8 rounded-lg flex items-center justify-center border transition-colors"
                style={{
                  borderColor: showCrmInfo ? A.blue : A.border,
                  background: showCrmInfo ? A.blueBg : 'transparent',
                  cursor: 'pointer',
                }}
                onMouseEnter={e => { if (!showCrmInfo) e.currentTarget.style.background = '#F3F4F6'; }}
                onMouseLeave={e => { if (!showCrmInfo) e.currentTarget.style.background = showCrmInfo ? A.blueBg : 'transparent'; }}
              >
                <Info className="w-4 h-4" style={{ color: showCrmInfo ? A.blue : A.text3 }} />
              </button>
            </div>

            {/* Main content area (messages + optional CRM sidebar) */}
            <div className="flex-1 flex overflow-hidden">
              {/* Messages column */}
              <div className="flex-1 flex flex-col" style={{ minWidth: 0 }}>
                {/* Messages area */}
                <div className="flex-1 overflow-y-auto py-3 px-8" style={{ background: '#F9FAFB' }}>
                <div className="mx-auto" style={{ maxWidth: 620 }}>
                  {loadingMessages ? (
                    <div className="flex items-center justify-center h-full">
                      <Loader2 className="w-5 h-5 animate-spin" style={{ color: A.text3 }} />
                    </div>
                  ) : messages.length === 0 ? (
                    <div className="flex items-center justify-center h-full">
                      <span className="text-xs" style={{ color: A.text3 }}>No messages yet</span>
                    </div>
                  ) : (
                    <>
                    <div className="flex flex-col gap-1.5">
                      {messages.map((msg: any, idx: number) => {
                        const isOutbound = msg.direction === 'outbound' || msg.direction === 'sent' || msg.is_outbound;
                        const ts = msg.timestamp || msg.sent_at || msg.received_at || msg.created_at;
                        const timeStr = ts ? new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
                        // Date separator
                        const msgDate = ts ? new Date(ts).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' }) : '';
                        const prevTs = idx > 0 ? (messages[idx-1].timestamp || messages[idx-1].sent_at) : null;
                        const prevDate = prevTs ? new Date(prevTs).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' }) : '';
                        const showDateSep = msgDate && msgDate !== prevDate;
                        return (
                          <span key={msg.id || idx}>
                          {showDateSep && (
                            <div className="flex justify-center my-3">
                              <span className="text-[11px] px-3 py-1 rounded-full" style={{ background: A.border, color: A.text2, fontWeight: 500 }}>{msgDate}</span>
                            </div>
                          )}
                          <div id={`msg-${msg.id}`}
                               className={`flex ${isOutbound ? 'justify-end' : 'justify-start'} group items-center gap-1.5`}
                               onContextMenu={e => {
                                 e.preventDefault();
                                 if (!selectMode) setCtxMenu({ x: e.clientX, y: e.clientY, msg });
                               }}
                               onDoubleClick={() => { if (!selectMode) { setSelectMode(true); setSelectedMsgs(new Set([msg.id])); } }}
                               onClick={() => {
                                 if (selectMode && msg.id) {
                                   const next = new Set(selectedMsgs);
                                   next.has(msg.id) ? next.delete(msg.id) : next.add(msg.id);
                                   if (next.size === 0) { setSelectMode(false); setSelectedMsgs(new Set()); }
                                   else setSelectedMsgs(next);
                                 }
                               }}
                               style={selectMode && selectedMsgs.has(msg.id) ? { background: `${A.blueBg}80`, borderRadius: 8 } : undefined}>
                            <div
                              className="max-w-[70%] px-3.5 py-2 text-[13px] relative"
                              style={{
                                background: isOutbound ? A.blueBg : '#F3F4F6',
                                color: A.text1,
                                borderRadius: isOutbound ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                                wordBreak: 'break-word',
                              }}
                            >
                              {/* Forwarded header */}
                              {msg.fwd_from && msg.fwd_from.from_name && (
                                <div className="mb-1 text-[11px] font-medium" style={{ color: A.blue }}>
                                  Forwarded from {msg.fwd_from.from_name}
                                </div>
                              )}
                              {/* Reply quote (from Telethon reply_to data) */}
                              {msg.reply_to && msg.reply_to.msg_id && (
                                <div className="mb-1.5 px-2 py-1 rounded-lg text-[11px] cursor-pointer"
                                     style={{ borderLeft: `3px solid ${A.blue}`, background: isOutbound ? 'rgba(79,107,240,0.08)' : 'rgba(0,0,0,0.04)' }}
                                     onClick={() => {
                                       const el = document.getElementById(`msg-${msg.reply_to.msg_id}`);
                                       if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); el.style.background = `${A.blueBg}90`; setTimeout(() => el.style.background = '', 1500); }
                                     }}>
                                  {msg.reply_to.sender_name && <span style={{ color: A.blue, fontWeight: 600 }}>{msg.reply_to.sender_name}</span>}
                                  <p className="truncate" style={{ color: A.text2 }}>{msg.reply_to.text || ''}</p>
                                </div>
                              )}
                              {/* Media content */}
                              {msg.media && (() => {
                                const mediaUrl = selectedDialog ? telegramOutreachApi.getDialogMediaUrl(selectedDialog.id, msg.id) : '';
                                return (
                                  <div className="mb-1">
                                    {msg.media.type === 'photo' && (
                                      <img src={mediaUrl} alt="Photo" loading="lazy"
                                        className="rounded-lg cursor-pointer max-w-full"
                                        style={{ maxHeight: 280, objectFit: 'contain' }}
                                        onClick={() => window.open(mediaUrl, '_blank')}
                                        onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; (e.target as HTMLImageElement).nextElementSibling && ((e.target as HTMLImageElement).nextElementSibling as HTMLElement).style.removeProperty('display'); }}
                                      />
                                    )}
                                    {msg.media.type === 'photo' && (
                                      <div className="flex items-center gap-1.5 text-[12px] py-1 px-2 rounded-md" style={{ display: 'none', background: isOutbound ? 'rgba(79,107,240,0.08)' : 'rgba(0,0,0,0.04)' }}>
                                        <Image className="w-3.5 h-3.5" style={{ color: A.blue }} /><span style={{ color: A.text2 }}>Photo</span>
                                      </div>
                                    )}
                                    {(msg.media.type === 'video' || msg.media.type === 'video_note') && (
                                      <video src={mediaUrl} controls preload="metadata"
                                        className="rounded-lg max-w-full"
                                        style={{ maxHeight: 280, borderRadius: msg.media.type === 'video_note' ? '50%' : undefined, width: msg.media.type === 'video_note' ? 200 : undefined, height: msg.media.type === 'video_note' ? 200 : undefined, objectFit: msg.media.type === 'video_note' ? 'cover' : undefined }}
                                      />
                                    )}
                                    {msg.media.type === 'voice' && (
                                      <audio src={mediaUrl} controls preload="metadata" style={{ maxWidth: 260, height: 36 }} />
                                    )}
                                    {msg.media.type === 'sticker' && (
                                      <img src={mediaUrl} alt="Sticker" loading="lazy" className="max-w-[160px] max-h-[160px]" />
                                    )}
                                    {msg.media.type === 'document' && (
                                      <a href={mediaUrl} download={msg.media.file_name || 'file'} target="_blank" rel="noreferrer"
                                        className="flex items-center gap-2 py-1.5 px-2 rounded-md text-[12px] no-underline hover:opacity-80 transition-opacity"
                                        style={{ background: isOutbound ? 'rgba(79,107,240,0.08)' : 'rgba(0,0,0,0.04)' }}>
                                        <FileIcon className="w-4 h-4 flex-shrink-0" style={{ color: A.blue }} />
                                        <span style={{ color: A.text1 }}>{msg.media.file_name || 'File'}</span>
                                        {msg.media.size && <span style={{ color: A.text3 }}>({msg.media.size >= 1048576 ? `${(msg.media.size / 1048576).toFixed(1)} MB` : `${(msg.media.size / 1024).toFixed(0)} KB`})</span>}
                                        <Download className="w-3.5 h-3.5 flex-shrink-0" style={{ color: A.blue }} />
                                      </a>
                                    )}
                                  </div>
                                );
                              })()}
                              {(msg.text || msg.rendered_text || msg.message_text) && <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.5' }}>{msg.text || msg.rendered_text || msg.message_text}</p>}
                              {/* Footer: reactions + time + read status — all inline */}
                              <div className="flex items-center gap-1.5 mt-1 flex-wrap" style={{ justifyContent: isOutbound ? 'flex-end' : 'flex-start' }}>
                                {msg.reactions && msg.reactions.length > 0 && msg.reactions.map((r: any, ri: number) => (
                                  <span key={ri} className="text-[13px]" style={{ cursor: 'default', lineHeight: 1 }}>{r.emoji || r}</span>
                                ))}
                                <span className="text-[10px]" style={{ color: A.text3 }}>{timeStr}</span>
                                {isOutbound && <span className="text-[10px]" style={{ color: msg.is_read ? A.blue : A.text3 }}>{msg.is_read ? '✓✓' : '✓'}</span>}
                              </div>
                            </div>
                            {/* Selection checkbox — right side */}
                            {selectMode && (
                              <div style={{ width: 22, height: 22, borderRadius: 11, border: `2px solid ${selectedMsgs.has(msg.id) ? A.blue : '#D1D5DB'}`, background: selectedMsgs.has(msg.id) ? A.blue : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, cursor: 'pointer', transition: 'all 0.15s' }}>
                                {selectedMsgs.has(msg.id) && <Check className="w-3 h-3 text-white" strokeWidth={3} />}
                              </div>
                            )}
                          </div>
                          </span>
                        );
                      })}
                      {peerTyping && (
                        <div className="flex justify-start">
                          <div className="flex items-center gap-1.5 px-3 py-2 rounded-2xl text-xs" style={{ background: A.surface, border: `1px solid ${A.border}` }}>
                            <span className="flex gap-0.5">
                              <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: A.text3, animationDelay: '0ms' }} />
                              <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: A.text3, animationDelay: '150ms' }} />
                              <span className="w-1.5 h-1.5 rounded-full animate-bounce" style={{ background: A.text3, animationDelay: '300ms' }} />
                            </span>
                            <span style={{ color: A.text3 }}>typing</span>
                          </div>
                        </div>
                      )}
                      <div ref={messagesEndRef} />
                    </div>

                    {/* Context menu */}
                    {ctxMenu && (
                      <div style={{ position: 'fixed', left: ctxMenu.x, top: ctxMenu.y, zIndex: 100, borderRadius: 12, border: `1px solid ${A.border}`, background: A.surface, boxShadow: '0 4px 16px rgba(0,0,0,0.12)', padding: '4px 0', minWidth: 160 }}
                           onClick={e => e.stopPropagation()}>
                        {/* Quick reactions */}
                        <div className="flex gap-1 px-3 py-1.5">
                          {['👍', '❤️', '😂', '🔥', '😢', '👏'].map(em => (
                            <button key={em} onClick={() => { handleReact(ctxMenu.msg.id, em); setCtxMenu(null); }}
                                    className="text-base hover:scale-125 transition-transform" style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2 }}>{em}</button>
                          ))}
                        </div>
                        <div style={{ height: 1, background: A.border, margin: '2px 0' }} />
                        <button onClick={() => { setReplyTo(ctxMenu.msg); setCtxMenu(null); editorRef.current?.focus(); }}
                                className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1, border: 'none', background: 'none', cursor: 'pointer' }}>
                          Reply
                        </button>
                        {ctxMenu.msg.out && ctxMenu.msg.text && (
                          <button onClick={() => {
                            setEditingMsg(ctxMenu.msg);
                            setReplyTo(null);
                            const editor = editorRef.current;
                            if (editor) { editor.textContent = ctxMenu.msg.text; }
                            setMessageText(ctxMenu.msg.text);
                            setCtxMenu(null);
                            editorRef.current?.focus();
                          }}
                                  className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1, border: 'none', background: 'none', cursor: 'pointer' }}>
                            Edit
                          </button>
                        )}
                        <button onClick={() => { setForwardPopup({ msgIds: [ctxMenu.msg.id] }); setForwardDialogs(dialogs); setCtxMenu(null); }}
                                className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1, border: 'none', background: 'none', cursor: 'pointer' }}>
                          Forward
                        </button>
                        <button onClick={() => { navigator.clipboard.writeText(ctxMenu.msg.text || ''); toast('Copied', 'success'); setCtxMenu(null); }}
                                className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1, border: 'none', background: 'none', cursor: 'pointer' }}>
                          Copy Text
                        </button>
                        <button onClick={() => { setSelectMode(true); setSelectedMsgs(new Set([ctxMenu.msg.id])); setCtxMenu(null); }}
                                className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1, border: 'none', background: 'none', cursor: 'pointer' }}>
                          Select
                        </button>
                        <div style={{ height: 1, background: A.border, margin: '2px 0' }} />
                        <button onClick={() => { setDeleteModal(ctxMenu.msg); setCtxMenu(null); }}
                                className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#FFF1F2]" style={{ color: A.rose, border: 'none', background: 'none', cursor: 'pointer' }}>
                          Delete
                        </button>
                      </div>
                    )}

                    {/* Delete confirmation modal */}
                    {deleteModal && (
                      <div style={{ position: 'fixed', inset: 0, zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.3)' }} onClick={() => setDeleteModal(null)} />
                        <div style={{ position: 'relative', zIndex: 10, width: 320, borderRadius: 16, background: A.surface, padding: 20, boxShadow: '0 20px 60px rgba(0,0,0,0.15)' }}>
                          <h3 style={{ fontSize: 15, fontWeight: 600, color: A.text1, marginBottom: 12 }}>
                            {deleteModal.bulk ? `Delete ${selectedMsgs.size} messages?` : 'Delete message?'}
                          </h3>
                          {!deleteModal.bulk && <p className="text-xs mb-4 truncate" style={{ color: A.text3 }}>{(deleteModal.text || '').slice(0, 80)}</p>}
                          <div className="flex flex-col gap-2">
                            <button onClick={() => { if (deleteModal.bulk) handleBulkDelete(true); else handleDeleteMsg(deleteModal.id, true); }}
                                    style={{ width: '100%', padding: '8px 0', borderRadius: 8, background: A.rose, color: '#fff', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer' }}>
                              Delete for everyone
                            </button>
                            <button onClick={() => { if (deleteModal.bulk) handleBulkDelete(false); else handleDeleteMsg(deleteModal.id, false); }}
                                    style={{ width: '100%', padding: '8px 0', borderRadius: 8, background: '#F3F4F6', color: A.text1, fontSize: 13, fontWeight: 500, border: 'none', cursor: 'pointer' }}>
                              Delete for me only
                            </button>
                            <button onClick={() => setDeleteModal(null)}
                                    style={{ width: '100%', padding: '6px 0', background: 'none', color: A.text3, fontSize: 12, border: 'none', cursor: 'pointer' }}>
                              Cancel
                            </button>
                          </div>
                        </div>
                      </div>
                    )}
                    </>
                  )}
                </div>
                </div>

                {/* Selection mode bar */}
                {selectMode && (
                  <div className="px-4 py-2 flex items-center gap-2" style={{ borderTop: `1px solid ${A.border}`, background: A.blueBg }}>
                    <span className="text-xs font-semibold" style={{ color: A.blue }}>{selectedMsgs.size} selected</span>
                    <div className="flex-1" />
                    <button onClick={() => { setForwardPopup({ msgIds: Array.from(selectedMsgs) }); setForwardDialogs(dialogs); }}
                            className="text-[11px] px-2.5 py-1 rounded-lg font-medium" style={{ background: A.blue, color: '#fff', border: 'none', cursor: 'pointer' }}>Forward</button>
                    <button onClick={handleBulkCopy} className="text-[11px] px-2.5 py-1 rounded-lg font-medium" style={{ background: A.surface, border: `1px solid ${A.border}`, color: A.text1, cursor: 'pointer' }}>Copy</button>
                    <button onClick={() => setDeleteModal({ bulk: true })} disabled={selectedMsgs.size === 0} className="text-[11px] px-2.5 py-1 rounded-lg font-medium" style={{ background: A.rose, color: '#fff', border: 'none', cursor: 'pointer' }}>Delete</button>
                    <button onClick={exitSelectMode} className="text-[11px] px-2 py-1 rounded-lg" style={{ background: 'none', border: 'none', color: A.text3, cursor: 'pointer' }}>Cancel</button>
                  </div>
                )}

                {/* Input area */}
                <div className="relative px-4 py-2 flex flex-col gap-1.5" style={{ borderTop: `1px solid ${A.border}` }}>
                  {/* Templates popup (absolute) */}
                  {showTemplates && (
                    <div
                      ref={templateRef}
                      className="absolute left-4 right-4 rounded-xl shadow-lg border overflow-hidden"
                      style={{
                        bottom: '100%',
                        marginBottom: 4,
                        background: A.surface,
                        borderColor: A.border,
                        zIndex: 20,
                      }}
                    >
                      <div className="px-3 py-2 flex items-center gap-1.5" style={{ borderBottom: `1px solid ${A.border}`, background: '#F9FAFB' }}>
                        <FileText className="w-3.5 h-3.5" style={{ color: A.text3 }} />
                        <span className="text-[11px] font-semibold" style={{ color: A.text2 }}>Quick replies</span>
                      </div>
                      <div className="p-1.5 flex flex-col gap-0.5">
                        {REPLY_TEMPLATES.map((tpl) => (
                          <button
                            key={tpl.label}
                            onClick={() => {
                              setEditorContent(tpl.text);
                              setShowTemplates(false);
                              editorRef.current?.focus();
                            }}
                            className="text-left px-2.5 py-2 rounded-lg text-xs transition-colors"
                            style={{ color: A.text1 }}
                            onMouseEnter={e => { e.currentTarget.style.background = A.blueBg; }}
                            onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                          >
                            <span className="font-semibold" style={{ color: A.blue }}>{tpl.label}</span>
                            <span className="block mt-0.5" style={{ color: A.text2, lineHeight: '1.4' }}>{tpl.text}</span>
                          </button>
                        ))}
                        {customTemplates.length > 0 && (
                          <>
                            <div style={{ height: 1, background: A.border, margin: '4px 0' }} />
                            <div className="px-2.5 py-1 text-[10px] font-semibold" style={{ color: A.text3 }}>SAVED</div>
                            {customTemplates.map((tpl, idx) => (
                              <div key={idx} className="flex items-center gap-1 px-1">
                                <button onClick={() => { setEditorContent(tpl.text); setShowTemplates(false); }}
                                  className="flex-1 text-left px-1.5 py-1.5 rounded-lg text-xs"
                                  style={{ color: A.text1 }}
                                  onMouseEnter={e => { e.currentTarget.style.background = A.blueBg; }}
                                  onMouseLeave={e => { e.currentTarget.style.background = ''; }}>
                                  <span className="font-semibold" style={{ color: A.teal }}>{tpl.label}</span>
                                  <span className="block mt-0.5 truncate" style={{ color: A.text2 }}>{tpl.text}</span>
                                </button>
                                <button onClick={() => deleteCustomTemplate(idx)} className="p-1 hover:bg-red-50 rounded" style={{ border: 'none', background: 'none', cursor: 'pointer' }}>
                                  <X className="w-3 h-3" style={{ color: A.rose }} />
                                </button>
                              </div>
                            ))}
                          </>
                        )}
                        <div style={{ height: 1, background: A.border, margin: '4px 0' }} />
                        <button onClick={() => { setShowTemplates(false); setShowSaveTemplate(true); }}
                          className="w-full text-left px-2.5 py-1.5 text-[11px] font-medium"
                          style={{ color: A.blue, border: 'none', background: 'none', cursor: 'pointer' }}
                          onMouseEnter={e => { e.currentTarget.style.background = A.blueBg; }}
                          onMouseLeave={e => { e.currentTarget.style.background = ''; }}>
                          + Create new template
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Notes popup (absolute) */}
                  {showNotes && selectedDialog && (
                    <div
                      ref={notesRef}
                      className="absolute left-4 right-4 rounded-xl shadow-lg border overflow-hidden"
                      style={{ bottom: '100%', marginBottom: 4, background: A.surface, borderColor: A.border, zIndex: 20 }}
                    >
                      <div className="px-3 py-2 flex items-center gap-1.5" style={{ borderBottom: `1px solid ${A.border}`, background: '#F9FAFB' }}>
                        <Edit3 className="w-3.5 h-3.5" style={{ color: A.text3 }} />
                        <span className="text-[11px] font-semibold" style={{ color: A.text2 }}>Notes</span>
                        <span className="text-[10px]" style={{ color: A.text3 }}>— {selectedDialog.peer_name || selectedDialog.name || 'Dialog'}</span>
                      </div>
                      <div className="p-2">
                        <textarea
                          value={dialogNotes[selectedDialog.id] || ''}
                          onChange={e => saveNote(selectedDialog.id, e.target.value)}
                          placeholder="Add notes about this contact..."
                          className="w-full text-xs rounded-lg border outline-none resize-none"
                          style={{ borderColor: A.border, color: A.text1, background: '#FAFAFA', padding: '8px 10px', minHeight: 80, maxHeight: 160 }}
                        />
                      </div>
                    </div>
                  )}

                  {/* Row 1: Quick Reply | Notes */}
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => { setShowTemplates(v => !v); setShowNotes(false); }}
                      title="Quick reply templates"
                      className="h-7 px-2 rounded-md flex items-center gap-1.5 border text-[11px] transition-colors"
                      style={{
                        borderColor: showTemplates ? A.blue : A.border,
                        background: showTemplates ? A.blueBg : 'transparent',
                        color: showTemplates ? A.blue : A.text3,
                        cursor: 'pointer',
                      }}
                      onMouseEnter={e => { if (!showTemplates) e.currentTarget.style.background = '#F3F4F6'; }}
                      onMouseLeave={e => { if (!showTemplates) e.currentTarget.style.background = showTemplates ? A.blueBg : 'transparent'; }}
                    >
                      <BookOpen className="w-3.5 h-3.5" />
                      <span className="font-medium">Templates</span>
                    </button>
                    <button
                      onClick={() => { setShowNotes(v => !v); setShowTemplates(false); }}
                      title="Notes for this contact"
                      className="h-7 px-2 rounded-md flex items-center gap-1.5 border text-[11px] transition-colors"
                      style={{
                        borderColor: showNotes ? A.blue : A.border,
                        background: showNotes ? A.blueBg : 'transparent',
                        color: showNotes ? A.blue : A.text3,
                        cursor: 'pointer',
                      }}
                      onMouseEnter={e => { if (!showNotes) e.currentTarget.style.background = '#F3F4F6'; }}
                      onMouseLeave={e => { if (!showNotes) e.currentTarget.style.background = showNotes ? A.blueBg : 'transparent'; }}
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                      <span className="font-medium">Notes</span>
                      {selectedDialog && dialogNotes[selectedDialog.id] && (
                        <span className="w-1.5 h-1.5 rounded-full" style={{ background: A.blue }} />
                      )}
                    </button>
                  </div>

                  {/* Row 2: Formatting toolbar */}
                  <div className="relative flex items-center gap-0.5 px-0.5">
                    {([
                      ['bold', 'B', 'Bold · Ctrl+B', 'font-bold'],
                      ['italic', 'I', 'Italic · Ctrl+I', 'italic'],
                      ['underline', 'U', 'Underline · Ctrl+U', 'underline'],
                      ['strikeThrough', 'S', 'Strikethrough · Ctrl+Shift+X', 'line-through'],
                      ['code', '</>', 'Code · Ctrl+Shift+M', ''],
                      ['span:tg-spoiler', '◉', 'Spoiler · Ctrl+Shift+P', ''],
                      ['blockquote', '❝', 'Quote · Ctrl+Shift+.', ''],
                    ] as [string, string, string, string][]).map(([fmt, label, title, cls]) => (
                      <button
                        key={fmt}
                        onMouseDown={e => e.preventDefault()}
                        onClick={() => {
                          if (fmt.startsWith('span:')) applyFormat('span', { class: fmt.split(':')[1] });
                          else applyFormat(fmt);
                        }}
                        title={title}
                        className={`fmt-btn ${cls}`}
                      >{label}</button>
                    ))}
                    <button
                      onMouseDown={e => e.preventDefault()}
                      onClick={() => applyFormat('createLink')}
                      title="Link · Ctrl+K"
                      className="fmt-btn"
                    ><Link2 className="w-3 h-3" /></button>
                    {/* Link URL popup */}
                    {linkPopup && (
                      <div className="absolute bottom-full left-0 mb-1 flex items-center gap-1 p-2 rounded-lg shadow-lg border"
                           style={{ background: A.surface, borderColor: A.border, zIndex: 10 }}>
                        <input
                          type="url"
                          value={linkPopup.url}
                          onChange={e => setLinkPopup({ url: e.target.value })}
                          onKeyDown={e => {
                            if (e.key === 'Enter') { e.preventDefault(); applyLink(linkPopup.url); }
                            if (e.key === 'Escape') { setLinkPopup(null); editorRef.current?.focus(); }
                          }}
                          placeholder="https://..."
                          autoFocus
                          className="h-7 px-2 text-xs rounded border outline-none"
                          style={{ borderColor: A.border, color: A.text1, width: 220 }}
                        />
                        <button onClick={() => applyLink(linkPopup.url)}
                                className="h-7 px-2.5 text-xs rounded text-white font-medium"
                                style={{ background: A.blue }}>
                          OK
                        </button>
                        <button onClick={() => { setLinkPopup(null); editorRef.current?.focus(); }}
                                className="fmt-btn" style={{ color: A.text3 }}>
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Edit preview */}
                  {editingMsg && (
                    <div className="flex items-center gap-2 px-2 py-1 rounded-lg text-[11px]" style={{ background: '#FEF3C7', color: A.text2 }}>
                      <div className="flex-1 truncate" style={{ borderLeft: '2px solid #F59E0B', paddingLeft: 6 }}>
                        <span style={{ color: '#D97706', fontWeight: 600 }}>Editing</span>{' '}
                        {(editingMsg.text || '').slice(0, 60)}
                      </div>
                      <button onClick={() => { setEditingMsg(null); const editor = editorRef.current; if (editor) editor.innerHTML = ''; setMessageText(''); }} style={{ background: 'none', border: 'none', cursor: 'pointer', color: A.text3, padding: 2 }}>
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  )}

                  {/* Reply preview */}
                  {replyTo && !editingMsg && (
                    <div className="flex items-center gap-2 px-2 py-1 rounded-lg text-[11px]" style={{ background: A.blueBg, color: A.text2 }}>
                      <div className="flex-1 truncate" style={{ borderLeft: `2px solid ${A.blue}`, paddingLeft: 6 }}>
                        <span style={{ color: A.blue, fontWeight: 600 }}>Reply</span>{' '}
                        {(replyTo.text || '').slice(0, 60)}
                      </div>
                      <button onClick={() => setReplyTo(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: A.text3, padding: 2 }}>
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  )}

                  {/* Attachment preview */}
                  {attachedFile && (
                    <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-[12px]" style={{ background: A.blueBg, color: A.text2 }}>
                      {attachedFile.type.startsWith('image/') ? <Image className="w-3.5 h-3.5" style={{ color: A.blue }} /> : <FileIcon className="w-3.5 h-3.5" style={{ color: A.blue }} />}
                      <span className="flex-1 truncate font-medium" style={{ color: A.text1 }}>{attachedFile.name}</span>
                      <span style={{ color: A.text3 }}>{(attachedFile.size / 1024).toFixed(0)} KB</span>
                      <button onClick={() => setAttachedFile(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: A.text3, padding: 2 }}>
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  )}

                  {/* Row 3: Editor + Attach + Send button */}
                  <div className="flex gap-2 items-end">
                    <input ref={fileInputRef} type="file" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) setAttachedFile(f); e.target.value = ''; }} />
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="h-9 w-9 rounded-lg flex items-center justify-center transition-colors flex-shrink-0"
                      title="Attach file"
                      style={{ background: 'transparent', border: `1px solid ${A.border}`, cursor: 'pointer' }}
                    >
                      <Paperclip className="w-4 h-4" style={{ color: A.text3 }} />
                    </button>
                    <div
                      ref={editorRef}
                      contentEditable={!sending}
                      suppressContentEditableWarning
                      onInput={() => setMessageText(editorRef.current?.textContent || '')}
                      onKeyDown={handleEditorKeyDown}
                      onPaste={handleEditorPaste}
                      data-placeholder="Type a message... (Shift+Enter for new line)"
                      className="inbox-editor flex-1 rounded-lg border text-sm outline-none"
                      style={{ borderColor: A.border, color: A.text1, background: '#F9FAFB' }}
                    />
                    <button
                      onClick={handleSend}
                      disabled={sending || (!messageText.trim() && !attachedFile)}
                      className="h-9 w-9 rounded-lg flex items-center justify-center transition-colors flex-shrink-0"
                      style={{
                        background: (messageText.trim() || attachedFile) ? (editingMsg ? '#D97706' : A.blue) : '#E5E7EB',
                        cursor: (messageText.trim() || attachedFile) ? 'pointer' : 'default',
                      }}
                    >
                      {sending
                        ? <Loader2 className="w-4 h-4 text-white animate-spin" />
                        : editingMsg ? <Check className="w-4 h-4 text-white" /> : <Send className="w-4 h-4 text-white" />}
                    </button>
                  </div>

                  {/* Row 4: Account signature */}
                  {selectedDialog && (selectedDialog.account_username || selectedDialog.account_phone) && (
                    <div className="flex items-center gap-1.5 px-1 text-[10px]" style={{ color: A.text3 }}>
                      <span>via</span>
                      <span className="font-medium" style={{ color: A.text2 }}>
                        {selectedDialog.account_username ? `@${selectedDialog.account_username}` : selectedDialog.account_phone}
                      </span>
                      {selectedDialog.account_name && (
                        <span style={{ color: A.text3 }}>({selectedDialog.account_name})</span>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Forward Popup */}
              {forwardPopup && (
                <div style={{ position: 'fixed', inset: 0, zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.4)' }} onClick={() => setForwardPopup(null)} />
                  <div style={{ position: 'relative', zIndex: 10, width: 400, maxHeight: '70vh', borderRadius: 16, background: A.surface, boxShadow: '0 20px 60px rgba(0,0,0,0.2)', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ padding: '16px 20px', borderBottom: `1px solid ${A.border}` }}>
                      <h3 style={{ fontSize: 16, fontWeight: 600, color: A.text1, marginBottom: 10 }}>Forward {forwardPopup.msgIds.length > 1 ? `${forwardPopup.msgIds.length} messages` : 'message'}...</h3>
                      <div style={{ position: 'relative' }}>
                        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: A.text3 }} />
                        <input value={forwardSearch} onChange={e => setForwardSearch(e.target.value)}
                               placeholder="Search contacts..." className="w-full h-8 pl-8 pr-3 rounded-lg text-xs outline-none"
                               style={{ border: `1px solid ${A.border}`, color: A.text1, background: '#F9FAFB' }} />
                      </div>
                    </div>
                    <div style={{ flex: 1, overflowY: 'auto', padding: '4px 0' }}>
                      {forwardDialogs
                        .filter(d => !forwardSearch || (d.peer_name || '').toLowerCase().includes(forwardSearch.toLowerCase()) || (d.peer_username || '').toLowerCase().includes(forwardSearch.toLowerCase()))
                        .map(d => (
                        <button key={d.id} onClick={async () => {
                          try {
                            await telegramOutreachApi.forwardDialogMessages(selectedDialog.id, d.id, forwardPopup.msgIds);
                            toast(`Forwarded to ${d.peer_name || 'contact'}`, 'success');
                            setForwardPopup(null); exitSelectMode();
                          } catch (e: any) {
                            toast(e?.response?.data?.detail || 'Forward failed', 'error');
                          }
                        }}
                          className="w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors"
                          style={{ border: 'none', background: 'transparent', cursor: 'pointer' }}
                          onMouseEnter={e => { e.currentTarget.style.background = '#F5F5F0'; }}
                          onMouseLeave={e => { e.currentTarget.style.background = ''; }}>
                          <div style={{ width: 36, height: 36, borderRadius: 18, display: 'flex', alignItems: 'center', justifyContent: 'center', background: `hsl(${(d.peer_id || 0) % 360}, 45%, 55%)`, color: '#fff', fontSize: 13, fontWeight: 600, flexShrink: 0 }}>
                            {((d.peer_name || '?')[0] || '?').toUpperCase()}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium truncate" style={{ color: A.text1 }}>{d.peer_name || 'Unknown'}</p>
                            {d.peer_username && <p className="text-[11px] truncate" style={{ color: A.text3 }}>@{d.peer_username}</p>}
                          </div>
                        </button>
                      ))}
                    </div>
                    <div style={{ padding: '12px 20px', borderTop: `1px solid ${A.border}`, textAlign: 'right' }}>
                      <button onClick={() => setForwardPopup(null)} style={{ fontSize: 13, color: A.text3, background: 'none', border: 'none', cursor: 'pointer' }}>Cancel</button>
                    </div>
                  </div>
                </div>
              )}

              {/* Save Template Popup */}
              {showSaveTemplate && (
                <div style={{ position: 'fixed', inset: 0, zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.3)' }} onClick={() => setShowSaveTemplate(false)} />
                  <div style={{ position: 'relative', zIndex: 10, width: 380, borderRadius: 16, background: A.surface, padding: 24, boxShadow: '0 20px 60px rgba(0,0,0,0.15)' }}>
                    <h3 style={{ fontSize: 16, fontWeight: 600, color: A.text1, marginBottom: 16 }}>Create Template</h3>
                    <div className="space-y-3">
                      <div>
                        <label className="text-xs font-medium" style={{ color: A.text2 }}>Name</label>
                        <input id="tpl-name" placeholder="e.g. Follow-up, Meeting request..."
                          className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none"
                          style={{ border: `1px solid ${A.border}`, color: A.text1 }} />
                      </div>
                      <div>
                        <label className="text-xs font-medium" style={{ color: A.text2 }}>Message</label>
                        <textarea id="tpl-text" rows={4} placeholder="Type your template message..."
                          className="w-full mt-1 px-3 py-2 rounded-lg text-sm outline-none resize-none"
                          style={{ border: `1px solid ${A.border}`, color: A.text1 }} />
                      </div>
                    </div>
                    <div className="flex justify-end gap-2 mt-4">
                      <button onClick={() => setShowSaveTemplate(false)}
                        style={{ padding: '8px 16px', borderRadius: 8, border: `1px solid ${A.border}`, background: A.surface, fontSize: 13, color: A.text1, cursor: 'pointer' }}>Cancel</button>
                      <button onClick={() => {
                        const name = (document.getElementById('tpl-name') as HTMLInputElement)?.value?.trim();
                        const text = (document.getElementById('tpl-text') as HTMLTextAreaElement)?.value?.trim();
                        if (!name || !text) { toast('Fill both fields', 'error'); return; }
                        saveCustomTemplate(name, text);
                        setShowSaveTemplate(false);
                        toast('Template saved', 'success');
                      }} style={{ padding: '8px 16px', borderRadius: 8, background: A.blue, color: '#fff', fontSize: 13, fontWeight: 600, border: 'none', cursor: 'pointer' }}>Save</button>
                    </div>
                  </div>
                </div>
              )}

              {/* CRM Info sidebar */}
              {showCrmInfo && (
                <div className="flex flex-col overflow-y-auto" style={{ width: 300, borderLeft: `1px solid ${A.border}`, background: A.surface }}>
                  <div className="p-4 flex flex-col gap-3">
                    {/* Contact header */}
                    <div className="flex flex-col items-center gap-2 pb-3" style={{ borderBottom: `1px solid ${A.border}` }}>
                      <DialogAvatar
                        name={selectedDialog.peer_name || selectedDialog.name || ''}
                        peerId={selectedDialog.peer_id || selectedDialog.id || 0}
                        accountId={filterAccount ? Number(filterAccount) : undefined}
                      />
                      <div className="text-center">
                        <p className="text-sm font-semibold" style={{ color: A.text1 }}>
                          {selectedDialog.peer_name || selectedDialog.name || 'Unknown'}
                        </p>
                        {(selectedDialog.peer_username || selectedDialog.username) && (
                          <p className="text-xs" style={{ color: A.text3 }}>@{selectedDialog.peer_username || selectedDialog.username}</p>
                        )}
                        {peerStatus && (
                          <p className="text-[10px] mt-0.5" style={{
                            color: peerStatus.status === 'online' ? '#22C55E'
                              : peerStatus.possibly_blocked ? '#EF4444' : A.text3,
                          }}>
                            {peerStatus.status === 'online' ? 'online'
                              : peerStatus.possibly_blocked ? 'possibly blocked'
                              : peerStatus.status === 'recently' ? 'was recently online'
                              : peerStatus.status === 'offline' && peerStatus.last_seen
                                ? `last seen ${new Date(peerStatus.last_seen).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}`
                              : peerStatus.status === 'within_week' ? 'was online within a week'
                              : peerStatus.status === 'within_month' ? 'was online within a month'
                              : null}
                          </p>
                        )}
                      </div>
                    </div>

                    {crmLoading ? (
                      <div className="flex justify-center py-6">
                        <Loader2 className="w-5 h-5 animate-spin" style={{ color: A.text3 }} />
                      </div>
                    ) : crmData ? (
                      <>
                        {/* CRM Status */}
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-wider mb-1" style={{ color: A.text3 }}>Lead Status</p>
                          <span className="text-xs font-medium px-2 py-0.5 rounded-full" style={{
                            background: crmData.status === 'replied' ? '#DBEAFE' : crmData.status === 'qualified' ? '#D1FAE5' : crmData.status === 'converted' ? '#ECFDF5' : crmData.status === 'not_interested' ? '#FEE2E2' : '#F3F4F6',
                            color: crmData.status === 'replied' ? '#1D4ED8' : crmData.status === 'qualified' ? '#065F46' : crmData.status === 'converted' ? '#047857' : crmData.status === 'not_interested' ? '#B91C1C' : A.text1,
                          }}>
                            {(crmData.status || 'unknown').replace('_', ' ')}
                          </span>
                        </div>

                        {/* Company */}
                        {crmData.company_name && (
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-wider mb-1" style={{ color: A.text3 }}>Company</p>
                            <p className="text-xs" style={{ color: A.text1 }}>{crmData.company_name}</p>
                          </div>
                        )}

                        {/* Campaigns */}
                        {crmData.campaigns && crmData.campaigns.length > 0 && (
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-wider mb-1" style={{ color: A.text3 }}>Campaigns</p>
                            <div className="flex flex-wrap gap-1">
                              {crmData.campaigns.map((c: any, i: number) => (
                                <span key={i} className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: '#F3F4F6', color: A.text2 }}>
                                  {c.name || `#${c.id}`}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Message stats */}
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-wider mb-1" style={{ color: A.text3 }}>Messages</p>
                          <div className="flex gap-4">
                            <div>
                              <span className="text-lg font-semibold" style={{ color: A.text1, fontVariantNumeric: 'tabular-nums' }}>{crmData.total_messages_sent}</span>
                              <span className="text-[10px] ml-1" style={{ color: A.text3 }}>sent</span>
                            </div>
                            <div>
                              <span className="text-lg font-semibold" style={{ color: A.text1, fontVariantNumeric: 'tabular-nums' }}>{crmData.total_replies_received}</span>
                              <span className="text-[10px] ml-1" style={{ color: A.text3 }}>replies</span>
                            </div>
                          </div>
                        </div>

                        {/* Dates */}
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-wider mb-1" style={{ color: A.text3 }}>Timeline</p>
                          <div className="flex flex-col gap-0.5">
                            {crmData.first_contacted_at && (
                              <p className="text-[11px]" style={{ color: A.text2 }}>
                                First contacted: {new Date(crmData.first_contacted_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })}
                              </p>
                            )}
                            {crmData.last_contacted_at && (
                              <p className="text-[11px]" style={{ color: A.text2 }}>
                                Last contacted: {new Date(crmData.last_contacted_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })}
                              </p>
                            )}
                            {crmData.last_reply_at && (
                              <p className="text-[11px]" style={{ color: A.text2 }}>
                                Last reply: {new Date(crmData.last_reply_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })}
                              </p>
                            )}
                          </div>
                        </div>

                        {/* Tags */}
                        {crmData.tags && crmData.tags.length > 0 && (
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-wider mb-1" style={{ color: A.text3 }}>Tags</p>
                            <div className="flex flex-wrap gap-1">
                              {crmData.tags.map((t: string, i: number) => (
                                <span key={i} className="text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: A.blueBg, color: A.blue }}>{t}</span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Notes */}
                        {crmData.notes && (
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-wider mb-1" style={{ color: A.text3 }}>Notes</p>
                            <p className="text-xs whitespace-pre-wrap" style={{ color: A.text2, lineHeight: '1.5' }}>{crmData.notes}</p>
                          </div>
                        )}

                        {/* Custom Properties */}
                        {crmFieldDefs.length > 0 && (
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-wider mb-1" style={{ color: A.text3 }}>Custom Properties</p>
                            <div className="flex flex-col gap-1">
                              {crmFieldDefs.map((fd: any) => {
                                const cv = crmCustomFields.find((v: any) => v.field_id === fd.id);
                                return (
                                  <div key={fd.id} className="flex items-center gap-1.5">
                                    <span className="text-[10px] shrink-0 w-20 truncate" style={{ color: A.text3 }}>{fd.name}</span>
                                    <input
                                      className="flex-1 text-[11px] px-1.5 py-0.5 rounded outline-none min-w-0"
                                      style={{ background: A.bg, border: `1px solid ${A.border}`, color: A.text1 }}
                                      type={fd.field_type === 'number' ? 'number' : fd.field_type === 'date' ? 'date' : 'text'}
                                      defaultValue={cv?.value || ''}
                                      placeholder="—"
                                      onBlur={async (e) => {
                                        if (!crmData?.contact_id) return;
                                        const val = e.target.value.trim();
                                        try {
                                          await telegramOutreachApi.updateContactCustomFields(crmData.contact_id, [{ field_id: fd.id, value: val || null }]);
                                        } catch { /* silent */ }
                                      }}
                                    />
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="text-center py-4">
                        <p className="text-xs" style={{ color: A.text3 }}>No CRM data for this contact</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
      {/* New Chat Modal */}
      {showNewChat && createPortal(
        <ModalBackdrop onClose={() => { setShowNewChat(false); setNewChatUsername(''); }}>
          <div className="w-[380px] rounded-xl border shadow-xl" style={{ borderColor: A.border, background: A.surface }}>
            <div className="flex items-center justify-between px-5 py-3 border-b" style={{ borderColor: A.border }}>
              <span className="text-sm font-semibold" style={{ color: A.text1 }}>New Chat</span>
              <button onClick={() => { setShowNewChat(false); setNewChatUsername(''); }} className="p-1 rounded hover:bg-gray-100">
                <X className="w-4 h-4" style={{ color: A.text3 }} />
              </button>
            </div>
            <div className="px-5 py-4 flex flex-col gap-3">
              <label className="text-xs font-medium" style={{ color: A.text2 }}>Telegram username</label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm" style={{ color: A.text3 }}>@</span>
                <input
                  type="text"
                  value={newChatUsername}
                  onChange={e => setNewChatUsername(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter' && newChatUsername.trim()) handleNewChat(); }}
                  placeholder="username"
                  autoFocus
                  className="w-full h-9 pl-7 pr-3 rounded-lg border text-sm outline-none"
                  style={{ borderColor: A.border, color: A.text1, background: '#F9FAFB' }}
                />
              </div>
              <button
                onClick={handleNewChat}
                disabled={newChatLoading || !newChatUsername.trim()}
                className="h-9 rounded-lg text-sm font-semibold text-white transition-colors flex items-center justify-center gap-2"
                style={{ background: !newChatUsername.trim() ? '#9CA3AF' : A.blue, cursor: newChatLoading ? 'wait' : 'pointer' }}
                onMouseEnter={e => { if (newChatUsername.trim()) e.currentTarget.style.background = A.blueHover; }}
                onMouseLeave={e => { if (newChatUsername.trim()) e.currentTarget.style.background = A.blue; }}
              >
                {newChatLoading ? <><Loader2 className="w-4 h-4 animate-spin" /> Resolving...</> : 'Start Chat'}
              </button>
            </div>
          </div>
        </ModalBackdrop>,
        document.body,
      )}
    </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════
// BLACKLIST TAB
// ═══════════════════════════════════════════════════════════════════════

function BlacklistTab({ toast }: { toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) {
  const [entries, setEntries] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [uploadText, setUploadText] = useState('');
  const [uploadReason, setUploadReason] = useState('');
  const [uploading, setUploading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const loadEntries = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { page, page_size: 50 };
      if (search) params.search = search;
      const data = await telegramOutreachApi.listBlacklist(params);
      setEntries(data.items);
      setTotal(data.total);
    } catch { toast('Failed to load blacklist', 'error'); }
    finally { setLoading(false); }
  }, [page, search, toast]);

  useEffect(() => { loadEntries(); }, [loadEntries]);

  const handleUpload = async () => {
    if (!uploadText.trim()) return;
    setUploading(true);
    try {
      const res = await telegramOutreachApi.uploadBlacklist(uploadText, uploadReason || undefined);
      toast(`Added ${res.added} usernames to blacklist${res.skipped ? `, ${res.skipped} duplicates skipped` : ''}`, 'success');
      setUploadText('');
      setUploadReason('');
      setShowUpload(false);
      loadEntries();
    } catch { toast('Upload failed', 'error'); }
    finally { setUploading(false); }
  };

  const totalPages = Math.ceil(total / 50);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold" style={{ color: A.text1 }}>Blacklist</h2>
          <p className="text-xs mt-0.5" style={{ color: A.text3 }}>
            Blacklisted usernames are automatically filtered out when uploading recipients to campaigns.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium" style={{ color: A.text3 }}>{total} entries</span>
          <button onClick={() => setShowUpload(!showUpload)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                  style={{ background: A.blue, color: '#fff' }}>
            <Plus className="w-3.5 h-3.5" /> Add Usernames
          </button>
        </div>
      </div>

      {/* Upload Panel */}
      {showUpload && (
        <div className="rounded-lg border p-4 space-y-3" style={{ borderColor: A.border, background: A.surface }}>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: A.text1 }}>
              Usernames (one per line)
            </label>
            <p className="text-[10px] mb-2" style={{ color: A.text3 }}>
              Supports: @username, t.me/username, https://t.me/username, telegram.me/username
            </p>
            <textarea
              value={uploadText}
              onChange={e => setUploadText(e.target.value)}
              rows={6}
              placeholder={"@user1\nhttps://t.me/user2\ntelegram.me/user3\nuser4"}
              className="w-full rounded-lg border px-3 py-2 text-xs font-mono"
              style={{ borderColor: A.border, background: A.bg, color: A.text1, resize: 'vertical' }}
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: A.text1 }}>
              Reason (optional)
            </label>
            <input
              type="text"
              value={uploadReason}
              onChange={e => setUploadReason(e.target.value)}
              placeholder="e.g. Requested removal, spam report, etc."
              className="w-full rounded-lg border px-3 py-1.5 text-xs"
              style={{ borderColor: A.border, background: A.bg, color: A.text1 }}
            />
          </div>
          <div className="flex items-center gap-2">
            <button onClick={handleUpload} disabled={uploading || !uploadText.trim()}
                    className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
                    style={{ background: A.blue, color: '#fff' }}>
              {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
              {uploading ? 'Uploading...' : 'Upload'}
            </button>
            <button onClick={() => { setShowUpload(false); setUploadText(''); setUploadReason(''); }}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors"
                    style={{ borderColor: A.border, color: A.text3 }}>
              Cancel
            </button>
            {uploadText.trim() && (
              <span className="text-xs" style={{ color: A.text3 }}>
                {uploadText.trim().split('\n').filter(l => l.trim()).length} usernames
              </span>
            )}
          </div>
        </div>
      )}

      {/* Search + Bulk Actions */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: A.text3 }} />
          <input type="text" placeholder="Search blacklist..." value={search}
                 onChange={e => { setSearch(e.target.value); setPage(1); }}
                 className="pl-8 pr-3 py-1.5 rounded-lg border text-xs w-full"
                 style={{ borderColor: A.border, background: A.surface, color: A.text1 }} />
        </div>
        {selectedIds.size > 0 && (
          <div className="flex items-center gap-1.5 ml-auto">
            <span className="text-xs" style={{ color: A.text3 }}>{selectedIds.size} selected</span>
            <button
              onClick={() => setDeleteConfirm('bulk')}
              className="px-2 py-1 rounded border text-xs font-medium transition-colors"
              style={{ borderColor: '#FECDD3', color: '#E11D48', background: '#FFF1F2', cursor: 'pointer' }}
              onMouseEnter={e => { e.currentTarget.style.background = '#FFE4E6'; }}
              onMouseLeave={e => { e.currentTarget.style.background = '#FFF1F2'; }}
            >
              <Trash2 className="w-3 h-3 inline-block mr-1" /> Remove
            </button>
          </div>
        )}
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin" style={{ color: A.text3 }} /></div>
      ) : entries.length === 0 ? (
        <div className="text-center py-12 rounded-lg border" style={{ borderColor: A.border }}>
          <ShieldAlert className="w-10 h-10 mx-auto mb-3" style={{ color: A.text3 }} />
          <p className="text-sm" style={{ color: A.text3 }}>
            No blacklisted usernames yet. Add usernames to prevent sending messages to them.
          </p>
        </div>
      ) : (
        <div className="rounded-lg border overflow-hidden" style={{ borderColor: A.border }}>
          <table className="w-full text-sm">
            <thead className="border-b" style={{ borderColor: A.border, background: '#F9F9F7' }}>
              <tr>
                <th className="w-8 px-2 py-2"><input type="checkbox" onChange={e => {
                  setSelectedIds(e.target.checked ? new Set(entries.map((e: any) => e.id)) : new Set());
                }} className="rounded" /></th>
                <th className="text-left px-3 py-2 text-xs font-medium" style={{ color: A.text3 }}>Username</th>
                <th className="text-left px-3 py-2 text-xs font-medium" style={{ color: A.text3 }}>Reason</th>
                <th className="text-left px-3 py-2 text-xs font-medium" style={{ color: A.text3 }}>Added</th>
                <th className="w-10 px-2 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry: any) => (
                <tr key={entry.id}
                    className={cn('border-b transition-colors',
                      selectedIds.has(entry.id) ? '' : 'hover:bg-[#F5F5F0]')}
                    style={{ borderColor: A.border, ...(selectedIds.has(entry.id) ? { background: A.blueBg } : {}) }}>
                  <td className="px-2 py-2">
                    <input type="checkbox" checked={selectedIds.has(entry.id)}
                           onChange={() => setSelectedIds(prev => {
                             const next = new Set(prev); next.has(entry.id) ? next.delete(entry.id) : next.add(entry.id); return next;
                           })} className="rounded" />
                  </td>
                  <td className="px-3 py-2 text-xs font-mono" style={{ color: A.text1 }}>@{entry.username}</td>
                  <td className="px-3 py-2 text-xs" style={{ color: A.text3 }}>{entry.reason || '--'}</td>
                  <td className="px-3 py-2 text-xs" style={{ color: A.text3 }}>
                    {entry.created_at ? new Date(entry.created_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }) : '--'}
                  </td>
                  <td className="px-2 py-2">
                    <button
                      onClick={() => {
                        telegramOutreachApi.deleteBlacklistEntry(entry.id)
                          .then(() => { toast('Removed from blacklist', 'success'); loadEntries(); })
                          .catch(() => toast('Failed to remove', 'error'));
                      }}
                      className="p-1 rounded transition-colors"
                      style={{ cursor: 'pointer' }}
                      onMouseEnter={e => { e.currentTarget.style.background = '#FFF1F2'; }}
                      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                    >
                      <X className="w-3.5 h-3.5" style={{ color: '#E11D48' }} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm" style={{ color: A.text3 }}>{total} total</span>
          <div className="flex items-center gap-2">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
                    className={cn('px-3 py-1.5 rounded border text-sm', page <= 1 && 'opacity-50')}
                    style={{ borderColor: A.border }}>Prev</button>
            <span className="text-sm" style={{ color: A.text1 }}>Page {page}/{totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
                    className={cn('px-3 py-1.5 rounded border text-sm', page >= totalPages && 'opacity-50')}
                    style={{ borderColor: A.border }}>Next</button>
          </div>
        </div>
      )}

      {/* Bulk Delete Confirm */}
      {deleteConfirm === 'bulk' && (
        <ConfirmModal message={`Remove ${selectedIds.size} entries from blacklist?`}
          onConfirm={() => {
            setDeleteConfirm(null);
            telegramOutreachApi.bulkDeleteBlacklist(Array.from(selectedIds))
              .then(() => { toast(`Removed ${selectedIds.size} entries`, 'success'); loadEntries(); setSelectedIds(new Set()); })
              .catch(() => toast('Delete failed', 'error'));
          }}
          onCancel={() => setDeleteConfirm(null)} />
      )}
    </div>
  );
}

// CRM_STATUS_COLORS removed — using StyledSelect for status

const CRM_PIPELINE = ['cold', 'contacted', 'replied', 'interested', 'qualified', 'meeting_set', 'converted', 'not_interested'];

const PIPELINE_LABELS: Record<string, string> = {
  cold: 'New', contacted: 'Contacted', replied: 'Replied', interested: 'Interested',
  qualified: 'Qualified', meeting_set: 'Meeting', converted: 'Closed Won', not_interested: 'Closed Lost',
};

const PIPELINE_COLORS: Record<string, { bg: string; text: string; border: string; dot: string }> = {
  cold:            { bg: '#F3F4F6', text: '#374151', border: '#D1D5DB', dot: '#9CA3AF' },
  contacted:       { bg: '#EEF1FE', text: '#3B4FCF', border: '#C7D0FA', dot: '#4F6BF0' },
  replied:         { bg: '#ECFDF5', text: '#065F46', border: '#A7F3D0', dot: '#10B981' },
  interested:      { bg: '#FFF7ED', text: '#9A3412', border: '#FED7AA', dot: '#F97316' },
  qualified:       { bg: '#F5F3FF', text: '#5B21B6', border: '#DDD6FE', dot: '#8B5CF6' },
  meeting_set:     { bg: '#FDF2F8', text: '#9D174D', border: '#FBCFE8', dot: '#EC4899' },
  converted:       { bg: '#F0FDF4', text: '#166534', border: '#BBF7D0', dot: '#22C55E' },
  not_interested:  { bg: '#FEF2F2', text: '#991B1B', border: '#FECACA', dot: '#EF4444' },
};

function PipelineTab({ toast }: { toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) {
  const currentProject = useAppStore(s => s.currentProject);
  const [pipeline, setPipeline] = useState<Record<string, { count: number; contacts: any[] }>>({});
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [searchDebounced, setSearchDebounced] = useState('');
  const [draggedContact, setDraggedContact] = useState<any>(null);
  const [dragOverStatus, setDragOverStatus] = useState<string | null>(null);
  const [selectedContact, setSelectedContact] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [campaignProgress, setCampaignProgress] = useState<any[]>([]);
  const searchTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const loadPipeline = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { limit_per_status: 50 };
      if (searchDebounced) params.search = searchDebounced;
      if (currentProject?.id) params.project_id = currentProject.id;
      setPipeline(await telegramOutreachApi.getCrmPipeline(params));
    } catch { toast('Failed to load pipeline', 'error'); }
    finally { setLoading(false); }
  }, [searchDebounced, currentProject?.id, toast]);

  useEffect(() => { loadPipeline(); }, [loadPipeline]);

  const onSearchChange = (val: string) => {
    setSearch(val);
    clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => setSearchDebounced(val), 300);
  };

  const handleDragStart = (e: React.DragEvent, contact: any) => {
    setDraggedContact(contact);
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(contact.id));
  };

  const handleDragOver = (e: React.DragEvent, status: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverStatus(status);
  };

  const handleDragLeave = () => setDragOverStatus(null);

  const handleDrop = async (e: React.DragEvent, targetStatus: string) => {
    e.preventDefault();
    setDragOverStatus(null);
    if (!draggedContact || draggedContact.status === targetStatus) {
      setDraggedContact(null);
      return;
    }
    // Optimistic update
    setPipeline(prev => {
      const next = { ...prev };
      const fromKey = draggedContact.status;
      if (next[fromKey]) {
        next[fromKey] = {
          count: next[fromKey].count - 1,
          contacts: next[fromKey].contacts.filter((c: any) => c.id !== draggedContact.id),
        };
      }
      if (next[targetStatus]) {
        next[targetStatus] = {
          count: next[targetStatus].count + 1,
          contacts: [{ ...draggedContact, status: targetStatus }, ...next[targetStatus].contacts],
        };
      }
      return next;
    });
    try {
      await telegramOutreachApi.updateCrmContact(draggedContact.id, { status: targetStatus });
    } catch {
      toast('Failed to update status', 'error');
      loadPipeline();
    }
    setDraggedContact(null);
  };

  const openContact = async (c: any) => {
    setSelectedContact(c);
    setCampaignProgress([]);
    try {
      const [h, cp] = await Promise.all([
        telegramOutreachApi.getCrmContactHistory(c.id),
        telegramOutreachApi.getCrmContactCampaigns(c.id),
      ]);
      setHistory(h.history);
      setCampaignProgress(cp.campaigns || []);
    } catch { setHistory([]); setCampaignProgress([]); }
  };

  const updateStatus = async (id: number, status: string) => {
    try {
      await telegramOutreachApi.updateCrmContact(id, { status });
      loadPipeline();
    } catch { toast('Failed', 'error'); }
  };

  const totalContacts = CRM_PIPELINE.reduce((sum, s) => sum + (pipeline[s]?.count || 0), 0);

  if (loading && Object.keys(pipeline).length === 0) {
    return <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin" style={{ color: A.text3 }} /></div>;
  }

  return (
    <div className="flex flex-col h-full -m-6">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-6 py-3 border-b" style={{ borderColor: A.border, background: A.surface }}>
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: A.text3 }} />
          <input type="text" placeholder="Search leads..." value={search}
                 onChange={e => onSearchChange(e.target.value)}
                 className="pl-8 pr-3 py-1.5 rounded-lg border text-xs w-full"
                 style={{ borderColor: A.border, background: A.bg, color: A.text1 }} />
        </div>
        <span className="text-xs" style={{ color: A.text3 }}>{totalContacts} leads</span>
        {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" style={{ color: A.text3 }} />}
      </div>

      {/* Kanban Board */}
      <div className="flex-1 overflow-x-auto overflow-y-hidden">
        <div className="flex gap-3 p-4 h-full" style={{ minWidth: CRM_PIPELINE.length * 260 }}>
          {CRM_PIPELINE.map(status => {
            const col = pipeline[status] || { count: 0, contacts: [] };
            const pc = PIPELINE_COLORS[status] || PIPELINE_COLORS.cold;
            const isDropTarget = dragOverStatus === status;
            return (
              <div key={status}
                   className="flex flex-col rounded-xl transition-all"
                   style={{
                     width: 260, minWidth: 260, flexShrink: 0,
                     background: isDropTarget ? pc.bg : '#F7F7F5',
                     border: `2px ${isDropTarget ? 'dashed' : 'solid'} ${isDropTarget ? pc.dot : 'transparent'}`,
                   }}
                   onDragOver={e => handleDragOver(e, status)}
                   onDragLeave={handleDragLeave}
                   onDrop={e => handleDrop(e, status)}>
                {/* Column Header */}
                <div className="flex items-center gap-2 px-3 py-2.5 shrink-0">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: pc.dot }} />
                  <span className="text-xs font-semibold truncate" style={{ color: A.text1 }}>
                    {PIPELINE_LABELS[status] || status}
                  </span>
                  <span className="ml-auto text-[10px] font-medium rounded-full px-1.5 py-0.5"
                        style={{ background: pc.bg, color: pc.text }}>
                    {col.count}
                  </span>
                </div>

                {/* Cards */}
                <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-1.5"
                     style={{ scrollbarWidth: 'thin', scrollbarColor: `${A.border} transparent` }}>
                  {col.contacts.map((c: any) => (
                    <div key={c.id}
                         draggable
                         onDragStart={e => handleDragStart(e, c)}
                         onClick={() => openContact(c)}
                         className="rounded-lg border p-2.5 cursor-grab active:cursor-grabbing transition-shadow hover:shadow-sm"
                         style={{
                           background: A.surface, borderColor: A.border,
                           opacity: draggedContact?.id === c.id ? 0.4 : 1,
                         }}>
                      {/* Avatar + Name */}
                      <div className="flex items-center gap-2 mb-1.5">
                        <div className="w-7 h-7 rounded-full shrink-0 flex items-center justify-center text-[10px] font-bold text-white"
                             style={{ background: pc.dot }}>
                          {(c.first_name?.[0] || c.username?.[0] || '?').toUpperCase()}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="text-xs font-medium truncate" style={{ color: A.text1 }}>
                            {[c.first_name, c.last_name].filter(Boolean).join(' ') || `@${c.username}`}
                          </div>
                          {c.company_name && (
                            <div className="text-[10px] truncate" style={{ color: A.text3 }}>{c.company_name}</div>
                          )}
                        </div>
                      </div>

                      {/* Tags */}
                      {c.tags?.length > 0 && (
                        <div className="flex flex-wrap gap-1 mb-1.5">
                          {c.tags.slice(0, 3).map((tag: string, i: number) => (
                            <span key={i} className="text-[9px] px-1.5 py-0.5 rounded"
                                  style={{ background: '#F3F4F6', color: A.text2 }}>{tag}</span>
                          ))}
                          {c.tags.length > 3 && (
                            <span className="text-[9px] px-1 py-0.5" style={{ color: A.text3 }}>+{c.tags.length - 3}</span>
                          )}
                        </div>
                      )}

                      {/* Footer: messages + date */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px]" style={{ color: A.text3 }}>
                            {c.total_messages_sent} sent
                          </span>
                          {c.total_replies_received > 0 && (
                            <span className="text-[10px]" style={{ color: '#16a34a' }}>
                              {c.total_replies_received} replies
                            </span>
                          )}
                        </div>
                        <span className="text-[10px]" style={{ color: A.text3 }}>
                          {c.last_contacted_at ? new Date(c.last_contacted_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) : ''}
                        </span>
                      </div>
                    </div>
                  ))}
                  {col.contacts.length === 0 && (
                    <div className="text-center py-6">
                      <p className="text-[10px]" style={{ color: A.text3 }}>No leads</p>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Contact Detail Modal */}
      {selectedContact && (
        <ModalBackdrop onClose={() => setSelectedContact(null)}>
          <div className="w-[600px] rounded-xl border shadow-xl max-h-[80vh] overflow-y-auto"
               style={{ borderColor: A.border, background: A.surface }}>
            <div className="px-6 py-4 border-b flex items-center justify-between" style={{ borderColor: A.border }}>
              <div>
                <h2 className="text-lg font-semibold" style={{ color: A.text1 }}>@{selectedContact.username}</h2>
                <p className="text-xs" style={{ color: A.text3 }}>
                  {[selectedContact.first_name, selectedContact.last_name].filter(Boolean).join(' ')}
                  {selectedContact.company_name ? ` - ${selectedContact.company_name}` : ''}
                </p>
              </div>
              <button onClick={() => setSelectedContact(null)} className="p-1 hover:bg-[#F5F5F0] rounded">
                <X className="w-5 h-5" style={{ color: A.text3 }} />
              </button>
            </div>
            <div className="px-6 py-4 space-y-4">
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: A.text3 }}>Status</label>
                <StyledSelect
                  value={selectedContact.status}
                  onChange={v => { updateStatus(selectedContact.id, v); setSelectedContact({ ...selectedContact, status: v }); }}
                  options={CRM_PIPELINE.map(s => ({ value: s, label: PIPELINE_LABELS[s] || s }))}
                />
              </div>
              {selectedContact.campaigns?.length > 0 && (
                <div>
                  <label className="block text-xs font-medium mb-1" style={{ color: A.text3 }}>Campaigns</label>
                  <div className="text-xs" style={{ color: A.text1 }}>
                    {selectedContact.campaigns.map((c: any) => c.name).join(', ')}
                  </div>
                </div>
              )}
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-lg border p-2" style={{ borderColor: A.border }}>
                  <div className="text-lg font-bold" style={{ color: A.text1 }}>{selectedContact.total_messages_sent}</div>
                  <div className="text-[10px]" style={{ color: A.text3 }}>Sent</div>
                </div>
                <div className="rounded-lg border p-2" style={{ borderColor: A.border }}>
                  <div className="text-lg font-bold text-green-600">{selectedContact.total_replies_received}</div>
                  <div className="text-[10px]" style={{ color: A.text3 }}>Replies</div>
                </div>
                <div className="rounded-lg border p-2" style={{ borderColor: A.border }}>
                  <div className="text-lg font-bold" style={{ color: A.text1 }}>
                    {selectedContact.last_contacted_at ? new Date(selectedContact.last_contacted_at).toLocaleDateString() : '--'}
                  </div>
                  <div className="text-[10px]" style={{ color: A.text3 }}>Last Contact</div>
                </div>
              </div>
              {/* Campaign Sequence Progress */}
              {campaignProgress.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold mb-2" style={{ color: A.text1 }}>Campaign Progress</h3>
                  <div className="space-y-2">
                    {campaignProgress.map((cp: any) => (
                      <div key={cp.campaign_id} className="rounded-lg border p-3" style={{ borderColor: A.border }}>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-medium" style={{ color: A.text1 }}>{cp.campaign_name}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] px-1.5 py-0.5 rounded" style={{
                              background: cp.campaign_status === 'active' ? '#ECFDF5' : cp.campaign_status === 'paused' ? '#FEF3C7' : '#F3F4F6',
                              color: cp.campaign_status === 'active' ? '#059669' : cp.campaign_status === 'paused' ? '#D97706' : '#6B7280',
                            }}>{cp.campaign_status}</span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded" style={{
                              background: cp.recipient_status === 'replied' ? '#ECFDF5' : cp.recipient_status === 'completed' ? '#F0F9FF' : cp.recipient_status === 'failed' ? '#FFF1F2' : '#F9F9F7',
                              color: cp.recipient_status === 'replied' ? '#059669' : cp.recipient_status === 'completed' ? '#0284C7' : cp.recipient_status === 'failed' ? '#E11D48' : A.text3,
                            }}>{cp.recipient_status}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          {cp.steps.map((step: any, si: number) => {
                            const color = step.status === 'sent' ? '#9CA3AF' : step.status === 'read' ? '#3B82F6'
                              : step.status === 'replied' ? '#10B981' : step.status === 'failed' || step.status === 'spamblocked' ? '#EF4444'
                              : step.status === 'scheduled' ? '#F59E0B' : '#E5E7EB';
                            return (
                              <div key={si} className="flex items-center" title={
                                `${step.label}${step.sent_at ? `\nSent: ${new Date(step.sent_at).toLocaleString()}` : ''}${step.read_at ? `\nRead: ${new Date(step.read_at).toLocaleString()}` : ''}`
                              }>
                                <div className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold text-white" style={{ background: color }}>
                                  {si + 1}
                                </div>
                                {si < cp.steps.length - 1 && (
                                  <div className="w-4 h-0.5" style={{ background: step.status !== 'pending' ? color : '#E5E7EB' }} />
                                )}
                              </div>
                            );
                          })}
                          <span className="text-[10px] ml-1" style={{ color: A.text3 }}>
                            {cp.current_step}/{cp.total_steps}
                          </span>
                        </div>
                        <div className="mt-1.5 text-[11px]" style={{ color: A.text3 }}>
                          {cp.recipient_status === 'replied' ? (
                            <>Replied after {cp.steps.find((s: any) => s.status === 'replied')?.label || `step ${cp.current_step}`}</>
                          ) : cp.recipient_status === 'completed' ? (
                            <>Completed all {cp.total_steps} steps</>
                          ) : cp.current_step > 0 ? (
                            <>Sent {cp.steps[cp.current_step - 1]?.label || `step ${cp.current_step}`}{cp.steps[cp.current_step]
                              ? `, next: ${cp.steps[cp.current_step]?.label} (+${cp.steps[cp.current_step]?.delay_days}d)`
                              : ''}</>
                          ) : (
                            <>Pending — not yet sent</>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {history.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold mb-2" style={{ color: A.text1 }}>History</h3>
                  <div className="space-y-1.5 max-h-60 overflow-y-auto">
                    {history.map((h: any, i: number) => (
                      <div key={i} className="rounded px-3 py-2 text-xs"
                           style={{ background: h.type === 'sent' ? '#F9F9F7' : A.tealBg }}>
                        <div className="flex items-center justify-between mb-0.5">
                          <span className="font-medium" style={{ color: h.type === 'sent' ? A.text3 : A.teal }}>
                            {h.type === 'sent' ? 'Sent' : 'Reply'}
                          </span>
                          <span className="text-[10px]" style={{ color: A.text3 }}>
                            {h.time ? new Date(h.time).toLocaleString() : ''}
                          </span>
                        </div>
                        <p style={{ color: A.text1 }}>{h.text}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </ModalBackdrop>
      )}
    </div>
  );
}


function CrmTab({ t: _t, toast }: { t: any; toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) { void _t;
  const currentProject = useAppStore(s => s.currentProject);
  const [contacts, setContacts] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [selectedContact, setSelectedContact] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [campaignProgress, setCampaignProgress] = useState<any[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [crmDeleteConfirm, setCrmDeleteConfirm] = useState<string | null>(null);
  const [contactFieldDefs, setContactFieldDefs] = useState<any[]>([]);
  const [contactFieldVals, setContactFieldVals] = useState<any[]>([]);
  const [cfFilterFieldId, setCfFilterFieldId] = useState<number | null>(null);
  const [cfFilterValue, setCfFilterValue] = useState('');
  const [allFieldDefs, setAllFieldDefs] = useState<any[]>([]);

  // Load custom field definitions once
  useEffect(() => {
    telegramOutreachApi.listCustomFields().then(setAllFieldDefs).catch(() => {});
  }, []);

  const loadContacts = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { page, page_size: 50 };
      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      if (currentProject?.id) params.project_id = currentProject.id;
      if (cfFilterFieldId && cfFilterValue) {
        params.cf_field_id = cfFilterFieldId;
        params.cf_value = cfFilterValue;
      }
      const data = await telegramOutreachApi.listCrmContacts(params);
      setContacts(data.items);
      setTotal(data.total);
    } catch { toast('Failed to load contacts', 'error'); }
    finally { setLoading(false); }
  }, [page, search, statusFilter, currentProject?.id, cfFilterFieldId, cfFilterValue, toast]);

  const loadStats = useCallback(async () => {
    try { setStats(await telegramOutreachApi.getCrmStats()); } catch { /* ok */ }
  }, []);

  useEffect(() => { loadContacts(); }, [loadContacts]);
  useEffect(() => { loadStats(); }, [loadStats]);

  const openContact = async (c: any) => {
    setSelectedContact(c);
    setCampaignProgress([]);
    setContactFieldVals([]);
    try {
      const [h, cp, fds, fvs] = await Promise.all([
        telegramOutreachApi.getCrmContactHistory(c.id),
        telegramOutreachApi.getCrmContactCampaigns(c.id),
        telegramOutreachApi.listCustomFields(),
        telegramOutreachApi.getContactCustomFields(c.id),
      ]);
      setHistory(h.history);
      setCampaignProgress(cp.campaigns || []);
      setContactFieldDefs(fds);
      setContactFieldVals(fvs);
    } catch { setHistory([]); setCampaignProgress([]); }
  };

  const updateStatus = async (id: number, status: string) => {
    try {
      await telegramOutreachApi.updateCrmContact(id, { status });
      loadContacts(); loadStats();
    } catch { toast('Failed', 'error'); }
  };

  const totalPages = Math.ceil(total / 50);

  return (
    <div className="space-y-4">
      {/* Pipeline Stats */}
      <div className="grid grid-cols-8 gap-2">
        {CRM_PIPELINE.map(s => (
          <button key={s} onClick={() => { setStatusFilter(statusFilter === s ? '' : s); setPage(1); }}
                  className={cn('rounded-lg border px-3 py-2 text-center transition-colors',
                    statusFilter === s ? 'ring-2 ring-[#4F6BF0]' : '')}
                  style={{ borderColor: A.border }}>
            <div className="text-xl font-bold" style={{ color: A.text1 }}>{stats[s] || 0}</div>
            <div className="text-[10px] capitalize" style={{ color: A.text3 }}>{s.replace('_', ' ')}</div>
          </button>
        ))}
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5" style={{ color: A.text3 }} />
          <input type="text" placeholder="Search contacts..." value={search}
                 onChange={e => { setSearch(e.target.value); setPage(1); }}
                 className="pl-8 pr-3 py-1.5 rounded-lg border text-xs w-full"
                 style={{ borderColor: A.border, background: A.surface, color: A.text1 }} />
        </div>
        {allFieldDefs.length > 0 && (
          <div className="flex items-center gap-1">
            <select
              value={cfFilterFieldId ?? ''}
              onChange={e => { setCfFilterFieldId(e.target.value ? Number(e.target.value) : null); setCfFilterValue(''); setPage(1); }}
              className="px-2 py-1.5 rounded-lg border text-xs"
              style={{ borderColor: A.border, background: A.surface, color: A.text1 }}
            >
              <option value="">Filter by field...</option>
              {allFieldDefs.map((f: any) => <option key={f.id} value={f.id}>{f.name}</option>)}
            </select>
            {cfFilterFieldId && (() => {
              const fd = allFieldDefs.find((f: any) => f.id === cfFilterFieldId);
              return fd?.field_type === 'select' || fd?.field_type === 'multi_select' ? (
                <select
                  value={cfFilterValue}
                  onChange={e => { setCfFilterValue(e.target.value); setPage(1); }}
                  className="px-2 py-1.5 rounded-lg border text-xs"
                  style={{ borderColor: A.border, background: A.surface, color: A.text1 }}
                >
                  <option value="">Any</option>
                  {(fd.options_json || []).map((o: string) => <option key={o} value={o}>{o}</option>)}
                </select>
              ) : (
                <input
                  value={cfFilterValue}
                  onChange={e => { setCfFilterValue(e.target.value); setPage(1); }}
                  placeholder="Value..."
                  className="px-2 py-1.5 rounded-lg border text-xs w-28"
                  style={{ borderColor: A.border, background: A.surface, color: A.text1 }}
                />
              );
            })()}
            {cfFilterFieldId && (
              <button onClick={() => { setCfFilterFieldId(null); setCfFilterValue(''); setPage(1); }}
                className="p-1 rounded hover:opacity-70" style={{ color: A.text3 }}>
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        )}
        <span className="text-xs" style={{ color: A.text3 }}>{total} contacts</span>
        {selectedIds.size > 0 && (
          <div className="flex items-center gap-1.5 ml-auto">
            <span className="text-xs" style={{ color: A.text3 }}>{selectedIds.size} selected</span>
            <StyledSelect
              value=""
              onChange={v => {
                if (!v) return;
                telegramOutreachApi.bulkUpdateCrmStatus(Array.from(selectedIds), v)
                  .then(() => { toast('Updated', 'success'); loadContacts(); loadStats(); setSelectedIds(new Set()); })
                  .catch(() => toast('Failed', 'error'));
              }}
              placeholder="Set status..."
              options={CRM_PIPELINE.map(s => ({ value: s, label: s.replace('_', ' ') }))}
            />
            <button
              onClick={() => setCrmDeleteConfirm('bulk')}
              className="px-2 py-1 rounded border text-xs font-medium transition-colors"
              style={{ borderColor: '#FECDD3', color: '#E11D48', background: '#FFF1F2', cursor: 'pointer' }}
              onMouseEnter={e => { e.currentTarget.style.background = '#FFE4E6'; }}
              onMouseLeave={e => { e.currentTarget.style.background = '#FFF1F2'; }}
            >
              <Trash2 className="w-3 h-3 inline-block mr-1" /> Delete
            </button>
          </div>
        )}
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="w-6 h-6 animate-spin" style={{ color: A.text3 }} /></div>
      ) : contacts.length === 0 ? (
        <div className="text-center py-12 rounded-lg border" style={{ borderColor: A.border }}>
          <Users className="w-10 h-10 mx-auto mb-3" style={{ color: A.text3 }} />
          <p className="text-sm" style={{ color: A.text3 }}>No CRM contacts yet. Contacts auto-created when campaigns send messages.</p>
        </div>
      ) : (
        <div className="rounded-lg border overflow-hidden" style={{ borderColor: A.border }}>
          <table className="w-full text-sm">
            <thead className="border-b" style={{ borderColor: A.border, background: '#F9F9F7' }}>
              <tr>
                <th className="w-8 px-2 py-2"><input type="checkbox" onChange={e => {
                  setSelectedIds(e.target.checked ? new Set(contacts.map((c: any) => c.id)) : new Set());
                }} className="rounded" /></th>
                <th className="text-left px-3 py-2 text-xs font-medium" style={{ color: A.text3 }}>Username</th>
                <th className="text-left px-3 py-2 text-xs font-medium" style={{ color: A.text3 }}>Name</th>
                <th className="text-left px-3 py-2 text-xs font-medium" style={{ color: A.text3 }}>Company</th>
                <th className="text-left px-3 py-2 text-xs font-medium" style={{ color: A.text3 }}>Status</th>
                <th className="text-left px-2 py-2 text-xs font-medium" style={{ color: A.text3 }}>Sent</th>
                <th className="text-left px-2 py-2 text-xs font-medium" style={{ color: A.text3 }}>Replies</th>
                <th className="text-left px-3 py-2 text-xs font-medium" style={{ color: A.text3 }}>Campaigns</th>
                <th className="text-left px-3 py-2 text-xs font-medium" style={{ color: A.text3 }}>Last Contact</th>
              </tr>
            </thead>
            <tbody>
              {contacts.map((c: any) => (
                <tr key={c.id} onClick={() => openContact(c)}
                    className={cn('border-b cursor-pointer transition-colors',
                      selectedIds.has(c.id) ? '' : 'hover:bg-[#F5F5F0]')}
                    style={{ borderColor: A.border, ...(selectedIds.has(c.id) ? { background: A.blueBg } : {}) }}>
                  <td className="px-2 py-2" onClick={e => e.stopPropagation()}>
                    <input type="checkbox" checked={selectedIds.has(c.id)}
                           onChange={() => setSelectedIds(prev => {
                             const next = new Set(prev); next.has(c.id) ? next.delete(c.id) : next.add(c.id); return next;
                           })} className="rounded" />
                  </td>
                  <td className="px-3 py-2 text-xs" style={{ color: A.text1 }}>@{c.username}</td>
                  <td className="px-3 py-2 text-xs" style={{ color: A.text1 }}>{[c.first_name, c.last_name].filter(Boolean).join(' ') || '--'}</td>
                  <td className="px-3 py-2 text-xs" style={{ color: A.text3 }}>{c.company_name || '--'}</td>
                  <td className="px-3 py-2" onClick={e => e.stopPropagation()}>
                    <StyledSelect
                      value={c.status}
                      onChange={v => updateStatus(c.id, v)}
                      options={CRM_PIPELINE.map(s => ({ value: s, label: s.replace('_', ' ') }))}
                    />
                  </td>
                  <td className="px-2 py-2 text-xs" style={{ color: A.text1, fontVariantNumeric: 'tabular-nums' }}>{c.total_messages_sent}</td>
                  <td className="px-2 py-2 text-xs" style={{ color: c.total_replies_received > 0 ? '#16a34a' : A.text3, fontVariantNumeric: 'tabular-nums' }}>
                    {c.total_replies_received}
                  </td>
                  <td className="px-3 py-2 text-[10px]" style={{ color: A.text3 }}>
                    {(c.campaigns || []).map((camp: any) => camp.name).join(', ').substring(0, 30) || '--'}
                  </td>
                  <td className="px-3 py-2 text-xs" style={{ color: A.text3 }}>
                    {c.last_contacted_at ? new Date(c.last_contacted_at).toLocaleDateString() : '--'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm" style={{ color: A.text3 }}>{total} total</span>
          <div className="flex items-center gap-2">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
                    className={cn('px-3 py-1.5 rounded border text-sm', page <= 1 && 'opacity-50')}
                    style={{ borderColor: A.border }}>Prev</button>
            <span className="text-sm" style={{ color: A.text1 }}>Page {page}/{totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
                    className={cn('px-3 py-1.5 rounded border text-sm', page >= totalPages && 'opacity-50')}
                    style={{ borderColor: A.border }}>Next</button>
          </div>
        </div>
      )}

      {/* Contact Detail Modal */}
      {selectedContact && (
        <ModalBackdrop onClose={() => setSelectedContact(null)}>
          <div className="w-[600px] rounded-xl border shadow-xl max-h-[80vh] overflow-y-auto"
               style={{ borderColor: A.border, background: A.surface }}>
            <div className="px-6 py-4 border-b flex items-center justify-between" style={{ borderColor: A.border }}>
              <div>
                <h2 className="text-lg font-semibold" style={{ color: A.text1 }}>@{selectedContact.username}</h2>
                <p className="text-xs" style={{ color: A.text3 }}>
                  {[selectedContact.first_name, selectedContact.last_name].filter(Boolean).join(' ')}
                  {selectedContact.company_name ? ` - ${selectedContact.company_name}` : ''}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCrmDeleteConfirm('single')}
                  className="p-1.5 rounded transition-colors"
                  style={{ cursor: 'pointer' }}
                  title="Delete contact"
                  onMouseEnter={e => { e.currentTarget.style.background = '#FFF1F2'; }}
                  onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                >
                  <Trash2 className="w-4 h-4" style={{ color: '#E11D48' }} />
                </button>
                <button onClick={() => setSelectedContact(null)} className="p-1 hover:bg-[#F5F5F0] rounded">
                  <X className="w-5 h-5" style={{ color: A.text3 }} />
                </button>
              </div>
            </div>
            <div className="px-6 py-4 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium mb-1" style={{ color: A.text3 }}>Status</label>
                  <select value={selectedContact.status}
                          onChange={e => { updateStatus(selectedContact.id, e.target.value); setSelectedContact({...selectedContact, status: e.target.value}); }}
                          className="w-full px-3 py-2 rounded-lg border text-sm"
                          style={{ borderColor: A.border, background: A.surface, color: A.text1 }}>
                    {CRM_PIPELINE.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1" style={{ color: A.text3 }}>Campaigns</label>
                  <div className="text-xs pt-2" style={{ color: A.text1 }}>
                    {(selectedContact.campaigns || []).map((c: any) => c.name).join(', ') || 'None'}
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-lg border p-2" style={{ borderColor: A.border }}>
                  <div className="text-lg font-bold" style={{ color: A.text1 }}>{selectedContact.total_messages_sent}</div>
                  <div className="text-[10px]" style={{ color: A.text3 }}>Sent</div>
                </div>
                <div className="rounded-lg border p-2" style={{ borderColor: A.border }}>
                  <div className="text-lg font-bold text-green-600">{selectedContact.total_replies_received}</div>
                  <div className="text-[10px]" style={{ color: A.text3 }}>Replies</div>
                </div>
                <div className="rounded-lg border p-2" style={{ borderColor: A.border }}>
                  <div className="text-lg font-bold" style={{ color: A.text1 }}>
                    {selectedContact.last_reply_at ? new Date(selectedContact.last_reply_at).toLocaleDateString() : '--'}
                  </div>
                  <div className="text-[10px]" style={{ color: A.text3 }}>Last Reply</div>
                </div>
              </div>
              {/* Campaign Sequence Progress */}
              {campaignProgress.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold mb-2" style={{ color: A.text1 }}>Campaign Progress</h3>
                  <div className="space-y-2">
                    {campaignProgress.map((cp: any) => (
                      <div key={cp.campaign_id} className="rounded-lg border p-3" style={{ borderColor: A.border }}>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-medium" style={{ color: A.text1 }}>{cp.campaign_name}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] px-1.5 py-0.5 rounded" style={{
                              background: cp.campaign_status === 'active' ? '#ECFDF5' : cp.campaign_status === 'paused' ? '#FEF3C7' : '#F3F4F6',
                              color: cp.campaign_status === 'active' ? '#059669' : cp.campaign_status === 'paused' ? '#D97706' : '#6B7280',
                            }}>{cp.campaign_status}</span>
                            <span className="text-[10px] px-1.5 py-0.5 rounded" style={{
                              background: cp.recipient_status === 'replied' ? '#ECFDF5' : cp.recipient_status === 'completed' ? '#F0F9FF' : cp.recipient_status === 'failed' ? '#FFF1F2' : '#F9F9F7',
                              color: cp.recipient_status === 'replied' ? '#059669' : cp.recipient_status === 'completed' ? '#0284C7' : cp.recipient_status === 'failed' ? '#E11D48' : A.text3,
                            }}>{cp.recipient_status}</span>
                          </div>
                        </div>
                        {/* Step indicators */}
                        <div className="flex items-center gap-1">
                          {cp.steps.map((step: any, si: number) => {
                            const color = step.status === 'sent' ? '#9CA3AF' : step.status === 'read' ? '#3B82F6'
                              : step.status === 'replied' ? '#10B981' : step.status === 'failed' || step.status === 'spamblocked' ? '#EF4444'
                              : step.status === 'scheduled' ? '#F59E0B' : '#E5E7EB';
                            return (
                              <div key={si} className="flex items-center" title={
                                `${step.label}${step.sent_at ? `\nSent: ${new Date(step.sent_at).toLocaleString()}` : ''}${step.read_at ? `\nRead: ${new Date(step.read_at).toLocaleString()}` : ''}`
                              }>
                                <div className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold text-white" style={{ background: color }}>
                                  {si + 1}
                                </div>
                                {si < cp.steps.length - 1 && (
                                  <div className="w-4 h-0.5" style={{ background: step.status !== 'pending' ? color : '#E5E7EB' }} />
                                )}
                              </div>
                            );
                          })}
                          <span className="text-[10px] ml-1" style={{ color: A.text3 }}>
                            {cp.current_step}/{cp.total_steps}
                          </span>
                        </div>
                        {/* Current step text summary */}
                        <div className="mt-1.5 text-[11px]" style={{ color: A.text3 }}>
                          {cp.recipient_status === 'replied' ? (
                            <>Replied after {cp.steps.find((s: any) => s.status === 'replied')?.label || `step ${cp.current_step}`}</>
                          ) : cp.recipient_status === 'completed' ? (
                            <>Completed all {cp.total_steps} steps</>
                          ) : cp.current_step > 0 ? (
                            <>Sent {cp.steps[cp.current_step - 1]?.label || `step ${cp.current_step}`}{cp.steps[cp.current_step]
                              ? `, next: ${cp.steps[cp.current_step]?.label} (+${cp.steps[cp.current_step]?.delay_days}d)`
                              : ''}</>
                          ) : (
                            <>Pending — not yet sent</>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {/* Custom Properties */}
              {contactFieldDefs.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold mb-2" style={{ color: A.text1 }}>Custom Properties</h3>
                  <div className="grid grid-cols-2 gap-2">
                    {contactFieldDefs.map((fd: any) => {
                      const cv = contactFieldVals.find((v: any) => v.field_id === fd.id);
                      return (
                        <div key={fd.id}>
                          <label className="block text-[10px] font-medium mb-0.5" style={{ color: A.text3 }}>{fd.name}</label>
                          {fd.field_type === 'select' ? (
                            <select
                              className="w-full px-2 py-1 rounded border text-xs"
                              style={{ borderColor: A.border, background: A.bg, color: A.text1 }}
                              defaultValue={cv?.value || ''}
                              onChange={async (e) => {
                                try {
                                  await telegramOutreachApi.updateContactCustomFields(selectedContact.id, [{ field_id: fd.id, value: e.target.value || null }]);
                                } catch { /* silent */ }
                              }}
                            >
                              <option value="">—</option>
                              {(fd.options_json || []).map((o: string) => <option key={o} value={o}>{o}</option>)}
                            </select>
                          ) : (
                            <input
                              className="w-full px-2 py-1 rounded border text-xs outline-none"
                              style={{ borderColor: A.border, background: A.bg, color: A.text1 }}
                              type={fd.field_type === 'number' ? 'number' : fd.field_type === 'date' ? 'date' : 'text'}
                              defaultValue={cv?.value || ''}
                              placeholder="—"
                              onBlur={async (e) => {
                                try {
                                  await telegramOutreachApi.updateContactCustomFields(selectedContact.id, [{ field_id: fd.id, value: e.target.value.trim() || null }]);
                                } catch { /* silent */ }
                              }}
                            />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
              <div>
                <h3 className="text-xs font-semibold mb-2" style={{ color: A.text1 }}>History</h3>
                {history.length === 0 ? (
                  <p className="text-xs text-center py-4" style={{ color: A.text3 }}>No messages yet</p>
                ) : (
                  <div className="space-y-1.5 max-h-60 overflow-y-auto">
                    {history.map((h: any, i: number) => (
                      <div key={i} className="rounded px-3 py-2 text-xs"
                           style={{ background: h.type === 'sent' ? '#F9F9F7' : A.tealBg }}>
                        <div className="flex items-center justify-between mb-0.5">
                          <span className="font-medium" style={{ color: h.type === 'sent' ? A.text3 : A.teal }}>
                            {h.type === 'sent' ? 'Sent' : 'Reply'}
                          </span>
                          <span className="text-[10px]" style={{ color: A.text3 }}>
                            {h.time ? new Date(h.time).toLocaleString() : ''}
                          </span>
                        </div>
                        <p style={{ color: A.text1 }}>{h.text}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </ModalBackdrop>
      )}
      {crmDeleteConfirm === 'bulk' && (
        <ConfirmModal message={`Delete ${selectedIds.size} contacts?`}
          onConfirm={() => {
            setCrmDeleteConfirm(null);
            telegramOutreachApi.bulkDeleteCrmContacts(Array.from(selectedIds))
              .then(() => { toast(`Deleted ${selectedIds.size} contacts`, 'success'); loadContacts(); loadStats(); setSelectedIds(new Set()); })
              .catch(() => toast('Delete failed', 'error'));
          }}
          onCancel={() => setCrmDeleteConfirm(null)} />
      )}
      {crmDeleteConfirm === 'single' && selectedContact && (
        <ConfirmModal message={`Delete contact @${selectedContact.username}?`}
          onConfirm={() => {
            setCrmDeleteConfirm(null);
            telegramOutreachApi.deleteCrmContact(selectedContact.id)
              .then(() => { toast('Contact deleted', 'success'); setSelectedContact(null); loadContacts(); loadStats(); })
              .catch(() => toast('Delete failed', 'error'));
          }}
          onCancel={() => setCrmDeleteConfirm(null)} />
      )}
    </div>
  );
}
