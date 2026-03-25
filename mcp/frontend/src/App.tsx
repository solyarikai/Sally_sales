import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { useState, useEffect, createContext, useContext } from 'react'
import SetupPage from './pages/SetupPage'
import PipelinePage from './pages/PipelinePage'

const ThemeContext = createContext({ dark: true, toggle: () => {} })
export const useTheme = () => useContext(ThemeContext)

export default function App() {
  const [dark, setDark] = useState(() => localStorage.getItem('theme') !== 'light')

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])

  const toggle = () => setDark(d => !d)

  return (
    <ThemeContext.Provider value={{ dark, toggle }}>
      <BrowserRouter>
        <div className={`min-h-screen transition-colors ${dark ? 'bg-gray-950 text-gray-100' : 'bg-white text-gray-900'}`}>
          <nav className={`border-b px-6 py-3 flex items-center justify-between ${dark ? 'border-gray-800' : 'border-gray-200'}`}>
            <div className="flex items-center gap-4">
              <Link to="/" className="text-lg font-bold">MCP LeadGen</Link>
              <span className={`text-xs ${dark ? 'text-gray-500' : 'text-gray-400'}`}>v1.0</span>
              <Link to="/" className={`text-sm ${dark ? 'text-gray-400 hover:text-white' : 'text-gray-600 hover:text-black'}`}>Setup</Link>
              <Link to="/runs" className={`text-sm ${dark ? 'text-gray-400 hover:text-white' : 'text-gray-600 hover:text-black'}`}>Runs</Link>
            </div>
            <button
              onClick={toggle}
              className={`px-3 py-1 rounded text-sm ${dark ? 'bg-gray-800 hover:bg-gray-700' : 'bg-gray-100 hover:bg-gray-200'}`}
            >
              {dark ? 'Light' : 'Dark'}
            </button>
          </nav>
          <Routes>
            <Route path="/" element={<SetupPage />} />
            <Route path="/setup" element={<SetupPage />} />
            <Route path="/pipeline/:runId" element={<PipelinePage />} />
            <Route path="/runs" element={<RunsPage />} />
          </Routes>
        </div>
      </BrowserRouter>
    </ThemeContext.Provider>
  )
}

function RunsPage() {
  const { dark } = useTheme()
  const [runs, setRuns] = useState<any[]>([])

  useEffect(() => {
    fetch('/api/pipeline/runs').then(r => r.json()).then(setRuns).catch(() => {})
  }, [])

  return (
    <div className="max-w-4xl mx-auto p-8">
      <h2 className="text-xl font-semibold mb-4">Pipeline Runs</h2>
      {runs.length === 0 ? (
        <div className="text-gray-500">No runs yet. Start a gathering via MCP client.</div>
      ) : (
        <div className="space-y-2">
          {runs.map((r: any) => (
            <Link key={r.id} to={`/pipeline/${r.id}`}
              className={`block rounded-lg p-4 transition-colors ${dark ? 'bg-gray-900 hover:bg-gray-800' : 'bg-gray-50 hover:bg-gray-100'}`}>
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-medium">Run #{r.id}</span>
                  <span className={`ml-3 text-sm ${dark ? 'text-gray-400' : 'text-gray-600'}`}>{r.source_type}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-green-400">{r.new_companies || 0} companies</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${r.status === 'completed' ? 'bg-green-900 text-green-300' : 'bg-blue-900 text-blue-300'}`}>
                    {r.phase || r.status}
                  </span>
                </div>
              </div>
              <div className="text-xs text-gray-500 mt-1">{r.created_at ? new Date(r.created_at).toLocaleString() : ''}</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
