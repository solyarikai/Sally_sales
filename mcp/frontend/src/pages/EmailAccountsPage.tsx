import { useState, useEffect, useCallback } from 'react'
import { authHeaders } from '../App'

const API = '/api'

interface Account { id: number; email: string; name?: string; cached_at?: string }
interface AccountList { id: number; name: string; filter_pattern?: string; account_ids: Account[]; account_count: number; created_at: string }

export default function EmailAccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([])
  const [lists, setLists] = useState<AccountList[]>([])
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [search, setSearch] = useState('')
  const [tab, setTab] = useState<'accounts' | 'lists'>('accounts')
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [listName, setListName] = useState('')
  const [showSave, setShowSave] = useState(false)
  const [expandedList, setExpandedList] = useState<number | null>(null)

  const loadAccounts = useCallback(() => {
    setLoading(true)
    fetch(`${API}/pipeline/email-accounts`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : { accounts: [] })
      .then(d => setAccounts(d.accounts || []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const loadLists = useCallback(() => {
    fetch(`${API}/pipeline/email-account-lists`, { headers: authHeaders() })
      .then(r => r.ok ? r.json() : [])
      .then(setLists)
      .catch(console.error)
  }, [])

  useEffect(() => { loadAccounts(); loadLists() }, [])

  const sync = async () => {
    setSyncing(true)
    try {
      const r = await fetch(`${API}/pipeline/email-accounts/sync`, { method: 'POST', headers: authHeaders() })
      if (r.ok) loadAccounts()
    } finally { setSyncing(false) }
  }

  const saveList = async () => {
    if (!listName.trim() || selected.size === 0) return
    const selectedAccounts = accounts.filter(a => selected.has(a.id)).map(a => ({ id: a.id, email: a.email, name: a.name }))
    await fetch(`${API}/pipeline/email-account-lists`, {
      method: 'POST', headers: authHeaders(),
      body: JSON.stringify({ name: listName, account_ids: selectedAccounts, filter_pattern: search || null }),
    })
    setListName(''); setShowSave(false); setSelected(new Set()); loadLists()
  }

  const deleteList = async (id: number) => {
    await fetch(`${API}/pipeline/email-account-lists/${id}`, { method: 'DELETE', headers: authHeaders() })
    loadLists()
  }

  const filtered = search
    ? accounts.filter(a => (a.email || '').toLowerCase().includes(search.toLowerCase()) || (a.name || '').toLowerCase().includes(search.toLowerCase()))
    : accounts

  const toggleSelect = (id: number) => {
    const next = new Set(selected)
    next.has(id) ? next.delete(id) : next.add(id)
    setSelected(next)
  }

  const toggleAll = () => {
    if (selected.size === filtered.length) setSelected(new Set())
    else setSelected(new Set(filtered.map(a => a.id)))
  }

  const sectionHeader: React.CSSProperties = { fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text-muted)' }
  const card: React.CSSProperties = { border: '1px solid var(--border)', borderRadius: 8, background: 'var(--bg-card)' }

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', padding: 24 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <div style={sectionHeader}>Email Accounts</div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>
            {accounts.length} accounts cached
            {accounts.length > 0 && accounts[0].cached_at && <span> · last sync {new Date(accounts[0].cached_at).toLocaleDateString()}</span>}
          </div>
        </div>
        <button onClick={sync} disabled={syncing} style={{
          padding: '6px 16px', borderRadius: 6, fontSize: 12, fontWeight: 500, cursor: 'pointer',
          background: syncing ? 'var(--bg)' : 'rgba(99,102,241,0.12)', color: '#818cf8',
          border: '1px solid rgba(99,102,241,0.25)',
        }}>{syncing ? 'Syncing...' : 'Sync from SmartLead'}</button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 20, borderBottom: '1px solid var(--border)' }}>
        {(['accounts', 'lists'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '8px 20px', fontSize: 13, fontWeight: 500, cursor: 'pointer', border: 'none',
            borderBottom: tab === t ? '2px solid #818cf8' : '2px solid transparent',
            color: tab === t ? 'var(--text)' : 'var(--text-muted)', background: 'transparent',
          }}>{t === 'accounts' ? `All Accounts (${accounts.length})` : `Saved Lists (${lists.length})`}</button>
        ))}
      </div>

      {/* All Accounts Tab */}
      {tab === 'accounts' && (
        <>
          {/* Search + actions */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <input
              value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search by email or name..."
              style={{ flex: 1, padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text)', fontSize: 13 }}
            />
            {selected.size > 0 && (
              <button onClick={() => setShowSave(true)} style={{
                padding: '8px 16px', borderRadius: 6, fontSize: 12, fontWeight: 500, cursor: 'pointer',
                background: '#22c55e', color: 'white', border: 'none',
              }}>Save {selected.size} as List</button>
            )}
          </div>

          {/* Save list dialog */}
          {showSave && (
            <div style={{ ...card, padding: 16, marginBottom: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
              <input value={listName} onChange={e => setListName(e.target.value)} placeholder="List name (e.g. 'Elnar TFP accounts')"
                style={{ flex: 1, padding: '8px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text)', fontSize: 13 }}
                onKeyDown={e => e.key === 'Enter' && saveList()} />
              <button onClick={saveList} style={{ padding: '8px 16px', borderRadius: 6, background: '#818cf8', color: 'white', border: 'none', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>Save</button>
              <button onClick={() => setShowSave(false)} style={{ padding: '8px 12px', borderRadius: 6, background: 'var(--bg)', color: 'var(--text-muted)', border: '1px solid var(--border)', fontSize: 12, cursor: 'pointer' }}>Cancel</button>
            </div>
          )}

          {loading ? <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Loading...</div> :
           filtered.length === 0 ? <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>{accounts.length === 0 ? 'No accounts cached. Connect SmartLead in Setup, then click Sync.' : 'No accounts match your search.'}</div> : (
            <div style={card}>
              {/* Select all header */}
              <div style={{ padding: '8px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10, background: 'var(--bg)' }}>
                <input type="checkbox" checked={selected.size === filtered.length && filtered.length > 0} onChange={toggleAll}
                  style={{ width: 14, height: 14, cursor: 'pointer' }} />
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  {selected.size > 0 ? `${selected.size} selected` : `${filtered.length} accounts`}
                </span>
              </div>
              {filtered.map((a, i) => (
                <div key={a.id} style={{
                  padding: '10px 16px', display: 'flex', alignItems: 'center', gap: 10,
                  borderBottom: i < filtered.length - 1 ? '1px solid var(--border)' : 'none',
                }}>
                  <input type="checkbox" checked={selected.has(a.id)} onChange={() => toggleSelect(a.id)}
                    style={{ width: 14, height: 14, cursor: 'pointer' }} />
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e', flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.email}</div>
                    {a.name && <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.name}</div>}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>ID: {a.id}</div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Saved Lists Tab */}
      {tab === 'lists' && (
        <>
          {lists.length === 0 ? <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>No saved lists yet. Select accounts and save as a list.</div> : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {lists.map(l => (
                <div key={l.id} style={card}>
                  <div onClick={() => setExpandedList(expandedList === l.id ? null : l.id)}
                    style={{ padding: '14px 20px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>{l.name}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                        {l.account_count} accounts
                        {l.filter_pattern && <span> · filter: "{l.filter_pattern}"</span>}
                        <span> · {new Date(l.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <button onClick={e => { e.stopPropagation(); navigator.clipboard.writeText(`use preset '${l.name}'`) }}
                        style={{ fontSize: 11, padding: '4px 10px', borderRadius: 6, background: 'rgba(99,102,241,0.12)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.25)', cursor: 'pointer' }}>
                        Copy for MCP
                      </button>
                      <button onClick={e => { e.stopPropagation(); if (confirm(`Delete "${l.name}"?`)) deleteList(l.id) }}
                        style={{ fontSize: 11, padding: '4px 10px', borderRadius: 6, background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.25)', cursor: 'pointer' }}>
                        Delete
                      </button>
                      <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>{expandedList === l.id ? '\u25B2' : '\u25BC'}</span>
                    </div>
                  </div>
                  {expandedList === l.id && (
                    <div style={{ borderTop: '1px solid var(--border)', padding: '12px 20px', background: 'var(--bg)' }}>
                      {(l.account_ids || []).map((a: any, i: number) => (
                        <div key={i} style={{ padding: '6px 0', fontSize: 13, display: 'flex', gap: 8, alignItems: 'center' }}>
                          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e' }} />
                          <span>{a.email}</span>
                          {a.name && <span style={{ color: 'var(--text-muted)' }}>({a.name})</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
