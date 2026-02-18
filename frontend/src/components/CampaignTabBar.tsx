import { useMemo } from 'react';
import { Linkedin, Mail } from 'lucide-react';
import { cn } from '../lib/utils';
import { buildCampaignList, type CampaignEntry } from './CampaignSidebar';

interface Activity {
  direction: 'inbound' | 'outbound';
  content: string;
  timestamp: string;
  channel?: 'email' | 'linkedin';
  campaign?: string;
  automation?: string;
}

export function CampaignTabBar({
  activities,
  selectedCampaign,
  onSelect,
  isDark = false,
}: {
  activities: Activity[];
  selectedCampaign: string | null;
  onSelect: (campaign: string | null) => void;
  isDark?: boolean;
}) {
  const { email, linkedin } = useMemo(() => buildCampaignList(activities), [activities]);
  const totalCount = activities.length;
  const allEntries: (CampaignEntry & { key: string })[] = useMemo(() => {
    const result: (CampaignEntry & { key: string })[] = [];
    for (const c of email) result.push({ ...c, key: `email::${c.name}` });
    for (const c of linkedin) result.push({ ...c, key: `linkedin::${c.name}` });
    return result;
  }, [email, linkedin]);

  // Don't render if only 1 campaign
  if (allEntries.length <= 1) return null;

  const pillCls = (active: boolean) =>
    isDark
      ? cn(
          'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] whitespace-nowrap transition-colors flex-shrink-0',
          active
            ? 'bg-[#37373d] text-[#d4d4d4] font-medium'
            : 'text-[#858585] hover:bg-[#2d2d2d]'
        )
      : cn(
          'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] whitespace-nowrap transition-colors flex-shrink-0',
          active
            ? 'bg-gray-200 text-gray-800 font-medium'
            : 'text-gray-500 hover:bg-gray-100'
        );

  const countStyle = isDark ? { color: '#6e6e6e' } : { color: '#999' };

  return (
    <div className="flex items-center gap-1 overflow-x-auto pb-1 scrollbar-hide" style={{ scrollbarWidth: 'none' }}>
      {/* All pill */}
      <button onClick={() => onSelect(null)} className={pillCls(selectedCampaign === null)}>
        All <span className="text-[10px]" style={countStyle}>({totalCount})</span>
      </button>

      {allEntries.map((entry) => (
        <button
          key={entry.key}
          onClick={() => onSelect(entry.key)}
          className={pillCls(selectedCampaign === entry.key)}
        >
          {entry.channel === 'linkedin'
            ? <Linkedin className="w-2.5 h-2.5" />
            : <Mail className="w-2.5 h-2.5" />
          }
          <span className="truncate max-w-[120px]">{entry.name}</span>
          <span className="text-[10px]" style={countStyle}>({entry.count})</span>
        </button>
      ))}
    </div>
  );
}
