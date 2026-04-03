import { useEffect, useState, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { FolderOpen, Plus, Search, MessageCircle, ChevronRight } from 'lucide-react';
import { contactsApi, type ProjectLite } from '../api/contacts';
import { useTheme } from '../hooks/useTheme';
import { cn } from '../lib/utils';

export function ProjectsPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectLite[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [creating, setCreating] = useState(false);
  const { isDark } = useTheme();

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
          <h1 className={cn("text-2xl font-bold flex items-center gap-2", isDark ? "text-[#d4d4d4]" : "text-neutral-900")}>
            <FolderOpen className="w-6 h-6" />
            Projects
          </h1>
          <p className={cn("text-sm mt-1", isDark ? "text-[#858585]" : "text-neutral-500")}>
            Manage projects and their campaign filters
          </p>
        </div>
        <button
          onClick={handleCreate}
          disabled={creating}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 transition-colors",
            isDark
              ? "bg-[#d4d4d4] text-[#1e1e1e] hover:bg-[#e0e0e0]"
              : "bg-black text-white hover:bg-neutral-800"
          )}
        >
          <Plus className="w-4 h-4" />
          {creating ? 'Creating...' : 'New Project'}
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-5">
        <Search className={cn("absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4", isDark ? "text-[#6e6e6e]" : "text-neutral-400")} />
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search projects..."
          className={cn(
            "w-full pl-9 pr-3 py-2.5 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/20",
            isDark
              ? "bg-[#3c3c3c] border border-transparent text-[#d4d4d4] placeholder-[#6e6e6e] focus:border-[#505050]"
              : "bg-white border border-neutral-200 text-neutral-900 focus:border-violet-300"
          )}
        />
      </div>

      {/* Project List */}
      {isLoading ? (
        <div className={cn("text-center py-12", isDark ? "text-[#858585]" : "text-neutral-500")} data-testid="projects-loading">Loading projects...</div>
      ) : filtered.length === 0 ? (
        <div className={cn("text-center py-12", isDark ? "text-[#858585]" : "text-neutral-500")}>
          {search ? `No projects matching "${search}"` : 'No projects yet. Create one to get started.'}
        </div>
      ) : (
        <div className="space-y-2" data-testid="projects-list">
          {filtered.map(project => (
            <Link
              key={project.id}
              to={`/projects/${project.id}`}
              data-testid="project-card"
              className={cn(
                "flex items-center gap-3 rounded-xl px-5 py-4 transition-all group border",
                isDark
                  ? "bg-[#252526] border-[#333] hover:border-[#505050] hover:bg-[#2d2d2d]"
                  : "bg-white border-neutral-200 hover:border-violet-300 hover:shadow-sm"
              )}
            >
              <div className={cn("w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0", isDark ? "bg-violet-900/30" : "bg-violet-50")}>
                <FolderOpen className={cn("w-4 h-4", isDark ? "text-violet-400" : "text-violet-600")} />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className={cn("font-semibold truncate", isDark ? "text-[#d4d4d4]" : "text-neutral-900")}>{project.name}</h3>
                <div className={cn("text-xs flex items-center gap-3 mt-0.5", isDark ? "text-[#858585]" : "text-neutral-500")}>
                  <span>{(project.campaign_filters || []).length} campaigns</span>
                  {project.telegram_username && (
                    <span className={cn("inline-flex items-center gap-1", isDark ? "text-blue-400" : "text-blue-600")}>
                      <MessageCircle className="w-3 h-3" />
                      @{project.telegram_username}
                    </span>
                  )}
                </div>
              </div>
              <ChevronRight className={cn("w-4 h-4 flex-shrink-0 transition-colors", isDark ? "text-[#4e4e4e] group-hover:text-violet-400" : "text-neutral-300 group-hover:text-violet-500")} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
