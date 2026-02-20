import { forwardRef, useImperativeHandle, useEffect } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useQueryDashboardFilter } from './QueryDashboardFilterContext';
import { cn } from '../../lib/utils';

const OPTIONS = [
  { key: null, label: 'All' },
  { key: true, label: 'Saturated' },
  { key: false, label: 'Non-saturated' },
] as const;

export const QuerySaturatedColumnFilter = forwardRef((props: IFilterParams, ref) => {
  const { saturatedFilter, setSaturatedFilter, resetPage } = useQueryDashboardFilter();

  useImperativeHandle(ref, () => ({
    isFilterActive: () => saturatedFilter !== null,
    getModel: () => (saturatedFilter !== null ? { value: saturatedFilter } : null),
    setModel: (model: { value: boolean } | null) => { setSaturatedFilter(model?.value ?? null); },
    doesFilterPass: () => true,
  }));

  useEffect(() => { props.filterChangedCallback?.(); }, [saturatedFilter]);

  return (
    <div className="p-3 min-w-[160px]">
      <div className="mb-2">
        <span className="text-xs font-medium text-neutral-500">SATURATION</span>
      </div>
      <div className="flex flex-col gap-1">
        {OPTIONS.map(({ key, label }) => {
          const isActive = saturatedFilter === key;
          return (
            <button key={String(key)} onClick={() => { setSaturatedFilter(key); resetPage(); }}
              className={cn("px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                isActive ? "bg-indigo-100 text-indigo-700 border-indigo-300" : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400")}>
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
});
QuerySaturatedColumnFilter.displayName = 'QuerySaturatedColumnFilter';
