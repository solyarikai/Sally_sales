import type { ReactNode } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { Database, FileText, Settings, BookOpen, Users, ChevronDown, MessageSquare, Contact, ListTodo, Search, Zap, Target, Layers, FolderOpen } from 'lucide-react';
import { cn } from '../lib/utils';
import { useAppStore } from '../store/appStore';
import { useState, useEffect, useRef } from 'react';
import { companiesApi } from '../api';
import { contactsApi, type Project } from '../api/contacts';
import { SectionErrorBoundary } from './ErrorBoundary';

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

  // Load projects on mount
  useEffect(() => {
    contactsApi.listProjects().then((loaded) => {
      setProjects(loaded);
      // Auto-select first project if none selected
      if (!currentProject && loaded.length > 0) {
        setCurrentProject(loaded[0]);
      }
    }).catch(console.error);
  }, []);

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
    <div className="h-screen flex flex-col bg-[#fafafa] overflow-hidden">
      {/* Top navigation bar */}
      <header className="h-14 bg-white border-b border-neutral-200 flex items-center px-5 flex-shrink-0">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2.5 mr-5">
          <div className="w-8 h-8 rounded-xl bg-black flex items-center justify-center">
            <span className="text-white font-bold text-sm">S</span>
          </div>
          <span className="font-semibold text-neutral-900 text-base tracking-tight">LeadGen</span>
        </Link>

        {/* Project Selector */}
        {projects.length > 0 && (
          <div className="relative mr-4" ref={projectDropdownRef}>
            <button
              onClick={() => setShowProjectDropdown(!showProjectDropdown)}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors text-sm',
                currentProject
                  ? 'bg-violet-50 text-violet-700 hover:bg-violet-100'
                  : 'text-neutral-500 hover:bg-neutral-100'
              )}
            >
              <FolderOpen className="w-3.5 h-3.5" />
              <span className="font-medium max-w-[140px] truncate">
                {currentProject ? currentProject.name : 'All Projects'}
              </span>
              <ChevronDown className="w-3.5 h-3.5" />
            </button>

            {showProjectDropdown && (
              <div className="absolute top-full left-0 mt-1 w-56 bg-white border border-neutral-200 rounded-xl shadow-lg z-50 py-1">
                <div className="px-3 py-2 border-b border-neutral-100">
                  <span className="text-xs font-medium text-neutral-500 uppercase tracking-wider">
                    Filter by Project
                  </span>
                </div>
                <div className="max-h-64 overflow-y-auto py-1">
                  <button
                    onClick={() => { setCurrentProject(null); setShowProjectDropdown(false); }}
                    className={cn(
                      'w-full px-3 py-2 text-left text-sm hover:bg-neutral-50 transition-colors',
                      !currentProject && 'bg-neutral-50 font-medium'
                    )}
                  >
                    All Projects
                  </button>
                  {projects.map((project) => (
                    <button
                      key={project.id}
                      onClick={() => { setCurrentProject(project); setShowProjectDropdown(false); }}
                      className={cn(
                        'w-full px-3 py-2 flex items-center justify-between text-sm hover:bg-neutral-50 transition-colors',
                        currentProject?.id === project.id && 'bg-violet-50'
                      )}
                    >
                      <span className="truncate">{project.name}</span>
                      {currentProject?.id === project.id && (
                        <div className="w-2 h-2 rounded-full bg-violet-500 flex-shrink-0 ml-2" />
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Navigation */}
        <nav className="flex items-center gap-1 overflow-x-auto">
          {navItems.map((item) => {
            // Hide company-scoped items if no company is selected
            if (item.needsCompany && !resolvedCompanyId) {
              return null;
            }

            const isActive = isPathActive(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-all whitespace-nowrap',
                  isActive
                    ? 'bg-black text-white'
                    : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100'
                )}
              >
                <item.icon className="w-4 h-4" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Spacer */}
        <div className="flex-1" />
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
