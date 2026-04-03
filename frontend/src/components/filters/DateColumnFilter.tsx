import { forwardRef, useImperativeHandle, useState, useEffect } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useContactsFilter } from './ContactsFilterContext';
import { cn } from '../../lib/utils';
import { Check } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';

function getPresetRange(key: string): { after: string; before: string | null } {
  const now = new Date();
  const fmt = (d: Date) => d.toISOString().split('T')[0];

  switch (key) {
    case 'today': {
      return { after: fmt(now), before: null };
    }
    case 'this_week': {
      const day = now.getDay();
      const monday = new Date(now);
      monday.setDate(now.getDate() - ((day + 6) % 7));
      return { after: fmt(monday), before: null };
    }
    case 'last_7d': {
      const d = new Date(now);
      d.setDate(now.getDate() - 7);
      return { after: fmt(d), before: null };
    }
    case 'last_30d': {
      const d = new Date(now);
      d.setDate(now.getDate() - 30);
      return { after: fmt(d), before: null };
    }
    default:
      return { after: fmt(now), before: null };
  }
}

const PRESETS = [
  { key: 'today', label: 'Today' },
  { key: 'this_week', label: 'This week' },
  { key: 'last_7d', label: 'Last 7 days' },
  { key: 'last_30d', label: 'Last 30 days' },
] as const;

export const DateColumnFilter = forwardRef((props: IFilterParams, ref) => {
  const { createdAfter, createdBefore, setDateRange, resetPage } = useContactsFilter();
  const { isDark } = useTheme();
  const [customFrom, setCustomFrom] = useState(createdAfter || '');
  const [customTo, setCustomTo] = useState(createdBefore || '');

  const activePreset = PRESETS.find(p => {
    const range = getPresetRange(p.key);
    return range.after === createdAfter && !createdBefore;
  })?.key || null;

  useImperativeHandle(ref, () => ({
    isFilterActive: () => !!(createdAfter || createdBefore),
    getModel: () => (createdAfter || createdBefore) ? { after: createdAfter, before: createdBefore } : null,
    setModel: (model: { after: string | null; before: string | null } | null) => {
      setDateRange(model?.after || null, model?.before || null);
    },
    doesFilterPass: () => true,
  }));

  useEffect(() => {
    props.filterChangedCallback?.();
  }, [createdAfter, createdBefore]);

  const handlePreset = (key: string) => {
    if (activePreset === key) {
      setDateRange(null, null);
      setCustomFrom('');
      setCustomTo('');
    } else {
      const range = getPresetRange(key);
      setDateRange(range.after, range.before);
      setCustomFrom(range.after);
      setCustomTo('');
    }
    resetPage();
  };

  const handleCustomApply = () => {
    setDateRange(customFrom || null, customTo || null);
    resetPage();
  };

  const handleClear = () => {
    setDateRange(null, null);
    setCustomFrom('');
    setCustomTo('');
    resetPage();
  };

  return (
    <div className={cn("p-3 min-w-[200px]", isDark && "bg-neutral-800")}>
      <div className="flex items-center justify-between mb-2">
        <span className={cn("text-xs font-medium", isDark ? "text-neutral-400" : "text-neutral-500")}>DATE ADDED</span>
        {(createdAfter || createdBefore) && (
          <button onClick={handleClear} className="text-[10px] text-red-500 hover:text-red-700">
            Clear
          </button>
        )}
      </div>

      <div className="flex flex-col gap-1 mb-3">
        {PRESETS.map(({ key, label }) => {
          const isActive = activePreset === key;
          return (
            <button
              key={key}
              onClick={() => handlePreset(key)}
              className={cn(
                "flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                isActive
                  ? (isDark ? "bg-indigo-900/40 text-indigo-300 border-indigo-700" : "bg-indigo-100 text-indigo-700 border-indigo-300")
                  : (isDark ? "bg-neutral-700 text-neutral-300 border-neutral-600 hover:border-neutral-400" : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400")
              )}
            >
              <span className={cn(
                "w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                isActive ? "bg-indigo-500 border-indigo-500" : (isDark ? "border-neutral-500" : "border-neutral-300")
              )}>
                {isActive && <Check className="w-2.5 h-2.5 text-white" />}
              </span>
              <span className="flex-1">{label}</span>
            </button>
          );
        })}
      </div>

      <div className={cn("border-t pt-2", isDark ? "border-neutral-700" : "border-neutral-100")}>
        <span className={cn("text-[10px] font-medium uppercase tracking-wide", isDark ? "text-neutral-500" : "text-neutral-400")}>Custom range</span>
        <div className="flex flex-col gap-1.5 mt-1.5">
          <input
            type="date"
            value={customFrom}
            onChange={(e) => setCustomFrom(e.target.value)}
            className={cn(
              "w-full px-2 py-1 text-xs border rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400",
              isDark ? "bg-neutral-700 border-neutral-600 text-neutral-200" : "border-neutral-200"
            )}
            placeholder="From"
          />
          <input
            type="date"
            value={customTo}
            onChange={(e) => setCustomTo(e.target.value)}
            className={cn(
              "w-full px-2 py-1 text-xs border rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-400",
              isDark ? "bg-neutral-700 border-neutral-600 text-neutral-200" : "border-neutral-200"
            )}
            placeholder="To"
          />
          <button
            onClick={handleCustomApply}
            disabled={!customFrom && !customTo}
            className="w-full px-2 py-1 text-xs font-medium rounded-lg bg-indigo-500 text-white hover:bg-indigo-600 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Apply
          </button>
        </div>
      </div>
    </div>
  );
});

DateColumnFilter.displayName = 'DateColumnFilter';
