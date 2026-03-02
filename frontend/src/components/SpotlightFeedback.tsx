import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Command, X, Loader2, Send, CheckCircle2, ExternalLink } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { useTheme } from '../hooks/useTheme';
import { themeColors } from '../lib/themeColors';
import { submitFeedback } from '../api/learning';
import { useToast } from './Toast';

interface Props {
  open: boolean;
  onClose: () => void;
}

export function SpotlightFeedback({ open, onClose }: Props) {
  const { currentProject } = useAppStore();
  const { isDark } = useTheme();
  const t = themeColors(isDark);
  const navigate = useNavigate();
  const { error: toastError } = useToast();
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState<{ logId: number } | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (open) {
      setText('');
      setSubmitted(null);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  async function handleSubmit() {
    if (!currentProject || !text.trim() || text.trim().length < 5) return;
    setSubmitting(true);
    try {
      const result = await submitFeedback(currentProject.id, text.trim());
      setSubmitted({ logId: result.learning_log_id });
      useAppStore.getState().setPendingLearning({
        logId: result.learning_log_id,
        projectId: currentProject.id,
      });
    } catch (e) {
      toastError('Failed to submit feedback');
    } finally {
      setSubmitting(false);
    }
  }

  function handleViewLog() {
    if (!currentProject || !submitted) return;
    const slug = currentProject.name.toLowerCase().replace(/\s+/g, '-');
    onClose();
    navigate(`/knowledge/logs?project=${slug}&logId=${submitted.logId}`);
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
            <Command className="w-4 h-4" style={{ color: t.text3 }} />
            <span className="text-[13px] font-medium" style={{ color: t.text1 }}>
              Feedback for {currentProject?.name || 'project'}
            </span>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:opacity-70">
            <X className="w-4 h-4" style={{ color: t.text4 }} />
          </button>
        </div>

        {/* Content */}
        <div className="p-4">
          {!currentProject ? (
            <p className="text-[13px] text-center py-4" style={{ color: t.text4 }}>
              Select a project first to submit feedback
            </p>
          ) : submitted ? (
            /* Success state with link to learning log */
            <div className="flex flex-col items-center py-4 gap-3">
              <CheckCircle2 className="w-8 h-8" style={{ color: '#22c55e' }} />
              <div className="text-center">
                <p className="text-[14px] font-medium" style={{ color: t.text1 }}>
                  Feedback submitted
                </p>
                <p className="text-[12px] mt-1" style={{ color: t.text4 }}>
                  AI is processing your feedback and updating templates...
                </p>
              </div>
              <button
                onClick={onClose}
                className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium transition-opacity hover:opacity-80 cursor-pointer"
                style={{ background: t.btnPrimaryBg, color: t.btnPrimaryText }}
              >
                Stay here
              </button>
              <button
                onClick={handleViewLog}
                className="flex items-center gap-1.5 text-[12px] transition-opacity hover:opacity-70 cursor-pointer"
                style={{ color: t.text5 }}
              >
                <ExternalLink className="w-3.5 h-3.5" />
                View in Learning Logs
              </button>
            </div>
          ) : (
            <>
              <textarea
                ref={inputRef}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Escape') onClose();
                  if (e.key === 'Enter' && e.metaKey) handleSubmit();
                }}
                placeholder="Tell the AI how to improve replies... (e.g., 'Be more casual on LinkedIn', 'Always mention our free trial')"
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
                  disabled={submitting || text.trim().length < 5}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[13px] font-medium transition-colors"
                  style={{
                    background: submitting || text.trim().length < 5 ? t.badgeBg : t.btnPrimaryBg,
                    color: submitting || text.trim().length < 5 ? t.text4 : t.btnPrimaryText,
                    cursor: submitting || text.trim().length < 5 ? 'not-allowed' : 'pointer',
                  }}
                >
                  {submitting ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Send className="w-3.5 h-3.5" />
                  )}
                  Submit
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
