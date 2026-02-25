import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Mail, User, Building, MapPin, Linkedin, MessageSquare,
  Clock, ArrowLeft, Loader2, Globe, ExternalLink, Phone,
} from 'lucide-react';
import { cn } from '../lib/utils';
import type { Contact } from '../api/contacts';
import { contactsApi } from '../api/contacts';

// ── Types ────────────────────────────────────────────────────────────

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

interface CampaignEntry {
  name: string;
  channel: 'email' | 'linkedin';
  count: number;
}

// ── Helpers ──────────────────────────────────────────────────────────

function buildCampaignList(activities: Activity[]): { email: CampaignEntry[]; linkedin: CampaignEntry[] } {
  const map = new Map<string, CampaignEntry>();
  for (const a of activities) {
    const name = a.campaign || a.automation || 'Unknown';
    const channel = a.channel || 'email';
    const key = `${channel}::${name}`;
    const entry = map.get(key);
    if (entry) entry.count++;
    else map.set(key, { name, channel: channel as 'email' | 'linkedin', count: 1 });
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

// ── Main Page ────────────────────────────────────────────────────────

export function ContactDetailPage() {
  const { contactId } = useParams<{ contactId: string }>();
  const [contact, setContact] = useState<Contact | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCampaign, setSelectedCampaign] = useState<string | null>(null);
  const [editingNotes, setEditingNotes] = useState(false);
  const [notes, setNotes] = useState('');

  const id = contactId ? parseInt(contactId) : null;

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);

    const load = async () => {
      try {
        // Load contact data
        const contactData = await contactsApi.getContactWithActivities(id);
        setContact(contactData);
        setNotes(contactData.notes || '');

        // Load conversation history
        const response = await fetch(`/api/contacts/${id}/history`);
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
        setError(err.message || 'Failed to load contact');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  const handleSaveNotes = useCallback(async () => {
    if (!id) return;
    try {
      await contactsApi.update(id, { notes });
      setEditingNotes(false);
    } catch (err) {
      console.error('Failed to save notes:', err);
    }
  }, [id, notes]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[500px]">
        <Loader2 className="w-6 h-6 animate-spin text-neutral-400" />
      </div>
    );
  }

  if (error || !contact) {
    return (
      <div className="p-6 max-w-[1400px] mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          {error || 'Contact not found'}
        </div>
        <Link to="/contacts" className="mt-4 inline-flex items-center gap-1 text-sm text-blue-600 hover:underline">
          <ArrowLeft className="w-4 h-4" /> Back to contacts
        </Link>
      </div>
    );
  }

  const contactName = [contact.first_name, contact.last_name].filter(Boolean).join(' ') || contact.email;

  return (
    <div className="h-[calc(100vh-48px)] flex flex-col">
      {/* Top bar */}
      <div className="flex items-center gap-3 px-6 py-3 border-b border-neutral-200 bg-white flex-shrink-0">
        <Link to="/contacts" className="p-1.5 hover:bg-neutral-100 rounded-lg transition-colors">
          <ArrowLeft className="w-5 h-5 text-neutral-600" />
        </Link>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-bold text-neutral-900 truncate">{contactName}</h1>
          <p className="text-xs text-neutral-500 truncate">
            {contact.email}
            {contact.company_name && <span> &middot; {contact.company_name}</span>}
            {contact.job_title && <span> &middot; {contact.job_title}</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn(
            'px-2 py-0.5 rounded-full text-xs font-medium',
            contact.source === 'smartlead' ? 'bg-purple-50 text-purple-600' :
            contact.source === 'getsales' ? 'bg-blue-50 text-blue-600' :
            'bg-gray-100 text-gray-600'
          )}>
            {contact.source}
          </span>
          <span className={cn(
            'px-2 py-0.5 rounded-full text-xs font-medium',
            contact.last_reply_at ? 'bg-green-50 text-green-600' : 'bg-gray-100 text-gray-600'
          )}>
            {contact.status}
          </span>
        </div>
      </div>

      {/* Two-panel layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left panel: Contact info */}
        <div className="w-[340px] flex-shrink-0 border-r border-neutral-200 overflow-y-auto bg-white">
          <div className="p-5 space-y-5">
            {/* Contact info */}
            <section className="space-y-3">
              <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Contact</h3>
              <InfoRow icon={Mail} label="Email">
                <a href={`mailto:${contact.email}`} className="text-blue-600 hover:underline text-sm truncate">
                  {contact.email}
                </a>
              </InfoRow>
              {contact.company_name && (
                <InfoRow icon={Building} label="Company">
                  <span className="text-sm">{contact.company_name}</span>
                </InfoRow>
              )}
              {contact.job_title && (
                <InfoRow icon={User} label="Title">
                  <span className="text-sm">{contact.job_title}</span>
                </InfoRow>
              )}
              {contact.domain && (
                <InfoRow icon={Globe} label="Domain">
                  <span className="text-sm text-neutral-600">{contact.domain}</span>
                </InfoRow>
              )}
              {contact.phone && (
                <InfoRow icon={Phone} label="Phone">
                  <span className="text-sm">{contact.phone}</span>
                </InfoRow>
              )}
              {contact.location && (
                <InfoRow icon={MapPin} label="Location">
                  <span className="text-sm">{contact.location}</span>
                </InfoRow>
              )}
              {contact.linkedin_url && (
                <InfoRow icon={Linkedin} label="LinkedIn">
                  <a
                    href={contact.linkedin_url.startsWith('http') ? contact.linkedin_url : `https://${contact.linkedin_url}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:underline text-sm inline-flex items-center gap-1"
                  >
                    Profile <ExternalLink className="w-3 h-3" />
                  </a>
                </InfoRow>
              )}
            </section>

            {/* Status */}
            <section className="space-y-2">
              <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Status</h3>
              <div className="flex flex-wrap gap-1.5">
                <span className={cn(
                  'px-2 py-0.5 rounded-full text-xs font-medium',
                  contact.last_reply_at ? 'bg-green-50 text-green-600' : 'bg-gray-100 text-gray-600'
                )}>
                  {contact.last_reply_at ? 'Replied' : 'No reply'}
                </span>
                <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                  {contact.status}
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-neutral-500">
                <Clock className="w-3.5 h-3.5" />
                Added {new Date(contact.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </div>
            </section>

            {/* Campaigns */}
            {contact.campaigns && contact.campaigns.length > 0 && (
              <section className="space-y-2">
                <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Campaigns</h3>
                <div className="space-y-1.5">
                  {contact.campaigns.map((c, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      {c.source === 'getsales' ? (
                        <Linkedin className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" />
                      ) : (
                        <Mail className="w-3.5 h-3.5 text-purple-500 flex-shrink-0" />
                      )}
                      <span className="font-medium text-neutral-700 truncate">{c.name}</span>
                      {c.status && (
                        <span className="text-neutral-400 flex-shrink-0">{c.status}</span>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Notes */}
            <section className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Notes</h3>
                {!editingNotes && (
                  <button
                    onClick={() => setEditingNotes(true)}
                    className="text-xs text-blue-600 hover:underline"
                  >
                    {contact.notes ? 'Edit' : 'Add'}
                  </button>
                )}
              </div>
              {editingNotes ? (
                <div className="space-y-2">
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    rows={3}
                    className="w-full text-sm border border-neutral-200 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-blue-100"
                    placeholder="Add notes..."
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={handleSaveNotes}
                      className="px-3 py-1 text-xs font-medium bg-blue-500 text-white rounded-lg hover:bg-blue-600"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => { setEditingNotes(false); setNotes(contact.notes || ''); }}
                      className="px-3 py-1 text-xs text-neutral-500 hover:text-neutral-700"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : contact.notes ? (
                <p className="text-sm text-neutral-600 bg-neutral-50 p-2.5 rounded-lg">{contact.notes}</p>
              ) : (
                <p className="text-xs text-neutral-300">No notes</p>
              )}
            </section>
          </div>
        </div>

        {/* Right panel: Conversation */}
        <div className="flex-1 flex overflow-hidden bg-white">
          {/* Campaign sidebar */}
          <CampaignSidebar
            activities={activities}
            selectedCampaign={selectedCampaign}
            onSelect={setSelectedCampaign}
          />

          {/* Messages */}
          <div className="flex-1 flex flex-col min-w-0">
            <ConversationView
              activities={activities}
              contactName={contactName}
              filterCampaign={selectedCampaign}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Subcomponents ────────────────────────────────────────────────────

function InfoRow({ icon: Icon, children }: { icon: any; label?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2.5">
      <Icon className="w-4 h-4 text-neutral-400 mt-0.5 flex-shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  );
}

function CampaignSidebar({
  activities,
  selectedCampaign,
  onSelect,
}: {
  activities: Activity[];
  selectedCampaign: string | null;
  onSelect: (campaign: string | null) => void;
}) {
  const { email, linkedin } = useMemo(() => buildCampaignList(activities), [activities]);
  const totalCount = activities.length;
  const emailCount = activities.filter(a => (a.channel || 'email') === 'email').length;
  const linkedinCount = activities.filter(a => a.channel === 'linkedin').length;

  return (
    <div className="w-[180px] flex-shrink-0 border-r border-gray-100 overflow-y-auto bg-gray-50/30">
      <div className="p-2">
        <button
          onClick={() => onSelect(null)}
          className={cn(
            'w-full text-left px-2.5 py-2 rounded-lg text-[12px] font-semibold transition-colors mb-1',
            selectedCampaign === null ? 'bg-blue-50 text-blue-700' : 'text-gray-600 hover:bg-gray-100'
          )}
        >
          All <span className="ml-1 text-[10px] font-normal text-gray-400">({totalCount})</span>
        </button>

        {emailCount > 0 && (
          <div className="mt-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
              <Mail className="w-3 h-3" /> Email <span className="ml-auto font-normal">({emailCount})</span>
            </div>
            {email.map((c) => (
              <button
                key={`email-${c.name}`}
                onClick={() => onSelect(`email::${c.name}`)}
                className={cn(
                  'w-full text-left px-2.5 py-1.5 rounded-lg text-[11px] transition-colors flex items-center gap-1.5',
                  selectedCampaign === `email::${c.name}` ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-500 hover:bg-gray-100'
                )}
              >
                <span className="truncate flex-1">{c.name}</span>
                <span className="text-[10px] text-gray-400 flex-shrink-0">{c.count}</span>
              </button>
            ))}
          </div>
        )}

        {linkedinCount > 0 && (
          <div className="mt-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-gray-400">
              <Linkedin className="w-3 h-3" /> LinkedIn <span className="ml-auto font-normal">({linkedinCount})</span>
            </div>
            {linkedin.map((c) => (
              <button
                key={`linkedin-${c.name}`}
                onClick={() => onSelect(`linkedin::${c.name}`)}
                className={cn(
                  'w-full text-left px-2.5 py-1.5 rounded-lg text-[11px] transition-colors flex items-center gap-1.5',
                  selectedCampaign === `linkedin::${c.name}` ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-500 hover:bg-gray-100'
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

function ConversationView({
  activities,
  contactName,
  filterCampaign = null,
}: {
  activities: Activity[];
  contactName: string;
  filterCampaign?: string | null;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [filtered]);

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
      month: 'short', day: 'numeric', year: 'numeric',
    });

    if (dateStr !== prevDate) {
      items.push({ kind: 'date', label: dateStr, key: `date-${i}` });
      prevDate = dateStr;
      prevCampaign = '';
    }

    const campaignLabel = act.campaign || act.automation || '';
    if (campaignLabel && campaignLabel !== prevCampaign) {
      items.push({ kind: 'campaign', label: campaignLabel, channel: act.channel, key: `campaign-${i}` });
      prevCampaign = campaignLabel;
    }

    const showTail = act.direction !== prevDirection;
    prevDirection = act.direction;
    items.push({ kind: 'message', activity: act, showTail, key: `msg-${act.id}` });
  }

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
                  'px-2.5 py-0.5 rounded-full text-[10px] font-medium inline-flex items-center gap-1',
                  item.channel === 'linkedin' ? 'bg-blue-50 text-blue-500' : 'bg-purple-50 text-purple-500'
                )}>
                  {item.channel === 'linkedin' ? <Linkedin className="w-2.5 h-2.5" /> : <Mail className="w-2.5 h-2.5" />}
                  {item.label}
                </span>
              </div>
            );
          }

          const { activity, showTail } = item;
          const isOut = activity.direction === 'outbound';
          const time = new Date(activity.timestamp).toLocaleTimeString('en-US', {
            hour: 'numeric', minute: '2-digit',
          });

          return (
            <div
              key={item.key}
              className={cn('flex', isOut ? 'justify-end' : 'justify-start', showTail ? 'mt-2' : 'mt-px')}
            >
              {!isOut && (
                <div className="w-7 flex-shrink-0 mt-auto mb-0.5 mr-1.5">
                  {showTail ? (
                    <div className="w-7 h-7 rounded-full bg-gray-200 flex items-center justify-center text-[10px] font-semibold text-gray-600">
                      {contactName.charAt(0).toUpperCase()}
                    </div>
                  ) : null}
                </div>
              )}
              <div className={cn(
                'max-w-[75%] px-3 py-2 relative text-sm',
                isOut ? 'bg-[#3B82F6] text-white rounded-2xl rounded-br-md' : 'bg-[#F1F1F1] text-gray-900 rounded-2xl rounded-bl-md'
              )}>
                <p className="whitespace-pre-wrap break-words leading-relaxed">{activity.content}</p>
                <div className={cn('flex items-center gap-1.5 mt-1', isOut ? 'justify-end' : 'justify-start')}>
                  <span className={cn('text-[11px]', isOut ? 'text-white/60' : 'text-gray-400')}>
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
