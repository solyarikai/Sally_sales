import { useState, useEffect } from 'react'
import { useProject } from '../App'

const API = '/api'
function headers() {
  return {
    'X-MCP-Token': localStorage.getItem('mcp_token') || '',
    'Content-Type': 'application/json',
  }
}

interface UsageEntry {
  tool: string
  action: string
  at: string
  extra?: Record<string, any>
}

interface RunEntry {
  id: number
  source_type: string
  phase: string
  companies: number
  targets: number
  target_rate: string
  credits_used: number
  created_at: string
}

export default function LearningPage() {
  const { project } = useProject()
  const [usage, setUsage] = useState<{ by_tool: Record<string, number>; recent: UsageEntry[] } | null>(null)
  const [runs, setRuns] = useState<RunEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      fetch(`${API}/account/usage`, { headers: headers() }).then(r => r.ok ? r.json() : null),
      fetch(`${API}/pipeline/runs`, { headers: headers() }).then(r => r.ok ? r.json() : []),
    ]).then(([usageData, runsData]) => {
      setUsage(usageData)
      setRuns(runsData || [])
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="max-w-4xl mx-auto p-8 text-sm text-gray-500">Loading...</div>

  const byTool = usage?.by_tool || {}
  const recent = usage?.recent || []
  const sortedTools = Object.entries(byTool).sort((a, b) => b[1] - a[1])
  const totalCalls = sortedTools.reduce((sum, [, count]) => sum + count, 0)

  // Filter runs for current project if one is selected
  const filteredRuns = project ? runs.filter((r: any) => r.project_id === project.id) : runs
  const runsWithTargets = filteredRuns.filter((r: any) => r.targets > 0)
  const avgTargetRate = runsWithTargets.length > 0
    ? (runsWithTargets.reduce((sum: number, r: any) => {
        const rate = parseFloat(String(r.target_rate).replace('%', '')) || 0
        return sum + rate
      }, 0) / runsWithTargets.length).toFixed(1) + '%'
    : 'N/A'

  return (
    <div className="max-w-4xl mx-auto p-8 space-y-8 overflow-y-auto" style={{ height: '100%' }}>
      <div>
        <h1 className="text-lg font-semibold">Learning</h1>
        <p className="text-sm text-gray-500 mt-1">
          Usage analytics and pipeline accuracy history
          {project ? ` for ${project.name}` : ''}
        </p>
      </div>

      {/* Usage overview */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Usage Overview</h2>
        <div className="grid grid-cols-3 gap-4">
          <StatCard label="Total Tool Calls" value={totalCalls} />
          <StatCard label="Unique Tools Used" value={sortedTools.length} />
          <StatCard label="Pipeline Runs" value={filteredRuns.length} />
        </div>
      </div>

      {/* Tool usage breakdown */}
      {sortedTools.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Tool Usage</h2>
          <div className="border border-gray-700 rounded-lg divide-y divide-gray-700">
            {sortedTools.map(([tool, count]) => {
              const pct = totalCalls > 0 ? (count / totalCalls * 100) : 0
              return (
                <div key={tool} className="flex items-center gap-3 px-4 py-2.5">
                  <span className="text-sm font-mono flex-1">{tool}</span>
                  <div className="w-32 h-1.5 rounded bg-gray-800 overflow-hidden">
                    <div
                      className="h-full rounded bg-blue-500"
                      style={{ width: `${Math.max(pct, 2)}%` }}
                    />
                  </div>
                  <span className="text-sm font-medium tabular-nums w-12 text-right">{count}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Pipeline accuracy history */}
      {filteredRuns.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">
            Pipeline Accuracy History
          </h2>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <StatCard label="Total Runs" value={filteredRuns.length} />
            <StatCard label="Runs with Targets" value={runsWithTargets.length} />
            <StatCard label="Avg Target Rate" value={avgTargetRate} isText />
          </div>
          <div className="border border-gray-700 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs uppercase text-gray-500 border-b border-gray-700">
                  <th className="px-4 py-2 text-left">Run</th>
                  <th className="px-4 py-2 text-left">Source</th>
                  <th className="px-4 py-2 text-right">Companies</th>
                  <th className="px-4 py-2 text-right">Targets</th>
                  <th className="px-4 py-2 text-right">Target Rate</th>
                  <th className="px-4 py-2 text-right">Credits</th>
                  <th className="px-4 py-2 text-left">Phase</th>
                  <th className="px-4 py-2 text-left">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                {filteredRuns.map((r: any) => (
                  <tr key={r.id}>
                    <td className="px-4 py-2">
                      <a href={`/pipeline/${r.id}`} className="text-blue-400 hover:underline">#{r.id}</a>
                    </td>
                    <td className="px-4 py-2 text-gray-400">
                      {(r.source_type || '').replace('companies.', '').replace('.manual', '')}
                    </td>
                    <td className="px-4 py-2 text-right">{r.companies || r.new_companies || 0}</td>
                    <td className="px-4 py-2 text-right">
                      {r.targets > 0 ? (
                        <span className="text-green-400">{r.targets}</span>
                      ) : (
                        <span className="text-gray-600">0</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-right">
                      {r.target_rate ? (
                        <span className="text-green-400">{r.target_rate}</span>
                      ) : (
                        <span className="text-gray-600">--</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-right font-mono">
                      {r.credits_used > 0 ? (
                        <span className="text-yellow-400">{r.credits_used}</span>
                      ) : (
                        <span className="text-gray-600">0</span>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <span className="px-2 py-0.5 rounded text-xs bg-gray-700">{r.phase}</span>
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

      {/* Recent activity */}
      {recent.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400">Recent Activity</h2>
          <div className="border border-gray-700 rounded-lg divide-y divide-gray-700">
            {recent.slice(0, 20).map((r, i) => (
              <div key={i} className="flex items-center justify-between px-4 py-2">
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-gray-400">{r.tool}</span>
                  <span className="text-xs text-gray-500">{r.action}</span>
                </div>
                <span className="text-xs text-gray-600">
                  {r.at ? new Date(r.at).toLocaleString() : ''}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {sortedTools.length === 0 && filteredRuns.length === 0 && (
        <div className="text-center text-gray-500 py-16">
          No usage data yet. Start using MCP tools to see analytics here.
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, isText }: { label: string; value: number | string; isText?: boolean }) {
  return (
    <div className="border border-gray-700 rounded-lg p-3 text-center">
      <div className={`text-xl font-bold ${isText ? '' : 'tabular-nums'}`}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  )
}
