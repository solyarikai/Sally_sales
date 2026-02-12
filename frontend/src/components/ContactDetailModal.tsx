import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { X, Mail, User, Building, MapPin, Linkedin, MessageSquare, Send, Clock, AlertTriangle, FolderPlus, ChevronLeft, ChevronRight, Loader2, SkipForward, Sparkles } from 'lucide-react';
import { cn } from '../lib/utils';
import type { Contact } from '../api/contacts';
import { contactsApi } from '../api/contacts';

interface Activity {
  id: number;
  type: string;
  content: string;
  timestamp: string;
  direction: 'inbound' | 'outbound';
  channel?: 'email' | 'linkedin';
  campaign?: string;
  automation?: string;
}

interface ContactDetailModalProps {
  contact: Contact | null;
  isOpen: boolean;
  onClose: () => void;
  // Reply mode props
  replyMode?: boolean;
  contactList?: Contact[];
  currentIndex?: number;
  onNavigate?: (index: number) => void;
  onMarkProcessed?: (contactId: number) => void;
}

// ── Campaign sidebar data ──────────────────────────────────────────
interface CampaignEntry {
  name: string;
  channel: 'email' | 'linkedin';
  count: number;
}

function buildCampaignList(activities: Activity[]): { email: CampaignEntry[]; linkedin: CampaignEntry[] } {
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
function CampaignSidebar({
  activities,
  selectedCampaign,
  onSelect,
}: {
  activities: Activity[];
  selectedCampaign: string | null; // null = All
  onSelect: (campaign: string | null) => void;
}) {
  const { email, linkedin } = useMemo(() => buildCampaignList(activities), [activities]);
  const totalCount = activities.length;
  const emailCount = activities.filter(a => (a.channel || 'email') === 'email').length;
  const linkedinCount = activities.filter(a => a.channel === 'linkedin').length;

  return (
    <div className="w-[180px] flex-shrink-0 border-r border-gray-100 overflow-y-auto bg-gray-50/30">
      <div className="p-2">
        {/* All */}
        <button
          onClick={() => onSelect(null)}
          className={cn(
            "w-full text-left px-2.5 py-2 rounded-lg text-[12px] font-semibold transition-colors mb-1",
            selectedCampaign === null
              ? "bg-blue-50 text-blue-700"
              : "text-gray-600 hover:bg-gray-100"
          )}
        >
          All
          <span className="ml-1 text-[10px] font-normal text-gray-400">({totalCount})</span>
        </button>

        {/* Email section */}
        {emailCount > 0 && (
          <div className="mt-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
              <Mail className="w-3 h-3" />
              Email
              <span className="ml-auto font-normal">({emailCount})</span>
            </div>
            {email.map((c) => (
              <button
                key={`email-${c.name}`}
                onClick={() => onSelect(`email::${c.name}`)}
                className={cn(
                  "w-full text-left px-2.5 py-1.5 rounded-lg text-[11px] transition-colors flex items-center gap-1.5",
                  selectedCampaign === `email::${c.name}`
                    ? "bg-blue-50 text-blue-700 font-medium"
                    : "text-gray-500 hover:bg-gray-100"
                )}
              >
                <span className="truncate flex-1">{c.name}</span>
                <span className="text-[10px] text-gray-400 flex-shrink-0">{c.count}</span>
              </button>
            ))}
          </div>
        )}

        {/* LinkedIn section */}
        {linkedinCount > 0 && (
          <div className="mt-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
              <Linkedin className="w-3 h-3" />
              LinkedIn
              <span className="ml-auto font-normal">({linkedinCount})</span>
            </div>
            {linkedin.map((c) => (
              <button
                key={`linkedin-${c.name}`}
                onClick={() => onSelect(`linkedin::${c.name}`)}
                className={cn(
                  "w-full text-left px-2.5 py-1.5 rounded-lg text-[11px] transition-colors flex items-center gap-1.5",
                  selectedCampaign === `linkedin::${c.name}`
                    ? "bg-blue-50 text-blue-700 font-medium"
                    : "text-gray-500 hover:bg-gray-100"
                )}
              >
                <span className="truncate flex-1">{c.name}</span>
                <span className="text-[10px] text-gray-400 flex-shrink-0">{c.count}</span>
              </button>
            ))}
          </div>
        )}

        {totalCount === 0 && (
          <p className="text-[11px] text-gray-300 px-2.5 py-4 text-center">No messages</p>
        )}
      </div>
    </div>
  );
}

// ── Messenger-style conversation view ──────────────────────────────
function ConversationView({
  activities,
  contactName,
  compact = false,
  filterCampaign = null,
}: {
  activities: Activity[];
  contactName: string;
  compact?: boolean;
  filterCampaign?: string | null; // "email::CampaignName" or "linkedin::CampaignName" or null (all)
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Filter activities by selected campaign
  const filtered = useMemo(() => {
    if (!filterCampaign) return activities;
    const [channel, ...nameParts] = filterCampaign.split('::');
    const name = nameParts.join('::');
    return activities.filter((a) => {
      const aChannel = a.channel || 'email';
      const aName = a.campaign || a.automation || 'Unknown';
      return aChannel === channel && aName === name;
    });
  }, [activities, filterCampaign]);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [filtered]);

  // Sort chronologically (oldest first, like a real chat)
  const sorted = [...filtered].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  if (sorted.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400">
        <div className="text-center">
          <MessageSquare className="w-10 h-10 mx-auto mb-2 opacity-20" />
          <p className="text-sm">No messages yet</p>
        </div>
      </div>
    );
  }

  // Group messages: insert date separators and campaign change markers
  type RenderItem =
    | { kind: 'date'; label: string; key: string }
    | { kind: 'campaign'; label: string; channel?: string; key: string }
    | { kind: 'message'; activity: Activity; showTail: boolean; key: string };

  const items: RenderItem[] = [];
  let prevDate = '';
  let prevCampaign = '';
  let prevDirection = '';

  for (let i = 0; i < sorted.length; i++) {
    const act = sorted[i];
    const dateStr = new Date(act.timestamp).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });

    // Date divider
    if (dateStr !== prevDate) {
      items.push({ kind: 'date', label: dateStr, key: `date-${i}` });
      prevDate = dateStr;
      prevCampaign = ''; // reset campaign on new date
    }

    // Campaign change divider
    const campaignLabel = act.campaign || act.automation || '';
    if (campaignLabel && campaignLabel !== prevCampaign) {
      items.push({
        kind: 'campaign',
        label: campaignLabel,
        channel: act.channel,
        key: `campaign-${i}`,
      });
      prevCampaign = campaignLabel;
    }

    // Show tail on first message of a direction group
    const showTail = act.direction !== prevDirection;
    prevDirection = act.direction;

    items.push({ kind: 'message', activity: act, showTail, key: `msg-${act.id}` });
  }

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
                  {item.channel === 'linkedin' ? (
                    <Linkedin className="w-2.5 h-2.5" />
                  ) : (
                    <Mail className="w-2.5 h-2.5" />
                  )}
                  {item.label}
                </span>
              </div>
            );
          }

          // Message bubble
          const { activity, showTail } = item;
          const isOut = activity.direction === 'outbound';
          const time = new Date(activity.timestamp).toLocaleTimeString('en-US', {
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
              {/* Inbound avatar (only on tail) */}
              {!isOut && (
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
                    ? cn(
                        "bg-[#3B82F6] text-white",
                        showTail
                          ? "rounded-2xl rounded-br-md"
                          : "rounded-2xl rounded-br-md"
                      )
                    : cn(
                        "bg-[#F1F1F1] text-gray-900",
                        showTail
                          ? "rounded-2xl rounded-bl-md"
                          : "rounded-2xl rounded-bl-md"
                      )
                )}
              >
                <p className="whitespace-pre-wrap break-words leading-relaxed">{activity.content}</p>
                <div className={cn(
                  "flex items-center gap-1.5 mt-1",
                  isOut ? "justify-end" : "justify-start"
                )}>
                  <span className={cn(
                    timeSize,
                    isOut ? "text-white/60" : "text-gray-400"
                  )}>
                    {time}
                  </span>
                </div>
              </div>

              {/* Spacer for outbound alignment */}
              {isOut && <div className="w-1 flex-shrink-0" />}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Compose area with auto-selected channel ────────────────────────
function ComposeArea({
  contact,
  replyChannel,
  setReplyChannel,
  draftReply,
  setDraftReply,
  savedDraft,
  setSavedDraft,
  isSaving,
  handleSaveDraft,
}: {
  contact: Contact;
  replyChannel: 'email' | 'linkedin' | null;
  setReplyChannel: (ch: 'email' | 'linkedin' | null) => void;
  draftReply: string;
  setDraftReply: (v: string) => void;
  savedDraft: boolean;
  setSavedDraft: (v: boolean) => void;
  isSaving: boolean;
  handleSaveDraft: () => void;
}) {
  // Auto-select channel on first render if not set
  useEffect(() => {
    if (replyChannel) return;
    if (contact.smartlead_id) {
      setReplyChannel('email');
    } else if (contact.getsales_id) {
      setReplyChannel('linkedin');
    }
  }, [contact.smartlead_id, contact.getsales_id, replyChannel, setReplyChannel]);

  const canEmail = !!contact.smartlead_id;
  const canLinkedin = !!contact.getsales_id;
  const channelLabel = replyChannel === 'email' ? 'Email' : 'LinkedIn';
  const viaLabel = replyChannel === 'email' ? 'via Smartlead' : 'via GetSales';

  // If no channel available at all
  if (!canEmail && !canLinkedin) {
    return (
      <div className="border-t border-gray-100 p-4 bg-white">
        <p className="text-[11px] text-gray-400 text-center">No reply channels available</p>
      </div>
    );
  }

  return (
    <div className="border-t border-gray-100 p-4 bg-white">
      <div className="flex items-center gap-2 mb-3 px-1">
        <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
        <p className="text-[11px] text-amber-600">Draft mode — replies are saved but NOT sent automatically</p>
      </div>

      <div className="flex items-center gap-2 mb-2">
        <span className={cn(
          "px-2 py-0.5 rounded-full text-[10px] font-medium",
          replyChannel === 'email' ? "bg-purple-50 text-purple-600" : "bg-blue-50 text-blue-600"
        )}>
          {channelLabel}
        </span>
        <span className="text-[10px] text-gray-400">{viaLabel}</span>
        {canEmail && canLinkedin && (
          <button
            onClick={() => setReplyChannel(replyChannel === 'email' ? 'linkedin' : 'email')}
            className="text-[10px] text-blue-500 hover:text-blue-700 transition-colors ml-1"
          >
            Switch
          </button>
        )}
      </div>

      <div className="flex gap-2">
        <textarea
          value={draftReply}
          onChange={(e) => { setDraftReply(e.target.value); setSavedDraft(false); }}
          placeholder={replyChannel === 'email' ? "Write your email reply..." : "Write your LinkedIn message..."}
          className="flex-1 p-3 border border-gray-200 rounded-xl resize-none text-sm focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-300 min-h-[60px] max-h-[120px]"
          autoFocus
          rows={2}
        />
        <button
          onClick={handleSaveDraft}
          disabled={!draftReply.trim() || isSaving}
          className={cn(
            "self-end p-2.5 rounded-xl transition-all",
            draftReply.trim()
              ? "bg-blue-500 text-white hover:bg-blue-600 shadow-sm"
              : "bg-gray-100 text-gray-400 cursor-not-allowed"
          )}
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
      {savedDraft && (
        <p className="mt-1.5 text-[10px] text-green-500 flex items-center gap-1">
          <CheckIcon className="w-3 h-3" /> Draft saved
        </p>
      )}
    </div>
  );
}

// ── Main Modal ─────────────────────────────────────────────────────
export function ContactDetailModal({
  contact, isOpen, onClose,
  replyMode = false, contactList = [], currentIndex = 0,
  onNavigate, onMarkProcessed,
}: ContactDetailModalProps) {
  const [activeTab, setActiveTab] = useState<'details' | 'conversation'>('details');
  const [activities, setActivities] = useState<Activity[]>([]);
  const [draftReply, setDraftReply] = useState('');
  const [replyChannel, setReplyChannel] = useState<'email' | 'linkedin' | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [savedDraft, setSavedDraft] = useState(false);
  const [projects, setProjects] = useState<Array<{id: number, name: string}>>([]);
  const [selectedProject, setSelectedProject] = useState<number | null>(null);
  const [isAddingToProject, setIsAddingToProject] = useState(false);
  const [addedToProject, setAddedToProject] = useState(false);
  const [selectedCampaign, setSelectedCampaign] = useState<string | null>(null);

  // AI draft state
  const [aiDraftLoading, setAiDraftLoading] = useState(false);
  const [, setAiDraftBody] = useState('');
  const [aiCategory, setAiCategory] = useState('');
  const [, setAiChannel] = useState<string | null>(null);

  // Fetch AI draft for reply mode
  const fetchAiDraft = useCallback(async (contactId: number) => {
    setAiDraftLoading(true);
    setAiDraftBody('');
    setAiCategory('');
    setAiChannel(null);
    try {
      const result = await contactsApi.generateReply(contactId);
      if (result.has_reply && result.draft_body) {
        setAiDraftBody(result.draft_body);
        setDraftReply(result.draft_body);
        setAiCategory(result.category || '');
        setAiChannel(result.channel || null);
        // Auto-set reply channel
        if (result.channel === 'email') setReplyChannel('email');
        else if (result.channel === 'linkedin') setReplyChannel('linkedin');
      }
    } catch (err) {
      console.error('Failed to fetch AI draft:', err);
    } finally {
      setAiDraftLoading(false);
    }
  }, []);

  useEffect(() => {
    if (contact && isOpen) {
      // Reset state when contact changes
      setDraftReply('');
      setReplyChannel(null);
      setSavedDraft(false);
      setActiveTab(replyMode ? 'conversation' : 'details');
      setSelectedProject(contact.project_id || null);
      setAddedToProject(false);
      setAiDraftBody('');
      setAiCategory('');
      setSelectedCampaign(null);

      // Fetch projects list
      const fetchProjects = async () => {
        try {
          const response = await fetch('/api/contacts/projects/names');
          if (response.ok) {
            const data = await response.json();
            setProjects(data);
          }
        } catch (err) {
          console.error('Failed to fetch projects:', err);
        }
      };
      fetchProjects();

      // Fetch activities/history from API
      const fetchHistory = async () => {
        try {
          const response = await fetch(`/api/contacts/${contact.id}/history`);
          if (response.ok) {
            const data = await response.json();
            const allActivities: Activity[] = [
              ...data.email_history.map((e: any, i: number) => ({
                id: e.id || i,
                type: e.type,
                content: e.body || e.snippet || '',
                timestamp: e.timestamp,
                direction: e.direction as 'inbound' | 'outbound',
                channel: (e.channel || 'email') as 'email' | 'linkedin',
                campaign: e.campaign,
              })),
              ...data.linkedin_history.map((l: any, i: number) => ({
                id: l.id || i + 1000,
                type: l.type,
                content: l.body || l.snippet || '',
                timestamp: l.timestamp,
                direction: l.direction as 'inbound' | 'outbound',
                channel: 'linkedin' as const,
                automation: l.automation,
              })),
            ];

            setActivities(allActivities);
          }
        } catch (err) {
          console.error('Failed to fetch history:', err);
        }
      };
      fetchHistory();

      // In reply mode, fetch AI draft
      if (replyMode && contact.has_replied) {
        fetchAiDraft(contact.id);
      }
    }
  }, [contact, isOpen, replyMode, fetchAiDraft]);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen || !replyMode) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft' && onNavigate && currentIndex > 0) {
        onNavigate(currentIndex - 1);
      } else if (e.key === 'ArrowRight' && onNavigate && currentIndex < contactList.length - 1) {
        onNavigate(currentIndex + 1);
      } else if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, replyMode, currentIndex, contactList.length, onNavigate, onClose]);

  if (!isOpen || !contact) return null;

  const contactFirstName = contact.first_name || 'Contact';

  const handleAddToProject = async () => {
    if (!selectedProject || !contact) return;
    setIsAddingToProject(true);
    try {
      const response = await fetch(`/api/contacts/${contact.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: selectedProject })
      });
      if (response.ok) setAddedToProject(true);
    } catch (err) {
      console.error('Failed to add to project:', err);
    }
    setIsAddingToProject(false);
  };

  const handleSaveDraft = async () => {
    if (!draftReply.trim()) return;
    setIsSaving(true);
    await new Promise(resolve => setTimeout(resolve, 500));
    setSavedDraft(true);
    setIsSaving(false);
    // In reply mode, mark as processed and go next
    if (replyMode && onMarkProcessed && contact) {
      onMarkProcessed(contact.id);
      // Auto-navigate to next
      if (onNavigate && currentIndex < contactList.length - 1) {
        setTimeout(() => onNavigate(currentIndex + 1), 300);
      }
    }
  };

  const handleSkip = () => {
    if (replyMode && onMarkProcessed && contact) {
      onMarkProcessed(contact.id);
      if (onNavigate && currentIndex < contactList.length - 1) {
        onNavigate(currentIndex + 1);
      }
    }
  };

  // ── Reply mode: 3-column split layout ─────────────────────────────
  if (replyMode) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
        <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-5xl h-[85vh] flex flex-col overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 bg-white/80 backdrop-blur-lg">
            <div className="flex items-center gap-2">
              <button
                onClick={() => onNavigate?.(currentIndex - 1)}
                disabled={currentIndex <= 0}
                className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-20 transition-colors"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-xs font-semibold">
                {contact.first_name?.[0]}{contact.last_name?.[0]}
              </div>
              <div className="ml-1">
                <h2 className="text-[15px] font-semibold text-gray-900 leading-tight">
                  {contact.first_name} {contact.last_name}
                </h2>
                <p className="text-[11px] text-gray-400 leading-tight">
                  {contact.email}
                  {contact.company_name ? ` · ${contact.company_name}` : ''}
                  {contact.job_title ? ` · ${contact.job_title}` : ''}
                </p>
              </div>
              <button
                onClick={() => onNavigate?.(currentIndex + 1)}
                disabled={currentIndex >= contactList.length - 1}
                className="p-1.5 rounded-lg hover:bg-gray-100 disabled:opacity-20 transition-colors ml-1"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
              <span className="text-[11px] text-gray-300 ml-1 tabular-nums">
                {currentIndex + 1}/{contactList.length}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {aiCategory && (
                <span className={cn(
                  "px-2 py-0.5 rounded-full text-[11px] font-medium",
                  aiCategory === 'interested' || aiCategory === 'meeting_request' ? "bg-green-50 text-green-600" :
                  aiCategory === 'not_interested' ? "bg-red-50 text-red-500" :
                  aiCategory === 'question' ? "bg-blue-50 text-blue-600" :
                  "bg-gray-100 text-gray-500"
                )}>
                  {aiCategory.replace(/_/g, ' ')}
                </span>
              )}
              <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors">
                <X className="w-4 h-4 text-gray-400" />
              </button>
            </div>
          </div>

          {/* 3-column split content */}
          <div className="flex-1 flex overflow-hidden">
            {/* Left: Campaign sidebar */}
            <CampaignSidebar
              activities={activities}
              selectedCampaign={selectedCampaign}
              onSelect={setSelectedCampaign}
            />

            {/* Center: Conversation (messenger view) */}
            <div className="flex-1 flex flex-col bg-white min-w-0">
              <ConversationView
                activities={activities}
                contactName={contactFirstName}
                compact
                filterCampaign={selectedCampaign}
              />
            </div>

            {/* Right: AI Draft + Reply */}
            <div className="w-[320px] flex flex-col border-l border-gray-100 bg-gray-50/50">
              {/* Contact summary */}
              <div className="px-4 py-3 border-b border-gray-100">
                <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                  <div>
                    <span className="text-gray-400 text-[10px] uppercase tracking-wider">Status</span>
                    <div className="font-medium text-gray-700">{contact.status || '—'}</div>
                  </div>
                  <div>
                    <span className="text-gray-400 text-[10px] uppercase tracking-wider">Source</span>
                    <div className="font-medium text-gray-700">{contact.source || '—'}</div>
                  </div>
                  {contact.campaigns && contact.campaigns.length > 0 && (
                    <div className="col-span-2 mt-1">
                      <span className="text-gray-400 text-[10px] uppercase tracking-wider">Campaigns</span>
                      <div className="font-medium text-gray-700 text-[11px] line-clamp-2">{contact.campaigns.map(c => c.name).join(', ')}</div>
                    </div>
                  )}
                </div>
              </div>

              {/* AI Draft */}
              <div className="flex-1 px-4 py-3 flex flex-col min-h-0">
                <div className="flex items-center gap-1.5 mb-3">
                  <Sparkles className="w-3.5 h-3.5 text-purple-500" />
                  <span className="text-xs font-semibold text-gray-700">AI Suggested Reply</span>
                </div>

                {aiDraftLoading ? (
                  <div className="flex items-center gap-2 text-xs text-gray-400 py-4">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Generating draft...
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col min-h-0">
                    {/* Channel selector */}
                    {replyChannel && (
                      <div className="flex items-center gap-2 mb-2">
                        <span className={cn(
                          "px-2 py-0.5 rounded-full text-[10px] font-medium",
                          replyChannel === 'email' ? "bg-purple-50 text-purple-600" : "bg-blue-50 text-blue-600"
                        )}>
                          {replyChannel === 'email' ? 'Email' : 'LinkedIn'}
                        </span>
                        <button
                          onClick={() => setReplyChannel(replyChannel === 'email' ? 'linkedin' : 'email')}
                          className="text-[10px] text-gray-400 hover:text-gray-600 transition-colors"
                        >
                          Switch
                        </button>
                      </div>
                    )}

                    <textarea
                      value={draftReply}
                      onChange={(e) => { setDraftReply(e.target.value); setSavedDraft(false); }}
                      placeholder="Write your reply..."
                      className="flex-1 w-full p-3 border border-gray-200 rounded-xl resize-none text-[13px] focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-300 min-h-[100px] bg-white transition-all"
                    />

                    <div className="flex items-center justify-between mt-3 gap-2">
                      <button
                        onClick={handleSkip}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-[11px] font-medium text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                      >
                        <SkipForward className="w-3 h-3" />
                        Skip
                      </button>

                      <button
                        onClick={handleSaveDraft}
                        disabled={!draftReply.trim() || isSaving}
                        className={cn(
                          "inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-[11px] font-semibold transition-all",
                          draftReply.trim()
                            ? "bg-blue-500 text-white hover:bg-blue-600 shadow-sm"
                            : "bg-gray-100 text-gray-400 cursor-not-allowed"
                        )}
                      >
                        <Send className="w-3 h-3" />
                        {isSaving ? 'Saving...' : savedDraft ? 'Saved' : 'Save & Next'}
                      </button>
                    </div>

                    {savedDraft && (
                      <div className="mt-2 text-[10px] text-green-500 flex items-center gap-1">
                        <CheckIcon className="w-3 h-3" /> Draft saved
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ── Normal mode: 2-column (sidebar + conversation) ────────────────
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-4xl h-[85vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div className="flex items-center gap-4">
            <div className="w-11 h-11 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-base font-semibold">
              {contact.first_name?.[0]}{contact.last_name?.[0]}
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                {contact.first_name} {contact.last_name}
              </h2>
              <p className="text-sm text-gray-400">{contact.email}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-100 px-6">
          <button
            onClick={() => setActiveTab('details')}
            className={cn(
              "px-4 py-3 text-sm font-medium border-b-2 transition-colors",
              activeTab === 'details'
                ? "border-blue-500 text-blue-600"
                : "border-transparent text-gray-400 hover:text-gray-600"
            )}
          >
            <User className="w-4 h-4 inline mr-1.5" />
            Details
          </button>
          <button
            onClick={() => setActiveTab('conversation')}
            className={cn(
              "px-4 py-3 text-sm font-medium border-b-2 transition-colors",
              activeTab === 'conversation'
                ? "border-blue-500 text-blue-600"
                : "border-transparent text-gray-400 hover:text-gray-600"
            )}
          >
            <MessageSquare className="w-4 h-4 inline mr-1.5" />
            Conversation
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {activeTab === 'details' && (
            <div className="flex-1 overflow-auto p-6">
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h3 className="font-semibold text-gray-900">Contact Information</h3>
                  <div className="space-y-3">
                    <div className="flex items-center gap-3">
                      <Mail className="w-4 h-4 text-gray-400" />
                      <a href={`mailto:${contact.email}`} className="text-blue-600 hover:underline">{contact.email}</a>
                    </div>
                    {contact.company_name && (
                      <div className="flex items-center gap-3">
                        <Building className="w-4 h-4 text-gray-400" />
                        <span>{contact.company_name}</span>
                      </div>
                    )}
                    {contact.job_title && (
                      <div className="flex items-center gap-3">
                        <User className="w-4 h-4 text-gray-400" />
                        <span>{contact.job_title}</span>
                      </div>
                    )}
                    {contact.location && (
                      <div className="flex items-center gap-3">
                        <MapPin className="w-4 h-4 text-gray-400" />
                        <span>{contact.location}</span>
                      </div>
                    )}
                    {contact.linkedin_url && (
                      <div className="flex items-center gap-3">
                        <Linkedin className="w-4 h-4 text-gray-400" />
                        <a href={`https://${contact.linkedin_url}`} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                          View LinkedIn Profile
                        </a>
                      </div>
                    )}
                  </div>
                </div>

                <div className="space-y-4">
                  <h3 className="font-semibold text-gray-900">Status</h3>
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-500">Source:</span>
                      <span className={cn(
                        "px-2 py-1 rounded-full text-xs font-medium",
                        contact.source === 'smartlead' ? "bg-purple-50 text-purple-600" :
                        contact.source === 'getsales' ? "bg-blue-50 text-blue-600" :
                        "bg-gray-100 text-gray-600"
                      )}>
                        {contact.source}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-500">Status:</span>
                      <span className="px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">{contact.status}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-500">Has Replied:</span>
                      <span className={cn("px-2 py-1 rounded-full text-xs font-medium", contact.has_replied ? "bg-green-50 text-green-600" : "bg-gray-100 text-gray-600")}>
                        {contact.has_replied ? 'Yes' : 'No'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4 text-gray-400" />
                      <span className="text-sm text-gray-500">Added {new Date(contact.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  {contact.notes && (
                    <div className="mt-4">
                      <h4 className="text-sm font-medium text-gray-700 mb-2">Notes</h4>
                      <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded-xl">{contact.notes}</p>
                    </div>
                  )}
                  <div className="mt-6 p-4 bg-gray-50 rounded-xl border border-gray-100">
                    <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                      <FolderPlus className="w-4 h-4 text-blue-500" />
                      Add to Project
                    </h4>
                    <div className="flex items-center gap-3">
                      <select
                        value={selectedProject || ''}
                        onChange={(e) => setSelectedProject(e.target.value ? Number(e.target.value) : null)}
                        className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-300"
                      >
                        <option value="">Select a project...</option>
                        {projects.map((project) => (
                          <option key={project.id} value={project.id}>{project.name}</option>
                        ))}
                      </select>
                      <button
                        onClick={handleAddToProject}
                        disabled={!selectedProject || isAddingToProject}
                        className={cn(
                          "px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-all",
                          selectedProject && !isAddingToProject
                            ? "bg-blue-500 text-white hover:bg-blue-600 shadow-sm"
                            : "bg-gray-100 text-gray-400 cursor-not-allowed"
                        )}
                      >
                        {isAddingToProject ? 'Adding...' : addedToProject ? 'Added!' : 'Add'}
                      </button>
                    </div>
                    {addedToProject && (
                      <p className="mt-2 text-sm text-green-500 flex items-center gap-1">
                        <CheckIcon className="w-4 h-4" /> Added to project
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'conversation' && (
            <div className="flex-1 flex overflow-hidden">
              {/* Campaign sidebar */}
              <CampaignSidebar
                activities={activities}
                selectedCampaign={selectedCampaign}
                onSelect={setSelectedCampaign}
              />

              {/* Conversation + compose */}
              <div className="flex-1 flex flex-col min-w-0">
                <ConversationView
                  activities={activities}
                  contactName={contactFirstName}
                  filterCampaign={selectedCampaign}
                />

                {/* Compose area with auto-selected channel */}
                <ComposeArea
                  contact={contact}
                  replyChannel={replyChannel}
                  setReplyChannel={setReplyChannel}
                  draftReply={draftReply}
                  setDraftReply={setDraftReply}
                  savedDraft={savedDraft}
                  setSavedDraft={setSavedDraft}
                  isSaving={isSaving}
                  handleSaveDraft={handleSaveDraft}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}
