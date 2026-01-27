export { api } from './client';
export * as environmentsApi from './environments';
export * as companiesApi from './companies';
export { datasetsApi, foldersApi } from './datasets';
export { enrichmentApi } from './enrichment';
export { templatesApi } from './templates';
export { settingsApi } from './settings';
export { exportApi } from './export';
export { integrationsApi } from './integrations';
export * as knowledgeBaseApi from './knowledgeBase';
export { prospectsApi } from './prospects';
export type { 
  Prospect, 
  ProspectsListResponse, 
  ProspectActivity,
  FieldMapping, 
  FieldMappingSuggestion,
  AddToProspectsRequest,
  AddToProspectsResponse,
  ProspectStats,
  ProspectFilters,
  CoreField,
  ColumnInfo
} from './prospects';
