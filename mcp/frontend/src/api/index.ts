import { api } from './client'
export { api }
export type { Contact, ContactListResponse, ContactStats, FilterOptions, Project, AISDRProject } from './contacts'

// Re-export types that main app expects
export type ImportResult = { success: boolean; imported: number; errors: string[] }
export type EnrichResult = { success: boolean; enriched: number }

// contactsApi — adapted for MCP backend
export const contactsApi = {
  async list(params: Record<string, any> = {}) {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') qs.set(k, String(v))
    }
    return api(`/pipeline/crm/contacts?${qs}`) as Promise<any>
  },

  async getStats(projectId?: number) {
    const qs = projectId ? `?project_id=${projectId}` : ''
    // Build stats from CRM endpoint
    const contacts = await api(`/pipeline/crm/contacts${qs}`)
    const total = contacts.total || (contacts.contacts || []).length
    return { total, by_status: {}, by_segment: {}, by_source: {}, by_project: {} }
  },

  async getFilterOptions() {
    return { statuses: ['new', 'pending'], sources: ['smartlead_import', 'pipeline'], segments: [], geos: [], projects: [] }
  },

  async listProjectNames() {
    const token = localStorage.getItem('mcp_token') || ''
    const res = await fetch('/api/pipeline/projects', { headers: { 'X-MCP-Token': token } })
    if (!res.ok) return []
    const projects = await res.json()
    return projects.map((p: any) => ({ id: p.id, name: p.name }))
  },

  async listProjects() { return this.listProjectNames() },

  async updateStatus(id: number, status: string) { return {} },
  async exportCsv(filters: any) { return new Blob() },
  async exportGoogleSheet(filters: any) { return {} },
  async deleteMany(ids: number[]) { return {} },
  async pushToSmartlead(ids: number[], name: string, opts: any) { return {} },
  async importCsv(file: File, projectId: number) { return { success: true, imported: 0, errors: [] } },
  async enrichCsv(file: File) { return { success: true, enriched: 0 } },
  async generateReply(id: number) { return { has_reply: false } },
  async crmSpotlightGTM(projectId: number, question: string, filters: any) { return {} },
  async getProject(id: number) { return {} },
  async listCampaigns() { return [] },
}
