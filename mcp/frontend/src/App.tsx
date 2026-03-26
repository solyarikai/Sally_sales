import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import { useState, useEffect, createContext, useContext, useRef } from 'react'
import SetupPage from './pages/SetupPage'
import PipelinePage from './pages/PipelinePage'
import PromptsPage from './pages/PromptsPage'

// REUSED from main app via @main alias — fix once, fixed everywhere
import { ContactsPage as CRMPage } from '@main/pages/ContactsPage'
import { TasksPage } from '@main/pages/TasksPage'
import { ToastProvider } from '@main/components/Toast'

// Theme
const ThemeCtx = createContext({ dark: true, toggle: () => {} })
export const useTheme = () => useContext(ThemeCtx)

// Project context
const ProjectCtx = createContext<{ project: any; projects: any[]; setProject: (p: any) => void; reload: () => void }>({ project: null, projects: [], setProject: () => {}, reload: () => {} })
export const useProject = () => useContext(ProjectCtx)

// Auth
export function getToken() { return localStorage.getItem('mcp_token') || '' }
export function authHeaders() { return { 'X-MCP-Token': getToken(), 'Content-Type': 'application/json' } }

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const loc = useLocation()
  const active = loc.pathname === to || (to !== '/' && to !== '/setup' && loc.pathname.startsWith(to))
  return (
    <Link to={to} style={{
      padding: '4px 10px', borderRadius: 6, fontSize: 13, fontWeight: 500,
      color: active ? 'var(--text)' : 'var(--text-muted)',
      background: active ? 'var(--active-bg)' : 'transparent',
      textDecoration: 'none', whiteSpace: 'nowrap',
    }}>{children}</Link>
  )
}

function ProjectSelector() {
  const { project, projects, setProject } = useProject()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h)
  }, [])

  return (
    <div ref={ref} style={{ position: 'relative', marginRight: 12 }}>
      <button onClick={() => setOpen(!open)} style={{
        display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 6, fontSize: 13, fontWeight: 500,
        background: 'var(--active-bg)', color: 'var(--text-secondary)', border: 'none', cursor: 'pointer',
      }}>
        {project ? project.name : 'All projects'} <span style={{ fontSize: 10, opacity: 0.5 }}>▼</span>
      </button>
      {open && (
        <div style={{ position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 50, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 4, minWidth: 240, boxShadow: '0 8px 24px rgba(0,0,0,0.3)' }}>
          <div onClick={() => { setProject(null); setOpen(false) }} style={{ padding: '6px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 13, color: !project ? 'var(--text)' : 'var(--text-muted)', background: !project ? 'var(--active-bg)' : 'transparent' }}>All projects</div>
          {projects.map((p: any) => (
            <div key={p.id} onClick={() => { setProject(p); setOpen(false) }} style={{ padding: '6px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 13, color: project?.id === p.id ? 'var(--text)' : 'var(--text-muted)', background: project?.id === p.id ? 'var(--active-bg)' : 'transparent' }}>{p.name}</div>
          ))}
        </div>
      )}
    </div>
  )
}

import { useTheme as useThemeStore } from './hooks/useTheme'

export default function App() {
  const { isDark: dark, toggle: toggleTheme } = useThemeStore()
  const [project, setPS] = useState<any>(null)
  const [projects, setProjects] = useState<any[]>([])

  const loadProjects = () => {
    const t = getToken(); if (!t) return
    fetch('/api/pipeline/projects', { headers: { 'X-MCP-Token': t } }).then(r => r.ok ? r.json() : []).then(setProjects)
  }
  useEffect(() => { loadProjects() }, [])

  const setProject = (p: any) => { setPS(p); p ? localStorage.setItem('mcp-project', String(p.id)) : localStorage.removeItem('mcp-project') }
  useEffect(() => { const s = localStorage.getItem('mcp-project'); if (s && projects.length) { const f = projects.find((p: any) => p.id === +s); if (f) setPS(f) } }, [projects])

  return (
    <ThemeCtx.Provider value={{ dark, toggle: toggleTheme }}>
      <ToastProvider>
      <ProjectCtx.Provider value={{ project, projects, setProject, reload: loadProjects }}>
        <BrowserRouter>
          <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: dark ? '#1e1e1e' : '#f5f5f5', color: dark ? '#d4d4d4' : '#333' }}>
            <header style={{ height: 48, borderBottom: `1px solid ${dark ? '#333' : '#e0e0e0'}`, display: 'flex', alignItems: 'center', padding: '0 16px', background: dark ? '#252526' : '#ffffff' }}>
              <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 8, marginRight: 16, textDecoration: 'none' }}>
                <div style={{ width: 24, height: 24, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', background: dark ? '#d4d4d4' : '#333' }}>
                  <span style={{ fontWeight: 700, fontSize: 11, color: dark ? '#1e1e1e' : 'white' }}>M</span>
                </div>
              </Link>
              <ProjectSelector />
              <nav style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <NavLink to="/pipeline">Pipeline</NavLink>
                <NavLink to="/crm">CRM</NavLink>
                <NavLink to="/tasks">Tasks</NavLink>
                <NavLink to="/setup">Setup</NavLink>
              </nav>
              <div style={{ marginLeft: 'auto' }}>
                <button onClick={toggleTheme} style={{ padding: '4px 8px', borderRadius: 4, fontSize: 12, border: 'none', cursor: 'pointer', background: 'transparent', color: 'var(--text-muted)' }}>{dark ? '☀' : '☾'}</button>
              </div>
            </header>
            <div className="mcp-content-area" style={{ flex: 1, overflow: 'hidden', height: 'calc(100vh - 48px)' }}>
              <Routes>
                <Route path="/" element={<PipelineRunsPage />} />
                <Route path="/setup" element={<SetupPage />} />
                <Route path="/pipeline" element={<PipelineRunsPage />} />
                <Route path="/pipeline/:runId" element={<PipelinePage />} />
                <Route path="/pipeline/:runId/prompts" element={<PromptsPage />} />
                <Route path="/crm" element={<CRMPage />} />
                <Route path="/tasks" element={<TasksPage />} />
                <Route path="/tasks/:tab" element={<TasksPage />} />
              </Routes>
            </div>
          </div>
        </BrowserRouter>
      </ProjectCtx.Provider>
      </ToastProvider>
    </ThemeCtx.Provider>
  )
}

// Pipeline runs list
function PipelineRunsPage() {
  const [runs, setRuns] = useState<any[]>([])
  useEffect(() => { fetch('/api/pipeline/runs').then(r => r.json()).then(setRuns).catch(() => {}) }, [])
  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: 24 }}>
      <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)', marginBottom: 12 }}>Pipeline Runs</div>
      {runs.length === 0 ? <div style={{ color: 'var(--text-muted)', padding: '40px 0', textAlign: 'center' }}>No runs yet.</div> : (
        <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
          <thead><tr style={{ textAlign: 'left', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-muted)' }}>
            <th style={{ paddingBottom: 8 }}>Run</th><th style={{ paddingBottom: 8 }}>Source</th><th style={{ paddingBottom: 8 }}>Companies</th><th style={{ paddingBottom: 8 }}>Phase</th><th style={{ paddingBottom: 8 }}>Created</th>
          </tr></thead>
          <tbody>{runs.map((r: any) => (
            <tr key={r.id} style={{ borderTop: '1px solid var(--border)' }}>
              <td style={{ padding: '8px 12px 8px 0' }}><Link to={`/pipeline/${r.id}`} style={{ color: 'var(--text-link)' }}>#{r.id}</Link></td>
              <td style={{ padding: '8px 12px 8px 0' }}>{r.source_type?.replace('companies.', '').replace('.manual', '')}</td>
              <td style={{ padding: '8px 12px 8px 0', color: 'var(--success)' }}>{r.new_companies || 0}</td>
              <td style={{ padding: '8px 12px 8px 0' }}><span style={{ padding: '2px 6px', borderRadius: 4, fontSize: 11, background: 'var(--active-bg)' }}>{r.phase}</span></td>
              <td style={{ padding: '8px 0', color: 'var(--text-muted)' }}>{r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
    </div>
  )
}
