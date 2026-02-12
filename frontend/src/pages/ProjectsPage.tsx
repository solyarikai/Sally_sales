import { useEffect, useState, useCallback, useRef } from 'react';
import { FolderOpen, Plus, Trash2, X, Search, Pencil, ChevronDown, ChevronUp } from 'lucide-react';
import { contactsApi, type ProjectLite } from '../api/contacts';

interface CampaignOption {
  name: string;
  source: string;
}

export function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectLite[]>([]);
  const [allCampaigns, setAllCampaigns] = useState<CampaignOption[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  // Create form
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newCampaignFilters, setNewCampaignFilters] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);

  // Edit state
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [editCampaignFilters, setEditCampaignFilters] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const [expandedProject, setExpandedProject] = useState<number | null>(null);

  // Delete confirm
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  const loadProjects = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await contactsApi.listProjectsLite();
      setProjects(data);
    } catch (err) {
      console.error('Failed to load projects:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const loadCampaigns = useCallback(async () => {
    try {
      const resp = await fetch('/api/contacts/campaigns');
      const data = await resp.json();
      setAllCampaigns(data.campaigns || []);
    } catch (err) {
      console.error('Failed to load campaigns:', err);
    }
  }, []);

  useEffect(() => {
    loadProjects();
    loadCampaigns();
  }, [loadProjects, loadCampaigns]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await contactsApi.createProject({
        name: newName.trim(),
        campaign_filters: newCampaignFilters,
      });
      setNewName('');
      setNewCampaignFilters([]);
      setShowCreateForm(false);
      await loadProjects();
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to create project';
      alert(detail);
    } finally {
      setCreating(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editingId || !editName.trim()) return;
    setSaving(true);
    try {
      await contactsApi.updateProject(editingId, {
        name: editName.trim(),
        campaign_filters: editCampaignFilters,
      });
      setEditingId(null);
      await loadProjects();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update project');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await contactsApi.deleteProject(id);
      setDeleteConfirm(null);
      await loadProjects();
    } catch (err) {
      console.error('Failed to delete project:', err);
    }
  };

  const startEdit = (project: ProjectLite) => {
    setEditingId(project.id);
    setEditName(project.name);
    setEditCampaignFilters(project.campaign_filters || []);
  };

  const toggleCampaign = (
    name: string,
    list: string[],
    setList: (v: string[]) => void
  ) => {
    if (list.includes(name)) {
      setList(list.filter(c => c !== name));
    } else {
      setList([...list, name]);
    }
  };

  return (
    <div className="max-w-5xl mx-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900 flex items-center gap-2">
            <FolderOpen className="w-6 h-6" />
            Projects
          </h1>
          <p className="text-sm text-neutral-500 mt-1">
            Manage projects and their campaign filters. Projects group campaigns for filtering replies and contacts.
          </p>
        </div>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="flex items-center gap-2 px-4 py-2 bg-black text-white rounded-lg text-sm font-medium hover:bg-neutral-800 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Project
        </button>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <div className="bg-white border border-neutral-200 rounded-xl p-5 mb-6">
          <h3 className="font-semibold text-neutral-900 mb-4">Create New Project</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Name</label>
              <input
                type="text"
                value={newName}
                onChange={e => setNewName(e.target.value)}
                placeholder="e.g. Rizzult"
                className="w-full px-3 py-2 border border-neutral-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
              />
            </div>
            <CampaignPicker
              selected={newCampaignFilters}
              allCampaigns={allCampaigns}
              onToggle={(name) => toggleCampaign(name, newCampaignFilters, setNewCampaignFilters)}
              onRemove={(name) => setNewCampaignFilters(newCampaignFilters.filter(c => c !== name))}
            />
            <div className="flex gap-3">
              <button
                onClick={handleCreate}
                disabled={!newName.trim() || creating}
                className="px-4 py-2 bg-black text-white rounded-lg text-sm font-medium hover:bg-neutral-800 disabled:opacity-40 transition-colors"
              >
                {creating ? 'Creating...' : 'Create Project'}
              </button>
              <button
                onClick={() => { setShowCreateForm(false); setNewName(''); setNewCampaignFilters([]); }}
                className="px-4 py-2 text-neutral-600 hover:text-neutral-900 text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Projects List */}
      {isLoading ? (
        <div className="text-center py-12 text-neutral-500">Loading projects...</div>
      ) : projects.length === 0 ? (
        <div className="text-center py-12 text-neutral-500">
          No projects yet. Create one to group campaigns for filtering.
        </div>
      ) : (
        <div className="space-y-3">
          {projects.map(project => (
            <div key={project.id} className="bg-white border border-neutral-200 rounded-xl overflow-hidden">
              {editingId === project.id ? (
                /* Edit Mode */
                <div className="p-5">
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-neutral-700 mb-1">Name</label>
                      <input
                        type="text"
                        value={editName}
                        onChange={e => setEditName(e.target.value)}
                        className="w-full px-3 py-2 border border-neutral-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
                      />
                    </div>
                    <CampaignPicker
                      selected={editCampaignFilters}
                      allCampaigns={allCampaigns}
                      onToggle={(name) => toggleCampaign(name, editCampaignFilters, setEditCampaignFilters)}
                      onRemove={(name) => setEditCampaignFilters(editCampaignFilters.filter(c => c !== name))}
                    />
                    <div className="flex gap-3">
                      <button
                        onClick={handleSaveEdit}
                        disabled={!editName.trim() || saving}
                        className="px-4 py-2 bg-black text-white rounded-lg text-sm font-medium hover:bg-neutral-800 disabled:opacity-40"
                      >
                        {saving ? 'Saving...' : 'Save Changes'}
                      </button>
                      <button
                        onClick={() => setEditingId(null)}
                        className="px-4 py-2 text-neutral-600 hover:text-neutral-900 text-sm"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                /* View Mode */
                <>
                  <div className="px-5 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3 min-w-0 flex-1">
                      <div className="w-9 h-9 rounded-lg bg-violet-50 flex items-center justify-center flex-shrink-0">
                        <FolderOpen className="w-4.5 h-4.5 text-violet-600" />
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-semibold text-neutral-900 truncate">{project.name}</h3>
                        <div className="text-xs text-neutral-500">
                          {(project.campaign_filters || []).length} campaigns
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setExpandedProject(expandedProject === project.id ? null : project.id)}
                        className="p-2 text-neutral-400 hover:text-neutral-700 transition-colors"
                        title="Show campaigns"
                      >
                        {expandedProject === project.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                      <button
                        onClick={() => startEdit(project)}
                        className="p-2 text-neutral-400 hover:text-neutral-700 transition-colors"
                        title="Edit"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
                      {deleteConfirm === project.id ? (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleDelete(project.id)}
                            className="px-2 py-1 bg-red-500 text-white rounded text-xs font-medium"
                          >
                            Delete
                          </button>
                          <button
                            onClick={() => setDeleteConfirm(null)}
                            className="px-2 py-1 text-neutral-500 text-xs"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setDeleteConfirm(project.id)}
                          className="p-2 text-neutral-400 hover:text-red-500 transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                  {/* Expanded campaign list */}
                  {expandedProject === project.id && (project.campaign_filters || []).length > 0 && (
                    <div className="px-5 pb-4 border-t border-neutral-100 pt-3">
                      <div className="text-xs font-medium text-neutral-500 mb-2">Campaign Filters</div>
                      <div className="flex flex-wrap gap-1.5">
                        {(project.campaign_filters || []).map(name => (
                          <span key={name} className="px-2 py-1 bg-neutral-100 text-neutral-700 rounded-md text-xs">
                            {name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* Reusable campaign picker component */
function CampaignPicker({
  selected,
  allCampaigns,
  onToggle,
  onRemove,
}: {
  selected: string[];
  allCampaigns: CampaignOption[];
  onToggle: (name: string) => void;
  onRemove: (name: string) => void;
}) {
  const [search, setSearch] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const filtered = allCampaigns
    .filter(c => c.name.toLowerCase().includes(search.toLowerCase()))
    .filter(c => !selected.includes(c.name))
    .slice(0, 30);

  return (
    <div>
      <label className="block text-sm font-medium text-neutral-700 mb-1">
        Campaign Filters ({selected.length} selected)
      </label>
      {/* Selected chips */}
      {selected.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {selected.map(name => (
            <span
              key={name}
              className="inline-flex items-center gap-1 px-2 py-1 bg-violet-50 text-violet-700 rounded-md text-xs"
            >
              {name}
              <button onClick={() => onRemove(name)} className="hover:text-violet-900">
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      {/* Search + dropdown */}
      <div className="relative" ref={dropdownRef}>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
          <input
            type="text"
            value={search}
            onChange={e => setSearch(e.target.value)}
            onFocus={() => setShowDropdown(true)}
            placeholder="Search campaigns to add..."
            className="w-full pl-9 pr-3 py-2 border border-neutral-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-black/10"
          />
        </div>
        {showDropdown && (search || filtered.length > 0) && (
          <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-neutral-200 rounded-lg shadow-lg z-50 max-h-48 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-3 py-2 text-xs text-neutral-500">No matching campaigns</div>
            ) : (
              filtered.map(c => (
                <button
                  key={c.name}
                  onClick={() => { onToggle(c.name); setSearch(''); }}
                  className="w-full px-3 py-2 text-left text-sm hover:bg-neutral-50 flex items-center justify-between"
                >
                  <span className="truncate">{c.name}</span>
                  <span className="text-xs text-neutral-400 ml-2 flex-shrink-0">{c.source}</span>
                </button>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
