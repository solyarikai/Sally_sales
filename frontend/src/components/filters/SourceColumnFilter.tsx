import { forwardRef, useImperativeHandle, useEffect, useState, useMemo } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useContactsFilter } from './ContactsFilterContext';
import { cn } from '../../lib/utils';
import { Check, Search } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';

const SOURCES = [
  { key: 'smartlead',                label: 'Email',        color: 'text-blue-600' },
  { key: 'getsales',                 label: 'LinkedIn',     color: 'text-amber-600' },
  { key: 'smartlead_pipeline_push',  label: 'Pipeline→SL',  color: 'text-emerald-600' },
  { key: 'pipeline',                 label: 'Pipeline',     color: 'text-emerald-600' },
  { key: 'smartlead_deliryo_sync',   label: 'SL Sync',      color: 'text-blue-500' },
] as const;

export const SourceColumnFilter = forwardRef((props: IFilterParams, ref) => {
  const { sourceFilter, setSourceFilter, resetPage } = useContactsFilter();
  const { isDark } = useTheme();
  const [query, setQuery] = useState('');

  useImperativeHandle(ref, () => ({
    isFilterActive: () => !!sourceFilter,
    getModel: () => (sourceFilter ? { value: sourceFilter } : null),
    setModel: (model: { value: string } | null) => {
      setSourceFilter(model?.value || null);
    },
    doesFilterPass: () => true,
  }));

  useEffect(() => {
    props.filterChangedCallback();
  }, [sourceFilter]);

  const handleSelect = (key: string) => {
    setSourceFilter(sourceFilter === key ? null : key);
    resetPage();
  };

  const filteredSources = useMemo(() => {
    if (!query.trim()) return SOURCES;
    const q = query.toLowerCase();
    return SOURCES.filter(s => s.label.toLowerCase().includes(q) || s.key.toLowerCase().includes(q));
  }, [query]);

  return (
    <div className={cn("p-3 min-w-[160px]", isDark && "bg-neutral-800")}>
      <div className="flex items-center justify-between mb-2">
        <span className={cn("text-xs font-medium", isDark ? "text-neutral-400" : "text-neutral-500")}>SOURCE</span>
        {sourceFilter && (
          <button
            onClick={() => { setSourceFilter(null); resetPage(); }}
            className="text-[10px] text-red-500 hover:text-red-700"
          >
            Clear
          </button>
        )}
      </div>
      <div className="relative mb-2">
        <Search className="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-neutral-400" />
        <input
          type="text"
          placeholder="Search sources..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className={cn(
            "w-full pl-7 pr-2 py-1.5 rounded-md border text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500",
            isDark ? "bg-neutral-700 border-neutral-600 text-neutral-200 placeholder-neutral-500" : "border-neutral-200"
          )}
        />
      </div>
      <div className="flex flex-col gap-1">
        {filteredSources.map(({ key, label, color }) => {
          const isActive = sourceFilter === key;
          return (
            <button
              key={key}
              onClick={() => handleSelect(key)}
              className={cn(
                "flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                isActive
                  ? (isDark ? "bg-emerald-900/40 text-emerald-300 border-emerald-700" : "bg-emerald-100 text-emerald-700 border-emerald-300")
                  : (isDark ? "bg-neutral-700 text-neutral-300 border-neutral-600 hover:border-neutral-400" : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400")
              )}
            >
              <span className={cn(
                "w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                isActive ? "bg-indigo-500 border-indigo-500" : (isDark ? "border-neutral-500" : "border-neutral-300")
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
