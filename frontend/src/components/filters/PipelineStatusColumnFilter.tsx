import { forwardRef, useImperativeHandle } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { usePipelineFilter } from './PipelineFilterContext';
import { cn } from '../../lib/utils';
import { Check } from 'lucide-react';

const STATUSES = [
  { key: 'new',                label: 'New',        dot: 'bg-blue-500',    colors: 'bg-blue-100 text-blue-700 border-blue-300' },
  { key: 'scraped',            label: 'Scraped',    dot: 'bg-cyan-500',    colors: 'bg-cyan-100 text-cyan-700 border-cyan-300' },
  { key: 'analyzed',           label: 'Analyzed',   dot: 'bg-yellow-500',  colors: 'bg-yellow-100 text-yellow-700 border-yellow-300' },
  { key: 'contacts_extracted', label: 'Contacts',   dot: 'bg-purple-500',  colors: 'bg-purple-100 text-purple-700 border-purple-300' },
  { key: 'enriched',           label: 'Enriched',   dot: 'bg-green-500',   colors: 'bg-green-100 text-green-700 border-green-300' },
  { key: 'exported',           label: 'Exported',   dot: 'bg-emerald-500', colors: 'bg-emerald-100 text-emerald-700 border-emerald-300' },
  { key: 'rejected',           label: 'Rejected',   dot: 'bg-red-500',     colors: 'bg-red-100 text-red-600 border-red-300' },
] as const;

export const PipelineStatusColumnFilter = forwardRef((_props: IFilterParams, ref) => {
  const { statusFilters, toggleStatus, setStatusFilters, resetPage } = usePipelineFilter();

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
            </button>
          );
        })}
      </div>
    </div>
  );
});

PipelineStatusColumnFilter.displayName = 'PipelineStatusColumnFilter';
