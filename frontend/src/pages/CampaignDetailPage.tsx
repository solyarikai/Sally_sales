import { useState, useCallback, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, Settings2, ListOrdered, Users, Eye, MessageSquare, Reply, Download, Bot,
  Plus, Trash2, Save, Upload, Loader2, Play, Pause,
  ChevronLeft, ChevronRight, RefreshCw, Type,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { useToast } from '../components/Toast';
import { telegramOutreachApi } from '../api/telegramOutreach';
import type {
  TgCampaign, TgSequence, TgSequenceStep, TgStepVariant,
  TgRecipient, TgCampaignStats, TgAccount,
} from '../api/telegramOutreach';

type Tab = 'settings' | 'sequence' | 'recipients' | 'messages' | 'replies' | 'autoreply' | 'preview';

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
  const [tab, setTab] = useState<Tab>('settings');
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
        <button onClick={() => navigate('/telegram-outreach')}
                className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm">
          Back to Outreach
        </button>
      </div>
    );
  }

  const tabs: { key: Tab; label: string; icon: typeof Settings2 }[] = [
    { key: 'settings', label: 'Settings', icon: Settings2 },
    { key: 'recipients', label: 'Recipients', icon: Users },
    { key: 'sequence', label: 'Sequence', icon: ListOrdered },
    { key: 'messages', label: 'Messages', icon: MessageSquare },
    { key: 'replies', label: 'Replies', icon: Reply },
    { key: 'autoreply', label: 'Auto-Reply', icon: Bot },
    { key: 'preview', label: 'Preview & Stats', icon: Eye },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className={cn('border-b px-6 py-4', t.cardBorder)}>
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/telegram-outreach')}
                  className={cn('p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800', t.text2)}>
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex-1">
            <h1 className={cn('text-xl font-semibold', t.text1)}>{campaign.name}</h1>
            <div className={cn('flex items-center gap-3 mt-1 text-sm', t.text3)}>
              <StatusBadge status={campaign.status} />
              <span>{campaign.total_recipients} recipients</span>
              <span>{campaign.total_messages_sent} sent</span>
              <span>{campaign.accounts_count} accounts</span>
            </div>
          </div>
          {/* Start / Pause */}
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
                  className={cn('flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium',
                    campaign.status === 'active'
                      ? 'bg-yellow-50 text-yellow-700 hover:bg-yellow-100 dark:bg-yellow-900/20 dark:text-yellow-400'
                      : 'bg-green-600 text-white hover:bg-green-700')}>
            {campaign.status === 'active' ? <><Pause className="w-4 h-4" /> Pause</> : <><Play className="w-4 h-4" /> Start</>}
          </button>
          {/* Report download */}
          <div className="flex items-center gap-1">
            <a href={telegramOutreachApi.downloadReportURL(campaignId, 'html')}
               className={cn('flex items-center gap-1 px-3 py-2 rounded-lg border text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder, t.text2)}>
              <Download className="w-3.5 h-3.5" /> HTML
            </a>
            <a href={telegramOutreachApi.downloadReportURL(campaignId, 'txt')}
               className={cn('flex items-center gap-1 px-3 py-2 rounded-lg border text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder, t.text2)}>
              <Download className="w-3.5 h-3.5" /> TXT
            </a>
          </div>
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
        {tab === 'settings' && (
          <SettingsTab campaign={campaign} onUpdate={loadCampaign} t={t} toast={toast} isDark={isDark} />
        )}
        {tab === 'sequence' && (
          <SequenceTab campaignId={campaignId} t={t} toast={toast} isDark={isDark} />
        )}
        {tab === 'recipients' && (
          <RecipientsTab campaignId={campaignId} t={t} toast={toast} isDark={isDark} />
        )}
        {tab === 'messages' && (
          <MessagesTab campaignId={campaignId} t={t} toast={toast} isDark={isDark} />
        )}
        {tab === 'replies' && (
          <RepliesTab campaignId={campaignId} t={t} toast={toast} isDark={isDark} />
        )}
        {tab === 'autoreply' && (
          <AutoReplyTab campaignId={campaignId} t={t} toast={toast} isDark={isDark} />
        )}
        {tab === 'preview' && (
          <PreviewStatsTab campaignId={campaignId} t={t} toast={toast} isDark={isDark} />
        )}
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
    delay_between_sends_min: campaign.delay_between_sends_min,
    delay_between_sends_max: campaign.delay_between_sends_max,
    delay_randomness_percent: campaign.delay_randomness_percent,
    spamblock_errors_to_skip: campaign.spamblock_errors_to_skip,
    link_preview: (campaign as any).link_preview || false,
    silent: (campaign as any).silent || false,
    delete_dialog_after: (campaign as any).delete_dialog_after || false,
  });
  const [saving, setSaving] = useState(false);

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

      await Promise.all([
        telegramOutreachApi.updateCampaign(campaign.id, updateData),
        telegramOutreachApi.setCampaignAccounts(campaign.id, Array.from(campaignAccountIds)),
      ]);
      toast('Settings saved', 'success');
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

  const inputCls = cn('w-full px-3 py-2 rounded-lg border text-sm', t.cardBorder, t.cardBg, t.text1);
  const labelCls = cn('block text-sm font-medium mb-1', t.text2);

  return (
    <div className="max-w-4xl space-y-6">
      {/* Campaign Name */}
      <div className={cn('rounded-lg border p-5', t.cardBorder)}>
        <h3 className={cn('text-sm font-semibold mb-4', t.text1)}>General</h3>
        <div>
          <label className={labelCls}>Campaign Name</label>
          <input type="text" value={form.name}
                 onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                 className={inputCls} />
        </div>
      </div>

      {/* Sending Settings */}
      <div className={cn('rounded-lg border p-5', t.cardBorder)}>
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
          <div>
            <label className={labelCls}>Delay Between Sends (min sec)</label>
            <input type="number" min={1} value={form.delay_between_sends_min}
                   onChange={e => setForm(f => ({ ...f, delay_between_sends_min: Number(e.target.value) }))}
                   className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>Delay Between Sends (max sec)</label>
            <input type="number" min={1} value={form.delay_between_sends_max}
                   onChange={e => setForm(f => ({ ...f, delay_between_sends_max: Number(e.target.value) }))}
                   className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>Delay Randomness %</label>
            <input type="number" min={0} max={100} value={form.delay_randomness_percent}
                   onChange={e => setForm(f => ({ ...f, delay_randomness_percent: Number(e.target.value) }))}
                   className={inputCls} />
          </div>
          <div>
            <label className={labelCls}>Spamblock Errors to Skip</label>
            <input type="number" min={0} value={form.spamblock_errors_to_skip}
                   onChange={e => setForm(f => ({ ...f, spamblock_errors_to_skip: Number(e.target.value) }))}
                   className={inputCls} />
          </div>
        </div>

        {/* Send Options */}
        <div className="flex items-center gap-6 mt-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.link_preview}
                   onChange={e => setForm(f => ({ ...f, link_preview: e.target.checked }))}
                   className="rounded" />
            <span className={cn('text-sm', t.text1)}>Link Preview</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.silent}
                   onChange={e => setForm(f => ({ ...f, silent: e.target.checked }))}
                   className="rounded" />
            <span className={cn('text-sm', t.text1)}>Silent Messages</span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={form.delete_dialog_after}
                   onChange={e => setForm(f => ({ ...f, delete_dialog_after: e.target.checked }))}
                   className="rounded" />
            <span className={cn('text-sm', t.text1)}>Delete Dialog After Send</span>
          </label>
        </div>
      </div>

      {/* Accounts */}
      <div className={cn('rounded-lg border p-5', t.cardBorder)}>
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
          <div className={cn('rounded-lg border overflow-hidden max-h-[320px] overflow-y-auto', t.cardBorder)}>
            <table className="w-full text-sm">
              <thead className={cn('border-b sticky top-0 z-10', t.cardBorder, isDark ? 'bg-gray-800/90' : 'bg-gray-50')}>
                <tr>
                  <th className="w-10 px-3 py-2" />
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
                        t.cardBorder,
                        campaignAccountIds.has(acc.id)
                          ? 'bg-indigo-50/50 dark:bg-indigo-900/15'
                          : 'hover:bg-gray-50 dark:hover:bg-gray-800/50',
                      )}>
                    <td className="px-3 py-2">
                      <input type="checkbox" checked={campaignAccountIds.has(acc.id)}
                             onChange={() => toggleAccount(acc.id)} className="rounded" />
                    </td>
                    <td className={cn('px-3 py-2 font-mono text-xs', t.text1)}>{acc.phone}</td>
                    <td className={cn('px-3 py-2', t.text1)}>
                      {[acc.first_name, acc.last_name].filter(Boolean).join(' ') || (
                        <span className={t.text3}>--</span>
                      )}
                    </td>
                    <td className="px-3 py-2"><StatusBadge status={acc.status} /></td>
                    <td className={cn('px-3 py-2 font-mono text-xs', t.text1)}>
                      <span className={acc.messages_sent_today >= acc.daily_message_limit ? 'text-red-500' : ''}>
                        {acc.messages_sent_today}
                      </span>
                      <span className={t.text3}> / {acc.daily_message_limit}</span>
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
    const textareaId = `seq-${stepIdx}-${varIdx}`;
    const el = document.getElementById(textareaId) as HTMLTextAreaElement | null;
    if (!el) return;
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const currentText = sequence?.steps[stepIdx]?.variants[varIdx]?.message_text || '';
    const newText = currentText.substring(0, start) + `{{${variable}}}` + currentText.substring(end);
    updateVariant(stepIdx, varIdx, { message_text: newText });
    // Restore cursor position after React re-render
    setTimeout(() => {
      el.focus();
      const pos = start + variable.length + 4;
      el.setSelectionRange(pos, pos);
    }, 0);
  };

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className={cn('w-6 h-6 animate-spin', t.text3)} />
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className={cn('text-sm font-semibold', t.text1)}>Message Sequence</h3>
          <p className={cn('text-xs mt-0.5', t.text3)}>
            Build your follow-up chain. Use {'{{variable}}'} for personalization and {'{option1|option2}'} for spintax.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={addStep}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">
            <Plus className="w-3.5 h-3.5" /> Add Step
          </button>
          <button onClick={handleSave} disabled={saving}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-700 disabled:opacity-50">
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            Save
          </button>
        </div>
      </div>

      {(!sequence || sequence.steps.length === 0) ? (
        <div className={cn('text-center py-12 rounded-lg border', t.cardBorder)}>
          <ListOrdered className={cn('w-10 h-10 mx-auto mb-3', t.text3)} />
          <p className={cn('text-sm', t.text3)}>No steps yet. Add your first message step.</p>
          <button onClick={addStep}
                  className="mt-3 px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">
            <Plus className="w-4 h-4 inline mr-1" /> Add Step
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {sequence.steps.map((step, stepIdx) => (
            <div key={stepIdx} className={cn('rounded-lg border', t.cardBorder)}>
              {/* Step Header */}
              <div className={cn('flex items-center justify-between px-4 py-3 border-b', t.cardBorder, isDark ? 'bg-gray-800/50' : 'bg-gray-50')}>
                <div className="flex items-center gap-3">
                  <span className="flex items-center justify-center w-7 h-7 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-400 text-xs font-bold">
                    {step.step_order}
                  </span>
                  <span className={cn('text-sm font-medium', t.text1)}>
                    {stepIdx === 0 ? 'Initial Message' : `Follow-up ${stepIdx}`}
                  </span>
                  {stepIdx > 0 && (
                    <div className="flex items-center gap-1.5">
                      <span className={cn('text-xs', t.text3)}>after</span>
                      <input type="number" min={0} value={step.delay_days}
                             onChange={e => updateStep(stepIdx, { delay_days: Number(e.target.value) })}
                             className={cn('w-14 px-2 py-1 rounded border text-xs text-center', t.cardBorder, t.cardBg, t.text1)} />
                      <span className={cn('text-xs', t.text3)}>days</span>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  {step.variants.length < 5 && (
                    <button onClick={() => addVariant(stepIdx)}
                            className={cn('text-xs px-2 py-1 rounded border hover:bg-gray-100 dark:hover:bg-gray-800', t.cardBorder, t.text3)}>
                      + A/B Variant
                    </button>
                  )}
                  <button onClick={() => removeStep(stepIdx)}
                          className="p-1 hover:bg-red-50 dark:hover:bg-red-900/20 rounded">
                    <Trash2 className="w-3.5 h-3.5 text-red-400" />
                  </button>
                </div>
              </div>

              {/* Variants */}
              <div className="p-4 space-y-3">
                {step.variants.map((variant, varIdx) => (
                  <div key={varIdx} className="space-y-2">
                    {step.variants.length > 1 && (
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className={cn('text-xs font-semibold px-1.5 py-0.5 rounded',
                            varIdx === 0 ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                            : 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'
                          )}>
                            Variant {variant.variant_label}
                          </span>
                          <div className="flex items-center gap-1">
                            <input type="number" min={1} max={99} value={variant.weight_percent}
                                   onChange={e => updateVariant(stepIdx, varIdx, { weight_percent: Number(e.target.value) })}
                                   className={cn('w-12 px-1.5 py-0.5 rounded border text-xs text-center', t.cardBorder, t.cardBg, t.text1)} />
                            <span className={cn('text-xs', t.text3)}>%</span>
                          </div>
                        </div>
                        {step.variants.length > 1 && (
                          <button onClick={() => removeVariant(stepIdx, varIdx)}
                                  className="p-0.5 hover:bg-red-50 dark:hover:bg-red-900/20 rounded">
                            <Trash2 className="w-3 h-3 text-red-400" />
                          </button>
                        )}
                      </div>
                    )}

                    {/* Variable Insert Buttons */}
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span className={cn('text-xs', t.text3)}>Insert:</span>
                      {['first_name', 'company_name', 'username', ...customVars].map(v => (
                        <button key={v} onClick={() => insertVariable(stepIdx, varIdx, v)}
                                className={cn('text-xs px-1.5 py-0.5 rounded border hover:bg-gray-100 dark:hover:bg-gray-800 font-mono', t.cardBorder,
                                  customVars.includes(v) ? 'text-indigo-600 dark:text-indigo-400 border-indigo-300 dark:border-indigo-700' : t.text3)}>
                          {`{{${v}}}`}
                        </button>
                      ))}
                    </div>

                    {/* Message textarea */}
                    <textarea
                      id={`seq-${stepIdx}-${varIdx}`}
                      rows={5}
                      value={variant.message_text}
                      onChange={e => updateVariant(stepIdx, varIdx, { message_text: e.target.value })}
                      placeholder="Type your message... Use {Hi|Hello|Hey} for spintax and {{first_name}} for variables"
                      className={cn('w-full px-3 py-2 rounded-lg border text-sm font-mono leading-relaxed resize-y', t.cardBorder, t.cardBg, t.text1)}
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
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
  const [uploading, setUploading] = useState(false);

  // CSV flow
  const [csvColumns, setCsvColumns] = useState<string[]>([]);
  const [csvPreview, setCsvPreview] = useState<Record<string, string>[]>([]);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvMapping, setCsvMapping] = useState<{
    username_column: string;
    first_name_column: string;
    company_name_column: string;
    custom_columns: Record<string, string>;
  }>({ username_column: '', first_name_column: '', company_name_column: '', custom_columns: {} });
  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const handleUploadText = async () => {
    if (!textInput.trim()) return;
    setUploading(true);
    try {
      const res = await telegramOutreachApi.uploadRecipientsText(campaignId, textInput);
      toast(`${res.added} recipients added (${res.total} total)`, 'success');
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
      // Auto-detect username column
      const usernameCol = res.columns.find((c: string) =>
        c.toLowerCase().includes('username') || c.toLowerCase().includes('user')
      ) || '';
      const firstNameCol = res.columns.find((c: string) =>
        c.toLowerCase().includes('first') || c.toLowerCase() === 'name'
      ) || '';
      const companyCol = res.columns.find((c: string) =>
        c.toLowerCase().includes('company') || c.toLowerCase().includes('org')
      ) || '';
      setCsvMapping({
        username_column: usernameCol,
        first_name_column: firstNameCol,
        company_name_column: companyCol,
        custom_columns: {},
      });
    } catch {
      toast('Failed to parse CSV', 'error');
    } finally {
      setUploading(false);
    }
  };

  const handleCSVImport = async () => {
    if (!csvFile || !csvMapping.username_column) {
      toast('Please select the username column', 'error');
      return;
    }
    setUploading(true);
    try {
      const res = await telegramOutreachApi.mapColumnsCSV(campaignId, csvFile, {
        username_column: csvMapping.username_column,
        first_name_column: csvMapping.first_name_column || undefined,
        company_name_column: csvMapping.company_name_column || undefined,
        custom_columns: csvMapping.custom_columns,
      });
      toast(`${res.added} recipients imported`, 'success');
      setCsvColumns([]);
      setCsvPreview([]);
      setCsvFile(null);
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
                className={cn('px-3 py-2 rounded-lg border text-sm', t.cardBorder, t.cardBg, t.text1)}>
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
                  className={cn('flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder, t.text2)}>
            <Type className="w-3.5 h-3.5" /> Paste Text
          </button>
          <button onClick={() => fileInputRef.current?.click()}
                  className="flex items-center gap-1.5 px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700">
            <Upload className="w-3.5 h-3.5" /> Upload CSV
          </button>
          <input ref={fileInputRef} type="file" accept=".csv,.txt" className="hidden"
                 onChange={e => {
                   const file = e.target.files?.[0];
                   if (file) { setUploadMode('csv'); handleCSVSelect(file); }
                   e.target.value = '';
                 }} />
        </div>
      </div>

      {/* Upload text panel */}
      {uploadMode === 'text' && (
        <div className={cn('rounded-lg border p-4 space-y-3', t.cardBorder)}>
          <h4 className={cn('text-sm font-medium', t.text1)}>Paste usernames (one per line)</h4>
          <textarea rows={6} value={textInput}
                    onChange={e => setTextInput(e.target.value)}
                    placeholder="@username1&#10;@username2&#10;username3"
                    className={cn('w-full px-3 py-2 rounded-lg border text-sm font-mono', t.cardBorder, t.cardBg, t.text1)} />
          <div className="flex items-center gap-2">
            <button onClick={handleUploadText} disabled={uploading || !textInput.trim()}
                    className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
              {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Add Recipients'}
            </button>
            <button onClick={() => { setUploadMode('none'); setTextInput(''); }}
                    className={cn('px-4 py-2 rounded-lg border text-sm', t.cardBorder, t.text2)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* CSV mapping panel */}
      {uploadMode === 'csv' && csvColumns.length > 0 && (
        <div className={cn('rounded-lg border p-4 space-y-4', t.cardBorder)}>
          <h4 className={cn('text-sm font-medium', t.text1)}>Map CSV Columns</h4>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className={cn('block text-xs font-medium mb-1', t.text2)}>Username Column *</label>
              <select value={csvMapping.username_column}
                      onChange={e => setCsvMapping(m => ({ ...m, username_column: e.target.value }))}
                      className={cn('w-full px-3 py-2 rounded-lg border text-sm', t.cardBorder, t.cardBg, t.text1)}>
                <option value="">-- Select --</option>
                {csvColumns.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className={cn('block text-xs font-medium mb-1', t.text2)}>First Name Column</label>
              <select value={csvMapping.first_name_column}
                      onChange={e => setCsvMapping(m => ({ ...m, first_name_column: e.target.value }))}
                      className={cn('w-full px-3 py-2 rounded-lg border text-sm', t.cardBorder, t.cardBg, t.text1)}>
                <option value="">-- None --</option>
                {csvColumns.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className={cn('block text-xs font-medium mb-1', t.text2)}>Company Name Column</label>
              <select value={csvMapping.company_name_column}
                      onChange={e => setCsvMapping(m => ({ ...m, company_name_column: e.target.value }))}
                      className={cn('w-full px-3 py-2 rounded-lg border text-sm', t.cardBorder, t.cardBg, t.text1)}>
                <option value="">-- None --</option>
                {csvColumns.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>

          {/* Custom Variables — remaining CSV columns */}
          {csvColumns.length > 0 && (() => {
            const extraCols = csvColumns.filter(c => c !== csvMapping.username_column && c !== csvMapping.first_name_column && c !== csvMapping.company_name_column);
            if (extraCols.length === 0) return null;
            const allSelected = extraCols.every(c => c in csvMapping.custom_columns);
            return (
              <div className={cn('rounded-lg border p-3', t.cardBorder)}>
                <div className="flex items-center justify-between mb-2">
                  <label className={cn('text-xs font-medium', t.text2)}>
                    Custom Variables — click columns to use as {'{{variable}}'} in messages
                  </label>
                  <button onClick={() => {
                            setCsvMapping(m => {
                              const custom = { ...m.custom_columns };
                              if (allSelected) {
                                extraCols.forEach(c => delete custom[c]);
                              } else {
                                extraCols.forEach(c => { custom[c] = c.toLowerCase().replace(/\s+/g, '_'); });
                              }
                              return { ...m, custom_columns: custom };
                            });
                          }}
                          className={cn('text-xs px-2 py-0.5 rounded border', t.cardBorder,
                            allSelected ? 'text-red-600' : 'text-indigo-600')}>
                    {allSelected ? 'Deselect All' : 'Select All'}
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {extraCols.map(col => {
                    const isSelected = col in csvMapping.custom_columns;
                    const varName = csvMapping.custom_columns[col] || col.toLowerCase().replace(/\s+/g, '_');
                    return (
                      <button key={col}
                              onClick={() => {
                                setCsvMapping(m => {
                                  const custom = { ...m.custom_columns };
                                  if (isSelected) delete custom[col];
                                  else custom[col] = col.toLowerCase().replace(/\s+/g, '_');
                                  return { ...m, custom_columns: custom };
                                });
                              }}
                              className={cn('px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors',
                                isSelected
                                  ? 'bg-indigo-50 text-indigo-700 border-indigo-300 dark:bg-indigo-900/30 dark:text-indigo-400 dark:border-indigo-700'
                                  : cn(t.cardBorder, t.text3, 'hover:bg-gray-50 dark:hover:bg-gray-800'))}>
                        {isSelected ? `${col} → {{${varName}}}` : col}
                      </button>
                    );
                  })}
                </div>
                {Object.keys(csvMapping.custom_columns).length > 0 && (
                  <p className={cn('text-xs mt-2', t.text3)}>
                    {Object.keys(csvMapping.custom_columns).length} variable(s) selected.
                    Use in Sequence tab: {Object.values(csvMapping.custom_columns).map(v => `{{${v}}}`).join(', ')}
                  </p>
                )}
              </div>
            );
          })()}

          {/* Preview */}
          {csvPreview.length > 0 && (
            <div className={cn('rounded-lg border overflow-auto max-h-40', t.cardBorder)}>
              <table className="w-full text-xs">
                <thead className={cn('border-b', t.cardBorder, isDark ? 'bg-gray-800/50' : 'bg-gray-50')}>
                  <tr>
                    {csvColumns.map(c => (
                      <th key={c} className={cn('text-left px-2 py-1.5 font-medium', t.text3)}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {csvPreview.map((row, i) => (
                    <tr key={i} className={cn('border-b', t.cardBorder)}>
                      {csvColumns.map(c => (
                        <td key={c} className={cn('px-2 py-1.5', t.text1)}>{row[c] || ''}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex items-center gap-2">
            <button onClick={handleCSVImport} disabled={uploading || !csvMapping.username_column}
                    className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50">
              {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Import Recipients'}
            </button>
            <button onClick={() => { setUploadMode('none'); setCsvColumns([]); setCsvPreview([]); setCsvFile(null); }}
                    className={cn('px-4 py-2 rounded-lg border text-sm', t.cardBorder, t.text2)}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Recipients Table */}
      <div className={cn('rounded-lg border overflow-hidden', t.cardBorder)}>
        <table className="w-full text-sm">
          <thead className={cn('border-b', t.cardBorder, isDark ? 'bg-gray-800/50' : 'bg-gray-50')}>
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
              <tr key={r.id} className={cn('border-b', t.cardBorder)}>
                <td className={cn('px-3 py-2 font-mono text-xs', t.text1)}>@{r.username}</td>
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
                    className={cn('px-3 py-1.5 rounded border text-sm', t.cardBorder, page <= 1 && 'opacity-50')}>
              Prev
            </button>
            <span className={cn('text-sm', t.text1)}>Page {page} of {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
                    className={cn('px-3 py-1.5 rounded border text-sm', t.cardBorder, page >= totalPages && 'opacity-50')}>
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════
// Preview & Stats Tab
// ══════════════════════════════════════════════════════════════════════

function PreviewStatsTab({ campaignId, t, toast, isDark }: TabProps & { campaignId: number }) {
  const [stats, setStats] = useState<TgCampaignStats | null>(null);
  const [previewSteps, setPreviewSteps] = useState<any[]>([]);
  const [recipientIdx, setRecipientIdx] = useState(0);
  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingPreview, setLoadingPreview] = useState(false);

  const loadStats = useCallback(async () => {
    setLoadingStats(true);
    try {
      setStats(await telegramOutreachApi.getCampaignStats(campaignId));
    } catch {
      toast('Failed to load stats', 'error');
    } finally {
      setLoadingStats(false);
    }
  }, [campaignId, toast]);

  const loadPreview = useCallback(async () => {
    setLoadingPreview(true);
    try {
      const data = await telegramOutreachApi.previewSequence(campaignId, recipientIdx);
      setPreviewSteps(data.steps);
    } catch {
      // Empty sequence is ok
      setPreviewSteps([]);
    } finally {
      setLoadingPreview(false);
    }
  }, [campaignId, recipientIdx, toast]);

  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => { loadPreview(); }, [loadPreview]);

  const funnelItems = stats ? [
    { label: 'Pending', value: stats.pending, color: 'bg-gray-400' },
    { label: 'In Sequence', value: stats.in_sequence, color: 'bg-blue-500' },
    { label: 'Replied', value: stats.replied, color: 'bg-green-500' },
    { label: 'Completed', value: stats.completed, color: 'bg-emerald-500' },
    { label: 'Failed', value: stats.failed, color: 'bg-red-500' },
    { label: 'Bounced', value: stats.bounced, color: 'bg-orange-500' },
  ] : [];

  const totalRecipients = stats?.total_recipients || 1;

  return (
    <div className="max-w-4xl space-y-6">
      {/* Stats */}
      <div className={cn('rounded-lg border p-5', t.cardBorder)}>
        <div className="flex items-center justify-between mb-4">
          <h3 className={cn('text-sm font-semibold', t.text1)}>Campaign Stats</h3>
          <button onClick={loadStats}
                  className={cn('p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800', t.text3)}>
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {loadingStats ? (
          <div className="flex justify-center py-6">
            <Loader2 className={cn('w-5 h-5 animate-spin', t.text3)} />
          </div>
        ) : stats ? (
          <div className="space-y-4">
            {/* Summary cards */}
            <div className="grid grid-cols-5 gap-3">
              <div className={cn('rounded-lg border p-3 text-center', t.cardBorder)}>
                <div className={cn('text-2xl font-bold', t.text1)}>{stats.total_recipients}</div>
                <div className={cn('text-xs', t.text3)}>Recipients</div>
              </div>
              <div className={cn('rounded-lg border p-3 text-center', t.cardBorder)}>
                <div className={cn('text-2xl font-bold', t.text1)}>{stats.total_messages_sent}</div>
                <div className={cn('text-xs', t.text3)}>Sent</div>
              </div>
              <div className={cn('rounded-lg border p-3 text-center', t.cardBorder)}>
                <div className="text-2xl font-bold text-green-600 dark:text-green-400">{stats.replied}</div>
                <div className={cn('text-xs', t.text3)}>Replied</div>
              </div>
              <div className={cn('rounded-lg border p-3 text-center', t.cardBorder)}>
                <div className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">
                  {stats.total_messages_sent > 0 ? Math.round((stats.replied / stats.total_recipients) * 100) : 0}%
                </div>
                <div className={cn('text-xs', t.text3)}>Reply Rate</div>
              </div>
              <div className={cn('rounded-lg border p-3 text-center', t.cardBorder)}>
                <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
                  {stats.total_recipients > 0 ? Math.round(((stats.total_recipients - stats.failed - stats.bounced) / stats.total_recipients) * 100) : 0}%
                </div>
                <div className={cn('text-xs', t.text3)}>Delivery Rate</div>
              </div>
            </div>

            {/* Funnel bars */}
            <div className="space-y-2">
              {funnelItems.map(item => (
                <div key={item.label} className="flex items-center gap-3">
                  <span className={cn('text-xs w-20 text-right', t.text3)}>{item.label}</span>
                  <div className={cn('flex-1 h-5 rounded-full overflow-hidden', isDark ? 'bg-gray-800' : 'bg-gray-100')}>
                    <div className={cn('h-full rounded-full transition-all', item.color)}
                         style={{ width: `${Math.max((item.value / totalRecipients) * 100, item.value > 0 ? 2 : 0)}%` }} />
                  </div>
                  <span className={cn('text-xs w-8 font-mono', t.text1)}>{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      {/* Preview */}
      <div className={cn('rounded-lg border p-5', t.cardBorder)}>
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
                  <div key={vi} className={cn('rounded-lg border p-3 ml-8', t.cardBorder, isDark ? 'bg-gray-800/30' : 'bg-gray-50/50')}>
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
                className={cn('p-2 rounded-lg border hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder)}>
          <RefreshCw className={cn('w-4 h-4', t.text3)} />
        </button>
      </div>

      {loading && activity.length === 0 ? (
        <div className="flex justify-center py-12">
          <Loader2 className={cn('w-6 h-6 animate-spin', t.text3)} />
        </div>
      ) : activity.length === 0 ? (
        <div className={cn('text-center py-12 rounded-lg border', t.cardBorder)}>
          <MessageSquare className={cn('w-10 h-10 mx-auto mb-3', t.text3)} />
          <p className={cn('text-sm', t.text3)}>No activity yet. Start the campaign to begin.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {activity.map((a: any, i: number) => (
            <div key={i} className={cn('rounded-lg border px-4 py-2.5 flex items-start gap-3', t.cardBorder,
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
                  className={cn('flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50', t.cardBorder, t.text2)}>
            <Download className="w-3.5 h-3.5" /> Export JSON
          </button>
          <button onClick={loadReplies}
                  className={cn('p-2 rounded-lg border hover:bg-gray-50 dark:hover:bg-gray-800', t.cardBorder)}>
            <RefreshCw className={cn('w-4 h-4', t.text3)} />
          </button>
        </div>
      </div>

      {loading && replies.length === 0 ? (
        <div className="flex justify-center py-12">
          <Loader2 className={cn('w-6 h-6 animate-spin', t.text3)} />
        </div>
      ) : replies.length === 0 ? (
        <div className={cn('text-center py-12 rounded-lg border', t.cardBorder)}>
          <Reply className={cn('w-10 h-10 mx-auto mb-3', t.text3)} />
          <p className={cn('text-sm', t.text3)}>No replies yet. Replies will appear here as recipients respond.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {replies.map((r: any) => (
            <div key={r.id} className={cn('rounded-lg border p-4', t.cardBorder)}>
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
                    className={cn('px-3 py-1.5 rounded border text-sm', t.cardBorder, page <= 1 && 'opacity-50')}>
              Prev
            </button>
            <span className={cn('text-sm', t.text1)}>Page {page} of {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
                    className={cn('px-3 py-1.5 rounded border text-sm', t.cardBorder, page >= totalPages && 'opacity-50')}>
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

  const inputCls = cn('w-full px-3 py-2 rounded-lg border text-sm', t.cardBorder, t.cardBg, t.text1);
  const labelCls = cn('block text-xs font-medium mb-1', t.text2);

  return (
    <div className="max-w-4xl space-y-6">
      <div className={cn('rounded-lg border p-5', t.cardBorder)}>
        <div className="flex items-center justify-between mb-4">
          <h3 className={cn('text-sm font-semibold', t.text1)}>Auto-Reply (Gemini AI)</h3>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={config?.enabled || false}
                   onChange={e => setConfig((c: any) => ({ ...c, enabled: e.target.checked }))} className="rounded" />
            <span className={cn('text-sm font-medium', config?.enabled ? 'text-green-600' : t.text3)}>
              {config?.enabled ? 'Enabled' : 'Disabled'}
            </span>
          </label>
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
                <input type="checkbox" checked={config?.simulate_human ?? true}
                       onChange={e => setConfig((c: any) => ({ ...c, simulate_human: e.target.checked }))} className="rounded" />
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
      <div className={cn('rounded-lg border p-5', t.cardBorder)}>
        <h3 className={cn('text-sm font-semibold mb-3', t.text1)}>Conversations ({conversations.length})</h3>
        {conversations.length === 0 ? (
          <p className={cn('text-sm text-center py-6', t.text3)}>No conversations yet</p>
        ) : conversations.map((conv: any) => (
          <div key={conv.id} className={cn('rounded-lg border p-3 mb-2', t.cardBorder)}>
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
