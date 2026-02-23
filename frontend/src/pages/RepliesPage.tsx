import { useEffect, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useAppStore } from '../store/appStore';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { ReplyQueue } from '../components/ReplyQueue';

export function RepliesPage() {
  const { currentProject, setCurrentProject, projects } = useAppStore();
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const [searchParams, setSearchParams] = useSearchParams();
  const campaignNamesParam = searchParams.get('campaigns') || undefined;

  /* ---- URL ↔ project sync ---- */
  const initialUrlParam = useRef(searchParams.get('project'));
  const urlApplied = useRef(!initialUrlParam.current);

  // URL → store
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

  // Store → URL
  useEffect(() => {
    if (!urlApplied.current) return;
    const currentParam = searchParams.get('project');
    const targetParam = currentProject
      ? currentProject.name.toLowerCase().replace(/\s+/g, '-')
      : null;
    if (currentParam !== targetParam) {
      setSearchParams(prev => {
        const next = new URLSearchParams(prev);
        if (targetParam) next.set('project', targetParam);
        else next.delete('project');
        return next;
      }, { replace: true });
    }
  }, [currentProject]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="h-full flex flex-col" style={{ background: t.pageBg }}>
      {/* Optional: project breadcrumb when standalone */}
      {currentProject && (
        <div
          className="px-5 py-1.5 border-b flex items-center gap-2 text-[12px]"
          style={{ background: t.headerBg, borderColor: t.cardBorder, color: t.text4 }}
        >
          <Link to={`/projects/${currentProject.id}`} className="hover:underline">
            {currentProject.name}
          </Link>
        </div>
      )}
      <div className="flex-1 min-h-0">
        <ReplyQueue isDark={isDark} campaignNames={campaignNamesParam} />
      </div>
    </div>
  );
}

export default RepliesPage;
