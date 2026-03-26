import { useProject } from '../App'

export default function RepliesPage() {
  const { project } = useProject()

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: 24 }}>
      <div style={{ fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)', marginBottom: 12 }}>
        Tasks {project ? `— ${project.name}` : ''}
      </div>

      <div style={{ padding: '60px 0', textAlign: 'center' }}>
        <div style={{ fontSize: 14, color: 'var(--text-secondary)', marginBottom: 8 }}>Replies will appear here once campaigns start receiving responses.</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          Flow: Pipeline → Gather → Analyze → Verify → Campaign → <b>Replies arrive here</b>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 16 }}>
          Same UX as main app Tasks: category tabs (Meetings, Interested, Questions, etc.), AI drafts, approve/dismiss/regenerate.
        </div>
      </div>
    </div>
  )
}
