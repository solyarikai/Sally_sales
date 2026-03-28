import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'

const API = '/api'

export default function PromptsPage() {
  const { runId } = useParams()
  const [prompts, setPrompts] = useState<any[]>([])
  const [expanded, setExpanded] = useState<number | null>(null)

  useEffect(() => {
    fetch(`${API}/pipeline/runs/${runId}/prompts`).then(r => r.ok ? r.json() : []).then(setPrompts)
  }, [runId])

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)' }}>Prompts — Run #{runId}</div>
        </div>
        <Link to={`/pipeline/${runId}`} style={{ padding: '4px 12px', borderRadius: 6, fontSize: 12, border: '1px solid var(--border)', color: 'var(--text-secondary)', textDecoration: 'none' }}>← Back to pipeline</Link>
      </div>

      {prompts.length === 0 ? (
        <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)' }}>No prompts used yet. Run the analyze phase to see GPT prompts.</div>
      ) : (
        <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.5, color: 'var(--text-muted)' }}>
              <th style={{ paddingBottom: 8 }}>Created</th>
              <th style={{ paddingBottom: 8 }}>Prompt ID</th>
              <th style={{ paddingBottom: 8 }}>Iteration</th>
              <th style={{ paddingBottom: 8 }}>Prompt Body</th>
              <th style={{ paddingBottom: 8 }}>Companies</th>
              <th style={{ paddingBottom: 8 }}>Targets</th>
              <th style={{ paddingBottom: 8 }}>Accuracy</th>
            </tr>
          </thead>
          <tbody>
            {prompts.map((p: any) => (
              <>
                <tr key={p.id} onClick={() => setExpanded(expanded === p.id ? null : p.id)} style={{ borderTop: '1px solid var(--border)', cursor: 'pointer' }}>
                  <td style={{ padding: '8px 8px 8px 0', color: 'var(--text-muted)' }}>{p.created_at ? new Date(p.created_at).toLocaleDateString() : '—'}</td>
                  <td style={{ padding: '8px 8px 8px 0' }}>#{p.id}</td>
                  <td style={{ padding: '8px 8px 8px 0' }}><Link to={`/pipeline/${runId}`} style={{ color: 'var(--text-link)' }}>#{runId}</Link></td>
                  <td style={{ padding: '8px 8px 8px 0', color: 'var(--text-secondary)', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.segment && <span style={{ padding: '1px 5px', borderRadius: 3, background: 'rgba(99,102,241,0.12)', color: '#818cf8', marginRight: 4, fontSize: 11 }}>{p.segment}</span>}
                    {p.prompt_text?.slice(0, 60) || p.tool || '...'}
                  </td>
                  <td style={{ padding: '8px 8px 8px 0' }}>{p.total_analyzed || p.total_companies || 0}</td>
                  <td style={{ padding: '8px 8px 8px 0', color: 'var(--success)' }}>{p.targets_found || 0}</td>
                  <td style={{ padding: '8px 0' }}>{p.total_analyzed && p.targets_found ? `${((p.targets_found / p.total_analyzed) * 100).toFixed(0)}%` : '—'}</td>
                </tr>
                {expanded === p.id && (
                  <tr key={`${p.id}-detail`}>
                    <td colSpan={7} style={{ paddingBottom: 12 }}>
                      <div style={{ marginLeft: 16, padding: 16, borderRadius: 8, background: 'var(--bg-card)', border: '1px solid var(--border)', fontSize: 12 }}>
                        <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 8 }}>Full Prompt</div>
                        <pre style={{ whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{p.prompt_text}</pre>
                        {p.avg_confidence && <div style={{ marginTop: 8 }}><span style={{ color: 'var(--text-muted)' }}>Avg confidence:</span> {(p.avg_confidence * 100).toFixed(1)}%</div>}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
