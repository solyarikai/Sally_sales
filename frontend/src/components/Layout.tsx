import type { ReactNode } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { Database, FileText, Settings, BookOpen, Users, ChevronDown, Building2, MessageSquare, Contact, ListTodo, Search, Zap, Target, Layers, FolderOpen } from 'lucide-react';
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
    currentCompany, companies, setCurrentCompany, setCompanies, resetCompanyData,
    currentProject, projects, setCurrentProject, setProjects,
  } = useAppStore();
  const [showProjectDropdown, setShowProjectDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Auto-resolve company prefix from currentCompany (not URL)
  const resolvedCompanyId = currentCompany?.id;
  const companyPrefix = resolvedCompanyId ? `/company/${resolvedCompanyId}` : '';

  const navItems = [
    { path: '/', icon: Search, label: 'Data Search', global: true },
    { path: '/search-results', icon: Target, label: 'Search Results', global: true },
    { path: '/pipeline', icon: Layers, label: 'Pipeline', global: true },
    { path: `${companyPrefix}/data`, icon: Database, label: 'Data', needsCompany: true },
    { path: `${companyPrefix}/prospects`, icon: Users, label: 'Prospects', needsCompany: true },
    { path: '/contacts', icon: Contact, label: 'CRM', global: true },
    { path: `${companyPrefix}/knowledge-base`, icon: BookOpen, label: 'Knowledge', needsCompany: true },
    { path: '/replies', icon: MessageSquare, label: 'Replies', global: true },
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

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowProjectDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleProjectChange = (project: Project) => {
    setCurrentProject(project);
    setShowProjectDropdown(false);
    // Auto-set company from first company (projects belong to company via API)
    if (companies.length > 0 && !currentCompany) {
      setCurrentCompany(companies[0]);
    }
  };

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
        <div className="relative mr-5" ref={dropdownRef}>
          <button
            onClick={() => setShowProjectDropdown(!showProjectDropdown)}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-neutral-100 transition-colors"
          >
            <div className="w-6 h-6 rounded-lg bg-emerald-50 flex items-center justify-center">
              <FolderOpen className="w-3.5 h-3.5 text-emerald-600" />
            </div>
            <span className="font-medium text-sm max-w-[180px] truncate text-neutral-900">
              {currentProject ? currentProject.name : 'Select Project'}
            </span>
            <ChevronDown className="w-4 h-4 text-neutral-500" />
          </button>

          {showProjectDropdown && (
            <div className="absolute top-full left-0 mt-1 w-72 bg-white border border-neutral-200 rounded-xl shadow-lg z-50 py-1">
              <div className="px-3 py-2 border-b border-neutral-100">
                <span className="text-xs font-medium text-neutral-500 uppercase tracking-wider">
                  Switch Project
                </span>
              </div>
              <div className="max-h-64 overflow-y-auto py-1">
                {projects.length === 0 && (
                  <div className="px-3 py-2 text-sm text-neutral-400">No projects found</div>
                )}
                {projects.map((project) => (
                  <button
                    key={project.id}
                    onClick={() => handleProjectChange(project)}
                    className={cn(
                      'w-full px-3 py-2 flex items-center gap-3 hover:bg-neutral-50 transition-colors',
                      currentProject?.id === project.id && 'bg-neutral-50'
                    )}
                  >
                    <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center flex-shrink-0">
                      <FolderOpen className="w-4 h-4 text-emerald-600" />
                    </div>
                    <div className="flex-1 text-left min-w-0">
                      <div className="font-medium text-neutral-900 text-sm truncate">
                        {project.name}
                      </div>
                      <div className="text-xs text-neutral-500 truncate">
                        {project.target_segments || 'No target segments'}
                      </div>
                    </div>
                    {currentProject?.id === project.id && (
                      <div className="w-2 h-2 rounded-full bg-emerald-500 flex-shrink-0" />
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

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
