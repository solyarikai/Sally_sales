import { useState, useEffect, useCallback } from 'react';
import {
  Loader2, Send, ChevronDown, ChevronRight,
  CheckCircle2, BarChart3, AlertTriangle,
} from 'lucide-react';
import {
  pipelineApi,
  type PushHistoryDetail,
  type PushEvent,
} from '../api/pipeline';
import { cn } from '../lib/utils';

interface Props {
  projectId: number;
}

export function PushTracker({ projectId }: Props) {
  const [data, setData] = useState<PushHistoryDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const result = await pipelineApi.getPushHistoryDetail(projectId);
      setData(result);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const toggleRow = (id: number) => {
    setExpandedRows(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-5 h-5 animate-spin text-neutral-400" />
      </div>
    );
  }

  if (!data || data.pushes.length === 0) {
    return (
      <div className="text-center py-12 text-neutral-400 text-sm">
        No push events recorded yet. Push contacts to SmartLead to start tracking.
      </div>
    );
  }

  const { pushes, summary } = data;

  // Group pushes by date (pipeline run)
  const grouped = new Map<string, PushEvent[]>();
  for (const p of pushes) {
    const dateKey = p.date ? p.date.split('T')[0] : 'unknown';
    if (!grouped.has(dateKey)) grouped.set(dateKey, []);
    grouped.get(dateKey)!.push(p);
  }

  return (
    <div className="space-y-5">
      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card icon={Send} label="Total Sent" value={summary.total_sent} color="blue" />
        <Card icon={CheckCircle2} label="Uploaded" value={summary.total_uploaded} color="green" />
        <Card icon={AlertTriangle} label="Duplicates" value={summary.total_duplicates} color="amber" />
        <Card icon={BarChart3} label="Push Batches" value={summary.total_pushes} color="purple" />
      </div>

      {/* Push events table */}
      <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-neutral-100 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider bg-neutral-50">
              <th className="px-3 py-2.5 w-8"></th>
              <th className="px-3 py-2.5">Date</th>
              <th className="px-3 py-2.5">Rule</th>
              <th className="px-3 py-2.5">Campaign</th>
              <th className="px-3 py-2.5 text-right">Sent</th>
              <th className="px-3 py-2.5 text-right">Uploaded</th>
              <th className="px-3 py-2.5 text-right">Dupes</th>
              <th className="px-3 py-2.5 text-right">Invalid</th>
            </tr>
          </thead>
          <tbody>
            {pushes.map(push => {
              const isExpanded = expandedRows.has(push.id);
              const hasSegments = push.segments && push.segments.length > 0;
              return (
                <>
                  <tr
                    key={push.id}
                    className={cn(
                      "border-b border-neutral-50 hover:bg-neutral-50 transition-colors",
                      hasSegments && "cursor-pointer",
                    )}
                    onClick={() => hasSegments && toggleRow(push.id)}
                  >
                    <td className="px-3 py-2.5 text-neutral-400">
                      {hasSegments ? (
                        isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />
                      ) : null}
                    </td>
                    <td className="px-3 py-2.5 text-neutral-600 font-mono text-xs">
                      {push.date ? formatDateTime(push.date) : '-'}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700">
                        {push.rule_name || '-'}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <div>
                        <span className="font-medium text-neutral-900 text-xs">{push.campaign_name || push.campaign_id}</span>
                        {push.campaign_name && (
                          <div className="text-[10px] text-neutral-400 font-mono">ID: {push.campaign_id}</div>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-right font-semibold text-neutral-900">{push.leads_sent}</td>
                    <td className="px-3 py-2.5 text-right font-semibold text-green-700">{push.leads_uploaded}</td>
                    <td className="px-3 py-2.5 text-right text-amber-600">{push.leads_duplicate || 0}</td>
                    <td className="px-3 py-2.5 text-right text-red-500">{push.leads_invalid || 0}</td>
                  </tr>
                  {isExpanded && hasSegments && (
                    <tr key={`${push.id}-detail`}>
                      <td colSpan={8} className="px-0 py-0">
                        <div className="bg-neutral-50 border-y border-neutral-100 px-8 py-3">
                          <div className="text-xs font-medium text-neutral-500 uppercase tracking-wider mb-2">
                            Segment / Geo Breakdown
                          </div>
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="text-neutral-400 text-left">
                                <th className="pb-1 pr-4">Segment</th>
                                <th className="pb-1 pr-4">Geo</th>
                                <th className="pb-1 pr-4">Source</th>
                                <th className="pb-1 pr-4">Sample Query</th>
                                <th className="pb-1 text-right">Contacts</th>
                              </tr>
                            </thead>
                            <tbody>
                              {push.segments.map((seg, idx) => (
                                <tr key={idx} className="text-neutral-700">
                                  <td className="py-0.5 pr-4">
                                    <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 font-medium">
                                      {seg.segment || '--'}
                                    </span>
                                  </td>
                                  <td className="py-0.5 pr-4">{seg.geo || '--'}</td>
                                  <td className="py-0.5 pr-4 text-neutral-500">{seg.extraction_source || '--'}</td>
                                  <td className="py-0.5 pr-4 text-neutral-500 truncate max-w-[300px]" title={seg.sample_query}>
                                    {seg.sample_query || '--'}
                                  </td>
                                  <td className="py-0.5 text-right font-medium">{seg.count}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
          </tbody>
          {/* Summary footer */}
          <tfoot>
            <tr className="border-t-2 border-neutral-200 bg-neutral-50 font-semibold text-sm">
              <td className="px-3 py-2.5" colSpan={4}>
                <span className="text-neutral-600">Total ({summary.total_pushes} pushes)</span>
              </td>
              <td className="px-3 py-2.5 text-right text-neutral-900">{summary.total_sent}</td>
              <td className="px-3 py-2.5 text-right text-green-700">{summary.total_uploaded}</td>
              <td className="px-3 py-2.5 text-right text-amber-600">{summary.total_duplicates}</td>
              <td className="px-3 py-2.5 text-right text-red-500">-</td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

function Card({ icon: Icon, label, value, color }: {
  icon: any; label: string; value: number; color: string;
}) {
  const colors: Record<string, string> = {
    blue: 'text-blue-600 bg-blue-50',
    green: 'text-green-600 bg-green-50',
    purple: 'text-purple-600 bg-purple-50',
    amber: 'text-amber-600 bg-amber-50',
  };
  const c = colors[color] || colors.blue;

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

function formatDateTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })
      + ' ' + d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso;
  }
}
