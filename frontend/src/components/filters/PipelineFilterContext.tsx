import { createContext, useContext } from 'react';
import type { PipelineStats } from '../../api/pipeline';

export interface PipelineFilterState {
  statusFilters: string[];
  setStatusFilters: (statuses: string[]) => void;
  toggleStatus: (status: string) => void;
  targetFilter: 'all' | 'targets' | 'non-targets';
  setTargetFilter: (filter: 'all' | 'targets' | 'non-targets') => void;
  stats: PipelineStats | null;
  resetPage: () => void;
}

export const PipelineFilterContext = createContext<PipelineFilterState | null>(null);

export function usePipelineFilter(): PipelineFilterState {
  const ctx = useContext(PipelineFilterContext);
  if (!ctx) throw new Error('usePipelineFilter must be used within PipelineFilterContext.Provider');
  return ctx;
}
