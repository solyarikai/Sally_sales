import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

const API = '/api'

const PHASES = [
  { key: 'gather', label: 'Gather + Dedup' },
  { key: 'blacklist', label: 'Blacklist Check' },
  { key: 'awaiting_scope_ok', label: '★ CP1: Scope Review' },
  { key: 'pre_filter', label: 'Pre-Filter' },
  { key: 'scrape', label: 'Website Scraping' },
  { key: 'analyze', label: 'AI Analysis' },
  { key: 'awaiting_targets_ok', label: '★ CP2: Target Review' },
  { key: 'prepare_verification', label: 'Prepare Verification' },
  { key: 'awaiting_verify_ok', label: '★ CP3: Cost Approval' },
  { key: 'verified', label: 'Verified ✓' },
]

export default function PipelinePage() {
  const { runId } = useParams()
  const [run, setRun] = useState<any>(null)
  const token = localStorage.getItem('mcp_token') || ''

  const loadRun = async () => {
    if (!runId) return
    const res = await fetch(`${API}/pipeline/runs/${runId}`, {
      headers: { 'X-MCP-Token': token },
    })
    if (res.ok) setRun(await res.json())
  }

  useEffect(() => { loadRun() }, [runId])

  const currentPhaseIdx = run ? PHASES.findIndex(p => p.key === run.current_phase) : -1

  return (
    <div className="max-w-3xl mx-auto p-8">
      <h2 className="text-xl font-semibold mb-6">Pipeline Run #{runId}</h2>
      {!run ? (
        <div className="text-gray-500">Loading...</div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div><span className="text-gray-500">Status:</span> <span className="text-white">{run.status}</span></div>
            <div><span className="text-gray-500">Phase:</span> <span className="text-white">{run.current_phase}</span></div>
            <div><span className="text-gray-500">Source:</span> <span className="text-white">{run.source_type}</span></div>
          </div>

          <div className="space-y-1">
            {PHASES.map((phase, idx) => {
              const done = idx < currentPhaseIdx
              const active = idx === currentPhaseIdx
              return (
                <div key={phase.key} className={`flex items-center gap-3 px-3 py-2 rounded text-sm ${active ? 'bg-blue-900/50 text-blue-300' : done ? 'text-green-400' : 'text-gray-600'}`}>
                  <span className="w-5 text-center">
                    {done ? '✓' : active ? '→' : '·'}
                  </span>
                  <span>{phase.label}</span>
                </div>
              )
            })}
          </div>

          {run.pending_gates?.length > 0 && (
            <div className="border border-yellow-800 bg-yellow-900/20 rounded p-4">
              <h3 className="font-medium text-yellow-400 mb-2">Pending Approval</h3>
              {run.pending_gates.map((g: any) => (
                <div key={g.gate_id} className="text-sm text-gray-300">
                  Gate #{g.gate_id}: {g.label} ({g.type})
                </div>
              ))}
            </div>
          )}

          <button className="text-sm text-blue-400 hover:text-blue-300" onClick={loadRun}>Refresh</button>
        </div>
      )}
    </div>
  )
}
