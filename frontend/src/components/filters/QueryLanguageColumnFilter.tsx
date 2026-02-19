import { forwardRef, useImperativeHandle, useEffect } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useQueryDashboardFilter } from './QueryDashboardFilterContext';
import { cn } from '../../lib/utils';
import { Check } from 'lucide-react';

const LANGUAGES = [
  { key: 'ru', label: 'Russian' },
  { key: 'en', label: 'English' },
] as const;

export const QueryLanguageColumnFilter = forwardRef((props: IFilterParams, ref) => {
  const { languageFilters, toggleLanguage, setLanguageFilters, filterOptions, resetPage } = useQueryDashboardFilter();

  useImperativeHandle(ref, () => ({
    isFilterActive: () => languageFilters.length > 0,
    getModel: () => (languageFilters.length > 0 ? { values: languageFilters } : null),
    setModel: (model: { values: string[] } | null) => { setLanguageFilters(model?.values || []); },
    doesFilterPass: () => true,
  }));

  useEffect(() => { props.filterChangedCallback(); }, [languageFilters]);

  const available = new Set(filterOptions?.languages || []);

  // Include both static + any dynamic languages from API
  const allLangs: Array<{ key: string; label: string }> = [...LANGUAGES.filter(l => available.has(l.key))];
  const extraLangs = (filterOptions?.languages || []).filter(l => !LANGUAGES.some(s => s.key === l));
  extraLangs.forEach(l => allLangs.push({ key: l, label: l.toUpperCase() }));

  return (
    <div className="p-3 min-w-[160px]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-neutral-500">LANGUAGE</span>
        {languageFilters.length > 0 && (
          <button onClick={() => { setLanguageFilters([]); resetPage(); }} className="text-[10px] text-red-500 hover:text-red-700">Clear</button>
        )}
      </div>
      <div className="flex flex-col gap-1">
        {allLangs.map(({ key, label }) => {
          const isActive = languageFilters.includes(key);
          return (
            <button key={key} onClick={() => { toggleLanguage(key); resetPage(); }}
              className={cn("flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                isActive ? "bg-blue-100 text-blue-700 border-blue-300" : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400")}>
              <span className={cn("w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                isActive ? "bg-indigo-500 border-indigo-500" : "border-neutral-300")}>
                {isActive && <Check className="w-2.5 h-2.5 text-white" />}
              </span>
              <span className="flex-1">{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
});
QueryLanguageColumnFilter.displayName = 'QueryLanguageColumnFilter';
