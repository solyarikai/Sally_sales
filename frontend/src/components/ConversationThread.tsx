import { useEffect, useRef, useMemo } from 'react';
import { Linkedin, Mail, MessageSquare, RefreshCw } from 'lucide-react';
import { cn } from '../lib/utils';
import { stripHtml } from '../lib/htmlUtils';

/* ---------- Shared message type ---------- */
export interface ThreadMessage {
  direction: 'inbound' | 'outbound';
  channel: 'email' | 'linkedin';
  body: string;
  subject?: string | null;
  timestamp: string;
  campaign?: string | null;
  source?: string;
}

/* ---------- Component props ---------- */
interface ConversationThreadProps {
  messages: ThreadMessage[];
  contactName?: string;
  showCampaignSidebar?: boolean;
  showDateSeparators?: boolean;
  showCampaignMarkers?: boolean;
  showAvatars?: boolean;
  compact?: boolean;
  isDark?: boolean;
  filterCampaign?: string | null;
  loading?: boolean;
}

/* ---------- Render items ---------- */
type RenderItem =
  | { kind: 'date'; label: string; key: string }
  | { kind: 'campaign'; label: string; channel?: string; key: string }
  | { kind: 'message'; msg: ThreadMessage; showTail: boolean; key: string };

/* ---------- Component ---------- */
export function ConversationThread({
  messages,
  contactName = 'Contact',
  showDateSeparators = false,
  showCampaignMarkers = false,
  showAvatars = false,
  compact = false,
  isDark = false,
  filterCampaign = null,
  loading = false,
}: ConversationThreadProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Filter by campaign if provided
  const filtered = useMemo(() => {
    if (!filterCampaign) return messages;
    const [channel, ...nameParts] = filterCampaign.split('::');
    const name = nameParts.join('::');
    const genericNames = new Set(['unknown', 'linkedin', 'email', '']);
    return messages.filter((m) => {
      const mChannel = m.channel || 'email';
      const mName = m.campaign || 'Unknown';
      if (mChannel !== channel) return false;
      if (mName === name) return true;
      return genericNames.has(mName.toLowerCase());
    });
  }, [messages, filterCampaign]);

  // Sort chronologically (oldest first)
  const sorted = useMemo(
    () => [...filtered].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()),
    [filtered]
  );

  // Scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [sorted]);

  /* -- Loading state -- */
  if (loading) {
    if (isDark) {
      return (
        <div className="flex items-center gap-1.5 py-1.5 text-[11px]" style={{ color: '#6e6e6e' }}>
          <RefreshCw className="w-3 h-3 animate-spin" /> Loading...
        </div>
      );
    }
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400">
        <RefreshCw className="w-4 h-4 animate-spin" />
      </div>
    );
  }

  /* -- Empty state -- */
  if (sorted.length === 0) {
    if (isDark) {
      return <div className="text-[11px] py-1" style={{ color: '#4e4e4e' }}>No history</div>;
    }
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400">
        <div className="text-center">
          <MessageSquare className="w-10 h-10 mx-auto mb-2 opacity-20" />
          <p className="text-sm">No messages yet</p>
        </div>
      </div>
    );
  }

  /* -- Build render items -- */
  const items: RenderItem[] = [];
  let prevDate = '';
  let prevCampaign = '';
  let prevDirection = '';

  for (let i = 0; i < sorted.length; i++) {
    const msg = sorted[i];
    const dateStr = new Date(msg.timestamp).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });

    if (showDateSeparators && dateStr !== prevDate) {
      items.push({ kind: 'date', label: dateStr, key: `date-${i}` });
      prevDate = dateStr;
      prevCampaign = '';
    }

    if (showCampaignMarkers) {
      const campaignLabel = msg.campaign || '';
      if (campaignLabel && campaignLabel !== prevCampaign) {
        items.push({
          kind: 'campaign',
          label: campaignLabel,
          channel: msg.channel,
          key: `campaign-${i}`,
        });
        prevCampaign = campaignLabel;
      }
    }

    const showTail = msg.direction !== prevDirection;
    prevDirection = msg.direction;
    items.push({ kind: 'message', msg, showTail, key: `msg-${i}` });
  }

  /* -- Dark compact mode (Replies page thread) -- */
  if (isDark && compact) {
    return (
      <div ref={scrollRef} className="space-y-1.5">
        {items.map((item) => {
          if (item.kind === 'date') {
            return (
              <div key={item.key} className="flex justify-center my-2">
                <span className="px-2 py-0.5 rounded-full text-[10px]" style={{ background: '#2d2d2d', color: '#858585' }}>
                  {item.label}
                </span>
              </div>
            );
          }
          if (item.kind === 'campaign') {
            return (
              <div key={item.key} className="flex justify-center my-1.5">
                <span className="px-2 py-0.5 rounded-full text-[10px] inline-flex items-center gap-1" style={{ background: '#2d2d2d', color: '#858585' }}>
                  {item.channel === 'linkedin' ? <Linkedin className="w-2.5 h-2.5" /> : <Mail className="w-2.5 h-2.5" />}
                  {item.label}
                </span>
              </div>
            );
          }

          const { msg } = item;
          const cleaned = stripHtml(msg.body || '');
          if (!cleaned || cleaned === '(no content)') return null;
          const isInbound = msg.direction === 'inbound';
          return (
            <div key={item.key} className={cn("flex flex-col", isInbound ? "items-start" : "items-end")}>
              <div className="text-[10px] font-medium mb-0.5 px-1" style={{ color: '#6e6e6e' }}>
                {isInbound ? 'Lead' : 'Operator'}
              </div>
              <div
                className="max-w-[85%] rounded px-3 py-2 text-[13px]"
                style={{
                  background: isInbound ? '#2d2d2d' : '#37373d',
                  color: isInbound ? '#b0b0b0' : '#969696',
                }}
              >
                <div className="whitespace-pre-wrap leading-relaxed">{cleaned}</div>
                <div className="text-[10px] mt-1" style={{ color: '#4e4e4e' }}>
                  {msg.timestamp ? new Date(msg.timestamp).toLocaleString() : ''}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  /* -- Light mode / full mode (CRM modal) -- */
  const bubbleSize = compact ? 'text-[13px]' : 'text-sm';
  const timeSize = compact ? 'text-[10px]' : 'text-[11px]';

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3">
      <div className="flex flex-col gap-0.5">
        {items.map((item) => {
          if (item.kind === 'date') {
            return (
              <div key={item.key} className="flex justify-center my-3">
                <span className="px-3 py-0.5 rounded-full bg-gray-100 text-[11px] font-medium text-gray-500">
                  {item.label}
                </span>
              </div>
            );
          }

          if (item.kind === 'campaign') {
            return (
              <div key={item.key} className="flex justify-center my-2">
                <span className={cn(
                  "px-2.5 py-0.5 rounded-full text-[10px] font-medium inline-flex items-center gap-1",
                  item.channel === 'linkedin'
                    ? "bg-blue-50 text-blue-500"
                    : "bg-purple-50 text-purple-500"
                )}>
                  {item.channel === 'linkedin' ? <Linkedin className="w-2.5 h-2.5" /> : <Mail className="w-2.5 h-2.5" />}
                  {item.label}
                </span>
              </div>
            );
          }

          const { msg, showTail } = item;
          const isOut = msg.direction === 'outbound';
          const time = new Date(msg.timestamp).toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
          });

          return (
            <div
              key={item.key}
              className={cn(
                "flex",
                isOut ? "justify-end" : "justify-start",
                showTail ? "mt-2" : "mt-px"
              )}
            >
              {/* Inbound avatar */}
              {showAvatars && !isOut && (
                <div className="w-7 flex-shrink-0 mt-auto mb-0.5 mr-1.5">
                  {showTail ? (
                    <div className="w-7 h-7 rounded-full bg-gray-200 flex items-center justify-center text-[10px] font-semibold text-gray-600">
                      {contactName.charAt(0).toUpperCase()}
                    </div>
                  ) : null}
                </div>
              )}

              <div
                className={cn(
                  "max-w-[75%] px-3 py-2 relative",
                  bubbleSize,
                  isOut
                    ? "bg-[#3B82F6] text-white rounded-2xl rounded-br-md"
                    : "bg-[#F1F1F1] text-gray-900 rounded-2xl rounded-bl-md"
                )}
              >
                <p className="whitespace-pre-wrap break-words leading-relaxed">
                  {stripHtml(msg.body || '')}
                </p>
                <div className={cn(
                  "flex items-center gap-1.5 mt-1",
                  isOut ? "justify-end" : "justify-start"
                )}>
                  <span className={cn(timeSize, isOut ? "text-white/60" : "text-gray-400")}>
                    {time}
                  </span>
                </div>
              </div>

              {isOut && <div className="w-1 flex-shrink-0" />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ---------- Adapter: Reply thread messages → ThreadMessage[] ---------- */
export function adaptReplyThread(
  messages: Array<{ direction: string; body: string; activity_at?: string; channel?: string }>
): ThreadMessage[] {
  return messages.map((m) => ({
    direction: m.direction as 'inbound' | 'outbound',
    channel: (m.channel || 'email') as 'email' | 'linkedin',
    body: m.body || '',
    timestamp: m.activity_at || '',
  }));
}

/* ---------- Adapter: Contact history activities → ThreadMessage[] ---------- */
export function adaptContactHistory(
  activities: Array<{
    direction: 'inbound' | 'outbound';
    content: string;
    timestamp: string;
    channel?: 'email' | 'linkedin';
    campaign?: string;
    automation?: string;
  }>
): ThreadMessage[] {
  return activities.map((a) => ({
    direction: a.direction,
    channel: (a.channel || 'email') as 'email' | 'linkedin',
    body: a.content || '',
    timestamp: a.timestamp,
    campaign: a.campaign || a.automation || null,
  }));
}
