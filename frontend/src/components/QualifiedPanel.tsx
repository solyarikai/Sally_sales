import { useState, useEffect, useCallback } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import {
  Star, CheckCircle2, Clock, Building2, Mail,
  RefreshCw, AlertTriangle, XCircle,
} from 'lucide-react';
import { contactsApi, type Contact } from '../api/contacts';
import { themeColors } from '../lib/themeColors';
import { useAppStore } from '../store/appStore';

export interface QualifiedPanelProps {
  isDark: boolean;
  onCountChange?: (count: number) => void;
}

function daysSince(dateStr: string): number {
  return Math.floor((Date.now() - new Date(dateStr).getTime()) / 86400000);
}

export function QualifiedPanel({ isDark, onCountChange }: QualifiedPanelProps) {
  const t = themeColors(isDark);
  const { currentProject } = useAppStore();

  const [awaiting, setAwaiting] = useState<Contact[]>([]);
  const [completed, setCompleted] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingIds, setUpdatingIds] = useState<Set<number>>(new Set());

  const toastOk = { background: t.toastBg, color: t.toastText, border: `1px solid ${t.toastBorder}` };
  const toastErr = { background: t.toastBg, color: t.toastErrText, border: `1px solid ${t.toastBorder}` };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [qualifiedRes, customerRes, lostRes] = await Promise.all([
        contactsApi.list({
          project_id: currentProject?.id,
          status: 'qualified',
          page_size: 100,
          sort_by: 'updated_at',
          sort_order: 'desc',
        }),
        contactsApi.list({
          project_id: currentProject?.id,
          status: 'customer',
          page_size: 50,
          sort_by: 'updated_at',
          sort_order: 'desc',
        }),
        contactsApi.list({
          project_id: currentProject?.id,
          status: 'lost',
          page_size: 50,
          sort_by: 'updated_at',
          sort_order: 'desc',
        }),
      ]);
      setAwaiting(qualifiedRes.contacts);
      const allCompleted = [...customerRes.contacts, ...lostRes.contacts]
        .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
      setCompleted(allCompleted);
      onCountChange?.(qualifiedRes.total);
    } catch (err) {
      console.error('Failed to load qualified data:', err);
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
      setAwaiting(prev => prev.filter(c => c.id !== contact.id));
      setCompleted(prev => prev.filter(c => c.id !== contact.id));
      load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update', { style: toastErr });
    } finally {
      setUpdatingIds(prev => { const s = new Set(prev); s.delete(contact.id); return s; });
    }
  };

  const statusBadge = (status: string) => {
    const isCustomer = status === 'customer';
    return (
      <span
        className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
        style={{
          background: isCustomer
            ? (isDark ? '#052e16' : '#dcfce7')
            : (isDark ? '#1c1917' : '#f5f5f4'),
          color: isCustomer
            ? (isDark ? '#4ade80' : '#166534')
            : (isDark ? '#a8a29e' : '#78716c'),
        }}
      >
        {isCustomer ? 'Customer' : 'Lost'}
      </span>
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
        {/* Section: Awaiting Confirmation */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <Star className="w-4 h-4" style={{ color: isDark ? '#3b82f6' : '#2563eb' }} />
            <h2 className="text-[14px] font-semibold uppercase tracking-wider" style={{ color: t.text2 }}>
              Awaiting Confirmation
            </h2>
            {awaiting.length > 0 && (
              <span
                className="text-[11px] px-2 py-0.5 rounded-full font-medium"
                style={{ background: isDark ? '#172554' : '#dbeafe', color: isDark ? '#60a5fa' : '#1e40af' }}
              >
                {awaiting.length}
              </span>
            )}
          </div>

          {awaiting.length === 0 ? (
            <div className="text-center py-8 text-[13px]" style={{ color: t.text5 }}>
              No contacts awaiting qualification
            </div>
          ) : (
            <div className="space-y-2">
              {awaiting.map(contact => {
                const days = daysSince(contact.updated_at);
                const stale = days > 3;
                const name = [contact.first_name, contact.last_name].filter(Boolean).join(' ') || contact.email;
                return (
                  <div
                    key={contact.id}
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
                              <AlertTriangle className="w-2.5 h-2.5" />{days}d
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 text-[11px]" style={{ color: t.text5 }}>
                          {contact.email && (
                            <span className="flex items-center gap-1">
                              <Mail className="w-3 h-3" />{contact.email}
                            </span>
                          )}
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />Qualified {days}d ago
                          </span>
                        </div>
                        {contact.notes && (
                          <div className="mt-1.5 text-[12px] line-clamp-2" style={{ color: t.text3 }}>
                            {contact.notes}
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <button
                          onClick={() => updateStatus(contact, 'customer')}
                          disabled={updatingIds.has(contact.id)}
                          className="flex items-center gap-1 px-2.5 py-1.5 rounded text-[12px] font-medium transition-all cursor-pointer active:scale-[0.98]"
                          style={{ background: t.btnPrimaryBg, color: t.btnPrimaryText }}
                        >
                          <CheckCircle2 className="w-3 h-3" /> Confirm
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
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>

        {/* Section: Completed */}
        <section>
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 className="w-4 h-4" style={{ color: t.text4 }} />
            <h2 className="text-[14px] font-semibold uppercase tracking-wider" style={{ color: t.text2 }}>
              Completed
            </h2>
            {completed.length > 0 && (
              <span className="text-[11px] px-2 py-0.5 rounded-full" style={{ background: t.badgeBg, color: t.badgeText }}>
                {completed.length}
              </span>
            )}
          </div>

          {completed.length === 0 ? (
            <div className="text-center py-8 text-[13px]" style={{ color: t.text5 }}>
              No completed leads yet
            </div>
          ) : (
            <div className="space-y-1.5">
              {completed.map(contact => {
                const name = [contact.first_name, contact.last_name].filter(Boolean).join(' ') || contact.email;
                return (
                  <div
                    key={contact.id}
                    className="rounded-lg border px-4 py-2.5 flex items-center gap-3"
                    style={{ background: t.cardBg, borderColor: t.cardBorder, opacity: 0.8 }}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[13px] truncate" style={{ color: t.text2 }}>
                          {name}
                        </span>
                        {contact.company_name && (
                          <span className="text-[12px] truncate" style={{ color: t.text5 }}>
                            {contact.company_name}
                          </span>
                        )}
                        {statusBadge(contact.status)}
                      </div>
                    </div>
                    <span className="text-[11px] flex-shrink-0" style={{ color: t.text5 }}>
                      {new Date(contact.updated_at).toLocaleDateString()}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
