import { useEffect, useState, useMemo } from 'react'
import { useProject } from '../App'

const API = '/api'

// Same status config as main app
const STATUS_DOTS: Record<string, string> = {
  new: '#9ca3af', replied: '#3b82f6', warm: '#f59e0b', meeting_booked: '#f97316',
  meeting_held: '#22c55e', qualified: '#10b981', not_qualified: '#4b5563',
}

export default function CRMPage() {
  const { project } = useProject()
  const [contacts, setContacts] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [expanded, setExpanded] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'contacts' | 'companies'>('contacts')

  const loadContacts = async () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (project) params.set('project_id', project.id)
    if (search) params.set('search', search)
    if (statusFilter !== 'all') params.set('status', statusFilter)
    try {
      const res = await fetch(`${API}/pipeline/crm/contacts?${params}`)
      if (res.ok) {
        const data = await res.json()
        setContacts(data.contacts || data)
        setTotal(data.total || (data.contacts || data).length)
      }
    } catch {}
    setLoading(false)
  }

  const loadCompanies = async () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (project) params.set('project_id', project.id)
    try {
      const res = await fetch(`${API}/pipeline/crm/companies?${params}`)
      if (res.ok) {
        const data = await res.json()
        setContacts(data)
        setTotal(data.length)
      }
    } catch {}
    setLoading(false)
  }

  useEffect(() => {
    if (tab === 'contacts') loadContacts()
    else loadCompanies()
  }, [project, tab])

  // Debounced search
  useEffect(() => {
    const t = setTimeout(() => { if (tab === 'contacts') loadContacts() }, 300)
    return () => clearTimeout(t)
  }, [search, statusFilter])

  const filteredContacts = useMemo(() => {
    if (tab === 'companies') {
      return contacts.filter(c => {
        if (search && !c.domain?.includes(search.toLowerCase()) && !(c.name || '').toLowerCase().includes(search.toLowerCase())) return false
        return true
      })
    }
    return contacts
  }, [contacts, search, tab])

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: 24 }}>

      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)' }}>
            CRM {project ? `— ${project.name}` : ''}
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
            {total} {tab === 'contacts' ? 'contacts' : 'companies'}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {/* Tab toggle */}
          <div style={{ display: 'flex', background: 'var(--active-bg)', borderRadius: 6, padding: 2 }}>
            {(['contacts', 'companies'] as const).map(t => (
              <button key={t} onClick={() => setTab(t)} style={{
                padding: '4px 12px', borderRadius: 4, fontSize: 12, fontWeight: 500,
                border: 'none', cursor: 'pointer',
                background: tab === t ? 'var(--bg-card)' : 'transparent',
                color: tab === t ? 'var(--text)' : 'var(--text-muted)',
                boxShadow: tab === t ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              }}>{t}</button>
            ))}
          </div>

          {/* Search */}
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search..."
            style={{
              padding: '5px 10px', borderRadius: 6, fontSize: 13, width: 200,
              background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text)',
              outline: 'none',
            }}
          />

          {tab === 'contacts' && (
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{
              padding: '5px 8px', borderRadius: 6, fontSize: 13,
              background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text)',
            }}>
              <option value="all">All statuses</option>
              <option value="target">Targets</option>
              <option value="blacklisted">Blacklisted</option>
              <option value="pending">Pending</option>
            </select>
          )}
        </div>
      </div>

      {loading ? (
        <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)' }}>Loading...</div>
      ) : (
        <>
          {/* Table */}
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ textAlign: 'left', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-muted)' }}>
                {tab === 'contacts' ? (
                  <>
                    <th style={{ paddingBottom: 8, width: 20 }}></th>
                    <th style={{ paddingBottom: 8 }}>Name</th>
                    <th style={{ paddingBottom: 8 }}>Email</th>
                    <th style={{ paddingBottom: 8 }}>Company</th>
                    <th style={{ paddingBottom: 8 }}>Title</th>
                    <th style={{ paddingBottom: 8 }}>Source</th>
                    <th style={{ paddingBottom: 8 }}>Status</th>
                  </>
                ) : (
                  <>
                    <th style={{ paddingBottom: 8, width: 20 }}></th>
                    <th style={{ paddingBottom: 8 }}>Domain</th>
                    <th style={{ paddingBottom: 8 }}>Name</th>
                    <th style={{ paddingBottom: 8 }}>Industry</th>
                    <th style={{ paddingBottom: 8 }}>Size</th>
                    <th style={{ paddingBottom: 8 }}>Country</th>
                    <th style={{ paddingBottom: 8 }}>Confidence</th>
                    <th style={{ paddingBottom: 8 }}>Status</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {filteredContacts.map((c: any) => (
                <ContactRow key={c.id} c={c} tab={tab} expanded={expanded === c.id} onToggle={() => setExpanded(expanded === c.id ? null : c.id)} />
              ))}
            </tbody>
          </table>

          {filteredContacts.length === 0 && (
            <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)' }}>
              {tab === 'contacts' ? 'No contacts yet. Run a pipeline with verification to extract contacts.' : 'No companies. Run a gathering pipeline first.'}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function ContactRow({ c, tab, expanded, onToggle }: { c: any; tab: string; expanded: boolean; onToggle: () => void }) {
  if (tab === 'companies') {
    return (
      <>
        <tr style={{ borderTop: '1px solid var(--border)', cursor: 'pointer' }} onClick={onToggle}>
          <td style={{ padding: '8px 4px', fontSize: 11, color: 'var(--text-muted)' }}>{expanded ? '▼' : '▶'}</td>
          <td style={{ padding: '8px 8px 8px 0', color: 'var(--text-link)' }}>{c.domain}</td>
          <td style={{ padding: '8px 8px 8px 0' }}>{c.name || <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
          <td style={{ padding: '8px 8px 8px 0', color: 'var(--text-secondary)' }}>{c.industry || '—'}</td>
          <td style={{ padding: '8px 8px 8px 0', color: 'var(--text-secondary)' }}>{c.employee_count || '—'}</td>
          <td style={{ padding: '8px 8px 8px 0', color: 'var(--text-secondary)' }}>{c.country || '—'}</td>
          <td style={{ padding: '8px 8px 8px 0' }}>
            {c.analysis_confidence != null
              ? <span style={{ color: c.analysis_confidence > 0.7 ? 'var(--success)' : c.analysis_confidence > 0.4 ? 'var(--warning)' : 'var(--danger)' }}>{(c.analysis_confidence * 100).toFixed(0)}%</span>
              : <span style={{ color: 'var(--text-muted)' }}>—</span>}
          </td>
          <td style={{ padding: '8px 0' }}>
            {c.is_blacklisted ? <span style={{ color: 'var(--danger)' }}>blacklisted</span> :
             c.is_target === true ? <span style={{ color: 'var(--success)' }}>target</span> :
             c.is_target === false ? <span style={{ color: 'var(--text-muted)' }}>rejected</span> :
             <span style={{ color: 'var(--text-muted)' }}>pending</span>}
          </td>
        </tr>
        {expanded && <CompanyDetail c={c} />}
      </>
    )
  }

  // Contacts tab
  return (
    <>
      <tr style={{ borderTop: '1px solid var(--border)', cursor: 'pointer' }} onClick={onToggle}>
        <td style={{ padding: '8px 4px', fontSize: 11, color: 'var(--text-muted)' }}>{expanded ? '▼' : '▶'}</td>
        <td style={{ padding: '8px 8px 8px 0' }}>{[c.first_name, c.last_name].filter(Boolean).join(' ') || <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
        <td style={{ padding: '8px 8px 8px 0', color: 'var(--text-link)' }}>{c.email || '—'}</td>
        <td style={{ padding: '8px 8px 8px 0', color: 'var(--text-secondary)' }}>{c.company_name || c.domain || '—'}</td>
        <td style={{ padding: '8px 8px 8px 0', color: 'var(--text-secondary)' }}>{c.job_title || '—'}</td>
        <td style={{ padding: '8px 8px 8px 0', color: 'var(--text-secondary)' }}>{c.email_source || '—'}</td>
        <td style={{ padding: '8px 0' }}>
          {c.email_verified ? <span style={{ color: 'var(--success)' }}>verified</span> : <span style={{ color: 'var(--text-muted)' }}>pending</span>}
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={7} style={{ paddingBottom: 12 }}>
            <div style={{ marginLeft: 32, padding: 12, borderRadius: 8, background: 'var(--bg-card)', border: '1px solid var(--border)', fontSize: 12 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 24px' }}>
                <div><span style={{ color: 'var(--text-muted)' }}>Email:</span> {c.email || 'N/A'}</div>
                <div><span style={{ color: 'var(--text-muted)' }}>LinkedIn:</span> {c.linkedin_url ? <a href={c.linkedin_url} target="_blank" style={{ color: 'var(--text-link)' }}>{c.linkedin_url.split('/in/')[1] || c.linkedin_url}</a> : 'N/A'}</div>
                <div><span style={{ color: 'var(--text-muted)' }}>Phone:</span> {c.phone || 'N/A'}</div>
                <div><span style={{ color: 'var(--text-muted)' }}>Verified:</span> {c.email_verified ? 'Yes' : 'No'}</div>
                <div><span style={{ color: 'var(--text-muted)' }}>Source:</span> {c.email_source || 'pipeline'}</div>
                <div><span style={{ color: 'var(--text-muted)' }}>Domain:</span> {c.domain || 'N/A'}</div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function CompanyDetail({ c }: { c: any }) {
  return (
    <tr>
      <td colSpan={8} style={{ paddingBottom: 12 }}>
        <div style={{ marginLeft: 32, padding: 12, borderRadius: 8, background: 'var(--bg-card)', border: '1px solid var(--border)', fontSize: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 24px' }}>
            <div><span style={{ color: 'var(--text-muted)' }}>Domain:</span> {c.domain}</div>
            <div><span style={{ color: 'var(--text-muted)' }}>Name:</span> {c.name || 'N/A'}</div>
            <div><span style={{ color: 'var(--text-muted)' }}>Industry:</span> {c.industry || 'N/A'}</div>
            <div><span style={{ color: 'var(--text-muted)' }}>Employees:</span> {c.employee_count || 'N/A'}{c.employee_range ? ` (${c.employee_range})` : ''}</div>
            <div><span style={{ color: 'var(--text-muted)' }}>Country:</span> {c.country || 'N/A'}</div>
            <div><span style={{ color: 'var(--text-muted)' }}>City:</span> {c.city || 'N/A'}</div>
            {c.linkedin_url && <div><span style={{ color: 'var(--text-muted)' }}>LinkedIn:</span> <a href={c.linkedin_url} target="_blank" style={{ color: 'var(--text-link)' }}>Profile</a></div>}
            {c.description && <div style={{ gridColumn: '1 / -1' }}><span style={{ color: 'var(--text-muted)' }}>Description:</span> {c.description}</div>}
          </div>

          {!c.name && !c.industry && (
            <div style={{ padding: '8px 10px', borderRadius: 6, background: 'var(--bg)', color: 'var(--warning)', fontSize: 11 }}>
              Fields empty — company was added via <b>manual source</b> (domain list only). Use <b>Apollo API</b> source to get full company data.
            </div>
          )}

          {c.analysis_reasoning && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-muted)', marginBottom: 4 }}>GPT Analysis</div>
              <div><span style={{ color: 'var(--text-muted)' }}>Segment:</span> {c.analysis_segment || 'N/A'}</div>
              <div><span style={{ color: 'var(--text-muted)' }}>Confidence:</span> {c.analysis_confidence ? `${(c.analysis_confidence * 100).toFixed(1)}%` : 'N/A'}</div>
              <div style={{ color: 'var(--text-secondary)', marginTop: 4 }}>{c.analysis_reasoning}</div>
            </div>
          )}

          {c.is_blacklisted && <div style={{ color: 'var(--danger)' }}>Blacklisted: {c.blacklist_reason || 'matched existing campaign'}</div>}

          {c.source_data && Object.keys(c.source_data).length > 0 && (
            <details>
              <summary style={{ fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer' }}>Raw source data</summary>
              <pre style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, padding: 8, borderRadius: 4, background: 'var(--bg)', overflow: 'auto', maxHeight: 200 }}>
                {JSON.stringify(c.source_data, null, 2)}
              </pre>
            </details>
          )}
        </div>
      </td>
    </tr>
  )
}
