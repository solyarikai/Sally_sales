import { api } from './client'
export { api }
export type { Contact, ContactListResponse, ContactStats, FilterOptions, Project, AISDRProject } from './contacts'

export type ImportResult = { success: boolean; imported: number; errors: string[]; skipped?: number; not_found?: number; created?: number; sample_created?: any[]; [key: string]: any }
export type EnrichResult = { success: boolean; enriched: number; skipped?: number; not_found?: number; errors?: string[]; [key: string]: any }

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
    try {
      const contacts = await api(`/pipeline/crm/contacts${qs}`)
      const total = contacts.total || (contacts.contacts || []).length
      return { total, by_status: {} as any, by_segment: {} as any, by_source: {} as any, by_project: {} as any }
    } catch { return { total: 0, by_status: {}, by_segment: {}, by_source: {}, by_project: {} } }
  },

  async getFilterOptions() {
    return { statuses: ['new', 'pending'] as string[], sources: ['smartlead_import', 'pipeline'] as string[], segments: [] as string[], geos: [] as string[], projects: [] as Array<{id: number, name: string}> }
  },

  async listProjectNames() {
    const token = localStorage.getItem('mcp_token') || ''
    const res = await fetch('/api/pipeline/projects', { headers: { 'X-MCP-Token': token } })
    if (!res.ok) return []
    return (await res.json()).map((p: any) => ({ id: p.id, name: p.name }))
  },

  async listProjects() { return this.listProjectNames() },
  async updateStatus(_id: number, _status: string) { return {} },
  async exportCsv(_filters: any) { return new Blob() },
  async exportGoogleSheet(_filters: any) { return {} },
  async deleteMany(_ids: number[]) { return {} },
  async pushToSmartlead(_ids: number[], _name: string, _opts: any) { return {} },
  async importCsv(_file: File, _opts?: any): Promise<ImportResult> { return { success: true, imported: 0, errors: [] } },
  async enrichCsv(_file: File, _opts?: any): Promise<EnrichResult> { return { success: true, enriched: 0 } },
  async generateReply(_id: number) { return { has_reply: false } },
  async crmSpotlightGTM(_projectId: number, _question: string, _filters: any) { return {} },
  async getProject(_id: number): Promise<any> { return {} },
  async listCampaigns(): Promise<any> { return [] },
  async deleteProject(_id: number): Promise<any> { return {} },
  async getProjectAISDR(_id: number): Promise<any> { return { tam_analysis: null, gtm_plan: null, pitch_templates: null } },
  async generateTAM(_id: number): Promise<any> { return { tam_analysis: '' } },
  async generateGTM(_id: number): Promise<any> { return { gtm_plan: '' } },
  async generatePitches(_id: number): Promise<any> { return { pitch_templates: '' } },
  async generateAllAISDR(_id: number): Promise<any> { return { tam_analysis: '', gtm_plan: '', pitch_templates: '' } },
  async getImportTemplate(): Promise<any> { return new Blob() },
  async importCsvBulk(_file: File, _opts: any): Promise<ImportResult> { return { success: true, imported: 0, errors: [] } },
  async create(_data: any): Promise<any> { return {} },
  async update(_id: number, _data: any): Promise<any> { return {} },
  async delete(_id: number): Promise<any> { return {} },
  async bulkCreate(_data: any): Promise<any> { return {} },
  async createProject(_data: any): Promise<any> { return {} },
  async updateProject(_id: number, _data: any): Promise<any> { return {} },
  async verifyCampaigns(_names: string[]): Promise<any> { return {} },
  async pushToSmartlead(_ids: number[], _name: string, _opts?: any): Promise<any> { return { leads_added: 0 } },
}
