import { forwardRef, useImperativeHandle } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useContactsFilter } from './ContactsFilterContext';
import { cn } from '../../lib/utils';
import { Check } from 'lucide-react';

const STATUSES = [
  { key: 'touched',        label: 'Touched',         dot: 'bg-blue-500',    colors: 'bg-blue-100 text-blue-700 border-blue-300' },
  { key: 'warm',           label: 'Warm',            dot: 'bg-amber-500',   colors: 'bg-amber-100 text-amber-700 border-amber-300' },
  { key: 'replied',        label: 'Replied',         dot: 'bg-green-500',   colors: 'bg-green-100 text-green-700 border-green-300' },
  { key: 'qualified',      label: 'Qualified',       dot: 'bg-emerald-500', colors: 'bg-emerald-100 text-emerald-700 border-emerald-300' },
  { key: 'not_interested', label: 'Not Interested',  dot: 'bg-gray-400',    colors: 'bg-gray-100 text-gray-600 border-gray-300' },
  { key: 'wrong_person',   label: 'Wrong Person',    dot: 'bg-red-400',     colors: 'bg-red-100 text-red-600 border-red-300' },
  { key: 'out_of_office',  label: 'OOO',             dot: 'bg-yellow-400',  colors: 'bg-yellow-100 text-yellow-700 border-yellow-300' },
  { key: 'other',          label: 'Other',           dot: 'bg-purple-400',  colors: 'bg-purple-100 text-purple-600 border-purple-300' },
  { key: 'customer',       label: 'Customer',        dot: 'bg-emerald-600', colors: 'bg-emerald-100 text-emerald-700 border-emerald-300' },
  { key: 'lost',           label: 'Lost',            dot: 'bg-red-500',     colors: 'bg-red-100 text-red-600 border-red-300' },
] as const;

export const StatusColumnFilter = forwardRef((_props: IFilterParams, ref) => {
  const { statusFilters, toggleStatus, setStatusFilters, stats, resetPage } = useContactsFilter();

  useImperativeHandle(ref, () => ({
    isFilterActive: () => statusFilters.length > 0,
    getModel: () => (statusFilters.length > 0 ? { values: statusFilters } : null),
    setModel: (model: { values: string[] } | null) => {
      setStatusFilters(model?.values || []);
    },
    doesFilterPass: () => true, // Server-side filtering
  }));

  const handleToggle = (key: string) => {
    toggleStatus(key);
    resetPage();
  };

  const fmtCount = (n: number) => {
    if (n >= 1000) return `${(n / 1000).toFixed(1).replace(/\.0$/, '')}K`;
    return String(n);
  };

  return (
    <div className="p-3 min-w-[180px]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-neutral-500">STATUS</span>
        {statusFilters.length > 0 && (
          <button
            onClick={() => { setStatusFilters([]); resetPage(); }}
            className="text-[10px] text-red-500 hover:text-red-700"
          >
            Clear ({statusFilters.length})
          </button>
        )}
      </div>
      <div className="flex flex-col gap-1">
        {STATUSES.map(({ key, label, dot, colors }) => {
          const isActive = statusFilters.includes(key);
          const count = stats?.by_status?.[key] ?? 0;
          return (
            <button
              key={key}
              onClick={() => handleToggle(key)}
              className={cn(
                "flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                isActive ? colors : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400"
              )}
            >
              <span className={cn(
                "w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                isActive ? "bg-indigo-500 border-indigo-500" : "border-neutral-300"
              )}>
                {isActive && <Check className="w-2.5 h-2.5 text-white" />}
              </span>
              <span className={cn("w-2 h-2 rounded-full shrink-0", dot)} />
              <span className="flex-1">{label}</span>
              {count > 0 && <span className="text-[10px] opacity-60">{fmtCount(count)}</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
});

StatusColumnFilter.displayName = 'StatusColumnFilter';
