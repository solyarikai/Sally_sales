import { forwardRef, useImperativeHandle, useEffect } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useQueryDashboardFilter } from './QueryDashboardFilterContext';
import { cn } from '../../lib/utils';
import { Check } from 'lucide-react';

const STATUSES = [
  { key: 'pending', label: 'Pending', dot: 'bg-amber-500', colors: 'bg-amber-100 text-amber-700 border-amber-300' },
  { key: 'done', label: 'Done', dot: 'bg-green-500', colors: 'bg-green-100 text-green-700 border-green-300' },
  { key: 'failed', label: 'Failed', dot: 'bg-red-500', colors: 'bg-red-100 text-red-600 border-red-300' },
] as const;

export const QueryStatusColumnFilter = forwardRef((props: IFilterParams, ref) => {
  const { statusFilters, toggleStatus, setStatusFilters, resetPage } = useQueryDashboardFilter();

  useImperativeHandle(ref, () => ({
    isFilterActive: () => statusFilters.length > 0,
    getModel: () => (statusFilters.length > 0 ? { values: statusFilters } : null),
    setModel: (model: { values: string[] } | null) => { setStatusFilters(model?.values || []); },
    doesFilterPass: () => true,
  }));

  useEffect(() => { props.filterChangedCallback(); }, [statusFilters]);

  return (
    <div className="p-3 min-w-[160px]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-neutral-500">STATUS</span>
        {statusFilters.length > 0 && (
          <button onClick={() => { setStatusFilters([]); resetPage(); }} className="text-[10px] text-red-500 hover:text-red-700">Clear</button>
        )}
      </div>
      <div className="flex flex-col gap-1">
        {STATUSES.map(({ key, label, dot, colors }) => {
          const isActive = statusFilters.includes(key);
          return (
            <button key={key} onClick={() => { toggleStatus(key); resetPage(); }}
              className={cn("flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                isActive ? colors : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400")}>
              <span className={cn("w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                isActive ? "bg-indigo-500 border-indigo-500" : "border-neutral-300")}>
                {isActive && <Check className="w-2.5 h-2.5 text-white" />}
              </span>
              <span className={cn("w-1.5 h-1.5 rounded-full", dot)} />
              <span className="flex-1">{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
});
QueryStatusColumnFilter.displayName = 'QueryStatusColumnFilter';
