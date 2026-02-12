import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Pencil, Check, X, Search, Trash2,
  MessageCircle, Loader2, Unlink, FolderOpen,
} from 'lucide-react';
import { contactsApi, type Project } from '../api/contacts';

interface CampaignOption {
  name: string;
  source: string;
}

export function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const projectId = Number(id);

  const [project, setProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [allCampaigns, setAllCampaigns] = useState<CampaignOption[]>([]);

  // Edit name
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState('');
  const [savingName, setSavingName] = useState(false);

  // Campaign picker
  const [campaignSearch, setCampaignSearch] = useState('');
  const [showCampaignDropdown, setShowCampaignDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Delete
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const loadProject = useCallback(async () => {
    if (!projectId) return;
    try {
      const data = await contactsApi.getProject(projectId);
      setProject(data);
      setNameValue(data.name);
    } catch {
      navigate('/projects');
    } finally {
      setIsLoading(false);
    }
  }, [projectId, navigate]);

  const loadCampaigns = useCallback(async () => {
    try {
      const resp = await fetch('/api/contacts/campaigns');
      const data = await resp.json();
      setAllCampaigns(data.campaigns || []);
    } catch {}
  }, []);

  useEffect(() => {
    loadProject();
    loadCampaigns();
  }, [loadProject, loadCampaigns]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowCampaignDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSaveName = async () => {
    if (!project || !nameValue.trim()) return;
    setSavingName(true);
    try {
      const updated = await contactsApi.updateProject(project.id, { name: nameValue.trim() });
      setProject(updated);
      setEditingName(false);
    } catch {}
    setSavingName(false);
  };

  const handleAddCampaign = async (name: string) => {
    if (!project) return;
    const filters = [...(project.campaign_filters || []), name];
    try {
      const updated = await contactsApi.updateProject(project.id, { campaign_filters: filters });
      setProject(updated);
      setCampaignSearch('');
    } catch {}
  };

  const handleRemoveCampaign = async (name: string) => {
    if (!project) return;
    const filters = (project.campaign_filters || []).filter(c => c !== name);
    try {
      const updated = await contactsApi.updateProject(project.id, { campaign_filters: filters });
      setProject(updated);
    } catch {}
  };

  const handleDelete = async () => {
    if (!project) return;
    try {
      await contactsApi.deleteProject(project.id);
      navigate('/projects');
    } catch {}
  };

  const getSource = (campaignName: string): string => {
    const match = allCampaigns.find(c => c.name === campaignName);
    return match?.source || 'unknown';
  };

  const filteredCampaigns = allCampaigns
    .filter(c => c.name.toLowerCase().includes(campaignSearch.toLowerCase()))
    .filter(c => !(project?.campaign_filters || []).includes(c.name))
    .slice(0, 30);

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="text-center py-20 text-neutral-400">Loading project...</div>
      </div>
    );
  }

  if (!project) return null;

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Back + Header */}
      <div>
        <Link
          to="/projects"
          className="inline-flex items-center gap-1.5 text-sm text-neutral-500 hover:text-neutral-900 mb-4 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          All Projects
        </Link>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-50 flex items-center justify-center">
              <FolderOpen className="w-5 h-5 text-violet-600" />
            </div>
            {editingName ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={nameValue}
                  onChange={e => setNameValue(e.target.value)}
                  autoFocus
                  onKeyDown={e => { if (e.key === 'Enter') handleSaveName(); if (e.key === 'Escape') setEditingName(false); }}
                  className="text-2xl font-bold px-2 py-1 border border-neutral-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-500/20"
                />
                <button onClick={handleSaveName} disabled={savingName} className="p-1 text-green-600 hover:text-green-700">
                  <Check className="w-5 h-5" />
                </button>
                <button onClick={() => { setEditingName(false); setNameValue(project.name); }} className="p-1 text-neutral-400 hover:text-neutral-600">
                  <X className="w-5 h-5" />
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold text-neutral-900">{project.name}</h1>
                <button onClick={() => setEditingName(true)} className="p-1 text-neutral-400 hover:text-neutral-700 transition-colors">
                  <Pencil className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>

          {showDeleteConfirm ? (
            <div className="flex items-center gap-2">
              <button onClick={handleDelete} className="px-3 py-1.5 bg-red-500 text-white rounded-lg text-sm font-medium">
                Confirm Delete
              </button>
              <button onClick={() => setShowDeleteConfirm(false)} className="px-3 py-1.5 text-neutral-500 text-sm">
                Cancel
              </button>
            </div>
          ) : (
            <button onClick={() => setShowDeleteConfirm(true)} className="p-2 text-neutral-400 hover:text-red-500 transition-colors" title="Delete project">
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Campaigns Section */}
      <div className="bg-white border border-neutral-200 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-neutral-900">
            Campaigns ({(project.campaign_filters || []).length})
          </h2>
        </div>

        {/* Campaign list with source badges */}
        {(project.campaign_filters || []).length > 0 ? (
          <div className="flex flex-wrap gap-2 mb-4">
            {(project.campaign_filters || []).map(name => {
              const source = getSource(name);
              return (
                <span
                  key={name}
                  className="inline-flex items-center gap-1.5 pl-2 pr-1 py-1 bg-neutral-50 border border-neutral-200 rounded-lg text-sm group"
                >
                  <span className={`text-[10px] font-bold px-1 py-0.5 rounded ${
                    source === 'smartlead' ? 'bg-blue-100 text-blue-700' :
                    source === 'getsales' ? 'bg-green-100 text-green-700' :
                    'bg-neutral-100 text-neutral-500'
                  }`}>
                    {source === 'smartlead' ? 'SL' : source === 'getsales' ? 'GS' : '?'}
                  </span>
                  <span className="text-neutral-700">{name}</span>
                  <button
                    onClick={() => handleRemoveCampaign(name)}
                    className="p-0.5 text-neutral-300 hover:text-red-500 transition-colors opacity-0 group-hover:opacity-100"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </span>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-neutral-400 mb-4">No campaigns linked yet. Add campaigns below.</p>
        )}

        {/* Add campaign search */}
        <div className="relative" ref={dropdownRef}>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
            <input
              type="text"
              value={campaignSearch}
              onChange={e => setCampaignSearch(e.target.value)}
              onFocus={() => setShowCampaignDropdown(true)}
              placeholder="Search campaigns to add..."
              className="w-full pl-9 pr-3 py-2 border border-neutral-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/20"
            />
          </div>
          {showCampaignDropdown && (campaignSearch || filteredCampaigns.length > 0) && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-neutral-200 rounded-lg shadow-lg z-50 max-h-56 overflow-y-auto">
              {filteredCampaigns.length === 0 ? (
                <div className="px-3 py-2 text-xs text-neutral-500">No matching campaigns</div>
              ) : (
                filteredCampaigns.map(c => (
                  <button
                    key={c.name}
                    onClick={() => { handleAddCampaign(c.name); setShowCampaignDropdown(false); }}
                    className="w-full px-3 py-2 text-left text-sm hover:bg-neutral-50 flex items-center gap-2"
                  >
                    <span className={`text-[10px] font-bold px-1 py-0.5 rounded ${
                      c.source === 'smartlead' ? 'bg-blue-100 text-blue-700' :
                      c.source === 'getsales' ? 'bg-green-100 text-green-700' :
                      'bg-neutral-100 text-neutral-500'
                    }`}>
                      {c.source === 'smartlead' ? 'SL' : c.source === 'getsales' ? 'GS' : '?'}
                    </span>
                    <span className="truncate">{c.name}</span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* Telegram Section */}
      <div className="bg-white border border-neutral-200 rounded-xl p-5">
        <h2 className="text-sm font-semibold text-neutral-900 mb-3 flex items-center gap-2">
          <MessageCircle className="w-4 h-4" />
          Telegram Notifications
        </h2>
        <TelegramConnect projectId={project.id} onUpdate={loadProject} />
      </div>
    </div>
  );
}


/* One-click Telegram connect component */
function TelegramConnect({ projectId, onUpdate }: { projectId: number; onUpdate: () => void }) {
  const [status, setStatus] = useState<'idle' | 'waiting' | 'connected'>('idle');
  const [firstName, setFirstName] = useState('');
  const [username, setUsername] = useState('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;
    contactsApi.getTelegramStatus(projectId).then(data => {
      if (cancelled) return;
      if (data.connected) {
        setStatus('connected');
        setFirstName(data.first_name || '');
        setUsername(data.username || '');
      }
    }).catch(() => {});
    return () => { cancelled = true; };
  }, [projectId]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  const handleConnect = () => {
    window.open(`https://t.me/ImpecableBot?start=project_${projectId}`, '_blank');
    setStatus('waiting');
    pollRef.current = setInterval(async () => {
      try {
        const data = await contactsApi.getTelegramStatus(projectId);
        if (data.connected) {
          setStatus('connected');
          setFirstName(data.first_name || '');
          setUsername(data.username || '');
          if (pollRef.current) clearInterval(pollRef.current);
          if (timeoutRef.current) clearTimeout(timeoutRef.current);
          onUpdate();
        }
      } catch {}
    }, 2000);
    timeoutRef.current = setTimeout(() => {
      if (pollRef.current) clearInterval(pollRef.current);
      setStatus(prev => prev === 'waiting' ? 'idle' : prev);
    }, 60000);
  };

  const handleDisconnect = async () => {
    try {
      await contactsApi.disconnectTelegram(projectId);
      setStatus('idle');
      setFirstName('');
      setUsername('');
      onUpdate();
    } catch {}
  };

  if (status === 'connected') {
    return (
      <div className="flex items-center justify-between py-2 px-3 bg-green-50 rounded-lg">
        <div className="flex items-center gap-2 text-sm text-green-700">
          <Check className="w-4 h-4" />
          <span>Connected{firstName ? ` as ${firstName}` : ''}{username ? ` (@${username})` : ''}</span>
        </div>
        <button onClick={handleDisconnect} className="flex items-center gap-1 text-xs text-neutral-400 hover:text-red-500 transition-colors">
          <Unlink className="w-3.5 h-3.5" />
          Disconnect
        </button>
      </div>
    );
  }

  if (status === 'waiting') {
    return (
      <div className="flex items-center gap-3 py-2 px-3 bg-blue-50 rounded-lg">
        <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
        <div className="text-sm text-blue-700">Tap <b>Start</b> in Telegram to connect...</div>
        <button onClick={() => { if (pollRef.current) clearInterval(pollRef.current); if (timeoutRef.current) clearTimeout(timeoutRef.current); setStatus('idle'); }} className="ml-auto text-xs text-neutral-400 hover:text-neutral-600">
          Cancel
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3">
      <button onClick={handleConnect} className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-100 transition-colors">
        <MessageCircle className="w-4 h-4" />
        Connect Telegram
      </button>
      <span className="text-xs text-neutral-400">Get reply notifications in Telegram</span>
    </div>
  );
}
