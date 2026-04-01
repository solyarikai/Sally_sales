import { useState, useEffect, useCallback, useMemo } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { authHeaders } from '../App'

const API = '/api'

export default function MCPCRMPage() {
  const [searchParams] = useSearchParams()
  const pipelineId = searchParams.get('pipeline')
  const [contacts, setContacts] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [sortCol, setSortCol] = useState('created_at')
  const [sortDir, setSortDir] = useState<'asc'|'desc'>('desc')

  // Column visibility (persisted)
  const [hiddenCols, setHiddenCols] = useState<Set<string>>(() => {
    try {
      const s = localStorage.getItem('mcp_crm_hidden')
      return s ? new Set(JSON.parse(s)) : new Set()
    } catch { return new Set() }
  })
  const [showColPicker, setShowColPicker] = useState(false)

  const toggleCol = (col: string) => {
    setHiddenCols(prev => {
      const next = new Set(prev)
      next.has(col) ? next.delete(col) : next.add(col)
      localStorage.setItem('mcp_crm_hidden', JSON.stringify([...next]))
      return next
    })
  }

  const loadContacts = useCallback(async () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (pipelineId) params.set('pipeline', pipelineId)
    if (search) params.set('search', search)
    const r = await fetch(`${API}/pipeline/crm/contacts?${params}`, { headers: authHeaders() })
    if (r.ok) {
      const data = await r.json()
      setContacts(data.contacts || [])
      setTotal(data.total || 0)
    }
    setLoading(false)
  }, [pipelineId, search])

  useEffect(() => { loadContacts() }, [loadContacts])

  // Sort
  const sorted = useMemo(() => {
    return [...contacts].sort((a, b) => {
      const av = a[sortCol] ?? '', bv = b[sortCol] ?? ''
      const cmp = String(av).localeCompare(String(bv))
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [contacts, sortCol, sortDir])

  const toggleSort = (col: string) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(col); setSortDir('asc') }
  }

  const allColumns = [
    { key: 'email', label: 'Email' },
    { key: 'first_name', label: 'Name' },
    { key: 'company_name', label: 'Company' },
    { key: 'job_title', label: 'Title' },
    { key: 'country', label: 'Geo' },
    { key: 'domain', label: 'Website' },
    { key: 'linkedin_url', label: 'LinkedIn' },
    { key: 'email_verified', label: 'Verified' },
    { key: 'created_at', label: 'Added' },
  ]
  const visibleColumns = allColumns.filter(c => !hiddenCols.has(c.key))

  return (
    <div style={{ padding: '16px 20px', maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12, fontSize: 12, color: 'var(--text-muted)' }}>
        <span>{total} contacts</span>
        {pipelineId && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            from <Link to={`/pipeline/${pipelineId}`} style={{ color: 'var(--text-link)', textDecoration: 'none' }}>pipeline #{pipelineId}</Link>
            <Link to="/crm" style={{ fontSize: 11, color: 'var(--text-muted)', textDecoration: 'none' }}>(show all)</Link>
          </span>
        )}

        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search..."
            style={{ padding: '4px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text)', fontSize: 12, width: 200, outline: 'none' }}
          />
          {/* Columns picker */}
          <div style={{ position: 'relative' }}>
            <button onClick={() => setShowColPicker(!showColPicker)} style={{ padding: '4px 8px', borderRadius: 6, fontSize: 14, border: '1px solid var(--border)', background: showColPicker ? 'var(--active-bg)' : 'transparent', color: 'var(--text-muted)', cursor: 'pointer' }} title="Columns">⊞</button>
            {showColPicker && (
              <div style={{ position: 'absolute', top: '100%', right: 0, marginTop: 4, zIndex: 50, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 8, minWidth: 160, boxShadow: '0 8px 24px rgba(0,0,0,0.3)' }}>
                {allColumns.map(c => (
                  <label key={c.key} onClick={() => toggleCol(c.key)} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '5px 8px', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'var(--active-bg)')} onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                    <span style={{ width: 16, height: 16, borderRadius: 4, border: '2px solid ' + (!hiddenCols.has(c.key) ? '#3b82f6' : 'var(--border)'), background: !hiddenCols.has(c.key) ? '#3b82f6' : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontSize: 10, flexShrink: 0 }}>
                      {!hiddenCols.has(c.key) && '✓'}
                    </span>
                    <span style={{ color: !hiddenCols.has(c.key) ? 'var(--text)' : 'var(--text-muted)' }}>{c.label}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
          {/* Export */}
          <button onClick={() => {
            const hdrs = visibleColumns.map(c => c.label)
            const esc = (v: any) => `"${String(v ?? '').replace(/"/g, '""')}"`
            const rows = sorted.map(r => visibleColumns.map(c => esc(r[c.key])).join(','))
            const csv = [hdrs.join(','), ...rows].join('\n')
            const blob = new Blob([csv], {type: 'text/csv'})
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a'); a.href = url; a.download = `crm_contacts${pipelineId ? '_pipeline' + pipelineId : ''}.csv`; a.click(); URL.revokeObjectURL(url)
          }} style={{ padding: '4px 8px', borderRadius: 6, fontSize: 14, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-muted)', cursor: 'pointer' }} title="Export CSV">↓</button>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Loading...</div>
      ) : sorted.length === 0 ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>No contacts found.</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse', tableLayout: 'fixed' }}>
            <thead>
              <tr>
                {visibleColumns.map(col => (
                  <th key={col.key} onClick={() => toggleSort(col.key)} style={{ padding: '6px 8px', textAlign: 'left', cursor: 'pointer', fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: 0.5, color: sortCol === col.key ? 'var(--text)' : 'var(--text-muted)', userSelect: 'none', borderBottom: '1px solid var(--border)' }}>
                    {col.label}{sortCol === col.key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((c: any) => (
                <tr key={c.id} style={{ borderTop: '1px solid var(--border)' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'var(--btn-hover)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                  {visibleColumns.map(col => {
                    const val = c[col.key]
                    if (col.key === 'email') return (
                      <td key={col.key} style={{ padding: '7px 8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        <span style={{ color: 'var(--text)' }}>{val || '—'}</span>
                      </td>
                    )
                    if (col.key === 'first_name') return (
                      <td key={col.key} style={{ padding: '7px 8px' }}>{c.first_name || ''} {c.last_name || ''}</td>
                    )
                    if (col.key === 'domain') return (
                      <td key={col.key} style={{ padding: '7px 8px' }}>
                        {val ? <a href={`https://${val}`} target="_blank" rel="noopener" style={{ color: 'var(--text-link)', fontSize: 12 }}>{val}</a> : '—'}
                      </td>
                    )
                    if (col.key === 'linkedin_url') return (
                      <td key={col.key} style={{ padding: '7px 8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {val ? <a href={val} target="_blank" rel="noopener" style={{ color: 'var(--text-link)', fontSize: 11 }}>{val.replace('https://www.linkedin.com/in/', '').replace('https://linkedin.com/in/', '').slice(0, 20)}</a> : '—'}
                      </td>
                    )
                    if (col.key === 'email_verified') return (
                      <td key={col.key} style={{ padding: '7px 8px', color: val ? '#22c55e' : 'var(--text-muted)', fontSize: 11 }}>{val ? '✓' : '—'}</td>
                    )
                    if (col.key === 'created_at') return (
                      <td key={col.key} style={{ padding: '7px 8px', fontSize: 11, color: 'var(--text-muted)' }}>{val ? new Date(val).toLocaleDateString() : '—'}</td>
                    )
                    return <td key={col.key} style={{ padding: '7px 8px', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{val || '—'}</td>
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
