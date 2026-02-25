import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAppStore } from '../store/appStore';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { ReplyQueue } from '../components/ReplyQueue';
import { MeetingsPanel } from '../components/MeetingsPanel';
import { QualifiedPanel } from '../components/QualifiedPanel';

type Tab = 'replies' | 'meetings' | 'qualified';

const TABS: { key: Tab; label: string }[] = [
  { key: 'replies', label: 'Replies' },
  { key: 'meetings', label: 'Meetings' },
  { key: 'qualified', label: 'Qualified' },
];

export function TasksPage() {
  const { currentProject, setCurrentProject, projects } = useAppStore();
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const [searchParams, setSearchParams] = useSearchParams();

  const tabParam = (searchParams.get('tab') as Tab) || 'replies';
  const [activeTab, setActiveTab] = useState<Tab>(
    TABS.some(t => t.key === tabParam) ? tabParam : 'replies'
  );

  // Badge counts
  const [repliesCount, setRepliesCount] = useState(0);
  const [meetingsCount, setMeetingsCount] = useState(0);
  const [qualifiedCount, setQualifiedCount] = useState(0);

  /* ---- URL ↔ project sync ---- */
  const initialUrlParam = useRef(searchParams.get('project'));
  const urlApplied = useRef(!initialUrlParam.current);

  useEffect(() => {
    const projectParam = searchParams.get('project');
    if (!projectParam || !projects.length) return;
    const normalized = projectParam.toLowerCase().replace(/-/g, ' ');
    const match = projects.find(p => p.name.toLowerCase() === normalized)
      || projects.find(p => p.id === Number(projectParam));
    if (match && (!currentProject || currentProject.id !== match.id)) {
      setCurrentProject(match);
    }
    urlApplied.current = true;
  }, [projects, searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync tab + project to URL
  useEffect(() => {
    if (!urlApplied.current) return;
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      // Tab
      if (activeTab !== 'replies') next.set('tab', activeTab);
      else next.delete('tab');
      // Project
      const targetProject = currentProject
        ? currentProject.name.toLowerCase().replace(/\s+/g, '-')
        : null;
      if (targetProject) next.set('project', targetProject);
      else next.delete('project');
      return next;
    }, { replace: true });
  }, [activeTab, currentProject]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleRepliesCounts = useCallback((counts: Record<string, number>, total: number) => {
    setRepliesCount(total);
  }, []);

  const handleMeetingsCount = useCallback((count: number) => {
    setMeetingsCount(count);
  }, []);

  const handleQualifiedCount = useCallback((count: number) => {
    setQualifiedCount(count);
  }, []);

  const getBadgeCount = (tab: Tab): number => {
    switch (tab) {
      case 'replies': return repliesCount;
      case 'meetings': return meetingsCount;
      case 'qualified': return qualifiedCount;
    }
  };

  const getBadgeColor = (tab: Tab): string => {
    switch (tab) {
      case 'replies': return isDark ? '#ef4444' : '#dc2626';
      case 'meetings': return isDark ? '#f59e0b' : '#d97706';
      case 'qualified': return isDark ? '#3b82f6' : '#2563eb';
    }
  };

  return (
    <div className="h-full flex flex-col" style={{ background: t.pageBg }}>
      {/* Tab bar */}
      <div
        className="border-b px-5 py-2 flex items-center gap-4"
        style={{ background: t.headerBg, borderColor: t.cardBorder }}
      >
        {/* Project name */}
        {currentProject && (
          <>
            <span className="text-[13px] font-medium" style={{ color: t.text2 }}>
              {currentProject.name}
            </span>
            <div className="w-px h-4" style={{ background: t.cardBorder }} />
          </>
        )}

        {/* Pill tabs */}
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
                onClick={() => setActiveTab(tab.key)}
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

      {/* Tab content */}
      <div className="flex-1 min-h-0">
        {activeTab === 'replies' && (
          <ReplyQueue isDark={isDark} onCountsChange={handleRepliesCounts} />
        )}
        {activeTab === 'meetings' && (
          <MeetingsPanel isDark={isDark} onCountChange={handleMeetingsCount} />
        )}
        {activeTab === 'qualified' && (
          <QualifiedPanel isDark={isDark} onCountChange={handleQualifiedCount} />
        )}
      </div>
    </div>
  );
}
