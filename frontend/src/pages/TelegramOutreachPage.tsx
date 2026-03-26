import { useState, useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users, Send, Shield, Plus, Search, RefreshCw, Trash2,
  Globe, Loader2, Play, Pause,
  X, Upload, FileJson, Edit3, ChevronDown, BookOpen,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { useToast } from '../components/Toast';
import { telegramOutreachApi } from '../api/telegramOutreach';
import type {
  TgAccount, TgAccountTag, TgProxyGroup, TgProxy, TgCampaign,
} from '../api/telegramOutreach';

type Tab = 'accounts' | 'campaigns' | 'proxies' | 'parser' | 'crm' | 'info';

// ── Helpers ───────────────────────────────────────────────────────────

/** Convert ISO 3166-1 alpha-2 country code to emoji flag. "RU" → 🇷🇺 */
function countryFlag(code: string): string {
  const upper = code.toUpperCase();
  if (upper.length !== 2) return code;
  return String.fromCodePoint(
    ...Array.from(upper).map(c => 0x1F1E6 + c.charCodeAt(0) - 65)
  );
}

// ── Status badges ─────────────────────────────────────────────────────

const ACCOUNT_STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  paused: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  spamblocked: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  dead: 'bg-gray-100 text-gray-700 dark:bg-gray-700/30 dark:text-gray-400',
  frozen: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
};

const CAMPAIGN_STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700 dark:bg-gray-700/30 dark:text-gray-400',
  active: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  paused: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  completed: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
};

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
    { key: 'info', label: 'Info', icon: BookOpen },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className={cn('border-b px-6 py-4', t.cardBorder)}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className={cn('text-xl font-semibold', t.text1)}>Telegram Outreach</h1>
            <p className={cn('text-sm mt-1', t.text3)}>
              Manage accounts, campaigns, and proxies for Telegram outreach
            </p>
          </div>

          {/* Worker status */}
          <span className={cn('flex items-center gap-1.5 text-xs font-medium',
            workerRunning ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400')}>
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
              className={cn(
                'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                tab === key
                  ? 'bg-indigo-50 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400'
                  : cn('hover:bg-gray-100 dark:hover:bg-gray-800', t.text3),
              )}
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
    try {
      setTags(await telegramOutreachApi.listTags());
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadAccounts(); }, [loadAccounts]);
  useEffect(() => { loadTags(); }, [loadTags]);

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === accounts.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(accounts.map(a => a.id)));
    }
  };

  // Delete is handled via BulkActionsBar and EditAccountModal

  const totalPages = Math.ceil(total / 50);

  // Stats
  const activeCount = accounts.filter(a => a.status === 'active').length;
  const spamCount = accounts.filter(a => a.status === 'spamblocked').length;
  const sentToday = accounts.reduce((s, a) => s + a.messages_sent_today, 0);

  return (
    <div className="space-y-4">
      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'All Accounts', value: total, color: 'text-indigo-600 dark:text-indigo-400' },
          { label: 'Active', value: activeCount, color: 'text-green-600 dark:text-green-400' },
          { label: 'Spamblocked', value: spamCount, color: 'text-red-500 dark:text-red-400' },
          { label: 'Sent Today', value: sentToday, color: 'text-blue-600 dark:text-blue-400' },
        ].map(s => (
          <div key={s.label} className={cn('rounded-lg border px-4 py-3', t.cardBorder)}>
            <div className={cn('text-2xl font-bold', s.color)}>{s.value}</div>
            <div className={cn('text-xs', t.text3)}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={() => setShowAddModal(true)}
                className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">
          <Plus className="w-4 h-4" /> Add
        </button>
        <button onClick={() => setShowImportModal(true)}
                className={cn('flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder, t.text1)}>
          <FileJson className="w-4 h-4" /> Import
        </button>
        <a href={telegramOutreachApi.exportAccountsURL()}
           className={cn('flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm font-medium hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder, t.text1)}>
          Export CSV
        </a>
        <button onClick={loadAccounts}
                className={cn('p-2 rounded-lg border hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder)}>
          <RefreshCw className={cn('w-4 h-4', t.text3)} />
        </button>
        <button onClick={toggleAll}
                className={cn('flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder, t.text3)}>
          {selectedIds.size === accounts.length && accounts.length > 0 ? 'Deselect All' : 'Select All'}
        </button>

        {/* Quick filters */}
        <div className="flex items-center gap-1 ml-2">
          {[
            { key: '', label: 'All', count: total },
            { key: 'active', label: 'Active', count: activeCount },
            { key: 'spamblocked', label: 'Spam', count: spamCount },
            { key: 'dead', label: 'Dead', count: accounts.filter(a => a.status === 'dead').length },
          ].map(f => (
            <button key={f.key}
                    onClick={() => { setStatusFilter(f.key); setPage(1); }}
                    className={cn('px-2.5 py-1 rounded-lg text-xs font-medium transition-colors',
                      statusFilter === f.key
                        ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400'
                        : cn(t.text3, 'hover:bg-gray-100 dark:hover:bg-gray-800'))}>
              {f.label} <span className="opacity-60">{f.count}</span>
            </button>
          ))}
        </div>

        <div className="ml-auto">
          <div className="relative">
            <Search className={cn('absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5', t.text3)} />
            <input type="text" placeholder="Search..." value={search}
                   onChange={e => { setSearch(e.target.value); setPage(1); }}
                   className={cn('pl-8 pr-3 py-1.5 rounded-lg border text-xs w-48', t.cardBorder, t.cardBg, t.text1)} />
          </div>
        </div>
      </div>

      {/* Bulk Actions Bar — sticky bottom */}
      {selectedIds.size > 0 && (
        <div className="fixed bottom-0 left-0 right-0 z-40 px-6 py-2 shadow-lg" style={{ background: 'inherit' }}>
          <BulkActionsBar
            selectedIds={selectedIds}
            t={t}
            toast={toast}
            onDone={() => { setSelectedIds(new Set()); loadAccounts(); }}
          />
        </div>
      )}

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-16">
          <Loader2 className={cn('w-8 h-8 animate-spin', t.text3)} />
        </div>
      ) : accounts.length === 0 ? (
        <div className={cn('text-center py-16 rounded-lg border', t.cardBorder)}>
          <Users className={cn('w-12 h-12 mx-auto mb-3', t.text3)} />
          <p className={cn('text-sm', t.text3)}>No accounts yet</p>
        </div>
      ) : (
        <div className={cn('rounded-lg border overflow-hidden', t.cardBorder)}>
          <table className="w-full text-sm">
            <thead className={cn('border-b', t.cardBorder, isDark ? 'bg-gray-800/50' : 'bg-gray-50')}>
              <tr>
                <th className="w-10 px-3 py-2.5">
                  <input type="checkbox" checked={selectedIds.size === accounts.length && accounts.length > 0}
                         onChange={toggleAll} className="rounded" />
                </th>
                <th className={cn('w-8 text-center px-1 py-2.5 text-xs font-medium', t.text3)}>#</th>
                <th className="w-10 px-1 py-2.5" />
                <th className={cn('text-left px-3 py-2.5 text-xs font-medium', t.text3)}>Phone</th>
                <th className={cn('text-center px-1 py-2.5 text-xs font-medium', t.text3)}>Geo</th>
                <th className={cn('text-left px-3 py-2.5 text-xs font-medium', t.text3)}>Username</th>
                <th className={cn('text-left px-3 py-2.5 text-xs font-medium', t.text3)}>Status</th>
                <th className={cn('text-left px-2 py-2.5 text-xs font-medium', t.text3)}>Age</th>
                <th className={cn('text-left px-2 py-2.5 text-xs font-medium', t.text3)}>Sent</th>
                <th className={cn('text-left px-3 py-2.5 text-xs font-medium', t.text3)}>Name</th>
                <th className="w-8 px-1 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {accounts.map((acc, idx) => {
                const initials = (acc.first_name?.[0] || '') + (acc.last_name?.[0] || '') || acc.phone.slice(-2);
                const hue = (parseInt(acc.phone.slice(-4), 10) || 0) % 360;
                const isSelected = selectedIds.has(acc.id);
                const atLimit = acc.messages_sent_today >= acc.daily_message_limit;
                return (
                  <tr key={acc.id}
                      onClick={() => setEditingAccount(acc)}
                      className={cn('border-b cursor-pointer transition-colors',
                        t.cardBorder,
                        isSelected ? 'bg-indigo-50/60 dark:bg-indigo-900/15' : 'hover:bg-gray-50 dark:hover:bg-gray-800/50')}>
                    <td className="px-3 py-2" onClick={e => e.stopPropagation()}>
                      <input type="checkbox" checked={isSelected}
                             onChange={() => toggleSelect(acc.id)} className="rounded" />
                    </td>
                    <td className={cn('text-center px-1 py-2 text-xs', t.text3)}>{(page - 1) * 50 + idx + 1}</td>
                    <td className="px-1 py-2">
                      <div className="w-9 h-9 rounded-full flex-shrink-0 overflow-hidden"
                           style={{ backgroundColor: `hsl(${hue}, 55%, 50%)` }}>
                        <img src={`/api/telegram-outreach/accounts/${acc.id}/avatar`}
                             alt=""
                             className="w-full h-full object-cover"
                             onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />
                        <span className="w-full h-full flex items-center justify-center text-white text-xs font-bold">
                          {initials.toUpperCase()}
                        </span>
                      </div>
                    </td>
                    <td className={cn('px-3 py-2 font-mono text-xs cursor-pointer hover:text-indigo-600', t.text1)}
                        onClick={e => { e.stopPropagation(); navigator.clipboard.writeText(acc.phone); }}
                        title="Click to copy">{acc.phone}</td>
                    <td className="px-1 py-2 text-center" title={acc.country_code || ''}>
                      {acc.country_code ? countryFlag(acc.country_code) : <span className={cn('text-xs', t.text3)}>--</span>}
                    </td>
                    <td className={cn('px-3 py-2 text-xs', t.text1)}>
                      {acc.username ? <span>@{acc.username}</span> : <span className={t.text3}>--</span>}
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge status={acc.status} colorMap={ACCOUNT_STATUS_COLORS} />
                      {acc.spamblock_type !== 'none' && (
                        <span className="ml-1 px-1 py-0.5 rounded text-[10px] bg-red-50 text-red-600 dark:bg-red-900/20 dark:text-red-400">
                          {acc.spamblock_type}
                        </span>
                      )}
                    </td>
                    <td className={cn('px-2 py-2 text-[10px]', t.text3)}>
                      {acc.session_created_at ? (() => {
                        const days = Math.floor((Date.now() - new Date(acc.session_created_at).getTime()) / 86400000);
                        return days >= 30 ? `${Math.floor(days/30)}m ${days%30}d` : `${days}d`;
                      })() : '--'}
                    </td>
                    <td className={cn('px-2 py-2 font-mono text-xs', t.text1)}>
                      <span className={atLimit ? 'text-red-500 font-semibold' : ''}>{acc.messages_sent_today}</span>
                      <span className={t.text3}>/{acc.daily_message_limit}</span>
                    </td>
                    <td className={cn('px-3 py-2 text-xs', t.text1)}>
                      {[acc.first_name, acc.last_name].filter(Boolean).join(' ') || <span className={t.text3}>--</span>}
                    </td>
                    {/* Tags removed for cleaner layout — visible in Edit modal */}
                    <td className="px-1 py-2" onClick={e => e.stopPropagation()}>
                      <button onClick={() => setEditingAccount(acc)}
                              className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
                        <Edit3 className="w-3.5 h-3.5 text-gray-400" />
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
        <div className="flex items-center justify-between">
          <span className={cn('text-sm', t.text3)}>{total} accounts</span>
          <div className="flex items-center gap-2">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
                    className={cn('px-3 py-1.5 rounded border text-sm', t.cardBorder, page <= 1 && 'opacity-50')}>
              Prev
            </button>
            <span className={cn('text-sm', t.text1)}>Page {page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
                    className={cn('px-3 py-1.5 rounded border text-sm', t.cardBorder, page >= totalPages && 'opacity-50')}>
              Next
            </button>
          </div>
        </div>
      )}

      {/* Add Account Modal */}
      {showAddModal && (
        <AddAccountModal t={t} toast={toast} isDark={isDark}
                         onClose={() => setShowAddModal(false)}
                         onSaved={() => { setShowAddModal(false); loadAccounts(); }} />
      )}

      {/* Edit Account Modal */}
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

function CampaignsTab({ t, toast }: { t: any; toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) {
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

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className={cn('text-sm', t.text3)}>{campaigns.length} campaigns</span>
        <button onClick={handleCreate}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition-colors">
          <Plus className="w-4 h-4" />
          New Campaign
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className={cn('w-6 h-6 animate-spin', t.text3)} />
        </div>
      ) : campaigns.length === 0 ? (
        <div className={cn('text-center py-12 rounded-lg border', t.cardBorder)}>
          <Send className={cn('w-10 h-10 mx-auto mb-3', t.text3)} />
          <p className={cn('text-sm', t.text3)}>No campaigns yet. Create your first campaign to start outreach.</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {campaigns.map(c => (
            <div key={c.id} onClick={() => navigate(`/telegram-outreach/campaign/${c.id}`)}
                 className={cn('rounded-lg border p-4 flex items-center gap-4 cursor-pointer', t.cardBorder, 'hover:shadow-sm transition-shadow')}>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className={cn('font-medium truncate', t.text1)}>{c.name}</h3>
                  <StatusBadge status={c.status} colorMap={CAMPAIGN_STATUS_COLORS} />
                </div>
                <div className={cn('flex items-center gap-4 mt-1 text-xs', t.text3)}>
                  <span>{c.total_recipients} recipients</span>
                  <span>{c.total_messages_sent} sent</span>
                  <span>{c.accounts_count} accounts</span>
                  <span>{c.delay_between_sends_min}-{c.delay_between_sends_max}s delay</span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button onClick={e => { e.stopPropagation(); handleToggle(c); }}
                        className={cn('p-2 rounded-lg border hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder)}
                        title={c.status === 'active' ? 'Pause' : 'Start'}>
                  {c.status === 'active' ? <Pause className="w-4 h-4 text-yellow-500" /> : <Play className="w-4 h-4 text-green-500" />}
                </button>
                <button onClick={e => { e.stopPropagation(); handleDelete(c.id); }}
                        className={cn('p-2 rounded-lg border hover:bg-red-50 dark:hover:bg-red-900/20', t.cardBorder)}
                        title="Delete">
                  <Trash2 className="w-4 h-4 text-red-400" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Proxies Tab
// ══════════════════════════════════════════════════════════════════════

function ProxiesTab({ t, toast }: { t: any; toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) {
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
  const { isDark } = useTheme();

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
      <div className={cn('w-72 flex-shrink-0 rounded-lg border flex flex-col', t.cardBorder)}>
        <div className={cn('px-4 py-3 border-b flex items-center justify-between', t.cardBorder)}>
          <h3 className={cn('text-sm font-medium', t.text1)}>Proxy Groups</h3>
          <button onClick={() => setShowAddGroup(true)} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded" title="New group">
            <Plus className={cn('w-4 h-4', t.text3)} />
          </button>
        </div>

        {showAddGroup && (
          <div className={cn('px-4 py-3 border-b space-y-2', t.cardBorder)}>
            <input type="text" placeholder="Group name" value={newGroupName}
                   onChange={e => setNewGroupName(e.target.value)}
                   className={cn('w-full px-3 py-1.5 rounded border text-sm', t.cardBorder, t.cardBg, t.text1)} />
            <input type="text" placeholder="Country (optional)" value={newGroupCountry}
                   onChange={e => setNewGroupCountry(e.target.value)}
                   className={cn('w-full px-3 py-1.5 rounded border text-sm', t.cardBorder, t.cardBg, t.text1)} />
            <div className="flex gap-2">
              <button onClick={handleCreateGroup}
                      className="px-3 py-1 bg-indigo-600 text-white rounded text-xs font-medium hover:bg-indigo-700">
                Create
              </button>
              <button onClick={() => setShowAddGroup(false)}
                      className={cn('px-3 py-1 rounded border text-xs', t.cardBorder, t.text1)}>
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="flex-1 overflow-auto">
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className={cn('w-5 h-5 animate-spin', t.text3)} />
            </div>
          ) : groups.length === 0 ? (
            <p className={cn('text-center py-8 text-sm', t.text3)}>No groups yet</p>
          ) : groups.map(g => (
            <div key={g.id}
                 onClick={() => setSelectedGroup(g)}
                 className={cn(
                   'px-4 py-3 cursor-pointer border-b flex items-center justify-between',
                   t.cardBorder,
                   selectedGroup?.id === g.id
                     ? 'bg-indigo-50 dark:bg-indigo-900/20'
                     : 'hover:bg-gray-50 dark:hover:bg-gray-800/50',
                 )}>
              <div>
                <div className={cn('text-sm font-medium', t.text1)}>{g.name}</div>
                <div className={cn('text-xs', t.text3)}>
                  {g.country ? `${g.country} · ` : ''}{g.proxies_count} proxies
                </div>
              </div>
              <button onClick={e => { e.stopPropagation(); handleDeleteGroup(g.id); }}
                      className="p-1 hover:bg-red-50 dark:hover:bg-red-900/20 rounded opacity-0 group-hover:opacity-100">
                <Trash2 className="w-3.5 h-3.5 text-red-400" />
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
              <h3 className={cn('text-sm font-medium', t.text1)}>
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
                        className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50', t.cardBorder, t.text1)}>
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
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400 text-xs font-medium hover:bg-red-100 dark:hover:bg-red-900/30 disabled:opacity-50">
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
                className={cn('flex-1 px-3 py-2 rounded-lg border text-sm font-mono', t.cardBorder, t.cardBg, t.text1)}
              />
              <button onClick={handleAddProxies} disabled={!proxyText.trim()}
                      className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 self-end">
                Add
              </button>
            </div>

            {/* Proxy list */}
            <div className={cn('rounded-lg border overflow-hidden flex-1', t.cardBorder)}>
              <table className="w-full text-sm">
                <thead className={cn('border-b', t.cardBorder, isDark ? 'bg-gray-800/50' : 'bg-gray-50')}>
                  <tr>
                    <th className={cn('text-left px-3 py-2 font-medium', t.text3)}>Host</th>
                    <th className={cn('text-left px-3 py-2 font-medium', t.text3)}>Port</th>
                    <th className={cn('text-left px-3 py-2 font-medium', t.text3)}>User</th>
                    <th className={cn('text-left px-3 py-2 font-medium', t.text3)}>Protocol</th>
                    <th className={cn('text-left px-3 py-2 font-medium', t.text3)}>Status</th>
                    <th className="w-10" />
                  </tr>
                </thead>
                <tbody>
                  {proxies.length === 0 ? (
                    <tr><td colSpan={6} className={cn('text-center py-8', t.text3)}>No proxies in this group</td></tr>
                  ) : proxies.map(p => (
                    <tr key={p.id} className={cn('border-b', t.cardBorder)}>
                      <td className={cn('px-3 py-2 font-mono text-xs', t.text1)}>{p.host}</td>
                      <td className={cn('px-3 py-2 font-mono text-xs', t.text1)}>{p.port}</td>
                      <td className={cn('px-3 py-2 text-xs', t.text3)}>{p.username || '—'}</td>
                      <td className={cn('px-3 py-2 text-xs', t.text3)}>{p.protocol}</td>
                      <td className="px-3 py-2">
                        {checkResults[p.id] ? (
                          <span className={cn('px-1.5 py-0.5 rounded text-xs',
                            checkResults[p.id].alive
                              ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                              : 'bg-red-100 text-red-600 dark:bg-red-900/20 dark:text-red-400'
                          )}>
                            {checkResults[p.id].alive
                              ? `alive ${checkResults[p.id].latency_ms}ms`
                              : `dead`}
                          </span>
                        ) : (
                          <span className={cn('px-1.5 py-0.5 rounded text-xs', p.is_active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-red-100 text-red-600')}>
                            {p.is_active ? 'active' : 'inactive'}
                          </span>
                        )}
                        {checkResults[p.id] && !checkResults[p.id].alive && checkResults[p.id].error && (
                          <span className="ml-1 text-xs text-red-400" title={checkResults[p.id].error!}>
                            ({checkResults[p.id].error!.substring(0, 20)})
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <button onClick={() => handleDeleteProxy(p.id)} className="p-1 hover:bg-red-50 dark:hover:bg-red-900/20 rounded">
                          <Trash2 className="w-3.5 h-3.5 text-red-400" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <div className={cn('flex items-center justify-center h-full', t.text3)}>
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
  const { isDark } = useTheme();
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

  const btnCls = cn('flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50', t.cardBorder, t.text1);
  const inputCls = cn('px-2 py-1 rounded border text-xs', t.cardBorder, t.cardBg, t.text1);

  return (
    <div className={cn('rounded-xl border p-3 space-y-2', t.cardBorder, isDark ? 'bg-gray-800/40' : 'bg-indigo-50/50')}>
      {/* Main buttons row */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className={cn('text-xs font-bold mr-1', t.text1)}>{selectedIds.size} selected</span>
        <div className="w-px h-4 bg-gray-300 dark:bg-gray-600" />

        {/* Profile */}
        <button onClick={() => setActivePanel(activePanel === 'names' ? null : 'names')} className={btnCls}>
          <Users className="w-3 h-3" /> Randomize Names
        </button>
        <button onClick={() => setActivePanel(activePanel === 'bio' ? null : 'bio')} className={btnCls}>
          Set Bio
        </button>
        <button onClick={() => photoInputRef.current?.click()} disabled={loading} className={btnCls}>
          Set Photo
        </button>
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

        {/* Technical */}
        <button onClick={() => run('Device randomized', () => telegramOutreachApi.bulkRandomizeDevice(ids))}
                disabled={loading} className={btnCls}>
          <RefreshCw className="w-3 h-3" /> Randomize Device
        </button>
        <button onClick={() => setActivePanel(activePanel === 'limit' ? null : 'limit')} className={btnCls}>
          Set Limit
        </button>
        <button onClick={() => setActivePanel(activePanel === 'lang' ? null : 'lang')} className={btnCls}>
          Set Language
        </button>
        <button onClick={() => setActivePanel(activePanel === '2fa' ? null : '2fa')} className={btnCls}>
          Set 2FA
        </button>

        {/* Proxy */}
        <button onClick={() => setActivePanel(activePanel === 'proxy' ? null : 'proxy')} className={btnCls}>
          <Shield className="w-3 h-3" /> Assign Proxy
        </button>

        {/* Sync + Check */}
        {/* Sync to TG removed — auto-syncs on name/bio/photo changes */}
        <button onClick={() => setActivePanel(activePanel === 'privacy' ? null : 'privacy')} className={btnCls}>
          Privacy
        </button>
        <button onClick={() => run('Re-authorized', () => telegramOutreachApi.bulkReauthorize(ids))}
                disabled={loading} className={btnCls}>Re-Auth</button>
        <button onClick={() => run('Sessions revoked', () => telegramOutreachApi.bulkRevokeSessions(ids))}
                disabled={loading} className={btnCls}>Revoke Sessions</button>
        <button onClick={() => run('Cleaned', () => telegramOutreachApi.bulkClean(ids, { delete_dialogs: true, delete_contacts: true }))}
                disabled={loading} className={btnCls}>Clean</button>
        <button onClick={() => run('Alive check done', () => telegramOutreachApi.bulkCheckAlive(ids))}
                disabled={loading} className={btnCls} title="Quick check: connect + authorized. Safe to run often.">
          {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />}
          Alive?
        </button>
        <button onClick={() => run('Spamblock checked', () => telegramOutreachApi.bulkCheck(ids))}
                disabled={loading} className={cn(btnCls, 'text-amber-600 dark:text-amber-400')} title="Full spamblock check via @SpamBot. Don't run too often.">
          <Shield className="w-3 h-3" />
          Spam?
        </button>

        {/* Delete */}
        <div className="ml-auto">
          <button onClick={async () => {
                    if (!confirm(`Delete ${ids.length} accounts?`)) return;
                    setLoading(true);
                    try { for (const id of ids) await telegramOutreachApi.deleteAccount(id);
                          toast(`${ids.length} deleted`, 'success'); onDone();
                    } catch { toast('Delete failed', 'error'); } finally { setLoading(false); }
                  }} disabled={loading}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-400 text-xs font-medium hover:bg-red-100 dark:hover:bg-red-900/30 disabled:opacity-50">
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
                  disabled={loading} className="px-3 py-1 bg-indigo-600 text-white rounded text-xs font-medium">
            {loading ? 'Working...' : `Apply to ${ids.length}`}
          </button>
        </div>
      )}
      {activePanel === 'limit' && (
        <div className="flex items-center gap-2 pt-1">
          <span className={cn('text-xs', t.text3)}>Daily limit:</span>
          <input type="number" value={limitValue} onChange={e => setLimitValue(e.target.value)} className={cn(inputCls, 'w-20')} />
          <button onClick={() => run('Limit set', () => telegramOutreachApi.bulkSetLimit(ids, Number(limitValue)))}
                  disabled={loading} className="px-3 py-1 bg-indigo-600 text-white rounded text-xs font-medium">Apply</button>
        </div>
      )}
      {activePanel === 'bio' && (
        <div className="flex items-center gap-2 pt-1">
          <span className={cn('text-xs', t.text3)}>Bio:</span>
          <input type="text" value={bioValue} onChange={e => setBioValue(e.target.value)}
                 placeholder="BDM at Company" className={cn(inputCls, 'flex-1')} />
          <button onClick={() => run('Bio set', () => telegramOutreachApi.bulkSetBio(ids, bioValue))}
                  disabled={loading || !bioValue} className="px-3 py-1 bg-indigo-600 text-white rounded text-xs font-medium">Apply</button>
        </div>
      )}
      {activePanel === '2fa' && (
        <div className="flex items-center gap-2 pt-1">
          <span className={cn('text-xs', t.text3)}>2FA password:</span>
          <input type="text" value={twoFaValue} onChange={e => setTwoFaValue(e.target.value)}
                 className={cn(inputCls, 'w-40')} />
          <button onClick={() => run('2FA set', () => telegramOutreachApi.bulkSet2FA(ids, twoFaValue))}
                  disabled={loading || !twoFaValue} className="px-3 py-1 bg-indigo-600 text-white rounded text-xs font-medium">Apply</button>
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
                  disabled={loading} className="px-3 py-1 bg-indigo-600 text-white rounded text-xs font-medium">Apply</button>
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
                  disabled={loading || !proxyGroupId} className="px-3 py-1 bg-indigo-600 text-white rounded text-xs font-medium">Apply</button>
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

function EditAccountModal({ t, toast, isDark, account, onClose, onSaved, onDeleted }: {
  t: any; toast: any; isDark: boolean; account: TgAccount;
  onClose: () => void; onSaved: () => void; onDeleted: () => void;
}) {
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
  const inputCls = cn('w-full px-3 py-2 rounded-lg border text-sm', t.cardBorder, t.cardBg, t.text1);
  const labelCls = cn('block text-xs font-medium mb-1', t.text3);

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

  return (
    <ModalBackdrop onClose={onClose}>
      <div className={cn('w-[560px] rounded-xl border shadow-xl', t.cardBorder, isDark ? 'bg-gray-900' : 'bg-white')}>
        {/* Header */}
        <div className={cn('flex items-center justify-between px-6 py-4 border-b', t.cardBorder)}>
          <div>
            <h2 className={cn('text-lg font-semibold', t.text1)}>Edit Account</h2>
            <p className={cn('text-xs font-mono', t.text3)}>{account.phone}</p>
          </div>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-4 space-y-4">
          {/* Status + Limit */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Status</label>
              <select value={form.status} onChange={e => set('status', e.target.value)} className={inputCls}>
                <option value="active">Active</option>
                <option value="paused">Paused</option>
                <option value="spamblocked">Spamblocked</option>
                <option value="dead">Dead</option>
                <option value="frozen">Frozen</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>Daily Message Limit</label>
              <input type="number" value={form.daily_message_limit}
                     onChange={e => set('daily_message_limit', e.target.value)} className={inputCls} />
            </div>
          </div>

          {/* Profile */}
          <div className="grid grid-cols-2 gap-3">
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
              <input value={form.username} onChange={e => set('username', e.target.value)} className={inputCls} />
            </div>
          </div>

          <div>
            <label className={labelCls}>Bio</label>
            <textarea value={form.bio} onChange={e => set('bio', e.target.value)} rows={2} className={inputCls} />
          </div>

          {/* Info block */}
          <div className={cn('rounded-lg border p-3 grid grid-cols-3 gap-3 text-center', t.cardBorder)}>
            <div>
              <div className={cn('text-lg font-bold', t.text1)}>{account.messages_sent_today}</div>
              <div className={cn('text-xs', t.text3)}>Sent Today</div>
            </div>
            <div>
              <div className={cn('text-lg font-bold', t.text1)}>{account.total_messages_sent}</div>
              <div className={cn('text-xs', t.text3)}>Total Sent</div>
            </div>
            <div>
              <div className={cn('text-lg font-bold', t.text1)}>{account.campaigns_count}</div>
              <div className={cn('text-xs', t.text3)}>Campaigns</div>
            </div>
          </div>

          {/* Telegram Actions */}
          <div className={cn('rounded-lg border p-4 space-y-3', t.cardBorder)}>
            <h4 className={cn('text-xs font-semibold', t.text3)}>Telegram Actions</h4>
            <div className="flex items-center gap-2 flex-wrap">
              {/* Upload Session */}
              <button onClick={() => sessionFileRef.current?.click()}
                      className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder, t.text1)}>
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
                      className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder, t.text1)}>
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
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 text-white text-xs font-medium hover:bg-emerald-700 disabled:opacity-50">
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
                      className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder, t.text1)}>
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
                      className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder, t.text1)}>
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
                      className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder, t.text1)}>
                TDATA → Session
              </button>
              <a href={telegramOutreachApi.downloadTdata(account.id)}
                 target="_blank" rel="noreferrer"
                 className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder, t.text1)}>
                Download TDATA
              </a>
            </div>

            {/* Auth code input */}
            {authStep === 'code_sent' && (
              <div className="flex items-center gap-2">
                <input value={authCode} onChange={e => setAuthCode(e.target.value)}
                       placeholder="Enter code from Telegram"
                       className={cn('flex-1 px-3 py-1.5 rounded-lg border text-sm font-mono', t.cardBorder, t.cardBg, t.text1)} />
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
                        className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-medium hover:bg-indigo-700 disabled:opacity-50">
                  {authLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Verify'}
                </button>
              </div>
            )}

            {/* 2FA input */}
            {authStep === '2fa_required' && (
              <div className="flex items-center gap-2">
                <input type="password" value={authPassword} onChange={e => setAuthPassword(e.target.value)}
                       placeholder="Enter 2FA password"
                       className={cn('flex-1 px-3 py-1.5 rounded-lg border text-sm', t.cardBorder, t.cardBg, t.text1)} />
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
                        className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-medium hover:bg-indigo-700 disabled:opacity-50">
                  {authLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Verify 2FA'}
                </button>
              </div>
            )}

            {/* Check result */}
            {checkResult && (
              <div className={cn('rounded-lg p-3 text-xs space-y-1', isDark ? 'bg-gray-800' : 'bg-gray-50')}>
                <div className="flex gap-4">
                  <span>Connected: <b className={checkResult.connected ? 'text-green-500' : 'text-red-500'}>{checkResult.connected ? 'Yes' : 'No'}</b></span>
                  <span>Authorized: <b className={checkResult.authorized ? 'text-green-500' : 'text-red-500'}>{checkResult.authorized ? 'Yes' : 'No'}</b></span>
                  <span>Spamblock: <b className={checkResult.spamblock === 'none' ? 'text-green-500' : 'text-red-500'}>{checkResult.spamblock}</b></span>
                </div>
                {checkResult.error && <p className="text-red-500">Error: {checkResult.error}</p>}
              </div>
            )}
          </div>

          {/* Technical */}
          <details className="group">
            <summary className={cn('text-xs font-semibold cursor-pointer select-none flex items-center gap-1', t.text3)}>
              <ChevronDown className="w-3.5 h-3.5 transition-transform group-open:rotate-180" />
              Technical Settings
            </summary>
            <div className="grid grid-cols-2 gap-3 mt-3">
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
        <div className={cn('flex items-center justify-between px-6 py-4 border-t', t.cardBorder)}>
          <button onClick={handleDelete}
                  className="flex items-center gap-1.5 px-3 py-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg text-sm">
            <Trash2 className="w-3.5 h-3.5" /> Delete
          </button>
          <div className="flex items-center gap-3">
            <button onClick={onClose}
                    className={cn('px-4 py-2 rounded-lg border text-sm', t.cardBorder, t.text1)}>Cancel</button>
            <button onClick={handleSave} disabled={saving}
                    className="flex items-center gap-2 px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              Save
            </button>
          </div>
        </div>
      </div>
    </ModalBackdrop>
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

function ParserTab({ t, toast }: { t: any; toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) {
  const { isDark } = useTheme();
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

  const inputCls = cn('px-3 py-2 rounded-lg border text-sm', t.cardBorder, t.cardBg, t.text1);

  return (
    <div className="max-w-4xl space-y-4">
      <div className={cn('rounded-lg border p-5', t.cardBorder)}>
        <h3 className={cn('text-sm font-semibold mb-4', t.text1)}>Scrape Group Members</h3>
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className={cn('block text-xs font-medium mb-1', t.text3)}>Group/Channel</label>
            <input value={groupInput} onChange={e => setGroupInput(e.target.value)}
                   placeholder="@group_username or t.me/group" className={inputCls + ' w-full'} />
          </div>
          <div>
            <label className={cn('block text-xs font-medium mb-1', t.text3)}>Account</label>
            <select value={accountId} onChange={e => setAccountId(e.target.value ? Number(e.target.value) : '')}
                    className={inputCls}>
              <option value="">Select...</option>
              {accounts.map(a => <option key={a.id} value={a.id}>{a.phone} {a.first_name || ''}</option>)}
            </select>
          </div>
          <button onClick={handleScrape} disabled={loading}
                  className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Scrape'}
          </button>
        </div>
      </div>

      {members.length > 0 && (
        <div className={cn('rounded-lg border p-5', t.cardBorder)}>
          <div className="flex items-center justify-between mb-3">
            <h3 className={cn('text-sm font-semibold', t.text1)}>{members.length} members found</h3>
            <div className="flex items-center gap-2">
              <select value={targetCampaignId}
                      onChange={e => setTargetCampaignId(e.target.value ? Number(e.target.value) : '')}
                      className={inputCls}>
                <option value="">Add to campaign...</option>
                {campaigns.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <button onClick={handleAddToCampaign} disabled={!targetCampaignId}
                      className="px-3 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50">
                Add All
              </button>
            </div>
          </div>
          <div className={cn('rounded-lg border overflow-auto max-h-80', t.cardBorder)}>
            <table className="w-full text-xs">
              <thead className={cn('border-b sticky top-0', t.cardBorder, isDark ? 'bg-gray-800' : 'bg-gray-50')}>
                <tr>
                  <th className={cn('text-left px-3 py-2 font-medium', t.text3)}>Username</th>
                  <th className={cn('text-left px-3 py-2 font-medium', t.text3)}>Name</th>
                  <th className={cn('text-left px-3 py-2 font-medium', t.text3)}>Premium</th>
                  <th className={cn('text-left px-3 py-2 font-medium', t.text3)}>Photo</th>
                </tr>
              </thead>
              <tbody>
                {members.map((m: any, i: number) => (
                  <tr key={i} className={cn('border-b', t.cardBorder)}>
                    <td className={cn('px-3 py-1.5 font-mono', t.text1)}>@{m.username}</td>
                    <td className={cn('px-3 py-1.5', t.text1)}>{[m.first_name, m.last_name].filter(Boolean).join(' ')}</td>
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

const CRM_STATUS_COLORS: Record<string, string> = {
  cold: 'bg-gray-100 text-gray-700 dark:bg-gray-700/30 dark:text-gray-400',
  contacted: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  replied: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  qualified: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  meeting_set: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400',
  converted: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  not_interested: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

const CRM_PIPELINE = ['cold', 'contacted', 'replied', 'qualified', 'meeting_set', 'converted', 'not_interested'];

function CrmTab({ t, toast }: { t: any; toast: (msg: string, type?: 'success' | 'error' | 'info') => void }) {
  const { isDark } = useTheme();
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
                  className={cn('rounded-lg border px-3 py-2 text-center transition-colors', t.cardBorder,
                    statusFilter === s ? 'ring-2 ring-indigo-500' : '')}>
            <div className={cn('text-xl font-bold', t.text1)}>{stats[s] || 0}</div>
            <div className={cn('text-[10px] capitalize', t.text3)}>{s.replace('_', ' ')}</div>
          </button>
        ))}
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1 max-w-md">
          <Search className={cn('absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5', t.text3)} />
          <input type="text" placeholder="Search contacts..." value={search}
                 onChange={e => { setSearch(e.target.value); setPage(1); }}
                 className={cn('pl-8 pr-3 py-1.5 rounded-lg border text-xs w-full', t.cardBorder, t.cardBg, t.text1)} />
        </div>
        <span className={cn('text-xs', t.text3)}>{total} contacts</span>
        {selectedIds.size > 0 && (
          <div className="flex items-center gap-1 ml-auto">
            <span className={cn('text-xs', t.text3)}>{selectedIds.size} selected</span>
            <select onChange={e => {
                      if (!e.target.value) return;
                      telegramOutreachApi.bulkUpdateCrmStatus(Array.from(selectedIds), e.target.value)
                        .then(() => { toast('Updated', 'success'); loadContacts(); loadStats(); setSelectedIds(new Set()); })
                        .catch(() => toast('Failed', 'error'));
                      e.target.value = '';
                    }}
                    className={cn('px-2 py-1 rounded border text-xs', t.cardBorder, t.cardBg, t.text1)}>
              <option value="">Set status...</option>
              {CRM_PIPELINE.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
            </select>
          </div>
        )}
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className={cn('w-6 h-6 animate-spin', t.text3)} /></div>
      ) : contacts.length === 0 ? (
        <div className={cn('text-center py-12 rounded-lg border', t.cardBorder)}>
          <Users className={cn('w-10 h-10 mx-auto mb-3', t.text3)} />
          <p className={cn('text-sm', t.text3)}>No CRM contacts yet. Contacts auto-created when campaigns send messages.</p>
        </div>
      ) : (
        <div className={cn('rounded-lg border overflow-hidden', t.cardBorder)}>
          <table className="w-full text-sm">
            <thead className={cn('border-b', t.cardBorder, isDark ? 'bg-gray-800/50' : 'bg-gray-50')}>
              <tr>
                <th className="w-8 px-2 py-2"><input type="checkbox" onChange={e => {
                  setSelectedIds(e.target.checked ? new Set(contacts.map((c: any) => c.id)) : new Set());
                }} className="rounded" /></th>
                <th className={cn('text-left px-3 py-2 text-xs font-medium', t.text3)}>Username</th>
                <th className={cn('text-left px-3 py-2 text-xs font-medium', t.text3)}>Name</th>
                <th className={cn('text-left px-3 py-2 text-xs font-medium', t.text3)}>Company</th>
                <th className={cn('text-left px-3 py-2 text-xs font-medium', t.text3)}>Status</th>
                <th className={cn('text-left px-2 py-2 text-xs font-medium', t.text3)}>Sent</th>
                <th className={cn('text-left px-2 py-2 text-xs font-medium', t.text3)}>Replies</th>
                <th className={cn('text-left px-3 py-2 text-xs font-medium', t.text3)}>Campaigns</th>
                <th className={cn('text-left px-3 py-2 text-xs font-medium', t.text3)}>Last Contact</th>
              </tr>
            </thead>
            <tbody>
              {contacts.map((c: any) => (
                <tr key={c.id} onClick={() => openContact(c)}
                    className={cn('border-b cursor-pointer transition-colors', t.cardBorder,
                      selectedIds.has(c.id) ? 'bg-indigo-50/60 dark:bg-indigo-900/15' : 'hover:bg-gray-50 dark:hover:bg-gray-800/50')}>
                  <td className="px-2 py-2" onClick={e => e.stopPropagation()}>
                    <input type="checkbox" checked={selectedIds.has(c.id)}
                           onChange={() => setSelectedIds(prev => {
                             const next = new Set(prev); next.has(c.id) ? next.delete(c.id) : next.add(c.id); return next;
                           })} className="rounded" />
                  </td>
                  <td className={cn('px-3 py-2 font-mono text-xs', t.text1)}>@{c.username}</td>
                  <td className={cn('px-3 py-2 text-xs', t.text1)}>{[c.first_name, c.last_name].filter(Boolean).join(' ') || '--'}</td>
                  <td className={cn('px-3 py-2 text-xs', t.text3)}>{c.company_name || '--'}</td>
                  <td className="px-3 py-2">
                    <select value={c.status} onClick={e => e.stopPropagation()}
                            onChange={e => updateStatus(c.id, e.target.value)}
                            className={cn('px-1.5 py-0.5 rounded-full text-[10px] font-medium border-0 cursor-pointer',
                              CRM_STATUS_COLORS[c.status] || 'bg-gray-100')}>
                      {CRM_PIPELINE.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                    </select>
                  </td>
                  <td className={cn('px-2 py-2 text-xs font-mono', t.text1)}>{c.total_messages_sent}</td>
                  <td className={cn('px-2 py-2 text-xs font-mono', c.total_replies_received > 0 ? 'text-green-600' : t.text3)}>
                    {c.total_replies_received}
                  </td>
                  <td className={cn('px-3 py-2 text-[10px]', t.text3)}>
                    {(c.campaigns || []).map((camp: any) => camp.name).join(', ').substring(0, 30) || '--'}
                  </td>
                  <td className={cn('px-3 py-2 text-xs', t.text3)}>
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
          <span className={cn('text-sm', t.text3)}>{total} total</span>
          <div className="flex items-center gap-2">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
                    className={cn('px-3 py-1.5 rounded border text-sm', t.cardBorder, page <= 1 && 'opacity-50')}>Prev</button>
            <span className={cn('text-sm', t.text1)}>Page {page}/{totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
                    className={cn('px-3 py-1.5 rounded border text-sm', t.cardBorder, page >= totalPages && 'opacity-50')}>Next</button>
          </div>
        </div>
      )}

      {/* Contact Detail Modal */}
      {selectedContact && (
        <ModalBackdrop onClose={() => setSelectedContact(null)}>
          <div className={cn('w-[600px] rounded-xl border shadow-xl max-h-[80vh] overflow-y-auto', t.cardBorder, isDark ? 'bg-gray-900' : 'bg-white')}>
            <div className={cn('px-6 py-4 border-b flex items-center justify-between', t.cardBorder)}>
              <div>
                <h2 className={cn('text-lg font-semibold', t.text1)}>@{selectedContact.username}</h2>
                <p className={cn('text-xs', t.text3)}>
                  {[selectedContact.first_name, selectedContact.last_name].filter(Boolean).join(' ')}
                  {selectedContact.company_name ? ` - ${selectedContact.company_name}` : ''}
                </p>
              </div>
              <button onClick={() => setSelectedContact(null)} className="p-1 hover:bg-gray-100 dark:hover:bg-gray-800 rounded">
                <X className="w-5 h-5 text-gray-400" />
              </button>
            </div>
            <div className="px-6 py-4 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={cn('block text-xs font-medium mb-1', t.text3)}>Status</label>
                  <select value={selectedContact.status}
                          onChange={e => { updateStatus(selectedContact.id, e.target.value); setSelectedContact({...selectedContact, status: e.target.value}); }}
                          className={cn('w-full px-3 py-2 rounded-lg border text-sm', t.cardBorder, t.cardBg, t.text1)}>
                    {CRM_PIPELINE.map(s => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
                  </select>
                </div>
                <div>
                  <label className={cn('block text-xs font-medium mb-1', t.text3)}>Campaigns</label>
                  <div className={cn('text-xs pt-2', t.text1)}>
                    {(selectedContact.campaigns || []).map((c: any) => c.name).join(', ') || 'None'}
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className={cn('rounded-lg border p-2', t.cardBorder)}>
                  <div className={cn('text-lg font-bold', t.text1)}>{selectedContact.total_messages_sent}</div>
                  <div className={cn('text-[10px]', t.text3)}>Sent</div>
                </div>
                <div className={cn('rounded-lg border p-2', t.cardBorder)}>
                  <div className="text-lg font-bold text-green-600">{selectedContact.total_replies_received}</div>
                  <div className={cn('text-[10px]', t.text3)}>Replies</div>
                </div>
                <div className={cn('rounded-lg border p-2', t.cardBorder)}>
                  <div className={cn('text-lg font-bold', t.text1)}>
                    {selectedContact.last_reply_at ? new Date(selectedContact.last_reply_at).toLocaleDateString() : '--'}
                  </div>
                  <div className={cn('text-[10px]', t.text3)}>Last Reply</div>
                </div>
              </div>
              <div>
                <h3 className={cn('text-xs font-semibold mb-2', t.text1)}>History</h3>
                {history.length === 0 ? (
                  <p className={cn('text-xs text-center py-4', t.text3)}>No messages yet</p>
                ) : (
                  <div className="space-y-1.5 max-h-60 overflow-y-auto">
                    {history.map((h: any, i: number) => (
                      <div key={i} className={cn('rounded px-3 py-2 text-xs',
                        h.type === 'sent' ? (isDark ? 'bg-gray-800' : 'bg-gray-50') : 'bg-green-50 dark:bg-green-900/20')}>
                        <div className="flex items-center justify-between mb-0.5">
                          <span className={cn('font-medium', h.type === 'sent' ? t.text3 : 'text-green-600')}>
                            {h.type === 'sent' ? 'Sent' : 'Reply'}
                          </span>
                          <span className={cn('text-[10px]', t.text3)}>
                            {h.time ? new Date(h.time).toLocaleString() : ''}
                          </span>
                        </div>
                        <p className={t.text1}>{h.text}</p>
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
