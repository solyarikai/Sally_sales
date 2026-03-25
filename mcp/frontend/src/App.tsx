import { BrowserRouter, Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom'
import { useState, useEffect, createContext, useContext, useRef } from 'react'
import SetupPage from './pages/SetupPage'
import PipelinePage from './pages/PipelinePage'
import CRMPage from './pages/CRMPage'

// ── Theme ──
const ThemeCtx = createContext({ dark: true, toggle: () => {} })
export const useTheme = () => useContext(ThemeCtx)

// ── Project context (reused across all pages) ──
const ProjectCtx = createContext<{
  project: any | null
  projects: any[]
  setProject: (p: any) => void
  reload: () => void
}>({ project: null, projects: [], setProject: () => {}, reload: () => {} })
export const useProject = () => useContext(ProjectCtx)

// ── Nav link ──
function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const loc = useLocation()
  const active = loc.pathname === to || (to !== '/' && loc.pathname.startsWith(to))
  return (
    <Link to={to} style={{
      padding: '4px 10px', borderRadius: 6, fontSize: 13, fontWeight: 500,
      color: active ? 'var(--text)' : 'var(--text-muted)',
      background: active ? 'var(--active-bg)' : 'transparent',
      transition: 'all 0.15s',
      whiteSpace: 'nowrap',
    }}>{children}</Link>
  )
}

// ── Project selector (top-left, like main app) ──
function ProjectSelector() {
  const { project, projects, setProject } = useProject()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  return (
    <div ref={ref} style={{ position: 'relative', marginRight: 12 }}>
      <button onClick={() => setOpen(!open)} style={{
        display: 'flex', alignItems: 'center', gap: 6,
        padding: '4px 10px', borderRadius: 6, fontSize: 13, fontWeight: 500,
        background: 'var(--active-bg)', color: 'var(--text-secondary)', border: 'none', cursor: 'pointer',
      }}>
        {project ? project.name : 'All projects'}
        <span style={{ fontSize: 10, opacity: 0.5 }}>▼</span>
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 50,
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 8, padding: 4, minWidth: 220, boxShadow: '0 8px 24px rgba(0,0,0,0.3)',
        }}>
          <div onClick={() => { setProject(null); setOpen(false) }} style={{
            padding: '6px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 13,
            color: !project ? 'var(--text)' : 'var(--text-muted)',
            background: !project ? 'var(--active-bg)' : 'transparent',
          }}>All projects</div>
          {projects.map((p: any) => (
            <div key={p.id} onClick={() => { setProject(p); setOpen(false) }} style={{
              padding: '6px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 13,
              color: project?.id === p.id ? 'var(--text)' : 'var(--text-muted)',
              background: project?.id === p.id ? 'var(--active-bg)' : 'transparent',
            }}>{p.name}</div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [dark, setDark] = useState(() => localStorage.getItem('mcp-theme') !== 'light')
  const [project, setProjectState] = useState<any | null>(null)
  const [projects, setProjects] = useState<any[]>([])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('mcp-theme', dark ? 'dark' : 'light')
  }, [dark])

  const loadProjects = () => {
    const token = localStorage.getItem('mcp_token') || ''
    if (!token) return
    fetch('/api/pipeline/projects', { headers: { 'X-MCP-Token': token } })
      .then(r => r.ok ? r.json() : [])
      .then(setProjects)
      .catch(() => {})
  }

  useEffect(() => { loadProjects() }, [])

  const setProject = (p: any) => {
    setProjectState(p)
    if (p) localStorage.setItem('mcp-active-project', String(p.id))
    else localStorage.removeItem('mcp-active-project')
  }

  // Restore active project from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('mcp-active-project')
    if (saved && projects.length > 0) {
      const found = projects.find((p: any) => p.id === Number(saved))
      if (found) setProjectState(found)
    }
  }, [projects])

  return (
    <ThemeCtx.Provider value={{ dark, toggle: () => setDark(d => !d) }}>
      <ProjectCtx.Provider value={{ project, projects, setProject, reload: loadProjects }}>
        <BrowserRouter>
          <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
            {/* Header */}
            <header style={{
              height: 48, borderBottom: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', padding: '0 16px',
              background: 'var(--bg-header)', flexShrink: 0,
            }}>
              <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 8, marginRight: 16, textDecoration: 'none' }}>
                <div style={{
                  width: 24, height: 24, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: dark ? '#d4d4d4' : '#333',
                }}>
                  <span style={{ fontWeight: 700, fontSize: 11, color: dark ? '#1e1e1e' : 'white' }}>M</span>
                </div>
              </Link>

              <ProjectSelector />

              <nav style={{ display: 'flex', alignItems: 'center', gap: 2, overflowX: 'auto' }}>
                <NavLink to="/runs">Pipeline</NavLink>
                <NavLink to="/crm">CRM</NavLink>
                <NavLink to="/setup">Setup</NavLink>
              </nav>

              <div style={{ marginLeft: 'auto' }}>
                <button onClick={() => setDark(d => !d)} style={{
                  padding: '4px 8px', borderRadius: 4, fontSize: 12, border: 'none', cursor: 'pointer',
                  background: 'transparent', color: 'var(--text-muted)',
                }}>{dark ? '☀' : '☾'}</button>
              </div>
            </header>

            <Routes>
              <Route path="/" element={<SetupPage />} />
              <Route path="/setup" element={<SetupPage />} />
              <Route path="/runs" element={<RunsPage />} />
              <Route path="/pipeline/:runId" element={<PipelinePage />} />
              <Route path="/crm" element={<CRMPage />} />
            </Routes>
          </div>
        </BrowserRouter>
      </ProjectCtx.Provider>
    </ThemeCtx.Provider>
  )
}

// ── Runs list page ──
function RunsPage() {
  const [runs, setRuns] = useState<any[]>([])
  useEffect(() => { fetch('/api/pipeline/runs').then(r => r.json()).then(setRuns).catch(() => {}) }, [])

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: 24 }}>
      <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)', marginBottom: 12 }}>Pipeline Runs</div>
      {runs.length === 0 ? (
        <div style={{ color: 'var(--text-muted)', padding: '40px 0', textAlign: 'center' }}>No runs yet. Start a gathering via MCP client.</div>
      ) : (
        <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-muted)' }}>
              <th style={{ paddingBottom: 8 }}>Run</th>
              <th style={{ paddingBottom: 8 }}>Source</th>
              <th style={{ paddingBottom: 8 }}>Companies</th>
              <th style={{ paddingBottom: 8 }}>Phase</th>
              <th style={{ paddingBottom: 8 }}>Created</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r: any) => (
              <tr key={r.id} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={{ padding: '8px 12px 8px 0' }}><Link to={`/pipeline/${r.id}`} style={{ color: 'var(--text-link)' }}>#{r.id}</Link></td>
                <td style={{ padding: '8px 12px 8px 0' }}>{r.source_type?.replace('companies.', '').replace('.manual', '')}</td>
                <td style={{ padding: '8px 12px 8px 0', color: 'var(--success)' }}>{r.new_companies || 0}</td>
                <td style={{ padding: '8px 12px 8px 0' }}><span style={{ padding: '2px 6px', borderRadius: 4, fontSize: 11, background: 'var(--active-bg)' }}>{r.phase}</span></td>
                <td style={{ padding: '8px 0', color: 'var(--text-muted)' }}>{r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
