import { forwardRef, useImperativeHandle, useState, useMemo, useEffect } from 'react';
import type { IFilterParams } from 'ag-grid-community';
import { useContactsFilter } from './ContactsFilterContext';
import { cn } from '../../lib/utils';
import { Search, X, Check } from 'lucide-react';
import { useTheme } from '../../hooks/useTheme';

/** Highlight matched substring in bold */
function HighlightMatch({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx < 0) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <strong className="font-semibold">{text.slice(idx, idx + query.length)}</strong>
      {text.slice(idx + query.length)}
    </>
  );
}

export const CampaignColumnFilter = forwardRef((props: IFilterParams, ref) => {
  const { campaignFilters, setCampaignFilters, toggleCampaign, campaigns, ensureCampaignsLoaded, resetPage, campaignIdFilter, setCampaignIdFilter } = useContactsFilter();
  const { isDark } = useTheme();
  const [query, setQuery] = useState('');

  // Lazy-load campaigns on first filter open
  useEffect(() => { ensureCampaignsLoaded(); }, []);

  useImperativeHandle(ref, () => ({
    isFilterActive: () => campaignFilters.length > 0 || !!campaignIdFilter,
    getModel: () => (campaignFilters.length > 0 || campaignIdFilter) ? { values: campaignFilters, ids: campaignIdFilter } : null,
    setModel: (model: { values: string[]; ids?: string | null } | null) => {
      setCampaignFilters(model?.values ?? []);
      if (model?.ids !== undefined) setCampaignIdFilter(model.ids ?? null);
    },
    doesFilterPass: () => true, // Server-side filtering
  }));

  useEffect(() => {
    props.filterChangedCallback();
  }, [campaignFilters, campaignIdFilter]);

  // Sort: prefix matches first, then includes
  const filtered = useMemo(() => {
    if (!query.trim()) return campaigns;
    const q = query.toLowerCase();
    const results = campaigns.filter(c => c.name.toLowerCase().includes(q));

    results.sort((a, b) => {
      const aPrefix = a.name.toLowerCase().startsWith(q) ? 0 : 1;
      const bPrefix = b.name.toLowerCase().startsWith(q) ? 0 : 1;
      if (aPrefix !== bPrefix) return aPrefix - bPrefix;
      return a.name.localeCompare(b.name);
    });

    return results;
  }, [campaigns, query]);

  // Group by source
  const emailCampaigns = filtered.filter(c => c.source === 'smartlead');
  const linkedinCampaigns = filtered.filter(c => c.source === 'getsales');

  const handleToggle = (name: string) => {
    toggleCampaign(name);
    resetPage();
  };

  const clearAll = () => {
    setCampaignFilters([]);
    setCampaignIdFilter(null);
    resetPage();
    setQuery('');
  };

  const renderCampaignRow = (c: { name: string; source: string }) => {
    const isActive = campaignFilters.includes(c.name);
    return (
      <button
        key={c.name}
        onClick={() => handleToggle(c.name)}
        className={cn(
          "flex items-center gap-2 w-full px-2 py-1.5 rounded text-xs text-left transition-colors",
          isActive
            ? (isDark ? "bg-indigo-900/40 text-indigo-300" : "bg-indigo-50 text-indigo-700")
            : (isDark ? "hover:bg-neutral-700 text-neutral-300" : "hover:bg-neutral-50 text-neutral-700")
        )}
      >
        <span className={cn(
          "w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0",
          isActive ? "bg-indigo-500 border-indigo-500" : (isDark ? "border-neutral-500" : "border-neutral-300")
        )}>
          {isActive && <Check className="w-2.5 h-2.5 text-white" />}
        </span>
        <span className="flex-1 truncate">
          <HighlightMatch text={c.name} query={query} />
        </span>
      </button>
    );
  };

  return (
    <div className={cn("p-3 min-w-[260px] max-w-[320px]", isDark && "bg-neutral-800")}>
      <div className="flex items-center justify-between mb-2">
        <span className={cn("text-xs font-medium", isDark ? "text-neutral-400" : "text-neutral-500")}>CAMPAIGN</span>
        {(campaignFilters.length > 0 || campaignIdFilter) && (
          <button onClick={clearAll} className="text-[10px] text-red-500 hover:text-red-700">
            Clear all {campaignFilters.length > 0 ? `(${campaignFilters.length})` : ''}
          </button>
        )}
      </div>

      {/* Campaign ID filter notice */}
      {campaignIdFilter && (
        <div className={cn(
          "flex items-center justify-between px-2 py-1.5 mb-2 rounded-lg border text-[11px]",
          isDark ? "bg-amber-900/30 border-amber-700 text-amber-300" : "bg-amber-50 border-amber-200 text-amber-700"
        )}>
          <span>Filtered by campaign IDs</span>
          <button onClick={() => { setCampaignIdFilter(null); resetPage(); }} className="text-amber-500 hover:text-amber-700">
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Selected campaign chips */}
      {campaignFilters.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {campaignFilters.map(name => (
            <div key={name} className={cn(
              "inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] max-w-[140px]",
              isDark ? "bg-indigo-900/40 border-indigo-700 text-indigo-300" : "bg-indigo-50 border-indigo-200 text-indigo-700"
            )}>
              <span className="truncate">{name}</span>
              <button onClick={() => handleToggle(name)} className={cn("shrink-0", isDark ? "text-indigo-400 hover:text-indigo-200" : "text-indigo-400 hover:text-indigo-700")}>
                <X className="w-2.5 h-2.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Search input */}
      <div className="relative mb-2">
        <Search className="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-neutral-400" />
        <input
          type="text"
          placeholder="Search campaigns..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className={cn(
            "w-full pl-7 pr-2 py-1.5 rounded-md border text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500",
            isDark ? "bg-neutral-700 border-neutral-600 text-neutral-200 placeholder-neutral-500" : "border-neutral-200"
          )}
        />
      </div>

      {/* Campaign list */}
      <div className="max-h-[240px] overflow-y-auto space-y-0.5">
        {emailCampaigns.length > 0 && (
          <>
            <div className={cn("text-[10px] font-medium uppercase px-1 pt-1", isDark ? "text-neutral-500" : "text-neutral-400")}>Email</div>
            {emailCampaigns.map(renderCampaignRow)}
          </>
        )}

        {linkedinCampaigns.length > 0 && (
          <>
            <div className={cn("text-[10px] font-medium uppercase px-1 pt-1", isDark ? "text-neutral-500" : "text-neutral-400")}>LinkedIn</div>
            {linkedinCampaigns.map(renderCampaignRow)}
          </>
        )}

        {filtered.length === 0 && (
          <div className={cn("text-xs px-2 py-3 text-center", isDark ? "text-neutral-500" : "text-neutral-400")}>No campaigns match</div>
        )}
      </div>
    </div>
  );
});

CampaignColumnFilter.displayName = 'CampaignColumnFilter';
