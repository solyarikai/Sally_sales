import { useState, useEffect, useCallback } from 'react';
import { X, Mail, User, Building, MapPin, Linkedin, MessageSquare, Send, Clock, AlertTriangle, FolderPlus, ChevronLeft, ChevronRight, Loader2, SkipForward, Sparkles, ExternalLink } from 'lucide-react';
import toast from 'react-hot-toast';
import { cn } from '../lib/utils';
import type { Contact } from '../api/contacts';
import { contactsApi } from '../api/contacts';
import { ConversationThread, adaptContactHistory } from './ConversationThread';
import { CampaignSidebar } from './CampaignSidebar';

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

// ── Messenger-style conversation view (delegates to shared ConversationThread) ──
function ConversationView({
  activities,
  contactName,
  compact = false,
  filterCampaign = null,
}: {
  activities: Activity[];
  contactName: string;
  compact?: boolean;
  filterCampaign?: string | null;
}) {
  return (
    <ConversationThread
      messages={adaptContactHistory(activities)}
      contactName={contactName}
      showAvatars
      showDateSeparators
      showCampaignMarkers
      compact={compact}
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
  const [activeTab, setActiveTab] = useState<'details' | 'conversation' | 'sequence'>('details');
  const [sequencePlan, setSequencePlan] = useState<any>(null);
  const [sequenceLoading, setSequenceLoading] = useState(false);
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
      setActiveTab('conversation');
      setSelectedProject(contact.project_id || null);
      setAddedToProject(false);
      setAiDraftBody('');
      setAiCategory('');
      setSelectedCampaign(null);

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
          const response = await fetch(`/api/contacts/${contact.id}/history`, { signal });
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
      if (replyMode && contact.has_replied) {
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
              {contact.smartlead_id && (
                <a
                  href={`https://app.smartlead.ai/app/email-accounts/leads/${contact.smartlead_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 px-2 py-1 rounded-lg text-[10px] text-gray-500 hover:bg-gray-100 transition-colors"
                  title="Open in SmartLead"
                >
                  <ExternalLink className="w-3 h-3" />
                </a>
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
              {isLoadingHistory ? (
                <div className="flex-1 p-4 space-y-3">
                  {[...Array(4)].map((_, i) => (
                    <div key={i} className="animate-pulse bg-gray-200/20 rounded h-4" style={{ width: `${60 + (i % 3) * 15}%` }} />
                  ))}
                </div>
              ) : (
                <ConversationView
                  activities={activities}
                  contactName={contactFirstName}
                  compact
                  filterCampaign={selectedCampaign}
                />
              )}
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
          <div className="flex items-center gap-2">
            {contact.smartlead_id && (
              <a
                href={`https://app.smartlead.ai/app/email-accounts/leads/${contact.smartlead_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] text-gray-500 hover:bg-gray-100 transition-colors"
                title="Open in SmartLead"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                SmartLead
              </a>
            )}
            <button onClick={onClose} className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
              <X className="w-5 h-5 text-gray-400" />
            </button>
          </div>
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
          <button
            onClick={() => setActiveTab('sequence')}
            className={cn(
              "px-4 py-3 text-sm font-medium border-b-2 transition-colors",
              activeTab === 'sequence'
                ? "border-blue-500 text-blue-600"
                : "border-transparent text-gray-400 hover:text-gray-600"
            )}
          >
            <SkipForward className="w-4 h-4 inline mr-1.5" />
            Sequence
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
                {isLoadingHistory ? (
                  <div className="flex-1 p-4 space-y-3">
                    {[...Array(4)].map((_, i) => (
                      <div key={i} className="animate-pulse bg-gray-200/20 rounded h-4" style={{ width: `${60 + (i % 3) * 15}%` }} />
                    ))}
                  </div>
                ) : (
                  <ConversationView
                    activities={activities}
                    contactName={contactFirstName}
                    filterCampaign={selectedCampaign}
                  />
                )}

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

          {activeTab === 'sequence' && (
            <div className="flex-1 overflow-auto p-6">
              {sequenceLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
                </div>
              ) : !sequencePlan || sequencePlan.campaigns?.length === 0 ? (
                <div className="text-center py-12 text-gray-400 text-sm">
                  No sequence data available for this contact.
                </div>
              ) : (
                <div className="space-y-6">
                  {sequencePlan.campaigns.map((camp: any) => (
                    <div key={camp.campaign_id} className="border border-gray-200 rounded-lg overflow-hidden">
                      <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
                        <div className="flex items-center justify-between">
                          <div>
                            <h4 className="font-medium text-gray-900 text-sm">{camp.campaign_name || camp.campaign_id}</h4>
                            <span className="text-xs text-gray-500">
                              {camp.steps_sent}/{camp.total_steps} steps sent
                            </span>
                          </div>
                          <span className={cn(
                            "text-xs font-medium px-2 py-0.5 rounded",
                            camp.steps_sent === camp.total_steps
                              ? "bg-green-100 text-green-700"
                              : camp.steps_sent > 0
                                ? "bg-blue-100 text-blue-700"
                                : "bg-gray-100 text-gray-500"
                          )}>
                            {camp.steps_sent === camp.total_steps ? 'Complete' : camp.steps_sent > 0 ? 'In Progress' : 'Queued'}
                          </span>
                        </div>
                        {/* Progress bar */}
                        <div className="mt-2 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-blue-500 rounded-full transition-all"
                            style={{ width: camp.total_steps > 0 ? `${(camp.steps_sent / camp.total_steps) * 100}%` : '0%' }}
                          />
                        </div>
                      </div>
                      <div className="divide-y divide-gray-100">
                        {camp.steps.map((step: any) => (
                          <div key={step.seq_number} className="px-4 py-3 flex items-start gap-3">
                            <div className={cn(
                              "w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 text-xs font-bold",
                              step.status === 'sent' ? "bg-green-100 text-green-700" :
                              step.status === 'scheduled' ? "bg-blue-100 text-blue-700" :
                              "bg-gray-100 text-gray-400"
                            )}>
                              {step.status === 'sent' ? (
                                <CheckIcon className="w-3.5 h-3.5" />
                              ) : (
                                step.seq_number
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-sm text-gray-900 truncate">
                                  {step.subject || `Step ${step.seq_number}`}
                                </span>
                                <span className={cn(
                                  "text-[10px] font-medium uppercase px-1.5 py-0.5 rounded flex-shrink-0",
                                  step.status === 'sent' ? "bg-green-100 text-green-700" :
                                  step.status === 'scheduled' ? "bg-blue-100 text-blue-700" :
                                  "bg-gray-100 text-gray-500"
                                )}>
                                  {step.status}
                                </span>
                              </div>
                              {step.body_preview && (
                                <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                                  {step.body_preview}
                                </p>
                              )}
                            </div>
                          </div>
                        ))}
                        {camp.steps.length === 0 && (
                          <div className="px-4 py-6 text-center text-gray-400 text-sm">
                            No sequence steps found for this campaign.
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
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
