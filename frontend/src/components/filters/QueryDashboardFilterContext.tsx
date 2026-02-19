import { createContext, useContext } from 'react';
import type { FilterOptionsResponse, GeoHierarchyResponse } from '../../api/queryDashboard';

export interface QueryDashboardFilterState {
  segmentFilters: string[];
  setSegmentFilters: (v: string[]) => void;
  toggleSegment: (v: string) => void;
  geoFilters: string[];
  setGeoFilters: (v: string[]) => void;
  toggleGeo: (v: string) => void;
  sourceFilters: string[];
  setSourceFilters: (v: string[]) => void;
  toggleSource: (v: string) => void;
  statusFilters: string[];
  setStatusFilters: (v: string[]) => void;
  toggleStatus: (v: string) => void;
  languageFilters: string[];
  setLanguageFilters: (v: string[]) => void;
  toggleLanguage: (v: string) => void;
  saturatedFilter: boolean | null; // null = all, true = saturated only, false = non-saturated only
  setSaturatedFilter: (v: boolean | null) => void;
  domainsMin: number | null;
  domainsMax: number | null;
  setDomainsRange: (min: number | null, max: number | null) => void;
  targetsMin: number | null;
  targetsMax: number | null;
  setTargetsRange: (min: number | null, max: number | null) => void;
  dateFrom: string | null;
  dateTo: string | null;
  setDateRange: (from: string | null, to: string | null) => void;
  filterOptions: FilterOptionsResponse | null;
  geoHierarchy: GeoHierarchyResponse | null;
  resetPage: () => void;
}

export const QueryDashboardFilterContext = createContext<QueryDashboardFilterState | null>(null);

export function useQueryDashboardFilter(): QueryDashboardFilterState {
  const ctx = useContext(QueryDashboardFilterContext);
  if (!ctx) throw new Error('useQueryDashboardFilter must be used within QueryDashboardFilterContext.Provider');
  return ctx;
}
