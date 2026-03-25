import { useState } from 'react'

const API = '/api'

export default function SetupPage() {
  const [token, setToken] = useState(localStorage.getItem('mcp_token') || '')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [message, setMessage] = useState('')
  const [integrations, setIntegrations] = useState<any[]>([])

  const [intName, setIntName] = useState('smartlead')
  const [intKey, setIntKey] = useState('')
  const [intResult, setIntResult] = useState('')

  const signup = async () => {
    const res = await fetch(`${API}/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, name }),
    })
    const data = await res.json()
    if (data.api_token) {
      setToken(data.api_token)
      localStorage.setItem('mcp_token', data.api_token)
      setMessage(`Account created! Token: ${data.api_token}`)
    } else {
      setMessage(data.detail || 'Error')
    }
  }

  const loadIntegrations = async () => {
    const res = await fetch(`${API}/setup/integrations`, {
      headers: { 'X-MCP-Token': token },
    })
    setIntegrations(await res.json())
  }

  const connectIntegration = async () => {
    setIntResult('Connecting...')
    const res = await fetch(`${API}/setup/integrations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-MCP-Token': token },
      body: JSON.stringify({ integration_name: intName, api_key: intKey }),
    })
    const data = await res.json()
    setIntResult(data.message || JSON.stringify(data))
    loadIntegrations()
  }

  return (
    <div className="max-w-2xl mx-auto p-8 space-y-8">
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">Account Setup</h2>
        {!token ? (
          <div className="space-y-2">
            <input className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} />
            <input className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2" placeholder="Name" value={name} onChange={e => setName(e.target.value)} />
            <button className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded" onClick={signup}>Sign Up</button>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="text-sm text-gray-400">Token: <code className="text-green-400">{token.slice(0, 20)}...</code></div>
            <button className="text-sm text-gray-500 hover:text-white" onClick={() => { setToken(''); localStorage.removeItem('mcp_token') }}>Reset</button>
          </div>
        )}
        {message && <div className="text-sm text-yellow-400">{message}</div>}
      </div>

      {token && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">Integrations</h2>
          <button className="text-sm text-blue-400 hover:text-blue-300" onClick={loadIntegrations}>Refresh</button>
          {integrations.map((i: any) => (
            <div key={i.name} className="flex items-center gap-2 text-sm">
              <span className={i.connected ? 'text-green-400' : 'text-red-400'}>{i.connected ? '●' : '○'}</span>
              <span>{i.name}</span>
              <span className="text-gray-500">{i.info}</span>
            </div>
          ))}

          <div className="border border-gray-800 rounded p-4 space-y-2">
            <select className="bg-gray-900 border border-gray-700 rounded px-2 py-1" value={intName} onChange={e => setIntName(e.target.value)}>
              <option value="smartlead">SmartLead</option>
              <option value="apollo">Apollo</option>
              <option value="findymail">FindyMail</option>
              <option value="openai">OpenAI</option>
              <option value="gemini">Gemini</option>
            </select>
            <input className="w-full bg-gray-900 border border-gray-700 rounded px-3 py-2 text-sm" placeholder="API Key" type="password" value={intKey} onChange={e => setIntKey(e.target.value)} />
            <button className="bg-green-700 hover:bg-green-600 px-4 py-2 rounded text-sm" onClick={connectIntegration}>Connect</button>
            {intResult && <div className="text-sm text-gray-400">{intResult}</div>}
          </div>
        </div>
      )}
    </div>
  )
}
