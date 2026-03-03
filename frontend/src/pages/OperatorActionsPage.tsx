import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ExternalLink, Loader2, ChevronLeft, ChevronRight } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { getOperatorCorrections } from '../api/learning';
import type { OperatorCorrection } from '../api/learning';

const ACTION_FILTERS = [
  { key: null, label: 'All' },
  { key: 'send', label: 'Sent' },
  { key: 'dismiss', label: 'Dismissed' },
  { key: 'regenerate', label: 'Regenerated' },
] as const;

const ACTION_BADGES: Record<string, { label: string; bg: string; bgDark: string; color: string; colorDark: string }> = {
  send: { label: 'Sent', bg: '#dcfce7', bgDark: '#052e16', color: '#166534', colorDark: '#4ade80' },
  dismiss: { label: 'Dismissed', bg: '#fee2e2', bgDark: '#450a0a', color: '#991b1b', colorDark: '#fca5a5' },
  regenerate: { label: 'Regenerated', bg: '#dbeafe', bgDark: '#172554', color: '#1e40af', colorDark: '#93c5fd' },
};

export function OperatorActionsPage() {
  const { currentProject, setCurrentProject, projects } = useAppStore();
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [corrections, setCorrections] = useState<OperatorCorrection[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [actionFilter, setActionFilter] = useState<string | null>(null);
  const pageSize = 30;

  // URL -> project sync
  useEffect(() => {
    if (!projects.length) return;
    const projectParam = searchParams.get('project');
    if (projectParam) {
      const normalized = projectParam.toLowerCase().replace(/-/g, ' ');
      const match = projects.find(p => p.name.toLowerCase() === normalized)
        || projects.find(p => p.id === Number(projectParam));
      if (match && (!currentProject || currentProject.id !== match.id)) {
        setCurrentProject(match);
      }
    }
  }, [projects, searchParams]);

  // Project -> URL sync
  useEffect(() => {
    const slug = currentProject
      ? currentProject.name.toLowerCase().replace(/\s+/g, '-')
      : null;
    const currentParam = searchParams.get('project');
    if (slug && currentParam !== slug) {
      navigate(`/actions?project=${slug}`, { replace: true });
    } else if (!slug && currentParam) {
      navigate('/actions', { replace: true });
    }
  }, [currentProject]);

  // Load corrections
  const loadCorrections = useCallback(async () => {
    if (!currentProject) return;
    setLoading(true);
    try {
      const data = await getOperatorCorrections(
        currentProject.id, page, pageSize, actionFilter || undefined
      );
      setCorrections(data.items);
      setTotal(data.total);
    } catch (e) {
      console.error('Failed to load corrections:', e);
    } finally {
      setLoading(false);
    }
  }, [currentProject?.id, page, actionFilter]);

  useEffect(() => {
    setCorrections([]);
    setTotal(0);
    setPage(1);
  }, [currentProject?.id, actionFilter]);

  useEffect(() => {
    if (currentProject) loadCorrections();
  }, [loadCorrections]);

  const totalPages = Math.ceil(total / pageSize);

  if (!currentProject) {
    return (
      <div className="h-full flex flex-col items-center justify-center" style={{ background: t.pageBg, color: t.text4 }}>
        <p className="text-[14px]">Select a project to view operator actions</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col" style={{ background: t.pageBg }}>
      {/* Header */}
      <div
        className="border-b px-5 py-2 flex items-center gap-4"
        style={{ background: t.headerBg, borderColor: t.cardBorder }}
      >
        <a
          href={`/projects/${currentProject.id}`}
          onClick={(e) => { e.preventDefault(); navigate(`/projects/${currentProject.id}`); }}
          className="flex items-center gap-1 text-[13px] font-medium hover:underline cursor-pointer"
          style={{ color: t.text2 }}
        >
          <ExternalLink className="w-3 h-3 opacity-50" />
          {currentProject.name}
        </a>
        <div className="w-px h-4" style={{ background: t.cardBorder }} />
        <span className="text-[13px] font-medium" style={{ color: t.text1 }}>
          Operator Actions
        </span>
        <span className="text-[12px]" style={{ color: t.text4 }}>
          {total} total
        </span>

        {/* Action type filter */}
        <div
          className="flex items-center gap-0.5 p-0.5 rounded-lg ml-auto"
          style={{ background: isDark ? '#2a2a2a' : '#e8e8e8' }}
        >
          {ACTION_FILTERS.map(f => {
            const isActive = actionFilter === f.key;
            return (
              <button
                key={f.key ?? 'all'}
                onClick={() => setActionFilter(f.key)}
                className="px-3 py-1.5 rounded-md text-[12px] font-medium transition-all cursor-pointer"
                style={{
                  background: isActive ? (isDark ? '#3c3c3c' : '#fff') : 'transparent',
                  color: isActive ? t.text1 : t.text4,
                  boxShadow: isActive ? (isDark ? '0 1px 3px rgba(0,0,0,0.3)' : '0 1px 3px rgba(0,0,0,0.08)') : 'none',
                }}
              >
                {f.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        {loading && corrections.length === 0 ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-5 h-5 animate-spin" style={{ color: t.text4 }} />
          </div>
        ) : corrections.length === 0 ? (
          <div className="flex items-center justify-center py-20 text-[14px]" style={{ color: t.text4 }}>
            No operator actions recorded yet
          </div>
        ) : (
          <div className="px-5 py-3">
            <table className="w-full text-[13px]" style={{ color: t.text2 }}>
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wide" style={{ color: t.text4 }}>
                  <th className="pb-2 pr-3 font-medium">Action</th>
                  <th className="pb-2 pr-3 font-medium">Category</th>
                  <th className="pb-2 pr-3 font-medium">Channel</th>
                  <th className="pb-2 pr-3 font-medium">Company</th>
                  <th className="pb-2 pr-3 font-medium">AI Draft</th>
                  <th className="pb-2 pr-3 font-medium">Operator Sent</th>
                  <th className="pb-2 font-medium">Time</th>
                </tr>
              </thead>
              <tbody>
                {corrections.map(c => {
                  const badge = ACTION_BADGES[c.action_type] || ACTION_BADGES.send;
                  const edited = c.was_edited;
                  return (
                    <tr
                      key={c.id}
                      className="border-t"
                      style={{ borderColor: t.cardBorder }}
                    >
                      <td className="py-2.5 pr-3">
                        <span
                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium"
                          style={{
                            background: isDark ? badge.bgDark : badge.bg,
                            color: isDark ? badge.colorDark : badge.color,
                          }}
                        >
                          {badge.label}
                          {edited && (
                            <span className="opacity-70">(edited)</span>
                          )}
                        </span>
                      </td>
                      <td className="py-2.5 pr-3">
                        <span className="text-[12px]" style={{ color: t.text3 }}>
                          {c.reply_category || '—'}
                        </span>
                      </td>
                      <td className="py-2.5 pr-3">
                        <span className="text-[12px]" style={{ color: t.text3 }}>
                          {c.channel || '—'}
                        </span>
                      </td>
                      <td className="py-2.5 pr-3">
                        <span className="text-[12px]" style={{ color: t.text3 }}>
                          {c.lead_company || '—'}
                        </span>
                      </td>
                      <td className="py-2.5 pr-3 max-w-[250px]">
                        <div className="text-[12px] truncate" style={{ color: t.text4 }} title={c.ai_draft_preview}>
                          {c.ai_draft_preview || '—'}
                        </div>
                      </td>
                      <td className="py-2.5 pr-3 max-w-[250px]">
                        <div className="text-[12px] truncate" style={{ color: edited ? t.text2 : t.text4 }} title={c.sent_preview}>
                          {c.sent_preview || '—'}
                        </div>
                      </td>
                      <td className="py-2.5 whitespace-nowrap">
                        <span className="text-[12px]" style={{ color: t.text4 }}>
                          {c.created_at ? new Date(c.created_at).toLocaleString('en-GB', {
                            day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
                          }) : '—'}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-3 py-4 text-[13px]" style={{ color: t.text3 }}>
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="p-1 rounded transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-default"
                  style={{ color: t.text3 }}
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span>{page} / {totalPages}</span>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="p-1 rounded transition-colors cursor-pointer disabled:opacity-30 disabled:cursor-default"
                  style={{ color: t.text3 }}
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
