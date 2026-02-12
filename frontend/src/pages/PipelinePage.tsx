import { useState, useEffect, useCallback } from 'react';
import {
  Layers, Target, Mail, Download, Globe, FileSpreadsheet,
  Loader2, AlertCircle, CheckCircle2, XCircle, Search,
  ExternalLink, Zap, UserPlus, ChevronDown,
  X, Settings2, RefreshCw,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useAppStore } from '../store/appStore';
import {
  pipelineApi,
  type DiscoveredCompany,
  type DiscoveredCompanyDetail,
  type PipelineStats,
  type ExtractedContact,
  type PipelineEventItem,
} from '../api/pipeline';

const statusColors: Record<string, string> = {
  new: 'bg-blue-100 text-blue-800',
  scraped: 'bg-cyan-100 text-cyan-800',
  analyzed: 'bg-yellow-100 text-yellow-800',
  contacts_extracted: 'bg-purple-100 text-purple-800',
  enriched: 'bg-green-100 text-green-800',
  exported: 'bg-emerald-100 text-emerald-800',
  rejected: 'bg-red-100 text-red-800',
};

const statusLabels: Record<string, string> = {
  new: 'New',
  scraped: 'Scraped',
  analyzed: 'Analyzed',
  contacts_extracted: 'Contacts',
  enriched: 'Enriched',
  exported: 'Exported',
  rejected: 'Rejected',
};

interface ProjectOption {
  id: number;
  name: string;
}

export function PipelinePage() {
  const { currentCompany } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [companies, setCompanies] = useState<DiscoveredCompany[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [stats, setStats] = useState<PipelineStats | null>(null);
  const [projects, setProjects] = useState<ProjectOption[]>([]);
  const [projectsLoading, setProjectsLoading] = useState(false);

  // Filters
  const [projectId, setProjectId] = useState<number | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [targetOnly, setTargetOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Selection
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Detail modal
  const [detailId, setDetailId] = useState<number | null>(null);
  const [detail, setDetail] = useState<DiscoveredCompanyDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Action state
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Apollo settings popover
  const [showApolloSettings, setShowApolloSettings] = useState(false);
  const [apolloTitles, setApolloTitles] = useState<string[]>(['CEO', 'Founder', 'Managing Director', 'Owner']);
  const [apolloMaxPeople, setApolloMaxPeople] = useState(5);
  const [apolloMaxCredits, setApolloMaxCredits] = useState(50);
  const [apolloTitleInput, setApolloTitleInput] = useState('');
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);

  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  // Load projects for filter dropdown (fast endpoint from pipeline API)
  useEffect(() => {
    if (!currentCompany) return;
    setProjectsLoading(true);
    pipelineApi.listProjects().then(data => {
      setProjects(data);
    }).catch(() => {}).finally(() => setProjectsLoading(false));
  }, [currentCompany]);

  const loadData = useCallback(async () => {
    if (!currentCompany) return;
    setLoading(true);
    setError(null);
    try {
      const [companiesData, statsData] = await Promise.all([
        pipelineApi.listDiscoveredCompanies({
          project_id: projectId,
          status: statusFilter || undefined,
          is_target: targetOnly ? true : undefined,
          search: searchQuery || undefined,
          page,
          page_size: 50,
        }),
        pipelineApi.getStats(projectId),
      ]);
      setCompanies(companiesData.items);
      setTotal(companiesData.total);
      setStats(statsData);
      setLastRefreshed(new Date());
    } catch (err: any) {
      setError(err.userMessage || 'Failed to load pipeline data');
    } finally {
      setLoading(false);
    }
  }, [projectId, statusFilter, targetOnly, searchQuery, page, currentCompany]);

  useEffect(() => { loadData(); }, [loadData]);


  // Load detail when modal opens
  useEffect(() => {
    if (detailId) {
      setDetailLoading(true);
      pipelineApi.getDiscoveredCompany(detailId)
        .then(setDetail)
        .catch(() => setDetail(null))
        .finally(() => setDetailLoading(false));
    } else {
      setDetail(null);
    }
  }, [detailId]);

  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const s = new Set(prev);
      s.has(id) ? s.delete(id) : s.add(id);
      return s;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === companies.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(companies.map(c => c.id)));
    }
  };

  const selectedCompanyIds = Array.from(selectedIds);

  // ========== Actions ==========

  const handleExtractContacts = async () => {
    if (selectedCompanyIds.length === 0) return;
    setActionLoading('extract');
    try {
      const result = await pipelineApi.extractContacts(selectedCompanyIds);
      alert(`Extracted ${result.contacts_found} contacts from ${result.processed} companies`);
      setSelectedIds(new Set());
      loadData();
    } catch (err: any) {
      alert(err.userMessage || 'Extraction failed');
    } finally {
      setActionLoading(null);
    }
  };

  const handleEnrichApollo = async () => {
    if (selectedCompanyIds.length === 0) return;
    setShowApolloSettings(false);
    setActionLoading('apollo');
    try {
      const result = await pipelineApi.enrichApollo(selectedCompanyIds, {
        maxPeople: apolloMaxPeople,
        titles: apolloTitles,
        maxCredits: apolloMaxCredits,
      });
      alert(
        `Apollo: ${result.people_found} people from ${result.processed} companies\n` +
        `Credits used: ${result.credits_used}` +
        (result.skipped ? ` | Skipped: ${result.skipped} (already enriched)` : '')
      );
      setSelectedIds(new Set());
      loadData();
    } catch (err: any) {
      alert(err.userMessage || 'Apollo enrichment failed');
    } finally {
      setActionLoading(null);
    }
  };

  const handlePromoteToCrm = async () => {
    // Collect all extracted contact IDs from selected companies
    // Need to load details for each selected company
    setActionLoading('promote');
    try {
      const contactIds: number[] = [];
      for (const id of selectedCompanyIds) {
        const d = await pipelineApi.getDiscoveredCompany(id);
        contactIds.push(...d.extracted_contacts.map(ec => ec.id).filter(id => !d.extracted_contacts.find(ec => ec.id === id && ec.contact_id)));
        contactIds.push(...d.extracted_contacts.filter(ec => !ec.contact_id).map(ec => ec.id));
      }

      if (contactIds.length === 0) {
        alert('No unpromoted contacts found. Extract contacts first.');
        setActionLoading(null);
        return;
      }

      const result = await pipelineApi.promoteToCrm(contactIds, projectId);
      alert(`Promoted ${result.promoted} contacts to CRM (${result.skipped} skipped)`);
      setSelectedIds(new Set());
      loadData();
    } catch (err: any) {
      alert(err.userMessage || 'CRM promotion failed');
    } finally {
      setActionLoading(null);
    }
  };

  const buildFilename = (suffix: string) => {
    const projName = projects.find(p => p.id === projectId)?.name || 'all';
    const ts = new Date().toISOString().slice(0, 16).replace('T', '_').replace(':', '-');
    return `${projName}_${suffix}_${ts}.csv`;
  };

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportCsv = async (emailOnly: boolean, phoneOnly: boolean, newOnly: boolean = false) => {
    setExportLoading(true);
    setShowExportMenu(false);
    try {
      const blob = await pipelineApi.exportContactsCsv(projectId, emailOnly, phoneOnly, newOnly);
      const suffix = (newOnly ? 'new_' : '') + (emailOnly ? 'email_contacts' : phoneOnly ? 'phone_contacts' : 'all_contacts');
      downloadBlob(blob, buildFilename(suffix));
    } catch (err: any) {
      alert(err.userMessage || 'CSV export failed');
    } finally {
      setExportLoading(false);
    }
  };

  const handleExportSheet = async (emailOnly: boolean, phoneOnly: boolean, newOnly: boolean = false) => {
    setExportLoading(true);
    setShowExportMenu(false);
    try {
      const result = await pipelineApi.exportContactsSheet(projectId, emailOnly, phoneOnly, newOnly);
      window.open(result.url, '_blank');
    } catch (err: any) {
      alert(err.response?.data?.detail || err.userMessage || 'Google Sheets export failed');
    } finally {
      setExportLoading(false);
    }
  };

  const handleReject = async () => {
    if (selectedCompanyIds.length === 0) return;
    setActionLoading('reject');
    try {
      await pipelineApi.updateStatus(selectedCompanyIds, 'rejected');
      setSelectedIds(new Set());
      loadData();
    } catch (err: any) {
      alert(err.userMessage || 'Status update failed');
    } finally {
      setActionLoading(null);
    }
  };

  if (!currentCompany) {
    return (
      <div className="p-6 max-w-[1400px] mx-auto">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-blue-700 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          Select a company to view the pipeline
        </div>
      </div>
    );
  }

  if (loading && companies.length === 0) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <Loader2 className="w-6 h-6 animate-spin text-neutral-400" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Pipeline</h1>
          <p className="text-neutral-500 text-sm mt-1">
            Manage discovered companies through the outreach pipeline
            {lastRefreshed && (
              <span className="ml-2 text-xs text-neutral-400">
                {lastRefreshed.toLocaleTimeString('ru-RU')}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg border border-neutral-200 text-neutral-500 hover:bg-neutral-50 disabled:opacity-50"
            title="Refresh data"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin')} />
          </button>
        <div className="relative">
          <button
            onClick={() => setShowExportMenu(!showExportMenu)}
            disabled={exportLoading}
            className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {exportLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            Export
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
          {showExportMenu && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setShowExportMenu(false)} />
              <div className="absolute right-0 top-full mt-1 z-20 w-72 bg-white rounded-lg shadow-lg border border-neutral-200 py-1 max-h-[70vh] overflow-y-auto">
                <div className="px-3 py-1.5 text-xs font-medium text-neutral-400 uppercase">All Targets</div>
                <button onClick={() => handleExportCsv(true, false)} className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 flex items-center gap-2">
                  <Mail className="w-4 h-4 text-blue-500" /> CSV — All with Email
                </button>
                <button onClick={() => handleExportSheet(true, false)} className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 flex items-center gap-2">
                  <FileSpreadsheet className="w-4 h-4 text-green-600" /> Sheet — All with Email
                </button>
                <button onClick={() => handleExportCsv(false, false)} className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 flex items-center gap-2">
                  <Download className="w-4 h-4 text-neutral-400" /> CSV — All Contacts
                </button>
                <div className="border-t border-neutral-100 my-1" />
                <div className="px-3 py-1.5 text-xs font-medium text-emerald-600 uppercase">New Only (not in campaigns)</div>
                <button onClick={() => handleExportCsv(true, false, true)} className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 flex items-center gap-2">
                  <Mail className="w-4 h-4 text-emerald-500" /> CSV — New with Email
                </button>
                <button onClick={() => handleExportSheet(true, false, true)} className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 flex items-center gap-2">
                  <FileSpreadsheet className="w-4 h-4 text-emerald-600" /> Sheet — New with Email
                </button>
                <button onClick={() => handleExportCsv(false, false, true)} className="w-full text-left px-3 py-2 text-sm hover:bg-neutral-50 flex items-center gap-2">
                  <Download className="w-4 h-4 text-emerald-400" /> CSV — All New Contacts
                </button>
              </div>
            </>
          )}
        </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4" /> {error}
        </div>
      )}

      {/* Stats cards */}
      {stats && (
        <div className="space-y-3">
          <div className="grid grid-cols-5 gap-3">
            <PipelineStatCard label="Discovered" value={stats.total_discovered} icon={Layers} />
            <PipelineStatCard label="Targets" value={stats.targets} icon={Target} color="green" />
            <PipelineStatCard label="New Targets" value={stats.targets_new} icon={CheckCircle2} color="emerald" subtitle="not in campaigns" />
            <PipelineStatCard label="In Campaigns" value={stats.targets_in_campaigns} icon={Mail} color="blue" subtitle="already contacted" />
            <PipelineStatCard label="Rejected" value={stats.rejected} icon={XCircle} color="red" />
          </div>
          {/* Contact breakdown */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-white rounded-xl border border-neutral-200 p-4">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-orange-500" />
                <span className="text-sm font-medium text-neutral-700">Apollo Enrichment</span>
                <span className="ml-auto text-xs text-neutral-400">{stats.apollo_contacts} credits used</span>
              </div>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <div className="text-xl font-bold text-neutral-900">{stats.apollo_contacts.toLocaleString()}</div>
                  <div className="text-xs text-neutral-500">contacts</div>
                </div>
                <div>
                  <div className="text-xl font-bold text-blue-600">{stats.apollo_with_email.toLocaleString()}</div>
                  <div className="text-xs text-neutral-500">with email</div>
                </div>
                <div>
                  <div className="text-xl font-bold text-sky-600">{stats.apollo_with_linkedin.toLocaleString()}</div>
                  <div className="text-xs text-neutral-500">with LinkedIn</div>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-xl border border-neutral-200 p-4">
              <div className="flex items-center gap-2 mb-2">
                <Globe className="w-4 h-4 text-purple-500" />
                <span className="text-sm font-medium text-neutral-700">Website Scraping</span>
              </div>
              <div className="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <div className="text-xl font-bold text-neutral-900">{stats.website_contacts.toLocaleString()}</div>
                  <div className="text-xs text-neutral-500">contacts</div>
                </div>
                <div>
                  <div className="text-xl font-bold text-blue-600">{stats.website_with_email.toLocaleString()}</div>
                  <div className="text-xs text-neutral-500">with email</div>
                </div>
                <div>
                  <div className="text-xl font-bold text-green-600">{stats.website_with_phone.toLocaleString()}</div>
                  <div className="text-xs text-neutral-500">with phone</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Project filter */}
        <select
          value={projectId || ''}
          onChange={e => { setProjectId(e.target.value ? parseInt(e.target.value) : undefined); setPage(1); }}
          className="px-3 py-1.5 text-sm rounded-lg border border-neutral-200 bg-white"
        >
          <option value="">All Projects</option>
          {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>

        {/* Status filter */}
        <select
          value={statusFilter}
          onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
          className="px-3 py-1.5 text-sm rounded-lg border border-neutral-200 bg-white"
        >
          <option value="">All Statuses</option>
          {Object.entries(statusLabels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>

        {/* Target only */}
        <label className="flex items-center gap-1.5 text-sm text-neutral-600 cursor-pointer">
          <input
            type="checkbox"
            checked={targetOnly}
            onChange={e => { setTargetOnly(e.target.checked); setPage(1); }}
            className="rounded"
          />
          Targets only
        </label>

        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={e => { setSearchQuery(e.target.value); setPage(1); }}
            placeholder="Search domain or name..."
            className="w-full pl-9 pr-3 py-1.5 text-sm rounded-lg border border-neutral-200 bg-white"
          />
        </div>

        <span className="text-sm text-neutral-400 ml-auto">{total} companies</span>
      </div>

      {/* Bulk action toolbar */}
      {selectedIds.size > 0 && (
        <div className="bg-black text-white rounded-xl px-4 py-3 flex items-center gap-3">
          <span className="text-sm font-medium">{selectedIds.size} selected</span>
          <div className="w-px h-5 bg-white/20" />
          <button
            onClick={handleExtractContacts}
            disabled={!!actionLoading}
            className="flex items-center gap-1.5 px-3 py-1 text-sm rounded-lg bg-white/10 hover:bg-white/20 disabled:opacity-50"
          >
            {actionLoading === 'extract' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Mail className="w-3.5 h-3.5" />}
            Extract Contacts
          </button>
          <div className="relative">
            <button
              onClick={() => setShowApolloSettings(!showApolloSettings)}
              disabled={!!actionLoading}
              className="flex items-center gap-1.5 px-3 py-1 text-sm rounded-lg bg-white/10 hover:bg-white/20 disabled:opacity-50"
            >
              {actionLoading === 'apollo' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
              Enrich Apollo
              <Settings2 className="w-3 h-3 opacity-50" />
            </button>
            {showApolloSettings && (
              <div className="absolute bottom-full left-0 mb-2 w-80 bg-white text-neutral-900 rounded-xl shadow-xl border border-neutral-200 p-4 z-50" onClick={e => e.stopPropagation()}>
                <div className="text-sm font-semibold mb-3">Apollo Settings</div>

                {/* Title filters */}
                <div className="mb-3">
                  <label className="text-xs text-neutral-500 block mb-1">Role/Title Filters</label>
                  <div className="flex flex-wrap gap-1 mb-2">
                    {apolloTitles.map((t, i) => (
                      <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 bg-purple-50 text-purple-700 rounded text-xs">
                        {t}
                        <button onClick={() => setApolloTitles(prev => prev.filter((_, j) => j !== i))} className="hover:text-purple-900">
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                    {apolloTitles.length === 0 && <span className="text-xs text-neutral-400">No filter (all roles)</span>}
                  </div>
                  <div className="flex gap-1">
                    <input
                      type="text"
                      value={apolloTitleInput}
                      onChange={e => setApolloTitleInput(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter' && apolloTitleInput.trim()) {
                          setApolloTitles(prev => [...prev, apolloTitleInput.trim()]);
                          setApolloTitleInput('');
                        }
                      }}
                      placeholder="Add role..."
                      className="flex-1 px-2 py-1 text-xs rounded border border-neutral-200 bg-white"
                    />
                    <button
                      onClick={() => {
                        if (apolloTitleInput.trim()) {
                          setApolloTitles(prev => [...prev, apolloTitleInput.trim()]);
                          setApolloTitleInput('');
                        }
                      }}
                      className="px-2 py-1 text-xs bg-neutral-100 rounded hover:bg-neutral-200"
                    >Add</button>
                  </div>
                </div>

                {/* Max people per company */}
                <div className="mb-3">
                  <label className="text-xs text-neutral-500 block mb-1">Max people per company</label>
                  <input
                    type="number"
                    min={1} max={25}
                    value={apolloMaxPeople}
                    onChange={e => setApolloMaxPeople(parseInt(e.target.value) || 5)}
                    className="w-full px-2 py-1 text-xs rounded border border-neutral-200"
                  />
                </div>

                {/* Max credits */}
                <div className="mb-3">
                  <label className="text-xs text-neutral-500 block mb-1">Max credits (1 credit = 1 domain lookup)</label>
                  <input
                    type="number"
                    min={1}
                    value={apolloMaxCredits}
                    onChange={e => setApolloMaxCredits(parseInt(e.target.value) || 50)}
                    className="w-full px-2 py-1 text-xs rounded border border-neutral-200"
                  />
                </div>

                {/* Summary */}
                <div className="text-xs text-neutral-500 mb-3 bg-neutral-50 rounded-lg p-2">
                  Will search <strong>{Math.min(selectedIds.size, apolloMaxCredits)}</strong> domains,
                  up to <strong>{apolloMaxPeople}</strong> people each
                  {apolloTitles.length > 0 && <>, filtered by: <strong>{apolloTitles.join(', ')}</strong></>}
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={handleEnrichApollo}
                    className="flex-1 px-3 py-1.5 text-xs font-medium bg-purple-600 text-white rounded-lg hover:bg-purple-700"
                  >
                    Run Enrichment
                  </button>
                  <button
                    onClick={() => setShowApolloSettings(false)}
                    className="px-3 py-1.5 text-xs rounded-lg border border-neutral-200 hover:bg-neutral-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
          <button
            onClick={handlePromoteToCrm}
            disabled={!!actionLoading}
            className="flex items-center gap-1.5 px-3 py-1 text-sm rounded-lg bg-white/10 hover:bg-white/20 disabled:opacity-50"
          >
            {actionLoading === 'promote' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <UserPlus className="w-3.5 h-3.5" />}
            Promote to CRM
          </button>
          <button
            onClick={handleReject}
            disabled={!!actionLoading}
            className="flex items-center gap-1.5 px-3 py-1 text-sm rounded-lg bg-red-500/20 hover:bg-red-500/30 disabled:opacity-50"
          >
            {actionLoading === 'reject' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <XCircle className="w-3.5 h-3.5" />}
            Reject
          </button>
          <button
            onClick={() => setSelectedIds(new Set())}
            className="ml-auto p-1 hover:bg-white/10 rounded"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Companies table */}
      <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-neutral-100 text-left text-xs font-medium text-neutral-500 uppercase tracking-wider">
              <th className="px-4 py-3 w-10">
                <input type="checkbox" checked={selectedIds.size === companies.length && companies.length > 0} onChange={toggleSelectAll} className="rounded" />
              </th>
              <th className="px-4 py-3">Domain</th>
              <th className="px-4 py-3">Company</th>
              <th className="px-4 py-3 text-center">Status</th>
              <th className="px-4 py-3 text-center">Target</th>
              <th className="px-4 py-3 text-right">Confidence</th>
              <th className="px-4 py-3 text-right">Contacts</th>
              <th className="px-4 py-3 text-right">Apollo</th>
            </tr>
          </thead>
          <tbody>
            {companies.map((c) => {
              const info = c.company_info || {};
              return (
                <tr
                  key={c.id}
                  className={cn(
                    'border-b border-neutral-50 hover:bg-neutral-50 transition-colors',
                    selectedIds.has(c.id) && 'bg-blue-50/50',
                    c.is_target && !selectedIds.has(c.id) && 'bg-green-50/30'
                  )}
                >
                  <td className="px-4 py-2.5" onClick={e => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(c.id)}
                      onChange={() => toggleSelect(c.id)}
                      className="rounded"
                    />
                  </td>
                  <td className="px-4 py-2.5 cursor-pointer" onClick={() => setDetailId(c.id)}>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-neutral-900">{c.domain}</span>
                      {c.url && (
                        <a href={c.url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}>
                          <ExternalLink className="w-3.5 h-3.5 text-neutral-400 hover:text-blue-500" />
                        </a>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-sm text-neutral-600 cursor-pointer" onClick={() => setDetailId(c.id)}>
                    {c.name || info.name || '-'}
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', statusColors[c.status] || 'bg-gray-100 text-gray-700')}>
                      {statusLabels[c.status] || c.status}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    {c.is_target ? <CheckCircle2 className="w-4 h-4 text-green-600 mx-auto" /> : <XCircle className="w-4 h-4 text-neutral-300 mx-auto" />}
                  </td>
                  <td className="px-4 py-2.5 text-sm text-right">
                    <span className={cn(
                      'font-medium',
                      (c.confidence || 0) >= 0.8 ? 'text-green-700' :
                      (c.confidence || 0) >= 0.5 ? 'text-yellow-700' : 'text-neutral-400'
                    )}>
                      {c.confidence ? `${(c.confidence * 100).toFixed(0)}%` : '-'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-sm text-right text-neutral-600">
                    {c.contacts_count || 0}
                  </td>
                  <td className="px-4 py-2.5 text-sm text-right text-neutral-600">
                    {c.apollo_people_count || 0}
                  </td>
                </tr>
              );
            })}
            {companies.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-12 text-center text-neutral-400">
                  No discovered companies yet. Run a project search first.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 50 && (
        <div className="flex justify-center gap-2">
          <button
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="px-3 py-1.5 text-sm rounded-lg border border-neutral-200 disabled:opacity-40 hover:bg-neutral-50"
          >
            Previous
          </button>
          <span className="px-3 py-1.5 text-sm text-neutral-500">
            Page {page} of {Math.ceil(total / 50)}
          </span>
          <button
            onClick={() => setPage(p => p + 1)}
            disabled={page >= Math.ceil(total / 50)}
            className="px-3 py-1.5 text-sm rounded-lg border border-neutral-200 disabled:opacity-40 hover:bg-neutral-50"
          >
            Next
          </button>
        </div>
      )}

      {/* Detail Modal */}
      {detailId && (
        <DetailModal
          detail={detail}
          loading={detailLoading}
          onClose={() => setDetailId(null)}
        />
      )}
    </div>
  );
}

// ============ Detail Modal ============

function DetailModal({
  detail,
  loading,
  onClose,
}: {
  detail: DiscoveredCompanyDetail | null;
  loading: boolean;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<'info' | 'contacts' | 'events'>('info');

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-neutral-200 flex items-center justify-between">
          <div>
            {detail ? (
              <>
                <h2 className="text-lg font-bold text-neutral-900">{detail.domain}</h2>
                <p className="text-sm text-neutral-500">{detail.name || detail.company_info?.name || 'Unknown company'}</p>
              </>
            ) : (
              <h2 className="text-lg font-bold text-neutral-900">Loading...</h2>
            )}
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-neutral-100 rounded-lg">
            <X className="w-5 h-5 text-neutral-500" />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="w-6 h-6 animate-spin text-neutral-400" />
          </div>
        ) : detail ? (
          <>
            {/* Tabs */}
            <div className="flex gap-1 px-6 border-b border-neutral-200">
              {(['info', 'contacts', 'events'] as const).map(t => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={cn(
                    'px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors capitalize',
                    tab === t ? 'border-black text-neutral-900' : 'border-transparent text-neutral-500 hover:text-neutral-700'
                  )}
                >
                  {t === 'contacts' ? `Contacts (${detail.extracted_contacts.length})` :
                   t === 'events' ? `Events (${detail.events.length})` : 'Info'}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-auto p-6">
              {tab === 'info' && <InfoTab detail={detail} />}
              {tab === 'contacts' && <ContactsTab contacts={detail.extracted_contacts} />}
              {tab === 'events' && <EventsTab events={detail.events} />}
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

function InfoTab({ detail }: { detail: DiscoveredCompanyDetail }) {
  const info = detail.company_info || {};
  return (
    <div className="space-y-4 text-sm">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <span className="text-neutral-500">Domain</span>
          <div className="font-medium">{detail.domain}</div>
        </div>
        <div>
          <span className="text-neutral-500">Status</span>
          <div>
            <span className={cn('px-2 py-0.5 rounded-full text-xs font-medium', statusColors[detail.status] || 'bg-gray-100')}>
              {statusLabels[detail.status] || detail.status}
            </span>
          </div>
        </div>
        <div>
          <span className="text-neutral-500">Target</span>
          <div className="font-medium">{detail.is_target ? 'Yes' : 'No'} {detail.confidence ? `(${(detail.confidence * 100).toFixed(0)}%)` : ''}</div>
        </div>
        <div>
          <span className="text-neutral-500">Industry</span>
          <div className="font-medium">{info.industry || '-'}</div>
        </div>
      </div>
      {detail.reasoning && (
        <div>
          <span className="text-neutral-500 block mb-1">GPT Reasoning</span>
          <p className="text-neutral-700 bg-neutral-50 rounded-lg p-3">{detail.reasoning}</p>
        </div>
      )}
      {info.description && (
        <div>
          <span className="text-neutral-500 block mb-1">Description</span>
          <p className="text-neutral-700">{info.description}</p>
        </div>
      )}
      {info.services && info.services.length > 0 && (
        <div>
          <span className="text-neutral-500 block mb-1">Services</span>
          <div className="flex flex-wrap gap-1">
            {info.services.map((s: string, i: number) => (
              <span key={i} className="px-2 py-0.5 bg-neutral-100 rounded text-xs">{s}</span>
            ))}
          </div>
        </div>
      )}
      {info.location && (
        <div>
          <span className="text-neutral-500">Location</span>
          <div className="font-medium">{info.location}</div>
        </div>
      )}
      {detail.emails_found && detail.emails_found.length > 0 && (
        <div>
          <span className="text-neutral-500 block mb-1">Emails Found</span>
          <div className="flex flex-wrap gap-1">
            {detail.emails_found.map((e, i) => (
              <span key={i} className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs">{e}</span>
            ))}
          </div>
        </div>
      )}
      {detail.phones_found && detail.phones_found.length > 0 && (
        <div>
          <span className="text-neutral-500 block mb-1">Phones Found</span>
          <div className="flex flex-wrap gap-1">
            {detail.phones_found.map((p, i) => (
              <span key={i} className="px-2 py-0.5 bg-green-50 text-green-700 rounded text-xs">{p}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ContactsTab({ contacts }: { contacts: ExtractedContact[] }) {
  if (contacts.length === 0) {
    return <p className="text-neutral-400 text-center py-8">No contacts extracted yet</p>;
  }

  return (
    <div className="space-y-3">
      {contacts.map(c => (
        <div key={c.id} className="border border-neutral-200 rounded-lg p-3 text-sm">
          <div className="flex items-center gap-2 mb-1">
            {c.first_name || c.last_name ? (
              <span className="font-medium text-neutral-900">{[c.first_name, c.last_name].filter(Boolean).join(' ')}</span>
            ) : (
              <span className="text-neutral-400">Unknown name</span>
            )}
            <span className={cn(
              'px-1.5 py-0.5 rounded text-xs',
              c.source === 'apollo' ? 'bg-purple-50 text-purple-700' : 'bg-blue-50 text-blue-700'
            )}>
              {c.source === 'apollo' ? 'Apollo' : 'Website'}
            </span>
            {c.is_verified && <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />}
            {c.contact_id && <span className="text-xs text-green-600 bg-green-50 px-1.5 py-0.5 rounded">In CRM</span>}
          </div>
          <div className="text-neutral-600 space-y-0.5">
            {c.email && <div className="flex items-center gap-1"><Mail className="w-3 h-3" /> {c.email}</div>}
            {c.job_title && <div className="text-neutral-500">{c.job_title}</div>}
            {c.phone && <div className="text-neutral-500">{c.phone}</div>}
            {c.linkedin_url && (
              <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline text-xs">LinkedIn</a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function EventsTab({ events }: { events: PipelineEventItem[] }) {
  if (events.length === 0) {
    return <p className="text-neutral-400 text-center py-8">No events yet</p>;
  }

  return (
    <div className="space-y-2">
      {events.map(e => (
        <div key={e.id} className="flex items-start gap-3 text-sm">
          <div className="w-2 h-2 rounded-full bg-neutral-300 mt-1.5 flex-shrink-0" />
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium text-neutral-700">{e.event_type.replace(/_/g, ' ')}</span>
              <span className="text-xs text-neutral-400">
                {e.created_at ? new Date(e.created_at).toLocaleString('ru-RU') : ''}
              </span>
            </div>
            {e.error_message && <div className="text-red-600 text-xs mt-0.5">{e.error_message}</div>}
            {e.detail && (
              <div className="text-neutral-500 text-xs mt-0.5">
                {Object.entries(e.detail).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(', ')}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ============ Helpers ============

function PipelineStatCard({ label, value, icon: Icon, color, subtitle }: { label: string; value: number; icon: any; color?: string; subtitle?: string }) {
  const colorMap: Record<string, string> = {
    green: 'text-green-600',
    purple: 'text-purple-600',
    blue: 'text-blue-600',
    emerald: 'text-emerald-600',
    red: 'text-red-600',
  };

  return (
    <div className="bg-white rounded-xl border border-neutral-200 p-4">
      <div className="flex items-center gap-2 mb-1">
        <Icon className={cn('w-4 h-4', color ? colorMap[color] : 'text-neutral-400')} />
        <span className="text-xs text-neutral-500">{label}</span>
      </div>
      <div className="text-2xl font-bold text-neutral-900">{value.toLocaleString()}</div>
      {subtitle && <div className="text-[10px] text-neutral-400 mt-0.5">{subtitle}</div>}
    </div>
  );
}
