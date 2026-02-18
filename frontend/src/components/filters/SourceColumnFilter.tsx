import { forwardRef, useImperativeHandle } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useContactsFilter } from './ContactsFilterContext';
import { cn } from '../../lib/utils';
import { Check } from 'lucide-react';

const SOURCES = [
  { key: 'smartlead',                label: 'Email',        color: 'text-blue-600' },
  { key: 'getsales',                 label: 'LinkedIn',     color: 'text-amber-600' },
  { key: 'smartlead_pipeline_push',  label: 'Pipeline→SL',  color: 'text-emerald-600' },
  { key: 'pipeline',                 label: 'Pipeline',     color: 'text-emerald-600' },
  { key: 'smartlead_deliryo_sync',   label: 'SL Sync',      color: 'text-blue-500' },
] as const;

export const SourceColumnFilter = forwardRef((_props: IFilterParams, ref) => {
  const { sourceFilter, setSourceFilter, resetPage } = useContactsFilter();

  useImperativeHandle(ref, () => ({
    isFilterActive: () => !!sourceFilter,
    getModel: () => (sourceFilter ? { value: sourceFilter } : null),
    setModel: (model: { value: string } | null) => {
      setSourceFilter(model?.value || null);
    },
    doesFilterPass: () => true,
  }));

  const handleSelect = (key: string) => {
    setSourceFilter(sourceFilter === key ? null : key);
    resetPage();
  };

  return (
    <div className="p-3 min-w-[160px]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-neutral-500">SOURCE</span>
        {sourceFilter && (
          <button
            onClick={() => { setSourceFilter(null); resetPage(); }}
            className="text-[10px] text-red-500 hover:text-red-700"
          >
            Clear
          </button>
        )}
      </div>
      <div className="flex flex-col gap-1">
        {SOURCES.map(({ key, label, color }) => {
          const isActive = sourceFilter === key;
          return (
            <button
              key={key}
              onClick={() => handleSelect(key)}
              className={cn(
                "flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                isActive
                  ? "bg-emerald-100 text-emerald-700 border-emerald-300"
                  : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400"
              )}
            >
              <span className={cn(
                "w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                isActive ? "bg-indigo-500 border-indigo-500" : "border-neutral-300"
              )}>
                {isActive && <Check className="w-2.5 h-2.5 text-white" />}
              </span>
              <span className={cn("flex-1", isActive ? "" : color)}>{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
});

SourceColumnFilter.displayName = 'SourceColumnFilter';
