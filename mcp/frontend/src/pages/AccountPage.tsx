import { useState, useEffect } from 'react'

const API = '/api'
function headers() { return { 'X-MCP-Token': localStorage.getItem('mcp_token') || '', 'Content-Type': 'application/json' } }

export default function AccountPage() {
  const [account, setAccount] = useState<any>(null)
  const [usage, setUsage] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      fetch(`${API}/account`, { headers: headers() }).then(r => r.json()),
      fetch(`${API}/account/usage`, { headers: headers() }).then(r => r.json()),
    ]).then(([acc, use]) => {
      setAccount(acc)
      setUsage(use)
    }).finally(() => setLoading(false))
  }, [])

  const logout = () => {
    localStorage.removeItem('mcp_token')
    window.location.href = '/setup'
  }

  if (loading) return <div className="max-w-3xl mx-auto p-8 text-sm text-gray-500">Loading...</div>
  if (!account?.authenticated) {
    window.location.href = '/setup'
    return null
  }

  const credits = account.credits || {}
  const stats = account.stats || {}
  const byTool = usage?.by_tool || {}
  const recent = usage?.recent || []

  return (
    <div className="max-w-3xl mx-auto p-8 space-y-8 overflow-y-auto" style={{ height: '100%' }}>
      {/* User card */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold">{account.user?.name}</div>
          <div className="text-sm text-gray-500">{account.user?.email}</div>
        </div>
        <button onClick={logout} className="text-sm text-red-400 hover:text-red-300 border border-red-400/30 hover:border-red-400/60 px-4 py-1.5 rounded">
          Logout
        </button>
      </div>

      {/* Credits Overview */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Credits Used</h2>
        <div className="grid grid-cols-3 gap-4">
          <CreditCard
            label="Apollo"
            value={credits.apollo?.total || 0}
            detail={`Gathering: ${credits.apollo?.gathering || 0} • Filter discovery: ${credits.apollo?.filter_discovery || 0}`}
            color="#6366f1"
          />
          <CreditCard
            label="OpenAI"
            value={credits.openai?.tool_calls || 0}
            detail={credits.openai?.note || 'GPT-4o-mini calls'}
            color="#10b981"
          />
          <CreditCard
            label="MCP Platform"
            value={credits.mcp?.tool_calls || 0}
            detail="Total MCP tool calls"
            color="#f59e0b"
          />
        </div>
      </div>

      {/* Platform Stats */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Platform Stats</h2>
        <div className="grid grid-cols-4 gap-4">
          <StatBox label="Contacts" value={stats.total_contacts} />
          <StatBox label="Companies" value={stats.total_companies} />
          <StatBox label="Campaigns" value={stats.total_campaigns} />
          <StatBox label="Tool Calls" value={stats.total_tool_calls} />
        </div>
      </div>

      {/* Integrations */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Connected Services</h2>
        <div className="border border-gray-700 rounded-lg divide-y divide-gray-700">
          {(account.integrations || []).length === 0 ? (
            <div className="px-4 py-3 text-sm text-gray-500">No integrations yet. <a href="/setup" className="text-blue-400 hover:underline">Set up API keys</a></div>
          ) : (
            (account.integrations || []).map((i: any) => (
              <div key={i.name} className="flex items-center justify-between px-4 py-3">
                <div className="flex items-center gap-3">
                  <span className={`w-2 h-2 rounded-full ${i.connected ? 'bg-green-400' : 'bg-gray-600'}`} />
                  <span className="text-sm font-medium capitalize">{i.name}</span>
                </div>
                <span className="text-xs text-gray-500">{i.info || (i.connected ? 'Connected' : 'Not connected')}</span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Usage by Tool */}
      {Object.keys(byTool).length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Usage by Tool</h2>
          <div className="border border-gray-700 rounded-lg divide-y divide-gray-700">
            {Object.entries(byTool).sort((a: any, b: any) => b[1] - a[1]).map(([tool, count]: any) => (
              <div key={tool} className="flex items-center justify-between px-4 py-2.5">
                <span className="text-sm font-mono">{tool}</span>
                <span className="text-sm font-medium tabular-nums">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Activity */}
      {recent.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Recent Activity</h2>
          <div className="border border-gray-700 rounded-lg divide-y divide-gray-700">
            {recent.map((r: any, i: number) => (
              <div key={i} className="flex items-center justify-between px-4 py-2">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-gray-400">{r.tool}</span>
                  <span className="text-xs text-gray-500">{r.action}</span>
                </div>
                <span className="text-xs text-gray-600">{r.at ? new Date(r.at).toLocaleString() : ''}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function CreditCard({ label, value, detail, color }: { label: string; value: number; detail: string; color: string }) {
  return (
    <div className="border border-gray-700 rounded-lg p-4 space-y-2">
      <div className="flex items-center gap-2">
        <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
        <span className="text-sm font-medium">{label}</span>
      </div>
      <div className="text-2xl font-bold tabular-nums">{value.toLocaleString()}</div>
      <div className="text-xs text-gray-500">{detail}</div>
    </div>
  )
}

function StatBox({ label, value }: { label: string; value: number }) {
  return (
    <div className="border border-gray-700 rounded-lg p-3 text-center">
      <div className="text-xl font-bold tabular-nums">{(value || 0).toLocaleString()}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  )
}
