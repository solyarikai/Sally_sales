import type { ReactNode } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { Database, FileText, Settings, BookOpen, Users, ChevronDown, Building2, ArrowLeft, MessageSquare } from 'lucide-react';
import { cn } from '../lib/utils';
import { useAppStore } from '../store/appStore';
import { useState, useEffect, useRef } from 'react';
import { companiesApi } from '../api';
import type { CompanyWithStats } from '../types';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { companyId } = useParams<{ companyId: string }>();
  const { currentCompany, companies, setCurrentCompany, setCompanies, resetCompanyData } = useAppStore();
  const [showCompanyDropdown, setShowCompanyDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Build nav items with company prefix
  const companyPrefix = companyId ? `/company/${companyId}` : '';
  const navItems = [
    { path: `${companyPrefix}/data`, icon: Database, label: 'Data' },
    { path: `${companyPrefix}/prospects`, icon: Users, label: 'All Prospects' },
    { path: `${companyPrefix}/knowledge-base`, icon: BookOpen, label: 'Knowledge Base' },
    { path: '/replies', icon: MessageSquare, label: 'Replies' },
    { path: '/templates', icon: FileText, label: 'Prompt Templates' },
    { path: '/settings', icon: Settings, label: 'Settings' },
  ];

  // Load companies on mount if not loaded
  useEffect(() => {
    if (companies.length === 0) {
      companiesApi.listCompanies().then(setCompanies).catch(console.error);
    }
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
          // Company not found, try to load it
          companiesApi.getCompany(numericId)
            .then(setCurrentCompany)
            .catch(() => {
              // Company doesn't exist, redirect to home
              navigate('/');
            });
        }
      }
    }
  }, [companyId, companies]);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowCompanyDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleCompanyChange = (company: CompanyWithStats) => {
    resetCompanyData();
    setCurrentCompany(company);
    setShowCompanyDropdown(false);
    
    // Navigate to the same section in the new company
    const currentPath = location.pathname;
    const pathParts = currentPath.split('/').filter(Boolean);
    
    // Find the section (data, prospects, knowledge-base)
    let section = 'data';
    if (pathParts.includes('prospects')) section = 'prospects';
    else if (pathParts.includes('knowledge-base')) section = 'knowledge-base';
    
    navigate(`/company/${company.id}/${section}`);
  };

  const isPathActive = (path: string) => {
    if (path === '/templates' || path === '/settings') {
      return location.pathname === path;
    }
    return location.pathname.startsWith(path);
  };

  return (
    <div className="h-screen flex flex-col bg-[#fafafa] overflow-hidden">
      {/* Top navigation bar */}
      <header className="h-14 bg-white border-b border-neutral-200 flex items-center px-5 flex-shrink-0">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2.5 mr-6">
          <div className="w-8 h-8 rounded-xl bg-black flex items-center justify-center">
            <span className="text-white font-bold text-sm">S</span>
          </div>
          <span className="font-semibold text-neutral-900 text-base tracking-tight">LeadGen</span>
        </Link>

        {/* Company Selector */}
        {currentCompany && (
          <div className="relative mr-6" ref={dropdownRef}>
            <button
              onClick={() => setShowCompanyDropdown(!showCompanyDropdown)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-neutral-100 transition-colors"
            >
              <div
                className="w-6 h-6 rounded-lg flex items-center justify-center"
                style={{ backgroundColor: `${currentCompany.color || '#3B82F6'}20` }}
              >
                <Building2 className="w-3.5 h-3.5" style={{ color: currentCompany.color || '#3B82F6' }} />
              </div>
              <span className="font-medium text-neutral-900 text-sm max-w-[150px] truncate">
                {currentCompany.name}
              </span>
              <ChevronDown className="w-4 h-4 text-neutral-500" />
            </button>

            {showCompanyDropdown && (
              <div className="absolute top-full left-0 mt-1 w-64 bg-white border border-neutral-200 rounded-xl shadow-lg z-50 py-1">
                <div className="px-3 py-2 border-b border-neutral-100">
                  <span className="text-xs font-medium text-neutral-500 uppercase tracking-wider">
                    Switch Company
                  </span>
                </div>
                <div className="max-h-64 overflow-y-auto py-1">
                  {companies.map((company) => (
                    <button
                      key={company.id}
                      onClick={() => handleCompanyChange(company)}
                      className={cn(
                        'w-full px-3 py-2 flex items-center gap-3 hover:bg-neutral-50 transition-colors',
                        company.id === currentCompany.id && 'bg-neutral-50'
                      )}
                    >
                      <div
                        className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                        style={{ backgroundColor: `${company.color || '#3B82F6'}20` }}
                      >
                        <Building2 className="w-4 h-4" style={{ color: company.color || '#3B82F6' }} />
                      </div>
                      <div className="flex-1 text-left min-w-0">
                        <div className="font-medium text-neutral-900 text-sm truncate">
                          {company.name}
                        </div>
                        <div className="text-xs text-neutral-500">
                          {company.prospects_count.toLocaleString()} prospects
                        </div>
                      </div>
                      {company.id === currentCompany.id && (
                        <div className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0" />
                      )}
                    </button>
                  ))}
                </div>
                <div className="border-t border-neutral-100 pt-1">
                  <Link
                    to="/"
                    onClick={() => setShowCompanyDropdown(false)}
                    className="w-full px-3 py-2 flex items-center gap-2 text-neutral-600 hover:bg-neutral-50 transition-colors text-sm"
                  >
                    <ArrowLeft className="w-4 h-4" />
                    All Companies
                  </Link>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Navigation */}
        <nav className="flex items-center gap-1">
          {navItems.map((item) => {
            // Skip company-scoped items if no company is selected
            if (!currentCompany && item.path.startsWith('/company')) {
              return null;
            }
            
            const isActive = isPathActive(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  'flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all',
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
        {children}
      </main>
    </div>
  );
}
