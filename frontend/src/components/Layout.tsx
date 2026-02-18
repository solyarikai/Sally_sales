import type { ReactNode } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { Database, FileText, Settings, BookOpen, Users, ChevronDown, MessageSquare, MessageCircle, Contact, ListTodo, Search, Zap, Target, Layers, FolderOpen, Moon, Sun } from 'lucide-react';
import { cn } from '../lib/utils';
import { useAppStore } from '../store/appStore';
import { useState, useEffect, useRef } from 'react';
import { companiesApi } from '../api';
import { contactsApi } from '../api/contacts';
import { SectionErrorBoundary } from './ErrorBoundary';
import { useTheme } from '../hooks/useTheme';

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
  const projectDropdownRef = useRef<HTMLDivElement>(null);
  const { isDark, toggle: toggleTheme } = useTheme();

  // Auto-resolve company prefix from currentCompany (not URL)
  const resolvedCompanyId = currentCompany?.id;
  const companyPrefix = resolvedCompanyId ? `/company/${resolvedCompanyId}` : '';

  const navItems = [
    { path: '/', icon: Search, label: 'Data Search', global: true },
    { path: '/search-results', icon: Target, label: 'Query Investigation', global: true },
    { path: '/pipeline', icon: Layers, label: 'Pipeline', global: true },
    { path: `${companyPrefix}/data`, icon: Database, label: 'Data', needsCompany: true },
    { path: `${companyPrefix}/prospects`, icon: Users, label: 'All Prospects', needsCompany: true },
    { path: '/contacts', icon: Contact, label: 'CRM', global: true },
    { path: `${companyPrefix}/knowledge-base`, icon: BookOpen, label: 'Knowledge Base', needsCompany: true },
    { path: '/projects', icon: FolderOpen, label: 'Projects', global: true },
    ...(currentProject ? [{ path: `/projects/${currentProject.id}/chat`, icon: MessageCircle, label: 'Project Chat', global: true }] : []),
    { path: '/replies', icon: MessageSquare, label: 'Replies', global: true },
    { path: '/prompt-debug', icon: Zap, label: 'Prompt Debug', global: true },
    { path: '/tasks', icon: ListTodo, label: 'Tasks', global: true },
    { path: '/templates', icon: FileText, label: 'Prompt Templates', global: true },
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
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
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
              onClick={() => setShowProjectDropdown(!showProjectDropdown)}
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

            {showProjectDropdown && (
              <div className={cn("absolute top-full left-0 mt-1 w-52 rounded-md shadow-xl z-50 py-0.5", isDark ? "bg-[#252526] border border-[#3c3c3c]" : "bg-white border border-[#ddd]")}>
                <div className="max-h-60 overflow-y-auto py-0.5">
                  <button
                    onClick={() => { setCurrentProject(null); setShowProjectDropdown(false); }}
                    className={cn(
                      'w-full px-3 py-1.5 text-left text-[13px] transition-colors',
                      !currentProject
                        ? isDark ? 'bg-[#37373d] text-[#d4d4d4]' : 'bg-[#e8e8e8] text-[#333]'
                        : isDark ? 'hover:bg-[#2d2d2d] text-[#969696]' : 'hover:bg-[#f0f0f0] text-[#666]'
                    )}
                  >
                    All Projects
                  </button>
                  {projects.map((project) => (
                    <button
                      key={project.id}
                      onClick={() => { setCurrentProject(project); setShowProjectDropdown(false); }}
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
                </div>
              </div>
            )}
          </div>
        )}

        {/* Navigation */}
        <nav className="flex items-center gap-0.5 overflow-x-auto">
          {navItems.map((item) => {
            if (item.needsCompany && !resolvedCompanyId) {
              return null;
            }

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
    </div>
  );
}
