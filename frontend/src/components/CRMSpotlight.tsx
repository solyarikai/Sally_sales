import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Command, X, Loader2, Send, CheckCircle2, TrendingUp } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { contactsApi } from '../api/contacts';
import { useToast } from './Toast';

interface Props {
  open: boolean;
  onClose: () => void;
  projectId: number | null;
  projectName: string | null;
  /** Current CRM filter state to pass to the backend */
  filters: Record<string, any>;
  contactCount: number;
}

export function CRMSpotlight({ open, onClose, projectId, projectName, filters, contactCount }: Props) {
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const navigate = useNavigate();
  const { error: toastError } = useToast();
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ contactsAnalyzed: number; slug: string } | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (open) {
      setText('');
      setResult(null);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  async function handleSubmit() {
    if (!projectId || !text.trim() || text.trim().length < 5) return;
    setSubmitting(true);
    try {
      const res = await contactsApi.crmSpotlightGTM(projectId, text.trim(), filters);
      setResult({
        contactsAnalyzed: res.contacts_analyzed || 0,
        slug: res.project_slug || projectName?.toLowerCase().replace(/\s+/g, '-') || '',
      });
    } catch (e: any) {
      toastError(e?.response?.data?.detail || 'Analysis failed');
    } finally {
      setSubmitting(false);
    }
  }

  function handleViewGTM() {
    if (!result) return;
    onClose();
    navigate(`/knowledge/gtm?project=${result.slug}`);
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[20vh]"
      style={{ backdropFilter: 'blur(4px)', background: 'rgba(0,0,0,0.4)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-lg rounded-xl shadow-2xl overflow-hidden"
        style={{ background: t.cardBg, border: `1px solid ${t.cardBorder}` }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: t.divider }}>
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4" style={{ color: '#3b82f6' }} />
            <span className="text-[13px] font-medium" style={{ color: t.text1 }}>
              CRM Spotlight — {projectName || 'project'}
            </span>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:opacity-70">
            <X className="w-4 h-4" style={{ color: t.text4 }} />
          </button>
        </div>

        {/* Content */}
        <div className="p-4">
          {!projectId ? (
            <p className="text-[13px] text-center py-4" style={{ color: t.text4 }}>
              Select a project first to analyze contacts
            </p>
          ) : result ? (
            /* Success state */
            <div className="flex flex-col items-center py-4 gap-3">
              <CheckCircle2 className="w-8 h-8" style={{ color: '#22c55e' }} />
              <div className="text-center">
                <p className="text-[14px] font-medium" style={{ color: t.text1 }}>
                  Analysis complete
                </p>
                <p className="text-[12px] mt-1" style={{ color: t.text4 }}>
                  {result.contactsAnalyzed} contacts analyzed with Gemini 2.5 Pro
                </p>
              </div>
              <button
                onClick={handleViewGTM}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-opacity hover:opacity-80 cursor-pointer"
                style={{ background: t.btnPrimaryBg, color: t.btnPrimaryText }}
              >
                <TrendingUp className="w-3.5 h-3.5" />
                View GTM Strategy
              </button>
              <button
                onClick={onClose}
                className="flex items-center gap-1.5 text-[12px] transition-opacity hover:opacity-70 cursor-pointer"
                style={{ color: t.text5 }}
              >
                Stay here
              </button>
            </div>
          ) : submitting ? (
            /* Loading state */
            <div className="flex flex-col items-center py-6 gap-3">
              <Loader2 className="w-8 h-8 animate-spin" style={{ color: '#3b82f6' }} />
              <div className="text-center">
                <p className="text-[14px] font-medium" style={{ color: t.text1 }}>
                  Analyzing conversations...
                </p>
                <p className="text-[12px] mt-1" style={{ color: t.text4 }}>
                  Gemini 2.5 Pro is reviewing {contactCount > 0 ? `~${contactCount}` : ''} contacts and their full conversation histories
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* Context badge */}
              <div
                className="flex items-center gap-2 px-3 py-2 rounded-lg mb-3 text-[12px]"
                style={{ background: isDark ? '#1a2332' : '#eff6ff', color: isDark ? '#93c5fd' : '#1d4ed8' }}
              >
                <Command className="w-3.5 h-3.5 shrink-0" />
                <span>
                  {contactCount > 0 ? `${contactCount} contacts` : 'Filtered contacts'} with warm replies
                  {filters.reply_category ? ` (${filters.reply_category})` : ''}
                </span>
              </div>

              <textarea
                ref={inputRef}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Escape') onClose();
                  if (e.key === 'Enter' && e.metaKey) handleSubmit();
                }}
                placeholder="Ask about these contacts... e.g. 'Why so few scheduled calls? How to improve scheduling rate from warm replies?'"
                rows={4}
                className="w-full rounded-lg px-3 py-2 text-[13px] resize-none focus:outline-none"
                style={{
                  background: t.inputBg,
                  color: t.text1,
                  border: `1px solid ${t.inputBorder}`,
                }}
              />
              <div className="flex items-center justify-between mt-3">
                <span className="text-[11px]" style={{ color: t.text5 }}>
                  {'\u2318'}+Enter to submit
                </span>
                <button
                  onClick={handleSubmit}
                  disabled={text.trim().length < 5}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[13px] font-medium transition-colors"
                  style={{
                    background: text.trim().length < 5 ? t.badgeBg : t.btnPrimaryBg,
                    color: text.trim().length < 5 ? t.text4 : t.btnPrimaryText,
                    cursor: text.trim().length < 5 ? 'not-allowed' : 'pointer',
                  }}
                >
                  <Send className="w-3.5 h-3.5" />
                  Analyze
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
