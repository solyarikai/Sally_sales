import { useMemo } from 'react';
import { Mail, Linkedin } from 'lucide-react';
import { cn } from '../lib/utils';

// ── Campaign sidebar data ──────────────────────────────────────────
export interface CampaignEntry {
  name: string;
  channel: 'email' | 'linkedin';
  count: number;
}

interface Activity {
  direction: 'inbound' | 'outbound';
  content: string;
  timestamp: string;
  channel?: 'email' | 'linkedin';
  campaign?: string;
  automation?: string;
}

export function buildCampaignList(activities: Activity[]): { email: CampaignEntry[]; linkedin: CampaignEntry[] } {
  const map = new Map<string, CampaignEntry>();
  for (const a of activities) {
    const name = a.campaign || a.automation || 'Unknown';
    const channel = a.channel || 'email';
    const key = `${channel}::${name}`;
    const entry = map.get(key);
    if (entry) {
      entry.count++;
    } else {
      map.set(key, { name, channel: channel as 'email' | 'linkedin', count: 1 });
    }
  }
  const email: CampaignEntry[] = [];
  const linkedin: CampaignEntry[] = [];
  for (const entry of map.values()) {
    if (entry.channel === 'linkedin') linkedin.push(entry);
    else email.push(entry);
  }
  email.sort((a, b) => b.count - a.count);
  linkedin.sort((a, b) => b.count - a.count);
  return { email, linkedin };
}

// ── Campaign sidebar component ─────────────────────────────────────
export function CampaignSidebar({
  activities,
  selectedCampaign,
  onSelect,
  isDark = false,
}: {
  activities: Activity[];
  selectedCampaign: string | null; // null = All
  onSelect: (campaign: string | null) => void;
  isDark?: boolean;
}) {
  const { email, linkedin } = useMemo(() => buildCampaignList(activities), [activities]);
  const totalCount = activities.length;
  const emailCount = activities.filter(a => (a.channel || 'email') === 'email').length;
  const linkedinCount = activities.filter(a => a.channel === 'linkedin').length;

  const containerCls = isDark
    ? 'w-[180px] flex-shrink-0 border-r border-[#333] overflow-y-auto bg-[#252526]'
    : 'w-[180px] flex-shrink-0 border-r border-gray-100 overflow-y-auto bg-gray-50/30';

  const allBtnCls = (active: boolean) =>
    isDark
      ? cn(
          'w-full text-left px-2.5 py-2 rounded-lg text-[12px] font-semibold transition-colors mb-1',
          active ? 'bg-[#37373d] text-[#d4d4d4]' : 'text-[#969696] hover:bg-[#2d2d2d]'
        )
      : cn(
          'w-full text-left px-2.5 py-2 rounded-lg text-[12px] font-semibold transition-colors mb-1',
          active ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
        );

  const sectionLabelCls = isDark
    ? 'flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-[#6e6e6e]'
    : 'flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400';

  const campaignBtnCls = (active: boolean) =>
    isDark
      ? cn(
          'w-full text-left px-2.5 py-1.5 rounded-lg text-[11px] transition-colors flex items-center gap-1.5',
          active ? 'bg-[#37373d] text-[#d4d4d4] font-medium' : 'text-[#858585] hover:bg-[#2d2d2d]'
        )
      : cn(
          'w-full text-left px-2.5 py-1.5 rounded-lg text-[11px] transition-colors flex items-center gap-1.5',
          active ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-500 hover:bg-gray-100'
        );

  const countCls = isDark ? 'text-[10px] text-[#6e6e6e] flex-shrink-0' : 'text-[10px] text-gray-400 flex-shrink-0';
  const mutedCountCls = isDark ? 'ml-auto font-normal text-[#6e6e6e]' : 'ml-auto font-normal';
  const emptyCls = isDark ? 'text-[11px] text-[#4e4e4e] px-2.5 py-4 text-center' : 'text-[11px] text-gray-300 px-2.5 py-4 text-center';

  return (
    <div className={containerCls}>
      <div className="p-2">
        {/* All */}
        <button onClick={() => onSelect(null)} className={allBtnCls(selectedCampaign === null)}>
          All
          <span className={cn('ml-1 text-[10px] font-normal', isDark ? 'text-[#6e6e6e]' : 'text-gray-400')}>
            ({totalCount})
          </span>
        </button>

        {/* Email section */}
        {emailCount > 0 && (
          <div className="mt-2">
            <div className={sectionLabelCls}>
              <Mail className="w-3 h-3" />
              Email
              <span className={mutedCountCls}>({emailCount})</span>
            </div>
            {email.map((c) => (
              <button
                key={`email-${c.name}`}
                onClick={() => onSelect(`email::${c.name}`)}
                className={campaignBtnCls(selectedCampaign === `email::${c.name}`)}
              >
                <span className="truncate flex-1">{c.name}</span>
                <span className={countCls}>{c.count}</span>
              </button>
            ))}
          </div>
        )}

        {/* LinkedIn section */}
        {linkedinCount > 0 && (
          <div className="mt-2">
            <div className={sectionLabelCls}>
              <Linkedin className="w-3 h-3" />
              LinkedIn
              <span className={mutedCountCls}>({linkedinCount})</span>
            </div>
            {linkedin.map((c) => (
              <button
                key={`linkedin-${c.name}`}
                onClick={() => onSelect(`linkedin::${c.name}`)}
                className={campaignBtnCls(selectedCampaign === `linkedin::${c.name}`)}
              >
                <span className="truncate flex-1">{c.name}</span>
                <span className={countCls}>{c.count}</span>
              </button>
            ))}
          </div>
        )}

        {totalCount === 0 && <p className={emptyCls}>No messages</p>}
      </div>
    </div>
  );
}
