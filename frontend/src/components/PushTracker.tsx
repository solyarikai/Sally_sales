import { useState, useEffect, useCallback } from 'react';
import {
  Loader2, Send, TrendingUp,
  CheckCircle2, BarChart3,
} from 'lucide-react';
import {
  pipelineApi,
  type PushHistory,
  type PushCampaign,
} from '../api/pipeline';
import { cn } from '../lib/utils';

interface Props {
  projectId: number;
}

export function PushTracker({ projectId }: Props) {
  const [history, setHistory] = useState<PushHistory | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await pipelineApi.getPushHistory(projectId);
      setHistory(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  if (loading && !history) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-neutral-400" />
      </div>
    );
  }

  if (!history) return null;

  // Group daily pushes by date
  const dailyMap = new Map<string, number>();
  for (const d of history.daily_pushes) {
    dailyMap.set(d.date, (dailyMap.get(d.date) || 0) + d.count);
  }
  const dailySorted = Array.from(dailyMap.entries())
    .sort((a, b) => b[0].localeCompare(a[0]));

  // Running total for the chart
  let runningTotal = 0;
  const runningData = dailySorted.slice().reverse().map(([date, count]) => {
    runningTotal += count;
    return { date, count, cumulative: runningTotal };
  });

  const maxDaily = Math.max(...dailySorted.map(([, c]) => c), 1);

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryCard
          icon={Send}
          label="Total Pushed"
          value={history.total_pushed}
          color="blue"
        />
        <SummaryCard
          icon={BarChart3}
          label="Total Synced"
          value={history.total_synced}
          color="green"
        />
        <SummaryCard
          icon={TrendingUp}
          label="Campaigns"
          value={history.campaigns.length}
          color="purple"
        />
        <SummaryCard
          icon={CheckCircle2}
          label="Active Rules"
          value={history.rules.filter(r => r.is_active).length}
          color="green"
        />
      </div>

      {/* Campaigns table */}
      <div>
        <h3 className="text-lg font-semibold text-neutral-900 mb-3">
          SmartLead Campaigns
        </h3>
        {history.campaigns.length > 0 ? (
          <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-neutral-100 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
                  <th className="px-4 py-3">Campaign</th>
                  <th className="px-4 py-3">Rule</th>
                  <th className="px-4 py-3 text-right">Leads Pushed</th>
                  <th className="px-4 py-3">Created</th>
                </tr>
              </thead>
              <tbody>
                {history.campaigns.map(c => (
                  <CampaignRow key={c.campaign_id} campaign={c} />
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-8 text-neutral-400 text-sm bg-white rounded-xl border border-neutral-200">
            No campaigns created yet. Push contacts to SmartLead to start tracking.
          </div>
        )}
      </div>

      {/* Daily push timeline */}
      <div>
        <h3 className="text-lg font-semibold text-neutral-900 mb-3">
          Daily Push Activity
        </h3>
        {dailySorted.length > 0 ? (
          <div className="bg-white rounded-xl border border-neutral-200 p-4 space-y-2">
            {/* Simple bar chart */}
            <div className="space-y-1.5">
              {dailySorted.slice(0, 30).map(([date, count]) => {
                const pct = (count / maxDaily) * 100;
                const runItem = runningData.find(r => r.date === date);
                return (
                  <div key={date} className="flex items-center gap-3">
                    <span className="text-xs text-neutral-500 font-mono w-24 flex-shrink-0">
                      {formatDate(date)}
                    </span>
                    <div className="flex-1 relative h-6">
                      <div
                        className="absolute inset-y-0 left-0 rounded-md bg-blue-500/20"
                        style={{ width: `${Math.max(pct, 2)}%` }}
                      />
                      <div
                        className="absolute inset-y-0 left-0 rounded-md bg-blue-500"
                        style={{ width: `${Math.max(pct, 1)}%`, maxWidth: '100%' }}
                      />
                      <span className="absolute inset-y-0 left-2 flex items-center text-xs font-medium text-white mix-blend-difference">
                        +{count}
                      </span>
                    </div>
                    <span className="text-xs text-neutral-400 w-16 text-right flex-shrink-0">
                      total: {runItem?.cumulative ?? '?'}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="text-center py-8 text-neutral-400 text-sm bg-white rounded-xl border border-neutral-200">
            No push activity yet.
          </div>
        )}
      </div>

      {/* Active rules status */}
      <div>
        <h3 className="text-lg font-semibold text-neutral-900 mb-3">
          Push Rules Status
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {history.rules.map(rule => (
            <div
              key={rule.id}
              className={cn(
                "bg-white rounded-lg border p-4",
                rule.is_active ? "border-neutral-200" : "border-neutral-100 opacity-50",
              )}
            >
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-neutral-900 text-sm">{rule.name}</span>
                <span className={cn(
                  "text-[10px] font-medium uppercase px-1.5 py-0.5 rounded",
                  rule.is_active ? "bg-green-100 text-green-700" : "bg-neutral-100 text-neutral-500",
                )}>
                  {rule.is_active ? 'active' : 'inactive'}
                </span>
              </div>
              {rule.current_campaign_id && (
                <div className="text-xs text-neutral-500">
                  <span>Current campaign: </span>
                  <span className="font-mono text-blue-600">{rule.current_campaign_id}</span>
                  <span className="ml-2">({rule.current_campaign_lead_count} leads)</span>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CampaignRow({ campaign }: { campaign: PushCampaign }) {
  return (
    <tr className="border-b border-neutral-50 hover:bg-neutral-50 transition-colors">
      <td className="px-4 py-3">
        <div>
          <span className="font-medium text-neutral-900 text-sm">{campaign.campaign_name || campaign.campaign_id}</span>
          <div className="text-xs text-neutral-400 font-mono mt-0.5">ID: {campaign.campaign_id}</div>
        </div>
      </td>
      <td className="px-4 py-3">
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700">
          {campaign.rule_name || '-'}
        </span>
      </td>
      <td className="px-4 py-3 text-right">
        <span className="font-semibold text-neutral-900">{campaign.leads_pushed}</span>
      </td>
      <td className="px-4 py-3 text-sm text-neutral-500">
        {campaign.created_at ? formatDate(campaign.created_at.split('T')[0]) : '-'}
      </td>
    </tr>
  );
}

function SummaryCard({ icon: Icon, label, value, color }: {
  icon: any; label: string; value: number; color: string;
}) {
  const colors = {
    blue: 'text-blue-600 bg-blue-50',
    green: 'text-green-600 bg-green-50',
    purple: 'text-purple-600 bg-purple-50',
  };
  const c = colors[color as keyof typeof colors] || colors.blue;

  return (
    <div className="bg-white rounded-lg border border-neutral-200 p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center", c)}>
          <Icon className="w-4 h-4" />
        </div>
        <span className="text-xs font-medium text-neutral-500 uppercase tracking-wide">{label}</span>
      </div>
      <div className="text-2xl font-bold text-neutral-900">{value.toLocaleString()}</div>
    </div>
  );
}

function formatDate(dateStr: string): string {
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: undefined });
  } catch {
    return dateStr;
  }
}
