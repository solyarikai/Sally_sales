import { useEffect, useState, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { FolderOpen, Plus, Search, MessageCircle, ChevronRight } from 'lucide-react';
import { contactsApi, type ProjectLite } from '../api/contacts';

export function ProjectsPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectLite[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [creating, setCreating] = useState(false);

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

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const handleCreate = async () => {
    const name = prompt('Project name:');
    if (!name?.trim()) return;
    setCreating(true);
    try {
      const project = await contactsApi.createProject({ name: name.trim() });
      navigate(`/projects/${project.id}`);
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to create project';
      alert(detail);
    } finally {
      setCreating(false);
    }
  };

  const filtered = projects.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900 flex items-center gap-2">
            <FolderOpen className="w-6 h-6" />
            Projects
          </h1>
          <p className="text-sm text-neutral-500 mt-1">
            Manage projects and their campaign filters
          </p>
        </div>
        <button
          onClick={handleCreate}
          disabled={creating}
          className="flex items-center gap-2 px-4 py-2 bg-black text-white rounded-lg text-sm font-medium hover:bg-neutral-800 disabled:opacity-50 transition-colors"
        >
          <Plus className="w-4 h-4" />
          {creating ? 'Creating...' : 'New Project'}
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-5">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search projects..."
          className="w-full pl-9 pr-3 py-2.5 bg-white border border-neutral-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-300"
        />
      </div>

      {/* Project List */}
      {isLoading ? (
        <div className="text-center py-12 text-neutral-500">Loading projects...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-neutral-500">
          {search ? `No projects matching "${search}"` : 'No projects yet. Create one to get started.'}
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(project => (
            <Link
              key={project.id}
              to={`/projects/${project.id}`}
              className="flex items-center gap-3 bg-white border border-neutral-200 rounded-xl px-5 py-4 hover:border-violet-300 hover:shadow-sm transition-all group"
            >
              <div className="w-9 h-9 rounded-lg bg-violet-50 flex items-center justify-center flex-shrink-0">
                <FolderOpen className="w-4 h-4 text-violet-600" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="font-semibold text-neutral-900 truncate">{project.name}</h3>
                <div className="text-xs text-neutral-500 flex items-center gap-3 mt-0.5">
                  <span>{(project.campaign_filters || []).length} campaigns</span>
                  {project.telegram_username && (
                    <span className="inline-flex items-center gap-1 text-blue-600">
                      <MessageCircle className="w-3 h-3" />
                      @{project.telegram_username}
                    </span>
                  )}
                </div>
              </div>
              <ChevronRight className="w-4 h-4 text-neutral-300 group-hover:text-violet-500 transition-colors flex-shrink-0" />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
