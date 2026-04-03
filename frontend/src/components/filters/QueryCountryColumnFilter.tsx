import { forwardRef, useImperativeHandle, useState, useMemo, useEffect } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useQueryDashboardFilter } from './QueryDashboardFilterContext';
import { cn } from '../../lib/utils';
import { Search, Check, X } from 'lucide-react';

export const QueryCountryColumnFilter = forwardRef((props: IFilterParams, ref) => {
  const { countryFilters, toggleCountry, setCountryFilters, filterOptions, resetPage } = useQueryDashboardFilter();
  const [query, setQuery] = useState('');

  useImperativeHandle(ref, () => ({
    isFilterActive: () => countryFilters.length > 0,
    getModel: () => (countryFilters.length > 0 ? { values: countryFilters } : null),
    setModel: (model: { values: string[] } | null) => { setCountryFilters(model?.values || []); },
    doesFilterPass: () => true,
  }));

  useEffect(() => { props.filterChangedCallback?.(); }, [countryFilters]);

  const countries = filterOptions?.countries || [];
  const filtered = useMemo(() => {
    if (!query.trim()) return countries;
    const q = query.toLowerCase();
    return countries.filter(c => c.toLowerCase().includes(q));
  }, [countries, query]);

  const handleToggle = (country: string) => { toggleCountry(country); resetPage(); };
  const clearAll = () => { setCountryFilters([]); resetPage(); setQuery(''); };

  return (
    <div className="p-3 min-w-[200px] max-w-[280px]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-neutral-500">COUNTRY</span>
        {countryFilters.length > 0 && (
          <button onClick={clearAll} className="text-[10px] text-red-500 hover:text-red-700">Clear all ({countryFilters.length})</button>
        )}
      </div>
      {countryFilters.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {countryFilters.map(c => (
            <div key={c} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-violet-50 border border-violet-200 text-[10px] text-violet-700 max-w-[140px]">
              <span className="truncate">{c.replace(/_/g, ' ')}</span>
              <button onClick={() => handleToggle(c)} className="text-violet-400 hover:text-violet-700 shrink-0"><X className="w-2.5 h-2.5" /></button>
            </div>
          ))}
        </div>
      )}
      {countries.length > 5 && (
        <div className="relative mb-2">
          <Search className="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-neutral-400" />
          <input type="text" placeholder="Search countries..." value={query} onChange={(e) => setQuery(e.target.value)}
            className="w-full pl-7 pr-2 py-1.5 rounded-md border border-neutral-200 text-xs focus:outline-none focus:ring-1 focus:ring-violet-500" />
        </div>
      )}
      <div className="flex flex-col gap-1 max-h-[240px] overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="text-xs text-neutral-400 px-2 py-3 text-center">{query ? 'No countries match' : 'No countries'}</div>
        ) : filtered.map((country) => {
          const isActive = countryFilters.includes(country);
          return (
            <button key={country} onClick={() => handleToggle(country)}
              className={cn("flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                isActive ? "bg-violet-100 text-violet-700 border-violet-300" : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400")}>
              <span className={cn("w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                isActive ? "bg-violet-500 border-violet-500" : "border-neutral-300")}>
                {isActive && <Check className="w-2.5 h-2.5 text-white" />}
              </span>
              <span className="flex-1 truncate">{country.replace(/_/g, ' ')}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
});
QueryCountryColumnFilter.displayName = 'QueryCountryColumnFilter';
