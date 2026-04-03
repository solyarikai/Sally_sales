import { forwardRef, useImperativeHandle, useState, useMemo, useEffect } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useContactsFilter } from './ContactsFilterContext';
import { cn } from '../../lib/utils';
import { Check, Search } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';

const STATUSES = [
  { key: 'new',                 label: 'New',                 dot: 'bg-gray-400',    colors: 'bg-gray-100 text-gray-600 border-gray-300' },
  { key: 'sent',                label: 'Sent',                dot: 'bg-gray-500',    colors: 'bg-gray-100 text-gray-600 border-gray-300' },
  { key: 'replied',             label: 'Replied',             dot: 'bg-blue-500',    colors: 'bg-blue-100 text-blue-700 border-blue-300' },
  { key: 'calendly_sent',       label: 'Calendly Sent',       dot: 'bg-orange-400',  colors: 'bg-orange-100 text-orange-700 border-orange-300' },
  { key: 'meeting_booked',      label: 'Meeting Booked',      dot: 'bg-orange-500',  colors: 'bg-orange-100 text-orange-700 border-orange-300' },
  { key: 'meeting_held',        label: 'Meeting Held',        dot: 'bg-green-500',   colors: 'bg-green-100 text-green-700 border-green-300' },
  { key: 'meeting_rescheduled', label: 'Meeting Rescheduled', dot: 'bg-amber-400',   colors: 'bg-amber-100 text-amber-700 border-amber-300' },
  { key: 'qualified',           label: 'Qualified',           dot: 'bg-emerald-500', colors: 'bg-emerald-100 text-emerald-700 border-emerald-300' },
  { key: 'not_qualified',       label: 'Not Qualified',       dot: 'bg-gray-600',    colors: 'bg-gray-100 text-gray-600 border-gray-300' },
] as const;

export const StatusColumnFilter = forwardRef((_props: IFilterParams, ref) => {
  const { statusFilters, setStatusFilters, stats, resetPage } = useContactsFilter();
  const { isDark } = useTheme();
  const [query, setQuery] = useState('');
  const [working, setWorking] = useState<string[]>(statusFilters);

  // Sync working state when context changes (e.g. URL navigation, external clear)
  useEffect(() => { setWorking(statusFilters); }, [statusFilters]);

  useImperativeHandle(ref, () => ({
    isFilterActive: () => statusFilters.length > 0,
    getModel: () => (statusFilters.length > 0 ? { values: statusFilters } : null),
    setModel: (model: { values: string[] } | null) => {
      setStatusFilters(model?.values || []);
    },
    doesFilterPass: () => true, // Server-side filtering
  }));

  const handleToggle = (key: string) => {
    setWorking(prev => prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]);
  };

  const handleApply = () => {
    setStatusFilters(working);
    resetPage();
  };

  const handleClear = () => {
    setWorking([]);
    setStatusFilters([]);
    resetPage();
  };

  const hasChanges = JSON.stringify([...working].sort()) !== JSON.stringify([...statusFilters].sort());

  const fmtCount = (n: number) => {
    if (n >= 1000) return `${(n / 1000).toFixed(1).replace(/\.0$/, '')}K`;
    return String(n);
  };

  const filteredStatuses = useMemo(() => {
    if (!query.trim()) return STATUSES;
    const q = query.toLowerCase();
    return STATUSES.filter(s => s.label.toLowerCase().includes(q) || s.key.toLowerCase().includes(q));
  }, [query]);

  return (
    <div className={cn("min-w-[180px] flex flex-col", isDark && "bg-neutral-800")}>
      <div className="p-3 pb-0">
        <div className="flex items-center justify-between mb-2">
          <span className={cn("text-xs font-medium", isDark ? "text-neutral-400" : "text-neutral-500")}>STATUS</span>
          {(working.length > 0 || statusFilters.length > 0) && (
            <button
              onClick={handleClear}
              className="text-[10px] text-red-500 hover:text-red-700"
            >
              Clear ({working.length})
            </button>
          )}
        </div>
        <div className="relative mb-2">
          <Search className="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-neutral-400" />
          <input
            type="text"
            placeholder="Search statuses..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className={cn(
              "w-full pl-7 pr-2 py-1.5 rounded-md border text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500",
              isDark ? "bg-neutral-700 border-neutral-600 text-neutral-200 placeholder-neutral-500" : "border-neutral-200"
            )}
          />
        </div>
      </div>
      <div className="flex flex-col gap-1 max-h-[320px] overflow-y-auto px-3">
        {filteredStatuses.map(({ key, label, dot }) => {
          const isActive = working.includes(key);
          const count = stats?.by_status?.[key] ?? 0;
          return (
            <button
              key={key}
              onClick={() => handleToggle(key)}
              className={cn(
                "flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                isActive
                  ? (isDark ? "bg-indigo-900/40 text-indigo-300 border-indigo-700" : "bg-indigo-50 text-indigo-700 border-indigo-200")
                  : (isDark ? "bg-neutral-700 text-neutral-300 border-neutral-600 hover:border-neutral-400" : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400")
              )}
            >
              <span className={cn(
                "w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                isActive ? "bg-indigo-500 border-indigo-500" : (isDark ? "border-neutral-500" : "border-neutral-300")
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
      <div className={cn(
        "sticky bottom-0 border-t p-2 flex justify-end",
        isDark ? "border-neutral-700 bg-neutral-800" : "border-neutral-200 bg-white"
      )}>
        <button
          onClick={handleApply}
          disabled={!hasChanges}
          className={cn(
            "px-4 py-1.5 rounded text-xs font-medium transition-colors",
            hasChanges
              ? "bg-indigo-600 text-white hover:bg-indigo-700"
              : (isDark ? "bg-neutral-700 text-neutral-500 cursor-not-allowed" : "bg-neutral-100 text-neutral-400 cursor-not-allowed")
          )}
        >
          OK
        </button>
      </div>
    </div>
  );
});

StatusColumnFilter.displayName = 'StatusColumnFilter';
