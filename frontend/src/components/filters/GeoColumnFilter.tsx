import { forwardRef, useImperativeHandle } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useContactsFilter } from './ContactsFilterContext';
import { cn } from '../../lib/utils';
import { Check } from 'lucide-react';

const GEOS = [
  { key: 'RU', label: 'Russia', flag: '🇷🇺' },
  { key: 'Global', label: 'Global', flag: '🌍' },
] as const;

export const GeoColumnFilter = forwardRef((_props: IFilterParams, ref) => {
  const { geoFilter, setGeoFilter, filterOptions, resetPage } = useContactsFilter();

  // Merge static GEOS with any dynamic ones from API
  const extraGeos = (filterOptions?.geos || []).filter(g => !GEOS.some(s => s.key === g));

  useImperativeHandle(ref, () => ({
    isFilterActive: () => !!geoFilter,
    getModel: () => (geoFilter ? { value: geoFilter } : null),
    setModel: (model: { value: string } | null) => {
      setGeoFilter(model?.value || null);
    },
    doesFilterPass: () => true,
  }));

  const handleSelect = (key: string) => {
    setGeoFilter(geoFilter === key ? null : key);
    resetPage();
  };

  return (
    <div className="p-3 min-w-[140px]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-neutral-500">GEO</span>
        {geoFilter && (
          <button
            onClick={() => { setGeoFilter(null); resetPage(); }}
            className="text-[10px] text-red-500 hover:text-red-700"
          >
            Clear
          </button>
        )}
      </div>
      <div className="flex flex-col gap-1">
        {GEOS.map(({ key, label, flag }) => {
          const isActive = geoFilter === key;
          return (
            <button
              key={key}
              onClick={() => handleSelect(key)}
              className={cn(
                "flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                isActive
                  ? "bg-indigo-100 text-indigo-700 border-indigo-300"
                  : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400"
              )}
            >
              <span className={cn(
                "w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                isActive ? "bg-indigo-500 border-indigo-500" : "border-neutral-300"
              )}>
                {isActive && <Check className="w-2.5 h-2.5 text-white" />}
              </span>
              <span>{flag}</span>
              <span className="flex-1">{label}</span>
            </button>
          );
        })}
        {extraGeos.map((key) => {
          const isActive = geoFilter === key;
          return (
            <button
              key={key}
              onClick={() => handleSelect(key)}
              className={cn(
                "flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left",
                isActive
                  ? "bg-indigo-100 text-indigo-700 border-indigo-300"
                  : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400"
              )}
            >
              <span className={cn(
                "w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                isActive ? "bg-indigo-500 border-indigo-500" : "border-neutral-300"
              )}>
                {isActive && <Check className="w-2.5 h-2.5 text-white" />}
              </span>
              <span className="flex-1">{key}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
});

GeoColumnFilter.displayName = 'GeoColumnFilter';
