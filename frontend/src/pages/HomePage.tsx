import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Plus, Building2, Users, Database, FileText, Trash2, Pencil, MoreVertical, Layers, FolderOpen, Search, ChevronLeft } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { companiesApi, environmentsApi } from '../api';
import type { CompanyWithStats, EnvironmentWithStats } from '../types';

// Pastel color palette
const COLORS = [
  '#93C5FD', // Pastel Blue
  '#C4B5FD', // Pastel Purple
  '#F9A8D4', // Pastel Pink
  '#FDBA74', // Pastel Orange
  '#86EFAC', // Pastel Green
  '#67E8F9', // Pastel Cyan
  '#FCD34D', // Pastel Amber
  '#FCA5A5', // Pastel Red
];

function getRandomColor() {
  return COLORS[Math.floor(Math.random() * COLORS.length)];
}

// ============ Environment Modal ============
interface EnvironmentModalProps {
  isOpen: boolean;
  environment?: EnvironmentWithStats | null;
  onClose: () => void;
  onSaved: (env: EnvironmentWithStats) => void;
}

function EnvironmentModal({ isOpen, environment, onClose, onSaved }: EnvironmentModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState(getRandomColor());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEdit = !!environment;

  useEffect(() => {
    if (environment) {
      setName(environment.name);
      setDescription(environment.description || '');
      setColor(environment.color || '#6366F1');
    } else {
      setName('');
      setDescription('');
      setColor(getRandomColor());
    }
  }, [environment, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsLoading(true);
    setError(null);
    try {
      if (isEdit && environment) {
        const updated = await environmentsApi.updateEnvironment(environment.id, {
          name: name.trim(),
          description: description.trim() || undefined,
          color,
        });
        onSaved({ ...updated, companies_count: environment.companies_count });
      } else {
        const created = await environmentsApi.createEnvironment({
          name: name.trim(),
          description: description.trim() || undefined,
          color,
        });
        onSaved({ ...created, companies_count: 0 });
      }
      onClose();
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Failed to save environment';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl w-full max-w-md p-6 shadow-2xl">
        <h2 className="text-xl font-semibold text-neutral-900 mb-6">
          {isEdit ? 'Edit Environment' : 'Create Environment'}
        </h2>
        
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">
              Environment Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Main, Clients, Demo"
              className="w-full px-3 py-2 border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-black/10"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description..."
              rows={2}
              className="w-full px-3 py-2 border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-black/10 resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-2">Color</label>
            <div className="flex gap-2">
              {COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setColor(c)}
                  className={`w-8 h-8 rounded-full transition-transform ${
                    color === c ? 'ring-2 ring-offset-2 ring-neutral-900 scale-110' : ''
                  }`}
                  style={{ backgroundColor: c }}
                />
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || isLoading}
              className="px-4 py-2 text-sm font-medium text-white bg-black rounded-lg hover:bg-neutral-800 transition-colors disabled:opacity-50"
            >
              {isLoading ? 'Saving...' : isEdit ? 'Save' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============ Company Modal ============
interface CompanyModalProps {
  isOpen: boolean;
  company?: CompanyWithStats | null;
  environmentId?: number | null;
  environments: EnvironmentWithStats[];
  onClose: () => void;
  onSaved: (company: CompanyWithStats) => void;
}

function CompanyModal({ isOpen, company, environmentId, environments, onClose, onSaved }: CompanyModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [website, setWebsite] = useState('');
  const [color, setColor] = useState(getRandomColor());
  const [selectedEnvId, setSelectedEnvId] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEdit = !!company;

  useEffect(() => {
    if (company) {
      setName(company.name);
      setDescription(company.description || '');
      setWebsite(company.website || '');
      setColor(company.color || '#3B82F6');
      setSelectedEnvId(company.environment_id);
    } else {
      setName('');
      setDescription('');
      setWebsite('');
      setColor(getRandomColor());
      setSelectedEnvId(environmentId || null);
    }
  }, [company, environmentId, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsLoading(true);
    setError(null);
    try {
      if (isEdit && company) {
        const updated = await companiesApi.updateCompany(company.id, {
          name: name.trim(),
          description: description.trim() || undefined,
          website: website.trim() || undefined,
          color,
          environment_id: selectedEnvId,
        });
        onSaved({
          ...updated,
          prospects_count: company.prospects_count,
          datasets_count: company.datasets_count,
          documents_count: company.documents_count,
        });
      } else {
        const created = await companiesApi.createCompany({
          name: name.trim(),
          description: description.trim() || undefined,
          website: website.trim() || undefined,
          color,
          environment_id: selectedEnvId || undefined,
        });
        onSaved({
          ...created,
          prospects_count: 0,
          datasets_count: 0,
          documents_count: 0,
        });
      }
      onClose();
    } catch (err: any) {
      const message = err?.response?.data?.detail || err?.message || 'Failed to save company';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl w-full max-w-md p-6 shadow-2xl">
        <h2 className="text-xl font-semibold text-neutral-900 mb-6">
          {isEdit ? 'Edit Company' : 'Create Company'}
        </h2>
        
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">
              Company Name *
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Acme Corp"
              className="w-full px-3 py-2 border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-black/10"
              autoFocus
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description..."
              rows={2}
              className="w-full px-3 py-2 border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-black/10 resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">
              Website <span className="text-neutral-400 text-xs">(auto-fetches logo)</span>
            </label>
            <input
              type="text"
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
              placeholder="e.g., acme.com"
              className="w-full px-3 py-2 border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-black/10"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">
              Environment
            </label>
            <select
              value={selectedEnvId || ''}
              onChange={(e) => setSelectedEnvId(e.target.value ? Number(e.target.value) : null)}
              className="w-full px-3 py-2 border border-neutral-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-black/10"
            >
              <option value="">No environment</option>
              {environments.map((env) => (
                <option key={env.id} value={env.id}>{env.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-2">Color</label>
            <div className="flex gap-2">
              {COLORS.map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => setColor(c)}
                  className={`w-8 h-8 rounded-full transition-transform ${
                    color === c ? 'ring-2 ring-offset-2 ring-neutral-900 scale-110' : ''
                  }`}
                  style={{ backgroundColor: c }}
                />
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-neutral-700 hover:bg-neutral-100 rounded-lg transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim() || isLoading}
              className="px-4 py-2 text-sm font-medium text-white bg-black rounded-lg hover:bg-neutral-800 transition-colors disabled:opacity-50"
            >
              {isLoading ? 'Saving...' : isEdit ? 'Save' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ============ Company Card ============
interface CompanyCardProps {
  company: CompanyWithStats;
  onSelect: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

function CompanyCard({ company, onSelect, onEdit, onDelete }: CompanyCardProps) {
  const [showMenu, setShowMenu] = useState(false);

  return (
    <div
      className="bg-white border border-neutral-200 rounded-xl p-5 hover:shadow-lg hover:border-neutral-300 transition-all cursor-pointer relative group"
      onClick={onSelect}
    >
      <div
        className="absolute top-0 left-0 right-0 h-1 rounded-t-xl"
        style={{ backgroundColor: company.color || '#3B82F6' }}
      />

      <div className="absolute top-3 right-3" onClick={(e) => e.stopPropagation()}>
        <button
          onClick={() => setShowMenu(!showMenu)}
          className="p-1.5 rounded-lg hover:bg-neutral-100 opacity-0 group-hover:opacity-100 transition-opacity"
        >
          <MoreVertical className="w-4 h-4 text-neutral-500" />
        </button>
        
        {showMenu && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowMenu(false)} />
            <div className="absolute right-0 mt-1 w-36 bg-white border border-neutral-200 rounded-lg shadow-lg z-20 py-1">
              <button
                onClick={() => { setShowMenu(false); onEdit(); }}
                className="w-full px-3 py-2 text-left text-sm text-neutral-700 hover:bg-neutral-50 flex items-center gap-2"
              >
                <Pencil className="w-4 h-4" /> Edit
              </button>
              <button
                onClick={() => { setShowMenu(false); onDelete(); }}
                className="w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center gap-2"
              >
                <Trash2 className="w-4 h-4" /> Delete
              </button>
            </div>
          </>
        )}
      </div>

      <div
        className={`w-12 h-12 rounded-xl flex items-center justify-center mb-4 overflow-hidden ${
          company.website && !company.logo_url ? 'animate-pulse' : ''
        }`}
        style={{ backgroundColor: company.logo_url ? 'transparent' : `${company.color || '#3B82F6'}20` }}
        title={company.website && !company.logo_url ? 'Loading favicon...' : undefined}
      >
        {company.logo_url ? (
          <img 
            src={company.logo_url} 
            alt={`${company.name} logo`}
            className="w-full h-full object-contain"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
          />
        ) : (
          <Building2 className="w-6 h-6" style={{ color: company.color || '#3B82F6' }} />
        )}
      </div>

      <h3 className="font-semibold text-neutral-900 text-lg mb-1">{company.name}</h3>
      {company.description && (
        <p className="text-sm text-neutral-500 mb-4 line-clamp-2">{company.description}</p>
      )}

      <div className="flex items-center gap-4 text-sm text-neutral-500 mt-4 pt-4 border-t border-neutral-100">
        <div className="flex items-center gap-1.5">
          <Users className="w-4 h-4" />
          <span>{company.prospects_count.toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Database className="w-4 h-4" />
          <span>{company.datasets_count}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <FileText className="w-4 h-4" />
          <span>{company.documents_count}</span>
        </div>
      </div>
    </div>
  );
}

// ============ Main HomePage ============
export function HomePage() {
  const navigate = useNavigate();
  const { 
    companies, setCurrentCompany, addCompany, updateCompany, removeCompany, resetCompanyData,
    environments, setEnvironments, currentEnvironment, setCurrentEnvironment, addEnvironment, updateEnvironment, removeEnvironment
  } = useAppStore();
  
  const [isLoading, setIsLoading] = useState(true);
  const [showEnvModal, setShowEnvModal] = useState(false);
  const [editingEnv, setEditingEnv] = useState<EnvironmentWithStats | null>(null);
  const [showCompanyModal, setShowCompanyModal] = useState(false);
  const [editingCompany, setEditingCompany] = useState<CompanyWithStats | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  // Auto-refresh for favicon updates
  useEffect(() => {
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const environmentsData = await environmentsApi.listEnvironments();
      setEnvironments(environmentsData);
      
      if (currentEnvironment) {
        const envExists = environmentsData.some(e => e.id === currentEnvironment.id);
        if (!envExists) {
          setCurrentEnvironment(environmentsData.length > 0 ? environmentsData[0] : null);
        }
      } else if (environmentsData.length > 0) {
        setCurrentEnvironment(environmentsData[0]);
      }
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectCompany = (company: CompanyWithStats) => {
    resetCompanyData();
    setCurrentCompany(company);
    navigate(`/company/${company.id}/data`);
  };

  const handleDeleteCompany = async (company: CompanyWithStats) => {
    if (!confirm(`Delete "${company.name}"? This cannot be undone.`)) return;
    try {
      await companiesApi.deleteCompany(company.id);
      removeCompany(company.id);
    } catch (error) {
      console.error('Failed to delete company:', error);
    }
  };

  const handleDeleteEnvironment = async (env: EnvironmentWithStats) => {
    if (!confirm(`Delete "${env.name}"? Companies will be moved to unassigned.`)) return;
    try {
      await environmentsApi.deleteEnvironment(env.id);
      removeEnvironment(env.id);
      if (currentEnvironment?.id === env.id) {
        setCurrentEnvironment(environments.find(e => e.id !== env.id) || null);
      }
    } catch (error) {
      console.error('Failed to delete environment:', error);
    }
  };

  const handleEnvSaved = (env: EnvironmentWithStats) => {
    if (editingEnv) {
      updateEnvironment(env);
    } else {
      addEnvironment(env);
      setCurrentEnvironment(env);
    }
    setEditingEnv(null);
  };

  const handleCompanySaved = (company: CompanyWithStats) => {
    if (editingCompany) {
      updateCompany(company);
    } else {
      addCompany(company);
    }
    setEditingCompany(null);
  };

  // Filter companies by current environment
  const currentCompanies = currentEnvironment 
    ? companies.filter(c => c.environment_id === currentEnvironment.id)
    : [];
  
  const unassignedCompanies = companies.filter(c => !c.environment_id);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#fafafa] flex items-center justify-center">
        <div className="text-neutral-500">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#fafafa]">
      {/* Header */}
      <header className="h-14 bg-white border-b border-neutral-200 flex items-center px-6">
        <Link to="/" className="flex items-center gap-2 mr-4 text-neutral-600 hover:text-neutral-900">
          <ChevronLeft className="w-4 h-4" />
          <Search className="w-4 h-4" />
          <span className="text-sm font-medium">Data Search</span>
        </Link>
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-black flex items-center justify-center">
            <span className="text-white font-bold text-sm">S</span>
          </div>
          <span className="font-semibold text-neutral-900 text-base tracking-tight">Companies</span>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        {/* Environments Section */}
        <div className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-neutral-900 flex items-center gap-2">
              <Layers className="w-5 h-5" />
              Environments
            </h2>
            <button
              onClick={() => { setEditingEnv(null); setShowEnvModal(true); }}
              className="text-sm text-neutral-600 hover:text-black flex items-center gap-1"
            >
              <Plus className="w-4 h-4" /> Add
            </button>
          </div>

          {environments.length === 0 ? (
            <div className="bg-white border-2 border-dashed border-neutral-200 rounded-xl p-8 text-center">
              <Layers className="w-12 h-12 text-neutral-300 mx-auto mb-3" />
              <h3 className="font-medium text-neutral-900 mb-1">No environments yet</h3>
              <p className="text-sm text-neutral-500 mb-4">Create an environment to organize your companies</p>
              <button
                onClick={() => { setEditingEnv(null); setShowEnvModal(true); }}
                className="inline-flex items-center gap-2 px-4 py-2 bg-black text-white rounded-lg text-sm hover:bg-neutral-800"
              >
                <Plus className="w-4 h-4" /> Create Environment
              </button>
            </div>
          ) : (
            <div className="flex gap-3 flex-wrap">
              {environments.map((env) => (
                <button
                  key={env.id}
                  onClick={() => setCurrentEnvironment(env)}
                  className={`group relative px-4 py-3 rounded-xl border-2 transition-all ${
                    currentEnvironment?.id === env.id
                      ? 'border-neutral-900 bg-neutral-900 text-white'
                      : 'border-neutral-200 bg-white hover:border-neutral-300'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: env.color || '#6366F1' }}
                    />
                    <span className="font-medium">{env.name}</span>
                    <span className={`text-sm ${currentEnvironment?.id === env.id ? 'text-neutral-300' : 'text-neutral-400'}`}>
                      {env.companies_count}
                    </span>
                  </div>
                  
                  {/* Edit/Delete on hover */}
                  <div 
                    className="absolute -top-2 -right-2 hidden group-hover:flex gap-1"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <button
                      onClick={() => { setEditingEnv(env); setShowEnvModal(true); }}
                      className="w-6 h-6 bg-white border border-neutral-200 rounded-full flex items-center justify-center hover:bg-neutral-50 shadow-sm"
                    >
                      <Pencil className="w-3 h-3 text-neutral-600" />
                    </button>
                    <button
                      onClick={() => handleDeleteEnvironment(env)}
                      className="w-6 h-6 bg-white border border-neutral-200 rounded-full flex items-center justify-center hover:bg-red-50 shadow-sm"
                    >
                      <Trash2 className="w-3 h-3 text-red-500" />
                    </button>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Companies Section */}
        {currentEnvironment && (
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-neutral-900">
                {currentEnvironment.name} Companies
              </h2>
              <button
                onClick={() => { setEditingCompany(null); setShowCompanyModal(true); }}
                className="flex items-center gap-2 px-4 py-2 bg-black text-white rounded-lg text-sm hover:bg-neutral-800"
              >
                <Plus className="w-4 h-4" /> Add Company
              </button>
            </div>

            {currentCompanies.length === 0 ? (
              <div className="bg-white border-2 border-dashed border-neutral-200 rounded-xl p-8 text-center">
                <Building2 className="w-12 h-12 text-neutral-300 mx-auto mb-3" />
                <h3 className="font-medium text-neutral-900 mb-1">No companies in this environment</h3>
                <p className="text-sm text-neutral-500 mb-4">Add a company to get started</p>
                <button
                  onClick={() => { setEditingCompany(null); setShowCompanyModal(true); }}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-black text-white rounded-lg text-sm hover:bg-neutral-800"
                >
                  <Plus className="w-4 h-4" /> Add Company
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {currentCompanies.map((company) => (
                  <CompanyCard
                    key={company.id}
                    company={company}
                    onSelect={() => handleSelectCompany(company)}
                    onEdit={() => { setEditingCompany(company); setShowCompanyModal(true); }}
                    onDelete={() => handleDeleteCompany(company)}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Unassigned Companies */}
        {(unassignedCompanies.length > 0 || !currentEnvironment) && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-neutral-900 flex items-center gap-2">
                <FolderOpen className="w-5 h-5 text-neutral-400" />
                Unassigned Companies
              </h2>
              <button
                onClick={() => { setEditingCompany(null); setShowCompanyModal(true); }}
                className="flex items-center gap-2 px-4 py-2 bg-black text-white rounded-lg text-sm hover:bg-neutral-800"
              >
                <Plus className="w-4 h-4" /> Add Company
              </button>
            </div>
            {unassignedCompanies.length === 0 ? (
              <div className="bg-white border-2 border-dashed border-neutral-200 rounded-xl p-8 text-center">
                <Building2 className="w-12 h-12 text-neutral-300 mx-auto mb-3" />
                <h3 className="font-medium text-neutral-900 mb-1">No companies yet</h3>
                <p className="text-sm text-neutral-500 mb-4">Create a company to get started</p>
                <button
                  onClick={() => { setEditingCompany(null); setShowCompanyModal(true); }}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-black text-white rounded-lg text-sm hover:bg-neutral-800"
                >
                  <Plus className="w-4 h-4" /> Add Company
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
                {unassignedCompanies.map((company) => (
                  <CompanyCard
                    key={company.id}
                    company={company}
                    onSelect={() => handleSelectCompany(company)}
                    onEdit={() => { setEditingCompany(company); setShowCompanyModal(true); }}
                    onDelete={() => handleDeleteCompany(company)}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Modals */}
      <EnvironmentModal
        isOpen={showEnvModal}
        environment={editingEnv}
        onClose={() => { setShowEnvModal(false); setEditingEnv(null); }}
        onSaved={handleEnvSaved}
      />

      <CompanyModal
        isOpen={showCompanyModal}
        company={editingCompany}
        environmentId={currentEnvironment?.id}
        environments={environments}
        onClose={() => { setShowCompanyModal(false); setEditingCompany(null); }}
        onSaved={handleCompanySaved}
      />
    </div>
  );
}

export default HomePage;
