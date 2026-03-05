import { forwardRef, useImperativeHandle, useState, useMemo, useEffect } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useContactsFilter } from './ContactsFilterContext';
import { cn } from '../../lib/utils';
import { Search, Check, X } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';

export const SegmentColumnFilter = forwardRef((props: IFilterParams, ref) => {
  const { segmentFilters, toggleSegment, setSegmentFilters, filterOptions, resetPage } = useContactsFilter();
  const { isDark } = useTheme();
  const [query, setQuery] = useState('');

  useImperativeHandle(ref, () => ({
    isFilterActive: () => segmentFilters.length > 0,
    getModel: () => (segmentFilters.length > 0 ? { values: segmentFilters } : null),
    setModel: (model: { values: string[] } | null) => {
      setSegmentFilters(model?.values || []);
    },
    doesFilterPass: () => true,
  }));

  useEffect(() => {
    props.filterChangedCallback?.();
  }, [segmentFilters]);

  const segments = filterOptions?.segments || [];

  const filtered = useMemo(() => {
    if (!query.trim()) return segments;
    const q = query.toLowerCase();
    return segments.filter(seg => seg.toLowerCase().includes(q));
  }, [segments, query]);

  const handleToggle = (seg: string) => {
    toggleSegment(seg);
    resetPage();
  };

  const clearAll = () => {
    setSegmentFilters([]);
    resetPage();
    setQuery('');
  };

  return (
    <div className={cn("p-3 min-w-[200px] max-w-[280px]", isDark && "bg-neutral-800")}>
      <div className="flex items-center justify-between mb-2">
        <span className={cn("text-xs font-medium", isDark ? "text-neutral-400" : "text-neutral-500")}>SEGMENT</span>
        {segmentFilters.length > 0 && (
          <button onClick={clearAll} className="text-[10px] text-red-500 hover:text-red-700">
            Clear all ({segmentFilters.length})
          </button>
        )}
      </div>

      {/* Selected segment chips */}
      {segmentFilters.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {segmentFilters.map(seg => (
            <div key={seg} className={cn(
              "inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] max-w-[140px]",
              isDark ? "bg-blue-900/40 border-blue-700 text-blue-300" : "bg-blue-50 border-blue-200 text-blue-700"
            )}>
              <span className="truncate">{seg.replace(/_/g, ' ')}</span>
              <button onClick={() => handleToggle(seg)} className={cn("shrink-0", isDark ? "text-blue-400 hover:text-blue-200" : "text-blue-400 hover:text-blue-700")}>
                <X className="w-2.5 h-2.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {segments.length > 5 && (
        <div className="relative mb-2">
          <Search className="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-neutral-400" />
          <input
            type="text"
            placeholder="Search segments..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className={cn(
              "w-full pl-7 pr-2 py-1.5 rounded-md border text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500",
              isDark ? "bg-neutral-700 border-neutral-600 text-neutral-200 placeholder-neutral-500" : "border-neutral-200"
            )}
          />
        </div>
      )}
      <div className="flex flex-col gap-1 max-h-[240px] overflow-y-auto">
        {filtered.length === 0 ? (
          <div className={cn("text-xs px-2 py-3 text-center", isDark ? "text-neutral-500" : "text-neutral-400")}>
            {query ? 'No segments match' : 'No segments'}
          </div>
        ) : (
          filtered.map((seg) => {
            const isActive = segmentFilters.includes(seg);
            return (
              <button
                key={seg}
                onClick={() => handleToggle(seg)}
                className={cn(
                  "flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                  isActive
                    ? (isDark ? "bg-blue-900/40 text-blue-300 border-blue-700" : "bg-blue-100 text-blue-700 border-blue-300")
                    : (isDark ? "bg-neutral-700 text-neutral-300 border-neutral-600 hover:border-neutral-400" : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400")
                )}
              >
                <span className={cn(
                  "w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                  isActive ? "bg-indigo-500 border-indigo-500" : (isDark ? "border-neutral-500" : "border-neutral-300")
                )}>
                  {isActive && <Check className="w-2.5 h-2.5 text-white" />}
                </span>
                <span className="flex-1 truncate">{seg.replace(/_/g, ' ')}</span>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
});

SegmentColumnFilter.displayName = 'SegmentColumnFilter';
