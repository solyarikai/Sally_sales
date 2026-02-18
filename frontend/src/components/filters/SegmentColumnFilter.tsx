import { forwardRef, useImperativeHandle } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useContactsFilter } from './ContactsFilterContext';
import { cn } from '../../lib/utils';
import { Check } from 'lucide-react';

export const SegmentColumnFilter = forwardRef((_props: IFilterParams, ref) => {
  const { segmentFilter, setSegmentFilter, filterOptions, resetPage } = useContactsFilter();

  useImperativeHandle(ref, () => ({
    isFilterActive: () => !!segmentFilter,
    getModel: () => (segmentFilter ? { value: segmentFilter } : null),
    setModel: (model: { value: string } | null) => {
      setSegmentFilter(model?.value || null);
    },
    doesFilterPass: () => true,
  }));

  const segments = filterOptions?.segments || [];

  const handleSelect = (seg: string) => {
    setSegmentFilter(segmentFilter === seg ? null : seg);
    resetPage();
  };

  return (
    <div className="p-3 min-w-[180px]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-neutral-500">SEGMENT</span>
        {segmentFilter && (
          <button
            onClick={() => { setSegmentFilter(null); resetPage(); }}
            className="text-[10px] text-red-500 hover:text-red-700"
          >
            Clear
          </button>
        )}
      </div>
      <div className="flex flex-col gap-1 max-h-[240px] overflow-y-auto">
        {segments.length === 0 ? (
          <div className="text-xs text-neutral-400 px-2 py-3 text-center">No segments</div>
        ) : (
          segments.map((seg) => {
            const isActive = segmentFilter === seg;
            return (
              <button
                key={seg}
                onClick={() => handleSelect(seg)}
                className={cn(
                  "flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                  isActive
                    ? "bg-blue-100 text-blue-700 border-blue-300"
                    : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400"
                )}
              >
                <span className={cn(
                  "w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                  isActive ? "bg-indigo-500 border-indigo-500" : "border-neutral-300"
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
