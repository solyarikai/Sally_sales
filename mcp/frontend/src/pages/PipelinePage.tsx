import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

const API = '/api'

const PHASES = [
  { key: 'gather', label: 'Gather + Dedup', icon: '1' },
  { key: 'blacklist', label: 'Blacklist Check', icon: '2' },
  { key: 'awaiting_scope_ok', label: 'CP1: Scope Review', icon: '!' },
  { key: 'pre_filter', label: 'Pre-Filter', icon: '3' },
  { key: 'scrape', label: 'Website Scraping', icon: '4' },
  { key: 'analyze', label: 'AI Analysis', icon: '5' },
  { key: 'awaiting_targets_ok', label: 'CP2: Target Review', icon: '!' },
  { key: 'prepare_verification', label: 'Prepare Verification', icon: '6' },
  { key: 'awaiting_verify_ok', label: 'CP3: Cost Approval', icon: '!' },
  { key: 'verified', label: 'Verified', icon: '7' },
  { key: 'completed', label: 'Completed', icon: '8' },
]

export default function PipelinePage() {
  const { runId } = useParams()
  const [run, setRun] = useState<any>(null)
  const [companies, setCompanies] = useState<any[]>([])
  const [error, setError] = useState('')

  const loadRun = async () => {
    if (!runId) return
    try {
      const res = await fetch(`${API}/pipeline/runs/${runId}`)
      if (!res.ok) { setError(`Error ${res.status}: ${res.statusText}`); return }
      const data = await res.json()
      setRun(data)
      setError('')
    } catch (e: any) {
      setError(e.message)
    }
  }

  const loadCompanies = async () => {
    if (!runId) return
    try {
      const res = await fetch(`${API}/pipeline/runs/${runId}/companies`)
      if (res.ok) setCompanies(await res.json())
    } catch {}
  }

  useEffect(() => { loadRun(); loadCompanies() }, [runId])
  useEffect(() => { const t = setInterval(loadRun, 10000); return () => clearInterval(t) }, [runId])

  const currentIdx = run ? PHASES.findIndex(p => p.key === run.current_phase) : -1
  const pendingGates = run?.gates?.filter((g: any) => g.status === 'pending') || []
  const approvedGates = run?.gates?.filter((g: any) => g.status === 'approved') || []

  return (
    <div className="max-w-5xl mx-auto p-6 md:p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold">Pipeline Run #{runId}</h2>
          {run && <div className="text-sm text-gray-400 mt-1">Project: {run.project_name} | Source: {run.source_type}</div>}
        </div>
        <button className="px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 rounded" onClick={() => { loadRun(); loadCompanies() }}>Refresh</button>
      </div>

      {error && <div className="bg-red-900/30 border border-red-700 rounded p-3 mb-6 text-red-300 text-sm">{error}</div>}

      {!run ? (
        <div className="text-gray-500">Loading...</div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Phase stepper */}
          <div className="lg:col-span-1">
            <div className="bg-gray-900 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-400 mb-3 uppercase tracking-wider">Phases</h3>
              <div className="space-y-0.5">
                {PHASES.map((phase, idx) => {
                  const done = idx < currentIdx
                  const active = idx === currentIdx
                  const isCheckpoint = phase.icon === '!'
                  return (
                    <div key={phase.key} className={`flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors
                      ${active ? 'bg-blue-900/60 text-blue-200 font-medium' : ''}
                      ${done ? 'text-green-400' : ''}
                      ${!done && !active ? 'text-gray-600' : ''}
                      ${isCheckpoint && active ? 'bg-yellow-900/40 text-yellow-300' : ''}
                    `}>
                      <span className={`w-6 h-6 flex items-center justify-center rounded-full text-xs font-bold
                        ${done ? 'bg-green-900 text-green-300' : ''}
                        ${active ? (isCheckpoint ? 'bg-yellow-800 text-yellow-200' : 'bg-blue-800 text-blue-200') : ''}
                        ${!done && !active ? 'bg-gray-800 text-gray-600' : ''}
                      `}>
                        {done ? '✓' : phase.icon}
                      </span>
                      <span>{phase.label}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* Right: Details */}
          <div className="lg:col-span-2 space-y-4">
            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: 'Companies', value: run.total_companies, color: 'text-white' },
                { label: 'New', value: run.new_companies, color: 'text-green-400' },
                { label: 'Rejected', value: run.rejected, color: 'text-red-400' },
                { label: 'Scraped', value: `${run.scraped_ok}/${run.scraped_ok + run.scraped_errors}`, color: 'text-blue-400' },
              ].map(s => (
                <div key={s.label} className="bg-gray-900 rounded-lg p-3">
                  <div className="text-xs text-gray-500 uppercase">{s.label}</div>
                  <div className={`text-2xl font-bold ${s.color}`}>{s.value || 0}</div>
                </div>
              ))}
            </div>

            {/* Pending checkpoints */}
            {pendingGates.length > 0 && (
              <div className="border-2 border-yellow-700 bg-yellow-900/20 rounded-lg p-4">
                <h3 className="font-bold text-yellow-300 mb-3 text-lg">Awaiting Approval</h3>
                {pendingGates.map((g: any) => (
                  <div key={g.gate_id} className="mb-3">
                    <div className="text-sm font-medium text-yellow-200">{g.label} (Gate #{g.gate_id})</div>
                    {g.scope && (
                      <pre className="text-xs text-gray-400 mt-1 bg-gray-900 rounded p-2 overflow-x-auto">
                        {JSON.stringify(g.scope, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
                <div className="text-xs text-gray-500 mt-2">Approve via MCP client or API</div>
              </div>
            )}

            {/* Approved checkpoints */}
            {approvedGates.length > 0 && (
              <div className="bg-gray-900 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-400 mb-2 uppercase tracking-wider">Approved Checkpoints</h3>
                {approvedGates.map((g: any) => (
                  <div key={g.gate_id} className="flex items-center gap-2 text-sm text-green-400 py-1">
                    <span>✓</span>
                    <span>{g.label}</span>
                    {g.decided_at && <span className="text-gray-600 text-xs">({new Date(g.decided_at).toLocaleString()})</span>}
                  </div>
                ))}
              </div>
            )}

            {/* Companies table */}
            {companies.length > 0 && (
              <div className="bg-gray-900 rounded-lg p-4">
                <h3 className="text-sm font-medium text-gray-400 mb-3 uppercase tracking-wider">
                  Companies ({companies.length})
                </h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 text-xs uppercase">
                        <th className="pb-2 pr-3">Domain</th>
                        <th className="pb-2 pr-3">Name</th>
                        <th className="pb-2 pr-3">Industry</th>
                        <th className="pb-2 pr-3">Size</th>
                        <th className="pb-2">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {companies.map((c: any) => (
                        <tr key={c.id} className="border-t border-gray-800">
                          <td className="py-2 pr-3 text-blue-400">{c.domain}</td>
                          <td className="py-2 pr-3">{c.name || '-'}</td>
                          <td className="py-2 pr-3 text-gray-500">{c.industry || '-'}</td>
                          <td className="py-2 pr-3 text-gray-500">{c.employee_count || '-'}</td>
                          <td className="py-2">
                            {c.is_blacklisted ? <span className="text-red-400">Blacklisted</span> :
                             c.is_target === true ? <span className="text-green-400">Target</span> :
                             c.is_target === false ? <span className="text-gray-500">Rejected</span> :
                             <span className="text-gray-600">Pending</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Run info */}
            <div className="text-xs text-gray-600">
              Status: {run.status} | Phase: {run.current_phase} | Credits: {run.credits_used || 0} | Created: {run.created_at ? new Date(run.created_at).toLocaleString() : '-'}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
