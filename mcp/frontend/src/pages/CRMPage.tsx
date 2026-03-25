import { useEffect, useState } from 'react'

const API = '/api'

export default function CRMPage() {
  const [companies, setCompanies] = useState<any[]>([])
  const [filter, setFilter] = useState({ status: 'all', search: '' })
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  useEffect(() => {
    fetch(`${API}/pipeline/crm/companies`).then(r => r.ok ? r.json() : []).then(setCompanies)
  }, [])

  const toggle = (id: number) => setExpanded(prev => {
    const n = new Set(prev)
    n.has(id) ? n.delete(id) : n.add(id)
    return n
  })

  const filtered = companies.filter(c => {
    if (filter.status === 'targets' && !c.is_target) return false
    if (filter.status === 'blacklisted' && !c.is_blacklisted) return false
    if (filter.status === 'pending' && (c.is_target != null || c.is_blacklisted)) return false
    if (filter.search && !c.domain.includes(filter.search.toLowerCase()) && !(c.name || '').toLowerCase().includes(filter.search.toLowerCase())) return false
    return true
  })

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-[11px] uppercase tracking-wider font-medium" style={{ color: 'var(--text-muted)' }}>CRM</div>
          <div className="text-[13px] mt-0.5" style={{ color: 'var(--text-secondary)' }}>{companies.length} companies from all pipelines</div>
        </div>
        <div className="flex gap-2">
          <input
            className="px-2.5 py-1 rounded text-[13px] border"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text)' }}
            placeholder="Search domain or name..."
            value={filter.search}
            onChange={e => setFilter({ ...filter, search: e.target.value })}
          />
          <select
            className="px-2.5 py-1 rounded text-[13px] border"
            style={{ background: 'var(--bg-card)', borderColor: 'var(--border)', color: 'var(--text)' }}
            value={filter.status}
            onChange={e => setFilter({ ...filter, status: e.target.value })}
          >
            <option value="all">All</option>
            <option value="targets">Targets only</option>
            <option value="blacklisted">Blacklisted</option>
            <option value="pending">Pending</option>
          </select>
        </div>
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
          {filtered.map((c: any) => (
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
                <tr key={`${c.id}-d`}>
                  <td colSpan={8} className="pb-3">
                    <div className="rounded p-3 ml-8 text-[12px] space-y-1" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
                      <div className="grid grid-cols-2 gap-x-6 gap-y-1">
                        <div><span style={{ color: 'var(--text-muted)' }}>Domain:</span> {c.domain}</div>
                        <div><span style={{ color: 'var(--text-muted)' }}>Name:</span> {c.name || 'N/A'}</div>
                        <div><span style={{ color: 'var(--text-muted)' }}>Industry:</span> {c.industry || 'N/A'}</div>
                        <div><span style={{ color: 'var(--text-muted)' }}>Employees:</span> {c.employee_count || 'N/A'}</div>
                        <div><span style={{ color: 'var(--text-muted)' }}>Country:</span> {c.country || 'N/A'}</div>
                        <div><span style={{ color: 'var(--text-muted)' }}>City:</span> {c.city || 'N/A'}</div>
                      </div>
                      {c.analysis_reasoning && (
                        <div className="mt-2">
                          <div className="text-[11px] uppercase tracking-wider font-medium" style={{ color: 'var(--text-muted)' }}>GPT Reasoning</div>
                          <div style={{ color: 'var(--text-secondary)' }}>{c.analysis_reasoning}</div>
                        </div>
                      )}
                      {c.is_blacklisted && <div style={{ color: 'var(--danger)' }}>Blacklist: {c.blacklist_reason || 'matched existing campaign'}</div>}
                    </div>
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
      {filtered.length === 0 && <div className="py-8 text-center" style={{ color: 'var(--text-muted)' }}>No companies match filters.</div>}
      <div className="text-[11px] mt-4" style={{ color: 'var(--text-muted)' }}>Showing {filtered.length} of {companies.length}</div>
    </div>
  )
}
