import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { authHeaders } from '../App'

const API = '/api'

export default function ProjectsPage() {
  const [projects, setProjects] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API}/pipeline/projects`, { headers: authHeaders() })
      .then(r => r.json())
      .then(setProjects)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)' }}>Projects</div>
      </div>
      {loading ? <div style={{ color: 'var(--text-muted)', padding: 40, textAlign: 'center' }}>Loading...</div> :
       projects.length === 0 ? <div style={{ color: 'var(--text-muted)', padding: 40, textAlign: 'center' }}>No projects yet. Create one via MCP.</div> : (
        <div style={{ display: 'grid', gap: 12 }}>
          {projects.map((p: any) => (
            <div key={p.id} style={{ padding: 16, border: '1px solid var(--border)', borderRadius: 8, background: 'var(--bg-card)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text)' }}>{p.name}</div>
                <Link to={`/pipeline`} style={{ fontSize: 12, color: 'var(--text-link)', textDecoration: 'none' }}>View pipeline →</Link>
              </div>
              {p.target_segments && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6 }}>
                  <span style={{ fontWeight: 500 }}>ICP:</span> {p.target_segments}
                </div>
              )}
              <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-secondary)' }}>
                {p.sender_name && <span>Sender: {p.sender_name}</span>}
                {p.sender_company && <span>Company: {p.sender_company}</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
