import { forwardRef, useImperativeHandle, useEffect } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useContactsFilter } from './ContactsFilterContext';
import { cn } from '../../lib/utils';
import { Check } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';

const GEOS = [
  { key: 'RU', label: 'Russia', flag: '🇷🇺' },
  { key: 'Global', label: 'Global', flag: '🌍' },
] as const;

export const GeoColumnFilter = forwardRef((props: IFilterParams, ref) => {
  const { geoFilter, setGeoFilter, filterOptions, resetPage } = useContactsFilter();
  const { isDark } = useTheme();

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

  useEffect(() => {
    props.filterChangedCallback();
  }, [geoFilter]);

  const handleSelect = (key: string) => {
    setGeoFilter(geoFilter === key ? null : key);
    resetPage();
  };

  const renderGeoButton = (key: string, label: string, flag?: string) => {
    const isActive = geoFilter === key;
    return (
      <button
        key={key}
        onClick={() => handleSelect(key)}
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
        {flag && <span>{flag}</span>}
        <span className="flex-1">{label}</span>
      </button>
    );
  };

  return (
    <div className={cn("p-3 min-w-[140px]", isDark && "bg-neutral-800")}>
      <div className="flex items-center justify-between mb-2">
        <span className={cn("text-xs font-medium", isDark ? "text-neutral-400" : "text-neutral-500")}>GEO</span>
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
        {GEOS.map(({ key, label, flag }) => renderGeoButton(key, label, flag))}
        {extraGeos.map((key) => renderGeoButton(key, key))}
      </div>
    </div>
  );
});

GeoColumnFilter.displayName = 'GeoColumnFilter';
