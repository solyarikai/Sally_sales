import { useState, useEffect, useCallback } from 'react'
import { authHeaders } from '../App'

interface ReasoningData {
  found: boolean
  domain: string
  name?: string
  is_target?: boolean
  segment?: string
  reasoning?: string
  status?: string
  industry?: string
  employee_count?: number
  country?: string
  city?: string
  funding_stage?: string
  pipeline_link?: string
}

/**
 * Floating panel that shows MCP classification reasoning for a company.
 * Listens for clicks on AG Grid rows to detect contact selection,
 * extracts the domain, and fetches reasoning from MCP backend.
 */
export default function CRMReasoningPanel() {
  const [data, setData] = useState<ReasoningData | null>(null)
  const [loading, setLoading] = useState(false)
  const [visible, setVisible] = useState(false)
  const [lastDomain, setLastDomain] = useState('')

  const fetchReasoning = useCallback(async (domain: string) => {
    if (!domain || domain === lastDomain) return
    setLastDomain(domain)
    setLoading(true)
    setVisible(true)
    try {
      const res = await fetch(`/api/pipeline/company-reasoning?domain=${encodeURIComponent(domain)}`, { headers: authHeaders() })
      const json = await res.json()
      setData(json)
    } catch {
      setData({ found: false, domain })
    } finally {
      setLoading(false)
    }
  }, [lastDomain])

  useEffect(() => {
    // Listen for clicks on AG Grid rows — extract domain from the row
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      const row = target.closest('.ag-row')
      if (!row) return

      // Try to find domain/company info from the row cells
      const cells = row.querySelectorAll('.ag-cell')
      let domain = ''
      cells.forEach(cell => {
        const text = (cell as HTMLElement).innerText?.trim() || ''
        // Match domain-like patterns
        if (text.match(/^[a-z0-9-]+\.[a-z]{2,}$/i) && !domain) {
          domain = text.toLowerCase()
        }
        // Also check cell with data-col-id containing 'domain' or 'website'
        const colId = (cell as HTMLElement).getAttribute('col-id') || ''
        if ((colId.includes('domain') || colId.includes('website')) && text) {
          domain = text.toLowerCase().replace(/^https?:\/\//, '').replace(/\/.*$/, '')
        }
      })

      if (domain) {
        fetchReasoning(domain)
      }
    }

    document.addEventListener('click', handler)
    return () => document.removeEventListener('click', handler)
  }, [fetchReasoning])

  if (!visible) return null

  const panelStyle: React.CSSProperties = {
    position: 'fixed', right: 16, top: 80, width: 320,
    background: 'var(--bg-card, white)', border: '1px solid var(--border, #e5e5e5)',
    borderRadius: 10, boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
    zIndex: 1000, overflow: 'hidden', fontSize: 13,
  }

  return (
    <div style={panelStyle}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', borderBottom: '1px solid var(--border, #e5e5e5)' }}>
        <span style={{ fontWeight: 600, fontSize: 12, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-muted)' }}>Company Intelligence</span>
        <button onClick={() => { setVisible(false); setLastDomain('') }}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', fontSize: 16, lineHeight: 1 }}>x</button>
      </div>

      {/* Content */}
      <div style={{ padding: '12px 14px' }}>
        {loading && <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>Loading...</div>}

        {!loading && data && !data.found && (
          <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>No MCP data for {data.domain}</div>
        )}

        {!loading && data?.found && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {/* Company name + target badge */}
            <div>
              <div style={{ fontWeight: 600, fontSize: 14 }}>{data.name || data.domain}</div>
              <div style={{ marginTop: 4, display: 'flex', gap: 6, alignItems: 'center' }}>
                <span style={{
                  display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                  background: data.is_target ? '#dcfce7' : '#fee2e2',
                  color: data.is_target ? '#166534' : '#991b1b',
                }}>{data.is_target ? 'TARGET' : 'REJECTED'}</span>
                {data.segment && data.segment !== 'NOT_A_MATCH' && (
                  <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 500, background: 'var(--bg)', color: 'var(--text-muted)' }}>{data.segment}</span>
                )}
              </div>
            </div>

            {/* Reasoning */}
            {data.reasoning && (
              <div>
                <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>Why</div>
                <div style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--text)' }}>{data.reasoning}</div>
              </div>
            )}

            {/* Details */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 11 }}>
              {data.industry && (
                <div><span style={{ color: 'var(--text-muted)' }}>Industry:</span> {data.industry}</div>
              )}
              {data.employee_count && (
                <div><span style={{ color: 'var(--text-muted)' }}>Size:</span> {data.employee_count}</div>
              )}
              {data.country && (
                <div><span style={{ color: 'var(--text-muted)' }}>Location:</span> {data.city ? `${data.city}, ` : ''}{data.country}</div>
              )}
              {data.funding_stage && (
                <div><span style={{ color: 'var(--text-muted)' }}>Funding:</span> {data.funding_stage}</div>
              )}
            </div>

            {/* Pipeline link */}
            {data.pipeline_link && (
              <a href={data.pipeline_link} style={{ fontSize: 11, color: '#3b82f6' }}>View in pipeline</a>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
