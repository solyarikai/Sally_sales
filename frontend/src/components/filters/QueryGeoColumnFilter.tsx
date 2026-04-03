import { forwardRef, useImperativeHandle, useState, useMemo, useEffect } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useQueryDashboardFilter } from './QueryDashboardFilterContext';
import { cn } from '../../lib/utils';
import { Search, Check, X } from 'lucide-react';

export const QueryGeoColumnFilter = forwardRef((props: IFilterParams, ref) => {
  const { geoFilters, toggleGeo, setGeoFilters, filterOptions, geoHierarchy, resetPage } = useQueryDashboardFilter();
  const [query, setQuery] = useState('');

  useImperativeHandle(ref, () => ({
    isFilterActive: () => geoFilters.length > 0,
    getModel: () => (geoFilters.length > 0 ? { values: geoFilters } : null),
    setModel: (model: { values: string[] } | null) => { setGeoFilters(model?.values || []); },
    doesFilterPass: () => true,
  }));

  useEffect(() => { props.filterChangedCallback?.(); }, [geoFilters]);

  const geos = filterOptions?.geos || [];

  // Build grouped list from hierarchy, filtered to only geos that exist in data
  const grouped = useMemo(() => {
    const geoSet = new Set(geos);
    if (!geoHierarchy) {
      // Flat list fallback
      return [{ country: 'All', items: geos }];
    }
    const groups: { country: string; items: string[] }[] = [];
    for (const cg of geoHierarchy.countries) {
      const items = cg.geos.map(g => g.key).filter(k => geoSet.has(k));
      if (items.length > 0) groups.push({ country: cg.country, items });
    }
    // Add any ungrouped geos
    const grouped_keys = new Set(groups.flatMap(g => g.items));
    const ungrouped = geos.filter(g => !grouped_keys.has(g));
    if (ungrouped.length > 0) groups.push({ country: 'Other', items: ungrouped });
    return groups;
  }, [geos, geoHierarchy]);

  const filteredGroups = useMemo(() => {
    if (!query.trim()) return grouped;
    const q = query.toLowerCase();
    return grouped
      .map(g => ({
        ...g,
        items: g.items.filter(item =>
          item.toLowerCase().includes(q) || g.country.toLowerCase().includes(q)
        ),
      }))
      .filter(g => g.items.length > 0);
  }, [grouped, query]);

  const handleToggle = (geo: string) => { toggleGeo(geo); resetPage(); };
  const clearAll = () => { setGeoFilters([]); resetPage(); setQuery(''); };

  return (
    <div className="p-3 min-w-[220px] max-w-[300px]">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-neutral-500">GEO</span>
        {geoFilters.length > 0 && (
          <button onClick={clearAll} className="text-[10px] text-red-500 hover:text-red-700">Clear all ({geoFilters.length})</button>
        )}
      </div>
      {geoFilters.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {geoFilters.map(geo => (
            <div key={geo} className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-emerald-50 border border-emerald-200 text-[10px] text-emerald-700 max-w-[140px]">
              <span className="truncate">{geo.replace(/_/g, ' ')}</span>
              <button onClick={() => handleToggle(geo)} className="text-emerald-400 hover:text-emerald-700 shrink-0"><X className="w-2.5 h-2.5" /></button>
            </div>
          ))}
        </div>
      )}
      {geos.length > 5 && (
        <div className="relative mb-2">
          <Search className="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-neutral-400" />
          <input type="text" placeholder="Search geos..." value={query} onChange={(e) => setQuery(e.target.value)}
            className="w-full pl-7 pr-2 py-1.5 rounded-md border border-neutral-200 text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500" />
        </div>
      )}
      <div className="flex flex-col gap-0.5 max-h-[280px] overflow-y-auto">
        {filteredGroups.length === 0 ? (
          <div className="text-xs text-neutral-400 px-2 py-3 text-center">{query ? 'No geos match' : 'No geos'}</div>
        ) : filteredGroups.map((group) => (
          <div key={group.country}>
            <div className="text-[10px] font-semibold text-neutral-400 uppercase tracking-wider px-2.5 pt-2 pb-1">{group.country}</div>
            {group.items.map((geo) => {
              const isActive = geoFilters.includes(geo);
              return (
                <button key={geo} onClick={() => handleToggle(geo)}
                  className={cn("flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all text-left w-full",
                    isActive ? "bg-emerald-100 text-emerald-700 border-emerald-300" : "bg-white text-neutral-600 border-neutral-200 hover:border-neutral-400")}>
                  <span className={cn("w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
                    isActive ? "bg-indigo-500 border-indigo-500" : "border-neutral-300")}>
                    {isActive && <Check className="w-2.5 h-2.5 text-white" />}
                  </span>
                  <span className="flex-1 truncate">{geo.replace(/_/g, ' ')}</span>
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
});
QueryGeoColumnFilter.displayName = 'QueryGeoColumnFilter';
