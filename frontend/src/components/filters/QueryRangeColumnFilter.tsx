import { forwardRef, useImperativeHandle, useState, useEffect } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useQueryDashboardFilter } from './QueryDashboardFilterContext';

interface QueryRangeColumnFilterProps extends IFilterParams {
  rangeField: 'domains' | 'targets';
}

export const QueryRangeColumnFilter = forwardRef((props: QueryRangeColumnFilterProps, ref) => {
  const ctx = useQueryDashboardFilter();
  const field = props.rangeField || 'domains';

  const min = field === 'domains' ? ctx.domainsMin : ctx.targetsMin;
  const max = field === 'domains' ? ctx.domainsMax : ctx.targetsMax;
  const setRange = field === 'domains' ? ctx.setDomainsRange : ctx.setTargetsRange;

  const [localMin, setLocalMin] = useState(min !== null ? String(min) : '');
  const [localMax, setLocalMax] = useState(max !== null ? String(max) : '');

  useImperativeHandle(ref, () => ({
    isFilterActive: () => min !== null || max !== null,
    getModel: () => (min !== null || max !== null ? { min, max } : null),
    setModel: (model: { min: number | null; max: number | null } | null) => {
      setRange(model?.min ?? null, model?.max ?? null);
    },
    doesFilterPass: () => true,
  }));

  useEffect(() => { props.filterChangedCallback?.(); }, [min, max]);

  // Sync local state with context
  useEffect(() => {
    setLocalMin(min !== null ? String(min) : '');
    setLocalMax(max !== null ? String(max) : '');
  }, [min, max]);

  const applyRange = () => {
    const newMin = localMin ? parseInt(localMin, 10) : null;
    const newMax = localMax ? parseInt(localMax, 10) : null;
    setRange(
      isNaN(newMin as number) ? null : newMin,
      isNaN(newMax as number) ? null : newMax,
    );
    ctx.resetPage();
  };

  const clear = () => { setRange(null, null); ctx.resetPage(); setLocalMin(''); setLocalMax(''); };

  const label = field === 'domains' ? 'DOMAINS' : 'TARGETS';

  return (
    <div className="p-3 min-w-[180px]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-neutral-500">{label} RANGE</span>
        {(min !== null || max !== null) && (
          <button onClick={clear} className="text-[10px] text-red-500 hover:text-red-700">Clear</button>
        )}
      </div>
      <div className="flex items-center gap-2 mb-2">
        <input type="number" placeholder="Min" value={localMin} onChange={(e) => setLocalMin(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && applyRange()}
          className="w-20 px-2 py-1.5 rounded-md border border-neutral-200 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500" />
        <span className="text-neutral-400 text-xs">–</span>
        <input type="number" placeholder="Max" value={localMax} onChange={(e) => setLocalMax(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && applyRange()}
          className="w-20 px-2 py-1.5 rounded-md border border-neutral-200 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500" />
      </div>
      <button onClick={applyRange}
        className="w-full px-2 py-1.5 rounded-md bg-indigo-500 text-white text-xs font-medium hover:bg-indigo-600 transition-colors">
        Apply
      </button>
    </div>
  );
});
QueryRangeColumnFilter.displayName = 'QueryRangeColumnFilter';
