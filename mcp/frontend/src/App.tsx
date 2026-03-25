import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import { useState, useEffect, createContext, useContext } from 'react'
import SetupPage from './pages/SetupPage'
import PipelinePage from './pages/PipelinePage'
import CRMPage from './pages/CRMPage'

// Theme context
const ThemeCtx = createContext({ dark: true, toggle: () => {} })
export const useTheme = () => useContext(ThemeCtx)

function NavLink({ to, children }: { to: string; children: React.ReactNode }) {
  const loc = useLocation()
  const active = loc.pathname === to || loc.pathname.startsWith(to + '/')
  return (
    <Link to={to} className={`px-2.5 py-1 rounded text-[13px] font-medium transition-colors whitespace-nowrap ${active ? 'bg-[--active-bg] text-[--text]' : 'text-[--text-muted] hover:text-[--text] hover:bg-[--btn-hover]'}`}>
      {children}
    </Link>
  )
}

export default function App() {
  const [dark, setDark] = useState(() => localStorage.getItem('mcp-theme') !== 'light')
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('mcp-theme', dark ? 'dark' : 'light')
  }, [dark])

  return (
    <ThemeCtx.Provider value={{ dark, toggle: () => setDark(d => !d) }}>
      <BrowserRouter>
        <div className="min-h-screen" style={{ background: 'var(--bg)', color: 'var(--text)' }}>
          {/* Header — same style as main app */}
          <header className="h-12 border-b flex items-center px-4 flex-shrink-0" style={{ background: 'var(--bg-header)', borderColor: 'var(--border)' }}>
            <Link to="/" className="flex items-center gap-2 mr-4">
              <div className="w-6 h-6 rounded flex items-center justify-center" style={{ background: dark ? '#d4d4d4' : '#333' }}>
                <span className="font-bold text-[11px]" style={{ color: dark ? '#1e1e1e' : 'white' }}>M</span>
              </div>
              <span className="font-medium text-[13px]" style={{ color: 'var(--text-secondary)' }}>MCP LeadGen</span>
            </Link>
            <nav className="flex items-center gap-0.5 overflow-x-auto">
              <NavLink to="/setup">Setup</NavLink>
              <NavLink to="/runs">Pipeline</NavLink>
              <NavLink to="/crm">CRM</NavLink>
            </nav>
            <div className="ml-auto">
              <button onClick={() => setDark(d => !d)} className="p-1.5 rounded transition-colors text-[13px]" style={{ color: 'var(--text-muted)' }}>
                {dark ? 'light' : 'dark'}
              </button>
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
    </ThemeCtx.Provider>
  )
}

function RunsPage() {
  const [runs, setRuns] = useState<any[]>([])
  useEffect(() => { fetch('/api/pipeline/runs').then(r => r.json()).then(setRuns).catch(() => {}) }, [])

  return (
    <div className="max-w-5xl mx-auto p-6">
      <h2 className="text-[13px] font-medium uppercase tracking-wider mb-4" style={{ color: 'var(--text-muted)' }}>Pipeline Runs</h2>
      {runs.length === 0 ? (
        <div style={{ color: 'var(--text-muted)' }}>No runs yet. Start a gathering via MCP client.</div>
      ) : (
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left uppercase tracking-wider" style={{ color: 'var(--text-muted)', fontSize: '11px' }}>
              <th className="pb-2 pr-4">ID</th>
              <th className="pb-2 pr-4">Source</th>
              <th className="pb-2 pr-4">Companies</th>
              <th className="pb-2 pr-4">Phase</th>
              <th className="pb-2">Created</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r: any) => (
              <tr key={r.id} className="border-t" style={{ borderColor: 'var(--border)' }}>
                <td className="py-2 pr-4"><Link to={`/pipeline/${r.id}`} style={{ color: 'var(--text-link)' }}>#{r.id}</Link></td>
                <td className="py-2 pr-4">{r.source_type}</td>
                <td className="py-2 pr-4" style={{ color: 'var(--success)' }}>{r.new_companies || 0}</td>
                <td className="py-2 pr-4"><span className="px-1.5 py-0.5 rounded text-[11px]" style={{ background: 'var(--active-bg)' }}>{r.phase}</span></td>
                <td className="py-2" style={{ color: 'var(--text-muted)' }}>{r.created_at ? new Date(r.created_at).toLocaleString() : ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
