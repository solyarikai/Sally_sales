import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

const API = '/api'

const PHASES = [
  { key: 'gather', label: 'Gather + Dedup' },
  { key: 'blacklist', label: 'Blacklist' },
  { key: 'awaiting_scope_ok', label: 'CP1: Scope' },
  { key: 'pre_filter', label: 'Pre-Filter' },
  { key: 'scrape', label: 'Scrape' },
  { key: 'analyze', label: 'Analysis' },
  { key: 'awaiting_targets_ok', label: 'CP2: Targets' },
  { key: 'prepare_verification', label: 'Verification' },
  { key: 'awaiting_verify_ok', label: 'CP3: Cost' },
  { key: 'verified', label: 'Done' },
]

export default function PipelinePage() {
  const { runId } = useParams()
  const [run, setRun] = useState<any>(null)
  const [companies, setCompanies] = useState<any[]>([])
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  const load = async () => {
    if (!runId) return
    const [r1, r2] = await Promise.all([
      fetch(`${API}/pipeline/runs/${runId}`).then(r => r.ok ? r.json() : null),
      fetch(`${API}/pipeline/runs/${runId}/companies`).then(r => r.ok ? r.json() : []),
    ])
    if (r1) setRun(r1)
    if (r2) setCompanies(r2)
  }

  useEffect(() => { load() }, [runId])
  useEffect(() => { const t = setInterval(load, 15000); return () => clearInterval(t) }, [runId])

  const toggle = (id: number) => setExpanded(prev => {
    const n = new Set(prev)
    n.has(id) ? n.delete(id) : n.add(id)
    return n
  })

  const currentIdx = run ? PHASES.findIndex(p => p.key === run.current_phase) : -1
  const filters = run ? (typeof run.filters === 'object' ? run.filters : {}) : {}

  if (!run) return <div className="p-6" style={{ color: 'var(--text-muted)' }}>Loading run #{runId}...</div>

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-5">

      {/* Run header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-wider font-medium" style={{ color: 'var(--text-muted)' }}>Pipeline Run #{runId}</div>
          <h2 className="text-[15px] font-medium mt-0.5">{run.project_name}</h2>
          <div className="text-[12px] mt-1" style={{ color: 'var(--text-muted)' }}>
            {run.source_type} &middot; {run.status} &middot; {run.created_at ? new Date(run.created_at).toLocaleString() : ''}
          </div>
        </div>
        <button onClick={load} className="px-2.5 py-1 rounded text-[12px]" style={{ background: 'var(--active-bg)', color: 'var(--text-secondary)' }}>refresh</button>
      </div>

      {/* Phase bar — horizontal */}
      <div className="flex gap-0.5 overflow-x-auto py-1">
        {PHASES.map((p, i) => (
          <div key={p.key} className={`px-2.5 py-1.5 rounded text-[11px] font-medium whitespace-nowrap transition-colors ${
            i < currentIdx ? 'text-[--success]' : i === currentIdx ? 'text-white' : ''
          }`} style={{
            background: i === currentIdx ? (p.key.startsWith('awaiting') ? 'var(--warning)' : 'var(--info)') : i < currentIdx ? 'transparent' : 'var(--bg-card)',
            color: i < currentIdx ? 'var(--success)' : i === currentIdx ? 'white' : 'var(--text-muted)',
            border: `1px solid ${i === currentIdx ? 'transparent' : 'var(--border)'}`,
          }}>
            {i < currentIdx ? '✓ ' : ''}{p.label}
          </div>
        ))}
      </div>

      {/* Stats row */}
      <div className="flex gap-4 text-[13px]">
        {[
          { l: 'companies', v: run.total_companies, c: '--text' },
          { l: 'new', v: run.new_companies, c: '--success' },
          { l: 'rejected', v: run.rejected, c: '--danger' },
          { l: 'scraped', v: `${run.scraped_ok}/${(run.scraped_ok||0)+(run.scraped_errors||0)}`, c: '--info' },
          { l: 'credits', v: run.credits_used || 0, c: '--text-muted' },
        ].map(s => (
          <div key={s.l}>
            <span style={{ color: `var(${s.c})`, fontWeight: 600 }}>{s.v || 0}</span>
            <span className="ml-1" style={{ color: 'var(--text-muted)' }}>{s.l}</span>
          </div>
        ))}
      </div>

      {/* Checkpoints */}
      {run.gates?.filter((g: any) => g.status === 'pending').map((g: any) => (
        <div key={g.gate_id} className="rounded p-4 border-2" style={{ borderColor: 'var(--warning)', background: 'color-mix(in srgb, var(--warning) 10%, var(--bg))' }}>
          <div className="text-[13px] font-medium" style={{ color: 'var(--warning)' }}>Awaiting: {g.label}</div>
          {g.scope && <pre className="text-[11px] mt-2 p-2 rounded overflow-x-auto" style={{ background: 'var(--bg-card)', color: 'var(--text-muted)' }}>{JSON.stringify(g.scope, null, 2)}</pre>}
          <div className="text-[11px] mt-2" style={{ color: 'var(--text-muted)' }}>Approve via MCP client: tam_approve_checkpoint(gate_id={g.gate_id})</div>
        </div>
      ))}

      {/* Apollo filters applied */}
      {run.filters && (
        <div className="rounded p-3 border" style={{ borderColor: 'var(--border)', background: 'var(--bg-card)' }}>
          <div className="text-[11px] uppercase tracking-wider font-medium mb-2" style={{ color: 'var(--text-muted)' }}>Filters Applied</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(run.filters || {}).map(([k, v]: [string, any]) => (
              v && <div key={k} className="text-[12px] px-2 py-0.5 rounded" style={{ background: 'var(--active-bg)' }}>
                <span style={{ color: 'var(--text-muted)' }}>{k.replace(/organization_|q_organization_/g, '')}:</span>{' '}
                <span style={{ color: 'var(--text)' }}>{Array.isArray(v) ? v.join(', ') : String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Companies table with expandable rows */}
      <div>
        <div className="text-[11px] uppercase tracking-wider font-medium mb-2" style={{ color: 'var(--text-muted)' }}>
          Companies ({companies.length})
        </div>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
              <th className="pb-2 pr-3 w-5"></th>
              <th className="pb-2 pr-3">Domain</th>
              <th className="pb-2 pr-3">Name</th>
              <th className="pb-2 pr-3">Industry</th>
              <th className="pb-2 pr-3">Size</th>
              <th className="pb-2 pr-3">Country</th>
              <th className="pb-2 pr-3">Confidence</th>
              <th className="pb-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {companies.map((c: any) => (
              <>
                <tr key={c.id} className="border-t cursor-pointer hover:opacity-80" style={{ borderColor: 'var(--border)' }} onClick={() => toggle(c.id)}>
                  <td className="py-2 pr-3 text-[11px]" style={{ color: 'var(--text-muted)' }}>{expanded.has(c.id) ? '▼' : '▶'}</td>
                  <td className="py-2 pr-3" style={{ color: 'var(--text-link)' }}>{c.domain}</td>
                  <td className="py-2 pr-3">{c.name || <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
                  <td className="py-2 pr-3" style={{ color: 'var(--text-secondary)' }}>{c.industry || '—'}</td>
                  <td className="py-2 pr-3" style={{ color: 'var(--text-secondary)' }}>{c.employee_count || '—'}</td>
                  <td className="py-2 pr-3" style={{ color: 'var(--text-secondary)' }}>{c.country || '—'}</td>
                  <td className="py-2 pr-3">
                    {c.analysis_confidence != null ? (
                      <span style={{ color: c.analysis_confidence > 0.7 ? 'var(--success)' : c.analysis_confidence > 0.4 ? 'var(--warning)' : 'var(--danger)' }}>
                        {(c.analysis_confidence * 100).toFixed(0)}%
                      </span>
                    ) : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                  </td>
                  <td className="py-2">
                    {c.is_blacklisted ? <span style={{ color: 'var(--danger)' }}>blacklisted</span> :
                     c.is_target === true ? <span style={{ color: 'var(--success)' }}>target</span> :
                     c.is_target === false ? <span style={{ color: 'var(--text-muted)' }}>rejected</span> :
                     <span style={{ color: 'var(--text-muted)' }}>pending</span>}
                  </td>
                </tr>
                {expanded.has(c.id) && (
                  <tr key={`${c.id}-detail`}>
                    <td colSpan={8} style={{ paddingBottom: 12 }}>
                      <div style={{ marginLeft: 32, padding: 16, borderRadius: 8, background: 'var(--bg-card)', border: '1px solid var(--border)', fontSize: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px 24px' }}>
                          {[
                            ['Domain', c.domain], ['Name', c.name], ['Industry', c.industry],
                            ['Employees', c.employee_count], ['Revenue', c.revenue], ['Founded', c.founded_year],
                            ['Country', c.country], ['City', c.city], ['Phone', c.phone],
                          ].map(([l, v]) => v ? <div key={l}><span style={{ color: 'var(--text-muted)' }}>{l}:</span> {v}</div> : null)}
                          {c.linkedin_url && <div><span style={{ color: 'var(--text-muted)' }}>LinkedIn:</span> <a href={c.linkedin_url} target="_blank" style={{ color: 'var(--text-link)' }}>Profile</a></div>}
                        </div>
                        {c.description && <div style={{ color: 'var(--text-secondary)' }}>{c.description}</div>}
                        {!c.name && !c.industry && (
                          <div style={{ padding: '8px 10px', borderRadius: 6, background: 'var(--bg)', color: 'var(--warning)', fontSize: 11 }}>
                            Manual source — use Apollo API for full data.
                          </div>
                        )}
                        {(c.analysis_reasoning || c.analysis_segment) && (
                          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8 }}>
                            <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-muted)', marginBottom: 4 }}>GPT Analysis</div>
                            {c.analysis_segment && <div><span style={{ color: 'var(--text-muted)' }}>Segment:</span> {c.analysis_segment}</div>}
                            {c.analysis_confidence != null && <div><span style={{ color: 'var(--text-muted)' }}>Confidence:</span> <span style={{ color: c.analysis_confidence > 0.7 ? 'var(--success)' : 'var(--warning)' }}>{(c.analysis_confidence*100).toFixed(0)}%</span></div>}
                            {c.analysis_reasoning && <div style={{ color: 'var(--text-secondary)', marginTop: 4 }}>{c.analysis_reasoning}</div>}
                          </div>
                        )}
                        {c.is_blacklisted && <div style={{ color: 'var(--danger)' }}>Blacklisted: {c.blacklist_reason}</div>}
                        {c.source_data && Object.keys(c.source_data).length > 0 && (
                          <details>
                            <summary style={{ fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer' }}>Raw Apollo data</summary>
                            <pre style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, padding: 8, borderRadius: 4, background: 'var(--bg)', overflow: 'auto', maxHeight: 200 }}>{JSON.stringify(c.source_data, null, 2)}</pre>
                          </details>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
        {companies.length === 0 && <div className="py-4 text-center" style={{ color: 'var(--text-muted)' }}>No companies in this run yet.</div>}
      </div>

      {/* Approved gates log */}
      {run.gates?.filter((g: any) => g.status === 'approved').length > 0 && (
        <div>
          <div className="text-[11px] uppercase tracking-wider font-medium mb-2" style={{ color: 'var(--text-muted)' }}>Checkpoint History</div>
          {run.gates.filter((g: any) => g.status === 'approved').map((g: any) => (
            <div key={g.gate_id} className="flex items-center gap-2 text-[12px] py-1">
              <span style={{ color: 'var(--success)' }}>✓</span>
              <span>{g.label}</span>
              <span style={{ color: 'var(--text-muted)' }}>{g.decided_at ? new Date(g.decided_at).toLocaleString() : ''}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
