import { useEffect, useState, useRef, useCallback, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { authHeaders } from '../App'

const API = '/api'
const PAGE_SIZE = 50

const STAGES = ['gather','blacklist','awaiting_scope_ok','scrape','analyze','awaiting_targets_ok','completed']
const STAGE_LABELS: Record<string,string> = { gather:'Collect',blacklist:'Check',awaiting_scope_ok:'Approve',scrape:'Scrape',analyze:'Analyze',awaiting_targets_ok:'Review',pre_filter:'Filter',prepare_verification:'Verify',awaiting_verify_ok:'Approve',completed:'Done',verified:'Done' }

const STATUS_COLORS: Record<string,string> = {
  gathered: 'var(--text-muted)', blacklisted: 'var(--danger)', filtered: 'var(--text-muted)',
  scraping: 'var(--info)', scraped: 'var(--text-secondary)', scrape_failed: 'var(--warning)',
  analyzing: 'var(--info)', target: 'var(--success)', rejected: 'var(--text-muted)',
  verifying: 'var(--info)', verified: 'var(--success)',
}

// ── Column header with hidden filter + resize handle ──
function ColHeader({ col, sortCol, sortDir, toggleSort, filterValue, onFilter, options, width, onResize }: any) {
  const [showFilter, setShowFilter] = useState(false)
  const hasFilter = !!filterValue
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!showFilter) return
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setShowFilter(false) }
    document.addEventListener('mousedown', h); return () => document.removeEventListener('mousedown', h)
  }, [showFilter])

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const startX = e.clientX
    const startW = width || 120
    const onMove = (ev: MouseEvent) => {
      const delta = ev.clientX - startX
      onResize(Math.max(50, startW + delta))
    }
    const onUp = () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [width, onResize])

  return (
    <th style={{ position: 'relative', paddingBottom: 6, userSelect: 'none', width: width || undefined, minWidth: 50 }}>
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
      {/* Resize handle — subtle line on right edge */}
      <div
        onMouseDown={handleResizeStart}
        style={{ position: 'absolute', top: 0, right: 0, width: 5, height: '100%', cursor: 'col-resize', zIndex: 10 }}
        onMouseEnter={e => (e.currentTarget.style.borderRight = '2px solid var(--info)')}
        onMouseLeave={e => (e.currentTarget.style.borderRight = 'none')}
      />
    </th>
  )
}

// ── Copy helper ──
function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button onClick={e => { e.stopPropagation(); navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500) }}
      style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 11, color: copied ? 'var(--success)' : 'var(--text-muted)', padding: '0 4px' }}
      title="Copy">{copied ? '✓' : '⧉'}</button>
  )
}

// ── Company detail modal ──
function CompanyModal({ company, onClose }: { company: any; onClose: () => void }) {
  const [tab, setTab] = useState<'analysis'|'details'|'scrape'|'source'>('analysis')
  const [detail, setDetail] = useState<any>(null)
  const [scrapeExpanded, setScrapeExpanded] = useState(false)

  useEffect(() => {
    fetch(`${API}/pipeline/companies/${company.id}`, { headers: authHeaders() }).then(r => r.ok ? r.json() : null).then(setDetail)
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
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2, display: 'flex', alignItems: 'center', gap: 6 }}>
              <a href={`https://${c.domain}`} target="_blank" rel="noopener" style={{ color: 'var(--text-link)' }}>{c.domain}</a>
              · <span style={{ color: STATUS_COLORS[c.status] || 'var(--text-muted)' }}>{c.status}</span>
              {c.analysis_segment && c.analysis_segment !== 'NOT_A_MATCH' && (
                <span style={{ padding: '1px 6px', borderRadius: 3, background: 'rgba(99,102,241,0.15)', color: '#818cf8', fontSize: 11, fontWeight: 500 }}>{c.analysis_segment}</span>
              )}
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, cursor: 'pointer', color: 'var(--text-muted)' }}>×</button>
        </div>

        {/* Tabs — Analysis first */}
        <div style={{ display: 'flex', gap: 0, padding: '0 20px', borderBottom: '1px solid var(--border)', background: 'var(--bg-header)' }}>
          <Tab k="analysis" label="Analysis" />
          <Tab k="details" label="Details" />
          <Tab k="scrape" label="Scrape" />
          <Tab k="source" label="Source" />
        </div>

        {/* Content */}
        <div style={{ padding: 20, fontSize: 13 }}>

          {tab === 'analysis' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {c.analysis_reasoning ? (
                <>
                  <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                    {c.analysis_segment && (
                      <div style={{ padding: '4px 10px', borderRadius: 6, background: c.analysis_segment === 'NOT_A_MATCH' ? 'var(--bg-card)' : 'rgba(99,102,241,0.12)', color: c.analysis_segment === 'NOT_A_MATCH' ? 'var(--text-muted)' : '#818cf8', fontWeight: 600, fontSize: 13 }}>
                        {c.analysis_segment}
                      </div>
                    )}
                    <div style={{ padding: '4px 10px', borderRadius: 6, background: 'var(--bg-card)', color: STATUS_COLORS[c.status] || 'var(--text-muted)', fontWeight: 500 }}>
                      {c.status}
                    </div>
                  </div>
                  <div style={{ color: 'var(--text-secondary)', lineHeight: 1.6, marginTop: 4 }}>{c.analysis_reasoning}</div>
                  {c.prompt_text && (
                    <details style={{ marginTop: 8 }}>
                      <summary style={{ fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer' }}>GPT prompt used</summary>
                      <pre style={{ fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-card)', padding: 10, borderRadius: 6, overflow: 'auto', maxHeight: 200, whiteSpace: 'pre-wrap', marginTop: 6 }}>{c.prompt_text}</pre>
                    </details>
                  )}
                </>
              ) : (
                <div style={{ color: 'var(--text-muted)', padding: '20px 0' }}>Not analyzed yet.</div>
              )}
            </div>
          )}

          {tab === 'details' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 24px' }}>
              {[
                ['Industry', c.industry],
                ['Keywords', Array.isArray(c.keywords) ? c.keywords.join(', ') : c.keywords],
                ['Employees', c.employee_count],
                ['Founded', c.founded_year],
                ['Country', c.country],
                ['City', c.city],
                ['Revenue', c.revenue],
                ['Phone', c.phone],
              ].map(([l, v]) => v ? <div key={l as string}><span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{l}:</span> <span style={{ fontSize: 13 }}>{v}</span></div> : null)}

              {/* Growth & Apollo people */}
              {(c.headcount_growth_12m || c.source_data?.headcount_12m_growth) && (
                <div><span style={{ color: 'var(--text-muted)', fontSize: 12 }}>Growth:</span> <span style={{ fontSize: 13, color: 'var(--success)', fontWeight: 500 }}>+{c.headcount_growth_12m || c.source_data?.headcount_12m_growth}%</span></div>
              )}
              {(c.num_contacts_apollo || c.source_data?.num_contacts_in_apollo) && (
                <div><span style={{ color: 'var(--text-muted)', fontSize: 12 }}>People in Apollo:</span> <span style={{ fontSize: 13 }}>{c.num_contacts_apollo || c.source_data?.num_contacts_in_apollo}</span></div>
              )}

              {/* Links with copy buttons */}
              {c.linkedin_url && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>LinkedIn:</span>
                  <a href={c.linkedin_url} target="_blank" rel="noopener" style={{ color: 'var(--text-link)', fontSize: 13 }}>{c.linkedin_url.replace('http://www.linkedin.com/company/', '').replace('https://www.linkedin.com/company/', 'linkedin.com/…/')}</a>
                  <CopyBtn text={c.linkedin_url} />
                </div>
              )}
              {c.apollo_url && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <a href={c.apollo_url} target="_blank" rel="noopener" style={{ color: 'var(--text-link)', fontSize: 13 }}>View on Apollo</a>
                  <CopyBtn text={c.apollo_url} />
                </div>
              )}
              {c.description && <div style={{ gridColumn: '1/-1', color: 'var(--text-secondary)', marginTop: 4, lineHeight: 1.5 }}>{c.description}</div>}
            </div>
          )}

          {tab === 'scrape' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 12 }}>
                <div><span style={{ color: 'var(--text-muted)' }}>Status:</span> <b style={{ color: c.scrape_status === 'success' ? 'var(--success)' : 'var(--danger)' }}>{c.scrape_status || 'pending'}</b></div>
                {c.scrape_text_size != null && <div><span style={{ color: 'var(--text-muted)' }}>Size:</span> {c.scrape_text_size > 1024 ? (c.scrape_text_size / 1024).toFixed(1) + 'KB' : c.scrape_text_size + 'B'}</div>}
                {c.scrape_http_code && <div><span style={{ color: 'var(--text-muted)' }}>HTTP:</span> {c.scrape_http_code}</div>}
                {c.scrape_timestamp && <div><span style={{ color: 'var(--text-muted)' }}>Scraped:</span> {new Date(c.scrape_timestamp).toLocaleString()}</div>}
                <div><span style={{ color: 'var(--text-muted)' }}>Page:</span> / (root)</div>
              </div>
              {c.scrape_error && <div style={{ color: 'var(--danger)', fontSize: 12 }}>Error: {c.scrape_error}</div>}
              {c.scrape_text ? (
                <div>
                  <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>Scraped Text</div>
                  <pre style={{ fontSize: 11, color: 'var(--text-secondary)', background: 'var(--bg-card)', padding: 10, borderRadius: 6, overflow: 'auto', maxHeight: scrapeExpanded ? 'none' : 300, whiteSpace: 'pre-wrap' }}>
                    {c.scrape_text}
                  </pre>
                  {c.scrape_text.length > 1000 && (
                    <button onClick={() => setScrapeExpanded(!scrapeExpanded)} style={{ fontSize: 11, color: 'var(--text-link)', background: 'none', border: 'none', cursor: 'pointer', marginTop: 4 }}>
                      {scrapeExpanded ? 'Collapse' : 'View full text'}
                    </button>
                  )}
                </div>
              ) : (
                <div style={{ color: 'var(--text-muted)' }}>No scrape data yet.</div>
              )}
            </div>
          )}

          {tab === 'source' && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 8 }}>Raw Apollo Data</div>
              <pre style={{ fontSize: 11, color: 'var(--text-muted)', background: 'var(--bg-card)', padding: 12, borderRadius: 6, overflow: 'auto', maxHeight: 500, whiteSpace: 'pre-wrap' }}>
                {JSON.stringify(c.source_data || {}, null, 2)}
              </pre>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main Pipeline Page ──
// ── KPI Progress Banner ──
function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds < 0) return '—'
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m < 60) return s ? `${m}m ${s}s` : `${m}m`
  const h = Math.floor(m / 60)
  const rm = m % 60
  return rm ? `${h}h ${rm}m` : `${h}h`
}

function ProgressBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0
  return (
    <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'var(--border)', overflow: 'hidden' }}>
      <div style={{ width: `${pct}%`, height: '100%', borderRadius: 3, background: color, transition: 'width 0.5s ease' }} />
    </div>
  )
}

function KPIProgressBanner({ run, onPause, onResume }: { run: any; onPause: () => void; onResume: () => void }) {
  const kpi = run.kpi || {}
  const progress = run.progress || {}
  const timing = run.timing || {}
  const isPaused = run.status === 'paused'

  const targetCount = kpi.target_people || kpi.target_count || 100
  const contactsPerCompany = kpi.max_people_per_company || kpi.contacts_per_company || 3
  const minTargets = kpi.target_companies || kpi.min_targets || Math.ceil(targetCount / contactsPerCompany)
  const peoplePct = progress.people_pct || 0
  const targetsPct = progress.targets_pct || 0

  return (
    <div style={{
      padding: '12px 16px',
      borderRadius: 8,
      background: isPaused ? 'rgba(245,158,11,0.06)' : 'rgba(59,130,246,0.06)',
      border: `1px solid ${isPaused ? 'rgba(245,158,11,0.2)' : 'rgba(59,130,246,0.2)'}`,
      marginBottom: 12,
    }}>
      {/* Top row: timing + status + pause/resume */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 10, fontSize: 12 }}>
        {isPaused && (
          <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600, background: 'rgba(245,158,11,0.15)', color: '#f59e0b' }}>PAUSED</span>
        )}
        {!isPaused && (
          <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600, background: 'rgba(59,130,246,0.15)', color: '#3b82f6' }}>RUNNING</span>
        )}
        <span style={{ color: 'var(--text-muted)' }}>
          {formatDuration(timing.elapsed_seconds)} elapsed
        </span>
        {timing.eta_seconds && (
          <span style={{ color: 'var(--text-muted)' }}>
            ETA ~{formatDuration(timing.eta_seconds)}
          </span>
        )}
        <span style={{ color: 'var(--text-muted)' }}>
          Iteration {progress.iteration || 0}
        </span>
        <span style={{ color: 'var(--text-muted)' }}>
          {progress.pages_fetched || 0} pages
        </span>
        {run.credits_used > 0 && (
          <span style={{ color: 'var(--text-muted)' }}>
            {run.credits_used} credits
          </span>
        )}
        <div style={{ marginLeft: 'auto' }}>
          {isPaused ? (
            <button onClick={onResume} style={{
              padding: '4px 14px', borderRadius: 6, fontSize: 12, fontWeight: 500,
              background: '#3b82f6', color: 'white', border: 'none', cursor: 'pointer',
            }}>Resume</button>
          ) : (
            <button onClick={onPause} style={{
              padding: '4px 14px', borderRadius: 6, fontSize: 12, fontWeight: 500,
              background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)', cursor: 'pointer',
            }}>Pause</button>
          )}
        </div>
      </div>

      {/* Progress bars */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', minWidth: 80 }}>People</span>
          <ProgressBar value={progress.people_found || 0} max={targetCount} color="#22c55e" />
          <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text)', minWidth: 100, textAlign: 'right' }}>
            {progress.people_found || 0}/{targetCount} ({peoplePct}%)
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 11, color: 'var(--text-muted)', minWidth: 80 }}>Companies</span>
          <ProgressBar value={progress.targets_found || 0} max={minTargets} color="#3b82f6" />
          <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text)', minWidth: 100, textAlign: 'right' }}>
            {progress.targets_found || 0}/{minTargets} ({targetsPct}%)
          </span>
        </div>
      </div>

      {/* KPI summary */}
      <div style={{ display: 'flex', gap: 16, marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
        <span>Target: {targetCount} contacts</span>
        <span>Max {contactsPerCompany}/company</span>
        <span>~{minTargets} target companies</span>
      </div>
    </div>
  )
}

export default function PipelinePage() {
  const { runId } = useParams()
  const [run, setRun] = useState<any>(null)
  const [companies, setCompanies] = useState<any[]>([])
  const [hasTargets, setHasTargets] = useState(false)
  const [totalContacts, setTotalContacts] = useState(0)
  const [iterations, setIterations] = useState<any[]>([])
  const [selectedIteration, setSelectedIteration] = useState<string>(() => {
    const p = new URLSearchParams(window.location.search)
    return p.get('iteration') || 'all'
  })
  const [iterDropOpen, setIterDropOpen] = useState(false)
  const [stageDropOpen, setStageDropOpen] = useState(false)
  const [showPromptHistory, setShowPromptHistory] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const [showPeopleFilters, setShowPeopleFilters] = useState(false)
  const [showCampaign, setShowCampaign] = useState(false)
  const [usageLogs, setUsageLogs] = useState<any[]>([])
  const [selectedCompany, setSelectedCompany] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [companyPage, setCompanyPage] = useState(1)
  const [totalCompanies, setTotalCompanies] = useState(0)

  // Column filters — read ?status= from URL on mount
  const [filters, setFilters] = useState<Record<string, string>>(() => {
    const p = new URLSearchParams(window.location.search)
    const s = p.get('status')
    return s ? { status: s } : {}
  })
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
      fetch(`${API}/pipeline/runs/${runId || ''}/companies?page=${companyPage}&page_size=${PAGE_SIZE}${selectedIteration !== 'all' ? `&iteration=${selectedIteration}` : ''}`, {headers: h}).then(r => r.ok ? r.json() : null),
      fetch(`${API}/pipeline/iterations`, {headers: h}).then(r => r.ok ? r.json() : []),
    ])
    if (r1) setRun(r1)
    if (r2 && r2.companies) {
      setCompanies(prev => companyPage === 1 ? r2.companies : [...prev, ...r2.companies])
      setHasTargets(r2.has_targets || false)
      setTotalContacts(r2.total_contacts || 0)
      setTotalCompanies(r2.total_companies || r2.companies.length)
    } else if (Array.isArray(r2)) {
      setCompanies(r2)
    }
    setIterations(r3)
    setLoading(false)
  }

  useEffect(() => { load() }, [runId, selectedIteration, companyPage])
  useEffect(() => { const t = setInterval(load, 15000); return () => clearInterval(t) }, [runId, selectedIteration])

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

  const currentStageIdx = run ? STAGES.indexOf(run.current_phase === 'verified' ? 'completed' : run.current_phase) : -1
  const isGathering = run?.status === 'running' && run?.current_phase === 'gather'

  // Column visibility — persisted per run in localStorage
  const colKey = `pipeline_columns_${runId || 'global'}`
  const colWidthKey = `pipeline_colwidths_${runId || 'global'}`
  const [columnConfig, setColumnConfig] = useState<Record<string, boolean>>(() => {
    try {
      const saved = localStorage.getItem(colKey)
      return saved ? JSON.parse(saved) : {}
    } catch { return {} }
  })
  const [columnWidths, setColumnWidths] = useState<Record<string, number>>(() => {
    try {
      const saved = localStorage.getItem(colWidthKey)
      return saved ? JSON.parse(saved) : {}
    } catch { return {} }
  })
  const [showColumnConfig, setShowColumnConfig] = useState(false)

  const setColWidth = useCallback((key: string, w: number) => {
    setColumnWidths(prev => {
      const next = { ...prev, [key]: w }
      localStorage.setItem(colWidthKey, JSON.stringify(next))
      return next
    })
  }, [colWidthKey])

  const toggleColumn = (key: string) => {
    setColumnConfig(prev => {
      const next = { ...prev, [key]: !(prev[key] ?? true) }
      localStorage.setItem(colKey, JSON.stringify(next))
      return next
    })
  }

  // Essential columns (always available, shown by default)
  const essentialColumns = [
    { key: 'domain', label: 'Domain', filterType: 'text' as const, essential: true },
    { key: 'name', label: 'Name', filterType: 'text' as const, essential: true },
    { key: 'status', label: 'Status', filterType: 'dropdown' as const, essential: true },
    { key: 'analysis_segment', label: 'Segment', filterType: 'dropdown' as const, essential: true },
  ]

  // Optional built-in columns (hideable)
  const optionalColumns = [
    { key: 'industry', label: 'Industry', filterType: 'dropdown' as const },
    { key: 'keywords', label: 'Keywords', filterType: 'text' as const },
    { key: 'employee_count', label: 'Size', filterType: 'text' as const },
    { key: 'country', label: 'Country', filterType: 'dropdown' as const },
    { key: 'city', label: 'City', filterType: 'text' as const },
    { key: 'scrape_text_preview', label: 'Scraped', filterType: 'text' as const },
    // confidence excluded per requirements — via negativa approach, no scores
    { key: 'analysis_reasoning', label: 'Analysis', filterType: 'text' as const },
    { key: 'contacts_count', label: 'People', filterType: 'text' as const },
  ]

  // Custom columns from current iteration's processing steps
  const customColumns = useMemo(() => {
    // Detect custom columns from company data (source_data.custom_columns keys)
    const customKeys = new Set<string>()
    for (const c of companies) {
      const cc = c.source_data?.custom_columns || c.source_data?.custom_analysis || {}
      Object.keys(cc).forEach(k => customKeys.add(k))
    }
    return Array.from(customKeys).map(key => ({
      key: `custom_${key}`,
      label: key.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()),
      filterType: 'dropdown' as const,
      customKey: key,
    }))
  }, [companies])

  // Build visible columns
  const columns = useMemo(() => {
    const all = [
      ...essentialColumns,
      ...optionalColumns.filter(c => columnConfig[c.key] !== false),
      ...customColumns.filter(c => columnConfig[c.key] !== false),
    ]
    return all
  }, [columnConfig, customColumns])

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
              <div onClick={() => { setSelectedIteration('all'); setIterDropOpen(false); const u = new URL(window.location.href); u.searchParams.delete('iteration'); window.history.replaceState({}, '', u.toString()) }} style={{ padding: '6px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 12, color: selectedIteration === 'all' ? 'var(--text)' : 'var(--text-muted)', background: selectedIteration === 'all' ? 'var(--active-bg)' : 'transparent' }}>All iterations</div>
              {iterations.map((it: any) => (
                <div key={it.id} onClick={() => { setSelectedIteration(String(it.id)); setIterDropOpen(false); const u = new URL(window.location.href); u.searchParams.set('iteration', String(it.id)); window.history.replaceState({}, '', u.toString()) }} style={{ padding: '6px 10px', borderRadius: 4, cursor: 'pointer', fontSize: 12, color: selectedIteration === String(it.id) ? 'var(--text)' : 'var(--text-muted)', background: selectedIteration === String(it.id) ? 'var(--active-bg)' : 'transparent' }}>
                  #{it.id} — {it.new_companies || 0} companies{it.target_count ? ` (${it.target_count} targets)` : ''} — {it.created_at ? new Date(it.created_at).toLocaleString([], {month:'short', day:'numeric', hour:'2-digit', minute:'2-digit'}) : ''}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Visual stepper — no clicking, just shows progress */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 0 }}>
          {STAGES.filter(s => !s.startsWith('awaiting')).map((s, i, arr) => {
            const stageIdx = STAGES.indexOf(s)
            const done = stageIdx < currentStageIdx
            const current = stageIdx === currentStageIdx || (s === 'analyze' && run?.current_phase?.startsWith('awaiting_targets'))
            const checkpoint = run?.current_phase?.startsWith('awaiting') && current
            const color = done ? '#22c55e' : current ? (checkpoint ? '#f59e0b' : '#3b82f6') : 'var(--border)'
            const label = STAGE_LABELS[s] || s
            const shortLabel = label.replace('Pre-', '').replace('Prepare ', '').substring(0, 8)
            return (
              <div key={s} style={{ display: 'flex', alignItems: 'center' }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
                  <div style={{ width: 10, height: 10, borderRadius: '50%', background: color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {done && <span style={{ fontSize: 7, color: 'white' }}>✓</span>}
                  </div>
                  <span style={{ fontSize: 9, color: current ? 'var(--text)' : 'var(--text-muted)', fontWeight: current ? 600 : 400 }}>{shortLabel}</span>
                </div>
                {i < arr.length - 1 && <div style={{ width: 12, height: 1, background: done ? '#22c55e' : 'var(--border)', marginBottom: 12 }} />}
              </div>
            )
          })}
        </div>

        {/* Prompts link */}
        {runId && <Link to={`/pipeline/${runId}/prompts`} style={{ padding: '5px 12px', borderRadius: 6, fontSize: 13, background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-secondary)', textDecoration: 'none' }}>Prompts</Link>}

        {/* Credits badge */}
        {run?.credits_used > 0 && (
          <span style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 500, background: 'rgba(245,158,11,0.15)', color: '#f59e0b' }}>
            {run.credits_used} Apollo credits
          </span>
        )}

        {/* Target rate badge with absolute numbers */}
        {run?.target_rate > 0 && (
          <span style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, fontWeight: 500, background: 'rgba(16,185,129,0.15)', color: '#10b981' }}>
            {run.targets_found || Math.round(run.target_rate * (run.new_companies || 0))}/{run.new_companies || '?'} targets ({(run.target_rate * 100).toFixed(0)}%)
          </span>
        )}

        {/* View in CRM — appears when contacts found */}
        {totalContacts > 0 && runId && (
          <Link to={`/crm?pipeline=${runId}`} style={{ padding: '5px 12px', borderRadius: 6, fontSize: 13, background: 'var(--success)', color: 'white', textDecoration: 'none', fontWeight: 500 }}>
            View {totalContacts} people in CRM
          </Link>
        )}

        {/* Campaign toggle — shows expandable block below */}
        {run?.campaign?.id && (
          <button onClick={() => setShowCampaign(!showCampaign)} style={{ padding: '5px 12px', borderRadius: 6, fontSize: 13, background: showCampaign ? 'rgba(99,102,241,0.15)' : 'transparent', color: '#6366f1', fontWeight: 500, border: '1px solid rgba(99,102,241,0.3)', cursor: 'pointer' }}>
            Campaign {run.campaign.status === 'mcp_draft' ? '(draft)' : ''}
          </button>
        )}

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button onClick={() => setShowColumnConfig(!showColumnConfig)} style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, border: '1px solid var(--border)', background: showColumnConfig ? 'var(--active-bg)' : 'transparent', color: 'var(--text-muted)', cursor: 'pointer' }}>Columns</button>
          <button onClick={() => setShowFilters(!showFilters)} style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, border: '1px solid var(--border)', background: showFilters ? 'var(--active-bg)' : 'transparent', color: 'var(--text-muted)', cursor: 'pointer' }}>Company Filters</button>
          <button onClick={() => setShowPeopleFilters(!showPeopleFilters)} style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, border: '1px solid var(--border)', background: showPeopleFilters ? 'var(--active-bg)' : 'transparent', color: 'var(--text-muted)', cursor: 'pointer' }}>People Filters</button>
          <button onClick={() => setShowPromptHistory(!showPromptHistory)} style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, border: '1px solid var(--border)', background: showPromptHistory ? 'var(--active-bg)' : 'transparent', color: 'var(--text-muted)', cursor: 'pointer' }}>User-MCP Conversation</button>
          {filtered.length > 0 && (
            <button onClick={() => {
              const headers = ['Domain','Name','Industry','Employees','Country','City','Segment','Status','Reasoning'];
              const esc = (v: any) => `"${String(v ?? '').replace(/"/g, '""')}"`;
              const rows = filtered.map((c: any) => [c.domain, c.name, c.industry, c.employee_count, c.country, c.city, c.analysis_segment, c.status, c.analysis_reasoning].map(esc).join(','));
              const csv = [headers.join(','), ...rows].join('\n');
              const blob = new Blob([csv], {type: 'text/csv'});
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a'); a.href = url; a.download = `pipeline_${runId}_companies.csv`; a.click(); URL.revokeObjectURL(url);
            }} style={{ padding: '4px 10px', borderRadius: 6, fontSize: 12, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer' }}>Export CSV</button>
          )}
        </div>
      </div>

      {/* ── KPI Progress Banner — shown when run is running or paused ── */}
      {run && (run.status === 'running' || run.status === 'paused') && run.kpi && (
        <KPIProgressBanner run={run} onPause={async () => {
          await fetch(`${API}/pipeline/runs/${runId}/pause`, { method: 'POST', headers: authHeaders() })
          load()
        }} onResume={async () => {
          await fetch(`${API}/pipeline/runs/${runId}/resume`, { method: 'POST', headers: authHeaders() })
          load()
        }} />
      )}

      {/* ── Collapsible panels ── */}

      {/* Column Configuration */}
      {showColumnConfig && (
        <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-card)', border: '1px solid var(--border)', marginBottom: 12, fontSize: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 8 }}>Column Visibility</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {essentialColumns.map(c => (
              <span key={c.key} style={{ padding: '3px 8px', borderRadius: 4, background: 'rgba(34,197,94,0.12)', color: '#22c55e', fontSize: 11 }}>
                {c.label} (always)
              </span>
            ))}
            {optionalColumns.map(c => (
              <button key={c.key} onClick={() => toggleColumn(c.key)} style={{
                padding: '3px 8px', borderRadius: 4, fontSize: 11, border: '1px solid var(--border)',
                background: columnConfig[c.key] !== false ? 'rgba(59,130,246,0.12)' : 'transparent',
                color: columnConfig[c.key] !== false ? '#3b82f6' : 'var(--text-muted)',
                cursor: 'pointer', opacity: columnConfig[c.key] !== false ? 1 : 0.5,
              }}>
                {columnConfig[c.key] !== false ? '✓ ' : ''}{c.label}
              </button>
            ))}
            {customColumns.length > 0 && (
              <>
                <span style={{ padding: '3px 0', color: 'var(--text-muted)', fontSize: 10, fontWeight: 600 }}>|</span>
                {customColumns.map(c => (
                  <button key={c.key} onClick={() => toggleColumn(c.key)} style={{
                    padding: '3px 8px', borderRadius: 4, fontSize: 11, border: '1px solid rgba(168,85,247,0.3)',
                    background: columnConfig[c.key] !== false ? 'rgba(168,85,247,0.12)' : 'transparent',
                    color: columnConfig[c.key] !== false ? '#a855f7' : 'var(--text-muted)',
                    cursor: 'pointer', opacity: columnConfig[c.key] !== false ? 1 : 0.5,
                  }}>
                    {columnConfig[c.key] !== false ? '✓ ' : ''}{c.label}
                  </button>
                ))}
              </>
            )}
          </div>
        </div>
      )}

      {showFilters && run?.filters && (
        <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-card)', border: '1px solid var(--border)', marginBottom: 12, fontSize: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 8 }}>Search Strategy — Run #{run.id}</div>

          {/* Strategy badge */}
          <div style={{ marginBottom: 10 }}>
            <span style={{
              padding: '3px 10px', borderRadius: 4, fontSize: 11, fontWeight: 600,
              background: run.filters.filter_strategy === 'industry_first' ? 'rgba(34,197,94,0.12)' : 'rgba(59,130,246,0.12)',
              color: run.filters.filter_strategy === 'industry_first' ? '#22c55e' : '#3b82f6',
            }}>
              {run.filters.filter_strategy === 'industry_first' ? 'INDUSTRY FIRST' : 'KEYWORDS FIRST'}
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>
              {run.filters.filter_strategy === 'industry_first'
                ? 'Specific industry match → high target rate. Keywords as fallback.'
                : 'Industry too broad → using specific keywords. Industry as fallback for scale.'}
            </span>
            <span title={run.filters.filter_strategy === 'industry_first'
              ? "Why industry first?\n\nAn AI classifier analyzed your query against Apollo's industry categories and found a SPECIFIC match. Tested: industry-based search gives 45-90% target rate (most companies ARE your targets). Keywords give only 10-40% for this segment.\n\nApollo's organization_industry_tag_ids filter provides the best pagination (up to 100 companies per page) and highest precision.\n\nWhen industry pages are exhausted (0 new targets in a full batch), the system automatically switches to keyword-based search for broader coverage."
              : "Why keywords first?\n\nAn AI classifier analyzed your query against Apollo's industry categories and found them TOO BROAD. For example, 'IT consulting' maps to 'information technology & services' which includes SaaS companies, hardware vendors, magazines, and recruiters — mostly NOT your targets.\n\nSpecific keywords (e.g. 'IT consulting', 'managed IT services') give better targeting for niche segments, even though pagination is less consistent.\n\nWhen keyword pages are exhausted, the system falls back to industry filters for maximum TAM coverage."
            } style={{ cursor: 'help', fontSize: 10, color: 'var(--text-muted)', textDecoration: 'underline dotted', marginLeft: 4 }}>(why?)</span>
          </div>

          {/* Primary filters */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', color: 'var(--success)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ fontSize: 12 }}>▶</span> Active filters
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {run.filters.filter_strategy === 'industry_first' && run.filters.industries?.map((ind: string) => (
                <span key={ind} style={{ padding: '2px 8px', borderRadius: 4, background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.2)', fontSize: 11, color: '#22c55e' }}>
                  {ind}
                </span>
              ))}
              {run.filters.filter_strategy !== 'industry_first' && run.filters.q_organization_keyword_tags?.slice(0, 8).map((kw: string) => (
                <span key={kw} style={{ padding: '2px 8px', borderRadius: 4, background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)', fontSize: 11, color: '#3b82f6' }}>
                  {kw}
                </span>
              ))}
              {run.filters.organization_locations?.map((loc: string) => (
                <span key={loc} style={{ padding: '2px 8px', borderRadius: 4, background: 'var(--active-bg)', fontSize: 11 }}>
                  <span style={{ color: 'var(--text-muted)' }}>geo:</span> {loc}
                </span>
              ))}
              {run.filters.organization_num_employees_ranges?.map((r: string) => (
                <span key={r} style={{ padding: '2px 8px', borderRadius: 4, background: 'var(--active-bg)', fontSize: 11 }}>
                  <span style={{ color: 'var(--text-muted)' }}>size:</span> {r}
                </span>
              ))}
            </div>
          </div>

          {/* Backlog filters */}
          <div style={{ opacity: 0.6 }}>
            <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ fontSize: 12 }}>⏸</span> Backlog (after active exhausted)
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {run.filters.filter_strategy === 'industry_first' && run.filters.q_organization_keyword_tags?.slice(0, 6).map((kw: string) => (
                <span key={kw} style={{ padding: '2px 8px', borderRadius: 4, border: '1px dashed var(--border)', fontSize: 11, color: 'var(--text-muted)' }}>
                  {kw}
                </span>
              ))}
              {run.filters.filter_strategy !== 'industry_first' && run.filters.industries?.map((ind: string) => (
                <span key={ind} style={{ padding: '2px 8px', borderRadius: 4, border: '1px dashed var(--border)', fontSize: 11, color: 'var(--text-muted)' }}>
                  {ind}
                </span>
              ))}
              {!run.filters.industries?.length && run.filters.filter_strategy !== 'industry_first' && (
                <span style={{ fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>no industry fallback available</span>
              )}
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, fontStyle: 'italic' }}>
              Switches when active filters yield 0 new targets for a full batch
              <span title="Apollo filters within different types (industry + keywords) are applied as AND — combining them NARROWS results instead of broadening. That's why we use one approach at a time. When the active approach returns a full batch (10 pages) with zero new target companies, the pipeline automatically switches to the backlog filters to find more targets from a different angle." style={{ cursor: 'help', textDecoration: 'underline dotted', marginLeft: 4 }}>(why?)</span>
            </div>
          </div>
        </div>
      )}

      {showPeopleFilters && (
        <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-card)', border: '1px solid var(--border)', marginBottom: 12, fontSize: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 8 }}>People Search Strategy</div>

          {/* Apollo seniority filters */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', color: 'var(--info)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
              Apollo seniority filter
              <span title={"Why seniority filter instead of specific job titles?\n\nTested on real data: searching by specific titles (e.g. 'CMO', 'Head of E-commerce') returns 0-1 people per company — Apollo's title database doesn't match GPT-predicted titles. Searching by seniority levels returns 4-25 people per company, including the same decision makers.\n\nAlso tested: combining seniority + titles in one search. Apollo treats them as AND (intersection), which REDUCES results to 0-3. That's why we search by seniority ONLY, then prioritize by role match client-side.\n\nThis search is FREE (no Apollo credits). Only the final top contacts get email enrichment (1 credit each)."} style={{ cursor: 'help', fontSize: 10, color: 'var(--text-muted)', textDecoration: 'underline dotted' }}>(?)</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {['owner', 'founder', 'c_suite', 'vp', 'head', 'director'].map(s => (
                <span key={s} style={{ padding: '2px 8px', borderRadius: 4, background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.2)', fontSize: 11, color: '#3b82f6' }}>
                  {s}
                </span>
              ))}
            </div>
          </div>

          {/* Target roles from offer */}
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', color: '#f59e0b', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
              Target roles (from offer analysis)
              <span title="These roles were identified during website analysis and aligned with you. People matching these roles are PRIORITIZED in the search results. Apollo returns all C-level/VP/director people, then we rank them by how well their title matches these target roles. The best matches get their emails enriched first." style={{ cursor: 'help', fontSize: 10, color: 'var(--text-muted)', textDecoration: 'underline dotted' }}>(?)</span>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {(run?.people_filters?.person_titles || run?.offer_summary?.target_roles?.titles || ['CEO', 'CMO', 'VP Sales', 'Head of Digital']).map((t: string) => (
                <span key={t} style={{ padding: '2px 8px', borderRadius: 4, background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)', fontSize: 11, color: '#f59e0b' }}>
                  ★ {t}
                </span>
              ))}
            </div>
            {run?.offer_summary?.target_roles?.reasoning && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, fontStyle: 'italic' }}>
                {run.offer_summary.target_roles.reasoning}
              </div>
            )}
          </div>

          {/* Max per company + enrichment rule */}
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', padding: '6px 0', borderTop: '1px solid var(--border)' }}>
            <span style={{ fontSize: 11 }}>
              <span style={{ color: 'var(--text-muted)' }}>Max per company:</span>{' '}
              <strong>{run?.kpi?.max_people_per_company || 3}</strong>
              <span title="Only the top N contacts per company (ranked by seniority + role match) will have their emails enriched. Email enrichment costs 1 Apollo credit per person. Increasing this number increases credit spend." style={{ cursor: 'help', fontSize: 10, color: 'var(--text-muted)', textDecoration: 'underline dotted', marginLeft: 4 }}>(?)</span>
            </span>
            <span style={{ fontSize: 11 }}>
              <span style={{ color: 'var(--text-muted)' }}>Email enrichment:</span>{' '}
              <span style={{ color: '#22c55e' }}>verified only</span>
              <span title="Only contacts with Apollo email_status='verified' are included. Apollo verifies email deliverability before returning it. This ensures high-quality outreach-ready emails." style={{ cursor: 'help', fontSize: 10, color: 'var(--text-muted)', textDecoration: 'underline dotted', marginLeft: 4 }}>(?)</span>
            </span>
          </div>

          {/* How it works explanation */}
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 6, lineHeight: 1.5, borderTop: '1px solid var(--border)', paddingTop: 6 }}>
            <strong>How it works:</strong> Apollo searches for people with senior roles at each target company (FREE).
            Results are ranked by: 1) seniority level (CEO → VP → Director) and 2) match to target roles above.
            Only the top {run?.kpi?.max_people_per_company || 3} per company get email enrichment (1 credit each, verified emails only).
          </div>

          {totalContacts > 0 && (
            <div style={{ marginTop: 8 }}>
              <Link to={`/crm?pipeline=${runId}`} style={{ fontSize: 12, color: 'var(--text-link)', textDecoration: 'none', fontWeight: 500 }}>
                View {totalContacts} people in CRM →
              </Link>
            </div>
          )}
        </div>
      )}

      {/* Campaign expandable block */}
      {showCampaign && run?.campaign && (
        <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-card)', border: '1px solid rgba(99,102,241,0.3)', marginBottom: 12, fontSize: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <span style={{ fontWeight: 600, fontSize: 13 }}>{run.campaign.name}</span>
              <span style={{ marginLeft: 8, padding: '1px 6px', borderRadius: 4, fontSize: 10, fontWeight: 600, textTransform: 'uppercase', background: run.campaign.status === 'mcp_draft' ? 'rgba(129,140,248,0.15)' : run.campaign.status === 'active' ? 'rgba(34,197,94,0.15)' : 'rgba(245,158,11,0.15)', color: run.campaign.status === 'mcp_draft' ? '#818cf8' : run.campaign.status === 'active' ? '#22c55e' : '#f59e0b' }}>{run.campaign.status}</span>
              {run.campaign.email_accounts?.length > 0 && (
                <span style={{ marginLeft: 8, color: 'var(--text-muted)' }}>{run.campaign.email_accounts.length} accounts: {run.campaign.email_accounts.map((a: any) => a.email).join(', ')}</span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {run.campaign.smartlead_url && <a href={run.campaign.smartlead_url} target="_blank" rel="noopener noreferrer" style={{ padding: '4px 10px', borderRadius: 6, background: 'rgba(99,102,241,0.12)', color: '#818cf8', textDecoration: 'none', fontSize: 11, border: '1px solid rgba(99,102,241,0.25)' }}>SmartLead ↗</a>}
              <Link to={`/campaigns/${run.campaign.id}`} style={{ padding: '4px 10px', borderRadius: 6, background: 'var(--bg)', color: 'var(--text-secondary)', textDecoration: 'none', fontSize: 11, border: '1px solid var(--border)' }}>Campaign</Link>
              <Link to={`/campaigns/${run.campaign.id}#accounts`} style={{ padding: '4px 10px', borderRadius: 6, background: 'var(--bg)', color: 'var(--text-secondary)', textDecoration: 'none', fontSize: 11, border: '1px solid var(--border)' }}>Accounts ({run.campaign.email_accounts?.length || 0})</Link>
            </div>
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

      <div style={{ overflowX: 'auto', overflowY: 'visible', paddingBottom: 8 }} className="pipeline-table-scroll">
        <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse', minWidth: 1400, tableLayout: Object.keys(columnWidths).length > 0 ? 'fixed' : 'auto' }}>
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
                  width={columnWidths[col.key]}
                  onResize={(w: number) => setColWidth(col.key, w)}
                />
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((c: any) => (
              <tr key={c.id} onClick={() => setSelectedCompany(c)} style={{ borderTop: '1px solid var(--border)', cursor: 'pointer' }} onMouseEnter={e => (e.currentTarget.style.background = 'var(--btn-hover)')} onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                {columns.map(col => {
                  // Custom columns from source_data.custom_columns or custom_analysis
                  const customCol = (col as any).customKey
                  const val = customCol
                    ? (c.source_data?.custom_columns?.[customCol] ?? c.source_data?.custom_analysis?.[customCol] ?? '—')
                    : c[col.key]

                  // Special rendering for known columns
                  if (col.key === 'domain') return (
                    <td key={col.key} style={{ padding: '7px 8px 7px 0' }}><a href={`https://${c.domain}`} target="_blank" rel="noopener" onClick={e => e.stopPropagation()} style={{ color: 'var(--text-link)' }}>{c.domain}</a></td>
                  )
                  if (col.key === 'analysis_segment') return (
                    <td key={col.key} style={{ padding: '7px 8px 7px 0', fontSize: 11 }}>
                      {c.analysis_segment ? (
                        <span style={{ padding: '1px 5px', borderRadius: 3, background: c.analysis_segment === 'NOT_A_MATCH' ? 'var(--bg)' : 'rgba(99,102,241,0.15)', color: c.analysis_segment === 'NOT_A_MATCH' ? 'var(--text-muted)' : '#818cf8', fontWeight: 500 }}>
                          {c.analysis_segment}
                        </span>
                      ) : '—'}
                    </td>
                  )
                  if (col.key === 'analysis_confidence') return (
                    <td key={col.key} style={{ padding: '7px 8px 7px 0', fontSize: 11, color: 'var(--text-muted)' }}>
                      —
                    </td>
                  )
                  if (col.key === 'status') return (
                    <td key={col.key} style={{ padding: '7px 0' }}>
                      <span style={{ color: STATUS_COLORS[c.status] || 'var(--text-muted)', fontWeight: c.status === 'target' || c.status === 'verified' ? 600 : 400 }}>{c.status}</span>
                    </td>
                  )
                  if (col.key === 'contacts_count') return (
                    <td key={col.key} style={{ padding: '7px 8px 7px 0', fontSize: 12 }}>
                      {(c.contacts_count || 0) > 0 ? (
                        <a href={`/crm?domain=${c.domain}`} target="_blank" rel="noopener" onClick={e => e.stopPropagation()}
                          style={{ color: c.status === 'blacklisted' ? 'var(--text-muted)' : 'var(--text-link)', fontWeight: 500 }}>
                          {c.contacts_count}
                        </a>
                      ) : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                    </td>
                  )
                  // Custom column with badge styling
                  if (customCol) return (
                    <td key={col.key} style={{ padding: '7px 8px 7px 0', fontSize: 11 }}>
                      {val && val !== '—' ? (
                        <span style={{ padding: '1px 5px', borderRadius: 3, background: 'rgba(168,85,247,0.12)', color: '#a855f7', fontWeight: 500 }}>
                          {String(val).slice(0, 30)}
                        </span>
                      ) : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                    </td>
                  )
                  // Default rendering
                  return (
                    <td key={col.key} style={{ padding: '7px 8px 7px 0', color: 'var(--text-secondary)', fontSize: col.key === 'analysis_reasoning' ? 11 : undefined, maxWidth: col.key === 'analysis_reasoning' || col.key === 'scrape_text_preview' ? 200 : undefined, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {val != null ? String(val) : '—'}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Loading / gathering indicator with spinner */}
      {isGathering && (
        <div style={{ padding: '16px 0', textAlign: 'center', color: 'var(--info)', fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
          <span style={{ display: 'inline-block', width: 14, height: 14, border: '2px solid var(--info)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
          Gathering in progress... {companies.length} companies found so far
        </div>
      )}
      {loading && !isGathering && companies.length === 0 && (
        <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
          <span style={{ display: 'inline-block', width: 14, height: 14, border: '2px solid var(--text-muted)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
          Loading companies...
        </div>
      )}

      {filtered.length === 0 && !loading && (
        <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)' }}>No companies match filters.</div>
      )}

      {/* Load More */}
      {!loading && companies.length < totalCompanies && (
        <div style={{ textAlign: 'center', padding: '16px 0' }}>
          <button onClick={() => setCompanyPage(p => p + 1)}
            style={{ padding: '8px 24px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 12 }}>
            Load more ({companies.length} of {totalCompanies})
          </button>
        </div>
      )}

      {/* Modal */}
      {selectedCompany && <CompanyModal company={selectedCompany} onClose={() => setSelectedCompany(null)} />}
    </div>
  )
}
