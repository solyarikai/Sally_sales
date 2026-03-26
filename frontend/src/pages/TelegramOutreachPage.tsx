import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users, Send, Shield, Plus, Search, Trash2,
  Globe, Loader2, Play, Pause, Filter, ArrowUpDown, ArrowUp, ArrowDown,
  X, Upload, Edit3, ChevronDown, BookOpen, Check, Minus, Download, RotateCw, RefreshCw,
  MessageCircle,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { useToast } from '../components/Toast';
import { telegramOutreachApi } from '../api/telegramOutreach';
import type {
  TgAccount, TgAccountTag, TgProxyGroup, TgProxy, TgCampaign,
} from '../api/telegramOutreach';

type Tab = 'accounts' | 'campaigns' | 'proxies' | 'parser' | 'crm' | 'inbox' | 'info';

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

const ACCOUNT_STATUS_COLORS: Record<string, string> = {
  active: `bg-[${A.tealBg}] text-[${A.teal}]`,
  paused: 'bg-amber-50 text-amber-600 dark:bg-amber-900/20 dark:text-amber-400',
  spamblocked: `bg-[${A.roseBg}] text-[${A.rose}]`,
  dead: 'bg-gray-100 text-gray-500 dark:bg-gray-700/30 dark:text-gray-400',
  frozen: 'bg-blue-50 text-blue-600 dark:bg-blue-900/20 dark:text-blue-400',
};

// Campaign status colors now handled inline in CampaignsTab

function StatusBadge({ status, colorMap }: { status: string; colorMap: Record<string, string> }) {
  return (
    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', colorMap[status] || 'bg-gray-100 text-gray-600')}>
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

  const [tab, setTab] = useState<Tab>('accounts');
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

  const tabs: { key: Tab; label: string; icon: typeof Users }[] = [
    { key: 'accounts', label: 'Accounts', icon: Users },
    { key: 'campaigns', label: 'Campaigns', icon: Send },
    { key: 'proxies', label: 'Proxies', icon: Shield },
    { key: 'parser', label: 'Parser', icon: Search },
    { key: 'crm', label: 'CRM', icon: Users },
    { key: 'inbox', label: 'Inbox', icon: MessageCircle },
    { key: 'info', label: 'Info', icon: BookOpen },
  ];

  return (
    <div className="flex flex-col h-full" style={{ background: A.bg }}>
      {/* Header */}
      <div className="px-6 py-4" style={{ background: A.surface, borderBottom: `1px solid ${A.border}` }}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold" style={{ color: A.text1 }}>Telegram Outreach</h1>
            <p className="text-sm mt-1" style={{ color: A.text3 }}>
              Manage accounts, campaigns, and proxies for Telegram outreach
            </p>
          </div>

          {/* Worker status */}
          <span className={cn('flex items-center gap-1.5 text-xs font-medium',
            workerRunning ? 'text-green-600' : 'text-red-500')}>
            <span className={cn('w-2 h-2 rounded-full',
              workerRunning ? 'bg-green-500 animate-pulse' : 'bg-red-500')} />
            {workerRunning ? 'Worker Active' : 'Worker Offline'}
          </span>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mt-4">
          {tabs.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
              style={tab === key
                ? { background: A.blueBg, color: A.blue }
                : { color: A.text3 }}
              onMouseEnter={e => { if (tab !== key) (e.currentTarget.style.background = '#F3F3F1'); }}
              onMouseLeave={e => { if (tab !== key) (e.currentTarget.style.background = 'transparent'); }}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto p-6">
        {tab === 'accounts' && <AccountsTab t={t} toast={toast} />}
        {tab === 'campaigns' && <CampaignsTab t={t} toast={toast} />}
        {tab === 'proxies' && <ProxiesTab t={t} toast={toast} />}
        {tab === 'parser' && <ParserTab t={t} toast={toast} />}
        {tab === 'crm' && <CrmTab t={t} toast={toast} />}
        {tab === 'inbox' && <InboxTab toast={toast} />}
        {tab === 'info' && <InfoTab t={t} />}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Accounts Tab
// ══════════════════════════════════════════════════════════════════════

function AccountsTab({ t, toast }: { t: any; toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) {
  const { isDark } = useTheme();
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
  const [showImportModal, setShowImportModal] = useState(false);
  const [editingAccount, setEditingAccount] = useState<TgAccount | null>(null);

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { page, page_size: 50 };
      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      const data = await telegramOutreachApi.listAccounts(params);
      setAccounts(data.items);
      setTotal(data.total);
    } catch {
      toast('Failed to load accounts', 'error');
    } finally {
      setLoading(false);
    }
  }, [page, search, statusFilter, toast]);

  const loadTags = useCallback(async () => {
    try { setTags(await telegramOutreachApi.listTags()); } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadAccounts(); }, [loadAccounts]);
  useEffect(() => { loadTags(); }, [loadTags]);

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
        case 'age': return acc.session_created_at || '';
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
              <button onClick={() => { setShowAddMenu(false); setShowAddModal(true); }}
                className="w-full text-left px-3 py-2 text-[13px] hover:bg-[#F5F5F0] transition-colors"
                style={{ color: A.text1 }}>
                <Plus className="w-3.5 h-3.5 inline mr-2 opacity-50" />Single Account
              </button>
              <button onClick={() => { setShowAddMenu(false); setShowImportModal(true); }}
                className="w-full text-left px-3 py-2 text-[13px] hover:bg-[#F5F5F0] transition-colors"
                style={{ color: A.text1 }}>
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

      {/* Bulk actions bar (inline, not fixed) */}
      {selectedIds.size > 0 && (
        <BulkActionsBar
          selectedIds={selectedIds}
          t={t}
          toast={toast}
          onDone={() => { setSelectedIds(new Set()); loadAccounts(); }}
        />
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
                const atLimit = acc.messages_sent_today >= acc.daily_message_limit;
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
                             style={{ backgroundColor: `hsl(${hue}, 45%, 60%)` }}>
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
                    <td className="px-2 py-2.5 font-mono text-[12px] whitespace-nowrap cursor-pointer"
                        style={{ color: A.text2 }}
                        onClick={e => { e.stopPropagation(); navigator.clipboard.writeText(acc.phone); toast('Copied', 'info'); }}
                        title="Click to copy">{acc.phone}</td>
                    <td className="px-1 py-2.5 text-center" title={acc.country_code || ''}>
                      {acc.country_code ? <CountryFlag code={acc.country_code} /> : <span className="text-[12px]" style={{ color: A.text3 }}>--</span>}
                    </td>
                    <td className="px-3 py-2.5 text-[12px] truncate" style={{ color: A.text2, maxWidth: 120 }}>
                      {acc.username ? `@${acc.username}` : <span style={{ color: A.text3 }}>--</span>}
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <StatusBadge status={acc.status} colorMap={ACCOUNT_STATUS_COLORS} />
                        {acc.spamblock_type !== 'none' && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium" style={{ background: A.roseBg, color: A.rose }}>
                            {acc.spamblock_type}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-2 py-2.5 text-[12px] whitespace-nowrap" style={{ color: A.text3 }}>
                      {acc.session_created_at ? (() => {
                        const days = Math.floor((Date.now() - new Date(acc.session_created_at).getTime()) / 86400000);
                        return days >= 30 ? `${Math.floor(days / 30)}m ${days % 30}d` : `${days}d`;
                      })() : '--'}
                    </td>
                    <td className="px-2 py-2.5 text-[12px] whitespace-nowrap tabular-nums">
                      <span style={{ color: atLimit ? A.rose : A.text1, fontWeight: atLimit ? 600 : 400 }}>{acc.messages_sent_today}</span>
                      <span style={{ color: A.text3 }}>/{acc.daily_message_limit}</span>
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
  const [campaigns, setCampaigns] = useState<TgCampaign[]>([]);
  const [loading, setLoading] = useState(true);

  const loadCampaigns = useCallback(async () => {
    setLoading(true);
    try {
      const data = await telegramOutreachApi.listCampaigns();
      setCampaigns(data.items);
    } catch {
      toast('Failed to load campaigns', 'error');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { loadCampaigns(); }, [loadCampaigns]);

  const handleCreate = async () => {
    try {
      await telegramOutreachApi.createCampaign({ name: 'New Campaign' });
      toast('Campaign created', 'success');
      loadCampaigns();
    } catch {
      toast('Failed to create campaign', 'error');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await telegramOutreachApi.deleteCampaign(id);
      toast('Campaign deleted', 'success');
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
                  onClick={() => navigate(`/telegram-outreach/campaign/${c.id}`)}
                  onMouseEnter={e => { e.currentTarget.style.background = '#F8F8F5'; }}
                  onMouseLeave={e => { e.currentTarget.style.background = ''; }}
                >
                  <td style={{ padding: '12px 16px', fontWeight: 500, color: A.text1, maxWidth: 260 }}>
                    <span className="truncate block">{c.name}</span>
                  </td>
                  <td style={{ padding: '12px 12px' }}>{statusBadge(c.status)}</td>
                  <td style={{ padding: '12px 12px', minWidth: 100 }}>{progressBar(c)}</td>
                  <td style={{ padding: '12px 12px', textAlign: 'right', fontSize: 12, color: A.text1, fontVariantNumeric: 'tabular-nums' }}>{c.total_messages_sent}</td>
                  <td style={{ padding: '12px 12px', textAlign: 'right', fontSize: 12, color: A.text1, fontVariantNumeric: 'tabular-nums' }}>{c.messages_sent_today}</td>
                  <td style={{ padding: '12px 12px', textAlign: 'right', fontSize: 12, color: A.text3 }}>&mdash;</td>
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
                      <button
                        onClick={() => handleDelete(c.id)}
                        title="Delete"
                        style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, borderRadius: 6, border: `1px solid ${A.border}`, background: 'transparent', cursor: 'pointer' }}
                        onMouseEnter={e => { e.currentTarget.style.background = A.roseBg; }}
                        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
                      >
                        <Trash2 className="w-3.5 h-3.5" style={{ color: A.rose }} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
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
                      <td className="px-3 py-2 font-mono text-xs" style={{ color: A.text1 }}>{p.host}</td>
                      <td className="px-3 py-2 font-mono text-xs" style={{ color: A.text1 }}>{p.port}</td>
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
// Bulk Actions Bar
// ══════════════════════════════════════════════════════════════════════

function BulkActionsBar({ selectedIds, t, toast, onDone }: {
  selectedIds: Set<number>; t: any; toast: any; onDone: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [activePanel, setActivePanel] = useState<string | null>(null);
  // Panel values
  const [limitValue, setLimitValue] = useState('10');
  const [bioValue, setBioValue] = useState('');
  const [twoFaValue, setTwoFaValue] = useState('');
  const [langCode, setLangCode] = useState('pt');
  const [sysLangCode, setSysLangCode] = useState('pt-PT');
  const [proxyGroupId, setProxyGroupId] = useState<number | ''>('');
  const [proxyGroups, setProxyGroups] = useState<TgProxyGroup[]>([]);
  const [nameCategory, setNameCategory] = useState('male_en');
  const photoInputRef = useRef<HTMLInputElement>(null);

  const ids = Array.from(selectedIds);

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

  const btnCls = 'flex items-center gap-1.5 px-2.5 py-[5px] rounded-md border text-[12px] font-medium transition-colors disabled:opacity-40';
  const btnStyle = { borderColor: A.border, color: A.text1, background: A.surface };
  const inputCls = cn('px-2 py-1 rounded-md border text-[12px] outline-none focus:border-[#4F6BF0]/50', t.cardBorder, t.cardBg, t.text1);

  return (
    <div className="rounded-xl border p-3 space-y-2" style={{ borderColor: A.blue + '25', background: A.blueBg }}>
      {/* Main buttons row */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[12px] font-semibold mr-1" style={{ color: A.blue }}>{selectedIds.size} selected</span>
        <button onClick={onDone} className="text-[11px] underline mr-1" style={{ color: A.text3 }}>Deselect</button>
        <div className="w-px h-4" style={{ background: A.border }} />

        {/* Dropdown: Оформление аккаунта */}
        <div className="relative">
          <button onClick={() => setActivePanel(activePanel === 'menu_profile' ? null : 'menu_profile')}
            className={btnCls} style={btnStyle}>
            <Users className="w-3 h-3" /> Оформление аккаунта <ChevronDown className="w-3 h-3" />
          </button>
          {activePanel === 'menu_profile' && (
            <div className="absolute top-full left-0 mt-1 w-44 rounded-lg border shadow-lg z-50 py-1"
              style={{ background: A.surface, borderColor: A.border }}>
              <button onClick={() => setActivePanel('names')} className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1 }}>
                Names
              </button>
              <button onClick={() => setActivePanel('bio')} className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1 }}>
                Bio
              </button>
              <button onClick={() => { setActivePanel(null); photoInputRef.current?.click(); }} className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1 }}>
                Photo
              </button>
              <button onClick={() => { setActivePanel(null); toast('Username — Coming soon', 'info'); }} className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1 }}>
                Username
              </button>
            </div>
          )}
        </div>
        <input ref={photoInputRef} type="file" accept="image/*" multiple className="hidden"
               onChange={async e => {
                 const files = e.target.files;
                 if (!files || files.length === 0) return;
                 setLoading(true);
                 try {
                   const res = await telegramOutreachApi.bulkSetPhoto(ids, Array.from(files));
                   toast(`Photos set for ${res.count} accounts (${res.photos_uploaded} photos)`, 'success');
                   onDone();
                 } catch { toast('Failed to set photos', 'error'); }
                 finally { setLoading(false); }
                 e.target.value = '';
               }} />

        {/* Dropdown: Технические настройки */}
        <div className="relative">
          <button onClick={() => setActivePanel(activePanel === 'menu_tech' ? null : 'menu_tech')}
            className={btnCls} style={btnStyle}>
            <RotateCw className="w-3 h-3" /> Технические настройки <ChevronDown className="w-3 h-3" />
          </button>
          {activePanel === 'menu_tech' && (
            <div className="absolute top-full left-0 mt-1 w-44 rounded-lg border shadow-lg z-50 py-1"
              style={{ background: A.surface, borderColor: A.border }}>
              <button onClick={() => { setActivePanel(null); run('Device randomized', () => telegramOutreachApi.bulkRandomizeDevice(ids)); }} className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1 }}>
                Device
              </button>
              <button onClick={() => setActivePanel('limit')} className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1 }}>
                Limit
              </button>
              <button onClick={() => setActivePanel('lang')} className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1 }}>
                Language
              </button>
              <button onClick={() => setActivePanel('2fa')} className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1 }}>
                2FA
              </button>
              <button onClick={() => setActivePanel('proxy')} className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1 }}>
                Proxy
              </button>
              <button onClick={() => setActivePanel('privacy')} className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1 }}>
                Privacy
              </button>
            </div>
          )}
        </div>

        {/* Dropdown: Session Settings */}
        <div className="relative">
          <button onClick={() => setActivePanel(activePanel === 'menu_session' ? null : 'menu_session')}
            className={btnCls} style={btnStyle}>
            <RefreshCw className="w-3 h-3" /> Session Settings <ChevronDown className="w-3 h-3" />
          </button>
          {activePanel === 'menu_session' && (
            <div className="absolute top-full left-0 mt-1 w-44 rounded-lg border shadow-lg z-50 py-1"
              style={{ background: A.surface, borderColor: A.border }}>
              <button onClick={() => { setActivePanel(null); run('Re-authorized', () => telegramOutreachApi.bulkReauthorize(ids)); }} className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1 }}>
                Re-Auth
              </button>
              <button onClick={() => { setActivePanel(null); run('Sessions revoked', () => telegramOutreachApi.bulkRevokeSessions(ids)); }} className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1 }}>
                Revoke Session
              </button>
              <button onClick={() => { setActivePanel(null); run('Cleaned', () => telegramOutreachApi.bulkClean(ids, { delete_dialogs: true, delete_contacts: true })); }} className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[#F5F5F0]" style={{ color: A.text1 }}>
                Clean Dialogs
              </button>
            </div>
          )}
        </div>

        <div className="w-px h-4" style={{ background: A.border }} />

        {/* Checks — standalone */}
        <button onClick={() => run('Alive check done', () => telegramOutreachApi.bulkCheckAlive(ids))}
                disabled={loading} className={btnCls} style={{ ...btnStyle, color: A.teal, borderColor: A.teal + '40' }}
                title="Quick alive check. Safe to run often.">
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />} Alive?
        </button>
        <button onClick={() => run('Spamblock checked', () => telegramOutreachApi.bulkCheck(ids))}
                disabled={loading} className={btnCls} style={{ ...btnStyle, color: '#D97706', borderColor: '#D9770640' }}
                title="Full spamblock check. Don't run too often.">
          <Shield className="w-3 h-3" /> Spam?
        </button>

        {/* Delete — far right */}
        <div className="ml-auto">
          <button onClick={async () => {
                    if (!confirm(`Delete ${ids.length} accounts?`)) return;
                    setLoading(true);
                    try { for (const id of ids) await telegramOutreachApi.deleteAccount(id);
                          toast(`${ids.length} deleted`, 'success'); onDone();
                    } catch { toast('Delete failed', 'error'); } finally { setLoading(false); }
                  }} disabled={loading}
                  className="flex items-center gap-1.5 px-2.5 py-[5px] rounded-md text-[12px] font-medium transition-colors disabled:opacity-40"
                  style={{ background: A.roseBg, color: A.rose }}>
            <Trash2 className="w-3 h-3" /> Delete
          </button>
        </div>
      </div>

      {/* Expandable panels */}
      {activePanel === 'names' && (
        <div className="flex items-center gap-2 pt-1">
          <span className={cn('text-xs', t.text3)}>Names:</span>
          <select value={nameCategory} onChange={e => setNameCategory(e.target.value)} className={inputCls}>
            <option value="male_en">Male (English)</option>
            <option value="female_en">Female (English)</option>
            <option value="male_pt">Male (Portuguese)</option>
            <option value="female_pt">Female (Portuguese)</option>
            <option value="male_ru">Male (Russian)</option>
            <option value="female_ru">Female (Russian)</option>
          </select>
          <button onClick={() => run('Names randomized', () => telegramOutreachApi.bulkRandomizeNames(ids, nameCategory))}
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
          <button onClick={() => run('Bio set', () => telegramOutreachApi.bulkSetBio(ids, bioValue))}
                  disabled={loading || !bioValue} className="px-3 py-1 text-white rounded-md text-[12px] font-medium" style={{ background: A.blue }}>Apply</button>
        </div>
      )}
      {activePanel === '2fa' && (
        <div className="flex items-center gap-2 pt-1">
          <span className={cn('text-xs', t.text3)}>2FA password:</span>
          <input type="text" value={twoFaValue} onChange={e => setTwoFaValue(e.target.value)}
                 className={cn(inputCls, 'w-40')} />
          <button onClick={() => run('2FA set', () => telegramOutreachApi.bulkSet2FA(ids, twoFaValue))}
                  disabled={loading || !twoFaValue} className="px-3 py-1 text-white rounded-md text-[12px] font-medium" style={{ background: A.blue }}>Apply</button>
        </div>
      )}
      {activePanel === 'lang' && (
        <div className="flex items-center gap-2 pt-1">
          <span className={cn('text-xs', t.text3)}>Lang:</span>
          <select value={langCode} onChange={e => setLangCode(e.target.value)} className={inputCls}>
            {['en','pt','es','de','fr','it','nl','ru'].map(l => <option key={l}>{l}</option>)}
          </select>
          <select value={sysLangCode} onChange={e => setSysLangCode(e.target.value)} className={inputCls}>
            {['en-US','pt-PT','es-ES','de-DE','fr-FR','it-IT','nl-NL','ru-RU'].map(l => <option key={l}>{l}</option>)}
          </select>
          <button onClick={() => run('Language set', () => telegramOutreachApi.bulkUpdateParams(ids, { lang_code: langCode, system_lang_code: sysLangCode }))}
                  disabled={loading} className="px-3 py-1 text-white rounded-md text-[12px] font-medium" style={{ background: A.blue }}>Apply</button>
        </div>
      )}
      {activePanel === 'proxy' && (
        <div className="flex items-center gap-2 pt-1">
          <span className={cn('text-xs', t.text3)}>Proxy group:</span>
          <select value={proxyGroupId} onChange={e => setProxyGroupId(e.target.value ? Number(e.target.value) : '')} className={inputCls}>
            <option value="">-- Select --</option>
            {proxyGroups.map(g => <option key={g.id} value={g.id}>{g.name} ({g.proxies_count})</option>)}
          </select>
          <button onClick={() => { if (!proxyGroupId) return; run('Proxy assigned', () => telegramOutreachApi.bulkAssignProxy(ids, proxyGroupId as number)); }}
                  disabled={loading || !proxyGroupId} className="px-3 py-1 text-white rounded-md text-[12px] font-medium" style={{ background: A.blue }}>Apply</button>
        </div>
      )}
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
                      if (e.target.value) run(`${p.label} updated`, () => telegramOutreachApi.bulkUpdatePrivacy(ids, { [p.key]: e.target.value }));
                    }}>
              <option value="">{p.label}</option>
              <option value="everyone">Everyone</option>
              <option value="contacts">Contacts</option>
              <option value="nobody">Nobody</option>
            </select>
          ))}
        </div>
      )}
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
    two_fa_password: '', daily_message_limit: '10',
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
      data.daily_message_limit = Number(data.daily_message_limit) || 10;
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
    device_model: account.device_model || '',
    system_version: account.system_version || '',
    app_version: account.app_version || '',
    lang_code: account.lang_code || '',
    system_lang_code: account.system_lang_code || '',
  });
  const [saving, setSaving] = useState(false);

  // Telethon state
  const [checking, setChecking] = useState(false);
  const [checkResult, setCheckResult] = useState<Record<string, any> | null>(null);
  const [authStep, setAuthStep] = useState<'none' | 'code_sent' | '2fa_required'>('none');
  const [authCode, setAuthCode] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authLoading, setAuthLoading] = useState(false);
  const sessionFileRef = useRef<HTMLInputElement>(null);

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const handleSave = async () => {
    setSaving(true);
    try {
      const data: Record<string, any> = { ...form };
      data.daily_message_limit = Number(data.daily_message_limit) || 10;
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

  const handleDelete = async () => {
    if (!confirm('Delete this account?')) return;
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
                <input value={form.username} onChange={e => set('username', e.target.value)}
                       className={panelInputCls}
                       style={{ background: A.surface, borderColor: A.border, color: A.text1 }} />
              </div>
              <div>
                <label className={panelLabelCls} style={{ color: A.text3 }}>Status</label>
                <select value={form.status} onChange={e => set('status', e.target.value)}
                        className={panelInputCls}
                        style={{ background: A.surface, borderColor: A.border, color: A.text1 }}>
                  <option value="active">Active</option>
                  <option value="paused">Paused</option>
                  <option value="spamblocked">Spamblocked</option>
                  <option value="dead">Dead</option>
                  <option value="frozen">Frozen</option>
                </select>
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
            <div className="rounded-lg p-3 grid grid-cols-3 gap-3 text-center"
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
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors hover:bg-[#F3F3F1]"
                        style={{ border: `1px solid ${A.border}`, color: A.text1 }}>
                  {checking ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                  Check Status
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
                            toast('Converted to TDATA. Download available.', 'success');
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
                            toast('Converted TDATA → Session', 'success');
                          } catch (e: any) {
                            toast(e?.response?.data?.detail || 'Conversion failed', 'error');
                          }
                        }}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors hover:bg-[#F3F3F1]"
                        style={{ border: `1px solid ${A.border}`, color: A.text1 }}>
                  TDATA → Session
                </button>
                <a href={telegramOutreachApi.downloadTdata(account.id)}
                   target="_blank" rel="noreferrer"
                   className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors hover:bg-[#F3F3F1]"
                   style={{ border: `1px solid ${A.border}`, color: A.text1 }}>
                  Download TDATA
                </a>
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
// Info Tab
// ══════════════════════════════════════════════════════════════════════

function InfoTab({ t }: { t: any }) {
  const { isDark } = useTheme();
  const sectionCls = cn('rounded-lg border p-5 space-y-3', t.cardBorder, t.cardBg);
  const h2Cls = cn('text-[15px] font-semibold', t.text1);
  const h3Cls = cn('text-[13px] font-semibold mt-3', t.text1);
  const pCls = cn('text-[13px] leading-relaxed', t.text2);
  const liCls = cn('text-[13px]', t.text2);
  const codeCls = cn('font-mono text-[12px] px-1.5 py-0.5 rounded', isDark ? 'bg-gray-800 text-blue-400' : 'bg-gray-100 text-blue-700');

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      {/* ── Accounts ── */}
      <div className={sectionCls}>
        <h2 className={h2Cls}>Accounts</h2>
        <p className={pCls}>Управление Telegram-аккаунтами для рассылки. Каждый аккаунт = отдельная Telethon-сессия.</p>

        <h3 className={h3Cls}>Кнопки</h3>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}><b>Add</b> — добавить аккаунт вручную (phone + session string)</li>
          <li className={liCls}><b>Import</b> — массовый импорт из TeleRaptor JSON (session + proxy + device)</li>
          <li className={liCls}><b>Export CSV</b> — выгрузка всех аккаунтов в CSV</li>
          <li className={liCls}><b>Select All</b> — выделить все для bulk-операций</li>
          <li className={liCls}><b>Фильтры</b> (All / Active / Spam / Dead) — быстрая фильтрация по статусу</li>
        </ul>

        <h3 className={h3Cls}>Bulk Actions (при выделении аккаунтов)</h3>
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

        <h3 className={h3Cls}>Статусы аккаунтов</h3>
        <ul className="space-y-1 list-disc list-inside">
          <li className={liCls}><span className={codeCls}>active</span> — рабочий, участвует в рассылке</li>
          <li className={liCls}><span className={codeCls}>paused</span> — на паузе, не отправляет</li>
          <li className={liCls}><span className={codeCls}>spamblocked</span> — получил спамблок от Telegram (temporary/permanent)</li>
          <li className={liCls}><span className={codeCls}>dead</span> — аккаунт мертв (забанен, удален)</li>
          <li className={liCls}><span className={codeCls}>frozen</span> — заморожен (нужна верификация)</li>
        </ul>

        <h3 className={h3Cls}>Таблица аккаунтов</h3>
        <p className={pCls}>Аватар, телефон (клик = копировать), гео-флаг, username, статус, возраст сессии, отправлено сегодня/лимит, имя. Клик на строку = модалка редактирования.</p>
      </div>

      {/* ── Campaigns ── */}
      <div className={sectionCls}>
        <h2 className={h2Cls}>Campaigns</h2>
        <p className={pCls}>Создание и управление рассылочными кампаниями. Кампания = набор аккаунтов + последовательность сообщений + список получателей.</p>

        <h3 className={h3Cls}>Кнопки</h3>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}><b>New Campaign</b> — создать новую кампанию (имя → переход на страницу настройки)</li>
          <li className={liCls}><b>Refresh</b> — обновить список кампаний</li>
        </ul>

        <h3 className={h3Cls}>Карточка кампании</h3>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}><b>Play / Pause</b> — запуск или пауза рассылки</li>
          <li className={liCls}><b>Delete</b> — удалить кампанию</li>
          <li className={liCls}>Отображает: статус, кол-во аккаунтов, получателей, отправлено сегодня / всего</li>
        </ul>

        <h3 className={h3Cls}>Внутри кампании (Campaign Detail)</h3>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}><b>Settings</b> — лимит/день, часы отправки, таймзона, задержки между сообщениями, порог спамблоков</li>
          <li className={liCls}><b>Sequence</b> — цепочка follow-up сообщений с задержками. Каждый шаг может иметь A/B варианты (spintax)</li>
          <li className={liCls}><b>Recipients</b> — список получателей (@username). Импорт из CSV / textarea. Статусы: pending → in_sequence → replied / completed / failed</li>
          <li className={liCls}><b>Messages</b> — лог отправленных сообщений с результатами (sent / failed / spamblocked)</li>
          <li className={liCls}><b>Replies</b> — входящие ответы от получателей</li>
          <li className={liCls}><b>AutoReply</b> — AI автоответчик (Gemini) для автоматических ответов на входящие</li>
          <li className={liCls}><b>Preview</b> — предпросмотр рендеринга сообщения с подстановкой переменных</li>
        </ul>

        <h3 className={h3Cls}>Статусы кампании</h3>
        <ul className="space-y-1 list-disc list-inside">
          <li className={liCls}><span className={codeCls}>draft</span> — черновик, не отправляет</li>
          <li className={liCls}><span className={codeCls}>active</span> — рассылка идет (worker отправляет сообщения)</li>
          <li className={liCls}><span className={codeCls}>paused</span> — на паузе</li>
          <li className={liCls}><span className={codeCls}>completed</span> — все получатели обработаны</li>
        </ul>
      </div>

      {/* ── Proxies ── */}
      <div className={sectionCls}>
        <h2 className={h2Cls}>Proxies</h2>
        <p className={pCls}>Управление прокси-серверами для маскировки IP аккаунтов. Прокси группируются — аккаунты привязываются к группе.</p>

        <h3 className={h3Cls}>Кнопки</h3>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}><b>Create Group</b> — создать группу прокси (имя, страна, описание)</li>
          <li className={liCls}><b>Add Proxy</b> — добавить прокси в группу (host:port, протокол, логин/пароль)</li>
          <li className={liCls}><b>Bulk Add</b> — массовый импорт прокси (формат: host:port:user:pass, по одному на строку)</li>
          <li className={liCls}><b>Health Check</b> — проверка работоспособности всех прокси в группе. Мертвые удаляются автоматически</li>
          <li className={liCls}><b>Delete</b> — удалить прокси или группу</li>
        </ul>

        <h3 className={h3Cls}>Протоколы</h3>
        <ul className="space-y-1 list-disc list-inside">
          <li className={liCls}><span className={codeCls}>socks5</span> — основной, поддерживается Telethon нативно</li>
          <li className={liCls}><span className={codeCls}>http</span> — HTTP CONNECT proxy</li>
          <li className={liCls}><span className={codeCls}>mtproto</span> — MTProto proxy (Telegram-native)</li>
        </ul>
      </div>

      {/* ── Parser ── */}
      <div className={sectionCls}>
        <h2 className={h2Cls}>Parser</h2>
        <p className={pCls}>Парсинг аудитории из Telegram-чатов и групп для формирования базы получателей.</p>

        <h3 className={h3Cls}>Возможности</h3>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}><b>Parse Group</b> — парсинг участников из Telegram-группы/чата по ссылке</li>
          <li className={liCls}><b>Export</b> — экспорт спарсенной аудитории в CSV для импорта в кампании</li>
          <li className={liCls}><b>Dedup</b> — дедупликация по username (исключение уже контактированных)</li>
        </ul>
      </div>

      {/* ── CRM ── */}
      <div className={sectionCls}>
        <h2 className={h2Cls}>CRM</h2>
        <p className={pCls}>Единая база контактов из всех Telegram-кампаний. Контакт создается автоматически при первой отправке сообщения.</p>

        <h3 className={h3Cls}>Pipeline (воронка)</h3>
        <ul className="space-y-1 list-disc list-inside">
          <li className={liCls}><span className={codeCls}>cold</span> — новый контакт, еще не написали</li>
          <li className={liCls}><span className={codeCls}>contacted</span> — сообщение отправлено</li>
          <li className={liCls}><span className={codeCls}>replied</span> — получен ответ</li>
          <li className={liCls}><span className={codeCls}>qualified</span> — квалифицирован (подходит под ICP)</li>
          <li className={liCls}><span className={codeCls}>meeting_set</span> — встреча назначена</li>
          <li className={liCls}><span className={codeCls}>converted</span> — конвертирован в клиента</li>
          <li className={liCls}><span className={codeCls}>not_interested</span> — не заинтересован</li>
        </ul>

        <h3 className={h3Cls}>Функции</h3>
        <ul className="space-y-1.5 list-disc list-inside">
          <li className={liCls}><b>Фильтр по статусу</b> — клик на карточку статуса = фильтрация таблицы</li>
          <li className={liCls}><b>Bulk Status</b> — массовое изменение статуса выбранных контактов</li>
          <li className={liCls}><b>Карточка контакта</b> — клик по строке: username, имя, компания, статус, история сообщений и ответов</li>
          <li className={liCls}><b>Sent / Replies</b> — сколько сообщений отправлено и получено ответов</li>
          <li className={liCls}><b>Campaigns</b> — в каких кампаниях участвовал контакт</li>
        </ul>
      </div>

      {/* ── Worker ── */}
      <div className={sectionCls}>
        <h2 className={h2Cls}>Sending Worker</h2>
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
      <div className={sectionCls}>
        <h2 className={h2Cls}>Reply Detection</h2>
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

const TAG_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  interested:      { bg: '#ECFDF5', text: '#0D9488', border: '#99F6E4' },
  info_requested:  { bg: '#FFFBEB', text: '#D97706', border: '#FDE68A' },
  not_interested:  { bg: '#FFF1F2', text: '#E05D6F', border: '#FECDD3' },
};

function InboxTab({ toast }: { toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) {
  const [threads, setThreads] = useState<any[]>([]);
  const [selectedThread, setSelectedThread] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [messageText, setMessageText] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [filterCampaign, setFilterCampaign] = useState('');
  const [filterAccount, setFilterAccount] = useState('');
  const [filterTag, setFilterTag] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load campaigns & accounts on mount
  useEffect(() => {
    (async () => {
      try {
        const [cRes, aRes] = await Promise.all([
          telegramOutreachApi.listCampaigns(),
          telegramOutreachApi.listAccounts({ page_size: 500 }),
        ]);
        setCampaigns(cRes.items || []);
        setAccounts(aRes.items || []);
      } catch { /* ignore */ }
    })();
  }, []);

  // Load threads (on mount + filter change + auto-refresh every 10s)
  const loadThreads = useCallback(async () => {
    try {
      const params: any = {};
      if (filterCampaign) params.campaign_id = Number(filterCampaign);
      if (filterAccount) params.account_id = Number(filterAccount);
      if (filterTag) params.tag = filterTag;
      params.page_size = 100;
      const data = await telegramOutreachApi.listInboxThreads(params);
      setThreads(data.items || data || []);
    } catch {
      // silently fail on auto-refresh
    } finally {
      setLoading(false);
    }
  }, [filterCampaign, filterAccount, filterTag]);

  useEffect(() => {
    setLoading(true);
    loadThreads();
    const iv = setInterval(loadThreads, 10000);
    return () => clearInterval(iv);
  }, [loadThreads]);

  // Load messages when thread selected
  useEffect(() => {
    if (!selectedThread) { setMessages([]); return; }
    let cancelled = false;
    (async () => {
      try {
        const data = await telegramOutreachApi.getThreadMessages(selectedThread.recipient_id, 50);
        if (!cancelled) setMessages(data.messages || data || []);
      } catch {
        if (!cancelled) setMessages([]);
      }
    })();
    return () => { cancelled = true; };
  }, [selectedThread]);

  // Auto-scroll to bottom when messages load
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Send handler
  const handleSend = async () => {
    if (!selectedThread || !messageText.trim() || sending) return;
    setSending(true);
    try {
      await telegramOutreachApi.sendInboxReply(selectedThread.recipient_id, messageText.trim());
      setMessageText('');
      const data = await telegramOutreachApi.getThreadMessages(selectedThread.recipient_id, 50);
      setMessages(data.messages || data || []);
      inputRef.current?.focus();
    } catch (e: any) {
      toast(e?.response?.data?.detail || 'Failed to send message', 'error');
    } finally {
      setSending(false);
    }
  };

  // Tag handler
  const handleTag = async (tag: string) => {
    if (!selectedThread) return;
    try {
      await telegramOutreachApi.tagInboxThread(selectedThread.recipient_id, tag);
      setSelectedThread((prev: any) => prev ? { ...prev, tag } : prev);
      setThreads(prev => prev.map(t =>
        t.recipient_id === selectedThread.recipient_id ? { ...t, tag } : t
      ));
      toast(`Tagged as ${tag.replace('_', ' ')}`, 'success');
    } catch (e: any) {
      toast(e?.response?.data?.detail || 'Failed to tag thread', 'error');
    }
  };

  const selectCls = `h-8 rounded-lg border text-xs px-2 outline-none appearance-none cursor-pointer`;

  return (
    <div className="flex rounded-xl overflow-hidden" style={{ background: A.surface, border: `1px solid ${A.border}`, height: 'calc(100vh - 220px)', minHeight: 500 }}>
      {/* ── Left panel: Thread list ── */}
      <div className="flex flex-col" style={{ width: 320, borderRight: `1px solid ${A.border}` }}>
        {/* Filters */}
        <div className="p-3 flex flex-col gap-2" style={{ borderBottom: `1px solid ${A.border}` }}>
          <div className="flex gap-2">
            <select
              value={filterCampaign}
              onChange={e => setFilterCampaign(e.target.value)}
              className={selectCls}
              style={{ flex: 1, borderColor: A.border, color: filterCampaign ? A.text1 : A.text3, background: A.surface }}
            >
              <option value="">All Campaigns</option>
              {campaigns.map((c: any) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <select
              value={filterAccount}
              onChange={e => setFilterAccount(e.target.value)}
              className={selectCls}
              style={{ flex: 1, borderColor: A.border, color: filterAccount ? A.text1 : A.text3, background: A.surface }}
            >
              <option value="">All Accounts</option>
              {accounts.map((a: any) => (
                <option key={a.id} value={a.id}>{a.phone}{a.username ? ` @${a.username}` : ''}</option>
              ))}
            </select>
          </div>
          <select
            value={filterTag}
            onChange={e => setFilterTag(e.target.value)}
            className={selectCls}
            style={{ borderColor: A.border, color: filterTag ? A.text1 : A.text3, background: A.surface }}
          >
            <option value="">All Tags</option>
            <option value="interested">Interested</option>
            <option value="info_requested">Info Requested</option>
            <option value="not_interested">Not Interested</option>
          </select>
        </div>

        {/* Thread list */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <Loader2 className="w-5 h-5 animate-spin" style={{ color: A.text3 }} />
            </div>
          ) : threads.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 gap-1">
              <MessageCircle className="w-6 h-6" style={{ color: A.text3 }} />
              <span className="text-xs" style={{ color: A.text3 }}>No conversations</span>
            </div>
          ) : (
            threads.map((thread: any) => {
              const isSelected = selectedThread?.recipient_id === thread.recipient_id;
              const tagInfo = thread.tag ? TAG_COLORS[thread.tag] : null;
              return (
                <div
                  key={thread.recipient_id}
                  onClick={() => setSelectedThread(thread)}
                  className="px-3 py-2.5 cursor-pointer transition-colors"
                  style={{
                    background: isSelected ? A.blueBg : 'transparent',
                    borderBottom: `1px solid ${A.border}`,
                  }}
                  onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = '#F9FAFB'; }}
                  onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent'; }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold truncate" style={{ color: A.text1 }}>
                      {thread.username || thread.first_name || `ID ${thread.recipient_id}`}
                    </span>
                    <span className="text-[10px] flex-shrink-0" style={{ color: A.text3 }}>
                      {formatRelativeTime(thread.last_message_at)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <p className="text-xs truncate flex-1" style={{ color: A.text2, lineHeight: '1.4' }}>
                      {thread.last_message_preview || 'No messages'}
                    </p>
                    {tagInfo && (
                      <span
                        className="text-[10px] font-medium px-1.5 py-0.5 rounded-full flex-shrink-0"
                        style={{ background: tagInfo.bg, color: tagInfo.text, border: `1px solid ${tagInfo.border}` }}
                      >
                        {thread.tag.replace('_', ' ')}
                      </span>
                    )}
                  </div>
                  {thread.campaign_name && (
                    <span className="text-[10px] mt-0.5 block" style={{ color: A.text3 }}>
                      {thread.campaign_name}
                    </span>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* ── Right panel: Chat view ── */}
      <div className="flex-1 flex flex-col" style={{ minWidth: 0 }}>
        {!selectedThread ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <MessageCircle className="w-10 h-10 mx-auto mb-2" style={{ color: A.text3 }} />
              <p className="text-sm" style={{ color: A.text3 }}>Select a conversation</p>
            </div>
          </div>
        ) : (
          <>
            {/* Chat header */}
            <div className="px-4 py-3 flex items-center gap-3" style={{ borderBottom: `1px solid ${A.border}` }}>
              <div className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-semibold" style={{ background: A.blueBg, color: A.blue }}>
                {(selectedThread.username || selectedThread.first_name || '?')[0].toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold truncate" style={{ color: A.text1 }}>
                  {selectedThread.username || selectedThread.first_name || `ID ${selectedThread.recipient_id}`}
                </p>
                <p className="text-[11px] truncate" style={{ color: A.text3 }}>
                  {[selectedThread.campaign_name, selectedThread.account_phone].filter(Boolean).join(' \u00B7 ')}
                </p>
              </div>
              {selectedThread.tag && TAG_COLORS[selectedThread.tag] && (
                <span
                  className="text-[11px] font-medium px-2 py-0.5 rounded-full"
                  style={{
                    background: TAG_COLORS[selectedThread.tag].bg,
                    color: TAG_COLORS[selectedThread.tag].text,
                    border: `1px solid ${TAG_COLORS[selectedThread.tag].border}`,
                  }}
                >
                  {selectedThread.tag.replace('_', ' ')}
                </span>
              )}
            </div>

            {/* Messages area */}
            <div className="flex-1 overflow-y-auto px-4 py-3" style={{ background: '#F9FAFB' }}>
              {messages.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <span className="text-xs" style={{ color: A.text3 }}>No messages yet</span>
                </div>
              ) : (
                <div className="flex flex-col gap-2">
                  {messages.map((msg: any, idx: number) => {
                    const isOutbound = msg.direction === 'outbound' || msg.direction === 'sent' || msg.is_outbound;
                    return (
                      <div key={msg.id || idx} className={`flex ${isOutbound ? 'justify-end' : 'justify-start'}`}>
                        <div
                          className="max-w-[75%] px-3 py-2 text-sm"
                          style={{
                            background: isOutbound ? A.blueBg : '#F3F4F6',
                            color: A.text1,
                            borderRadius: isOutbound
                              ? '16px 16px 4px 16px'
                              : '16px 16px 16px 4px',
                            wordBreak: 'break-word',
                          }}
                        >
                          <p style={{ whiteSpace: 'pre-wrap', lineHeight: '1.45' }}>{msg.text || msg.rendered_text || msg.message_text || ''}</p>
                          <p className="text-[10px] mt-1 text-right" style={{ color: A.text3 }}>
                            {msg.sent_at || msg.received_at || msg.created_at
                              ? new Date(msg.sent_at || msg.received_at || msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                              : ''}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* Tag buttons */}
            <div className="px-4 py-2 flex gap-2" style={{ borderTop: `1px solid ${A.border}` }}>
              {([
                { key: 'interested', label: 'Interested', bg: '#ECFDF5', text: '#0D9488', border: '#99F6E4' },
                { key: 'info_requested', label: 'Info Requested', bg: '#FFFBEB', text: '#D97706', border: '#FDE68A' },
                { key: 'not_interested', label: 'Not Interested', bg: '#FFF1F2', text: '#E05D6F', border: '#FECDD3' },
              ] as const).map(t => {
                const isActive = selectedThread.tag === t.key;
                return (
                  <button
                    key={t.key}
                    onClick={() => handleTag(t.key)}
                    className="text-[11px] font-medium px-3 py-1 rounded-full transition-all"
                    style={{
                      background: isActive ? t.bg : 'transparent',
                      color: isActive ? t.text : A.text3,
                      border: `1px solid ${isActive ? t.border : A.border}`,
                    }}
                    onMouseEnter={e => { if (!isActive) { e.currentTarget.style.background = t.bg; e.currentTarget.style.color = t.text; e.currentTarget.style.borderColor = t.border; } }}
                    onMouseLeave={e => { if (!isActive) { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = A.text3; e.currentTarget.style.borderColor = A.border; } }}
                  >
                    {t.label}
                  </button>
                );
              })}
            </div>

            {/* Input row */}
            <div className="px-4 py-3 flex gap-2 items-center" style={{ borderTop: `1px solid ${A.border}` }}>
              <input
                ref={inputRef}
                type="text"
                value={messageText}
                onChange={e => setMessageText(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                placeholder="Type a message..."
                className="flex-1 h-9 px-3 rounded-lg border text-sm outline-none"
                style={{ borderColor: A.border, color: A.text1, background: '#F9FAFB' }}
                disabled={sending}
              />
              <button
                onClick={handleSend}
                disabled={sending || !messageText.trim()}
                className="h-9 w-9 rounded-lg flex items-center justify-center transition-colors"
                style={{
                  background: messageText.trim() ? A.blue : '#E5E7EB',
                  cursor: messageText.trim() ? 'pointer' : 'default',
                }}
              >
                {sending
                  ? <Loader2 className="w-4 h-4 text-white animate-spin" />
                  : <Send className="w-4 h-4 text-white" />}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

const CRM_STATUS_COLORS: Record<string, string> = {
  cold: 'bg-gray-100 text-gray-700',
  contacted: 'bg-blue-100 text-blue-700',
  replied: 'bg-green-100 text-green-700',
  qualified: 'bg-purple-100 text-purple-700',
  meeting_set: 'bg-indigo-100 text-indigo-700',
  converted: 'bg-emerald-100 text-emerald-700',
  not_interested: 'bg-red-100 text-red-700',
};

const CRM_PIPELINE = ['cold', 'contacted', 'replied', 'qualified', 'meeting_set', 'converted', 'not_interested'];

function CrmTab({ t: _t, toast }: { t: any; toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) { void _t;
  const [contacts, setContacts] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [selectedContact, setSelectedContact] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const loadContacts = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { page, page_size: 50 };
      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      const data = await telegramOutreachApi.listCrmContacts(params);
      setContacts(data.items);
      setTotal(data.total);
    } catch { toast('Failed to load contacts', 'error'); }
    finally { setLoading(false); }
  }, [page, search, statusFilter, toast]);

  const loadStats = useCallback(async () => {
    try { setStats(await telegramOutreachApi.getCrmStats()); } catch { /* ok */ }
  }, []);

  useEffect(() => { loadContacts(); }, [loadContacts]);
  useEffect(() => { loadStats(); }, [loadStats]);

  const openContact = async (c: any) => {
    setSelectedContact(c);
    try {
      const h = await telegramOutreachApi.getCrmContactHistory(c.id);
      setHistory(h.history);
    } catch { setHistory([]); }
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
      <div className="grid grid-cols-7 gap-2">
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
        <span className="text-xs" style={{ color: A.text3 }}>{total} contacts</span>
        {selectedIds.size > 0 && (
          <div className="flex items-center gap-1 ml-auto">
            <span className="text-xs" style={{ color: A.text3 }}>{selectedIds.size} selected</span>
            <select onChange={e => {
                      if (!e.target.value) return;
                      telegramOutreachApi.bulkUpdateCrmStatus(Array.from(selectedIds), e.target.value)
                        .then(() => { toast('Updated', 'success'); loadContacts(); loadStats(); setSelectedIds(new Set()); })
                        .catch(() => toast('Failed', 'error'));
                      e.target.value = '';
                    }}
                    className="px-2 py-1 rounded border text-xs"
                    style={{ borderColor: A.border, background: A.surface, color: A.text1 }}>
              <option value="">Set status...</option>
              {CRM_PIPELINE.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
            </select>
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
                  <td className="px-3 py-2 font-mono text-xs" style={{ color: A.text1 }}>@{c.username}</td>
                  <td className="px-3 py-2 text-xs" style={{ color: A.text1 }}>{[c.first_name, c.last_name].filter(Boolean).join(' ') || '--'}</td>
                  <td className="px-3 py-2 text-xs" style={{ color: A.text3 }}>{c.company_name || '--'}</td>
                  <td className="px-3 py-2">
                    <select value={c.status} onClick={e => e.stopPropagation()}
                            onChange={e => updateStatus(c.id, e.target.value)}
                            className={cn('px-1.5 py-0.5 rounded-full text-[10px] font-medium border-0 cursor-pointer',
                              CRM_STATUS_COLORS[c.status] || 'bg-gray-100')}>
                      {CRM_PIPELINE.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                    </select>
                  </td>
                  <td className="px-2 py-2 text-xs font-mono" style={{ color: A.text1 }}>{c.total_messages_sent}</td>
                  <td className="px-2 py-2 text-xs font-mono" style={{ color: c.total_replies_received > 0 ? '#16a34a' : A.text3 }}>
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
              <button onClick={() => setSelectedContact(null)} className="p-1 hover:bg-[#F5F5F0] rounded">
                <X className="w-5 h-5" style={{ color: A.text3 }} />
              </button>
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
    </div>
  );
}
