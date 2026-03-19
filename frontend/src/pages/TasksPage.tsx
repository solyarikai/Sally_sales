import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate, useSearchParams } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { ReplyQueue } from '../components/ReplyQueue';
import { MeetingsPanel } from '../components/MeetingsPanel';
type Tab = 'replies' | 'followups' | 'meetings';

const TABS: { key: Tab; label: string }[] = [
  { key: 'replies', label: 'Replies' },
  { key: 'followups', label: 'Follow-ups' },
  { key: 'meetings', label: 'Meetings' },
];

const VALID_TABS = new Set<string>(TABS.map(t => t.key));

export function TasksPage() {
  const { currentProject, setCurrentProject, projects } = useAppStore();
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const navigate = useNavigate();
  const { tab: tabParam } = useParams<{ tab?: string }>();
  const [searchParams] = useSearchParams();

  const activeTab: Tab = VALID_TABS.has(tabParam || '') ? (tabParam as Tab) : 'replies';

  const [repliesCount, setRepliesCount] = useState(0);
  const [followupsCount, setFollowupsCount] = useState(0);
  const [meetingsCount, setMeetingsCount] = useState(0);

  // Skip the first project→URL sync so the URL→project effect runs first
  const urlSynced = useRef(false);

  /* ---- URL → project (on load / link share) ---- */
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
  }, [projects, searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ---- project → URL (keep query param in sync when project changes) ---- */
  useEffect(() => {
    if (!urlSynced.current) return;
    const currentParam = searchParams.get('project');
    const leadParam = searchParams.get('lead');
    const expectedSlug = currentProject
      ? currentProject.name.toLowerCase().replace(/\s+/g, '-')
      : null;

    const leadSuffix = leadParam ? `&lead=${encodeURIComponent(leadParam)}` : '';

    if (expectedSlug && currentParam !== expectedSlug) {
      navigate(`/tasks/${activeTab}?project=${expectedSlug}${leadSuffix}`, { replace: true });
    } else if (!expectedSlug && currentParam) {
      navigate(`/tasks/${activeTab}${leadSuffix ? `?${leadSuffix.slice(1)}` : ''}`, { replace: true });
    }
  }, [currentProject]); // eslint-disable-line react-hooks/exhaustive-deps

  const switchTab = (tab: Tab) => {
    const projectSlug = currentProject
      ? `?project=${currentProject.name.toLowerCase().replace(/\s+/g, '-')}`
      : '';
    navigate(`/tasks/${tab}${projectSlug}`, { replace: true });
  };

  const handleRepliesCounts = useCallback((_counts: Record<string, number>, total: number) => {
    setRepliesCount(total);
  }, []);

  const handleFollowupsCounts = useCallback((_counts: Record<string, number>, total: number) => {
    setFollowupsCount(total);
  }, []);

  const handleMeetingsCount = useCallback((count: number) => {
    setMeetingsCount(count);
  }, []);

  const getBadgeCount = (tab: Tab): number => {
    switch (tab) {
      case 'replies': return repliesCount;
      case 'followups': return followupsCount;
      case 'meetings': return meetingsCount;
    }
  };

  const getBadgeColor = (tab: Tab): string => {
    switch (tab) {
      case 'replies': return isDark ? '#ef4444' : '#dc2626';
      case 'followups': return isDark ? '#8b5cf6' : '#7c3aed';
      case 'meetings': return isDark ? '#f59e0b' : '#d97706';
    }
  };

  return (
    <div className="h-full flex flex-col" style={{ background: t.pageBg }}>
      {/* Tab bar */}
      <div
        className="border-b px-5 py-2 flex items-center gap-4"
        style={{ background: t.headerBg, borderColor: t.cardBorder }}
      >
        {currentProject && (
          <>
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
          </>
        )}

        <div
          className="flex items-center gap-0.5 p-0.5 rounded-lg"
          style={{ background: isDark ? '#2a2a2a' : '#e8e8e8' }}
        >
          {TABS.map(tab => {
            const isActive = activeTab === tab.key;
            const count = getBadgeCount(tab.key);
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
                {count > 0 && (
                  <span
                    className="ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full text-[10px] font-bold text-white"
                    style={{ background: getBadgeColor(tab.key) }}
                  >
                    {count > 99 ? '99+' : count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab content — all panels stay mounted so counters persist across tab switches */}
      <div className="flex-1 min-h-0 relative">
        <div className={`absolute inset-0 ${activeTab === 'replies' ? '' : 'invisible pointer-events-none'}`}>
          <ReplyQueue isDark={isDark} mode="replies" onCountsChange={handleRepliesCounts} initialSearch={searchParams.get('lead') || undefined} />
        </div>
        <div className={`absolute inset-0 ${activeTab === 'followups' ? '' : 'invisible pointer-events-none'}`}>
          <ReplyQueue isDark={isDark} mode="followups" onCountsChange={handleFollowupsCounts} />
        </div>
        <div className={`absolute inset-0 ${activeTab === 'meetings' ? '' : 'invisible pointer-events-none'}`}>
          <MeetingsPanel isDark={isDark} onCountChange={handleMeetingsCount} />
        </div>
      </div>
    </div>
  );
}
