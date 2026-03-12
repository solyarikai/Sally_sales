import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { ExternalLink, Loader2, AlertTriangle, Linkedin } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { getLearningOverview } from '../api/learning';
import type { LearningOverview } from '../api/learning';
import { ICPPanel } from '../components/knowledge/ICPPanel';
import { TemplatesPanel } from '../components/knowledge/TemplatesPanel';
import { LearningLogsPanel } from '../components/knowledge/LearningLogsPanel';
import { GTMPanel } from '../components/knowledge/GTMPanel';
import { ChatIntelPanel } from '../components/knowledge/ChatIntelPanel';
import { KnowledgeChatPanel } from '../components/knowledge/KnowledgeChatPanel';
import { AnalyticsPanel } from '../components/knowledge/AnalyticsPanel';

type Tab = 'icp' | 'templates' | 'logs' | 'gtm' | 'analytics' | 'chat-intel' | 'chat';

const TABS: { key: Tab; label: string }[] = [
  { key: 'chat', label: 'Chat' },
  { key: 'chat-intel', label: 'Chat Intel' },
  { key: 'icp', label: 'ICP' },
  { key: 'templates', label: 'Templates' },
  { key: 'logs', label: 'Learning Logs' },
  { key: 'analytics', label: 'Analytics' },
  { key: 'gtm', label: 'GTM Strategy' },
];

const VALID_TABS = new Set<string>(TABS.map(t => t.key));

export function KnowledgePage() {
  const { currentProject, setCurrentProject, projects } = useAppStore();
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const navigate = useNavigate();
  const { tab: tabParam } = useParams<{ tab?: string }>();
  const [searchParams] = useSearchParams();

  const logIdParam = searchParams.get('logId');
  const highlightLogId = logIdParam ? Number(logIdParam) : undefined;

  // logId overrides to logs tab UNLESS the URL explicitly says gtm
  const activeTab: Tab = highlightLogId && tabParam !== 'gtm'
    ? 'logs'
    : VALID_TABS.has(tabParam || '') ? (tabParam as Tab) : 'chat';

  const [overview, setOverview] = useState<LearningOverview | null>(null);
  const [loading, setLoading] = useState(false);
  const [logsRefreshKey, setLogsRefreshKey] = useState(0);

  const urlSynced = useRef(false);

  /* ---- URL -> project (on load / link share) ---- */
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
    urlSynced.current = true;
  }, [projects, searchParams]);

  /* ---- project -> URL ---- */
  useEffect(() => {
    if (!urlSynced.current) return;
    const currentParam = searchParams.get('project');
    const expectedSlug = currentProject
      ? currentProject.name.toLowerCase().replace(/\s+/g, '-')
      : null;

    if (expectedSlug && currentParam !== expectedSlug) {
      navigate(`/knowledge/${activeTab}?project=${expectedSlug}`, { replace: true });
    } else if (!expectedSlug && currentParam) {
      navigate(`/knowledge/${activeTab}`, { replace: true });
    }
  }, [currentProject]);

  /* ---- Load overview when project changes ---- */
  useEffect(() => {
    if (currentProject) {
      loadOverview(currentProject.id);
    } else {
      setOverview(null);
    }
  }, [currentProject?.id]);

  async function loadOverview(projectId: number) {
    setLoading(true);
    try {
      const data = await getLearningOverview(projectId);
      setOverview(data);
    } catch (e) {
      console.error('Failed to load learning overview:', e);
    } finally {
      setLoading(false);
    }
  }

  const switchTab = (tab: Tab) => {
    const projectSlug = currentProject
      ? `?project=${currentProject.name.toLowerCase().replace(/\s+/g, '-')}`
      : '';
    navigate(`/knowledge/${tab}${projectSlug}`, { replace: true });
  };

  const handleLearningComplete = useCallback(() => {
    if (currentProject) loadOverview(currentProject.id);
    setLogsRefreshKey(k => k + 1);
  }, [currentProject]);

  if (!currentProject) {
    return (
      <div className="h-full flex flex-col items-center justify-center" style={{ background: t.pageBg, color: t.text4 }}>
        <p className="text-[14px]">Select a project to view knowledge</p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col" style={{ background: t.pageBg }}>
      {/* Tab bar */}
      <div
        className="border-b px-5 py-2 flex items-center gap-4"
        style={{ background: t.headerBg, borderColor: t.cardBorder }}
      >
        <a
          href={`/projects/${currentProject.id}`}
          onClick={(e) => { e.preventDefault(); navigate(`/projects/${currentProject.id}`); }}
          className="flex items-center gap-1 text-[13px] font-medium hover:underline cursor-pointer"
          style={{ color: t.text2 }}
          title="Go to project page"
        >
          <ExternalLink className="w-3 h-3 opacity-50" />
          {currentProject.name}
        </a>
        <div className="w-px h-4" style={{ background: t.cardBorder }} />

        <div
          className="flex items-center gap-0.5 p-0.5 rounded-lg"
          style={{ background: isDark ? '#2a2a2a' : '#e8e8e8' }}
        >
          {TABS.map(tab => {
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => switchTab(tab.key)}
                className="relative px-3.5 py-1.5 rounded-md text-[13px] font-medium transition-all cursor-pointer"
                style={{
                  background: isActive
                    ? (isDark ? '#3c3c3c' : '#ffffff')
                    : 'transparent',
                  color: isActive ? t.text1 : t.text4,
                  boxShadow: isActive
                    ? (isDark ? '0 1px 3px rgba(0,0,0,0.3)' : '0 1px 3px rgba(0,0,0,0.08)')
                    : 'none',
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Setup warnings — hide on analytics/gtm tabs (irrelevant there) */}
      {overview?.setup_warnings && overview.setup_warnings.length > 0 && !['analytics', 'gtm'].includes(activeTab) && (
        <div
          className="mx-5 mt-3 px-4 py-3 rounded-lg border text-[13px]"
          style={{
            background: isDark ? '#422006' : '#fffbeb',
            borderColor: isDark ? '#78350f' : '#fde68a',
            color: isDark ? '#fbbf24' : '#92400e',
          }}
        >
          <div className="flex items-center gap-2 font-medium mb-1.5">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            Missing setup — AI draft quality will be reduced
          </div>
          <ul className="space-y-0.5 ml-6 list-disc">
            {overview.setup_warnings.map(w => (
              <li key={w.field}>{w.message}</li>
            ))}
          </ul>
        </div>
      )}

      {/* LinkedIn senders */}
      {overview?.getsales_senders && overview.getsales_senders.length > 0 && (
        <div
          className="mx-5 mt-3 px-4 py-2.5 rounded-lg border text-[13px]"
          style={{
            background: isDark ? '#1e293b' : '#f8fafc',
            borderColor: isDark ? '#334155' : '#e2e8f0',
            color: t.text3,
          }}
        >
          <div className="flex items-center gap-1.5 text-[12px] mb-1.5" style={{ color: t.text4 }}>
            <Linkedin className="w-3.5 h-3.5" />
            LinkedIn senders ({overview.getsales_senders.length})
          </div>
          <div className="flex flex-wrap gap-1.5">
            {overview.getsales_senders.map(s => (
              <span
                key={s.uuid}
                className="px-2 py-0.5 rounded text-[12px]"
                style={{
                  background: isDark ? '#334155' : '#e2e8f0',
                  color: t.text2,
                }}
                title={s.uuid}
              >
                {s.name}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Tab content - all panels mounted for state persistence */}
      <div className="flex-1 min-h-0 relative">
        {loading && !overview ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 className="w-5 h-5 animate-spin" style={{ color: t.text4 }} />
          </div>
        ) : (
          <>
            <div className={`absolute inset-0 ${activeTab === 'chat' ? '' : 'invisible pointer-events-none'}`}>
              <KnowledgeChatPanel projectId={currentProject.id} />
            </div>
            <div className={`absolute inset-0 overflow-y-auto ${activeTab === 'chat-intel' ? '' : 'invisible pointer-events-none'}`}>
              <div className="p-5">
                <ChatIntelPanel projectId={currentProject.id} />
              </div>
            </div>
            <div className={`absolute inset-0 overflow-y-auto ${activeTab === 'icp' ? '' : 'invisible pointer-events-none'}`}>
              <ICPPanel entries={overview?.icp || []} isDark={isDark} t={t} />
            </div>
            <div className={`absolute inset-0 overflow-y-auto ${activeTab === 'templates' ? '' : 'invisible pointer-events-none'}`}>
              <TemplatesPanel
                projectId={currentProject.id}
                isDark={isDark}
                t={t}
                onLearningComplete={handleLearningComplete}
              />
            </div>
            <div className={`absolute inset-0 overflow-y-auto ${activeTab === 'logs' ? '' : 'invisible pointer-events-none'}`}>
              <LearningLogsPanel
                projectId={currentProject.id}
                isDark={isDark}
                t={t}
                refreshKey={logsRefreshKey}
                highlightLogId={highlightLogId}
              />
            </div>
            <div className={`absolute inset-0 overflow-y-auto ${activeTab === 'analytics' ? '' : 'invisible pointer-events-none'}`}>
              <AnalyticsPanel
                projectId={currentProject.id}
                isDark={isDark}
                t={t}
              />
            </div>
            <div className={`absolute inset-0 overflow-y-auto ${activeTab === 'gtm' ? '' : 'invisible pointer-events-none'}`}>
              <GTMPanel
                projectId={currentProject.id}
                isDark={isDark}
                t={t}
                logId={activeTab === 'gtm' ? highlightLogId : undefined}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
