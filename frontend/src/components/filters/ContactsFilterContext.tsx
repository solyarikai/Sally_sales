import { createContext, useContext } from 'react';
import type { ContactStats } from '../../api/contacts';

export interface ContactsFilterState {
  campaignFilters: string[];
  setCampaignFilters: (names: string[]) => void;
  toggleCampaign: (name: string) => void;
  statusFilters: string[];
  setStatusFilters: (statuses: string[]) => void;
  toggleStatus: (status: string) => void;
  campaigns: Array<{ name: string; source: string }>;
  stats: ContactStats | null;
  resetPage: () => void;
}

export const ContactsFilterContext = createContext<ContactsFilterState | null>(null);

export function useContactsFilter(): ContactsFilterState {
  const ctx = useContext(ContactsFilterContext);
  if (!ctx) throw new Error('useContactsFilter must be used within ContactsFilterContext.Provider');
  return ctx;
}
