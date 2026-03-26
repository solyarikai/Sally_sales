import { useEffect, useState } from 'react'
import { authHeaders, getToken } from '../App'

const API = '/api'

export default function ProjectsPage() {
  const [projects, setProjects] = useState<any[]>([])
  const [expanded, setExpanded] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ name: '', target_segments: '', target_industries: '', sender_name: '', sender_company: '' })

  const load = () => {
    fetch(`${API}/pipeline/projects`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : []).then(setProjects)
  }
  useEffect(() => { load() }, [])

  const create = async () => {
    if (!form.name) return
    await fetch(`${API}/pipeline/projects`, { method: 'POST', headers: authHeaders(), body: JSON.stringify(form) })
    setCreating(false)
    setForm({ name: '', target_segments: '', target_industries: '', sender_name: '', sender_company: '' })
    load()
  }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)' }}>Projects</div>
        <button onClick={() => setCreating(!creating)} style={{ padding: '4px 12px', borderRadius: 6, fontSize: 12, border: '1px solid var(--border)', background: 'var(--bg-card)', color: 'var(--text)', cursor: 'pointer' }}>
          {creating ? 'Cancel' : '+ New Project'}
        </button>
      </div>

      {creating && (
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 16, marginBottom: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {[
              { key: 'name', label: 'Project Name', placeholder: 'EasyStaff Global - DACH' },
              { key: 'sender_name', label: 'Sender Name', placeholder: 'Marina Mikhaylova' },
              { key: 'sender_company', label: 'Sender Company', placeholder: 'easystaff.io' },
              { key: 'target_industries', label: 'Target Industries', placeholder: 'SaaS, Fintech, IT Services' },
            ].map(f => (
              <div key={f.key}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>{f.label}</div>
                <input value={(form as any)[f.key]} onChange={e => setForm({ ...form, [f.key]: e.target.value })} placeholder={f.placeholder}
                  style={{ width: '100%', padding: '6px 10px', borderRadius: 6, fontSize: 13, background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text)', outline: 'none' }} />
              </div>
            ))}
          </div>
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>ICP / Target Segments</div>
            <textarea value={form.target_segments} onChange={e => setForm({ ...form, target_segments: e.target.value })} placeholder="Series A-B SaaS in DACH, 50-500 employees, hiring remote talent"
              style={{ width: '100%', padding: '6px 10px', borderRadius: 6, fontSize: 13, background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text)', outline: 'none', minHeight: 60, resize: 'vertical' }} />
          </div>
          <button onClick={create} style={{ marginTop: 8, padding: '6px 16px', borderRadius: 6, fontSize: 13, border: 'none', background: 'var(--info)', color: 'white', cursor: 'pointer' }}>Create Project</button>
        </div>
      )}

      {projects.length === 0 ? (
        <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)' }}>No projects. Create one to get started.</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {projects.map((p: any) => (
            <div key={p.id} style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
              <div onClick={() => setExpanded(expanded === p.id ? null : p.id)} style={{ padding: '12px 16px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 500 }}>{p.name}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{p.sender_name} @ {p.sender_company}</div>
                </div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{expanded === p.id ? '▼' : '▶'}</span>
              </div>
              {expanded === p.id && (
                <div style={{ padding: '0 16px 16px', borderTop: '1px solid var(--border)' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 24px', marginTop: 12, fontSize: 12 }}>
                    <div><span style={{ color: 'var(--text-muted)' }}>ICP:</span> {p.target_segments || 'Not defined'}</div>
                    <div><span style={{ color: 'var(--text-muted)' }}>Industries:</span> {p.target_industries || 'Not defined'}</div>
                    <div><span style={{ color: 'var(--text-muted)' }}>Sender:</span> {p.sender_name || '—'}</div>
                    <div><span style={{ color: 'var(--text-muted)' }}>Company:</span> {p.sender_company || '—'}</div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
