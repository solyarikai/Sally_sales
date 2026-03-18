import { forwardRef, useImperativeHandle, useState, useMemo } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useContactsFilter } from './ContactsFilterContext';
import { cn } from '../../lib/utils';
import { Check, Search } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';

const REPLY_CATEGORIES = [
  { key: 'meeting_request', label: 'Просит встречу',  dot: 'bg-green-500' },
  { key: 'interested',      label: 'Заинтересован',   dot: 'bg-blue-500' },
  { key: 'question',        label: 'Вопрос',          dot: 'bg-indigo-500' },
  { key: 'not_interested',  label: 'Не интересно',    dot: 'bg-gray-400' },
  { key: 'out_of_office',   label: 'Нет на месте',    dot: 'bg-yellow-400' },
  { key: 'wrong_person',    label: 'Не тот человек',  dot: 'bg-red-400' },
  { key: 'unsubscribe',     label: 'Отписка',         dot: 'bg-orange-400' },
  { key: 'other',           label: 'Другое',          dot: 'bg-purple-400' },
] as const;

export const ReplyCategoryColumnFilter = forwardRef((_props: IFilterParams, ref) => {
  const { replyCategoryFilters, toggleReplyCategory, setReplyCategoryFilters, resetPage } = useContactsFilter();
  const { isDark } = useTheme();
  const [query, setQuery] = useState('');

  useImperativeHandle(ref, () => ({
    isFilterActive: () => replyCategoryFilters.length > 0,
    getModel: () => (replyCategoryFilters.length > 0 ? { values: replyCategoryFilters } : null),
    setModel: (model: { values: string[] } | null) => {
      setReplyCategoryFilters(model?.values || []);
    },
    doesFilterPass: () => true, // Server-side filtering
  }));

  const handleToggle = (key: string) => {
    toggleReplyCategory(key);
    resetPage();
  };

  const filteredCategories = useMemo(() => {
    if (!query.trim()) return REPLY_CATEGORIES;
    const q = query.toLowerCase();
    return REPLY_CATEGORIES.filter(c => c.label.toLowerCase().includes(q) || c.key.toLowerCase().includes(q));
  }, [query]);

  return (
    <div className={cn("p-3 min-w-[180px]", isDark && "bg-neutral-800")}>
      <div className="flex items-center justify-between mb-2">
        <span className={cn("text-xs font-medium", isDark ? "text-neutral-400" : "text-neutral-500")}>REPLY TYPE</span>
        {replyCategoryFilters.length > 0 && (
          <button
            onClick={() => { setReplyCategoryFilters([]); resetPage(); }}
            className="text-[10px] text-red-500 hover:text-red-700"
          >
            Clear ({replyCategoryFilters.length})
          </button>
        )}
      </div>
      <div className="relative mb-2">
        <Search className="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-neutral-400" />
        <input
          type="text"
          placeholder="Search types..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className={cn(
            "w-full pl-7 pr-2 py-1.5 rounded-md border text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500",
            isDark ? "bg-neutral-700 border-neutral-600 text-neutral-200 placeholder-neutral-500" : "border-neutral-200"
          )}
        />
      </div>
      <div className="flex flex-col gap-1 max-h-[320px] overflow-y-auto">
        {filteredCategories.map(({ key, label, dot }) => {
          const isActive = replyCategoryFilters.includes(key);
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
            </button>
          );
        })}
      </div>
    </div>
  );
});

ReplyCategoryColumnFilter.displayName = 'ReplyCategoryColumnFilter';
