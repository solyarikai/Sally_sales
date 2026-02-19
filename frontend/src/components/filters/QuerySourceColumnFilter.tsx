import { forwardRef, useImperativeHandle, useEffect } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useQueryDashboardFilter } from './QueryDashboardFilterContext';
import { cn } from '../../lib/utils';
import { Check } from 'lucide-react';

const SOURCES = [
  { key: 'google_serp', label: 'Google SERP', color: 'text-blue-600' },
  { key: 'yandex_api', label: 'Yandex API', color: 'text-red-600' },
  { key: 'apollo_org', label: 'Apollo Org', color: 'text-purple-600' },
  { key: 'clay', label: 'Clay', color: 'text-amber-600' },
] as const;

export const QuerySourceColumnFilter = forwardRef((props: IFilterParams, ref) => {
  const { sourceFilters, toggleSource, setSourceFilters, filterOptions, resetPage } = useQueryDashboardFilter();

  useImperativeHandle(ref, () => ({
    isFilterActive: () => sourceFilters.length > 0,
    getModel: () => (sourceFilters.length > 0 ? { values: sourceFilters } : null),
    setModel: (model: { values: string[] } | null) => { setSourceFilters(model?.values || []); },
    doesFilterPass: () => true,
  }));

  useEffect(() => { props.filterChangedCallback(); }, [sourceFilters]);

  const available = new Set(filterOptions?.sources || []);

  return (
    <div className="p-3 min-w-[180px]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-neutral-500">SOURCE</span>
        {sourceFilters.length > 0 && (
          <button onClick={() => { setSourceFilters([]); resetPage(); }} className="text-[10px] text-red-500 hover:text-red-700">Clear</button>
        )}
      </div>
      <div className="flex flex-col gap-1">
        {SOURCES.filter(s => available.has(s.key)).map(({ key, label, color }) => {
          const isActive = sourceFilters.includes(key);
          return (
            <button key={key} onClick={() => { toggleSource(key); resetPage(); }}
              className={cn("flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                isActive ? "bg-blue-100 text-blue-700 border-blue-300" : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400")}>
              <span className={cn("w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                isActive ? "bg-indigo-500 border-indigo-500" : "border-neutral-300")}>
                {isActive && <Check className="w-2.5 h-2.5 text-white" />}
              </span>
              <span className={cn("flex-1", color)}>{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
});
QuerySourceColumnFilter.displayName = 'QuerySourceColumnFilter';
