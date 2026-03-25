import { useState, useEffect } from 'react'

const API = '/api'

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

  // Load user info if token exists
  useEffect(() => {
    if (token) {
      fetch(`${API}/auth/me`, { headers: { 'X-MCP-Token': token } })
        .then(r => { if (!r.ok) throw new Error('Invalid token'); return r.json() })
        .then(d => { setUserName(d.name); loadIntegrations() })
        .catch(() => { setToken(''); localStorage.removeItem('mcp_token'); setMsg('Token expired or invalid', 'error') })
    }
  }, [token])

  const setMsg = (text: string, type: 'info' | 'error' | 'success' = 'info') => {
    setMessage(text)
    setMessageType(type)
  }

  const signup = async () => {
    if (!email || !name) { setMsg('Email and name required', 'error'); return }
    const res = await fetch(`${API}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, name }),
    })
    const data = await res.json()
    if (data.api_token) {
      setToken(data.api_token)
      localStorage.setItem('mcp_token', data.api_token)
      setMsg(`Account created! Save your token: ${data.api_token}`, 'success')
    } else {
      setMsg(data.detail || 'Signup failed', 'error')
    }
  }

  const loginWithToken = async () => {
    if (!existingToken.startsWith('mcp_')) { setMsg('Token must start with mcp_', 'error'); return }
    const res = await fetch(`${API}/auth/me`, { headers: { 'X-MCP-Token': existingToken } })
    if (res.ok) {
      const data = await res.json()
      setToken(existingToken)
      localStorage.setItem('mcp_token', existingToken)
      setUserName(data.name)
      setMsg(`Welcome back, ${data.name}!`, 'success')
    } else {
      setMsg('Invalid token', 'error')
    }
  }

  const loadIntegrations = async () => {
    const t = token || existingToken
    if (!t) return
    const res = await fetch(`${API}/setup/integrations`, { headers: { 'X-MCP-Token': t } })
    if (res.ok) setIntegrations(await res.json())
  }

  const connectIntegration = async () => {
    if (!intKey) { setIntResult('Enter an API key'); return }
    setIntResult('Connecting...')
    const res = await fetch(`${API}/setup/integrations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-MCP-Token': token },
      body: JSON.stringify({ integration_name: intName, api_key: intKey }),
    })
    const data = await res.json()
    setIntResult(data.message || JSON.stringify(data))
    setIntKey('')
    loadIntegrations()
  }

  const logout = () => {
    setToken('')
    setUserName('')
    setIntegrations([])
    setMode('choose')
    setMessage('')
    localStorage.removeItem('mcp_token')
  }

  const msgColor = messageType === 'error' ? 'text-red-400' : messageType === 'success' ? 'text-green-400' : 'text-yellow-400'

  return (
    <div className="max-w-2xl mx-auto p-8 space-y-8">

      {/* Account Section */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Account</h2>

        {!token ? (
          <>
            {mode === 'choose' && (
              <div className="flex gap-3">
                <button className="bg-blue-600 hover:bg-blue-700 px-5 py-2.5 rounded font-medium" onClick={() => setMode('signup')}>
                  New Account
                </button>
                <button className="bg-gray-700 hover:bg-gray-600 px-5 py-2.5 rounded font-medium" onClick={() => setMode('login')}>
                  I Have a Token
                </button>
              </div>
            )}

            {mode === 'signup' && (
              <div className="space-y-2">
                <input className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} />
                <input className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2" placeholder="Name" value={name} onChange={e => setName(e.target.value)} />
                <div className="flex gap-2">
                  <button className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded" onClick={signup}>Sign Up</button>
                  <button className="text-sm text-gray-500 hover:text-white px-3" onClick={() => setMode('choose')}>Back</button>
                </div>
              </div>
            )}

            {mode === 'login' && (
              <div className="space-y-2">
                <input className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 font-mono text-sm" placeholder="mcp_a1b2c3d4..." value={existingToken} onChange={e => setExistingToken(e.target.value)} />
                <div className="flex gap-2">
                  <button className="bg-green-700 hover:bg-green-600 px-4 py-2 rounded" onClick={loginWithToken}>Connect</button>
                  <button className="text-sm text-gray-500 hover:text-white px-3" onClick={() => setMode('choose')}>Back</button>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="flex items-center justify-between bg-gray-900 border border-gray-800 rounded p-4">
            <div>
              <div className="font-medium">{userName || 'Loading...'}</div>
              <div className="text-xs text-gray-500 font-mono mt-1">{token.slice(0, 20)}...</div>
            </div>
            <button className="text-sm text-gray-500 hover:text-red-400 px-3 py-1" onClick={logout}>Logout</button>
          </div>
        )}

        {message && <div className={`text-sm ${msgColor}`}>{message}</div>}
      </div>

      {/* Integrations Section */}
      {token && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Integrations</h2>
            <button className="text-sm text-blue-400 hover:text-blue-300" onClick={loadIntegrations}>Refresh</button>
          </div>

          {integrations.length > 0 && (
            <div className="space-y-1">
              {integrations.map((i: any) => (
                <div key={i.name} className="flex items-center gap-3 py-1.5 text-sm">
                  <span className={`text-lg ${i.connected ? 'text-green-400' : 'text-gray-600'}`}>{i.connected ? '●' : '○'}</span>
                  <span className="font-medium w-24">{i.name}</span>
                  <span className="text-gray-500">{i.info}</span>
                </div>
              ))}
            </div>
          )}

          <div className="border border-gray-800 rounded p-4 space-y-3">
            <div className="text-sm text-gray-400 font-medium">Connect a service</div>
            <select className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2" value={intName} onChange={e => setIntName(e.target.value)}>
              <option value="smartlead">SmartLead</option>
              <option value="apollo">Apollo</option>
              <option value="findymail">FindyMail</option>
              <option value="openai">OpenAI</option>
              <option value="gemini">Gemini</option>
            </select>
            <input className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm font-mono" placeholder="API Key" type="password" value={intKey} onChange={e => setIntKey(e.target.value)} />
            <button className="bg-green-700 hover:bg-green-600 px-4 py-2 rounded text-sm w-full" onClick={connectIntegration}>Test & Connect</button>
            {intResult && <div className="text-sm text-gray-400 text-center">{intResult}</div>}
          </div>
        </div>
      )}
    </div>
  )
}
