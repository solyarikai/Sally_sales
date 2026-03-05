import { useState, useEffect, useCallback, useMemo } from 'react';
import { X, Mail, User, Building, MapPin, Linkedin, MessageSquare, Send, Clock, AlertTriangle, FolderPlus, ChevronLeft, ChevronRight, Loader2, SkipForward, Sparkles, ExternalLink, Link2, ChevronDown, Database, Search as SearchIcon, Globe } from 'lucide-react';
import toast from 'react-hot-toast';
import type { Contact } from '../api/contacts';
import { contactsApi } from '../api/contacts';
import { ConversationThread, adaptContactHistory } from './ConversationThread';
import { CampaignDropdown } from './CampaignDropdown';
import type { FullHistoryCampaign } from '../api/replies';
import { useTheme } from '../hooks/useTheme';

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

// Build CampaignDropdown data from activities
function buildCampaignsFromActivities(activities: Activity[]): FullHistoryCampaign[] {
  const map = new Map<string, { channel: string; campaign_name: string; count: number; latest: string; earliest: string }>();
  for (const a of activities) {
    const name = a.campaign || a.automation || 'Unknown';
    const ch = a.channel || 'email';
    const key = `${ch}::${name}`;
    const entry = map.get(key);
    if (entry) {
      entry.count++;
      if (a.timestamp > entry.latest) entry.latest = a.timestamp;
      if (a.timestamp < entry.earliest) entry.earliest = a.timestamp;
    } else {
      map.set(key, { channel: ch, campaign_name: name, count: 1, latest: a.timestamp, earliest: a.timestamp });
    }
  }
  return Array.from(map.values())
    .map(e => ({ channel: e.channel, campaign_name: e.campaign_name, message_count: e.count, latest_at: e.latest, earliest_at: e.earliest }))
    .sort((a, b) => b.latest_at.localeCompare(a.latest_at));
}

// Theme tokens (matching RepliesPage)
function modalTheme(isDark: boolean) {
  return isDark ? {
    bg: '#1e1e1e', cardBg: '#252526', border: '#333', divider: '#2d2d2d',
    text1: '#d4d4d4', text2: '#b0b0b0', text3: '#969696', text4: '#858585', text5: '#6e6e6e', text6: '#4e4e4e',
    inputBg: '#3c3c3c', inputBorder: '#505050', badgeBg: '#2d2d2d', badgeText: '#858585',
    tabActive: '#d4d4d4', tabInactive: '#6e6e6e', tabBorder: '#d4d4d4',
    btnPrimaryBg: '#d4d4d4', btnPrimaryText: '#1e1e1e', btnPrimaryHover: '#e0e0e0',
    btnGhostHover: '#2d2d2d', overlay: 'rgba(0,0,0,0.6)',
    composeBg: '#252526', composeBorder: '#333',
  } : {
    bg: '#ffffff', cardBg: '#ffffff', border: '#e0e0e0', divider: '#f0f0f0',
    text1: '#1a1a1a', text2: '#333', text3: '#555', text4: '#777', text5: '#999', text6: '#bbb',
    inputBg: '#f5f5f5', inputBorder: '#ddd', badgeBg: '#eee', badgeText: '#666',
    tabActive: '#1a1a1a', tabInactive: '#999', tabBorder: '#1a1a1a',
    btnPrimaryBg: '#333', btnPrimaryText: '#fff', btnPrimaryHover: '#222',
    btnGhostHover: '#f5f5f5', overlay: 'rgba(0,0,0,0.4)',
    composeBg: '#ffffff', composeBorder: '#e0e0e0',
  };
}

interface ContactDetailModalProps {
  contact: Contact | null;
  isOpen: boolean;
  onClose: () => void;
  // Campaign pre-selection (from redirect with ?campaign=channel::name)
  initialCampaignKey?: string | null;
  // Reply mode props
  replyMode?: boolean;
  contactList?: Contact[];
  currentIndex?: number;
  onNavigate?: (index: number) => void;
  onMarkProcessed?: (contactId: number) => void;
}

// ── Messenger-style conversation view (delegates to shared ConversationThread) ──
function ConversationView({
  activities,
  contactName,
  compact = false,
  isDark = false,
  filterCampaign = null,
}: {
  activities: Activity[];
  contactName: string;
  compact?: boolean;
  isDark?: boolean;
  filterCampaign?: string | null;
}) {
  return (
    <ConversationThread
      messages={adaptContactHistory(activities)}
      contactName={contactName}
      showDateSeparators
      showCampaignMarkers={false}
      compact={compact}
      isDark={isDark}
      filterCampaign={filterCampaign}
    />
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
  isDark = false,
  t,
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
  isDark?: boolean;
  t?: ReturnType<typeof modalTheme>;
}) {
  const th = t || modalTheme(isDark);

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

  if (!canEmail && !canLinkedin) {
    return (
      <div className="p-4" style={{ borderTop: `1px solid ${th.border}`, background: th.composeBg }}>
        <p className="text-[11px] text-center" style={{ color: th.text5 }}>No reply channels available</p>
      </div>
    );
  }

  return (
    <div className="p-4" style={{ borderTop: `1px solid ${th.border}`, background: th.composeBg }}>
      <div className="flex items-center gap-2 mb-3 px-1">
        <AlertTriangle className="w-3.5 h-3.5" style={{ color: isDark ? '#d4a464' : '#f59e0b' }} />
        <p className="text-[11px]" style={{ color: isDark ? '#d4a464' : '#d97706' }}>Draft mode — replies are saved but NOT sent automatically</p>
      </div>

      <div className="flex items-center gap-2 mb-2">
        <span
          className="px-2 py-0.5 rounded-full text-[10px] font-medium"
          style={{ background: isDark ? '#2d2d2d' : (replyChannel === 'email' ? '#faf5ff' : '#eff6ff'), color: isDark ? th.text3 : (replyChannel === 'email' ? '#9333ea' : '#2563eb') }}
        >
          {channelLabel}
        </span>
        <span className="text-[10px]" style={{ color: th.text5 }}>{viaLabel}</span>
        {canEmail && canLinkedin && (
          <button
            onClick={() => setReplyChannel(replyChannel === 'email' ? 'linkedin' : 'email')}
            className="text-[10px] transition-colors ml-1 cursor-pointer"
            style={{ color: isDark ? th.text3 : '#3b82f6' }}
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
          className="flex-1 p-3 rounded-xl resize-none text-sm focus:outline-none min-h-[60px] max-h-[120px]"
          style={{ background: th.inputBg, color: th.text1, border: `1px solid ${th.inputBorder}` }}
          autoFocus
          rows={2}
        />
        <button
          onClick={handleSaveDraft}
          disabled={!draftReply.trim() || isSaving}
          className="self-end p-2.5 rounded-xl transition-all cursor-pointer"
          style={{
            background: draftReply.trim() ? th.btnPrimaryBg : th.badgeBg,
            color: draftReply.trim() ? th.btnPrimaryText : th.text5,
          }}
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
  initialCampaignKey,
  replyMode = false, contactList = [], currentIndex = 0,
  onNavigate, onMarkProcessed,
}: ContactDetailModalProps) {
  const { isDark } = useTheme();
  const t = modalTheme(isDark);

  const [activeTab, setActiveTab] = useState<'details' | 'conversation' | 'source'>('details');
  const [sequenceExpanded, setSequenceExpanded] = useState(false);
  const [sequencePlan, setSequencePlan] = useState<any>(null);
  const [, setSequenceLoading] = useState(false);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [draftReply, setDraftReply] = useState('');
  const [replyChannel, setReplyChannel] = useState<'email' | 'linkedin' | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [savedDraft, setSavedDraft] = useState(false);
  const [projects, setProjects] = useState<Array<{id: number, name: string}>>([]);
  const [selectedProject, setSelectedProject] = useState<number | null>(null);
  const [isAddingToProject, setIsAddingToProject] = useState(false);
  const [addedToProject, setAddedToProject] = useState(false);
  const [selectedCampaign, setSelectedCampaign] = useState<string | null>(null);
  const [inboxLinks, setInboxLinks] = useState<Record<string, string>>({});

  // Build campaigns list for CampaignDropdown
  const campaigns = useMemo(() => buildCampaignsFromActivities(activities), [activities]);

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
      const controller = new AbortController();
      const { signal } = controller;

      // Reset state when contact changes
      setDraftReply('');
      setReplyChannel(null);
      setSavedDraft(false);
      setActiveTab('details');
      setSelectedProject(contact.project_id || null);
      setAddedToProject(false);
      setAiDraftBody('');
      setAiCategory('');
      setSelectedCampaign(null);
      setInboxLinks({});

      // Fetch projects list
      const fetchProjects = async () => {
        try {
          const response = await fetch('/api/contacts/projects/names', { signal });
          if (response.ok) {
            const data = await response.json();
            setProjects(data);
          }
        } catch (err: any) {
          if (err.name !== 'AbortError') {
            toast.error('Failed to load projects');
          }
        }
      };
      fetchProjects();

      // Fetch activities/history from API
      const fetchHistory = async () => {
        setIsLoadingHistory(true);
        try {
          const response = await fetch(`/api/contacts/${contact.id}/history`, { signal, cache: 'no-store' });
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
            if (data.inbox_links) setInboxLinks(data.inbox_links);
            // Campaign pre-selection: prefer initialCampaignKey (from redirect), else most recent
            if (allActivities.length > 0) {
              const campaignMap = new Map<string, string>();
              for (const a of allActivities) {
                const name = a.campaign || a.automation || 'Unknown';
                const ch = a.channel || 'email';
                const key = `${ch}::${name}`;
                if (!campaignMap.has(key)) campaignMap.set(key, a.timestamp);
                else if (a.timestamp > (campaignMap.get(key) || '')) campaignMap.set(key, a.timestamp);
              }

              // Try initialCampaignKey from URL redirect (format: "channel::campaign_name")
              let preSelected = '';
              if (initialCampaignKey && campaignMap.has(initialCampaignKey)) {
                preSelected = initialCampaignKey;
              }

              // Fallback: pick most recent campaign (F19)
              if (!preSelected) {
                let latestTs = '';
                for (const [key, ts] of campaignMap) {
                  if (ts > latestTs) { preSelected = key; latestTs = ts; }
                }
              }
              if (preSelected) setSelectedCampaign(preSelected);
            }
          }
        } catch (err: any) {
          if (err.name !== 'AbortError') {
            toast.error('Failed to load conversation history');
          }
        } finally {
          setIsLoadingHistory(false);
        }
      };
      fetchHistory();

      // Fetch sequence plan
      const fetchSequence = async () => {
        try {
          setSequenceLoading(true);
          const resp = await fetch(`/api/contacts/${contact.id}/sequence-plan`, { signal });
          if (resp.ok) {
            const data = await resp.json();
            setSequencePlan(data);
          }
        } catch (err: any) {
          if (err.name !== 'AbortError') {
            toast.error('Failed to load sequence plan');
          }
        } finally {
          setSequenceLoading(false);
        }
      };
      fetchSequence();

      // In reply mode, fetch AI draft
      if (replyMode && contact.last_reply_at) {
        fetchAiDraft(contact.id);
      }

      return () => controller.abort();
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

  const handleShareLink = () => {
    if (!contact) return;
    const url = new URL(window.location.href);
    url.searchParams.set('contact_id', String(contact.id));
    navigator.clipboard.writeText(url.toString()).then(() => {
      toast('Link copied to clipboard');
    }).catch(() => {
      toast.error('Failed to copy link');
    });
  };

  // ── Reply mode: 2-column split layout ──────────────────────────────
  if (replyMode) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        <div className="absolute inset-0 backdrop-blur-sm" style={{ background: t.overlay }} onClick={onClose} />
        <div className="relative rounded-2xl shadow-2xl w-full max-w-5xl h-[85vh] flex flex-col overflow-hidden" style={{ background: t.cardBg }}>
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3" style={{ borderBottom: `1px solid ${t.border}`, background: t.cardBg }}>
            <div className="flex items-center gap-2">
              <button
                onClick={() => onNavigate?.(currentIndex - 1)}
                disabled={currentIndex <= 0}
                className="p-1.5 rounded-lg disabled:opacity-20 transition-colors cursor-pointer"
                style={{ color: t.text3 }}
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <div className="w-9 h-9 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-xs font-semibold">
                {contact.first_name?.[0]}{contact.last_name?.[0]}
              </div>
              <div className="ml-1">
                <h2 className="text-[15px] font-semibold leading-tight" style={{ color: t.text1 }}>
                  {contact.first_name} {contact.last_name}
                </h2>
                <p className="text-[11px] leading-tight" style={{ color: t.text4 }}>
                  {contact.email}
                  {contact.company_name ? ` · ${contact.company_name}` : ''}
                  {contact.job_title ? ` · ${contact.job_title}` : ''}
                </p>
              </div>
              <button
                onClick={() => onNavigate?.(currentIndex + 1)}
                disabled={currentIndex >= contactList.length - 1}
                className="p-1.5 rounded-lg disabled:opacity-20 transition-colors ml-1 cursor-pointer"
                style={{ color: t.text3 }}
              >
                <ChevronRight className="w-4 h-4" />
              </button>
              <span className="text-[11px] ml-1 tabular-nums" style={{ color: t.text6 }}>
                {currentIndex + 1}/{contactList.length}
              </span>
            </div>
            <div className="flex items-center gap-2">
              {aiCategory && (
                <span className="px-2 py-0.5 rounded-full text-[11px] font-medium" style={{ background: t.badgeBg, color: t.badgeText }}>
                  {aiCategory.replace(/_/g, ' ')}
                </span>
              )}
              {contact.smartlead_id && (
                <a href={`https://app.smartlead.ai/app/email-accounts/leads/${contact.smartlead_id}`} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] transition-colors" style={{ color: t.text5 }} title="Open in SmartLead">
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
              <button
                onClick={handleShareLink}
                className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] transition-colors cursor-pointer"
                style={{ color: t.text5 }}
                title="Copy link to contact"
              >
                <Link2 className="w-3 h-3" />
              </button>
              <button onClick={onClose} className="p-1.5 rounded-lg transition-colors cursor-pointer" style={{ color: t.text4 }}>
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* 2-column split content */}
          <div className="flex-1 flex overflow-hidden">
            {/* Left: Conversation with CampaignDropdown */}
            <div className="flex-1 flex flex-col min-w-0" style={{ background: isDark ? '#1e1e1e' : '#fafafa' }}>
              {/* Campaign dropdown bar — hidden for 1-campaign contacts (Rule 2) */}
              {campaigns.length > 1 && (
              <div className="px-4 py-2 flex items-center gap-2" style={{ borderBottom: `1px solid ${t.divider}` }}>
                <CampaignDropdown
                  campaigns={campaigns}
                  selectedCampaign={selectedCampaign}
                  onSelect={setSelectedCampaign}
                  isDark={isDark}
                />
                {selectedCampaign && (() => {
                  const campName = selectedCampaign.split('::')[1] || selectedCampaign;
                  const link = inboxLinks[campName];
                  if (!link) return null;
                  const isGetSales = link.includes('getsales');
                  return (
                    <a href={link} target="_blank" rel="noopener noreferrer"
                      className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] transition-colors ml-auto"
                      style={{ color: t.text5 }} title={isGetSales ? 'Open in GetSales' : 'Open in SmartLead'}>
                      <ExternalLink className="w-3 h-3" />
                      {isGetSales ? 'GetSales' : 'SmartLead'}
                    </a>
                  );
                })()}
              </div>
              )}

              {isLoadingHistory ? (
                <div className="flex-1 p-4 space-y-3">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="animate-pulse rounded h-4" style={{ width: `${60 + (i % 3) * 15}%`, background: t.divider }} />
                  ))}
                </div>
              ) : (
                <ConversationView
                  activities={activities}
                  contactName={contactFirstName}
                  compact
                  isDark={isDark}
                  filterCampaign={selectedCampaign}
                />
              )}
            </div>

            {/* Right: AI Draft + Reply */}
            <div className="w-[320px] flex flex-col" style={{ borderLeft: `1px solid ${t.border}`, background: t.cardBg }}>
              {/* Contact summary */}
              <div className="px-4 py-3" style={{ borderBottom: `1px solid ${t.divider}` }}>
                <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
                  <div>
                    <span className="text-[10px] uppercase tracking-wider" style={{ color: t.text5 }}>Status</span>
                    <div className="font-medium" style={{ color: t.text2 }}>{contact.status || '—'}</div>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase tracking-wider" style={{ color: t.text5 }}>Source</span>
                    <div className="font-medium" style={{ color: t.text2 }}>{contact.source || '—'}</div>
                  </div>
                </div>
              </div>

              {/* AI Draft */}
              <div className="flex-1 px-4 py-3 flex flex-col min-h-0">
                <div className="flex items-center gap-1.5 mb-3">
                  <Sparkles className="w-3.5 h-3.5" style={{ color: isDark ? '#a78bfa' : '#8b5cf6' }} />
                  <span className="text-xs font-semibold" style={{ color: t.text2 }}>AI Suggested Reply</span>
                </div>

                {aiDraftLoading ? (
                  <div className="flex items-center gap-2 text-xs py-4" style={{ color: t.text5 }}>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" /> Generating draft...
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col min-h-0">
                    {replyChannel && (
                      <div className="flex items-center gap-2 mb-2">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-medium" style={{ background: t.badgeBg, color: t.badgeText }}>
                          {replyChannel === 'email' ? 'Email' : 'LinkedIn'}
                        </span>
                        <button onClick={() => setReplyChannel(replyChannel === 'email' ? 'linkedin' : 'email')}
                          className="text-[10px] transition-colors cursor-pointer" style={{ color: t.text5 }}>Switch</button>
                      </div>
                    )}

                    <textarea
                      value={draftReply}
                      onChange={(e) => { setDraftReply(e.target.value); setSavedDraft(false); }}
                      placeholder="Write your reply..."
                      className="flex-1 w-full p-3 rounded-xl resize-none text-[13px] focus:outline-none min-h-[100px] transition-all"
                      style={{ background: t.inputBg, color: t.text1, border: `1px solid ${t.inputBorder}` }}
                    />

                    <div className="flex items-center justify-between mt-3 gap-2">
                      <button onClick={handleSkip}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-[11px] font-medium transition-colors cursor-pointer"
                        style={{ color: t.text4 }}>
                        <SkipForward className="w-3 h-3" /> Skip
                      </button>
                      <button onClick={handleSaveDraft} disabled={!draftReply.trim() || isSaving}
                        className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-[11px] font-semibold transition-all cursor-pointer"
                        style={{ background: draftReply.trim() ? t.btnPrimaryBg : t.badgeBg, color: draftReply.trim() ? t.btnPrimaryText : t.text5 }}>
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

  // ── Normal mode: conversation-first with tabs ─────────────────────
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 backdrop-blur-sm" style={{ background: t.overlay }} onClick={onClose} />
      <div className="relative rounded-2xl shadow-2xl w-full max-w-4xl h-[85vh] flex flex-col overflow-hidden" style={{ background: t.cardBg }}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4" style={{ borderBottom: `1px solid ${t.border}` }}>
          <div className="flex items-center gap-4">
            <div className="w-11 h-11 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white text-base font-semibold">
              {contact.first_name?.[0]}{contact.last_name?.[0]}
            </div>
            <div>
              <h2 className="text-lg font-semibold" style={{ color: t.text1 }}>
                {contact.first_name} {contact.last_name}
              </h2>
              <p className="text-sm" style={{ color: t.text4 }}>{contact.email}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {contact.smartlead_id && (
              <a href={`https://app.smartlead.ai/app/email-accounts/leads/${contact.smartlead_id}`} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] transition-colors"
                style={{ color: t.text5 }} title="Open in SmartLead">
                <ExternalLink className="w-3.5 h-3.5" /> SmartLead
              </a>
            )}
            {contact.getsales_id && (
              <a href={`https://amazing.getsales.io/messenger?contactId=${contact.getsales_id}`} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] transition-colors"
                style={{ color: t.text5 }} title="Open in GetSales">
                <Linkedin className="w-3.5 h-3.5" /> GetSales
              </a>
            )}
            <button
              onClick={handleShareLink}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] transition-colors cursor-pointer"
              style={{ color: t.text5 }}
              title="Copy link to contact"
            >
              <Link2 className="w-3.5 h-3.5" />
              Share
            </button>
            <button onClick={onClose} className="p-2 rounded-lg transition-colors cursor-pointer" style={{ color: t.text4 }}>
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex px-6" style={{ borderBottom: `1px solid ${t.border}` }}>
          {([
            { key: 'details', label: 'Details', icon: User },
            { key: 'conversation', label: 'Conversation', icon: MessageSquare },
            { key: 'source', label: 'Source', icon: Database },
          ] as const).map(({ key, label, icon: Icon }) => {
            const active = activeTab === key;
            return (
              <button key={key} onClick={() => setActiveTab(key)}
                className="px-4 py-3 text-sm font-medium border-b-2 transition-colors cursor-pointer"
                style={{ borderColor: active ? t.tabBorder : 'transparent', color: active ? t.tabActive : t.tabInactive }}>
                <Icon className="w-4 h-4 inline mr-1.5" />{label}
              </button>
            );
          })}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {activeTab === 'details' && (
            <div className="flex-1 overflow-auto p-6">
              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h3 className="font-semibold" style={{ color: t.text1 }}>Contact Information</h3>
                  <div className="space-y-3">
                    <div className="flex items-center gap-3">
                      <Mail className="w-4 h-4" style={{ color: t.text5 }} />
                      <a href={`mailto:${contact.email}`} style={{ color: isDark ? '#93c5fd' : '#2563eb' }}>{contact.email}</a>
                    </div>
                    {contact.company_name && (
                      <div className="flex items-center gap-3">
                        <Building className="w-4 h-4" style={{ color: t.text5 }} />
                        <span style={{ color: t.text2 }}>{contact.company_name}</span>
                      </div>
                    )}
                    {contact.job_title && (
                      <div className="flex items-center gap-3">
                        <User className="w-4 h-4" style={{ color: t.text5 }} />
                        <span style={{ color: t.text2 }}>{contact.job_title}</span>
                      </div>
                    )}
                    {contact.location && (
                      <div className="flex items-center gap-3">
                        <MapPin className="w-4 h-4" style={{ color: t.text5 }} />
                        <span style={{ color: t.text2 }}>{contact.location}</span>
                      </div>
                    )}
                    {contact.linkedin_url && (
                      <div className="flex items-center gap-3">
                        <Linkedin className="w-4 h-4" style={{ color: t.text5 }} />
                        <a href={`https://${contact.linkedin_url}`} target="_blank" rel="noopener noreferrer" style={{ color: isDark ? '#93c5fd' : '#2563eb' }}>
                          View LinkedIn Profile
                        </a>
                      </div>
                    )}
                  </div>
                </div>

                <div className="space-y-4">
                  <h3 className="font-semibold" style={{ color: t.text1 }}>Status</h3>
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <span className="text-sm" style={{ color: t.text4 }}>Source:</span>
                      <span className="px-2 py-1 rounded-full text-xs font-medium" style={{ background: t.badgeBg, color: t.badgeText }}>{contact.source}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm" style={{ color: t.text4 }}>Status:</span>
                      <span className="px-2 py-1 rounded-full text-xs font-medium" style={{ background: t.badgeBg, color: t.badgeText }}>{contact.status}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm" style={{ color: t.text4 }}>Has Replied:</span>
                      <span className="px-2 py-1 rounded-full text-xs font-medium"
                        style={{ background: contact.last_reply_at ? (isDark ? '#1a3a2a' : '#f0fdf4') : t.badgeBg, color: contact.last_reply_at ? (isDark ? '#6ee7b7' : '#16a34a') : t.badgeText }}>
                        {contact.last_reply_at ? 'Yes' : 'No'}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4" style={{ color: t.text5 }} />
                      <span className="text-sm" style={{ color: t.text4 }}>Added {new Date(contact.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  {contact.notes && (
                    <div className="mt-4">
                      <h4 className="text-sm font-medium mb-2" style={{ color: t.text2 }}>Notes</h4>
                      <p className="text-sm p-3 rounded-xl" style={{ background: t.divider, color: t.text3 }}>{contact.notes}</p>
                    </div>
                  )}
                  <div className="mt-6 p-4 rounded-xl" style={{ background: t.divider, border: `1px solid ${t.border}` }}>
                    <h4 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: t.text1 }}>
                      <FolderPlus className="w-4 h-4" style={{ color: isDark ? '#93c5fd' : '#3b82f6' }} />
                      Add to Project
                    </h4>
                    <div className="flex items-center gap-3">
                      <select
                        value={selectedProject || ''}
                        onChange={(e) => setSelectedProject(e.target.value ? Number(e.target.value) : null)}
                        className="flex-1 px-3 py-2 rounded-lg text-sm focus:outline-none"
                        style={{ background: t.inputBg, color: t.text1, border: `1px solid ${t.inputBorder}` }}
                      >
                        <option value="">Select a project...</option>
                        {projects.map((project) => (
                          <option key={project.id} value={project.id}>{project.name}</option>
                        ))}
                      </select>
                      <button onClick={handleAddToProject} disabled={!selectedProject || isAddingToProject}
                        className="px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-all cursor-pointer"
                        style={{ background: (selectedProject && !isAddingToProject) ? t.btnPrimaryBg : t.badgeBg, color: (selectedProject && !isAddingToProject) ? t.btnPrimaryText : t.text5 }}>
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
            <div className="flex-1 flex flex-col overflow-hidden">
              {/* Campaign dropdown bar — hidden for 1-campaign contacts (Rule 2) */}
              {campaigns.length > 1 && (
                <div className="px-4 py-2 flex items-center gap-2" style={{ borderBottom: `1px solid ${t.divider}` }}>
                  <CampaignDropdown
                    campaigns={campaigns}
                    selectedCampaign={selectedCampaign}
                    onSelect={setSelectedCampaign}
                    isDark={isDark}
                  />
                  {selectedCampaign && (() => {
                    const campName = selectedCampaign.split('::')[1] || selectedCampaign;
                    const link = inboxLinks[campName];
                    if (!link) return null;
                    const isGetSales = link.includes('getsales');
                    return (
                      <a href={link} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] transition-colors ml-auto"
                        style={{ color: t.text5 }} title={isGetSales ? 'Open in GetSales' : 'Open in SmartLead'}>
                        <ExternalLink className="w-3 h-3" />
                        {isGetSales ? 'GetSales' : 'SmartLead'}
                      </a>
                    );
                  })()}
                </div>
              )}

              {/* Collapsible sequence plan section */}
              {sequencePlan && sequencePlan.campaigns?.length > 0 && (
                <div style={{ borderBottom: `1px solid ${t.divider}` }}>
                  <button
                    onClick={() => setSequenceExpanded(!sequenceExpanded)}
                    className="w-full flex items-center justify-between px-4 py-2 text-xs font-medium transition-colors cursor-pointer"
                    style={{ color: t.text3 }}
                  >
                    <span className="flex items-center gap-1.5">
                      <SkipForward className="w-3 h-3" />
                      Sequence Plan
                      <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: t.badgeBg, color: t.badgeText }}>
                        {sequencePlan.campaigns.reduce((acc: number, c: any) => acc + (c.steps_sent || 0), 0)}/{sequencePlan.campaigns.reduce((acc: number, c: any) => acc + (c.total_steps || 0), 0)} steps
                      </span>
                    </span>
                    <ChevronDown className={`w-3.5 h-3.5 transition-transform ${sequenceExpanded ? 'rotate-180' : ''}`} />
                  </button>
                  {sequenceExpanded && (
                    <div className="px-4 pb-3 space-y-3">
                      {sequencePlan.campaigns.map((camp: any) => (
                        <div key={camp.campaign_id} className="rounded-lg overflow-hidden" style={{ border: `1px solid ${t.border}` }}>
                          <div className="px-3 py-2" style={{ background: t.divider, borderBottom: `1px solid ${t.border}` }}>
                            <div className="flex items-center justify-between">
                              <div>
                                <h4 className="font-medium text-xs" style={{ color: t.text1 }}>{camp.campaign_name || camp.campaign_id}</h4>
                                <span className="text-[10px]" style={{ color: t.text4 }}>{camp.steps_sent}/{camp.total_steps} steps sent</span>
                              </div>
                              <span className="text-[10px] font-medium px-1.5 py-0.5 rounded" style={{ background: t.badgeBg, color: t.badgeText }}>
                                {camp.steps_sent === camp.total_steps ? 'Complete' : camp.steps_sent > 0 ? 'In Progress' : 'Queued'}
                              </span>
                            </div>
                            <div className="mt-1.5 h-1 rounded-full overflow-hidden" style={{ background: t.divider }}>
                              <div className="h-full rounded-full transition-all" style={{ width: camp.total_steps > 0 ? `${(camp.steps_sent / camp.total_steps) * 100}%` : '0%', background: isDark ? '#d4d4d4' : '#3b82f6' }} />
                            </div>
                          </div>
                          <div>
                            {camp.steps.map((step: any, si: number) => (
                              <div key={step.seq_number} className="px-3 py-2 flex items-start gap-2" style={{ borderTop: si > 0 ? `1px solid ${t.divider}` : undefined }}>
                                <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 text-[10px] font-bold"
                                  style={{ background: t.badgeBg, color: step.status === 'sent' ? (isDark ? '#6ee7b7' : '#16a34a') : t.badgeText }}>
                                  {step.status === 'sent' ? <CheckIcon className="w-3 h-3" /> : step.seq_number}
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-1.5">
                                    <span className="font-medium text-xs truncate" style={{ color: t.text1 }}>{step.subject || `Step ${step.seq_number}`}</span>
                                    <span className="text-[9px] font-medium uppercase px-1 py-0.5 rounded flex-shrink-0" style={{ background: t.badgeBg, color: t.badgeText }}>{step.status}</span>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Conversation */}
              <div className="flex-1 flex flex-col min-w-0 overflow-hidden" style={{ background: isDark ? '#1e1e1e' : '#fafafa' }}>
                {isLoadingHistory ? (
                  <div className="flex-1 p-4 space-y-3">
                    {[...Array(4)].map((_, i) => (
                      <div key={i} className="animate-pulse rounded h-4" style={{ width: `${60 + (i % 3) * 15}%`, background: t.divider }} />
                    ))}
                  </div>
                ) : (
                  <ConversationView
                    activities={activities}
                    contactName={contactFirstName}
                    compact
                    isDark={isDark}
                    filterCampaign={selectedCampaign}
                  />
                )}
              </div>

              {/* Compose area — only in reply mode */}
              {replyMode && (
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
                  isDark={isDark}
                  t={t}
                />
              )}
            </div>
          )}

          {activeTab === 'source' && (
            <div className="flex-1 overflow-auto p-6">
              <SourceTab contact={contact} isDark={isDark} t={t} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Source tab — shows provenance, platform state, campaigns
function SourceTab({ contact, isDark, t }: { contact: Contact; isDark: boolean; t: ReturnType<typeof modalTheme> }) {
  const prov = contact.provenance || {};
  const platformState = contact.platform_state || {};
  const campaigns = contact.campaigns || [];

  const sourceLabel = prov.source === 'APOLLO' ? 'Apollo' : prov.source === 'WEBSITE_SCRAPE' ? 'Web Scrape' : prov.source || contact.source || 'Unknown';

  return (
    <div className="space-y-6">
      {/* Origin */}
      <div>
        <h3 className="text-xs font-medium uppercase tracking-wide mb-3" style={{ color: t.text4 }}>Origin</h3>
        <div className="space-y-2.5">
          <div className="flex items-center gap-3">
            <Database className="w-4 h-4 shrink-0" style={{ color: t.text5 }} />
            <span className="text-sm" style={{ color: t.text2 }}>{sourceLabel}</span>
          </div>
          {prov.query && (
            <div className="flex items-start gap-3">
              <SearchIcon className="w-4 h-4 shrink-0 mt-0.5" style={{ color: t.text5 }} />
              <div>
                <span className="text-[10px] uppercase tracking-wide" style={{ color: t.text5 }}>Search Query</span>
                <p className="text-sm mt-0.5" style={{ color: t.text1 }}>{prov.query}</p>
              </div>
            </div>
          )}
          {prov.domain && (
            <div className="flex items-center gap-3">
              <Globe className="w-4 h-4 shrink-0" style={{ color: t.text5 }} />
              <div>
                <span className="text-[10px] uppercase tracking-wide" style={{ color: t.text5 }}>Domain</span>
                <p className="text-sm mt-0.5" style={{ color: t.text2 }}>{prov.domain}</p>
              </div>
            </div>
          )}
          {prov.segment && (
            <div className="flex items-center gap-3">
              <span className="w-4 h-4 shrink-0 flex items-center justify-center text-[10px] font-bold" style={{ color: t.text5 }}>S</span>
              <div>
                <span className="text-[10px] uppercase tracking-wide" style={{ color: t.text5 }}>Segment</span>
                <p className="text-sm mt-0.5" style={{ color: t.text2 }}>{String(prov.segment).replace(/_/g, ' ')}</p>
              </div>
            </div>
          )}
          {prov.gathered_at && (
            <div className="flex items-center gap-3">
              <Clock className="w-4 h-4 shrink-0" style={{ color: t.text5 }} />
              <div>
                <span className="text-[10px] uppercase tracking-wide" style={{ color: t.text5 }}>Gathered</span>
                <p className="text-sm mt-0.5" style={{ color: t.text3 }}>{new Date(prov.gathered_at).toLocaleString()}</p>
              </div>
            </div>
          )}
          {prov.apollo_enriched && (
            <div className="flex items-center gap-3">
              <span className="w-4 h-4 shrink-0 flex items-center justify-center text-[10px]" style={{ color: isDark ? '#4ade80' : '#16a34a' }}>A</span>
              <span className="text-sm" style={{ color: t.text3 }}>Apollo enriched</span>
            </div>
          )}
          {prov.search_job_id && (
            <div className="flex items-center gap-3">
              <span className="w-4 h-4 shrink-0 text-[10px] text-center" style={{ color: t.text5 }}>#</span>
              <span className="text-sm" style={{ color: t.text4 }}>Search job {prov.search_job_id}</span>
            </div>
          )}
        </div>
      </div>

      {/* Campaigns */}
      {campaigns.length > 0 && (
        <div>
          <h3 className="text-xs font-medium uppercase tracking-wide mb-3" style={{ color: t.text4 }}>Campaigns</h3>
          <div className="space-y-1.5">
            {campaigns.map((c, i) => (
              <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-lg" style={{ background: t.divider }}>
                <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: c.source === 'smartlead' ? '#3b82f6' : '#f59e0b' }} />
                <span className="text-xs flex-1 truncate" style={{ color: t.text2 }}>{c.name}</span>
                <span className="text-[10px]" style={{ color: t.text5 }}>{c.source === 'smartlead' ? 'Email' : 'LinkedIn'}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Platform State */}
      {Object.keys(platformState).length > 0 && (
        <div>
          <h3 className="text-xs font-medium uppercase tracking-wide mb-3" style={{ color: t.text4 }}>Platform Data</h3>
          {Object.entries(platformState).map(([platform, data]) => (
            <div key={platform} className="mb-3">
              <span className="text-[10px] uppercase tracking-wide font-medium" style={{ color: t.text5 }}>{platform}</span>
              <pre className="mt-1 text-[11px] p-3 rounded-lg overflow-auto max-h-40" style={{ background: t.divider, color: t.text3 }}>
                {JSON.stringify(data, null, 2)}
              </pre>
            </div>
          ))}
        </div>
      )}

      {/* Raw provenance */}
      {Object.keys(prov).length > 0 && (
        <div>
          <h3 className="text-xs font-medium uppercase tracking-wide mb-3" style={{ color: t.text4 }}>Raw Provenance</h3>
          <pre className="text-[11px] p-3 rounded-lg overflow-auto max-h-40" style={{ background: t.divider, color: t.text3 }}>
            {JSON.stringify(prov, null, 2)}
          </pre>
        </div>
      )}
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
