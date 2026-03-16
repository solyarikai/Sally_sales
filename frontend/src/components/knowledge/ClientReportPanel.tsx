import { useState, useEffect, useCallback } from 'react';
import {
  RefreshCw, Plus, Trash2, Pencil, Check, X, Download,
  Users, MessageSquare, ThumbsUp, Calendar, Loader2,
  TrendingUp, BarChart3,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { useTheme } from '../../hooks/useTheme';
import { themeColors } from '../../lib/themeColors';

interface OutreachStat {
  id: number;
  project_id: number;
  period_start: string;
  period_end: string;
  channel: string;
  segment: string;
  plan_contacts: number;
  contacts_sent: number;
  contacts_accepted: number;
  replies_count: number;
  positive_replies: number;
  meetings_scheduled: number;
  meetings_completed: number;
  reply_rate: number;
  positive_rate: number;
  accept_rate: number;
  meeting_rate: number;
  is_manual: boolean;
  data_source: string | null;
  notes: string | null;
  last_synced_at: string | null;
}

interface StatsResponse {
  period_start: string;
  period_end: string;
  stats: OutreachStat[];
  totals_by_channel: any[];
  grand_total: any;
}

const CHANNELS = ['email', 'linkedin', 'telegram', 'whatsapp', 'other'];

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function KPICard({ icon: Icon, label, value, subValue, color }: {
  icon: any;
  label: string;
  value: string | number;
  subValue?: string;
  color: string;
}) {
  return (
    <div className="bg-white dark:bg-neutral-800 rounded-xl border border-neutral-200 dark:border-neutral-700 p-4">
      <div className="flex items-center gap-3">
        <div className={cn('p-2 rounded-lg', color)}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">{value}</div>
          <div className="text-xs text-neutral-500">{label}</div>
          {subValue && <div className="text-xs text-neutral-400 mt-0.5">{subValue}</div>}
        </div>
      </div>
    </div>
  );
}

export function ClientReportPanel({ projectId }: { projectId: number }) {
  const { isDark } = useTheme();
  const t = themeColors(isDark);

  const [stats, setStats] = useState<OutreachStat[]>([]);
  const [grandTotal, setGrandTotal] = useState<any>(null);
  const [totalsByChannel, setTotalsByChannel] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [periodStart, setPeriodStart] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - 30);
    return d.toISOString().split('T')[0];
  });
  const [periodEnd, setPeriodEnd] = useState(() => new Date().toISOString().split('T')[0]);

  // Add row modal
  const [showAddModal, setShowAddModal] = useState(false);
  const [newRow, setNewRow] = useState({
    channel: 'telegram',
    segment: '',
    plan_contacts: 0,
    contacts_sent: 0,
    replies_count: 0,
    positive_replies: 0,
    meetings_scheduled: 0,
  });
  const [addingRow, setAddingRow] = useState(false);

  // Edit row
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editValues, setEditValues] = useState<any>({});

  const loadStats = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        period_start: periodStart,
        period_end: periodEnd,
      });
      const resp = await fetch(`/api/projects/${projectId}/outreach-stats?${params}`);
      const data: StatsResponse = await resp.json();
      setStats(data.stats || []);
      setGrandTotal(data.grand_total || null);
      setTotalsByChannel(data.totals_by_channel || []);
    } catch (e) {
      console.error('Failed to load stats:', e);
    } finally {
      setLoading(false);
    }
  }, [projectId, periodStart, periodEnd]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const syncStats = async () => {
    setSyncing(true);
    try {
      const params = new URLSearchParams({
        period_start: periodStart,
        period_end: periodEnd,
      });
      await fetch(`/api/projects/${projectId}/outreach-stats/sync?${params}`, { method: 'POST' });
      await loadStats();
    } catch (e) {
      console.error('Failed to sync stats:', e);
    } finally {
      setSyncing(false);
    }
  };

  const addRow = async () => {
    if (!newRow.segment.trim()) return;
    setAddingRow(true);
    try {
      await fetch(`/api/projects/${projectId}/outreach-stats`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...newRow,
          period_start: periodStart,
          period_end: periodEnd,
          is_manual: true,
        }),
      });
      setShowAddModal(false);
      setNewRow({
        channel: 'telegram',
        segment: '',
        plan_contacts: 0,
        contacts_sent: 0,
        replies_count: 0,
        positive_replies: 0,
        meetings_scheduled: 0,
      });
      await loadStats();
    } catch (e) {
      console.error('Failed to add row:', e);
    } finally {
      setAddingRow(false);
    }
  };

  const startEdit = (stat: OutreachStat) => {
    setEditingId(stat.id);
    setEditValues({
      plan_contacts: stat.plan_contacts,
      contacts_sent: stat.contacts_sent,
      replies_count: stat.replies_count,
      positive_replies: stat.positive_replies,
      meetings_scheduled: stat.meetings_scheduled,
    });
  };

  const saveEdit = async () => {
    if (!editingId) return;
    try {
      await fetch(`/api/projects/${projectId}/outreach-stats/${editingId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editValues),
      });
      setEditingId(null);
      await loadStats();
    } catch (e) {
      console.error('Failed to save edit:', e);
    }
  };

  const deleteRow = async (id: number) => {
    if (!confirm('Delete this row?')) return;
    try {
      await fetch(`/api/projects/${projectId}/outreach-stats/${id}`, { method: 'DELETE' });
      await loadStats();
    } catch (e) {
      console.error('Failed to delete row:', e);
    }
  };

  const exportCSV = () => {
    const headers = ['Channel', 'Segment', 'Plan', 'Sent', 'Accepted', 'Replies', 'Reply%', 'Positive', 'Pos%', 'Meetings'];
    const rows = stats.map(s => [
      s.channel,
      s.segment,
      s.plan_contacts,
      s.contacts_sent,
      s.contacts_accepted,
      s.replies_count,
      formatPercent(s.reply_rate),
      s.positive_replies,
      formatPercent(s.positive_rate),
      s.meetings_scheduled,
    ]);
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `outreach_stats_${periodStart}_${periodEnd}.csv`;
    a.click();
  };

  // Group stats by channel for display
  const groupedStats: Record<string, OutreachStat[]> = {};
  for (const stat of stats) {
    if (!groupedStats[stat.channel]) groupedStats[stat.channel] = [];
    groupedStats[stat.channel].push(stat);
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold" style={{ color: t.text1 }}>Client Report</h2>
        <div className="flex items-center gap-3">
          {/* Period selector */}
          <div className="flex items-center gap-2 text-sm">
            <input
              type="date"
              value={periodStart}
              onChange={e => setPeriodStart(e.target.value)}
              className="px-2 py-1 rounded border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-800"
              style={{ color: t.text1 }}
            />
            <span style={{ color: t.text3 }}>—</span>
            <input
              type="date"
              value={periodEnd}
              onChange={e => setPeriodEnd(e.target.value)}
              className="px-2 py-1 rounded border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-800"
              style={{ color: t.text1 }}
            />
          </div>

          <button
            onClick={syncStats}
            disabled={syncing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <RefreshCw className={cn('w-4 h-4', syncing && 'animate-spin')} />
            {syncing ? 'Syncing...' : 'Sync Now'}
          </button>

          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-700"
          >
            <Plus className="w-4 h-4" />
            Add Row
          </button>

          <button
            onClick={exportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium border border-neutral-300 dark:border-neutral-600 hover:bg-neutral-100 dark:hover:bg-neutral-700"
            style={{ color: t.text2 }}
          >
            <Download className="w-4 h-4" />
            Export
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      {grandTotal && (
        <div className="grid grid-cols-4 gap-4">
          <KPICard
            icon={Users}
            label="Contacted"
            value={grandTotal.contacts_sent?.toLocaleString() || 0}
            subValue={`Plan: ${grandTotal.plan_contacts?.toLocaleString() || 0}`}
            color="bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-400"
          />
          <KPICard
            icon={MessageSquare}
            label="Replies"
            value={grandTotal.replies_count || 0}
            subValue={formatPercent(grandTotal.reply_rate || 0)}
            color="bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-400"
          />
          <KPICard
            icon={ThumbsUp}
            label="Positive"
            value={grandTotal.positive_replies || 0}
            subValue={formatPercent(grandTotal.positive_rate || 0)}
            color="bg-green-100 text-green-700 dark:bg-green-900/50 dark:text-green-400"
          />
          <KPICard
            icon={Calendar}
            label="Meetings"
            value={grandTotal.meetings_scheduled || 0}
            subValue={`${grandTotal.meetings_completed || 0} completed`}
            color="bg-orange-100 text-orange-700 dark:bg-orange-900/50 dark:text-orange-400"
          />
        </div>
      )}

      {/* Stats Table */}
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
        </div>
      ) : stats.length === 0 ? (
        <div className="text-center py-12" style={{ color: t.text4 }}>
          <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>No stats yet. Click "Sync Now" to pull data from integrations or "Add Row" for manual channels.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-200 dark:border-neutral-700">
                <th className="text-left py-2 px-3 font-medium" style={{ color: t.text3 }}>Channel</th>
                <th className="text-left py-2 px-3 font-medium" style={{ color: t.text3 }}>Segment</th>
                <th className="text-right py-2 px-3 font-medium" style={{ color: t.text3 }}>Plan</th>
                <th className="text-right py-2 px-3 font-medium" style={{ color: t.text3 }}>Sent</th>
                <th className="text-right py-2 px-3 font-medium" style={{ color: t.text3 }}>Accepted</th>
                <th className="text-right py-2 px-3 font-medium" style={{ color: t.text3 }}>Replies</th>
                <th className="text-right py-2 px-3 font-medium" style={{ color: t.text3 }}>Reply%</th>
                <th className="text-right py-2 px-3 font-medium" style={{ color: t.text3 }}>Positive</th>
                <th className="text-right py-2 px-3 font-medium" style={{ color: t.text3 }}>Meetings</th>
                <th className="text-right py-2 px-3 font-medium" style={{ color: t.text3 }}>Source</th>
                <th className="w-24"></th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(groupedStats).map(([channel, channelStats]) => (
                <>
                  {channelStats.map((stat, idx) => (
                    <tr
                      key={stat.id}
                      className={cn(
                        'border-b border-neutral-100 dark:border-neutral-800 hover:bg-neutral-50 dark:hover:bg-neutral-800/50',
                        idx === 0 && 'border-t-2 border-t-neutral-300 dark:border-t-neutral-600'
                      )}
                    >
                      <td className="py-2 px-3 font-medium capitalize" style={{ color: t.text1 }}>
                        {idx === 0 ? channel : ''}
                      </td>
                      <td className="py-2 px-3" style={{ color: t.text2 }}>{stat.segment}</td>

                      {editingId === stat.id ? (
                        <>
                          <td className="py-2 px-3 text-right">
                            <input
                              type="number"
                              value={editValues.plan_contacts}
                              onChange={e => setEditValues({ ...editValues, plan_contacts: Number(e.target.value) })}
                              className="w-16 px-1 py-0.5 text-right rounded border"
                            />
                          </td>
                          <td className="py-2 px-3 text-right">
                            {stat.is_manual ? (
                              <input
                                type="number"
                                value={editValues.contacts_sent}
                                onChange={e => setEditValues({ ...editValues, contacts_sent: Number(e.target.value) })}
                                className="w-16 px-1 py-0.5 text-right rounded border"
                              />
                            ) : (
                              <span style={{ color: t.text2 }}>{stat.contacts_sent}</span>
                            )}
                          </td>
                          <td className="py-2 px-3 text-right" style={{ color: t.text2 }}>{stat.contacts_accepted}</td>
                          <td className="py-2 px-3 text-right">
                            {stat.is_manual ? (
                              <input
                                type="number"
                                value={editValues.replies_count}
                                onChange={e => setEditValues({ ...editValues, replies_count: Number(e.target.value) })}
                                className="w-16 px-1 py-0.5 text-right rounded border"
                              />
                            ) : (
                              <span style={{ color: t.text2 }}>{stat.replies_count}</span>
                            )}
                          </td>
                          <td className="py-2 px-3 text-right" style={{ color: t.text2 }}>{formatPercent(stat.reply_rate)}</td>
                          <td className="py-2 px-3 text-right">
                            {stat.is_manual ? (
                              <input
                                type="number"
                                value={editValues.positive_replies}
                                onChange={e => setEditValues({ ...editValues, positive_replies: Number(e.target.value) })}
                                className="w-16 px-1 py-0.5 text-right rounded border"
                              />
                            ) : (
                              <span className="text-green-600">{stat.positive_replies}</span>
                            )}
                          </td>
                          <td className="py-2 px-3 text-right">
                            {stat.is_manual ? (
                              <input
                                type="number"
                                value={editValues.meetings_scheduled}
                                onChange={e => setEditValues({ ...editValues, meetings_scheduled: Number(e.target.value) })}
                                className="w-16 px-1 py-0.5 text-right rounded border"
                              />
                            ) : (
                              <span className="text-orange-600">{stat.meetings_scheduled}</span>
                            )}
                          </td>
                          <td className="py-2 px-3 text-right text-xs" style={{ color: t.text4 }}>
                            {stat.is_manual ? 'manual' : stat.data_source}
                          </td>
                          <td className="py-2 px-3 text-right">
                            <button onClick={saveEdit} className="p-1 text-green-600 hover:bg-green-100 rounded">
                              <Check className="w-4 h-4" />
                            </button>
                            <button onClick={() => setEditingId(null)} className="p-1 text-red-600 hover:bg-red-100 rounded ml-1">
                              <X className="w-4 h-4" />
                            </button>
                          </td>
                        </>
                      ) : (
                        <>
                          <td className="py-2 px-3 text-right" style={{ color: t.text2 }}>{stat.plan_contacts}</td>
                          <td className="py-2 px-3 text-right font-medium" style={{ color: t.text1 }}>{stat.contacts_sent}</td>
                          <td className="py-2 px-3 text-right" style={{ color: t.text2 }}>{stat.contacts_accepted}</td>
                          <td className="py-2 px-3 text-right" style={{ color: t.text2 }}>{stat.replies_count}</td>
                          <td className="py-2 px-3 text-right" style={{ color: stat.reply_rate > 0.05 ? '#16a34a' : t.text3 }}>
                            {formatPercent(stat.reply_rate)}
                          </td>
                          <td className="py-2 px-3 text-right text-green-600">{stat.positive_replies}</td>
                          <td className="py-2 px-3 text-right text-orange-600">{stat.meetings_scheduled}</td>
                          <td className="py-2 px-3 text-right text-xs" style={{ color: t.text4 }}>
                            {stat.is_manual ? 'manual' : stat.data_source}
                          </td>
                          <td className="py-2 px-3 text-right">
                            <button onClick={() => startEdit(stat)} className="p-1 hover:bg-neutral-100 dark:hover:bg-neutral-700 rounded" style={{ color: t.text3 }}>
                              <Pencil className="w-4 h-4" />
                            </button>
                            {stat.is_manual && (
                              <button onClick={() => deleteRow(stat.id)} className="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 rounded ml-1 text-red-500">
                                <Trash2 className="w-4 h-4" />
                              </button>
                            )}
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                  {/* Channel subtotal */}
                  {totalsByChannel.find(tc => tc.channel === channel) && (
                    <tr className="bg-neutral-50 dark:bg-neutral-800/50 font-medium">
                      <td className="py-2 px-3" style={{ color: t.text2 }}></td>
                      <td className="py-2 px-3 text-xs uppercase" style={{ color: t.text3 }}>Total {channel}</td>
                      <td className="py-2 px-3 text-right" style={{ color: t.text2 }}>
                        {totalsByChannel.find(tc => tc.channel === channel)?.plan_contacts}
                      </td>
                      <td className="py-2 px-3 text-right" style={{ color: t.text1 }}>
                        {totalsByChannel.find(tc => tc.channel === channel)?.contacts_sent}
                      </td>
                      <td className="py-2 px-3 text-right" style={{ color: t.text2 }}>
                        {totalsByChannel.find(tc => tc.channel === channel)?.contacts_accepted}
                      </td>
                      <td className="py-2 px-3 text-right" style={{ color: t.text2 }}>
                        {totalsByChannel.find(tc => tc.channel === channel)?.replies_count}
                      </td>
                      <td className="py-2 px-3 text-right" style={{ color: t.text2 }}>
                        {formatPercent(totalsByChannel.find(tc => tc.channel === channel)?.reply_rate || 0)}
                      </td>
                      <td className="py-2 px-3 text-right text-green-600">
                        {totalsByChannel.find(tc => tc.channel === channel)?.positive_replies}
                      </td>
                      <td className="py-2 px-3 text-right text-orange-600">
                        {totalsByChannel.find(tc => tc.channel === channel)?.meetings_scheduled}
                      </td>
                      <td colSpan={2}></td>
                    </tr>
                  )}
                </>
              ))}
              {/* Grand total */}
              {grandTotal && (
                <tr className="bg-neutral-100 dark:bg-neutral-700 font-bold border-t-2 border-neutral-300 dark:border-neutral-500">
                  <td className="py-3 px-3" style={{ color: t.text1 }}>TOTAL</td>
                  <td className="py-3 px-3"></td>
                  <td className="py-3 px-3 text-right" style={{ color: t.text1 }}>{grandTotal.plan_contacts}</td>
                  <td className="py-3 px-3 text-right" style={{ color: t.text1 }}>{grandTotal.contacts_sent}</td>
                  <td className="py-3 px-3 text-right" style={{ color: t.text1 }}>{grandTotal.contacts_accepted}</td>
                  <td className="py-3 px-3 text-right" style={{ color: t.text1 }}>{grandTotal.replies_count}</td>
                  <td className="py-3 px-3 text-right" style={{ color: t.text1 }}>{formatPercent(grandTotal.reply_rate)}</td>
                  <td className="py-3 px-3 text-right text-green-600">{grandTotal.positive_replies}</td>
                  <td className="py-3 px-3 text-right text-orange-600">{grandTotal.meetings_scheduled}</td>
                  <td colSpan={2}></td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Add Row Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-neutral-800 rounded-xl p-6 w-[400px] shadow-xl">
            <h3 className="text-lg font-semibold mb-4" style={{ color: t.text1 }}>Add Manual Row</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Channel</label>
                <select
                  value={newRow.channel}
                  onChange={e => setNewRow({ ...newRow, channel: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700"
                  style={{ color: t.text1 }}
                >
                  {CHANNELS.map(ch => (
                    <option key={ch} value={ch}>{ch}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Segment</label>
                <input
                  type="text"
                  value={newRow.segment}
                  onChange={e => setNewRow({ ...newRow, segment: e.target.value })}
                  placeholder="e.g., FinTech, iGaming Marketing"
                  className="w-full px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700"
                  style={{ color: t.text1 }}
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Plan</label>
                  <input
                    type="number"
                    value={newRow.plan_contacts}
                    onChange={e => setNewRow({ ...newRow, plan_contacts: Number(e.target.value) })}
                    className="w-full px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700"
                    style={{ color: t.text1 }}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Sent</label>
                  <input
                    type="number"
                    value={newRow.contacts_sent}
                    onChange={e => setNewRow({ ...newRow, contacts_sent: Number(e.target.value) })}
                    className="w-full px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700"
                    style={{ color: t.text1 }}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Replies</label>
                  <input
                    type="number"
                    value={newRow.replies_count}
                    onChange={e => setNewRow({ ...newRow, replies_count: Number(e.target.value) })}
                    className="w-full px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700"
                    style={{ color: t.text1 }}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Positive</label>
                  <input
                    type="number"
                    value={newRow.positive_replies}
                    onChange={e => setNewRow({ ...newRow, positive_replies: Number(e.target.value) })}
                    className="w-full px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700"
                    style={{ color: t.text1 }}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: t.text2 }}>Meetings</label>
                  <input
                    type="number"
                    value={newRow.meetings_scheduled}
                    onChange={e => setNewRow({ ...newRow, meetings_scheduled: Number(e.target.value) })}
                    className="w-full px-3 py-2 rounded-lg border border-neutral-300 dark:border-neutral-600 bg-white dark:bg-neutral-700"
                    style={{ color: t.text1 }}
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2 mt-6">
              <button
                onClick={() => setShowAddModal(false)}
                className="px-4 py-2 rounded-lg text-sm font-medium border border-neutral-300 dark:border-neutral-600 hover:bg-neutral-100 dark:hover:bg-neutral-700"
                style={{ color: t.text2 }}
              >
                Cancel
              </button>
              <button
                onClick={addRow}
                disabled={addingRow || !newRow.segment.trim()}
                className="px-4 py-2 rounded-lg text-sm font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
              >
                {addingRow ? 'Adding...' : 'Add Row'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
