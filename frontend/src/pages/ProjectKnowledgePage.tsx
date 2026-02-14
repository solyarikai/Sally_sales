import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ArrowLeft, Target, Globe, Mail, Building2,
  ChevronDown, ChevronRight, BarChart3, ExternalLink,
  Loader2, AlertCircle,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useAppStore } from '../store/appStore';
import {
  projectKnowledgeApi,
  type ProjectKnowledge,
  type ProjectKnowledgeSegment,
} from '../api/dataSearch';

function StatCard({ label, value, sub, icon: Icon, color = 'neutral' }: {
  label: string;
  value: number | string;
  sub?: string;
  icon: any;
  color?: 'neutral' | 'green' | 'blue' | 'indigo';
}) {
  const colors = {
    neutral: 'bg-neutral-50 text-neutral-600',
    green: 'bg-green-50 text-green-700',
    blue: 'bg-blue-50 text-blue-700',
    indigo: 'bg-indigo-50 text-indigo-700',
  };
  return (
    <div className="bg-white rounded-xl border border-neutral-200 p-4 flex items-start gap-3">
      <div className={cn('p-2 rounded-lg', colors[color])}>
        <Icon className="w-4 h-4" />
      </div>
      <div>
        <div className="text-2xl font-bold text-neutral-900">{value}</div>
        <div className="text-xs text-neutral-500">{label}</div>
        {sub && <div className="text-[10px] text-neutral-400 mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}

function SegmentPanel({ name, data, isExpanded, onToggle, projectId }: {
  name: string;
  data: ProjectKnowledgeSegment;
  isExpanded: boolean;
  onToggle: () => void;
  projectId: string;
}) {
  const pct = data.total_analyzed > 0
    ? Math.round((data.targets / data.total_analyzed) * 100)
    : 0;

  return (
    <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-neutral-50 transition-colors"
      >
        <div className="flex items-center gap-3">
          {isExpanded ? <ChevronDown className="w-4 h-4 text-neutral-400" /> : <ChevronRight className="w-4 h-4 text-neutral-400" />}
          <span className="inline-flex items-center px-2.5 py-1 rounded-lg text-sm font-semibold bg-blue-50 text-blue-700 border border-blue-100">
            {name.replace(/_/g, ' ')}
          </span>
        </div>
        <div className="flex items-center gap-6 text-sm">
          <div className="text-right">
            <span className="font-semibold text-green-700">{data.targets}</span>
            <span className="text-neutral-400 ml-1">targets</span>
          </div>
          <div className="text-right">
            <span className="font-medium text-neutral-700">{data.domains}</span>
            <span className="text-neutral-400 ml-1">domains</span>
          </div>
          <div className="text-right">
            <span className="font-medium text-blue-700">{data.contacts_with_email}</span>
            <span className="text-neutral-400 ml-1">emails</span>
          </div>
          {data.queries != null && (
            <div className="text-right">
              <span className="font-medium text-neutral-600">{data.queries}</span>
              <span className="text-neutral-400 ml-1">queries</span>
            </div>
          )}
          <div className="w-16">
            <div className="h-1.5 bg-neutral-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-green-500 rounded-full transition-all"
                style={{ width: `${Math.min(pct, 100)}%` }}
              />
            </div>
            <div className="text-[10px] text-neutral-400 mt-0.5 text-center">{pct}% hit</div>
          </div>
        </div>
      </button>

      {isExpanded && (
        <div className="border-t border-neutral-100 px-5 py-4">
          <div className="grid grid-cols-5 gap-3 mb-4 text-xs">
            <div className="bg-neutral-50 rounded-lg p-3 text-center">
              <div className="text-lg font-bold text-neutral-900">{data.total_analyzed}</div>
              <div className="text-neutral-500">Analyzed</div>
            </div>
            <div className="bg-green-50 rounded-lg p-3 text-center">
              <div className="text-lg font-bold text-green-700">{data.targets}</div>
              <div className="text-green-600">Targets</div>
            </div>
            <div className="bg-blue-50 rounded-lg p-3 text-center">
              <div className="text-lg font-bold text-blue-700">{data.target_domains}</div>
              <div className="text-blue-600">Target Domains</div>
            </div>
            <div className="bg-indigo-50 rounded-lg p-3 text-center">
              <div className="text-lg font-bold text-indigo-700">{data.contacts_with_email}</div>
              <div className="text-indigo-600">Emails Found</div>
            </div>
            <Link
              to={`/contacts?project_id=${projectId}&segment=${name}`}
              className="bg-emerald-50 rounded-lg p-3 text-center hover:bg-emerald-100 transition-colors"
            >
              <div className="text-lg font-bold text-emerald-700">{data.contacts_with_email}</div>
              <div className="text-emerald-600 flex items-center justify-center gap-1">
                View in CRM <ExternalLink className="w-3 h-3" />
              </div>
            </Link>
          </div>

          {data.top_domains.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">
                Top Target Domains
              </h4>
              <div className="space-y-1">
                {data.top_domains.map((d) => (
                  <div
                    key={d.domain}
                    className="flex items-center justify-between py-1.5 px-3 rounded-lg hover:bg-neutral-50 text-sm"
                  >
                    <div className="flex items-center gap-2">
                      <Globe className="w-3.5 h-3.5 text-neutral-400" />
                      <a
                        href={`https://${d.domain}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 hover:underline font-medium"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {d.domain}
                      </a>
                      {d.name && (
                        <span className="text-neutral-400 text-xs">{d.name}</span>
                      )}
                    </div>
                    <div className="flex items-center gap-4 text-xs">
                      {d.confidence != null && (
                        <span className={cn(
                          'px-1.5 py-0.5 rounded font-medium',
                          d.confidence >= 0.8 ? 'bg-green-100 text-green-700' :
                          d.confidence >= 0.5 ? 'bg-yellow-100 text-yellow-700' :
                          'bg-neutral-100 text-neutral-600'
                        )}>
                          {Math.round(d.confidence * 100)}%
                        </span>
                      )}
                      {d.emails > 0 && (
                        <span className="text-blue-600 flex items-center gap-1">
                          <Mail className="w-3 h-3" />
                          {d.emails}
                        </span>
                      )}
                      <a
                        href={`https://${d.domain}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-neutral-400 hover:text-neutral-600"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {data.top_domains.length === 0 && (
            <div className="text-center text-neutral-400 text-sm py-4">
              No target domains found for this segment yet.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ProjectKnowledgePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { currentCompany } = useAppStore();
  const [data, setData] = useState<ProjectKnowledge | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedSegments, setExpandedSegments] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!projectId || !currentCompany) return;
    setLoading(true);
    setError(null);
    projectKnowledgeApi.getProjectKnowledge(Number(projectId))
      .then((d) => {
        setData(d);
        // Auto-expand segments with targets
        const withTargets = Object.entries(d.segments)
          .filter(([, s]) => s.targets > 0)
          .map(([k]) => k);
        setExpandedSegments(new Set(withTargets.length > 0 ? withTargets : Object.keys(d.segments).slice(0, 3)));
      })
      .catch((err) => setError(err.userMessage || 'Failed to load knowledge'))
      .finally(() => setLoading(false));
  }, [projectId, currentCompany]);

  const toggleSegment = (key: string) => {
    setExpandedSegments((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24 text-neutral-400">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        Loading project knowledge...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center py-24 text-red-500 gap-2">
        <AlertCircle className="w-5 h-5" />
        {error || 'Failed to load'}
      </div>
    );
  }

  const segmentEntries = Object.entries(data.segments).sort(
    ([, a], [, b]) => b.targets - a.targets
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            to="/search-results"
            className="p-1.5 rounded-lg hover:bg-neutral-100 transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-neutral-500" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-neutral-900">
              {data.project_name} — Knowledge Base
            </h1>
            <p className="text-sm text-neutral-500">
              Target segments, discovered companies, and contacts breakdown
            </p>
          </div>
        </div>
        {data.target_segments.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {data.target_segments.map((s) => (
              <span
                key={s}
                className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-indigo-50 text-indigo-700 border border-indigo-100"
              >
                {s}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Overall stats */}
      <div className="grid grid-cols-5 gap-4">
        <StatCard
          icon={Building2}
          label="Discovered"
          value={data.totals.discovered}
          color="neutral"
        />
        <StatCard
          icon={Target}
          label="Targets"
          value={data.totals.targets}
          sub={`${data.totals.target_domains} unique domains`}
          color="green"
        />
        <StatCard
          icon={Mail}
          label="Emails Found"
          value={data.totals.contacts_with_email}
          sub={`of ${data.totals.contacts_total} contacts`}
          color="blue"
        />
        <StatCard
          icon={BarChart3}
          label="Segments"
          value={segmentEntries.length}
          sub={`${segmentEntries.filter(([, s]) => s.targets > 0).length} with targets`}
          color="indigo"
        />
        <StatCard
          icon={Globe}
          label="Hit Rate"
          value={data.totals.discovered > 0
            ? `${Math.round((data.totals.targets / data.totals.discovered) * 100)}%`
            : '0%'}
          sub="targets / analyzed"
          color="neutral"
        />
      </div>

      {/* Segment panels */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-neutral-700 uppercase tracking-wider">
            Segments ({segmentEntries.length})
          </h2>
          <div className="flex gap-2">
            <button
              onClick={() => setExpandedSegments(new Set(segmentEntries.map(([k]) => k)))}
              className="text-xs text-blue-600 hover:underline"
            >
              Expand all
            </button>
            <button
              onClick={() => setExpandedSegments(new Set())}
              className="text-xs text-neutral-500 hover:underline"
            >
              Collapse all
            </button>
          </div>
        </div>
        <div className="space-y-2">
          {segmentEntries.map(([name, segData]) => (
            <SegmentPanel
              key={name}
              name={name}
              data={segData}
              isExpanded={expandedSegments.has(name)}
              onToggle={() => toggleSegment(name)}
              projectId={projectId!}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default ProjectKnowledgePage;
