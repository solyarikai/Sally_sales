import { forwardRef, useImperativeHandle, useEffect, useMemo } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useQueryDashboardFilter } from './QueryDashboardFilterContext';
import { cn } from '../../lib/utils';

const PRESETS = [
  { key: 'today', label: 'Today' },
  { key: 'this_week', label: 'This week' },
  { key: 'last_7d', label: 'Last 7 days' },
  { key: 'last_30d', label: 'Last 30 days' },
] as const;

function getPresetRange(key: string): { after: string; before: string | null } {
  const now = new Date();
  const fmt = (d: Date) => d.toISOString().split('T')[0];
  switch (key) {
    case 'today': return { after: fmt(now), before: null };
    case 'this_week': {
      const day = now.getDay();
      const monday = new Date(now);
      monday.setDate(now.getDate() - ((day + 6) % 7));
      return { after: fmt(monday), before: null };
    }
    case 'last_7d': {
      const d = new Date(now);
      d.setDate(d.getDate() - 7);
      return { after: fmt(d), before: null };
    }
    case 'last_30d': {
      const d = new Date(now);
      d.setDate(d.getDate() - 30);
      return { after: fmt(d), before: null };
    }
    default: return { after: fmt(now), before: null };
  }
}

export const QueryDateColumnFilter = forwardRef((props: IFilterParams, ref) => {
  const { dateFrom, dateTo, setDateRange, resetPage } = useQueryDashboardFilter();

  useImperativeHandle(ref, () => ({
    isFilterActive: () => dateFrom !== null || dateTo !== null,
    getModel: () => (dateFrom || dateTo ? { from: dateFrom, to: dateTo } : null),
    setModel: (model: { from: string | null; to: string | null } | null) => {
      setDateRange(model?.from ?? null, model?.to ?? null);
    },
    doesFilterPass: () => true,
  }));

  useEffect(() => { props.filterChangedCallback(); }, [dateFrom, dateTo]);

  const activePreset = useMemo(() => {
    if (!dateFrom) return null;
    for (const p of PRESETS) {
      const range = getPresetRange(p.key);
      if (range.after === dateFrom && (range.before ?? null) === dateTo) return p.key;
    }
    return null;
  }, [dateFrom, dateTo]);

  const handlePreset = (key: string) => {
    if (activePreset === key) { setDateRange(null, null); }
    else {
      const range = getPresetRange(key);
      setDateRange(range.after, range.before);
    }
    resetPage();
  };

  const clear = () => { setDateRange(null, null); resetPage(); };

  return (
    <div className="p-3 min-w-[200px]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-neutral-500">DATE</span>
        {(dateFrom || dateTo) && (
          <button onClick={clear} className="text-[10px] text-red-500 hover:text-red-700">Clear</button>
        )}
      </div>
      <div className="flex flex-col gap-1 mb-3">
        {PRESETS.map(({ key, label }) => (
          <button key={key} onClick={() => handlePreset(key)}
            className={cn("px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
              activePreset === key ? "bg-indigo-100 text-indigo-700 border-indigo-300" : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400")}>
            {label}
          </button>
        ))}
      </div>
      <div className="text-[10px] text-neutral-400 mb-1.5">Custom range</div>
      <div className="flex flex-col gap-1.5">
        <input type="date" value={dateFrom || ''} onChange={(e) => { setDateRange(e.target.value || null, dateTo); resetPage(); }}
          className="w-full px-2 py-1.5 rounded-md border border-neutral-200 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500" />
        <input type="date" value={dateTo || ''} onChange={(e) => { setDateRange(dateFrom, e.target.value || null); resetPage(); }}
          className="w-full px-2 py-1.5 rounded-md border border-neutral-200 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500" />
      </div>
    </div>
  );
});
QueryDateColumnFilter.displayName = 'QueryDateColumnFilter';
