import { useEffect, useState, useRef, useCallback, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { authHeaders } from '../App'

const API = '/api'
const PAGE_SIZE = 50

const STAGES = ['gather','blacklist','awaiting_scope_ok','pre_filter','scrape','analyze','awaiting_targets_ok','prepare_verification','awaiting_verify_ok','verified','completed']
const STAGE_LABELS: Record<string,string> = { gather:'Gather',blacklist:'Blacklist',awaiting_scope_ok:'CP1: Scope',pre_filter:'Pre-Filter',scrape:'Scrape',analyze:'Analysis',awaiting_targets_ok:'CP2: Targets',prepare_verification:'Verification',awaiting_verify_ok:'CP3: Cost',verified:'Done',completed:'Done' }

const STATUS_COLORS: Record<string,string> = {
  gathered: 'var(--text-muted)', blacklisted: 'var(--danger)', filtered: 'var(--text-muted)',
  scraping: 'var(--info)', scraped: 'var(--text-secondary)', scrape_failed: 'var(--warning)',
  analyzing: 'var(--info)', target: 'var(--success)', rejected: 'var(--text-muted)',
  verifying: 'var(--info)', verified: 'var(--success)',
}

// ── Column header with hidden filter (click ▼ to show) ──
function ColHeader({ col, sortCol, sortDir, toggleSort, filterValue, onFilter, options }: any) {
  const [showFilter, setShowFilter] = useState(false)
  const hasFilter = !!filterValue
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!showFilter) return
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setShowFilter(false) }
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h)
  }, [showFilter])

  return (
    <th style={{ position: 'relative', paddingBottom: 6, userSelect: 'none' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <span onClick={() => toggleSort(col.key)} style={{ cursor: 'pointer', fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: 0.5, color: sortCol === col.key ? 'var(--text)' : 'var(--text-muted)' }}>
          {col.label}{sortCol === col.key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
        </span>
        <span onClick={e => { e.stopPropagation(); setShowFilter(!showFilter) }} style={{ cursor: 'pointer', fontSize: 9, color: hasFilter ? 'var(--info)' : 'var(--text-muted)', opacity: hasFilter ? 1 : 0.5 }}>▼</span>
      </div>
      {showFilter && (
        <div ref={ref} style={{ position: 'absolute', top: '100%', left: 0, zIndex: 40, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 6, padding: 6, minWidth: 160, boxShadow: '0 4px 12px rgba(0,0,0,0.2)' }}>
          {options ? (
            <select value={filterValue} onChange={e => onFilter(e.target.value)} autoFocus style={{ width: '100%', padding: '4px 6px', fontSize: 12, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text)', outline: 'none' }}>
              <option value="">All</option>
              {options.map((o: string) => <option key={o} value={o}>{o}</option>)}
            </select>
          ) : (
            <input value={filterValue} onChange={e => onFilter(e.target.value)} placeholder={`Filter ${col.label}...`} autoFocus
              style={{ width: '100%', padding: '4px 6px', fontSize: 12, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 4, color: 'var(--text)', outline: 'none' }}
              onKeyDown={e => { if (e.key === 'Escape') setShowFilter(false) }}
            />
          )}
          {filterValue && <button onClick={() => { onFilter(''); setShowFilter(false) }} style={{ marginTop: 4, width: '100%', padding: '3px', fontSize: 11, background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>Clear</button>}
        </div>
      )}
    </th>
  )
}

// ── Company detail modal ──
function CompanyModal({ company, onClose }: { company: any; onClose: () => void }) {
  const [tab, setTab] = useState<'details'|'analysis'|'scrape'|'source'>('details')
  const [detail, setDetail] = useState<any>(null)

  useEffect(() => {
    // Load full detail
    fetch(`${API}/pipeline/companies/${company.id}`).then(r => r.ok ? r.json() : null).then(setDetail)
  }, [company.id])

  const c = detail || company
  const Tab = ({ k, label }: { k: string; label: string }) => (
    <button onClick={() => setTab(k as any)} style={{ padding: '6px 12px', fontSize: 12, fontWeight: 500, borderRadius: '6px 6px 0 0', border: 'none', cursor: 'pointer', background: tab === k ? 'var(--bg-card)' : 'transparent', color: tab === k ? 'var(--text)' : 'var(--text-muted)' }}>{label}</button>
  )

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.6)' }} />
      <div style={{ position: 'relative', width: '90%', maxWidth: 720, maxHeight: '85vh', overflow: 'auto', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 12, padding: 0 }}>
        {/* Header */}
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 15, fontWeight: 600 }}>{c.name || c.domain}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              {c.domain} · <span style={{ color: STATUS_COLORS[c.status] || 'var(--text-muted)' }}>{c.status}</span>
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, cursor: 'pointer', color: 'var(--text-muted)' }}>×</button>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: 0, padding: '0 20px', borderBottom: '1px solid var(--border)', background: 'var(--bg-header)' }}>
          <Tab k="details" label="Details" />
          <Tab k="analysis" label="Analysis" />
          <Tab k="scrape" label="Scrape" />
          <Tab k="source" label="Source" />
        </div>

        {/* Content */}
        <div style={{ padding: 20, fontSize: 13 }}>
          {tab === 'details' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 24px' }}>
              {[
                ['Domain', c.domain], ['Name', c.name], ['Industry', c.industry], ['Keywords', c.keywords],
                ['Employees', c.employee_count], ['Revenue', c.revenue], ['Founded', c.founded_year],
                ['Country', c.country], ['City', c.city], ['Phone', c.phone],
              ].map(([l, v]) => v ? <div key={l as string}><span style={{ color: 'var(--text-muted)' }}>{l}:</span> {v}</div> : null)}
              {c.linkedin_url && <div><span style={{ color: 'var(--text-muted)' }}>LinkedIn:</span> <a href={c.linkedin_url} target="_blank" style={{ color: 'var(--text-link)' }}>Profile</a></div>}
              {c.apollo_url && <div><span style={{ color: 'var(--text-muted)' }}>Apollo:</span> <a href={c.apollo_url} target="_blank" style={{ color: 'var(--text-link)' }}>View on Apollo</a></div>}
              <div><span style={{ color: 'var(--text-muted)' }}>Website:</span> <a href={`https://${c.domain}`} target="_blank" style={{ color: 'var(--text-link)' }}>{c.domain}</a></div>
              {c.description && <div style={{ gridColumn: '1/-1', color: 'var(--text-secondary)' }}>{c.description}</div>}
            </div>
          )}

          {tab === 'analysis' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {c.analysis_reasoning ? (
                <>
                  <div style={{ display: 'flex', gap: 16 }}>
                    {c.analysis_segment && <div><span style={{ color: 'var(--text-muted)' }}>Segment:</span> <b>{c.analysis_segment}</b></div>}
                    {c.analysis_confidence != null && <div><span style={{ color: 'var(--text-muted)' }}>Confidence:</span> <b style={{ color: c.analysis_confidence > 0.7 ? 'var(--success)' : 'var(--warning)' }}>{(c.analysis_confidence*100).toFixed(0)}%</b></div>}
                  </div>
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>Reasoning</div>
                    <div style={{ color: 'var(--text-secondary)', lineHeight: 1.5 }}>{c.analysis_reasoning}</div>
                  </div>
                  {c.prompt_text && (
                    <div>
                      <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>GPT Prompt Used</div>
                      <pre style={{ fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-card)', padding: 10, borderRadius: 6, overflow: 'auto', maxHeight: 200, whiteSpace: 'pre-wrap' }}>{c.prompt_text}</pre>
                    </div>
                  )}
                </>
              ) : (
                <div style={{ color: 'var(--text-muted)', padding: '20px 0' }}>No analysis yet. Run the analyze phase to see GPT reasoning.</div>
              )}
            </div>
          )}

          {tab === 'scrape' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', gap: 16 }}>
                <div><span style={{ color: 'var(--text-muted)' }}>Status:</span> {c.scrape_status || 'pending'}</div>
                {c.scrape_text_size && <div><span style={{ color: 'var(--text-muted)' }}>Size:</span> {(c.scrape_text_size / 1024).toFixed(1)}KB</div>}
                {c.scrape_http_code && <div><span style={{ color: 'var(--text-muted)' }}>HTTP:</span> {c.scrape_http_code}</div>}
                {c.scrape_timestamp && <div><span style={{ color: 'var(--text-muted)' }}>Scraped:</span> {new Date(c.scrape_timestamp).toLocaleString()}</div>}
              </div>
              {c.scrape_error && <div style={{ color: 'var(--danger)' }}>Error: {c.scrape_error}</div>}
              {c.scrape_text ? (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>Scraped Text</div>
                  <pre style={{ fontSize: 11, color: 'var(--text-secondary)', background: 'var(--bg-card)', padding: 10, borderRadius: 6, overflow: 'auto', maxHeight: 400, whiteSpace: 'pre-wrap' }}>{c.scrape_text}</pre>
                </div>
              ) : (
                <div style={{ color: 'var(--text-muted)' }}>No scrape data. Run the scrape phase first.</div>
              )}
            </div>
          )}

          {tab === 'source' && (
            <pre style={{ fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-card)', padding: 12, borderRadius: 6, overflow: 'auto', maxHeight: 500, whiteSpace: 'pre-wrap' }}>
              {JSON.stringify(c.source_data || {}, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main Pipeline Page ──
export default function PipelinePage() {
  const { runId } = useParams()
  const [run, setRun] = useState<any>(null)
  const [companies, setCompanies] = useState<any[]>([])
  const [hasTargets, setHasTargets] = useState(false)
  const [totalContacts, setTotalContacts] = useState(0)
  const [iterations, setIterations] = useState<any[]>([])
  const [selectedIteration, setSelectedIteration] = useState<string>('all')
  const [iterDropOpen, setIterDropOpen] = useState(false)
  const [stageDropOpen, setStageDropOpen] = useState(false)
  const [showPromptHistory, setShowPromptHistory] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const [usageLogs, setUsageLogs] = useState<any[]>([])
  const [selectedCompany, setSelectedCompany] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  // Column filters
  const [filters, setFilters] = useState<Record<string, string>>({})
  const setFilter = (col: string, val: string) => setFilters(prev => ({ ...prev, [col]: val }))

  // Sort
  const [sortCol, setSortCol] = useState('domain')
  const [sortDir, setSortDir] = useState<'asc'|'desc'>('asc')
  const toggleSort = (col: string) => { if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc'); else { setSortCol(col); setSortDir('asc') } }

  const load = async () => {
    setLoading(true)
    const h = authHeaders()
    const [r1, r2, r3] = await Promise.all([
      runId ? fetch(`${API}/pipeline/runs/${runId}`, {headers: h}).then(r => r.ok ? r.json() : null) : Promise.resolve(null),
      fetch(`${API}/pipeline/runs/${runId || ''}/companies`, {headers: h}).then(r => r.ok ? r.json() : null),
      fetch(`${API}/pipeline/iterations`, {headers: h}).then(r => r.ok ? r.json() : []),
    ])
    if (r1) setRun(r1)
    if (r2 && r2.companies) {
      setCompanies(r2.companies)
      setHasTargets(r2.has_targets || false)
      setTotalContacts(r2.total_contacts || 0)
    } else if (Array.isArray(r2)) {
      setCompanies(r2)
    }
    setIterations(r3)
    setLoading(false)
  }

  useEffect(() => { load() }, [runId])
  useEffect(() => { const t = setInterval(load, 15000); return () => clearInterval(t) }, [runId])

  // Load usage logs when panel opens
  useEffect(() => {
    if (showPromptHistory && runId) {
      fetch(`${API}/pipeline/usage-logs?run_id=${runId}`, {headers: authHeaders()}).then(r => r.ok ? r.json() : []).then(setUsageLogs)
    }
  }, [showPromptHistory, runId])

  // Unique filter options
  const uniqueVals = useCallback((key: string) => {
    const vals = new Set(companies.map((c: any) => c[key]).filter(Boolean))
    return Array.from(vals).sort() as string[]
  }, [companies])

  // Filter + sort companies
  const filtered = useMemo(() => {
    let result = companies
    // Iteration filter
    if (selectedIteration !== 'all') {
      result = result.filter((c: any) => String(c.iteration_id) === selectedIteration)
    }
    // Column filters
    Object.entries(filters).forEach(([col, val]) => {
      if (!val) return
      result = result.filter((c: any) => {
        const cv = String(c[col] || '').toLowerCase()
        return cv.includes(val.toLowerCase())
      })
    })
    // Sort
    result = [...result].sort((a, b) => {
      const av = a[sortCol] ?? '', bv = b[sortCol] ?? ''
      const cmp = typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv))
      return sortDir === 'asc' ? cmp : -cmp
    })
    return result
  }, [companies, filters, sortCol, sortDir, selectedIteration])

  const currentStageIdx = run ? STAGES.indexOf(run.current_phase) : -1
  const isGathering = run?.status === 'running' && run?.current_phase === 'gather'

  // Column definitions — contacts column appears only when targets exist
  const columns = [
    { key: 'domain', label: 'Domain', filterType: 'text' as const },
    { key: 'name', label: 'Name', filterType: 'text' as const },
    { key: 'industry', label: 'Industry', filterType: 'dropdown' as const },
    { key: 'keywords', label: 'Keywords', filterType: 'text' as const },
    { key: 'employee_count', label: 'Size', filterType: 'text' as const },
    { key: 'country', label: 'Country', filterType: 'dropdown' as const },
    { key: 'city', label: 'City', filterType: 'text' as const },
    { key: 'scrape_text_preview', label: 'Scraped', filterType: 'text' as const },
    { key: 'analysis_segment', label: 'Segment', filterType: 'dropdown' as const },
    { key: 'analysis_confidence', label: 'Conf.', filterType: 'text' as const },
    { key: 'analysis_reasoning', label: 'Analysis', filterType: 'text' as const },
    { key: 'status', label: 'Status', filterType: 'dropdown' as const },
    ...(hasTargets ? [{ key: 'contacts_status', label: 'People', filterType: 'dropdown' as const }] : []),
  ]

  if (!run && loading) return <div style={{ padding: 24, color: 'var(--text-muted)' }}>Loading...</div>

  return (
    <div style={{ padding: '16px 20px', maxWidth: 1400, margin: '0 auto' }}>
      {/* ── Top bar ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
        {/* Iteration selector */}
        <div style={{ position: 'relative' }}>
          <button onClick={() => setIterDropOpen(!iterDropOpen)} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderRadius: 6, fontSize: 13, fontWeight: 500, background: 'var(--active-bg)', color: 'var(--text-secondary)', border: 'none', cursor: 'pointer' }}>
            {selectedIteration === 'all' ? 'All iterations' : `Iteration #${selectedIteration}`} <span style={{ fontSize: 10, opacity: 0.5 }}>▼</span>
          </button>
          {iterDropOpen && (
            <div style={{ position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 50, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 4, minWidth: 300, boxShadow: '0 8px 24px rgba(0,0,0,0.3)' }}>
              <div onClick={() => { setSelectedIteration('all'); setIterDropOpen(false) }} style={{ padding: '6px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 12, color: selectedIteration === 'all' ? 'var(--text)' : 'var(--text-muted)', background: selectedIteration === 'all' ? 'var(--active-bg)' : 'transparent' }}>All iterations</div>
              {iterations.map((it: any) => (
                <div key={it.id} onClick={() => { setSelectedIteration(String(it.id)); setIterDropOpen(false) }} style={{ padding: '6px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 12, color: selectedIteration === String(it.id) ? 'var(--text)' : 'var(--text-muted)', background: selectedIteration === String(it.id) ? 'var(--active-bg)' : 'transparent' }}>
                  #{it.id} — {it.source_type?.replace('companies.','').replace('.manual','')} — {it.new_companies || 0} companies — {it.created_at ? new Date(it.created_at).toLocaleDateString() : ''}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Stage indicator */}
        <div style={{ position: 'relative' }}>
          <button onClick={() => setStageDropOpen(!stageDropOpen)} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderRadius: 6, fontSize: 13, fontWeight: 500, background: run?.current_phase?.startsWith('awaiting') ? 'var(--warning)' : 'var(--info)', color: 'white', border: 'none', cursor: 'pointer' }}>
            {STAGE_LABELS[run?.current_phase] || run?.current_phase || 'N/A'} <span style={{ fontSize: 10, opacity: 0.7 }}>▼</span>
          </button>
          {stageDropOpen && (
            <div style={{ position: 'absolute', top: '100%', left: 0, marginTop: 4, zIndex: 50, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 4, minWidth: 200, boxShadow: '0 8px 24px rgba(0,0,0,0.3)' }}>
              {STAGES.map((s, i) => (
                <div key={s} style={{ padding: '4px 10px', fontSize: 12, color: i < currentStageIdx ? 'var(--success)' : i === currentStageIdx ? 'var(--text)' : 'var(--text-muted)' }}>
                  {i < currentStageIdx ? '✓ ' : i === currentStageIdx ? '→ ' : '  '}{STAGE_LABELS[s]}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Prompts link */}
        {runId && <Link to={`/pipeline/${runId}/prompts`} style={{ padding: '5px 12px', borderRadius: 6, fontSize: 13, background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-secondary)', textDecoration: 'none' }}>Prompts</Link>}

        {/* Credits badge */}
        {run?.credits_used > 0 && (
          <span style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 500, background: 'rgba(245,158,11,0.15)', color: '#f59e0b' }}>
            {run.credits_used} credits
          </span>
        )}

        {/* Target rate badge */}
        {run?.target_rate > 0 && (
          <span style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 500, background: 'rgba(16,185,129,0.15)', color: '#10b981' }}>
            {(run.target_rate * 100).toFixed(0)}% target rate
          </span>
        )}

        {/* View in CRM — appears when contacts found */}
        {totalContacts > 0 && runId && (
          <Link to={`/crm?pipeline=${runId}`} style={{ padding: '5px 12px', borderRadius: 6, fontSize: 13, background: 'var(--success)', color: 'white', textDecoration: 'none', fontWeight: 500 }}>
            View {totalContacts} people in CRM
          </Link>
        )}

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button onClick={() => setShowFilters(!showFilters)} style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, border: '1px solid var(--border)', background: showFilters ? 'var(--active-bg)' : 'transparent', color: 'var(--text-muted)', cursor: 'pointer' }}>Apollo Filters</button>
          <button onClick={() => setShowPromptHistory(!showPromptHistory)} style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, border: '1px solid var(--border)', background: showPromptHistory ? 'var(--active-bg)' : 'transparent', color: 'var(--text-muted)', cursor: 'pointer' }}>Prompt History</button>
        </div>
      </div>

      {/* ── Collapsible panels ── */}
      {showFilters && run?.filters && (
        <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-card)', border: '1px solid var(--border)', marginBottom: 12, fontSize: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 6 }}>Apollo Filters — Run #{run.id}</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {Object.entries(run.filters || {}).map(([k, v]: [string, any]) => v ? (
              <span key={k} style={{ padding: '3px 8px', borderRadius: 4, background: 'var(--active-bg)', fontSize: 11 }}>
                <span style={{ color: 'var(--text-muted)' }}>{k.replace(/organization_|q_organization_/g, '')}:</span> {Array.isArray(v) ? v.join(', ') : String(v)}
              </span>
            ) : null)}
          </div>
        </div>
      )}

      {showPromptHistory && (
        <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-card)', border: '1px solid var(--border)', marginBottom: 12, fontSize: 12, maxHeight: 200, overflow: 'auto' }}>
          <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 6 }}>User-MCP Conversation</div>
          {usageLogs.length === 0 ? <div style={{ color: 'var(--text-muted)' }}>No logs yet.</div> : (
            usageLogs.map((log: any) => (
              <div key={log.id} style={{ padding: '3px 0', borderBottom: '1px solid var(--border)', display: 'flex', gap: 8 }}>
                <span style={{ color: 'var(--text-muted)', minWidth: 60, fontSize: 11 }}>{log.created_at ? new Date(log.created_at).toLocaleTimeString() : ''}</span>
                <span style={{ color: 'var(--info)', minWidth: 140 }}>{log.tool_name}</span>
                <span style={{ color: 'var(--text-secondary)' }}>{log.action}</span>
              </div>
            ))
          )}
        </div>
      )}

      {/* ── Table ── */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>{filtered.length} companies{selectedIteration !== 'all' ? ` (iteration #${selectedIteration})` : ''}</div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse', minWidth: 1100 }}>
          <thead>
            <tr style={{ textAlign: 'left' }}>
              {columns.map(col => (
                <ColHeader
                  key={col.key}
                  col={col}
                  sortCol={sortCol}
                  sortDir={sortDir}
                  toggleSort={toggleSort}
                  filterValue={filters[col.key] || ''}
                  onFilter={(v: string) => setFilter(col.key, v)}
                  options={col.filterType === 'dropdown' ? uniqueVals(col.key) : undefined}
                />
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((c: any) => (
              <tr key={c.id} onClick={() => setSelectedCompany(c)} style={{ borderTop: '1px solid var(--border)', cursor: 'pointer' }} onMouseEnter={e => (e.currentTarget.style.background = 'var(--btn-hover)')} onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                <td style={{ padding: '7px 8px 7px 0', color: 'var(--text-link)' }}>{c.domain}</td>
                <td style={{ padding: '7px 8px 7px 0' }}>{c.name || <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
                <td style={{ padding: '7px 8px 7px 0', color: 'var(--text-secondary)' }}>{c.industry || '—'}</td>
                <td style={{ padding: '7px 8px 7px 0', color: 'var(--text-secondary)', fontSize: 11 }}>{Array.isArray(c.keywords) ? c.keywords.join(', ') : (c.keywords || '—')}</td>
                <td style={{ padding: '7px 8px 7px 0', color: 'var(--text-secondary)' }}>{c.employee_count || '—'}</td>
                <td style={{ padding: '7px 8px 7px 0', color: 'var(--text-secondary)' }}>{c.country || '—'}</td>
                <td style={{ padding: '7px 8px 7px 0', color: 'var(--text-secondary)' }}>{c.city || '—'}</td>
                <td style={{ padding: '7px 8px 7px 0', fontSize: 11, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.scrape_text_preview ? <span style={{ color: 'var(--text-secondary)' }} title={c.scrape_text_preview}>{c.scrape_text_preview.slice(0, 60)}...</span> :
                   c.scrape_status === 'success' ? <span style={{ color: 'var(--success)' }}>✓ scraped</span> :
                   c.scrape_status === 'error' ? <span style={{ color: 'var(--danger)' }}>error</span> :
                   <span style={{ color: 'var(--text-muted)' }}>—</span>}
                </td>
                <td style={{ padding: '7px 8px 7px 0', fontSize: 11 }}>
                  {c.analysis_segment ? (
                    <span style={{ padding: '1px 5px', borderRadius: 3, background: c.analysis_segment === 'NOT_A_MATCH' ? 'var(--bg)' : 'rgba(99,102,241,0.15)', color: c.analysis_segment === 'NOT_A_MATCH' ? 'var(--text-muted)' : '#818cf8', fontWeight: 500 }}>
                      {c.analysis_segment}
                    </span>
                  ) : '—'}
                </td>
                <td style={{ padding: '7px 8px 7px 0', fontSize: 11, fontWeight: 600, color: c.analysis_confidence >= 0.8 ? 'var(--success)' : c.analysis_confidence >= 0.5 ? 'var(--warning)' : 'var(--text-muted)' }}>
                  {c.analysis_confidence != null ? `${(c.analysis_confidence*100).toFixed(0)}%` : '—'}
                </td>
                <td style={{ padding: '7px 8px 7px 0', color: 'var(--text-secondary)', fontSize: 11, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.analysis_reasoning || c.analysis_short || '—'}</td>
                <td style={{ padding: '7px 0' }}>
                  <span style={{ color: STATUS_COLORS[c.status] || 'var(--text-muted)', fontWeight: c.status === 'target' || c.status === 'verified' ? 600 : 400 }}>{c.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Loading / gathering indicator */}
      {isGathering && (
        <div style={{ padding: '16px 0', textAlign: 'center', color: 'var(--info)', fontSize: 13 }}>
          Gathering in progress... {companies.length} companies found so far
        </div>
      )}

      {filtered.length === 0 && !loading && (
        <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)' }}>No companies match filters.</div>
      )}

      {/* Modal */}
      {selectedCompany && <CompanyModal company={selectedCompany} onClose={() => setSelectedCompany(null)} />}
    </div>
  )
}
