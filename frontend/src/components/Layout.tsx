import type { ReactNode } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { Settings, ChevronDown, Contact, ListTodo, FolderOpen, Moon, Sun, Search, Target, Layers, BarChart2, BookOpen, Activity, Shield } from 'lucide-react';
import { cn } from '../lib/utils';
import { useAppStore } from '../store/appStore';
import { useState, useEffect, useRef } from 'react';
import { companiesApi } from '../api';
import { contactsApi } from '../api/contacts';
import { SectionErrorBoundary } from './ErrorBoundary';
import { SpotlightFeedback } from './SpotlightFeedback';
import { useTheme } from '../hooks/useTheme';
import { godPanelApi } from '../api/godPanel';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { companyId } = useParams<{ companyId: string }>();
  const {
    currentCompany, companies, setCurrentCompany, setCompanies,
    currentProject, projects, setCurrentProject, setProjects,
  } = useAppStore();
  const [showProjectDropdown, setShowProjectDropdown] = useState(false);
  const [projectSearch, setProjectSearch] = useState('');
  const [showSpotlight, setShowSpotlight] = useState(false);
  const projectDropdownRef = useRef<HTMLDivElement>(null);
  const { isDark, toggle: toggleTheme } = useTheme();
  const [unresolvedCount, setUnresolvedCount] = useState(0);

  // Poll unresolved campaign count for God Panel badge
  useEffect(() => {
    const poll = () => godPanelApi.getUnresolvedCount().then(setUnresolvedCount).catch(() => {});
    poll();
    const interval = setInterval(poll, 30_000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { path: '/', icon: Search, label: 'Data Search', global: true },
    { path: '/search-results', icon: Target, label: 'Query Investigation', global: true },
    { path: '/pipeline', icon: Layers, label: 'Pipeline', global: true },
    { path: '/dashboard/queries', icon: BarChart2, label: 'Query Dashboard', global: true },
    { path: '/projects', icon: FolderOpen, label: 'Projects', global: true },
    { path: '/tasks/replies', icon: ListTodo, label: 'Tasks', global: true },
    { path: '/knowledge/icp', icon: BookOpen, label: 'Knowledge', global: true },
    { path: '/actions', icon: Activity, label: 'Actions', global: true },
    { path: '/god-panel', icon: Shield, label: 'God Panel', global: true, badge: true },
    { path: '/contacts', icon: Contact, label: 'CRM', global: true },
    { path: '/settings', icon: Settings, label: 'Settings', global: true },
  ];

  // Load companies on mount
  useEffect(() => {
    companiesApi.listCompanies().then((loaded) => {
      setCompanies(loaded);
      if (!currentCompany && loaded.length > 0) {
        setCurrentCompany(loaded[0]);
      }
    }).catch(console.error);
  }, []);

  // Load projects on mount (use list-lite for speed + campaign_filters)
  useEffect(() => {
    contactsApi.listProjectsLite().then((loaded) => {
      setProjects(loaded as any);
    }).catch(console.error);
  }, []);
  // Set current company from URL param
  useEffect(() => {
    if (companyId) {
      const numericId = parseInt(companyId, 10);
      if (currentCompany?.id !== numericId) {
        const company = companies.find(c => c.id === numericId);
        if (company) {
          setCurrentCompany(company);
        } else if (companies.length > 0) {
          companiesApi.getCompany(numericId)
            .then(setCurrentCompany)
            .catch(() => navigate('/'));
        }
      }
    }
  }, [companyId, companies]);

  // Heavy listProjects() removed — listProjectsLite() above is fast and has campaign_filters

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (projectDropdownRef.current && !projectDropdownRef.current.contains(event.target as Node)) {
        setShowProjectDropdown(false);
        setProjectSearch('');
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Cmd+K (Mac) / Ctrl+K (Windows) spotlight feedback
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setShowSpotlight(prev => !prev);
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  const isPathActive = (path: string) => {
    if (path === '/') {
      return location.pathname === '/' || location.pathname === '/data-search';
    }
    if (path === '/settings') {
      return location.pathname === path;
    }
    if (path === '/search-results') {
      return location.pathname.startsWith('/search-results');
    }
    if (path.startsWith('/tasks/')) {
      return location.pathname.startsWith('/tasks');
    }
    if (path.startsWith('/knowledge/')) {
      return location.pathname.startsWith('/knowledge');
    }
    return location.pathname.startsWith(path);
  };

  return (
    <div className={cn("h-screen flex flex-col overflow-hidden", isDark ? "bg-[#1e1e1e]" : "bg-[#f5f5f5]")}>
      {/* Top navigation bar */}
      <header className={cn("h-12 border-b flex items-center px-4 flex-shrink-0", isDark ? "bg-[#252526] border-[#333]" : "bg-white border-[#e0e0e0]")}>
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 mr-4">
          <div className={cn("w-6 h-6 rounded flex items-center justify-center", isDark ? "bg-[#d4d4d4]" : "bg-[#333]")}>
            <span className={cn("font-bold text-[11px]", isDark ? "text-[#1e1e1e]" : "text-white")}>S</span>
          </div>
          <span className={cn("font-medium text-[13px]", isDark ? "text-[#b0b0b0]" : "text-[#666]")}>LeadGen</span>
        </Link>

        {/* Project Selector */}
        {projects.length > 0 && (
          <div className="relative mr-3" ref={projectDropdownRef}>
            <button
              onClick={() => { setShowProjectDropdown(!showProjectDropdown); setProjectSearch(''); }}
              className={cn(
                'flex items-center gap-1.5 px-2.5 py-1 rounded transition-colors text-[13px]',
                currentProject
                  ? isDark ? 'bg-[#37373d] text-[#d4d4d4] hover:bg-[#3c3c3c]' : 'bg-[#e8e8e8] text-[#333] hover:bg-[#ddd]'
                  : isDark ? 'text-[#858585] hover:text-[#d4d4d4] hover:bg-[#2d2d2d]' : 'text-[#888] hover:text-[#333] hover:bg-[#eee]'
              )}
            >
              <FolderOpen className="w-3.5 h-3.5" />
              <span className="max-w-[120px] truncate">
                {currentProject ? currentProject.name : 'All Projects'}
              </span>
              <ChevronDown className="w-3 h-3" />
            </button>

            {showProjectDropdown && (() => {
              const filteredProjects = projectSearch
                ? projects.filter(p => p.name.toLowerCase().includes(projectSearch.toLowerCase()))
                : projects;
              return (
                <div className={cn("absolute top-full left-0 mt-1 w-52 rounded-md shadow-xl z-50 py-0.5", isDark ? "bg-[#252526] border border-[#3c3c3c]" : "bg-white border border-[#ddd]")}>
                  <div className="px-1.5 py-1.5">
                    <input
                      type="text"
                      value={projectSearch}
                      onChange={(e) => setProjectSearch(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Escape') { setShowProjectDropdown(false); setProjectSearch(''); }
                        if (e.key === 'Enter' && filteredProjects.length > 0) {
                          setCurrentProject(filteredProjects[0]);
                          setShowProjectDropdown(false);
                          setProjectSearch('');
                        }
                      }}
                      placeholder="Search projects..."
                      autoFocus
                      className={cn(
                        "w-full px-2 py-1 text-[12px] rounded border-none focus:outline-none",
                        isDark ? "bg-[#3c3c3c] text-[#d4d4d4] placeholder-[#6e6e6e]" : "bg-[#f0f0f0] text-[#333] placeholder-[#999]"
                      )}
                    />
                  </div>
                  <div className="max-h-60 overflow-y-auto py-0.5">
                    <button
                      onClick={() => {
                        setCurrentProject(null);
                        setShowProjectDropdown(false);
                        setProjectSearch('');
                        if (location.pathname.startsWith('/tasks')) {
                          const tab = location.pathname.split('/')[2] || 'replies';
                          navigate(`/tasks/${tab}`, { replace: true });
                        }
                        if (location.pathname.startsWith('/knowledge')) {
                          const tab = location.pathname.split('/')[2] || 'icp';
                          navigate(`/knowledge/${tab}`, { replace: true });
                        }
                      }}
                      className={cn(
                        'w-full px-3 py-1.5 text-left text-[13px] transition-colors',
                        !currentProject
                          ? isDark ? 'bg-[#37373d] text-[#d4d4d4]' : 'bg-[#e8e8e8] text-[#333]'
                          : isDark ? 'hover:bg-[#2d2d2d] text-[#969696]' : 'hover:bg-[#f0f0f0] text-[#666]'
                      )}
                    >
                      All Projects
                    </button>
                    {filteredProjects.map((project) => (
                      <button
                        key={project.id}
                        onClick={() => {
                          setCurrentProject(project);
                          setShowProjectDropdown(false);
                          setProjectSearch('');
                          if (location.pathname.startsWith('/tasks')) {
                            const tab = location.pathname.split('/')[2] || 'replies';
                            const slug = project.name.toLowerCase().replace(/\s+/g, '-');
                            navigate(`/tasks/${tab}?project=${slug}`, { replace: true });
                          }
                          if (location.pathname.startsWith('/knowledge')) {
                            const tab = location.pathname.split('/')[2] || 'icp';
                            const slug = project.name.toLowerCase().replace(/\s+/g, '-');
                            navigate(`/knowledge/${tab}?project=${slug}`, { replace: true });
                          }
                        }}
                        className={cn(
                          'w-full px-3 py-1.5 text-left text-[13px] truncate transition-colors',
                          currentProject?.id === project.id
                            ? isDark ? 'bg-[#37373d] text-[#d4d4d4]' : 'bg-[#e8e8e8] text-[#333]'
                            : isDark ? 'hover:bg-[#2d2d2d] text-[#969696]' : 'hover:bg-[#f0f0f0] text-[#666]'
                        )}
                      >
                        {project.name}
                      </button>
                    ))}
                    {filteredProjects.length === 0 && projectSearch && (
                      <div className={cn("px-3 py-2 text-[12px]", isDark ? "text-[#6e6e6e]" : "text-[#999]")}>
                        No projects found
                      </div>
                    )}
                  </div>
                </div>
              );
            })()}
          </div>
        )}

        {/* Navigation */}
        <nav className="flex items-center gap-0.5 overflow-x-auto">
          {navItems.map((item) => {
            const isActive = isPathActive(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  'flex items-center gap-1.5 px-2.5 py-1 rounded text-[13px] font-medium transition-colors whitespace-nowrap',
                  isActive
                    ? isDark ? 'bg-[#37373d] text-[#d4d4d4]' : 'bg-[#e8e8e8] text-[#333]'
                    : isDark ? 'text-[#858585] hover:text-[#d4d4d4] hover:bg-[#2d2d2d]' : 'text-[#888] hover:text-[#333] hover:bg-[#eee]'
                )}
              >
                <item.icon className="w-3.5 h-3.5" />
                <span>{item.label}</span>
                {(item as any).badge && unresolvedCount > 0 && (
                  <span className="ml-0.5 px-1 py-0 rounded-full text-[10px] font-bold leading-tight bg-red-500 text-white min-w-[16px] text-center">
                    {unresolvedCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        <div className="flex-1" />

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="p-1.5 rounded hover:bg-[--btn-hover] transition-colors"
          style={{ '--btn-hover': isDark ? '#2d2d2d' : '#e5e5e5' } as React.CSSProperties}
          title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {isDark ? <Sun className="w-4 h-4 text-[#858585]" /> : <Moon className="w-4 h-4 text-[#666]" />}
        </button>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <SectionErrorBoundary>
          {children}
        </SectionErrorBoundary>
      </main>

      {/* Cmd+K Spotlight Feedback */}
      <SpotlightFeedback open={showSpotlight} onClose={() => setShowSpotlight(false)} />
    </div>
  );
}
