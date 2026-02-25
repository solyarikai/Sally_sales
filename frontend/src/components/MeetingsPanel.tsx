import { useState, useEffect, useCallback } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import {
  Calendar, CheckCircle2, Clock, User, Building2, Mail,
  RefreshCw, ChevronRight, AlertTriangle, XCircle,
} from 'lucide-react';
import { contactsApi, type Contact } from '../api/contacts';
import { themeColors } from '../lib/themeColors';
import { useAppStore } from '../store/appStore';

export interface MeetingsPanelProps {
  isDark: boolean;
  onCountChange?: (count: number) => void;
}

function daysSince(dateStr: string): number {
  return Math.floor((Date.now() - new Date(dateStr).getTime()) / 86400000);
}

export function MeetingsPanel({ isDark, onCountChange }: MeetingsPanelProps) {
  const t = themeColors(isDark);
  const { currentProject } = useAppStore();

  const [scheduling, setScheduling] = useState<Contact[]>([]);
  const [scheduled, setScheduled] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingIds, setUpdatingIds] = useState<Set<number>>(new Set());

  const toastOk = { background: t.toastBg, color: t.toastText, border: `1px solid ${t.toastBorder}` };
  const toastErr = { background: t.toastBg, color: t.toastErrText, border: `1px solid ${t.toastBorder}` };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [repliedRes, scheduledRes] = await Promise.all([
        contactsApi.list({
          project_id: currentProject?.id,
          status: 'replied',
          has_replied: true,
          page_size: 100,
          sort_by: 'updated_at',
          sort_order: 'desc',
        }),
        contactsApi.list({
          project_id: currentProject?.id,
          status: 'scheduled',
          page_size: 100,
          sort_by: 'updated_at',
          sort_order: 'desc',
        }),
      ]);
      setScheduling(repliedRes.contacts);
      setScheduled(scheduledRes.contacts);
      onCountChange?.(repliedRes.total + scheduledRes.total);
    } catch (err) {
      console.error('Failed to load meetings data:', err);
    } finally {
      setLoading(false);
    }
  }, [currentProject?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load(); }, [load]);

  const updateStatus = async (contact: Contact, newStatus: string) => {
    setUpdatingIds(prev => new Set(prev).add(contact.id));
    try {
      await contactsApi.updateStatus(contact.id, newStatus);
      toast.success(`Moved to ${newStatus}`, { style: toastOk });
      // Optimistic: remove from current list
      setScheduling(prev => prev.filter(c => c.id !== contact.id));
      setScheduled(prev => prev.filter(c => c.id !== contact.id));
      // Refresh to get updated counts
      load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update', { style: toastErr });
    } finally {
      setUpdatingIds(prev => { const s = new Set(prev); s.delete(contact.id); return s; });
    }
  };

  const ContactCard = ({ contact, actions }: { contact: Contact; actions: React.ReactNode }) => {
    const days = daysSince(contact.updated_at);
    const stale = days > 5;
    const name = [contact.first_name, contact.last_name].filter(Boolean).join(' ') || contact.email;

    return (
      <div
        className="rounded-lg border px-4 py-3 transition-colors"
        style={{
          background: t.cardBg,
          borderColor: stale ? (isDark ? '#5a3030' : '#fecaca') : t.cardBorder,
        }}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[13px] font-medium truncate" style={{ color: t.text1 }}>
                {name}
              </span>
              {contact.company_name && (
                <span className="flex items-center gap-1 text-[12px] truncate" style={{ color: t.text4 }}>
                  <Building2 className="w-3 h-3" />{contact.company_name}
                </span>
              )}
              {stale && (
                <span
                  className="flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                  style={{ background: isDark ? '#3a2020' : '#fef2f2', color: isDark ? '#f87171' : '#dc2626' }}
                >
                  <AlertTriangle className="w-2.5 h-2.5" />{days}d stale
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-[11px]" style={{ color: t.text5 }}>
              {contact.email && (
                <span className="flex items-center gap-1">
                  <Mail className="w-3 h-3" />{contact.email}
                </span>
              )}
              {contact.campaign && (
                <span className="truncate">{contact.campaign}</span>
              )}
            </div>
            {contact.notes && (
              <div className="mt-1.5 text-[12px] line-clamp-2" style={{ color: t.text3 }}>
                {contact.notes}
              </div>
            )}
          </div>
          <div className="flex items-center gap-1 flex-shrink-0">
            {actions}
          </div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20" style={{ background: t.pageBg }}>
        <RefreshCw className="w-5 h-5 animate-spin" style={{ color: t.text5 }} />
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto" style={{ background: t.pageBg }}>
      <Toaster position="top-center" />
      <div className="max-w-4xl mx-auto py-4 px-4 space-y-6">
        {/* Section: Scheduling */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <Calendar className="w-4 h-4" style={{ color: isDark ? '#f59e0b' : '#d97706' }} />
            <h2 className="text-[14px] font-semibold uppercase tracking-wider" style={{ color: t.text2 }}>
              Needs Scheduling
            </h2>
            {scheduling.length > 0 && (
              <span
                className="text-[11px] px-2 py-0.5 rounded-full font-medium"
                style={{ background: isDark ? '#451a03' : '#fef3c7', color: isDark ? '#fbbf24' : '#92400e' }}
              >
                {scheduling.length}
              </span>
            )}
          </div>

          {scheduling.length === 0 ? (
            <div className="text-center py-8 text-[13px]" style={{ color: t.text5 }}>
              No contacts need scheduling
            </div>
          ) : (
            <div className="space-y-2">
              {scheduling.map(contact => (
                <ContactCard
                  key={contact.id}
                  contact={contact}
                  actions={
                    <>
                      <button
                        onClick={() => updateStatus(contact, 'scheduled')}
                        disabled={updatingIds.has(contact.id)}
                        className="flex items-center gap-1 px-2.5 py-1.5 rounded text-[12px] font-medium transition-all cursor-pointer active:scale-[0.98]"
                        style={{ background: t.btnPrimaryBg, color: t.btnPrimaryText }}
                      >
                        <Calendar className="w-3 h-3" /> Schedule
                      </button>
                      <button
                        onClick={() => updateStatus(contact, 'lead')}
                        disabled={updatingIds.has(contact.id)}
                        className="p-1.5 rounded transition-colors cursor-pointer"
                        style={{ color: t.text5 }}
                        title="Not interested"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                      </button>
                    </>
                  }
                />
              ))}
            </div>
          )}
        </section>

        {/* Section: Scheduled */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 className="w-4 h-4" style={{ color: isDark ? '#22c55e' : '#16a34a' }} />
            <h2 className="text-[14px] font-semibold uppercase tracking-wider" style={{ color: t.text2 }}>
              Scheduled
            </h2>
            {scheduled.length > 0 && (
              <span
                className="text-[11px] px-2 py-0.5 rounded-full font-medium"
                style={{ background: isDark ? '#052e16' : '#dcfce7', color: isDark ? '#4ade80' : '#166534' }}
              >
                {scheduled.length}
              </span>
            )}
          </div>

          {scheduled.length === 0 ? (
            <div className="text-center py-8 text-[13px]" style={{ color: t.text5 }}>
              No scheduled meetings
            </div>
          ) : (
            <div className="space-y-2">
              {scheduled.map(contact => (
                <ContactCard
                  key={contact.id}
                  contact={contact}
                  actions={
                    <>
                      <button
                        onClick={() => updateStatus(contact, 'qualified')}
                        disabled={updatingIds.has(contact.id)}
                        className="flex items-center gap-1 px-2.5 py-1.5 rounded text-[12px] font-medium transition-all cursor-pointer active:scale-[0.98]"
                        style={{ background: t.btnPrimaryBg, color: t.btnPrimaryText }}
                      >
                        <ChevronRight className="w-3 h-3" /> Qualify
                      </button>
                      <button
                        onClick={() => updateStatus(contact, 'lost')}
                        disabled={updatingIds.has(contact.id)}
                        className="p-1.5 rounded transition-colors cursor-pointer"
                        style={{ color: t.text5 }}
                        title="Not qualified"
                      >
                        <XCircle className="w-3.5 h-3.5" />
                      </button>
                    </>
                  }
                />
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
