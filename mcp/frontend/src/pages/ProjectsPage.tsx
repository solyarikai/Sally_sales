import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { authHeaders } from '../App'

const API = '/api'

function ProjectCard({ project }: { project: any }) {
  const [expanded, setExpanded] = useState(false)
  const [runs, setRuns] = useState<any[]>([])
  const [campaigns, setCampaigns] = useState<string[]>([])

  useEffect(() => {
    if (!expanded) return
    // Fetch pipeline runs for this project
    fetch(`${API}/pipeline/iterations`, { headers: authHeaders() })
      .then(r => r.json())
      .then((data: any[]) => {
        setRuns(data.filter((r: any) => r.project_id === project.id))
      })
      .catch(() => {})

    // Campaign filters = connected campaigns
    if (project.campaign_filters && Array.isArray(project.campaign_filters)) {
      setCampaigns(project.campaign_filters)
    }
  }, [expanded, project.id])

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, background: 'var(--bg-card)', overflow: 'hidden' }}>
      <div
        onClick={() => setExpanded(!expanded)}
        style={{ padding: 16, cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
      >
        <div>
          <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text)' }}>{project.name}</div>
          {project.target_segments && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
              <span style={{ fontWeight: 500 }}>ICP:</span> {project.target_segments}
            </div>
          )}
          <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
            {project.sender_name && <span>Sender: {project.sender_name}</span>}
            {project.sender_company && <span>Company: {project.sender_company}</span>}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Link to="/pipeline" onClick={e => e.stopPropagation()} style={{ fontSize: 12, color: 'var(--text-link)', textDecoration: 'none', padding: '4px 10px', borderRadius: 6, border: '1px solid var(--border)' }}>Pipeline →</Link>
          <Link to="/crm" onClick={e => e.stopPropagation()} style={{ fontSize: 12, color: 'var(--text-link)', textDecoration: 'none', padding: '4px 10px', borderRadius: 6, border: '1px solid var(--border)' }}>CRM →</Link>
          <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {expanded && (
        <div style={{ borderTop: '1px solid var(--border)', padding: 16, background: 'var(--bg)' }}>
          {/* Connected Campaigns */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 6 }}>Connected Campaigns ({campaigns.length})</div>
            {campaigns.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {campaigns.map((c: string, i: number) => (
                  <span key={i} style={{ fontSize: 11, padding: '2px 8px', borderRadius: 4, background: 'rgba(99,102,241,0.1)', color: '#6366f1' }}>{c}</span>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No campaigns connected. Import via MCP.</div>
            )}
          </div>

          {/* Quick Links */}
          <div style={{ marginBottom: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Link to={`/pipeline`} style={{ fontSize: 12, padding: '4px 10px', borderRadius: 6, background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-link)', textDecoration: 'none' }}>
              Pipeline runs ({runs.length}) →
            </Link>
            <Link to={`/campaigns`} style={{ fontSize: 12, padding: '4px 10px', borderRadius: 6, background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-link)', textDecoration: 'none' }}>
              Campaigns →
            </Link>
            <Link to={`/crm`} style={{ fontSize: 12, padding: '4px 10px', borderRadius: 6, background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-link)', textDecoration: 'none' }}>
              CRM contacts →
            </Link>
            <Link to={`/crm?reply_category=interested`} style={{ fontSize: 12, padding: '4px 10px', borderRadius: 6, background: 'rgba(34,197,94,0.1)', border: '1px solid rgba(34,197,94,0.3)', color: '#22c55e', textDecoration: 'none' }}>
              Warm leads →
            </Link>
          </div>

          {/* Pipeline Runs */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 6 }}>Pipeline Runs ({runs.length})</div>
            {runs.length > 0 ? (
              <div style={{ display: 'grid', gap: 4 }}>
                {runs.map((r: any) => (
                  <Link key={r.id} to={`/pipeline/${r.id}`} style={{ textDecoration: 'none', display: 'flex', justifyContent: 'space-between', padding: '6px 10px', borderRadius: 6, background: 'var(--bg-card)', border: '1px solid var(--border)', fontSize: 12 }}>
                    <span style={{ color: 'var(--text)' }}>Run #{r.id} — {r.source_type || 'apollo'}</span>
                    <span style={{ color: 'var(--text-muted)' }}>{r.new_companies || 0} companies · {r.current_phase}</span>
                  </Link>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No pipeline runs yet.</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

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
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{projects.length} project{projects.length !== 1 ? 's' : ''}</div>
      </div>
      {loading ? <div style={{ color: 'var(--text-muted)', padding: 40, textAlign: 'center' }}>Loading...</div> :
       projects.length === 0 ? <div style={{ color: 'var(--text-muted)', padding: 40, textAlign: 'center' }}>No projects yet. Create one via MCP.</div> : (
        <div style={{ display: 'grid', gap: 12 }}>
          {projects.map((p: any) => <ProjectCard key={p.id} project={p} />)}
        </div>
      )}
    </div>
  )
}
