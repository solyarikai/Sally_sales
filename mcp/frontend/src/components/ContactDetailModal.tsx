// Stub — will be replaced with full copy from main app
export function ContactDetailModal({ contact, onClose, replyMode, onSave, onNext, onPrev }: any) {
  if (!contact) return null
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div onClick={onClose} style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.5)' }} />
      <div style={{ position: 'relative', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 12, padding: 24, width: '80%', maxWidth: 700, maxHeight: '85vh', overflow: 'auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <h3>{contact.first_name} {contact.last_name}</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: 'var(--text-muted)' }}>×</button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 24px', fontSize: 13 }}>
          <div><span style={{ color: 'var(--text-muted)' }}>Email:</span> {contact.email}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Company:</span> {contact.company_name}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Title:</span> {contact.job_title}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Source:</span> {contact.source}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Status:</span> {contact.status}</div>
          <div><span style={{ color: 'var(--text-muted)' }}>Domain:</span> {contact.domain}</div>
          {contact.linkedin_url && <div><span style={{ color: 'var(--text-muted)' }}>LinkedIn:</span> <a href={contact.linkedin_url} target="_blank" style={{ color: 'var(--text-link)' }}>Profile</a></div>}
          {contact.phone && <div><span style={{ color: 'var(--text-muted)' }}>Phone:</span> {contact.phone}</div>}
        </div>
      </div>
    </div>
  )
}
