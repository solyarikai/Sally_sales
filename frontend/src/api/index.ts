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
export { repliesApi } from './replies';
export { contactsApi } from './contacts';
export { dashboardApi } from './dashboard';
export type { DashboardResponse, DashboardStats, ActivityItem, QuickStats } from './dashboard';
// Old tasksApi removed — task functionality now uses contactsApi.listTasks/updateTask
export { dataSearchApi } from './dataSearch';
export type { SearchFilter, CompanyResult, SearchResponse, ParsedQuery, ChatMessage } from './dataSearch';
export type { Contact, ContactListResponse, ContactStats, Project, FilterOptions, AISDRProject, AISDRGenerationResult, ImportResult, EnrichResult, ContactActivity, ContactWithActivities, SyncStatus, OperatorTask, TasksListResponse, KanbanContact, KanbanColumn, KanbanResponse } from './contacts';
export { queryDashboardApi } from './queryDashboard';
export type { QueryRecord, QueryListResponse, QuerySummaryResponse, FilterOptionsResponse as QueryFilterOptions, GeoHierarchyResponse, QueryDashboardFilters, SegmentSaturation } from './queryDashboard';
export { igamingApi } from './igaming';
export type { IGamingContact, IGamingCompany, IGamingEmployee, IGamingImport, IGamingStats } from './igaming';
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
