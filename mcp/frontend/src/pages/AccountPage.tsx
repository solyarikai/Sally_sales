import { useState, useEffect } from 'react'

const API = '/api'
function headers() { return { 'X-MCP-Token': localStorage.getItem('mcp_token') || '', 'Content-Type': 'application/json' } }

export default function AccountPage() {
  const [account, setAccount] = useState<any>(null)
  const [usage, setUsage] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')

  const loadData = () => {
    setLoading(true)
    const params = new URLSearchParams()
    if (dateFrom) params.set('from', dateFrom)
    if (dateTo) params.set('to', dateTo)
    const qs = params.toString() ? `?${params}` : ''
    Promise.all([
      fetch(`${API}/account${qs}`, { headers: headers() }).then(r => r.json()),
      fetch(`${API}/account/usage${qs}`, { headers: headers() }).then(r => r.json()),
    ]).then(([acc, use]) => {
      setAccount(acc)
      setUsage(use)
    }).finally(() => setLoading(false))
  }

  useEffect(() => { loadData() }, [dateFrom, dateTo])

  const logout = () => {
    localStorage.removeItem('mcp_token')
    window.location.href = '/setup'
  }

  if (loading) return <div className="max-w-3xl mx-auto p-8 text-sm text-gray-500">Loading...</div>
  if (!account?.authenticated) {
    window.location.href = '/setup'
    return null
  }

  const costs = account.costs || {}
  const stats = account.stats || {}
  const byTool = usage?.by_tool || {}
  const recent = usage?.recent || []
  const runs = account.pipeline_runs || []

  const apollo = costs.apollo || {}
  const openai = costs.openai || {}
  const apify = costs.apify || {}
  const mcp = costs.mcp || {}
  const openaiModels = openai.by_model || {}

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

      {/* Date Range Filter */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500">From</label>
          <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            className="border rounded px-2 py-1 text-sm" />
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-500">To</label>
          <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)}
            className="border rounded px-2 py-1 text-sm" />
        </div>
        {(dateFrom || dateTo) && (
          <button onClick={() => { setDateFrom(''); setDateTo('') }}
            className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">Clear</button>
        )}
        <span className="text-xs text-gray-600">{dateFrom || dateTo ? `Showing: ${dateFrom || 'start'} → ${dateTo || 'now'}` : 'All time'}</span>
      </div>

      {/* Total Cost */}
      <div className="border rounded-lg p-5 bg-gray-50 dark:bg-gray-800/30">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-400">Total Spend</span>
          <span className="text-2xl font-bold text-white">${(costs.total_usd || 0).toFixed(2)}</span>
        </div>
      </div>

      {/* Cost Breakdown by Service */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">
          Costs {dateFrom || dateTo ? `(${dateFrom || 'start'} → ${dateTo || 'now'})` : '(All Time)'}
        </h2>
        <div className="grid grid-cols-4 gap-4">
          {/* Apollo */}
          <div className="border rounded-lg p-4 space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-indigo-500" />
              <span className="text-sm font-medium">Apollo</span>
            </div>
            <div className="text-2xl font-bold tabular-nums">${(apollo.cost_usd || 0).toFixed(2)}</div>
            <div className="text-xs text-gray-500 space-y-0.5">
              <div>{apollo.credits || 0} credits total</div>
              <div>Gathering: {apollo.gathering_credits || 0}</div>
              <div>Enrichment: {apollo.enrichment_credits || 0}</div>
            </div>
          </div>

          {/* OpenAI */}
          <div className="border rounded-lg p-4 space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
              <span className="text-sm font-medium">OpenAI</span>
            </div>
            <div className="text-2xl font-bold tabular-nums">${(openai.total_cost_usd || 0).toFixed(4)}</div>
            <div className="text-xs text-gray-500 space-y-0.5">
              <div>{(openai.total_tokens || 0).toLocaleString()} tokens</div>
              {Object.entries(openaiModels).map(([model, d]: any) => (
                <div key={model} className="flex justify-between">
                  <span className="text-gray-400">{model}</span>
                  <span>{d.input_tokens?.toLocaleString()}+{d.output_tokens?.toLocaleString()} · ${d.cost_usd?.toFixed(4)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Apify */}
          <div className="border rounded-lg p-4 space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-amber-500" />
              <span className="text-sm font-medium">Apify</span>
            </div>
            <div className="text-2xl font-bold tabular-nums">${(apify.cost_usd || 0).toFixed(2)}</div>
            <div className="text-xs text-gray-500 space-y-0.5">
              <div>{apify.websites_scraped || 0} websites scraped</div>
              <div>{apify.gb_used || 0} GB proxy used</div>
            </div>
          </div>

          {/* MCP */}
          <div className="border rounded-lg p-4 space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-2.5 h-2.5 rounded-full bg-rose-500" />
              <span className="text-sm font-medium">MCP</span>
            </div>
            <div className="text-2xl font-bold tabular-nums">{((mcp.total_tokens || 0) / 1000).toFixed(1)}K</div>
            <div className="text-xs text-gray-500 space-y-0.5">
              <div>{(mcp.input_tokens || 0).toLocaleString()} input tokens</div>
              <div>{(mcp.output_tokens || 0).toLocaleString()} output tokens</div>
              <div>{mcp.tool_calls || 0} tool calls</div>
            </div>
          </div>
        </div>
      </div>

      {/* Platform Stats */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Your Stats</h2>
        <div className="grid grid-cols-4 gap-4">
          <StatBox label="Contacts" value={stats.total_contacts} />
          <StatBox label="Companies" value={stats.total_companies} />
          <StatBox label="Campaigns" value={stats.total_campaigns} />
          <StatBox label="Tool Calls" value={stats.total_tool_calls} />
        </div>
      </div>

      {/* Pipeline Runs with Credits */}
      {runs.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Pipeline Runs</h2>
          <div className="border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs uppercase text-gray-500 border-b">
                  <th className="px-4 py-2 text-left">Run</th>
                  <th className="px-4 py-2 text-left">Source</th>
                  <th className="px-4 py-2 text-right">Companies</th>
                  <th className="px-4 py-2 text-right">Targets</th>
                  <th className="px-4 py-2 text-right">Credits</th>
                  <th className="px-4 py-2 text-left">Phase</th>
                  <th className="px-4 py-2 text-left">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {runs.map((r: any) => (
                  <tr key={r.id}>
                    <td className="px-4 py-2">
                      <a href={`/pipeline/${r.id}`} className="text-blue-400 hover:underline">#{r.id}</a>
                    </td>
                    <td className="px-4 py-2 text-gray-400">{r.source_type?.replace('companies.', '').replace('.manual', '')}</td>
                    <td className="px-4 py-2 text-right">{r.companies}</td>
                    <td className="px-4 py-2 text-right">
                      {r.targets > 0 && <span className="text-green-400">{r.targets}</span>}
                      {r.targets > 0 && <span className="text-gray-500 ml-1">({r.target_rate})</span>}
                    </td>
                    <td className="px-4 py-2 text-right font-mono">
                      {r.credits_used > 0 ? (
                        <span className="text-yellow-400">{r.credits_used}</span>
                      ) : (
                        <span className="text-gray-600">0</span>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <span className="px-2 py-0.5 rounded text-xs bg-gray-100 dark:bg-gray-700">{r.phase}</span>
                    </td>
                    <td className="px-4 py-2 text-gray-500 text-xs">
                      {r.created_at ? new Date(r.created_at).toLocaleDateString() : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Integrations */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Connected Services</h2>
        <div className="border rounded-lg divide-y divide-gray-200 dark:divide-gray-700">
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
          <div className="border rounded-lg divide-y divide-gray-200 dark:divide-gray-700">
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
          <div className="border rounded-lg divide-y divide-gray-200 dark:divide-gray-700">
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
    <div className="border rounded-lg p-4 space-y-2">
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
    <div className="border rounded-lg p-3 text-center">
      <div className="text-xl font-bold tabular-nums">{(value || 0).toLocaleString()}</div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  )
}
