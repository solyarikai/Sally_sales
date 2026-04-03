import { useState, useCallback, useEffect, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Settings2, ListOrdered, Users, Eye, MessageSquare, Reply, Download,
  Plus, Trash2, Save, Upload, Loader2, Play, Pause,
  ChevronLeft, ChevronRight, RefreshCw, Type, BarChart3, X, Search, UserPlus, Check,
  Table2, AlertTriangle, Image, Video, FileText, Mic, Paperclip,
  Bold, Italic, Code2, Braces, Pencil, ChevronDown, Clock,
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { cn } from '../lib/utils';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { useToast } from '../components/Toast';
import { telegramOutreachApi } from '../api/telegramOutreach';
import type {
  TgCampaign, TgSequence, TgSequenceStep, TgStepVariant,
  TgRecipient, TgCampaignStats, TgAccount, MessageType,
} from '../api/telegramOutreach';

type Tab = 'recipients' | 'messages' | 'accounts' | 'review';

// ── Design tokens (match TelegramOutreachPage) ──────────────────────
const B = {
  border: '#E8E6E3', bg: '#FAFAF8', surface: '#FFFFFF',
  text1: '#1A1A1A', text2: '#6B6B6B', text3: '#9CA3AF',
  blue: '#4F6BF0', blueBg: '#EEF1FE',
};

// ══════════════════════════════════════════════════════════════════════
// Main Page
// ══════════════════════════════════════════════════════════════════════

export function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const toastCtx = useToast();
  const toast = useCallback((msg: string, type: 'success' | 'error' | 'info' = 'info') => {
    toastCtx[type](msg);
  }, [toastCtx]);

  const campaignId = Number(id);
  const [campaign, setCampaign] = useState<TgCampaign | null>(null);
  const [tab, setTab] = useState<Tab>('recipients');
  const [loading, setLoading] = useState(true);

  const loadCampaign = useCallback(async () => {
    try {
      const data = await telegramOutreachApi.listCampaigns();
      const found = data.items.find((c: TgCampaign) => c.id === campaignId);
      if (found) setCampaign(found);
      else toast('Campaign not found', 'error');
    } catch {
      toast('Failed to load campaign', 'error');
    } finally {
      setLoading(false);
    }
  }, [campaignId, toast]);

  useEffect(() => { loadCampaign(); }, [loadCampaign]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className={cn('w-8 h-8 animate-spin', t.text3)} />
      </div>
    );
  }

  if (!campaign) {
    return (
      <div className={cn('flex flex-col items-center justify-center h-full gap-4', t.text3)}>
        <p>Campaign not found</p>
        <button onClick={() => navigate('/outreach/campaigns')}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm">
          Back to Outreach
        </button>
      </div>
    );
  }

  const isTabFilled = (key: Tab): boolean => {
    switch (key) {
      case 'recipients': return campaign.total_recipients > 0;
      case 'messages': return true;
      case 'accounts': return campaign.accounts_count > 0;
      case 'review': return true;
    }
  };

  const tabs: { key: Tab; label: string; icon: typeof Settings2; step: number }[] = [
    { key: 'recipients', label: 'Recipients', icon: Users, step: 1 },
    { key: 'messages', label: 'Messages', icon: MessageSquare, step: 2 },
    { key: 'accounts', label: 'Accounts', icon: Settings2, step: 3 },
    { key: 'review', label: 'Review', icon: Eye, step: 4 },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div style={{ borderBottom: `1px solid ${B.border}` }} className="px-6 py-4">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/outreach/campaigns')}
                  className="p-1.5 rounded-lg hover:bg-gray-100" style={{ color: B.text2 }}>
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex-1">
            <h1 className="text-xl font-semibold" style={{ color: B.text1 }}>{campaign.name}</h1>
            <div className="flex items-center gap-3 mt-1 text-sm" style={{ color: B.text3 }}>
              <StatusBadge status={campaign.status} />
              <span>{campaign.total_recipients} recipients</span>
              <span>{campaign.total_messages_sent} sent</span>
              <span>{campaign.accounts_count} accounts</span>
            </div>
          </div>
          <button onClick={async () => {
                    try {
                      if (campaign.status === 'active') {
                        await telegramOutreachApi.pauseCampaign(campaignId);
                        toast('Campaign paused', 'info');
                      } else {
                        await telegramOutreachApi.startCampaign(campaignId);
                        toast('Campaign started', 'success');
                      }
                      loadCampaign();
                    } catch (e: any) {
                      toast(e?.response?.data?.detail || 'Action failed', 'error');
                    }
                  }}
                  style={{ background: campaign.status === 'active' ? '#FFFBEB' : '#059669', color: campaign.status === 'active' ? '#D97706' : '#fff', borderRadius: 8 }}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium">
            {campaign.status === 'active' ? <><Pause className="w-4 h-4" /> Pause</> : <><Play className="w-4 h-4" /> Start</>}
          </button>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-1 mt-4">
          {tabs.map(({ key, label, icon: Icon, step }, i) => {
            const active = tab === key;
            const filled = isTabFilled(key);
            return (
              <div key={key} className="flex items-center">
                {i > 0 && <div className="w-6 h-px mx-0.5" style={{ background: B.border }} />}
                <button
                  onClick={() => setTab(key)}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                  style={active
                    ? { background: B.blueBg, color: B.blue }
                    : { color: B.text3 }}
                  onMouseEnter={e => { if (!active) (e.currentTarget as HTMLElement).style.background = '#F5F5F0'; }}
                  onMouseLeave={e => { if (!active) (e.currentTarget as HTMLElement).style.background = ''; }}
                >
                  <span className={cn(
                    'flex items-center justify-center w-5 h-5 rounded-full text-[11px] font-bold shrink-0',
                    active ? 'bg-[#4F6BF0] text-white' :
                    filled ? 'bg-emerald-100 text-emerald-600' :
                    'bg-gray-200 text-gray-400'
                  )}>
                    {filled && !active ? <Check className="w-3 h-3" /> : step}
                  </span>
                  <Icon className="w-4 h-4" />
                  {label}
                  {!filled && key !== 'review' && !active && (
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400 shrink-0" />
                  )}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-5xl mx-auto">
          {tab === 'recipients' && (
            <RecipientsTab campaignId={campaignId} t={t} toast={toast} isDark={isDark} />
          )}
          {tab === 'messages' && (
            <div className="space-y-8">
              <SequenceTab campaignId={campaignId} t={t} toast={toast} isDark={isDark} />
              <div className="border-t pt-8" style={{ borderColor: B.border }}>
                <AutoReplyTab campaignId={campaignId} t={t} toast={toast} isDark={isDark} />
              </div>
            </div>
          )}
          {tab === 'accounts' && (
            <SettingsTab campaign={campaign} onUpdate={loadCampaign} t={t} toast={toast} isDark={isDark} />
          )}
          {tab === 'review' && (
            <ReviewTab campaignId={campaignId} campaign={campaign} t={t} toast={toast} isDark={isDark} onStart={async () => {
              const missing: string[] = [];
              if (campaign.total_recipients === 0) missing.push('Recipients');
              if (campaign.accounts_count === 0) missing.push('Accounts');
              if (missing.length > 0) {
                toast(`Please fill in: ${missing.join(', ')}`, 'error');
                return;
              }
              try {
                await telegramOutreachApi.startCampaign(campaignId);
                toast('Campaign started!', 'success');
                loadCampaign();
              } catch (e: any) {
                toast(e?.response?.data?.detail || 'Failed to start campaign', 'error');
              }
            }} />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Status Badge ──────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700 dark:bg-gray-700/30 dark:text-gray-400',
  active: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  paused: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
  completed: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
};

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', STATUS_COLORS[status] || 'bg-gray-100 text-gray-600')}>
      {status}
    </span>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Settings Tab
// ══════════════════════════════════════════════════════════════════════

interface TabProps {
  t: ReturnType<typeof themeColors>;
  toast: (msg: string, type?: 'success' | 'error' | 'info') => void;
  isDark: boolean;
}

function SettingsTab({ campaign, onUpdate, t, toast, isDark }: TabProps & { campaign: TgCampaign; onUpdate: () => void }) {
  const [form, setForm] = useState({
    name: campaign.name,
    daily_message_limit: campaign.daily_message_limit ?? '',
    timezone: campaign.timezone,
    send_from_hour: campaign.send_from_hour,
    send_to_hour: campaign.send_to_hour,
    link_preview: (campaign as any).link_preview || false,
    silent: (campaign as any).silent || false,
    delete_dialog_after: (campaign as any).delete_dialog_after || false,
    crm_tag_on_reply: campaign.crm_tag_on_reply || [],
    crm_status_on_reply: campaign.crm_status_on_reply || '',
    crm_owner_on_reply: campaign.crm_owner_on_reply || '',
    crm_auto_create_contact: campaign.crm_auto_create_contact !== false,
  });
  const [saving, setSaving] = useState(false);
  const [newCrmTag, setNewCrmTag] = useState('');

  // Accounts management
  const [allAccounts, setAllAccounts] = useState<TgAccount[]>([]);
  const [campaignAccountIds, setCampaignAccountIds] = useState<Set<number>>(new Set());
  const [loadingAccounts, setLoadingAccounts] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [accData, campAccs] = await Promise.all([
          telegramOutreachApi.listAccounts({ page_size: 200 }),
          telegramOutreachApi.getCampaignAccounts(campaign.id),
        ]);
        setAllAccounts(accData.items);
        setCampaignAccountIds(new Set((campAccs as any[]).map((a: any) => a.id)));
      } catch {
        toast('Failed to load accounts', 'error');
      } finally {
        setLoadingAccounts(false);
      }
    })();
  }, [campaign.id, toast]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const updateData: Record<string, any> = { ...form };
      if (updateData.daily_message_limit === '') updateData.daily_message_limit = null;
      else updateData.daily_message_limit = Number(updateData.daily_message_limit);
      if (updateData.crm_status_on_reply === '') updateData.crm_status_on_reply = null;
      if (updateData.crm_owner_on_reply === '') updateData.crm_owner_on_reply = null;

      await telegramOutreachApi.updateCampaign(campaign.id, updateData);
      await telegramOutreachApi.setCampaignAccounts(campaign.id, Array.from(campaignAccountIds));
      toast('Settings saved', 'success');
      // Reload account assignments to confirm save
      const freshAccs = await telegramOutreachApi.getCampaignAccounts(campaign.id);
      setCampaignAccountIds(new Set((freshAccs as any[]).map((a: any) => a.id)));
      onUpdate();
    } catch {
      toast('Failed to save settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  const toggleAccount = (id: number) => {
    setCampaignAccountIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const inputCls = cn('w-full px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 text-sm focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-400 outline-none', 'bg-white dark:bg-gray-900', t.text1);
  const labelCls = cn('block text-sm font-medium mb-1', t.text2);

  return (
    <div className="space-y-6">
      {/* Campaign Name */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-700 p-5 shadow-sm">
        <h3 className={cn('text-sm font-semibold mb-4', t.text1)}>General</h3>
        <div>
          <label className={labelCls}>Campaign Name</label>
          <input type="text" value={form.name}
                 onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                 className={inputCls} />
        </div>
      </div>

      {/* Sending Settings */}
      <div className={cn('rounded-lg border p-5', 'border-gray-200 dark:border-gray-700')}>
        <h3 className={cn('text-sm font-semibold mb-4', t.text1)}>Sending Settings</h3>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Daily Message Limit (campaign-wide)</label>
            <input type="number" value={form.daily_message_limit}
                   onChange={e => setForm(f => ({ ...f, daily_message_limit: e.target.value as any }))}
                   placeholder="No limit"
                   className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>Timezone</label>
            <select value={form.timezone}
                    onChange={e => setForm(f => ({ ...f, timezone: e.target.value }))}
                    className={inputCls}>
              <option value="Europe/Moscow">Europe/Moscow</option>
              <option value="Europe/London">Europe/London</option>
              <option value="Europe/Berlin">Europe/Berlin</option>
              <option value="America/New_York">America/New_York</option>
              <option value="Asia/Singapore">Asia/Singapore</option>
              <option value="Asia/Tokyo">Asia/Tokyo</option>
              <option value="UTC">UTC</option>
            </select>
          </div>
          <div>
            <label className={labelCls}>Send From (hour)</label>
            <input type="number" min={0} max={23} value={form.send_from_hour}
                   onChange={e => setForm(f => ({ ...f, send_from_hour: Number(e.target.value) }))}
                   className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>Send To (hour)</label>
            <input type="number" min={0} max={23} value={form.send_to_hour}
                   onChange={e => setForm(f => ({ ...f, send_to_hour: Number(e.target.value) }))}
                   className={inputCls} />
          </div>
        </div>

        {/* Send Options */}
        <div className="flex items-center gap-6 mt-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.link_preview}
                   onChange={e => setForm(f => ({ ...f, link_preview: e.target.checked }))}
                   className="rounded" style={{ accentColor: '#4F6BF0' }} />
            <span className={cn('text-sm', t.text1)}>Link Preview</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.silent}
                   onChange={e => setForm(f => ({ ...f, silent: e.target.checked }))}
                   className="rounded" style={{ accentColor: '#4F6BF0' }} />
            <span className={cn('text-sm', t.text1)}>Silent Messages</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.delete_dialog_after}
                   onChange={e => setForm(f => ({ ...f, delete_dialog_after: e.target.checked }))}
                   className="rounded" style={{ accentColor: '#4F6BF0' }} />
            <span className={cn('text-sm', t.text1)}>Delete Dialog After Send</span>
          </label>
        </div>
      </div>

      {/* CRM Lead Settings */}
      <div className={cn('rounded-lg border p-5', 'border-gray-200 dark:border-gray-700')}>
        <h3 className={cn('text-sm font-semibold mb-1', t.text1)}>CRM Lead Settings</h3>
        <p className={cn('text-xs mb-4', t.text3)}>Auto-apply tags, status and owner when a lead replies to this campaign.</p>

        <div className="grid grid-cols-2 gap-4">
          {/* Status on reply */}
          <div>
            <label className={labelCls}>Status on Reply</label>
            <select value={form.crm_status_on_reply}
                    onChange={e => setForm(f => ({ ...f, crm_status_on_reply: e.target.value }))}
                    className={inputCls}>
              <option value="">Default (replied)</option>
              <option value="replied">Replied</option>
              <option value="interested">Interested</option>
              <option value="qualified">Qualified</option>
              <option value="meeting_set">Meeting Set</option>
              <option value="converted">Converted</option>
              <option value="not_interested">Not Interested</option>
            </select>
          </div>

          {/* Owner on reply */}
          <div>
            <label className={labelCls}>Owner on Reply</label>
            <input type="text" value={form.crm_owner_on_reply}
                   onChange={e => setForm(f => ({ ...f, crm_owner_on_reply: e.target.value }))}
                   placeholder="e.g. John"
                   className={inputCls} />
          </div>
        </div>

        {/* Tags on reply */}
        <div className="mt-4">
          <label className={labelCls}>Tags on Reply</label>
          <div className="flex flex-wrap gap-2 mb-2">
            {form.crm_tag_on_reply.map(tag => (
              <span key={tag} className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
                {tag}
                <button onClick={() => setForm(f => ({ ...f, crm_tag_on_reply: f.crm_tag_on_reply.filter(t2 => t2 !== tag) }))}
                        className="hover:text-red-500 transition-colors">&times;</button>
              </span>
            ))}
          </div>
          <div className="flex gap-2">
            <input type="text" value={newCrmTag}
                   onChange={e => setNewCrmTag(e.target.value)}
                   onKeyDown={e => {
                     if (e.key === 'Enter' && newCrmTag.trim()) {
                       e.preventDefault();
                       if (!form.crm_tag_on_reply.includes(newCrmTag.trim())) {
                         setForm(f => ({ ...f, crm_tag_on_reply: [...f.crm_tag_on_reply, newCrmTag.trim()] }));
                       }
                       setNewCrmTag('');
                     }
                   }}
                   placeholder="Add tag and press Enter"
                   className={inputCls} />
          </div>
        </div>

        {/* Auto-create contact */}
        <div className="flex items-center gap-2 mt-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.crm_auto_create_contact}
                   onChange={e => setForm(f => ({ ...f, crm_auto_create_contact: e.target.checked }))}
                   className="rounded" style={{ accentColor: '#4F6BF0' }} />
            <span className={cn('text-sm', t.text1)}>Auto-create CRM contact on reply (if not exists)</span>
          </label>
        </div>

        {/* Pipeline info */}
        <div className={cn('mt-4 p-3 rounded-lg text-xs', 'bg-gray-50 dark:bg-gray-800/50', t.text3)}>
          <span className="font-medium">Pipeline automation:</span>{' '}
          Sent &rarr; Contacted &bull; Replied &rarr; {form.crm_status_on_reply || 'Replied'} &bull; No reply after all steps &rarr; Not Interested
        </div>
      </div>

      {/* Accounts */}
      <div className={cn('rounded-lg border p-5', 'border-gray-200 dark:border-gray-700')}>
        <h3 className={cn('text-sm font-semibold mb-1', t.text1)}>Accounts</h3>
        <p className={cn('text-xs mb-4', t.text3)}>
          Select accounts to use for this campaign. {campaignAccountIds.size} selected.
        </p>

        {loadingAccounts ? (
          <div className="flex justify-center py-6">
            <Loader2 className={cn('w-5 h-5 animate-spin', t.text3)} />
          </div>
        ) : allAccounts.length === 0 ? (
          <p className={cn('text-sm py-4 text-center', t.text3)}>No accounts yet. Add accounts first.</p>
        ) : (
          <div className={cn('rounded-lg border overflow-hidden max-h-[320px] overflow-y-auto', 'border-gray-200 dark:border-gray-700')}>
            <table className="w-full text-sm">
              <thead className={cn('border-b sticky top-0 z-10', 'border-gray-200 dark:border-gray-700', isDark ? 'bg-gray-800/90' : 'bg-gray-50')}>
                <tr>
                  <th className="w-10 px-3 py-2">
                      <input type="checkbox"
                             checked={allAccounts.length > 0 && campaignAccountIds.size === allAccounts.length}
                             ref={el => { if (el) el.indeterminate = campaignAccountIds.size > 0 && campaignAccountIds.size < allAccounts.length; }}
                             onChange={() => {
                               if (campaignAccountIds.size === allAccounts.length) {
                                 setCampaignAccountIds(new Set());
                               } else {
                                 setCampaignAccountIds(new Set(allAccounts.map(a => a.id)));
                               }
                             }}
                             className="rounded" style={{ accentColor: '#4F6BF0', cursor: 'pointer' }} />
                    </th>
                  <th className={cn('text-left px-3 py-2 font-medium', t.text3)}>Phone</th>
                  <th className={cn('text-left px-3 py-2 font-medium', t.text3)}>Name</th>
                  <th className={cn('text-left px-3 py-2 font-medium', t.text3)}>Status</th>
                  <th className={cn('text-left px-3 py-2 font-medium', t.text3)}>Sent / Limit</th>
                  <th className={cn('text-left px-3 py-2 font-medium', t.text3)}>Campaigns</th>
                </tr>
              </thead>
              <tbody>
                {allAccounts.map(acc => (
                  <tr key={acc.id}
                      onClick={() => toggleAccount(acc.id)}
                      className={cn(
                        'border-b cursor-pointer transition-colors',
                        'border-gray-200 dark:border-gray-700',
                        campaignAccountIds.has(acc.id)
                          ? 'bg-indigo-50/50 dark:bg-indigo-900/15'
                          : 'hover:bg-gray-50 dark:hover:bg-gray-800/50',
                      )}>
                    <td className="px-3 py-2" onClick={e => e.stopPropagation()}>
                      <input type="checkbox" checked={campaignAccountIds.has(acc.id)}
                             onChange={() => toggleAccount(acc.id)} className="rounded" style={{ accentColor: '#4F6BF0', cursor: 'pointer' }} />
                    </td>
                    <td className={cn('px-3 py-2 text-xs', t.text1)} style={{ fontVariantNumeric: 'tabular-nums' }}>{acc.phone}</td>
                    <td className={cn('px-3 py-2', t.text1)}>
                      {[acc.first_name, acc.last_name].filter(Boolean).join(' ') || (
                        <span className={t.text3}>--</span>
                      )}
                    </td>
                    <td className="px-3 py-2"><StatusBadge status={acc.status} /></td>
                    <td className={cn('px-3 py-2 text-xs', t.text1)} style={{ fontVariantNumeric: 'tabular-nums' }}>
                      <span className={acc.messages_sent_today >= (acc.effective_daily_limit ?? acc.daily_message_limit) ? 'text-red-500' : ''}>
                        {acc.messages_sent_today}
                      </span>
                      <span className={t.text3}> / {acc.effective_daily_limit ?? acc.daily_message_limit}</span>
                      {acc.warmup_day != null && <span className="text-amber-500 text-[10px] ml-1" title={`Warm-up day ${acc.warmup_day}`}>WU</span>}
                      {acc.is_young_session && <span className="text-red-600 text-[10px] ml-1 font-semibold" title="Young session (<7 days) — reduced limits & slower sending">YOUNG</span>}
                    </td>
                    <td className={cn('px-3 py-2 text-xs', t.text3)}>{acc.campaigns_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Save */}
      <div className="flex justify-end">
        <button onClick={handleSave} disabled={saving}
                className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          Save Settings
        </button>
      </div>
    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════
// Sequence Tab
// ══════════════════════════════════════════════════════════════════════

function SequenceTab({ campaignId, t, toast, isDark }: TabProps & { campaignId: number }) {
  const [sequence, setSequence] = useState<TgSequence | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [customVars, setCustomVars] = useState<string[]>([]);
  const [stepStats, setStepStats] = useState<Record<number, { sent: number; read: number; replied: number }>>({});
  const [editingStep, setEditingStep] = useState<number | null>(null);
  const [previewStep, setPreviewStep] = useState<{ stepIdx: number; varIdx: number; text: string } | null>(null);

  // Load custom variable names from first recipient
  useEffect(() => {
    (async () => {
      try {
        const data = await telegramOutreachApi.listRecipients(campaignId, { page_size: 1 });
        if (data.items.length > 0 && data.items[0].custom_variables) {
          setCustomVars(Object.keys(data.items[0].custom_variables));
        }
      } catch { /* ok */ }
    })();
  }, [campaignId]);

  const loadSequence = useCallback(async () => {
    setLoading(true);
    try {
      const data = await telegramOutreachApi.getSequence(campaignId);
      setSequence(data);
    } catch {
      toast('Failed to load sequence', 'error');
    } finally {
      setLoading(false);
    }
  }, [campaignId, toast]);

  useEffect(() => { loadSequence(); }, [loadSequence]);

  // Load per-step statistics
  useEffect(() => {
    (async () => {
      try {
        const data = await telegramOutreachApi.getCampaignStepStats(campaignId);
        const map: Record<number, { sent: number; read: number; replied: number }> = {};
        data.steps.forEach(s => { map[s.step_order] = { sent: s.sent, read: s.read, replied: s.replied }; });
        setStepStats(map);
      } catch { /* ok */ }
    })();
  }, [campaignId]);

  const handleSave = async () => {
    if (!sequence) return;
    setSaving(true);
    try {
      const saved = await telegramOutreachApi.updateSequence(campaignId, sequence);
      setSequence(saved);
      toast('Sequence saved', 'success');
    } catch {
      toast('Failed to save sequence', 'error');
    } finally {
      setSaving(false);
    }
  };

  const addStep = () => {
    if (!sequence) return;
    const newOrder = sequence.steps.length + 1;
    setSequence({
      ...sequence,
      steps: [
        ...sequence.steps,
        {
          step_order: newOrder,
          delay_days: newOrder === 1 ? 0 : 1,
          message_type: 'text' as MessageType,
          variants: [{ variant_label: 'A', message_text: '', weight_percent: 100 }],
        },
      ],
    });
  };

  const removeStep = (idx: number) => {
    if (!sequence) return;
    const steps = sequence.steps.filter((_, i) => i !== idx)
      .map((s, i) => ({ ...s, step_order: i + 1 }));
    setSequence({ ...sequence, steps });
  };

  const updateStep = (idx: number, patch: Partial<TgSequenceStep>) => {
    if (!sequence) return;
    const steps = sequence.steps.map((s, i) => i === idx ? { ...s, ...patch } : s);
    setSequence({ ...sequence, steps });
  };

  const addVariant = (stepIdx: number) => {
    if (!sequence) return;
    const step = sequence.steps[stepIdx];
    const labels = 'ABCDEFGH';
    const newLabel = labels[step.variants.length] || `V${step.variants.length + 1}`;
    // Redistribute weights evenly
    const count = step.variants.length + 1;
    const weight = Math.floor(100 / count);
    const variants = [
      ...step.variants.map(v => ({ ...v, weight_percent: weight })),
      { variant_label: newLabel, message_text: '', weight_percent: 100 - weight * (count - 1) },
    ];
    updateStep(stepIdx, { variants });
  };

  const removeVariant = (stepIdx: number, varIdx: number) => {
    if (!sequence) return;
    const step = sequence.steps[stepIdx];
    if (step.variants.length <= 1) return;
    const variants = step.variants.filter((_, i) => i !== varIdx);
    // Redistribute weights
    const weight = Math.floor(100 / variants.length);
    const redistributed = variants.map((v, i) => ({
      ...v,
      weight_percent: i === variants.length - 1 ? 100 - weight * (variants.length - 1) : weight,
    }));
    updateStep(stepIdx, { variants: redistributed });
  };

  const updateVariant = (stepIdx: number, varIdx: number, patch: Partial<TgStepVariant>) => {
    if (!sequence) return;
    const step = sequence.steps[stepIdx];
    const variants = step.variants.map((v, i) => i === varIdx ? { ...v, ...patch } : v);
    updateStep(stepIdx, { variants });
  };

  const insertVariable = (stepIdx: number, varIdx: number, variable: string) => {
    setVarPopup(null);
    const textareaId = `seq-${stepIdx}-${varIdx}`;
    const el = document.getElementById(textareaId) as HTMLTextAreaElement | null;
    if (!el) return;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const currentText = sequence?.steps[stepIdx]?.variants[varIdx]?.message_text || '';
    const newText = currentText.substring(0, start) + `{{${variable}}}` + currentText.substring(end);
    updateVariant(stepIdx, varIdx, { message_text: newText });
    setTimeout(() => {
      el.focus();
      const pos = start + variable.length + 4;
      el.setSelectionRange(pos, pos);
    }, 0);
  };

  // ── { Variable insertion popup ────────────────────────────────────
  const [varPopup, setVarPopup] = useState<{
    stepIdx: number; varIdx: number; triggerPos: number; selectedIdx: number; filter: string;
  } | null>(null);
  const varPopupRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!varPopup) return;
    const handler = (e: MouseEvent) => {
      if (varPopupRef.current && !varPopupRef.current.contains(e.target as Node)) setVarPopup(null);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [varPopup]);

  const popupItems = useMemo(() => {
    const items: { name: string; label: string; type: 'var' | 'spintax'; section: 'system' | 'csv' }[] = [
      { name: 'username', label: 'Username', type: 'var', section: 'system' },
      { name: 'first_name', label: 'First name', type: 'var', section: 'system' },
      { name: 'company_name', label: 'Company name', type: 'var', section: 'system' },
      { name: '__spintax__', label: 'Random text (Spintax)', type: 'spintax', section: 'system' },
      ...customVars.map(v => ({ name: v, label: v, type: 'var' as const, section: 'csv' as const })),
    ];
    if (!varPopup?.filter) return items;
    const f = varPopup.filter;
    return items.filter(v => v.name.toLowerCase().includes(f) || v.label.toLowerCase().includes(f));
  }, [varPopup?.filter, customVars]);

  const selectPopupItem = (item: { name: string; type: string }) => {
    if (!varPopup || !sequence) return;
    const { stepIdx, varIdx, triggerPos } = varPopup;
    const el = document.getElementById(`seq-${stepIdx}-${varIdx}`) as HTMLTextAreaElement;
    const currentText = sequence.steps[stepIdx]?.variants[varIdx]?.message_text || '';
    const cursorPos = el?.selectionStart ?? triggerPos;
    const before = currentText.substring(0, triggerPos - 1);
    const after = currentText.substring(cursorPos);
    if (item.type === 'spintax') {
      const tpl = '{option1|option2|option3}';
      updateVariant(stepIdx, varIdx, { message_text: before + tpl + after });
      setVarPopup(null);
      setTimeout(() => { el?.focus(); el?.setSelectionRange(before.length + 1, before.length + tpl.length - 1); }, 0);
    } else {
      const ins = `{{${item.name}}}`;
      updateVariant(stepIdx, varIdx, { message_text: before + ins + after });
      setVarPopup(null);
      setTimeout(() => { el?.focus(); const p = before.length + ins.length; el?.setSelectionRange(p, p); }, 0);
    }
  };

  const handleSeqChange = (e: React.ChangeEvent<HTMLTextAreaElement>, stepIdx: number, varIdx: number) => {
    const val = e.target.value;
    updateVariant(stepIdx, varIdx, { message_text: val });
    const cur = e.target.selectionStart;
    if (cur > 0 && val[cur - 1] === '{') {
      if (cur > 1 && val[cur - 2] === '{') { setVarPopup(null); return; }
      setVarPopup({ stepIdx, varIdx, triggerPos: cur, selectedIdx: 0, filter: '' });
    } else if (varPopup?.stepIdx === stepIdx && varPopup?.varIdx === varIdx) {
      if (cur < varPopup.triggerPos) setVarPopup(null);
      else setVarPopup(p => p ? { ...p, filter: val.substring(p.triggerPos, cur).toLowerCase(), selectedIdx: 0 } : null);
    }
  };

  const handleSeqKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>, stepIdx: number, varIdx: number) => {
    if (!varPopup || varPopup.stepIdx !== stepIdx || varPopup.varIdx !== varIdx || !popupItems.length) return;
    if (e.key === 'Escape') { e.preventDefault(); setVarPopup(null); return; }
    if (e.key === 'ArrowDown') { e.preventDefault(); setVarPopup(p => p ? { ...p, selectedIdx: Math.min(p.selectedIdx + 1, popupItems.length - 1) } : null); return; }
    if (e.key === 'ArrowUp') { e.preventDefault(); setVarPopup(p => p ? { ...p, selectedIdx: Math.max(p.selectedIdx - 1, 0) } : null); return; }
    if (e.key === 'Enter' || e.key === 'Tab') { e.preventDefault(); selectPopupItem(popupItems[Math.min(varPopup.selectedIdx, popupItems.length - 1)]); }
  };

  const insertFormatting = (stepIdx: number, varIdx: number, type: 'bold' | 'italic' | 'code' | 'braces') => {
    const el = document.getElementById(`seq-${stepIdx}-${varIdx}`) as HTMLTextAreaElement | null;
    if (!el) return;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const text = el.value;
    const selected = text.substring(start, end);
    let before = '', after = '';
    switch (type) {
      case 'bold': before = '**'; after = '**'; break;
      case 'italic': before = '__'; after = '__'; break;
      case 'code': before = '`'; after = '`'; break;
      case 'braces': before = '{{'; after = '}}'; break;
    }
    const newText = text.substring(0, start) + before + (selected || (type === 'braces' ? 'variable' : 'text')) + after + text.substring(end);
    updateVariant(stepIdx, varIdx, { message_text: newText });
    setTimeout(() => {
      el.focus();
      if (selected) {
        el.setSelectionRange(start + before.length, start + before.length + selected.length);
      } else {
        el.setSelectionRange(start + before.length, start + before.length + (type === 'braces' ? 8 : 4));
      }
    }, 0);
  };

  const handlePreview = async (stepIdx: number, varIdx: number) => {
    const text = sequence?.steps[stepIdx]?.variants[varIdx]?.message_text || '';
    if (!text) return;
    setPreviewStep({ stepIdx, varIdx, text });
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className={cn('w-6 h-6 animate-spin', t.text3)} />
      </div>
    );
  }

  return (
    <div className="max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-base font-semibold" style={{ color: B.text1 }}>Message Sequence</h3>
          <p className="text-xs mt-1" style={{ color: B.text3 }}>
            Build your follow-up chain. Use {'{{variable}}'} for personalization and {'{option1|option2}'} for spintax.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={addStep}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors hover:opacity-90"
                  style={{ background: B.blue, color: '#fff' }}>
            <Plus className="w-3.5 h-3.5" /> Add Step
          </button>
          <button onClick={handleSave} disabled={saving}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors hover:opacity-90 disabled:opacity-50"
                  style={{ background: '#059669', color: '#fff' }}>
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            Save
          </button>
        </div>
      </div>

      {(!sequence || sequence.steps.length === 0) ? (
        <div className="text-center py-16 rounded-xl border" style={{ borderColor: B.border, background: B.surface }}>
          <ListOrdered className="w-10 h-10 mx-auto mb-3" style={{ color: B.text3 }} />
          <p className="text-sm" style={{ color: B.text3 }}>No steps yet. Add your first message step.</p>
          <button onClick={addStep}
                  className="mt-3 px-4 py-2 rounded-lg text-sm font-medium hover:opacity-90"
                  style={{ background: B.blue, color: '#fff' }}>
            <Plus className="w-4 h-4 inline mr-1" /> Add Step
          </button>
        </div>
      ) : (
        /* Steps with vertical timeline */
        <div className="relative pl-10">
          {/* Vertical connector line */}
          {sequence.steps.length > 1 && (
            <div className="absolute left-[15px] top-5 bottom-5 w-0.5 rounded-full" style={{ background: '#BBF7D0' }} />
          )}

          <div className="space-y-3">
            {sequence.steps.map((step, stepIdx) => {
              const isEditing = editingStep === stepIdx;
              const stats = stepStats[step.step_order];
              const preview = step.variants[0]?.message_text || '';
              const typeLabel = stepIdx === 0
                ? (step.message_type === 'text' ? 'Send text' : `Send ${step.message_type}`)
                : `Wait ${step.delay_days}d \u2192 Send ${step.message_type || 'text'}`;

              return (
                <div key={stepIdx} className="relative">
                  {/* Green circle marker on timeline */}
                  <div className="absolute -left-10 top-4 flex items-center justify-center w-[30px] h-[30px] rounded-full border-2 z-10 transition-colors"
                       style={{
                         background: isEditing ? '#059669' : B.surface,
                         borderColor: '#059669',
                         color: isEditing ? '#fff' : '#059669',
                       }}>
                    <span className="text-xs font-bold">{step.step_order}</span>
                  </div>

                  {isEditing ? (
                    /* ═══════════ EXPANDED EDIT CARD ═══════════ */
                    <div className="rounded-xl border overflow-hidden transition-shadow"
                         style={{ borderColor: '#059669', background: B.surface, boxShadow: '0 1px 8px rgba(5,150,105,0.08)' }}>
                      {/* Card header */}
                      <div className="flex items-center justify-between px-5 py-3 border-b" style={{ borderColor: B.border, background: '#F0FDF4' }}>
                        <div className="flex items-center gap-3">
                          <span className="text-sm font-semibold" style={{ color: B.text1 }}>
                            {stepIdx === 0 ? 'Initial Message' : `Follow-up ${stepIdx}`}
                          </span>
                          {stepIdx > 0 && (
                            <div className="flex items-center gap-1.5">
                              <Clock className="w-3.5 h-3.5" style={{ color: B.text3 }} />
                              <span className="text-xs" style={{ color: B.text3 }}>after</span>
                              <input type="number" min={0} value={step.delay_days}
                                     onChange={e => updateStep(stepIdx, { delay_days: Number(e.target.value) })}
                                     className="w-14 px-2 py-1 rounded-md border text-xs text-center"
                                     style={{ borderColor: B.border, background: B.surface, color: B.text1 }} />
                              <span className="text-xs" style={{ color: B.text3 }}>days</span>
                            </div>
                          )}
                          <select value={step.message_type || 'text'}
                                  onChange={e => updateStep(stepIdx, { message_type: e.target.value as MessageType })}
                                  className="text-xs px-2 py-1 rounded-md border"
                                  style={{ borderColor: B.border, background: B.surface, color: B.text1 }}>
                            <option value="text">Text</option>
                            <option value="image">Image</option>
                            <option value="video">Video</option>
                            <option value="document">Document</option>
                            <option value="voice">Voice</option>
                          </select>
                        </div>
                        <div className="flex items-center gap-2">
                          {step.variants.length < 5 && (
                            <button onClick={() => addVariant(stepIdx)}
                                    className="text-xs px-2.5 py-1 rounded-lg border font-medium hover:bg-gray-50 transition-colors"
                                    style={{ borderColor: B.border, color: B.text2 }}>
                              + A/B
                            </button>
                          )}
                          <button onClick={() => setEditingStep(null)}
                                  className="text-xs px-2.5 py-1 rounded-lg border font-medium hover:bg-gray-50 transition-colors"
                                  style={{ borderColor: B.border, color: B.text2 }}>
                            <ChevronDown className="w-3.5 h-3.5 rotate-180 inline mr-0.5" /> Collapse
                          </button>
                          <button onClick={() => removeStep(stepIdx)}
                                  className="p-1.5 rounded-lg hover:bg-red-50 transition-colors">
                            <Trash2 className="w-3.5 h-3.5 text-red-400" />
                          </button>
                        </div>
                      </div>

                      {/* Variants editor */}
                      <div className="p-5 space-y-4">
                        {step.variants.map((variant, varIdx) => (
                          <div key={varIdx} className="space-y-2">
                            {step.variants.length > 1 && (
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                                        style={{ background: varIdx === 0 ? '#DBEAFE' : '#F3E8FF', color: varIdx === 0 ? '#2563EB' : '#9333EA' }}>
                                    Variant {variant.variant_label}
                                  </span>
                                  <input type="number" min={1} max={99} value={variant.weight_percent}
                                         onChange={e => updateVariant(stepIdx, varIdx, { weight_percent: Number(e.target.value) })}
                                         className="w-12 px-1.5 py-0.5 rounded border text-xs text-center"
                                         style={{ borderColor: B.border, background: B.surface, color: B.text1 }} />
                                  <span className="text-xs" style={{ color: B.text3 }}>%</span>
                                </div>
                                <button onClick={() => removeVariant(stepIdx, varIdx)} className="p-0.5 hover:bg-red-50 rounded">
                                  <Trash2 className="w-3 h-3 text-red-400" />
                                </button>
                              </div>
                            )}

                            {/* Media upload for non-text steps */}
                            {(step.message_type || 'text') !== 'text' && (
                              <div className="flex items-center gap-3 p-3 rounded-lg border border-dashed" style={{ borderColor: '#D1D5DB', background: B.bg }}>
                                {variant.media_file_path ? (
                                  <div className="flex items-center gap-2 flex-1 min-w-0">
                                    {step.message_type === 'image' && <Image className="w-4 h-4 text-blue-500 shrink-0" />}
                                    {step.message_type === 'video' && <Video className="w-4 h-4 text-purple-500 shrink-0" />}
                                    {step.message_type === 'document' && <FileText className="w-4 h-4 text-orange-500 shrink-0" />}
                                    {step.message_type === 'voice' && <Mic className="w-4 h-4 text-green-500 shrink-0" />}
                                    <span className="text-xs truncate" style={{ color: B.text2 }}>{variant.media_file_path.split('/').pop()}</span>
                                    <button onClick={() => updateVariant(stepIdx, varIdx, { media_file_path: null })}
                                            className="p-0.5 hover:bg-red-50 rounded shrink-0">
                                      <X className="w-3 h-3 text-red-400" />
                                    </button>
                                  </div>
                                ) : (
                                  <label className="flex items-center gap-2 cursor-pointer flex-1">
                                    <Paperclip className="w-4 h-4" style={{ color: B.text3 }} />
                                    <span className="text-xs" style={{ color: B.text3 }}>
                                      Upload {step.message_type === 'voice' ? 'voice message (.ogg)' : step.message_type}
                                    </span>
                                    <input type="file" className="hidden"
                                           accept={step.message_type === 'image' ? 'image/*' : step.message_type === 'video' ? 'video/*' : step.message_type === 'voice' ? 'audio/ogg,audio/*' : '*/*'}
                                           onChange={async (e) => {
                                             const f = e.target.files?.[0];
                                             if (!f || !campaignId) return;
                                             try {
                                               const res = await telegramOutreachApi.uploadMedia(Number(campaignId), f);
                                               updateVariant(stepIdx, varIdx, { media_file_path: res.file_path });
                                               toast('File uploaded', 'success');
                                             } catch { toast('Upload failed', 'error'); }
                                           }} />
                                  </label>
                                )}
                              </div>
                            )}

                            {/* Formatting toolbar + Variable buttons */}
                            {(step.message_type || 'text') !== 'voice' && (
                              <div className="flex items-center gap-1 rounded-lg border px-2 py-1.5 flex-wrap" style={{ borderColor: B.border, background: B.bg }}>
                                <button onClick={() => insertFormatting(stepIdx, varIdx, 'bold')} title="Bold **text**"
                                        className="p-1.5 rounded hover:bg-gray-200 transition-colors">
                                  <Bold className="w-3.5 h-3.5" style={{ color: B.text2 }} />
                                </button>
                                <button onClick={() => insertFormatting(stepIdx, varIdx, 'italic')} title="Italic __text__"
                                        className="p-1.5 rounded hover:bg-gray-200 transition-colors">
                                  <Italic className="w-3.5 h-3.5" style={{ color: B.text2 }} />
                                </button>
                                <button onClick={() => insertFormatting(stepIdx, varIdx, 'code')} title="Code `text`"
                                        className="p-1.5 rounded hover:bg-gray-200 transition-colors">
                                  <Code2 className="w-3.5 h-3.5" style={{ color: B.text2 }} />
                                </button>
                                <button onClick={() => insertFormatting(stepIdx, varIdx, 'braces')} title="Variable {{name}}"
                                        className="p-1.5 rounded hover:bg-gray-200 transition-colors">
                                  <Braces className="w-3.5 h-3.5" style={{ color: B.text2 }} />
                                </button>
                                <div className="w-px h-4 mx-1" style={{ background: B.border }} />
                                {['first_name', 'company_name', 'username', ...customVars].map(v => (
                                  <button key={v} onClick={() => insertVariable(stepIdx, varIdx, v)}
                                          className="text-[11px] px-1.5 py-0.5 rounded font-mono hover:bg-gray-200 transition-colors"
                                          style={{ color: customVars.includes(v) ? '#4F46E5' : B.text3 }}>
                                    {v}
                                  </button>
                                ))}
                              </div>
                            )}

                            {/* Message textarea with { variable popup */}
                            <div className="relative">
                              <textarea
                                id={`seq-${stepIdx}-${varIdx}`}
                                rows={step.message_type === 'voice' ? 1 : 5}
                                value={variant.message_text}
                                onChange={e => handleSeqChange(e, stepIdx, varIdx)}
                                onKeyDown={e => handleSeqKeyDown(e, stepIdx, varIdx)}
                                placeholder={step.message_type === 'voice' ? 'Voice messages have no text caption' : (step.message_type || 'text') !== 'text' ? 'Caption (optional)... Use {Hi|Hello|Hey} for spintax and {{first_name}} for variables' : 'Type your message... Use {Hi|Hello|Hey} for spintax and {{first_name}} for variables'}
                                className={cn('w-full px-3 py-2.5 rounded-lg border text-sm font-mono leading-relaxed resize-y focus:ring-1 focus:ring-emerald-300 focus:border-emerald-400 outline-none transition-colors', step.message_type === 'voice' && 'hidden')}
                                style={{ borderColor: B.border, background: B.surface, color: B.text1 }}
                              />

                              {/* Preview overlay */}
                              {previewStep?.stepIdx === stepIdx && previewStep?.varIdx === varIdx && (
                                <div className="absolute inset-0 rounded-lg border-2 p-3 text-sm leading-relaxed overflow-auto z-20"
                                     style={{ borderColor: '#059669', background: '#ECFDF5', color: B.text1 }}>
                                  <div className="flex items-center justify-between mb-2">
                                    <span className="text-xs font-semibold" style={{ color: '#059669' }}>Preview</span>
                                    <button onClick={() => setPreviewStep(null)} className="p-0.5 rounded hover:bg-emerald-200">
                                      <X className="w-3 h-3" style={{ color: '#059669' }} />
                                    </button>
                                  </div>
                                  <div className="whitespace-pre-wrap">{previewStep.text}</div>
                                </div>
                              )}

                              {varPopup?.stepIdx === stepIdx && varPopup?.varIdx === varIdx && popupItems.length > 0 && (() => {
                                const sysItems = popupItems.filter(i => i.section === 'system' && i.type === 'var');
                                const spxItem = popupItems.find(i => i.type === 'spintax');
                                const csvItems = popupItems.filter(i => i.section === 'csv');
                                return (
                                  <div ref={varPopupRef}
                                       className="absolute z-50 left-0 w-72 bottom-full mb-1 rounded-lg border shadow-lg overflow-hidden max-h-64 overflow-y-auto"
                                       style={{ borderColor: B.border, background: B.surface }}>
                                    {sysItems.length > 0 && (
                                      <div className="px-3 py-1 text-[10px] uppercase tracking-wider font-semibold" style={{ background: B.bg, color: B.text3 }}>
                                        Variables
                                      </div>
                                    )}
                                    {sysItems.map(item => {
                                      const gi = popupItems.indexOf(item);
                                      return (
                                        <button key={item.name}
                                                onClick={() => selectPopupItem(item)}
                                                onMouseEnter={() => setVarPopup(p => p ? { ...p, selectedIdx: gi } : null)}
                                                className="w-full text-left px-3 py-1.5 text-sm flex items-center gap-2 transition-colors"
                                                style={{
                                                  background: varPopup.selectedIdx === gi ? '#F0FDF4' : 'transparent',
                                                  color: varPopup.selectedIdx === gi ? '#059669' : B.text1,
                                                }}>
                                          <span className="font-mono text-xs opacity-40">{'{{'}</span>
                                          <span>{item.label}</span>
                                          <span className="font-mono text-xs opacity-40">{'}}'}</span>
                                        </button>
                                      );
                                    })}
                                    {spxItem && (() => {
                                      const gi = popupItems.indexOf(spxItem);
                                      return (
                                        <button onClick={() => selectPopupItem(spxItem)}
                                                onMouseEnter={() => setVarPopup(p => p ? { ...p, selectedIdx: gi } : null)}
                                                className="w-full text-left px-3 py-1.5 text-sm flex items-center gap-2 border-t transition-colors"
                                                style={{
                                                  borderColor: B.border,
                                                  background: varPopup.selectedIdx === gi ? '#F0FDF4' : 'transparent',
                                                  color: varPopup.selectedIdx === gi ? '#059669' : B.text1,
                                                }}>
                                          <Type className="w-3.5 h-3.5 opacity-50" />
                                          <span>Random text</span>
                                          <span className="text-xs ml-auto" style={{ color: B.text3 }}>Spintax</span>
                                        </button>
                                      );
                                    })()}
                                    {csvItems.length > 0 && (
                                      <div className="px-3 py-1 text-[10px] uppercase tracking-wider font-semibold border-t"
                                           style={{ borderColor: B.border, background: B.bg, color: B.text3 }}>
                                        CSV Columns
                                      </div>
                                    )}
                                    {csvItems.map(item => {
                                      const gi = popupItems.indexOf(item);
                                      return (
                                        <button key={item.name}
                                                onClick={() => selectPopupItem(item)}
                                                onMouseEnter={() => setVarPopup(p => p ? { ...p, selectedIdx: gi } : null)}
                                                className="w-full text-left px-3 py-1.5 text-sm flex items-center gap-2 transition-colors"
                                                style={{
                                                  background: varPopup.selectedIdx === gi ? '#F0FDF4' : 'transparent',
                                                  color: varPopup.selectedIdx === gi ? '#059669' : B.text1,
                                                }}>
                                          <span className="font-mono text-xs" style={{ color: '#4F46E5' }}>{'{{'}</span>
                                          <span>{item.label}</span>
                                          <span className="font-mono text-xs" style={{ color: '#4F46E5' }}>{'}}'}</span>
                                        </button>
                                      );
                                    })}
                                  </div>
                                );
                              })()}
                            </div>
                          </div>
                        ))}
                      </div>

                      {/* Footer: Preview + Save */}
                      <div className="flex items-center justify-end gap-2 px-5 py-3 border-t" style={{ borderColor: B.border, background: B.bg }}>
                        <button onClick={() => handlePreview(stepIdx, 0)}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border hover:bg-gray-50 transition-colors"
                                style={{ borderColor: B.border, color: B.text2 }}>
                          <Eye className="w-3.5 h-3.5" /> Preview
                        </button>
                        <button onClick={handleSave} disabled={saving}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors hover:opacity-90 disabled:opacity-50"
                                style={{ background: '#059669', color: '#fff' }}>
                          {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                          Save
                        </button>
                      </div>
                    </div>
                  ) : (
                    /* ═══════════ COLLAPSED VIEW CARD ═══════════ */
                    <div className="rounded-xl border cursor-pointer group transition-all hover:shadow-sm"
                         onClick={() => setEditingStep(stepIdx)}
                         style={{ borderColor: B.border, background: B.surface }}>
                      <div className="px-5 py-4">
                        <div className="flex items-center justify-between mb-1.5">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium" style={{ color: B.text1 }}>{typeLabel}</span>
                            {step.message_type !== 'text' && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                                    style={{ background: '#FEF3C7', color: '#B45309' }}>
                                {step.message_type}
                              </span>
                            )}
                            {step.variants.length > 1 && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                                    style={{ background: '#EEF2FF', color: '#4F46E5' }}>
                                {step.variants.length} variants
                              </span>
                            )}
                          </div>
                          <Pencil className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: B.text3 }} />
                        </div>
                        {preview && (
                          <p className="text-sm mb-3 leading-relaxed" style={{ color: B.text2 }}>
                            {preview.length > 120 ? preview.slice(0, 120) + '\u2026' : preview}
                          </p>
                        )}
                        {stats && (stats.sent > 0 || stats.read > 0 || stats.replied > 0) && (
                          <div className="flex items-center gap-4 pt-2.5 border-t" style={{ borderColor: B.border }}>
                            <span className="text-xs" style={{ color: B.text3 }}>
                              Sent <span className="font-semibold" style={{ color: B.text1 }}>{stats.sent}</span>
                            </span>
                            <span className="text-xs" style={{ color: B.text3 }}>
                              Read <span className="font-semibold" style={{ color: B.text1 }}>{stats.read}</span>
                              {stats.sent > 0 && <span className="ml-0.5">({Math.round(stats.read / stats.sent * 100)}%)</span>}
                            </span>
                            <span className="text-xs" style={{ color: B.text3 }}>
                              Replied <span className="font-semibold" style={{ color: '#059669' }}>{stats.replied}</span>
                              {stats.sent > 0 && <span className="ml-0.5">({Math.round(stats.replied / stats.sent * 100)}%)</span>}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════
// Recipients Tab
// ══════════════════════════════════════════════════════════════════════

function RecipientsTab({ campaignId, t, toast, isDark }: TabProps & { campaignId: number }) {
  const [recipients, setRecipients] = useState<TgRecipient[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);

  // Upload states
  const [uploadMode, setUploadMode] = useState<'none' | 'text' | 'csv'>('none');
  const [textInput, setTextInput] = useState('');

  // CRM picker modal
  const [crmOpen, setCrmOpen] = useState(false);
  const [crmContacts, setCrmContacts] = useState<any[]>([]);
  const [crmTotal, setCrmTotal] = useState(0);
  const [crmPage, setCrmPage] = useState(1);
  const [crmSearch, setCrmSearch] = useState('');
  const [crmStatus, setCrmStatus] = useState('');
  const [crmLoading, setCrmLoading] = useState(false);
  const [crmSelected, setCrmSelected] = useState<Set<number>>(new Set());
  const [crmAdding, setCrmAdding] = useState(false);
  const [uploading, setUploading] = useState(false);

  // CSV flow
  const [csvColumns, setCsvColumns] = useState<string[]>([]);
  const [csvPreview, setCsvPreview] = useState<Record<string, string>[]>([]);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  type CsvRole = 'username' | 'phone' | 'first_name' | 'company' | 'custom' | 'skip';
  const [csvColumnRoles, setCsvColumnRoles] = useState<Record<string, CsvRole>>({});
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Cross-campaign duplicate check
  const [crossDupes, setCrossDupes] = useState<{
    duplicates_count: number;
    duplicates: Array<{
      username: string; campaign_id: number; campaign_name: string;
      campaign_status: string; current_step: number; total_steps: number;
      step_label: string; recipient_status: string; campaign_completion_pct: number;
      assigned_account: string | null;
    }>;
  } | null>(null);
  const [removingDupes, setRemovingDupes] = useState<Set<string>>(new Set());

  const loadRecipients = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { page, page_size: 50 };
      if (statusFilter) params.status = statusFilter;
      const data = await telegramOutreachApi.listRecipients(campaignId, params);
      setRecipients(data.items);
      setTotal(data.total);
    } catch {
      toast('Failed to load recipients', 'error');
    } finally {
      setLoading(false);
    }
  }, [campaignId, page, statusFilter, toast]);

  useEffect(() => { loadRecipients(); }, [loadRecipients]);

  const loadCrmContacts = useCallback(async () => {
    setCrmLoading(true);
    try {
      const params: any = { page: crmPage, page_size: 50, exclude_campaign_id: campaignId };
      if (crmSearch) params.search = crmSearch;
      if (crmStatus) params.status = crmStatus;
      const data = await telegramOutreachApi.listCrmContacts(params);
      setCrmContacts(data.items);
      setCrmTotal(data.total);
    } catch {
      toast('Failed to load CRM contacts', 'error');
    } finally {
      setCrmLoading(false);
    }
  }, [campaignId, crmPage, crmSearch, crmStatus, toast]);

  useEffect(() => { if (crmOpen) loadCrmContacts(); }, [crmOpen, loadCrmContacts]);

  const handleAddFromCrm = async () => {
    if (crmSelected.size === 0) return;
    setCrmAdding(true);
    try {
      const res = await telegramOutreachApi.addRecipientsFromCrm(campaignId, Array.from(crmSelected));
      const blMsg = res.blacklisted ? `, ${res.blacklisted} blacklisted` : '';
      const skipMsg = res.skipped ? `, ${res.skipped} duplicates skipped` : '';
      const crossMsg = res.cross_duplicates ? ` (${res.cross_duplicates} already in other campaigns)` : '';
      toast(`${res.added} recipients added${skipMsg}${blMsg}${crossMsg}`, 'success');
      setCrmOpen(false);
      setCrmSelected(new Set());
      loadRecipients();
    } catch {
      toast('Failed to add contacts', 'error');
    } finally {
      setCrmAdding(false);
    }
  };

  const toggleCrmSelect = (id: number) => {
    setCrmSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleCrmSelectAll = () => {
    const pageIds = crmContacts.map(c => c.id);
    const allSelected = pageIds.every(id => crmSelected.has(id));
    setCrmSelected(prev => {
      const next = new Set(prev);
      pageIds.forEach(id => allSelected ? next.delete(id) : next.add(id));
      return next;
    });
  };

  const handleUploadText = async () => {
    if (!textInput.trim()) return;
    setUploading(true);
    try {
      const res = await telegramOutreachApi.uploadRecipientsText(campaignId, textInput);
      const blMsg = res.blacklisted ? `, ${res.blacklisted} blacklisted removed` : '';
      const crossMsg = res.cross_duplicates ? ` (${res.cross_duplicates} already in other campaigns)` : '';
      toast(`${res.added} recipients added (${res.total} total${blMsg})${crossMsg}`, 'success');
      // If cross-campaign duplicates found, fetch details
      if (res.cross_duplicates > 0) {
        const usernames = textInput.trim().split('\n').map((l: string) => l.trim().replace(/^@/, '')).filter(Boolean);
        const dupeRes = await telegramOutreachApi.checkDuplicates(campaignId, usernames);
        if (dupeRes.duplicates_count > 0) setCrossDupes(dupeRes);
      }
      setTextInput('');
      setUploadMode('none');
      loadRecipients();
    } catch {
      toast('Failed to upload recipients', 'error');
    } finally {
      setUploading(false);
    }
  };

  const handleCSVSelect = async (file: File) => {
    setCsvFile(file);
    setUploading(true);
    try {
      const res = await telegramOutreachApi.uploadRecipientsCSV(campaignId, file);
      setCsvColumns(res.columns);
      setCsvPreview(res.preview);
      // Auto-detect column roles
      const roles: Record<string, CsvRole> = {};
      for (const col of res.columns) {
        const lc = col.toLowerCase();
        if (lc.includes('username') || lc.includes('user') || lc === 'nick' || lc === 'nickname' || lc === 'login' || lc === 'handle') {
          if (!Object.values(roles).includes('username')) { roles[col] = 'username'; continue; }
        }
        if (lc.includes('phone') || lc === 'tel' || lc === 'mobile' || lc === 'cell') {
          if (!Object.values(roles).includes('phone')) { roles[col] = 'phone'; continue; }
        }
        if (lc.includes('first') || lc === 'name' || lc === 'fname') {
          if (!Object.values(roles).includes('first_name')) { roles[col] = 'first_name'; continue; }
        }
        if (lc.includes('company') || lc.includes('org') || lc === 'employer') {
          if (!Object.values(roles).includes('company')) { roles[col] = 'company'; continue; }
        }
        roles[col] = 'custom';
      }
      setCsvColumnRoles(roles);
    } catch {
      toast('Failed to parse CSV', 'error');
    } finally {
      setUploading(false);
    }
  };

  const handleCSVImport = async () => {
    const usernameCol = Object.entries(csvColumnRoles).find(([, r]) => r === 'username')?.[0];
    if (!csvFile || !usernameCol) {
      toast('Please assign a Username column', 'error');
      return;
    }
    const phoneCol = Object.entries(csvColumnRoles).find(([, r]) => r === 'phone')?.[0];
    const firstNameCol = Object.entries(csvColumnRoles).find(([, r]) => r === 'first_name')?.[0];
    const companyCol = Object.entries(csvColumnRoles).find(([, r]) => r === 'company')?.[0];
    const customCols: Record<string, string> = {};
    Object.entries(csvColumnRoles).forEach(([col, role]) => {
      if (role === 'custom') customCols[col] = col.toLowerCase().replace(/\s+/g, '_');
    });
    setUploading(true);
    try {
      const res = await telegramOutreachApi.mapColumnsCSV(campaignId, csvFile, {
        username_column: usernameCol,
        phone_column: phoneCol || undefined,
        first_name_column: firstNameCol || undefined,
        company_name_column: companyCol || undefined,
        custom_columns: customCols,
      });
      const blMsg = res.blacklisted ? `, ${res.blacklisted} blacklisted removed` : '';
      const crossMsg = res.cross_duplicates ? ` (${res.cross_duplicates} already in other campaigns)` : '';
      toast(`${res.added} recipients imported${blMsg}${crossMsg}`, 'success');
      // If cross-campaign duplicates, fetch details for the preview rows
      if (res.cross_duplicates > 0) {
        const usernames = csvPreview.map(r => (r[usernameCol!] || '').replace(/^@/, '')).filter(Boolean);
        // Re-read CSV for full usernames list would be complex; use the count warning
        // The check-duplicates endpoint is also available for a dedicated pre-import check
        try {
          const dupeRes = await telegramOutreachApi.checkDuplicates(campaignId, usernames);
          if (dupeRes.duplicates_count > 0) setCrossDupes(dupeRes);
        } catch { /* best effort */ }
      }
      setCsvColumns([]);
      setCsvPreview([]);
      setCsvFile(null);
      setCsvColumnRoles({});
      setUploadMode('none');
      loadRecipients();
    } catch {
      toast('Failed to import CSV', 'error');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (recipientId: number) => {
    try {
      await telegramOutreachApi.deleteRecipient(campaignId, recipientId);
      loadRecipients();
    } catch {
      toast('Failed to delete recipient', 'error');
    }
  };

  const totalPages = Math.ceil(total / 50);

  const RECIPIENT_STATUS_COLORS: Record<string, string> = {
    pending: 'bg-gray-100 text-gray-700 dark:bg-gray-700/30 dark:text-gray-400',
    in_sequence: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    replied: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    completed: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    failed: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    bounced: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
  };

  return (
    <div className="max-w-5xl space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3 flex-wrap">
        <select value={statusFilter}
                onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
                className={cn('px-3 py-2 rounded-lg border text-sm', 'border-gray-200 dark:border-gray-700', 'bg-white dark:bg-gray-900', t.text1)}>
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="in_sequence">In Sequence</option>
          <option value="replied">Replied</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
          <option value="bounced">Bounced</option>
        </select>

        <span className={cn('text-sm', t.text3)}>{total} recipients</span>

        <div className="ml-auto flex items-center gap-2">
          <button onClick={() => setUploadMode('text')}
                  className={cn('flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm hover:bg-gray-50 dark:hover:bg-gray-800', 'border-gray-200 dark:border-gray-700', t.text2)}>
            <Type className="w-3.5 h-3.5" /> Paste Text
          </button>
          <button onClick={() => setUploadMode('csv')}
                  className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">
            <Upload className="w-3.5 h-3.5" /> Upload CSV
          </button>
          <button onClick={() => { setCrmOpen(true); setCrmPage(1); setCrmSearch(''); setCrmStatus(''); setCrmSelected(new Set()); }}
                  className={cn('flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm hover:bg-gray-50 dark:hover:bg-gray-800', 'border-gray-200 dark:border-gray-700', t.text2)}>
            <UserPlus className="w-3.5 h-3.5" /> Add from CRM
          </button>
          <input ref={fileInputRef} type="file" accept=".csv,.txt" className="hidden"
                 onChange={e => {
                   const file = e.target.files?.[0];
                   if (file) { setUploadMode('csv'); handleCSVSelect(file); }
                   e.target.value = '';
                 }} />
        </div>
      </div>

      {/* Cross-campaign duplicates warning */}
      {crossDupes && crossDupes.duplicates_count > 0 && (
        <div className="rounded-lg border border-amber-300 dark:border-amber-600 bg-amber-50 dark:bg-amber-900/20 p-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-medium text-amber-800 dark:text-amber-300">
                  {crossDupes.duplicates_count} lead{crossDupes.duplicates_count !== 1 ? 's' : ''} already in other campaigns
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setCrossDupes(null)}
                    className="px-2.5 py-1 text-xs font-medium rounded bg-amber-200 dark:bg-amber-800 text-amber-800 dark:text-amber-200 hover:bg-amber-300 dark:hover:bg-amber-700"
                  >
                    Keep All
                  </button>
                  <button
                    onClick={async () => {
                      const uniqueUsernames = [...new Set(crossDupes.duplicates.map(d => d.username))];
                      setRemovingDupes(new Set(uniqueUsernames.map(u => u.toLowerCase())));
                      try {
                        const res = await telegramOutreachApi.bulkRemoveRecipients(campaignId, uniqueUsernames);
                        toast(`Removed ${res.removed} duplicate lead${res.removed !== 1 ? 's' : ''}`, 'success');
                        setCrossDupes(null);
                        setRemovingDupes(new Set());
                        loadRecipients();
                      } catch { toast('Failed to remove duplicates', 'error'); setRemovingDupes(new Set()); }
                    }}
                    className="px-2.5 py-1 text-xs font-medium rounded bg-red-100 dark:bg-red-900/40 text-red-700 dark:text-red-300 hover:bg-red-200 dark:hover:bg-red-800"
                  >
                    Remove All
                  </button>
                </div>
              </div>
              <div className="mt-1 max-h-64 overflow-y-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-amber-700 dark:text-amber-400 border-b border-amber-200 dark:border-amber-700">
                      <th className="pb-1 pr-3">Username</th>
                      <th className="pb-1 pr-3">Campaign</th>
                      <th className="pb-1 pr-3">Progress</th>
                      <th className="pb-1 pr-3">Step</th>
                      <th className="pb-1 pr-3">Status</th>
                      <th className="pb-1">Action</th>
                    </tr>
                  </thead>
                  <tbody className="text-amber-800 dark:text-amber-300">
                    {crossDupes.duplicates.map((d, i) => (
                      <tr key={i} className={cn(
                        'border-b border-amber-100 dark:border-amber-800/50',
                        removingDupes.has(d.username.toLowerCase()) && 'opacity-50'
                      )}>
                        <td className="py-1.5 pr-3 font-mono">@{d.username}</td>
                        <td className="py-1.5 pr-3">
                          <span>{d.campaign_name}</span>
                          <span className="ml-1 text-[10px] text-amber-500">({d.campaign_status})</span>
                        </td>
                        <td className="py-1.5 pr-3">
                          <div className="flex items-center gap-1.5">
                            <div className="w-12 h-1.5 rounded-full bg-amber-200 dark:bg-amber-800 overflow-hidden">
                              <div className="h-full rounded-full bg-amber-500" style={{ width: `${d.campaign_completion_pct}%` }} />
                            </div>
                            <span className="text-[10px]">{d.campaign_completion_pct}%</span>
                          </div>
                        </td>
                        <td className="py-1.5 pr-3 whitespace-nowrap">{d.step_label}</td>
                        <td className="py-1.5 pr-3">
                          <span className={cn('px-1.5 py-0.5 rounded text-[10px] font-medium',
                            d.recipient_status === 'replied' ? 'bg-green-100 dark:bg-green-900/40 text-green-700 dark:text-green-300' :
                            d.recipient_status === 'completed' ? 'bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300' :
                            d.recipient_status === 'in_sequence' ? 'bg-purple-100 dark:bg-purple-900/40 text-purple-700 dark:text-purple-300' :
                            'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400'
                          )}>{d.recipient_status}</span>
                        </td>
                        <td className="py-1.5">
                          <button
                            disabled={removingDupes.has(d.username.toLowerCase())}
                            onClick={async () => {
                              setRemovingDupes(prev => new Set([...prev, d.username.toLowerCase()]));
                              try {
                                await telegramOutreachApi.bulkRemoveRecipients(campaignId, [d.username]);
                                setCrossDupes(prev => {
                                  if (!prev) return null;
                                  const remaining = prev.duplicates.filter(x => x.username.toLowerCase() !== d.username.toLowerCase());
                                  if (remaining.length === 0) return null;
                                  return { ...prev, duplicates: remaining, duplicates_count: new Set(remaining.map(r => r.username.toLowerCase())).size };
                                });
                                setRemovingDupes(prev => { const n = new Set(prev); n.delete(d.username.toLowerCase()); return n; });
                                loadRecipients();
                                toast(`Removed @${d.username}`, 'success');
                              } catch { toast('Failed to remove', 'error'); setRemovingDupes(prev => { const n = new Set(prev); n.delete(d.username.toLowerCase()); return n; }); }
                            }}
                            className="px-2 py-0.5 text-[10px] font-medium rounded bg-red-100 dark:bg-red-900/40 text-red-600 dark:text-red-400 hover:bg-red-200 dark:hover:bg-red-800 disabled:opacity-50"
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-xs text-amber-600 dark:text-amber-400">
                These leads are already in other campaigns. Remove to avoid duplicate outreach, or keep to send anyway.
              </p>
            </div>
            <button onClick={() => setCrossDupes(null)} className="text-amber-500 hover:text-amber-700 dark:hover:text-amber-300">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Upload text panel */}
      {uploadMode === 'text' && (
        <div className={cn('rounded-lg border p-4 space-y-3', 'border-gray-200 dark:border-gray-700')}>
          <h4 className={cn('text-sm font-medium', t.text1)}>Paste usernames (one per line)</h4>
          <textarea rows={6} value={textInput}
                    onChange={e => setTextInput(e.target.value)}
                    placeholder="@username1&#10;@username2&#10;username3"
                    className={cn('w-full px-3 py-2 rounded-lg border text-sm font-mono', 'border-gray-200 dark:border-gray-700', 'bg-white dark:bg-gray-900', t.text1)} />
          <div className="flex items-center gap-2">
            <button onClick={handleUploadText} disabled={uploading || !textInput.trim()}
                    className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
              {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Add Recipients'}
            </button>
            <button onClick={() => { setUploadMode('none'); setTextInput(''); }}
                    className={cn('px-4 py-2 rounded-lg border text-sm', 'border-gray-200 dark:border-gray-700', t.text2)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* CSV upload panel */}
      {uploadMode === 'csv' && (
        <div className={cn('rounded-lg border p-4 space-y-4', 'border-gray-200 dark:border-gray-700')}>
          {/* Drag-and-drop zone (shown when no file loaded yet) */}
          {csvColumns.length === 0 && (
            <>
              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={e => {
                  e.preventDefault(); setDragOver(false);
                  const file = e.dataTransfer.files[0];
                  if (file && (file.name.endsWith('.csv') || file.name.endsWith('.txt'))) {
                    handleCSVSelect(file);
                  } else {
                    toast('Please drop a .csv or .txt file', 'error');
                  }
                }}
                className={cn(
                  'border-2 border-dashed rounded-xl p-10 text-center transition-colors cursor-pointer',
                  dragOver
                    ? 'border-indigo-400 bg-indigo-50 dark:bg-indigo-900/20'
                    : 'border-gray-300 dark:border-gray-600 hover:border-indigo-300 dark:hover:border-indigo-700',
                )}
                onClick={() => fileInputRef.current?.click()}
              >
                {uploading ? (
                  <div className="flex flex-col items-center gap-2">
                    <Loader2 className={cn('w-8 h-8 animate-spin', 'text-indigo-500')} />
                    <p className={cn('text-sm font-medium', t.text2)}>Parsing CSV...</p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <Upload className={cn('w-8 h-8', dragOver ? 'text-indigo-500' : t.text3)} />
                    <p className={cn('text-sm font-medium', t.text1)}>
                      Drop your CSV file here
                    </p>
                    <p className={cn('text-xs', t.text3)}>
                      or <span className="text-indigo-600 dark:text-indigo-400 underline">browse files</span> — .csv, .txt
                    </p>
                  </div>
                )}
              </div>
              <div className="flex justify-end">
                <button onClick={() => { setUploadMode('none'); setCsvFile(null); }}
                        className={cn('px-4 py-2 rounded-lg border text-sm', 'border-gray-200 dark:border-gray-700', t.text2)}>
                  Cancel
                </button>
              </div>
            </>
          )}

          {/* Column mapping + preview (shown after file parsed) */}
          {csvColumns.length > 0 && (() => {
            const roleLabels: Record<CsvRole, string> = {
              username: 'Username', phone: 'Phone', first_name: 'First Name',
              company: 'Company', custom: 'Custom Variable', skip: 'Skip',
            };
            const hasUsername = Object.values(csvColumnRoles).includes('username');
            const usernameCol = Object.entries(csvColumnRoles).find(([, r]) => r === 'username')?.[0];
            const phoneCol = Object.entries(csvColumnRoles).find(([, r]) => r === 'phone')?.[0];

            // Validation helpers
            const isValidUsername = (val: string) => {
              const v = val.trim().replace(/^@/, '');
              return v.length >= 3 && v.length <= 32 && /^[a-zA-Z0-9_]+$/.test(v);
            };
            const isValidPhone = (val: string) => {
              const v = val.trim().replace(/[\s\-\(\)\+]/g, '');
              return v.length >= 7 && v.length <= 15 && /^\d+$/.test(v);
            };

            // Count valid/invalid for summary
            const usernameValues = usernameCol ? csvPreview.map(r => r[usernameCol] || '') : [];
            const invalidUsernames = usernameValues.filter(v => v && !isValidUsername(v)).length;
            const phoneValues = phoneCol ? csvPreview.map(r => r[phoneCol] || '') : [];
            const invalidPhones = phoneValues.filter(v => v && !isValidPhone(v)).length;

            const customVarCols = Object.entries(csvColumnRoles).filter(([, r]) => r === 'custom');

            return (
              <>
                <div className="flex items-center justify-between">
                  <h4 className={cn('text-sm font-medium', t.text1)}>
                    Map Columns — {csvFile?.name}
                  </h4>
                  <button onClick={() => { setCsvColumns([]); setCsvPreview([]); setCsvFile(null); setCsvColumnRoles({}); }}
                          className={cn('text-xs px-2 py-1 rounded border flex items-center gap-1', 'border-gray-200 dark:border-gray-700', t.text3)}>
                    <X className="w-3 h-3" /> Change file
                  </button>
                </div>

                {/* Per-column role dropdowns */}
                <div className={cn('rounded-lg border overflow-hidden', 'border-gray-200 dark:border-gray-700')}>
                  <table className="w-full text-sm">
                    <thead className={cn('border-b', 'border-gray-200 dark:border-gray-700', isDark ? 'bg-gray-800/50' : 'bg-gray-50')}>
                      <tr>
                        <th className={cn('text-left px-3 py-2 font-medium text-xs', t.text3)}>CSV Column</th>
                        <th className={cn('text-left px-3 py-2 font-medium text-xs', t.text3)}>Maps To</th>
                        <th className={cn('text-left px-3 py-2 font-medium text-xs', t.text3)}>Sample Values</th>
                      </tr>
                    </thead>
                    <tbody>
                      {csvColumns.map(col => {
                        const role = csvColumnRoles[col] || 'skip';
                        const samples = csvPreview.slice(0, 3).map(r => r[col] || '').filter(Boolean).join(', ');
                        return (
                          <tr key={col} className={cn('border-b', 'border-gray-200 dark:border-gray-700',
                            role === 'skip' ? 'opacity-50' : '')}>
                            <td className={cn('px-3 py-2 font-medium text-xs', t.text1)}>{col}</td>
                            <td className="px-3 py-2">
                              <select
                                value={role}
                                onChange={e => {
                                  const newRole = e.target.value as CsvRole;
                                  setCsvColumnRoles(prev => {
                                    const updated = { ...prev };
                                    // Ensure unique for singleton roles
                                    if (['username', 'phone', 'first_name', 'company'].includes(newRole)) {
                                      Object.keys(updated).forEach(k => {
                                        if (updated[k] === newRole) updated[k] = 'custom';
                                      });
                                    }
                                    updated[col] = newRole;
                                    return updated;
                                  });
                                }}
                                className={cn('px-2 py-1.5 rounded-lg border text-xs', 'border-gray-200 dark:border-gray-700',
                                  'bg-white dark:bg-gray-900', t.text1,
                                  role === 'username' ? 'ring-1 ring-indigo-400' : '')}
                              >
                                {Object.entries(roleLabels).map(([val, label]) => (
                                  <option key={val} value={val}>{label}</option>
                                ))}
                              </select>
                            </td>
                            <td className={cn('px-3 py-2 text-xs truncate max-w-[200px]', t.text3)}>{samples}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {!hasUsername && (
                  <p className="text-xs text-red-500 font-medium">Please assign one column as Username (required)</p>
                )}

                {/* Custom variable summary */}
                {customVarCols.length > 0 && (
                  <p className={cn('text-xs', t.text3)}>
                    Custom variables: {customVarCols.map(([col]) => `{{${col.toLowerCase().replace(/\s+/g, '_')}}}`).join(', ')}
                  </p>
                )}

                {/* Preview with validation */}
                {csvPreview.length > 0 && (
                  <div>
                    <h5 className={cn('text-xs font-medium mb-1.5', t.text2)}>
                      Preview (first {csvPreview.length} rows)
                      {(invalidUsernames > 0 || invalidPhones > 0) && (
                        <span className="text-red-500 ml-2 font-normal">
                          {invalidUsernames > 0 && `${invalidUsernames} invalid username(s)`}
                          {invalidUsernames > 0 && invalidPhones > 0 && ', '}
                          {invalidPhones > 0 && `${invalidPhones} invalid phone(s)`}
                        </span>
                      )}
                    </h5>
                    <div className={cn('rounded-lg border overflow-auto max-h-52', 'border-gray-200 dark:border-gray-700')}>
                      <table className="w-full text-xs">
                        <thead className={cn('border-b sticky top-0', 'border-gray-200 dark:border-gray-700', isDark ? 'bg-gray-800/50' : 'bg-gray-50')}>
                          <tr>
                            {csvColumns.filter(c => csvColumnRoles[c] !== 'skip').map(c => (
                              <th key={c} className={cn('text-left px-2 py-1.5 font-medium whitespace-nowrap', t.text3)}>
                                {c}
                                {csvColumnRoles[c] && csvColumnRoles[c] !== 'custom' && (
                                  <span className="ml-1 text-indigo-500 font-normal">({roleLabels[csvColumnRoles[c]]})</span>
                                )}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {csvPreview.map((row, i) => (
                            <tr key={i} className={cn('border-b', 'border-gray-200 dark:border-gray-700')}>
                              {csvColumns.filter(c => csvColumnRoles[c] !== 'skip').map(c => {
                                const val = row[c] || '';
                                const role = csvColumnRoles[c];
                                let cellClass = t.text1;
                                if (role === 'username' && val && !isValidUsername(val)) {
                                  cellClass = 'text-red-600 bg-red-50 dark:bg-red-900/20';
                                } else if (role === 'phone' && val && !isValidPhone(val)) {
                                  cellClass = 'text-red-600 bg-red-50 dark:bg-red-900/20';
                                }
                                return (
                                  <td key={c} className={cn('px-2 py-1.5', cellClass)}>{val}</td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <button onClick={handleCSVImport} disabled={uploading || !hasUsername}
                          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
                    {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Import Recipients'}
                  </button>
                  <button onClick={() => { setUploadMode('none'); setCsvColumns([]); setCsvPreview([]); setCsvFile(null); setCsvColumnRoles({}); }}
                          className={cn('px-4 py-2 rounded-lg border text-sm', 'border-gray-200 dark:border-gray-700', t.text2)}>
                    Cancel
                  </button>
                </div>
              </>
            );
          })()}
        </div>
      )}

      {/* Recipients Table */}
      <div className={cn('rounded-lg border overflow-hidden', 'border-gray-200 dark:border-gray-700')}>
        <table className="w-full text-sm">
          <thead className={cn('border-b', 'border-gray-200 dark:border-gray-700', isDark ? 'bg-gray-800/50' : 'bg-gray-50')}>
            <tr>
              <th className={cn('text-left px-3 py-2.5 font-medium', t.text3)}>Username</th>
              <th className={cn('text-left px-3 py-2.5 font-medium', t.text3)}>First Name</th>
              <th className={cn('text-left px-3 py-2.5 font-medium', t.text3)}>Company</th>
              <th className={cn('text-left px-3 py-2.5 font-medium', t.text3)}>Status</th>
              <th className={cn('text-left px-3 py-2.5 font-medium', t.text3)}>Step</th>
              <th className={cn('text-left px-3 py-2.5 font-medium', t.text3)}>Last Sent</th>
              <th className="w-10 px-3 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="text-center py-12">
                  <Loader2 className={cn('w-6 h-6 animate-spin mx-auto', t.text3)} />
                </td>
              </tr>
            ) : recipients.length === 0 ? (
              <tr>
                <td colSpan={7} className={cn('text-center py-12', t.text3)}>
                  No recipients yet. Upload usernames or a CSV file.
                </td>
              </tr>
            ) : recipients.map(r => (
              <tr key={r.id} className={cn('border-b', 'border-gray-200 dark:border-gray-700')}>
                <td className={cn('px-3 py-2 text-xs', t.text1)}>@{r.username}</td>
                <td className={cn('px-3 py-2', t.text1)}>{r.first_name || <span className={t.text3}>--</span>}</td>
                <td className={cn('px-3 py-2', t.text1)}>{r.company_name || <span className={t.text3}>--</span>}</td>
                <td className="px-3 py-2">
                  <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium',
                    RECIPIENT_STATUS_COLORS[r.status] || 'bg-gray-100 text-gray-600')}>
                    {r.status.replace('_', ' ')}
                  </span>
                </td>
                <td className={cn('px-3 py-2 text-xs', t.text3)}>{r.current_step || '--'}</td>
                <td className={cn('px-3 py-2 text-xs', t.text3)}>
                  {r.last_message_sent_at ? new Date(r.last_message_sent_at).toLocaleString() : '--'}
                </td>
                <td className="px-3 py-2">
                  <button onClick={() => handleDelete(r.id)}
                          className="p-1 hover:bg-red-50 dark:hover:bg-red-900/20 rounded">
                    <Trash2 className="w-3.5 h-3.5 text-red-400" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className={cn('text-sm', t.text3)}>{total} total</span>
          <div className="flex items-center gap-2">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
                    className={cn('px-3 py-1.5 rounded border text-sm', 'border-gray-200 dark:border-gray-700', page <= 1 && 'opacity-50')}>
              Prev
            </button>
            <span className={cn('text-sm', t.text1)}>Page {page} of {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
                    className={cn('px-3 py-1.5 rounded border text-sm', 'border-gray-200 dark:border-gray-700', page >= totalPages && 'opacity-50')}>
              Next
            </button>
          </div>
        </div>
      )}

      {/* ── CRM Picker Modal ──────────────────────────────────────── */}
      {crmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setCrmOpen(false)}>
          <div className={cn('w-[900px] max-h-[80vh] rounded-xl shadow-2xl flex flex-col', isDark ? 'bg-gray-900 border border-gray-700' : 'bg-white border border-gray-200')}
               onClick={e => e.stopPropagation()}>
            {/* Header */}
            <div className={cn('flex items-center justify-between px-5 py-4 border-b', 'border-gray-200 dark:border-gray-700')}>
              <div>
                <h3 className={cn('text-base font-semibold', t.text1)}>Add from CRM</h3>
                <p className={cn('text-xs mt-0.5', t.text3)}>
                  {crmSelected.size > 0 ? `${crmSelected.size} selected` : `${crmTotal} contacts available`}
                </p>
              </div>
              <button onClick={() => setCrmOpen(false)} className={cn('p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800', t.text3)}>
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Filters */}
            <div className={cn('flex items-center gap-3 px-5 py-3 border-b', 'border-gray-200 dark:border-gray-700')}>
              <div className="relative flex-1 max-w-xs">
                <Search className={cn('absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5', t.text3)} />
                <input value={crmSearch}
                       onChange={e => { setCrmSearch(e.target.value); setCrmPage(1); }}
                       placeholder="Search username, name, company..."
                       className={cn('w-full pl-8 pr-3 py-2 rounded-lg border text-sm', 'border-gray-200 dark:border-gray-700', 'bg-white dark:bg-gray-900', t.text1)} />
              </div>
              <select value={crmStatus}
                      onChange={e => { setCrmStatus(e.target.value); setCrmPage(1); }}
                      className={cn('px-3 py-2 rounded-lg border text-sm', 'border-gray-200 dark:border-gray-700', 'bg-white dark:bg-gray-900', t.text1)}>
                <option value="">All statuses</option>
                {['cold', 'contacted', 'replied', 'interested', 'qualified', 'meeting_set', 'converted', 'not_interested'].map(s => (
                  <option key={s} value={s}>{s.replace('_', ' ')}</option>
                ))}
              </select>
            </div>

            {/* Table */}
            <div className="flex-1 overflow-auto">
              <table className="w-full text-sm">
                <thead className={cn('border-b sticky top-0', 'border-gray-200 dark:border-gray-700', isDark ? 'bg-gray-800/90' : 'bg-gray-50')}>
                  <tr>
                    <th className="w-10 px-3 py-2.5">
                      <input type="checkbox"
                             checked={crmContacts.length > 0 && crmContacts.every(c => crmSelected.has(c.id))}
                             onChange={toggleCrmSelectAll}
                             className="rounded border-gray-300" />
                    </th>
                    <th className={cn('text-left px-3 py-2.5 font-medium', t.text3)}>Username</th>
                    <th className={cn('text-left px-3 py-2.5 font-medium', t.text3)}>Name</th>
                    <th className={cn('text-left px-3 py-2.5 font-medium', t.text3)}>Company</th>
                    <th className={cn('text-left px-3 py-2.5 font-medium', t.text3)}>Status</th>
                    <th className={cn('text-left px-3 py-2.5 font-medium', t.text3)}>Sent</th>
                    <th className={cn('text-left px-3 py-2.5 font-medium', t.text3)}>Replies</th>
                  </tr>
                </thead>
                <tbody>
                  {crmLoading ? (
                    <tr><td colSpan={7} className="text-center py-12"><Loader2 className={cn('w-5 h-5 animate-spin mx-auto', t.text3)} /></td></tr>
                  ) : crmContacts.length === 0 ? (
                    <tr><td colSpan={7} className={cn('text-center py-12', t.text3)}>No contacts found</td></tr>
                  ) : crmContacts.map(c => (
                    <tr key={c.id}
                        onClick={() => toggleCrmSelect(c.id)}
                        className={cn('border-b cursor-pointer transition-colors', 'border-gray-200 dark:border-gray-700',
                          crmSelected.has(c.id)
                            ? 'bg-indigo-50/60 dark:bg-indigo-900/20'
                            : 'hover:bg-gray-50 dark:hover:bg-gray-800/50')}>
                      <td className="px-3 py-2">
                        <input type="checkbox" checked={crmSelected.has(c.id)} onChange={() => toggleCrmSelect(c.id)}
                               className="rounded border-gray-300" />
                      </td>
                      <td className={cn('px-3 py-2 font-mono text-xs', t.text1)}>@{c.username}</td>
                      <td className={cn('px-3 py-2', t.text1)}>{[c.first_name, c.last_name].filter(Boolean).join(' ') || <span className={t.text3}>--</span>}</td>
                      <td className={cn('px-3 py-2', t.text1)}>{c.company_name || <span className={t.text3}>--</span>}</td>
                      <td className="px-3 py-2">
                        <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium',
                          c.status === 'replied' || c.status === 'interested' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                          c.status === 'qualified' || c.status === 'meeting_set' || c.status === 'converted' ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' :
                          c.status === 'not_interested' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                          c.status === 'contacted' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                          'bg-gray-100 text-gray-700 dark:bg-gray-700/30 dark:text-gray-400')}>
                          {c.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className={cn('px-3 py-2 text-xs tabular-nums', t.text3)}>{c.total_messages_sent || 0}</td>
                      <td className={cn('px-3 py-2 text-xs tabular-nums', t.text3)}>{c.total_replies_received || 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Footer */}
            <div className={cn('flex items-center justify-between px-5 py-3 border-t', 'border-gray-200 dark:border-gray-700')}>
              <div className="flex items-center gap-3">
                {Math.ceil(crmTotal / 50) > 1 && (
                  <>
                    <button disabled={crmPage <= 1} onClick={() => setCrmPage(p => p - 1)}
                            className={cn('px-2.5 py-1 rounded border text-xs', 'border-gray-200 dark:border-gray-700', crmPage <= 1 && 'opacity-50')}>
                      Prev
                    </button>
                    <span className={cn('text-xs', t.text3)}>Page {crmPage} of {Math.ceil(crmTotal / 50)}</span>
                    <button disabled={crmPage >= Math.ceil(crmTotal / 50)} onClick={() => setCrmPage(p => p + 1)}
                            className={cn('px-2.5 py-1 rounded border text-xs', 'border-gray-200 dark:border-gray-700', crmPage >= Math.ceil(crmTotal / 50) && 'opacity-50')}>
                      Next
                    </button>
                  </>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => setCrmOpen(false)}
                        className={cn('px-4 py-2 rounded-lg border text-sm', 'border-gray-200 dark:border-gray-700', t.text2)}>
                  Cancel
                </button>
                <button onClick={handleAddFromCrm}
                        disabled={crmAdding || crmSelected.size === 0}
                        className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
                  {crmAdding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                  Add {crmSelected.size > 0 ? `${crmSelected.size} Selected` : 'Selected'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════
// Preview & Stats Tab
// ══════════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════════
// Analytics Tab
// ══════════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════════
// Timeline Tab
// ══════════════════════════════════════════════════════════════════════

type TimelineData = Awaited<ReturnType<typeof telegramOutreachApi.getCampaignTimeline>>;

const TIMELINE_STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  replied: { bg: '#DCFCE7', text: '#166534', label: 'Replied' },
  read: { bg: '#DBEAFE', text: '#1E40AF', label: 'Read' },
  sent: { bg: '#F3F4F6', text: '#374151', label: 'Sent' },
  scheduled: { bg: '#FEF9C3', text: '#854D0E', label: 'Scheduled' },
  failed: { bg: '#FEE2E2', text: '#991B1B', label: 'Failed' },
  spamblocked: { bg: '#FEE2E2', text: '#991B1B', label: 'Spamblock' },
  pending: { bg: '#F9FAFB', text: '#9CA3AF', label: '—' },
};

function formatTimelineDate(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ', ' +
         d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function TimelineTab({ campaignId, t: _t, toast }: TabProps & { campaignId: number }) { void _t;
  const [data, setData] = useState<TimelineData | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [sortBy, setSortBy] = useState('username');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const PAGE_SIZE = 50;

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const result = await telegramOutreachApi.getCampaignTimeline(campaignId, {
        page, page_size: PAGE_SIZE, search: search || undefined, sort_by: sortBy, sort_dir: sortDir,
      });
      setData(result);
    } catch (e: any) {
      toast(e?.response?.data?.detail || 'Failed to load timeline', 'error');
    } finally {
      setLoading(false);
    }
  }, [campaignId, page, search, sortBy, sortDir, toast]);

  useEffect(() => { loadData(); }, [loadData]);

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => { setSearch(searchInput); setPage(1); }, 400);
    return () => clearTimeout(timer);
  }, [searchInput]);

  const toggleSort = (col: string) => {
    if (sortBy === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(col); setSortDir('asc'); }
    setPage(1);
  };

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold" style={{ color: B.text1 }}>Campaign Timeline</h2>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2" style={{ color: B.text3 }} />
            <input
              value={searchInput}
              onChange={e => setSearchInput(e.target.value)}
              placeholder="Search username..."
              className="pl-9 pr-3 py-1.5 border rounded-lg text-sm w-56"
              style={{ borderColor: B.border, background: B.surface, color: B.text1 }}
            />
          </div>
          <button onClick={loadData}
                  className="p-1.5 rounded-lg hover:bg-gray-100" style={{ color: B.text2 }}>
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="border rounded-lg overflow-x-auto" style={{ borderColor: B.border, background: B.surface }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ borderBottom: `1px solid ${B.border}`, background: B.bg }}>
              <th className="px-3 py-2.5 text-left font-medium cursor-pointer select-none whitespace-nowrap"
                  style={{ color: B.text2, minWidth: 140 }}
                  onClick={() => toggleSort('username')}>
                Lead {sortBy === 'username' && (sortDir === 'asc' ? '↑' : '↓')}
              </th>
              <th className="px-3 py-2.5 text-left font-medium whitespace-nowrap"
                  style={{ color: B.text2, minWidth: 120 }}>
                Account
              </th>
              <th className="px-3 py-2.5 text-left font-medium cursor-pointer select-none whitespace-nowrap"
                  style={{ color: B.text2, minWidth: 80 }}
                  onClick={() => toggleSort('status')}>
                Status {sortBy === 'status' && (sortDir === 'asc' ? '↑' : '↓')}
              </th>
              {data?.steps.map(step => (
                <th key={step.step_order}
                    className="px-3 py-2.5 text-center font-medium whitespace-nowrap"
                    style={{ color: B.text2, minWidth: 110 }}>
                  {step.step_order === 1 ? 'Initial' : `Follow-up ${step.step_order - 1}`}
                  {step.delay_days > 0 && <span className="text-xs font-normal ml-1" style={{ color: B.text3 }}>+{step.delay_days}d</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && !data && (
              <tr><td colSpan={99} className="py-12 text-center">
                <Loader2 className="w-5 h-5 animate-spin mx-auto" style={{ color: B.text3 }} />
              </td></tr>
            )}
            {data && data.recipients.length === 0 && (
              <tr><td colSpan={3 + data.steps.length} className="py-12 text-center" style={{ color: B.text3 }}>
                {search ? 'No recipients match your search' : 'No recipients yet'}
              </td></tr>
            )}
            {data?.recipients.map(r => (
              <tr key={r.id} style={{ borderBottom: `1px solid ${B.border}` }}
                  className="hover:bg-gray-50/50">
                <td className="px-3 py-2" style={{ color: B.text1 }}>
                  <div className="font-medium">@{r.username}</div>
                  {r.first_name && <div className="text-xs" style={{ color: B.text3 }}>{r.first_name}</div>}
                </td>
                <td className="px-3 py-2 text-xs" style={{ color: B.text2 }}>
                  {r.assigned_account_phone || '—'}
                </td>
                <td className="px-3 py-2">
                  <span className="px-2 py-0.5 rounded text-xs font-medium"
                        style={{
                          background: TIMELINE_STATUS_STYLES[r.status]?.bg || '#F3F4F6',
                          color: TIMELINE_STATUS_STYLES[r.status]?.text || '#374151',
                        }}>
                    {r.status}
                  </span>
                </td>
                {data.steps.map(step => {
                  const cell = r.steps[String(step.step_order)];
                  if (!cell) return <td key={step.step_order} className="px-3 py-2 text-center text-xs" style={{ color: B.text3 }}>—</td>;
                  const style = TIMELINE_STATUS_STYLES[cell.status] || TIMELINE_STATUS_STYLES.pending;
                  return (
                    <td key={step.step_order} className="px-3 py-2 text-center group relative">
                      <span className="px-2 py-0.5 rounded text-xs font-medium inline-block"
                            style={{ background: style.bg, color: style.text }}>
                        {style.label}
                      </span>
                      {/* Tooltip */}
                      {cell.status !== 'pending' && (
                        <div className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-1 hidden group-hover:block">
                          <div className="bg-gray-900 text-white text-xs rounded-lg px-3 py-2 whitespace-nowrap shadow-lg">
                            {cell.status === 'scheduled' && cell.sent_at && <div>Scheduled: {formatTimelineDate(cell.sent_at)}</div>}
                            {cell.status !== 'scheduled' && cell.sent_at && <div>Sent: {formatTimelineDate(cell.sent_at)}</div>}
                            {cell.read_at && <div>Read: {formatTimelineDate(cell.read_at)}</div>}
                            {cell.replied_at && <div>Replied: {formatTimelineDate(cell.replied_at)}</div>}
                            {cell.error_message && <div className="text-red-300">{cell.status === 'failed' ? 'Failed' : 'Error'}: {cell.error_message}</div>}
                          </div>
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm" style={{ color: B.text2 }}>
          <span>{data?.total || 0} recipients total</span>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
                    className="p-1 rounded hover:bg-gray-100 disabled:opacity-40">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span>Page {page} of {totalPages}</span>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
                    className="p-1 rounded hover:bg-gray-100 disabled:opacity-40">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


function AnalyticsTab({ campaignId, t, toast, isDark: _isDark }: TabProps & { campaignId: number }) { void _isDark;
  const [stats, setStats] = useState<TgCampaignStats | null>(null);
  const [stepStats, setStepStats] = useState<{
    steps: { step_order: number; step_id: number; delay_days: number; sent: number; read: number; replied: number }[];
    totals: { sent: number; read: number; replied: number; total_recipients: number };
    period: string | null;
  } | null>(null);
  const [chartData, setChartData] = useState<{ date: string; sent: number; replied: number; failed: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState<string>('all');
  const [customFrom, setCustomFrom] = useState('');
  const [customTo, setCustomTo] = useState('');

  const periodParams = useMemo(() => {
    if (period === 'all') return {};
    if (period === 'custom') return { period: 'custom', from_date: customFrom || undefined, to_date: customTo || undefined };
    return { period };
  }, [period, customFrom, customTo]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [s, ss, ds] = await Promise.all([
        telegramOutreachApi.getCampaignStats(campaignId),
        telegramOutreachApi.getCampaignStepStats(campaignId, periodParams),
        telegramOutreachApi.getCampaignDailyStats(campaignId, periodParams),
      ]);
      setStats(s);
      setStepStats(ss);
      setChartData(ds.daily || []);
    } catch { toast('Failed to load analytics', 'error'); }
    finally { setLoading(false); }
  }, [campaignId, toast, periodParams]);

  useEffect(() => { loadData(); }, [loadData]);

  const funnelItems = stats ? [
    { label: 'Pending', value: stats.pending, color: '#9CA3AF' },
    { label: 'In Sequence', value: stats.in_sequence, color: '#3B82F6' },
    { label: 'Replied', value: stats.replied, color: '#22C55E' },
    { label: 'Completed', value: stats.completed, color: '#10B981' },
    { label: 'Failed', value: stats.failed, color: '#EF4444' },
    { label: 'Bounced', value: stats.bounced, color: '#F97316' },
  ] : [];
  const totalR = stats?.total_recipients || 1;
  const pct = (n: number, d: number) => d > 0 ? Math.round((n / d) * 100) : 0;

  if (loading) return <div className="flex justify-center py-12"><Loader2 className={cn('w-6 h-6 animate-spin', t.text3)} /></div>;

  return (
    <div className="space-y-6">
      {/* Period Selector */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 rounded-lg p-0.5" style={{ background: B.bg, border: `1px solid ${B.border}` }}>
          {[
            { key: 'all', label: 'All Time' },
            { key: '7d', label: '7 Days' },
            { key: '30d', label: '30 Days' },
            { key: 'custom', label: 'Custom' },
          ].map(p => (
            <button key={p.key} onClick={() => setPeriod(p.key)}
              className="px-3 py-1.5 text-xs font-medium rounded-md transition-all"
              style={{
                background: period === p.key ? B.surface : 'transparent',
                color: period === p.key ? B.blue : B.text3,
                boxShadow: period === p.key ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
              }}>
              {p.label}
            </button>
          ))}
        </div>
        {period === 'custom' && (
          <div className="flex items-center gap-2">
            <input type="date" value={customFrom} onChange={e => setCustomFrom(e.target.value)}
              className="px-2 py-1 text-xs rounded-md" style={{ border: `1px solid ${B.border}`, color: B.text1, background: B.surface }} />
            <span className="text-xs" style={{ color: B.text3 }}>to</span>
            <input type="date" value={customTo} onChange={e => setCustomTo(e.target.value)}
              className="px-2 py-1 text-xs rounded-md" style={{ border: `1px solid ${B.border}`, color: B.text1, background: B.surface }} />
          </div>
        )}
      </div>

      {/* Summary Cards — Sent / Read / Replied */}
      {stepStats && (
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'Sent', value: stepStats.totals.sent, pctVal: 100, color: '#6366F1', bg: '#EEF2FF' },
            { label: 'Read', value: stepStats.totals.read, pctVal: pct(stepStats.totals.read, stepStats.totals.sent), color: '#3B82F6', bg: '#EFF6FF' },
            { label: 'Replied', value: stepStats.totals.replied, pctVal: pct(stepStats.totals.replied, stepStats.totals.sent), color: '#22C55E', bg: '#F0FDF4' },
          ].map(c => (
            <div key={c.label} className="rounded-xl p-5 text-center" style={{ border: `1px solid ${B.border}`, background: B.surface }}>
              <div className="text-3xl font-bold tabular-nums" style={{ color: c.color }}>{c.value}</div>
              <div className="text-lg font-semibold tabular-nums mt-0.5" style={{ color: c.color, opacity: 0.7 }}>{c.pctVal}%</div>
              <div className="text-xs mt-1 font-medium" style={{ color: B.text3 }}>{c.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Per-Step Funnel */}
      {stepStats && stepStats.steps.length > 0 && (
        <div className="rounded-xl p-5" style={{ border: `1px solid ${B.border}`, background: B.surface }}>
          <h3 className="text-sm font-semibold mb-4" style={{ color: B.text1 }}>Per-Step Analytics</h3>
          <div className="space-y-3">
            {stepStats.steps.map((step) => (
              <div key={step.step_id} className="rounded-lg p-3" style={{ border: `1px solid ${B.border}`, background: B.bg }}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="flex items-center justify-center w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold">
                      {step.step_order}
                    </span>
                    <span className="text-sm font-medium" style={{ color: B.text1 }}>
                      {step.step_order === 1 ? 'Initial Message' : `Follow-up ${step.step_order - 1}`}
                    </span>
                    {step.delay_days > 0 && (
                      <span className="text-xs px-1.5 py-0.5 rounded" style={{ color: B.text3, background: B.surface }}>
                        +{step.delay_days}d
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-6">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: '#6366F1' }} />
                    <span className="text-xs" style={{ color: B.text3 }}>Sent</span>
                    <span className="text-sm font-semibold tabular-nums" style={{ color: B.text1 }}>{step.sent}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: '#3B82F6' }} />
                    <span className="text-xs" style={{ color: B.text3 }}>Read</span>
                    <span className="text-sm font-semibold tabular-nums" style={{ color: B.text1 }}>{step.read}</span>
                    {step.sent > 0 && <span className="text-xs tabular-nums" style={{ color: B.text3 }}>({pct(step.read, step.sent)}%)</span>}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full" style={{ background: '#22C55E' }} />
                    <span className="text-xs" style={{ color: B.text3 }}>Replied</span>
                    <span className="text-sm font-semibold tabular-nums" style={{ color: B.text1 }}>{step.replied}</span>
                    {step.sent > 0 && <span className="text-xs tabular-nums" style={{ color: B.text3 }}>({pct(step.replied, step.sent)}%)</span>}
                  </div>
                </div>
                {/* Mini progress bar */}
                {step.sent > 0 && (
                  <div className="flex h-1.5 rounded-full overflow-hidden mt-2" style={{ background: '#E5E7EB' }}>
                    <div className="h-full" style={{ width: `${pct(step.read, step.sent)}%`, background: '#3B82F6' }} />
                    <div className="h-full" style={{ width: `${pct(step.replied, step.sent)}%`, background: '#22C55E' }} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Additional metrics row */}
      {stats && (
        <div className="grid grid-cols-5 gap-3">
          {[
            { label: 'Recipients', value: stats.total_recipients, color: B.blue },
            { label: 'Total Sent', value: stats.total_messages_sent, color: B.text1 },
            { label: 'Total Replied', value: stats.replied, color: '#22C55E' },
            { label: 'Reply Rate', value: `${pct(stats.replied, totalR)}%`, color: B.blue },
            { label: 'Delivery', value: `${pct(totalR - stats.failed - stats.bounced, totalR)}%`, color: '#3B82F6' },
          ].map(s => (
            <div key={s.label} className="rounded-xl p-4 text-center" style={{ border: `1px solid ${B.border}`, background: B.surface }}>
              <div className="text-2xl font-bold tabular-nums" style={{ color: s.color }}>{s.value}</div>
              <div className="text-xs mt-1" style={{ color: B.text3 }}>{s.label}</div>
            </div>
          ))}
        </div>
      )}

      <div className="rounded-xl p-5" style={{ border: `1px solid ${B.border}`, background: B.surface }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold" style={{ color: B.text1 }}>Daily Activity</h3>
          <div className="flex items-center gap-4">
            {[{ l: 'Sent', c: '#6366f1' }, { l: 'Replied', c: '#22c55e' }, { l: 'Failed', c: '#ef4444' }].map(x => (
              <div key={x.l} className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: x.c }} />
                <span className="text-xs" style={{ color: B.text3 }}>{x.l}</span>
              </div>
            ))}
          </div>
        </div>
        {chartData.length === 0 ? (
          <div className="text-center py-12" style={{ color: B.text3 }}>
            <BarChart3 className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p className="text-sm">No activity data yet.</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="gS" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#6366f1" stopOpacity={0.2}/><stop offset="95%" stopColor="#6366f1" stopOpacity={0}/></linearGradient>
                <linearGradient id="gR" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#22c55e" stopOpacity={0.2}/><stop offset="95%" stopColor="#22c55e" stopOpacity={0}/></linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#E8E6E3" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#9CA3AF' }} tickFormatter={(v: string) => { const d = new Date(v); return `${d.getDate()}/${d.getMonth()+1}`; }} />
              <YAxis tick={{ fontSize: 11, fill: '#9CA3AF' }} allowDecimals={false} />
              <Tooltip contentStyle={{ background: '#fff', border: '1px solid #E8E6E3', borderRadius: 8, fontSize: 12 }} />
              <Area type="monotone" dataKey="sent" stroke="#6366f1" strokeWidth={2} fill="url(#gS)" />
              <Area type="monotone" dataKey="replied" stroke="#22c55e" strokeWidth={2} fill="url(#gR)" />
              <Area type="monotone" dataKey="failed" stroke="#ef4444" strokeWidth={1.5} fill="transparent" strokeDasharray="4 4" />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {stats && (
        <div className="rounded-xl p-5" style={{ border: `1px solid ${B.border}`, background: B.surface }}>
          <h3 className="text-sm font-semibold mb-4" style={{ color: B.text1 }}>Recipient Funnel</h3>
          <div className="space-y-2.5">
            {funnelItems.map(item => (
              <div key={item.label} className="flex items-center gap-3">
                <span className="text-xs w-20 text-right" style={{ color: B.text3 }}>{item.label}</span>
                <div className="flex-1 h-6 rounded-full overflow-hidden" style={{ background: B.bg }}>
                  <div className="h-full rounded-full transition-all" style={{ width: `${Math.max((item.value / totalR) * 100, item.value > 0 ? 2 : 0)}%`, background: item.color }} />
                </div>
                <span className="text-xs w-10 tabular-nums font-medium" style={{ color: item.color }}>{item.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center gap-3">
        <a href={telegramOutreachApi.analyticsExportCSVURL(campaignId, periodParams)}
           className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium hover:opacity-80"
           style={{ border: `1px solid ${B.blue}`, color: B.blue, background: B.blueBg }}>
          <Download className="w-3.5 h-3.5" /> CSV Export
        </a>
        <a href={telegramOutreachApi.downloadReportURL(campaignId, 'html')}
           className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium hover:opacity-80"
           style={{ border: `1px solid ${B.border}`, color: B.text2 }}>
          <Download className="w-3.5 h-3.5" /> HTML Report
        </a>
        <a href={telegramOutreachApi.downloadReportURL(campaignId, 'txt')}
           className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium hover:opacity-80"
           style={{ border: `1px solid ${B.border}`, color: B.text2 }}>
          <Download className="w-3.5 h-3.5" /> TXT Report
        </a>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Preview Tab (message preview only)
// ══════════════════════════════════════════════════════════════════════

function PreviewStatsTab({ campaignId, t, toast, isDark: _isDark }: TabProps & { campaignId: number }) { void _isDark;
  const [previewSteps, setPreviewSteps] = useState<any[]>([]);
  const [recipientIdx, setRecipientIdx] = useState(0);
  const [loadingPreview, setLoadingPreview] = useState(false);

  const loadPreview = useCallback(async () => {
    setLoadingPreview(true);
    try {
      const data = await telegramOutreachApi.previewSequence(campaignId, recipientIdx);
      setPreviewSteps(data.steps);
    } catch {
      setPreviewSteps([]);
    } finally {
      setLoadingPreview(false);
    }
  }, [campaignId, recipientIdx, toast]);

  useEffect(() => { loadPreview(); }, [loadPreview]);

  return (
    <div className="space-y-6">
      {/* Preview */}
      <div className="rounded-xl p-5" style={{ border: `1px solid ${B.border}`, background: B.surface }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className={cn('text-sm font-semibold', t.text1)}>Message Preview</h3>
          <div className="flex items-center gap-2">
            <button onClick={() => setRecipientIdx(Math.max(0, recipientIdx - 1))}
                    disabled={recipientIdx === 0}
                    className={cn('p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800', recipientIdx === 0 && 'opacity-30')}>
              <ChevronLeft className={cn('w-4 h-4', t.text3)} />
            </button>
            <span className={cn('text-xs', t.text3)}>Recipient #{recipientIdx + 1}</span>
            <button onClick={() => setRecipientIdx(recipientIdx + 1)}
                    className={cn('p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800')}>
              <ChevronRight className={cn('w-4 h-4', t.text3)} />
            </button>
            <button onClick={loadPreview}
                    className={cn('p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 ml-2', t.text3)}>
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {loadingPreview ? (
          <div className="flex justify-center py-6">
            <Loader2 className={cn('w-5 h-5 animate-spin', t.text3)} />
          </div>
        ) : previewSteps.length === 0 ? (
          <p className={cn('text-sm text-center py-6', t.text3)}>
            No sequence steps yet. Go to the Sequence tab to add messages.
          </p>
        ) : (
          <div className="space-y-4">
            {previewSteps.map((step: any, i: number) => (
              <div key={i} className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="flex items-center justify-center w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400 text-xs font-bold">
                    {step.step_order}
                  </span>
                  <span className={cn('text-xs font-medium', t.text2)}>
                    {i === 0 ? 'Initial Message' : `Follow-up ${i} (after ${step.delay_days} days)`}
                  </span>
                </div>
                {step.rendered_variants?.map((v: any, vi: number) => (
                  <div key={vi} className="rounded-lg p-3 ml-8" style={{ border: `1px solid ${B.border}`, background: B.bg }}>
                    {step.rendered_variants.length > 1 && (
                      <span className={cn('text-xs font-semibold mb-1 inline-block px-1.5 py-0.5 rounded',
                        'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400')}>
                        Variant {v.label}
                      </span>
                    )}
                    <p className={cn('text-sm whitespace-pre-wrap leading-relaxed', t.text1)}>{v.text}</p>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════
// Messages Tab (sent message log)
// ══════════════════════════════════════════════════════════════════════

function MessagesTab({ campaignId, t, toast }: TabProps & { campaignId: number }) {
  const [activity, setActivity] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const loadActivity = useCallback(async () => {
    setLoading(true);
    try {
      const data = await telegramOutreachApi.getCampaignActivity(campaignId, 100);
      setActivity(data.activity);
    } catch {
      toast('Failed to load activity', 'error');
    } finally {
      setLoading(false);
    }
  }, [campaignId, toast]);

  useEffect(() => { loadActivity(); }, [loadActivity]);
  useEffect(() => {
    const interval = setInterval(loadActivity, 8000);
    return () => clearInterval(interval);
  }, [loadActivity]);

  const STATUS_COLORS: Record<string, string> = {
    sent: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    failed: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    spamblocked: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    replied: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  };

  return (
    <div className="max-w-5xl space-y-4">
      <div className="flex items-center justify-between">
        <span className={cn('text-sm font-medium', t.text1)}>Activity Log</span>
        <button onClick={loadActivity}
                className={cn('p-2 rounded-lg border hover:bg-gray-50 dark:hover:bg-gray-800', 'border-gray-200 dark:border-gray-700')}>
          <RefreshCw className={cn('w-4 h-4', t.text3)} />
        </button>
      </div>

      {loading && activity.length === 0 ? (
        <div className="flex justify-center py-12">
          <Loader2 className={cn('w-6 h-6 animate-spin', t.text3)} />
        </div>
      ) : activity.length === 0 ? (
        <div className={cn('text-center py-12 rounded-lg border', 'border-gray-200 dark:border-gray-700')}>
          <MessageSquare className={cn('w-10 h-10 mx-auto mb-3', t.text3)} />
          <p className={cn('text-sm', t.text3)}>No activity yet. Start the campaign to begin.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {activity.map((a: any, i: number) => (
            <div key={i} className={cn('rounded-lg border px-4 py-2.5 flex items-start gap-3', 'border-gray-200 dark:border-gray-700',
              a.type === 'reply' ? 'border-l-4 border-l-blue-500' : '')}>
              {/* Icon */}
              <div className={cn('w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 text-xs',
                a.type === 'reply' ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400'
                : a.status === 'sent' ? 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400'
                : 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400')}>
                {a.type === 'reply' ? '←' : '→'}
              </div>
              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={cn('text-xs font-mono font-medium', t.text1)}>
                    {a.type === 'reply' ? `@${a.recipient_username}` : a.account_phone}
                  </span>
                  <span className={cn('text-xs', t.text3)}>
                    {a.type === 'reply' ? `replied via ${a.account_phone}` : `→ @${a.recipient_username}`}
                  </span>
                  <span className={cn('px-1.5 py-0.5 rounded-full text-[10px] font-medium',
                    STATUS_COLORS[a.status] || 'bg-gray-100 text-gray-600')}>
                    {a.status}
                  </span>
                  {a.error && <span className="text-[10px] text-red-500">({a.error})</span>}
                </div>
                <p className={cn('text-xs mt-0.5 truncate', t.text3)}>{a.text}</p>
              </div>
              {/* Time */}
              <span className={cn('text-[10px] whitespace-nowrap flex-shrink-0', t.text3)}>
                {a.time ? new Date(a.time).toLocaleTimeString() : ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════
// Replies Tab
// ══════════════════════════════════════════════════════════════════════

function RepliesTab({ campaignId, t, toast }: TabProps & { campaignId: number }) {
  const [replies, setReplies] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const loadReplies = useCallback(async () => {
    setLoading(true);
    try {
      const data = await telegramOutreachApi.listCampaignReplies(campaignId, { page, page_size: 50 });
      setReplies(data.items);
      setTotal(data.total);
    } catch {
      toast('Failed to load replies', 'error');
    } finally {
      setLoading(false);
    }
  }, [campaignId, page, toast]);

  useEffect(() => { loadReplies(); }, [loadReplies]);

  // Auto-refresh every 15s
  useEffect(() => {
    const interval = setInterval(loadReplies, 15000);
    return () => clearInterval(interval);
  }, [loadReplies]);

  const handleExport = async () => {
    try {
      const data = await telegramOutreachApi.exportCampaignReplies(campaignId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `campaign_${campaignId}_replies.json`;
      a.click();
      URL.revokeObjectURL(url);
      toast('Replies exported', 'success');
    } catch {
      toast('Export failed', 'error');
    }
  };

  const totalPages = Math.ceil(total / 50);

  return (
    <div className="max-w-5xl space-y-4">
      <div className="flex items-center justify-between">
        <span className={cn('text-sm font-medium', t.text1)}>
          {total} replies
        </span>
        <div className="flex items-center gap-2">
          <button onClick={handleExport} disabled={total === 0}
                  className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50', 'border-gray-200 dark:border-gray-700', t.text2)}>
            <Download className="w-3.5 h-3.5" /> Export JSON
          </button>
          <button onClick={loadReplies}
                  className={cn('p-2 rounded-lg border hover:bg-gray-50 dark:hover:bg-gray-800', 'border-gray-200 dark:border-gray-700')}>
            <RefreshCw className={cn('w-4 h-4', t.text3)} />
          </button>
        </div>
      </div>

      {loading && replies.length === 0 ? (
        <div className="flex justify-center py-12">
          <Loader2 className={cn('w-6 h-6 animate-spin', t.text3)} />
        </div>
      ) : replies.length === 0 ? (
        <div className={cn('text-center py-12 rounded-lg border', 'border-gray-200 dark:border-gray-700')}>
          <Reply className={cn('w-10 h-10 mx-auto mb-3', t.text3)} />
          <p className={cn('text-sm', t.text3)}>No replies yet. Replies will appear here as recipients respond.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {replies.map((r: any) => (
            <div key={r.id} className={cn('rounded-lg border p-4', 'border-gray-200 dark:border-gray-700')}>
              <div className="flex items-center gap-2 mb-1.5">
                <span className={cn('font-mono text-sm font-medium', t.text1)}>@{r.recipient_username}</span>
                <span className="text-xs text-gray-400">→</span>
                <span className={cn('text-xs font-mono', t.text3)}>{r.account_phone}</span>
                <span className={cn('text-xs ml-auto', t.text3)}>
                  {r.received_at ? new Date(r.received_at).toLocaleString() : ''}
                </span>
              </div>
              <p className={cn('text-sm whitespace-pre-wrap leading-relaxed', t.text1)}>{r.message_text}</p>
            </div>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between pt-2 replies-pagination">
          <span className={cn('text-sm', t.text3)}>{total} total</span>
          <div className="flex items-center gap-2">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}
                    className={cn('px-3 py-1.5 rounded border text-sm', 'border-gray-200 dark:border-gray-700', page <= 1 && 'opacity-50')}>
              Prev
            </button>
            <span className={cn('text-sm', t.text1)}>Page {page} of {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
                    className={cn('px-3 py-1.5 rounded border text-sm', 'border-gray-200 dark:border-gray-700', page >= totalPages && 'opacity-50')}>
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════
// Auto-Reply Tab (Gemini AI)
// ══════════════════════════════════════════════════════════════════════

function AutoReplyTab({ campaignId, t, toast }: TabProps & { campaignId: number }) {
  const [config, setConfig] = useState<any>(null);
  const [conversations, setConversations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedConvId, setSelectedConvId] = useState<number | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [cfg, convs] = await Promise.all([
        telegramOutreachApi.getAutoReplyConfig(campaignId),
        telegramOutreachApi.listConversations(campaignId),
      ]);
      setConfig(cfg);
      setConversations(convs);
    } catch {
      toast('Failed to load', 'error');
    } finally {
      setLoading(false);
    }
  }, [campaignId, toast]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      await telegramOutreachApi.updateAutoReplyConfig(campaignId, config);
      toast('Config saved', 'success');
    } catch { toast('Failed', 'error'); }
    finally { setSaving(false); }
  };

  if (loading) return <div className="flex justify-center py-12"><Loader2 className={cn('w-6 h-6 animate-spin', t.text3)} /></div>;

  const inputCls = cn('w-full px-3 py-2 rounded-lg border text-sm', 'border-gray-200 dark:border-gray-700', 'bg-white dark:bg-gray-900', t.text1);
  const labelCls = cn('block text-xs font-medium mb-1', t.text2);

  return (
    <div className="max-w-4xl space-y-6">
      <div className={cn('rounded-lg border p-5', 'border-gray-200 dark:border-gray-700')}>
        <div className="flex items-center justify-between mb-4">
          <h3 className={cn('text-sm font-semibold', t.text1)}>Auto-Reply (Gemini AI)</h3>
          <button onClick={() => setConfig((c: any) => ({ ...c, enabled: !c?.enabled }))}
                  className="flex items-center gap-2 cursor-pointer">
            <div style={{ width: 36, height: 20, borderRadius: 10, background: config?.enabled ? '#4F6BF0' : '#D1D5DB', transition: 'background 0.2s', position: 'relative' }}>
              <div style={{ width: 16, height: 16, borderRadius: 8, background: '#fff', position: 'absolute', top: 2, left: config?.enabled ? 18 : 2, transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }} />
            </div>
            <span style={{ fontSize: 13, fontWeight: 600, color: config?.enabled ? '#059669' : '#9CA3AF' }}>
              {config?.enabled ? 'Enabled' : 'Disabled'}
            </span>
          </button>
        </div>
        <div className="space-y-4">
          <div>
            <label className={labelCls}>System Prompt</label>
            <textarea rows={4} value={config?.system_prompt || ''}
                      onChange={e => setConfig((c: any) => ({ ...c, system_prompt: e.target.value }))}
                      className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>Stop Phrases (one per line)</label>
            <textarea rows={3} value={(config?.stop_phrases || []).join('\n')}
                      onChange={e => setConfig((c: any) => ({ ...c, stop_phrases: e.target.value.split('\n').filter((s: string) => s.trim()) }))}
                      className={inputCls} />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className={labelCls}>Max Replies</label>
              <input type="number" min={1} value={config?.max_replies_per_conversation || 5}
                     onChange={e => setConfig((c: any) => ({ ...c, max_replies_per_conversation: Number(e.target.value) }))}
                     className={inputCls} />
            </div>
            <div>
              <label className={labelCls}>Timeout (hours)</label>
              <input type="number" min={1} value={config?.dialog_timeout_hours || 24}
                     onChange={e => setConfig((c: any) => ({ ...c, dialog_timeout_hours: Number(e.target.value) }))}
                     className={inputCls} />
            </div>
            <div className="flex items-end pb-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <button onClick={() => setConfig((c: any) => ({ ...c, simulate_human: !(c?.simulate_human ?? true) }))}
                        style={{ width: 36, height: 20, borderRadius: 10, background: (config?.simulate_human ?? true) ? '#4F6BF0' : '#D1D5DB', transition: 'background 0.2s', position: 'relative', border: 'none', cursor: 'pointer', padding: 0 }}>
                  <div style={{ width: 16, height: 16, borderRadius: 8, background: '#fff', position: 'absolute', top: 2, left: (config?.simulate_human ?? true) ? 18 : 2, transition: 'left 0.2s', boxShadow: '0 1px 3px rgba(0,0,0,0.2)' }} />
                </button>
                <span className={cn('text-sm', t.text1)}>Simulate Human</span>
              </label>
            </div>
          </div>
          <div className="flex justify-end">
            <button onClick={handleSave} disabled={saving}
                    className="flex items-center gap-2 px-5 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Save
            </button>
          </div>
        </div>
      </div>
      <div className={cn('rounded-lg border p-5', 'border-gray-200 dark:border-gray-700')}>
        <h3 className={cn('text-sm font-semibold mb-3', t.text1)}>Conversations ({conversations.length})</h3>
        {conversations.length === 0 ? (
          <p className={cn('text-sm text-center py-6', t.text3)}>No conversations yet</p>
        ) : conversations.map((conv: any) => (
          <div key={conv.id} className={cn('rounded-lg border p-3 mb-2', 'border-gray-200 dark:border-gray-700')}>
            <div className="flex items-center justify-between cursor-pointer"
                 onClick={() => setSelectedConvId(selectedConvId === conv.id ? null : conv.id)}>
              <div className="flex items-center gap-2">
                <span className={cn('font-mono text-sm', t.text1)}>@{conv.recipient_username}</span>
                <span className={cn('px-1.5 py-0.5 rounded-full text-[10px] font-medium',
                  conv.status === 'active' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'bg-gray-100 text-gray-600')}>
                  {conv.status}
                </span>
                <span className={cn('text-xs', t.text3)}>{conv.replies_sent} replies</span>
              </div>
              {conv.status === 'active' && (
                <button onClick={async e => { e.stopPropagation(); await telegramOutreachApi.stopConversation(campaignId, conv.id); loadData(); }}
                        className="px-2 py-0.5 text-xs text-red-600 hover:bg-red-50 rounded">Stop</button>
              )}
            </div>
            {selectedConvId === conv.id && conv.messages && (
              <div className="mt-2 space-y-1.5 max-h-48 overflow-y-auto">
                {conv.messages.map((msg: any, i: number) => (
                  <div key={i} className={cn('rounded px-3 py-1.5 text-xs',
                    msg.role === 'user' ? 'bg-gray-100 dark:bg-gray-800' : 'bg-indigo-50 dark:bg-indigo-900/20')}>
                    <b>{msg.role === 'user' ? 'Them' : 'AI'}:</b> {msg.text}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════
// Review Tab (Wizard Step 4)
// ══════════════════════════════════════════════════════════════════════

type ReviewSubTab = 'timeline' | 'analytics' | 'sent' | 'replies' | 'preview';

function ReviewTab({ campaignId, campaign, t, toast, isDark, onStart }: TabProps & { campaignId: number; campaign: TgCampaign; onStart: () => void }) {
  const [subTab, setSubTab] = useState<ReviewSubTab>('timeline');

  const subTabs: { key: ReviewSubTab; label: string; icon: typeof Table2 }[] = [
    { key: 'timeline', label: 'Timeline', icon: Table2 },
    { key: 'analytics', label: 'Analytics', icon: BarChart3 },
    { key: 'sent', label: 'Sent Messages', icon: MessageSquare },
    { key: 'replies', label: 'Replies', icon: Reply },
    { key: 'preview', label: 'Preview', icon: Eye },
  ];

  return (
    <div className="space-y-6">
      {/* Start Campaign CTA */}
      {(campaign.status === 'draft' || campaign.status === 'paused') && (
        <div className="rounded-xl border-2 border-dashed p-6 text-center"
             style={{ borderColor: '#c7d2fe', background: '#eef2ff' }}>
          <h3 className="text-lg font-semibold mb-2" style={{ color: B.text1 }}>Ready to launch?</h3>
          <p className="text-sm mb-4" style={{ color: B.text3 }}>
            {campaign.total_recipients} recipients &middot; {campaign.accounts_count} accounts
          </p>
          <button onClick={onStart}
                  className="inline-flex items-center gap-2 px-6 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 transition-colors">
            <Play className="w-4 h-4" />
            Start Campaign
          </button>
        </div>
      )}

      {/* Sub-tabs */}
      <div className="flex gap-1 border-b" style={{ borderColor: B.border }}>
        {subTabs.map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setSubTab(key)}
                  className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors -mb-px"
                  style={subTab === key
                    ? { borderBottom: `2px solid ${B.blue}`, color: B.blue }
                    : { borderBottom: '2px solid transparent', color: B.text3 }}>
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Sub-tab content */}
      {subTab === 'timeline' && <TimelineTab campaignId={campaignId} t={t} toast={toast} isDark={isDark} />}
      {subTab === 'analytics' && <AnalyticsTab campaignId={campaignId} t={t} toast={toast} isDark={isDark} />}
      {subTab === 'sent' && <MessagesTab campaignId={campaignId} t={t} toast={toast} isDark={isDark} />}
      {subTab === 'replies' && <RepliesTab campaignId={campaignId} t={t} toast={toast} isDark={isDark} />}
      {subTab === 'preview' && <PreviewStatsTab campaignId={campaignId} t={t} toast={toast} isDark={isDark} />}
    </div>
  );
}
