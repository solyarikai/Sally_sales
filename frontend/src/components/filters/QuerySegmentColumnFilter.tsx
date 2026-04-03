import { forwardRef, useImperativeHandle, useState, useMemo, useEffect } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useQueryDashboardFilter } from './QueryDashboardFilterContext';
import { cn } from '../../lib/utils';
import { Search, Check, X } from 'lucide-react';

export const QuerySegmentColumnFilter = forwardRef((props: IFilterParams, ref) => {
  const { segmentFilters, toggleSegment, setSegmentFilters, filterOptions, resetPage } = useQueryDashboardFilter();
  const [query, setQuery] = useState('');

  useImperativeHandle(ref, () => ({
    isFilterActive: () => segmentFilters.length > 0,
    getModel: () => (segmentFilters.length > 0 ? { values: segmentFilters } : null),
    setModel: (model: { values: string[] } | null) => { setSegmentFilters(model?.values || []); },
    doesFilterPass: () => true,
  }));

  useEffect(() => { props.filterChangedCallback?.(); }, [segmentFilters]);

  const segments = filterOptions?.segments || [];
  const filtered = useMemo(() => {
    if (!query.trim()) return segments;
    const q = query.toLowerCase();
    return segments.filter(s => s.toLowerCase().includes(q));
  }, [segments, query]);

  const handleToggle = (seg: string) => { toggleSegment(seg); resetPage(); };
  const clearAll = () => { setSegmentFilters([]); resetPage(); setQuery(''); };

  return (
    <div className="p-3 min-w-[200px] max-w-[280px]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-neutral-500">SEGMENT</span>
        {segmentFilters.length > 0 && (
          <button onClick={clearAll} className="text-[10px] text-red-500 hover:text-red-700">Clear all ({segmentFilters.length})</button>
        )}
      </div>
      {segmentFilters.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {segmentFilters.map(seg => (
            <div key={seg} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-blue-50 border border-blue-200 text-[10px] text-blue-700 max-w-[140px]">
              <span className="truncate">{seg.replace(/_/g, ' ')}</span>
              <button onClick={() => handleToggle(seg)} className="text-blue-400 hover:text-blue-700 shrink-0"><X className="w-2.5 h-2.5" /></button>
            </div>
          ))}
        </div>
      )}
      {segments.length > 5 && (
        <div className="relative mb-2">
          <Search className="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-neutral-400" />
          <input type="text" placeholder="Search segments..." value={query} onChange={(e) => setQuery(e.target.value)}
            className="w-full pl-7 pr-2 py-1.5 rounded-md border border-neutral-200 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500" />
        </div>
      )}
      <div className="flex flex-col gap-1 max-h-[240px] overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="text-xs text-neutral-400 px-2 py-3 text-center">{query ? 'No segments match' : 'No segments'}</div>
        ) : filtered.map((seg) => {
          const isActive = segmentFilters.includes(seg);
          return (
            <button key={seg} onClick={() => handleToggle(seg)}
              className={cn("flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                isActive ? "bg-blue-100 text-blue-700 border-blue-300" : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400")}>
              <span className={cn("w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                isActive ? "bg-indigo-500 border-indigo-500" : "border-neutral-300")}>
                {isActive && <Check className="w-2.5 h-2.5 text-white" />}
              </span>
              <span className="flex-1 truncate">{seg.replace(/_/g, ' ')}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
});
QuerySegmentColumnFilter.displayName = 'QuerySegmentColumnFilter';
