import { BrowserRouter, Routes, Route } from 'react-router-dom'
import SetupPage from './pages/SetupPage'
import PipelinePage from './pages/PipelinePage'

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen">
        <nav className="border-b border-gray-800 px-6 py-3 flex items-center gap-4">
          <h1 className="text-lg font-bold text-white">MCP LeadGen</h1>
          <span className="text-xs text-gray-500">v1.0</span>
        </nav>
        <Routes>
          <Route path="/" element={<SetupPage />} />
          <Route path="/setup" element={<SetupPage />} />
          <Route path="/pipeline/:runId" element={<PipelinePage />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
