const BASE = '/api'

export async function api(path: string, options: RequestInit = {}) {
  const token = localStorage.getItem('mcp_token') || ''
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  }
  if (token) headers['X-MCP-Token'] = token
  headers['X-Company-ID'] = '1'

  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}
