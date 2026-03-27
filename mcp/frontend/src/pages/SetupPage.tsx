import { useState, useEffect } from 'react'

const API = '/api'

const inputStyle: React.CSSProperties = {
  width: '100%', background: 'var(--bg-card)', border: '1px solid var(--border)',
  borderRadius: 6, padding: '8px 12px', color: 'var(--text)', outline: 'none', fontSize: 14,
}

export default function SetupPage() {
  const [token, setToken] = useState(localStorage.getItem('mcp_token') || '')
  const [mode, setMode] = useState<'choose' | 'signup' | 'login'>('choose')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [existingToken, setExistingToken] = useState('')
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState<'info' | 'error' | 'success'>('info')
  const [integrations, setIntegrations] = useState<any[]>([])

  const [intName, setIntName] = useState('smartlead')
  const [intKey, setIntKey] = useState('')
  const [intResult, setIntResult] = useState('')

  const [userName, setUserName] = useState('')

  useEffect(() => {
    if (token) {
      fetch(`${API}/auth/me`, { headers: { 'X-MCP-Token': token } })
        .then(r => { if (!r.ok) throw new Error('Invalid token'); return r.json() })
        .then(d => { setUserName(d.name); loadIntegrations() })
        .catch(() => { setToken(''); localStorage.removeItem('mcp_token'); setMsg('Token expired or invalid', 'error') })
    }
  }, [token])

  const setMsg = (text: string, type: 'info' | 'error' | 'success' = 'info') => {
    setMessage(text); setMessageType(type)
  }

  const signup = async () => {
    if (!email || !name) { setMsg('Email and name required', 'error'); return }
    const res = await fetch(`${API}/auth/signup`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, name }),
    })
    const data = await res.json()
    if (data.api_token) {
      setToken(data.api_token); localStorage.setItem('mcp_token', data.api_token)
      setMsg(`Account created! Save your token: ${data.api_token}`, 'success')
    } else { setMsg(data.detail || 'Signup failed', 'error') }
  }

  const loginWithToken = async () => {
    if (!existingToken.startsWith('mcp_')) { setMsg('Token must start with mcp_', 'error'); return }
    const res = await fetch(`${API}/auth/me`, { headers: { 'X-MCP-Token': existingToken } })
    if (res.ok) {
      const data = await res.json()
      setToken(existingToken); localStorage.setItem('mcp_token', existingToken)
      setUserName(data.name); setMsg(`Welcome back, ${data.name}!`, 'success')
    } else { setMsg('Invalid token', 'error') }
  }

  const loadIntegrations = async () => {
    const t = token || existingToken; if (!t) return
    const res = await fetch(`${API}/setup/integrations`, { headers: { 'X-MCP-Token': t } })
    if (res.ok) setIntegrations(await res.json())
  }

  const connectIntegration = async () => {
    if (!intKey) { setIntResult('Enter an API key'); return }
    setIntResult('Connecting...')
    const res = await fetch(`${API}/setup/integrations`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', 'X-MCP-Token': token },
      body: JSON.stringify({ integration_name: intName, api_key: intKey }),
    })
    const data = await res.json()
    setIntResult(data.message || JSON.stringify(data)); setIntKey(''); loadIntegrations()
  }

  const logout = () => {
    setToken(''); setUserName(''); setIntegrations([]); setMode('choose'); setMessage('')
    localStorage.removeItem('mcp_token')
  }

  const msgColor = messageType === 'error' ? '#ef4444' : messageType === 'success' ? '#22c55e' : '#eab308'

  return (
    <div style={{ maxWidth: 640, margin: '0 auto', padding: 32, display: 'flex', flexDirection: 'column', gap: 32 }}>

      {/* Account Section */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        <h2 style={{ fontSize: 18, fontWeight: 600 }}>Account</h2>

        {!token ? (
          <>
            {mode === 'choose' && (
              <div style={{ display: 'flex', gap: 12 }}>
                <button onClick={() => setMode('signup')} style={{ padding: '10px 20px', borderRadius: 6, fontWeight: 500, background: '#3b82f6', color: 'white', border: 'none', cursor: 'pointer' }}>New Account</button>
                <button onClick={() => setMode('login')} style={{ padding: '10px 20px', borderRadius: 6, fontWeight: 500, background: 'var(--bg-card)', color: 'var(--text-secondary)', border: '1px solid var(--border)', cursor: 'pointer' }}>I Have a Token</button>
              </div>
            )}

            {mode === 'signup' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <input style={inputStyle} placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} />
                <input style={inputStyle} placeholder="Name" value={name} onChange={e => setName(e.target.value)} />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={signup} style={{ padding: '8px 16px', borderRadius: 6, background: '#3b82f6', color: 'white', border: 'none', cursor: 'pointer' }}>Sign Up</button>
                  <button onClick={() => setMode('choose')} style={{ padding: '8px 12px', fontSize: 13, background: 'transparent', color: 'var(--text-muted)', border: 'none', cursor: 'pointer' }}>Back</button>
                </div>
              </div>
            )}

            {mode === 'login' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <input style={{ ...inputStyle, fontFamily: 'monospace', fontSize: 13 }} placeholder="mcp_a1b2c3d4..." value={existingToken} onChange={e => setExistingToken(e.target.value)} />
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={loginWithToken} style={{ padding: '8px 16px', borderRadius: 6, background: '#16a34a', color: 'white', border: 'none', cursor: 'pointer' }}>Connect</button>
                  <button onClick={() => setMode('choose')} style={{ padding: '8px 12px', fontSize: 13, background: 'transparent', color: 'var(--text-muted)', border: 'none', cursor: 'pointer' }}>Back</button>
                </div>
              </div>
            )}
          </>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: 16 }}>
            <div>
              <div style={{ fontWeight: 500 }}>{userName || 'Loading...'}</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'monospace', marginTop: 4 }}>{token.slice(0, 20)}...</div>
            </div>
            <button onClick={logout} style={{ fontSize: 13, color: 'var(--text-muted)', background: 'transparent', border: 'none', cursor: 'pointer' }}>Logout</button>
          </div>
        )}

        {message && <div style={{ fontSize: 13, color: msgColor }}>{message}</div>}
      </div>

      {/* Integrations Section */}
      {token && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ fontSize: 18, fontWeight: 600 }}>Integrations</h2>
            <button onClick={loadIntegrations} style={{ fontSize: 13, color: '#3b82f6', background: 'transparent', border: 'none', cursor: 'pointer' }}>Refresh</button>
          </div>

          {integrations.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {integrations.map((i: any) => (
                <div key={i.name} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '6px 0', fontSize: 14 }}>
                  <span style={{ fontSize: 16, color: i.connected ? '#22c55e' : 'var(--text-muted)' }}>{i.connected ? '●' : '○'}</span>
                  <span style={{ fontWeight: 500, width: 96 }}>{i.name}</span>
                  <span style={{ color: 'var(--text-muted)' }}>{i.info}</span>
                </div>
              ))}
            </div>
          )}

          <div style={{ border: '1px solid var(--border)', borderRadius: 8, padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 500 }}>Connect a service</div>
            <select style={inputStyle} value={intName} onChange={e => setIntName(e.target.value)}>
              <option value="smartlead">SmartLead</option>
              <option value="apollo">Apollo</option>
              <option value="findymail">FindyMail</option>
              <option value="openai">OpenAI</option>
              <option value="gemini">Gemini</option>
            </select>
            <input style={{ ...inputStyle, fontFamily: 'monospace', fontSize: 13 }} placeholder="API Key" type="password" value={intKey} onChange={e => setIntKey(e.target.value)} />
            <button onClick={connectIntegration} style={{ width: '100%', padding: '10px', borderRadius: 6, fontSize: 13, background: '#16a34a', color: 'white', border: 'none', cursor: 'pointer', fontWeight: 500 }}>Test & Connect</button>
            {intResult && <div style={{ fontSize: 13, color: 'var(--text-muted)', textAlign: 'center' }}>{intResult}</div>}
          </div>
        </div>
      )}
    </div>
  )
}
