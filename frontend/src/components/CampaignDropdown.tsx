import { useState, useMemo, useRef, useEffect } from 'react';
import { ChevronDown, Search, Linkedin, Mail } from 'lucide-react';
import { cn } from '../lib/utils';
import type { FullHistoryCampaign } from '../api/replies';

function timeAgoShort(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  if (days < 30) return `${Math.floor(days / 7)}w ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined });
}

const INITIAL_SHOW = 8;

export function CampaignDropdown({
  campaigns,
  selectedCampaign,
  onSelect,
  isDark = false,
}: {
  campaigns: FullHistoryCampaign[];
  selectedCampaign: string | null; // "channel::name" — F19: null no longer means "all"
  onSelect: (campaign: string | null) => void;
  isDark?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAll, setShowAll] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
        setSearchQuery('');
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [isOpen]);

  // Focus search on open
  useEffect(() => {
    if (isOpen) searchRef.current?.focus();
  }, [isOpen]);

  // Don't render if 0 campaigns
  if (campaigns.length === 0) return null;

  // Find selected campaign info for button label
  const selectedInfo = selectedCampaign
    ? campaigns.find(c => `${c.channel}::${c.campaign_name}` === selectedCampaign)
    : null;

  // Filter by search
  const filtered = useMemo(() => {
    if (!searchQuery) return campaigns;
    const q = searchQuery.toLowerCase();
    return campaigns.filter(c => c.campaign_name.toLowerCase().includes(q));
  }, [campaigns, searchQuery]);

  // Show limited or all
  const visible = showAll || searchQuery ? filtered : filtered.slice(0, INITIAL_SHOW);
  const hasMore = !showAll && !searchQuery && filtered.length > INITIAL_SHOW;

  // Theme tokens
  const bg = isDark ? '#252526' : '#fff';
  const border = isDark ? '#333' : '#e0e0e0';
  const hoverBg = isDark ? '#2d2d2d' : '#f5f5f5';
  const activeBg = isDark ? '#37373d' : '#eff6ff';
  const text1 = isDark ? '#d4d4d4' : '#1a1a1a';
  const text2 = isDark ? '#969696' : '#666';
  const text3 = isDark ? '#6e6e6e' : '#999';
  const inputBg = isDark ? '#3c3c3c' : '#f5f5f5';
  const badgeBg = isDark ? '#37373d' : '#e5e7eb';
  const badgeText = isDark ? '#969696' : '#6b7280';

  return (
    <div ref={dropdownRef} className="relative">
      {/* Trigger button — collapsed by default */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 px-2 py-1 rounded text-[11px] transition-colors"
        style={{ color: text2, background: isOpen ? hoverBg : 'transparent' }}
        onMouseEnter={e => { if (!isOpen) (e.currentTarget as HTMLElement).style.background = hoverBg; }}
        onMouseLeave={e => { if (!isOpen) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
      >
        {selectedInfo ? (
          <>
            {selectedInfo.channel === 'linkedin' ? <Linkedin className="w-3 h-3" /> : <Mail className="w-3 h-3" />}
            <span className="truncate max-w-[140px]">{selectedInfo.campaign_name}</span>
            <span style={{ color: text3 }}>({selectedInfo.message_count})</span>
          </>
        ) : (
          <span>Select campaign</span>
        )}
        {/* F20: Campaign count badge */}
        {campaigns.length > 1 && (
          <span
            className="ml-1 px-1.5 py-px rounded-full text-[10px]"
            style={{ background: badgeBg, color: badgeText }}
          >
            {campaigns.length} campaigns
          </span>
        )}
        <ChevronDown className={cn("w-3 h-3 transition-transform", isOpen && "rotate-180")} />
      </button>

      {/* Dropdown panel */}
      {isOpen && (
        <div
          className="absolute left-0 top-full mt-1 rounded-lg border shadow-lg z-50 min-w-[260px] max-w-[320px]"
          style={{ background: bg, borderColor: border }}
        >
          {/* Search */}
          {campaigns.length > 5 && (
            <div className="px-2 pt-2 pb-1">
              <div className="flex items-center gap-1.5 rounded px-2 py-1" style={{ background: inputBg }}>
                <Search className="w-3 h-3 flex-shrink-0" style={{ color: text3 }} />
                <input
                  ref={searchRef}
                  type="text"
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  placeholder="Search campaigns..."
                  className="flex-1 bg-transparent outline-none text-[11px]"
                  style={{ color: text1 }}
                />
              </div>
            </div>
          )}

          <div className="max-h-[280px] overflow-y-auto py-1">
            {/* Campaign list — F19: no "All campaigns" option */}
            {visible.map(c => {
              const key = `${c.channel}::${c.campaign_name}`;
              const isActive = selectedCampaign === key;
              return (
                <button
                  key={key}
                  onClick={() => { onSelect(key); setIsOpen(false); setSearchQuery(''); }}
                  className="w-full text-left px-3 py-1.5 text-[11px] flex items-center gap-2 transition-colors"
                  style={{
                    background: isActive ? activeBg : 'transparent',
                    color: isActive ? (isDark ? '#d4d4d4' : '#1d4ed8') : text1,
                    fontWeight: isActive ? 600 : 400,
                  }}
                  onMouseEnter={e => { if (!isActive) (e.currentTarget as HTMLElement).style.background = hoverBg; }}
                  onMouseLeave={e => { if (!isActive) (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
                >
                  {c.channel === 'linkedin' ? <Linkedin className="w-3 h-3 flex-shrink-0" /> : <Mail className="w-3 h-3 flex-shrink-0" />}
                  <span className="truncate flex-1">{c.campaign_name}</span>
                  <span className="flex items-center gap-1.5 flex-shrink-0" style={{ color: text3 }}>
                    <span>{c.message_count}</span>
                    <span className="text-[10px]">{c.latest_at ? timeAgoShort(c.latest_at) : ''}</span>
                  </span>
                </button>
              );
            })}

            {/* Load more */}
            {hasMore && (
              <button
                onClick={() => setShowAll(true)}
                className="w-full text-center py-1.5 text-[10px] font-medium transition-colors"
                style={{ color: isDark ? '#858585' : '#6b7280' }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = hoverBg; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent'; }}
              >
                Show {filtered.length - INITIAL_SHOW} more campaigns...
              </button>
            )}

            {filtered.length === 0 && searchQuery && (
              <div className="px-3 py-3 text-center text-[11px]" style={{ color: text3 }}>
                No campaigns match "{searchQuery}"
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
