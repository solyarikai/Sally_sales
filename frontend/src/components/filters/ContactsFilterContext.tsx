import { createContext, useContext } from 'react';
import type { ContactStats, FilterOptions } from '../../api/contacts';

export interface ContactsFilterState {
  campaignFilters: string[];
  setCampaignFilters: (names: string[]) => void;
  toggleCampaign: (name: string) => void;
  statusFilters: string[];
  setStatusFilters: (statuses: string[]) => void;
  toggleStatus: (status: string) => void;
  segmentFilter: string | null;
  setSegmentFilter: (s: string | null) => void;
  sourceFilter: string | null;
  setSourceFilter: (s: string | null) => void;
  geoFilter: string | null;
  setGeoFilter: (s: string | null) => void;
  repliedFilter: boolean | null;
  setRepliedFilter: (v: boolean | null) => void;
  followupFilter: boolean | null;
  setFollowupFilter: (v: boolean | null) => void;
  campaigns: Array<{ name: string; source: string }>;
  stats: ContactStats | null;
  filterOptions: FilterOptions | null;
  resetPage: () => void;
  createdAfter: string | null;
  createdBefore: string | null;
  setDateRange: (after: string | null, before: string | null) => void;
}

export const ContactsFilterContext = createContext<ContactsFilterState | null>(null);

export function useContactsFilter(): ContactsFilterState {
  const ctx = useContext(ContactsFilterContext);
  if (!ctx) throw new Error('useContactsFilter must be used within ContactsFilterContext.Provider');
  return ctx;
}
