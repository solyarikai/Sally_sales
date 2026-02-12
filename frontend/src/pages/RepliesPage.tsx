import toast, { Toaster } from 'react-hot-toast';
import { useEffect, useState, useCallback } from 'react';
import {
  MessageSquare, Search, RefreshCw,
  X, Copy, Check,
  Calendar, Mail, Building2,
  ExternalLink,
  CheckCircle, XCircle, Shield, Zap, Hash, Send, MessageCircle
} from 'lucide-react';
import {
  repliesApi,
  type ProcessedReply,
  type ProcessedReplyStats,
  type ReplyCategory,
  type ConversationMessage,
} from '../api/replies';
import { cn, formatNumber } from '../lib/utils';
import { useAppStore } from '../store/appStore';

const CATEGORY_CONFIG: Record<ReplyCategory, { label: string; color: string; emoji: string }> = {
  interested: { label: 'Interested', color: 'bg-emerald-100 text-emerald-700 border-emerald-200', emoji: '🟢' },
  meeting_request: { label: 'Meeting Request', color: 'bg-blue-100 text-blue-700 border-blue-200', emoji: '📅' },
  not_interested: { label: 'Not Interested', color: 'bg-red-100 text-red-700 border-red-200', emoji: '🔴' },
  out_of_office: { label: 'Out of Office', color: 'bg-amber-100 text-amber-700 border-amber-200', emoji: '🏖️' },
  wrong_person: { label: 'Wrong Person', color: 'bg-purple-100 text-purple-700 border-purple-200', emoji: '🔄' },
  unsubscribe: { label: 'Unsubscribe', color: 'bg-gray-100 text-gray-700 border-gray-200', emoji: '🚫' },
  question: { label: 'Question', color: 'bg-cyan-100 text-cyan-700 border-cyan-200', emoji: '❓' },
  other: { label: 'Other', color: 'bg-neutral-100 text-neutral-700 border-neutral-200', emoji: '📧' },
};

export function RepliesPage() {
  const { currentProject } = useAppStore();

  // Data state
  const [replies, setReplies] = useState<ProcessedReply[]>([]);
  const [stats, setStats] = useState<ProcessedReplyStats | null>(null);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<ReplyCategory | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [needsReplyFilter, setNeedsReplyFilter] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);

  // UI state
  const [selectedReply, setSelectedReply] = useState<ProcessedReply | null>(null);
  const [confirmReply, setConfirmReply] = useState<ProcessedReply | null>(null);
  const [isSending, setIsSending] = useState(false);

  // Load data
  const loadReplies = useCallback(async () => {
    setIsLoading(true);
    try {
      const campaignNames = currentProject?.campaign_filters?.length
        ? currentProject.campaign_filters.join(',')
        : undefined;
      const response = await repliesApi.getReplies({
        campaign_names: campaignNames,
        category: categoryFilter || undefined,
        approval_status: statusFilter || undefined,
        needs_reply: needsReplyFilter || undefined,
        page,
        page_size: pageSize,
      });
      setReplies(response.replies || []);
      setTotal(response.total || 0);
    } catch (err) {
      console.error('Failed to load replies:', err);
    } finally {
      setIsLoading(false);
    }
  }, [categoryFilter, statusFilter, needsReplyFilter, page, pageSize, currentProject]);

  const loadStats = useCallback(async () => {
    try {
      const campaignNames = currentProject?.campaign_filters?.length
        ? currentProject.campaign_filters.join(',')
        : undefined;
      const data = await repliesApi.getReplyStats({ campaign_names: campaignNames });
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  }, [currentProject]);

  useEffect(() => { setPage(1); }, [currentProject]);

  useEffect(() => {
    loadReplies();
    loadStats();
  }, [loadReplies, loadStats]);

  const handleRefresh = () => { loadReplies(); loadStats(); };

  const handleCopyDraft = async (reply: ProcessedReply) => {
    if (reply.draft_reply) {
      await navigator.clipboard.writeText(reply.draft_reply);
      toast.success('Draft copied!');
    }
  };

  const handleApproveAndSend = async (replyId: number) => {
    setIsSending(true);
    try {
      const result = await repliesApi.approveAndSendReply(replyId);
      if (result.test_mode) {
        toast.success(`Test sent to ${result.sent_to || 'pn@getsally.io'}`);
      } else if (result.dry_run) {
        toast.success('Approved (dry run)');
      } else {
        toast.success('Reply sent!');
      }
      setConfirmReply(null);
      loadReplies();
      loadStats();
      if (selectedReply?.id === replyId) setSelectedReply(null);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to approve and send');
    } finally {
      setIsSending(false);
    }
  };

  const handleDismissReply = async (replyId: number) => {
    try {
      await repliesApi.dismissReply(replyId);
      toast.success('Reply skipped');
      loadReplies();
      loadStats();
      if (selectedReply?.id === replyId) setSelectedReply(null);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to dismiss');
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  // Client-side search filter
  const filteredReplies = (replies || []).filter(reply => {
    if (!search) return true;
    const s = search.toLowerCase();
    return (
      reply.lead_email?.toLowerCase().includes(s) ||
      reply.lead_first_name?.toLowerCase().includes(s) ||
      reply.lead_last_name?.toLowerCase().includes(s) ||
      reply.lead_company?.toLowerCase().includes(s) ||
      reply.email_subject?.toLowerCase().includes(s) ||
      reply.campaign_name?.toLowerCase().includes(s)
    );
  });

  // Top categories for stats bar
  const topCategories = stats?.by_category
    ? Object.entries(stats.by_category).sort(([, a], [, b]) => b - a).slice(0, 4)
    : [];

  return (
    <div className="h-full flex flex-col bg-neutral-50">
      <Toaster position="top-center" />

      {/* Header */}
      <div className="bg-white border-b border-neutral-200 px-6 py-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
              <MessageSquare className="w-5 h-5 text-violet-600" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-neutral-900">Replies</h1>
              <p className="text-sm text-neutral-500">{formatNumber(total)} total</p>
            </div>
          </div>
          <button onClick={handleRefresh} className="btn btn-secondary btn-sm">
            <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
          </button>
        </div>

        {/* Stats row */}
        {stats && (
          <div className="flex items-center gap-2 flex-wrap mb-3">
            <StatBadge label="Total" value={formatNumber(stats.total)} />
            <StatBadge label="Pending" value={formatNumber(stats.pending)} color="amber" />
            <StatBadge label="Today" value={formatNumber(stats.today)} color="blue" />
            {topCategories.map(([cat, count]) => {
              const config = CATEGORY_CONFIG[cat as ReplyCategory];
              return <StatBadge key={cat} label={config?.label || cat} value={formatNumber(count)} emoji={config?.emoji} />;
            })}
          </div>
        )}

        {/* Filters */}
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 max-w-sm">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input
              type="text"
              placeholder="Search by email, name, company..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input pl-9 w-full text-sm"
            />
          </div>

          <select
            value={categoryFilter || ''}
            onChange={(e) => { setCategoryFilter(e.target.value as ReplyCategory || null); setPage(1); }}
            className="input text-sm"
          >
            <option value="">All Categories</option>
            {Object.entries(CATEGORY_CONFIG).map(([key, config]) => (
              <option key={key} value={key}>{config.emoji} {config.label}</option>
            ))}
          </select>

          <select
            value={statusFilter || ''}
            onChange={(e) => { setStatusFilter(e.target.value || null); setPage(1); }}
            className="input text-sm"
          >
            <option value="">All Statuses</option>
            <option value="pending">Pending</option>
            <option value="approved">Approved</option>
            <option value="dismissed">Dismissed</option>
          </select>

          <button
            onClick={() => { setNeedsReplyFilter(!needsReplyFilter); setPage(1); }}
            className={cn(
              "flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium border transition-colors",
              needsReplyFilter
                ? "bg-orange-100 text-orange-700 border-orange-300"
                : "bg-white text-neutral-600 border-neutral-200 hover:border-orange-300 hover:text-orange-700"
            )}
          >
            <MessageCircle className="w-4 h-4" />
            Needs Reply
          </button>

          <button
            onClick={() => { setStatusFilter(prev => prev === 'pending' ? null : 'pending'); setPage(1); }}
            className={cn(
              "flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium border transition-colors",
              statusFilter === 'pending'
                ? "bg-amber-100 text-amber-700 border-amber-300"
                : "bg-white text-neutral-600 border-neutral-200 hover:border-amber-300 hover:text-amber-700"
            )}
          >
            <Shield className="w-4 h-4" />
            Moderation
            {stats?.pending ? (
              <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-amber-500 text-white font-semibold">
                {stats.pending}
              </span>
            ) : null}
          </button>
        </div>
      </div>

      {/* Reply list - full width */}
      <div className="flex-1 overflow-auto p-4">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-6 h-6 animate-spin text-neutral-400" />
          </div>
        ) : filteredReplies.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12">
            <div className="w-16 h-16 rounded-xl bg-neutral-100 flex items-center justify-center mb-4">
              <Mail className="w-8 h-8 text-neutral-400" />
            </div>
            <p className="text-neutral-500">No replies found</p>
            <p className="text-sm text-neutral-400 mt-1">
              {needsReplyFilter ? 'No leads currently need a response' : 'Replies will appear here when your campaigns receive responses'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredReplies.map(reply => (
              <ReplyCard
                key={reply.id}
                reply={reply}
                onClick={() => setSelectedReply(reply)}
                onApprove={() => setConfirmReply(reply)}
                onDismiss={() => handleDismissReply(reply.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="bg-white border-t border-neutral-200 px-6 py-3 flex items-center justify-between">
          <div className="text-sm text-neutral-500">Page {page} of {totalPages}</div>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn btn-secondary btn-sm">Prev</button>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="btn btn-secondary btn-sm">Next</button>
          </div>
        </div>
      )}

      {/* Reply Detail Slide-out */}
      {selectedReply && (
        <ReplyDetailPanel
          reply={selectedReply}
          onClose={() => setSelectedReply(null)}
          onCopyDraft={() => handleCopyDraft(selectedReply)}
          onApprove={() => setConfirmReply(selectedReply)}
          onDismiss={() => handleDismissReply(selectedReply.id)}
        />
      )}

      {/* Send Confirmation Dialog */}
      {confirmReply && (
        <SendConfirmDialog
          reply={confirmReply}
          isSending={isSending}
          onConfirm={() => handleApproveAndSend(confirmReply.id)}
          onCancel={() => setConfirmReply(null)}
        />
      )}
    </div>
  );
}

// ---------- Stat Badge ----------
function StatBadge({ label, value, color, emoji }: { label: string; value: string; color?: string; emoji?: string }) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 border-blue-200 text-blue-700',
    amber: 'bg-amber-50 border-amber-200 text-amber-700',
    purple: 'bg-purple-50 border-purple-200 text-purple-700',
    green: 'bg-emerald-50 border-emerald-200 text-emerald-700',
  };
  return (
    <div className={cn("rounded-lg px-3 py-1.5 border text-sm", color ? colors[color] : 'bg-neutral-50 border-neutral-100')}>
      {emoji && <span className="mr-1">{emoji}</span>}
      <span className="font-semibold">{value}</span>
      <span className="text-xs ml-1 opacity-70">{label}</span>
    </div>
  );
}

// ---------- Reply Card ----------
interface ReplyCardProps {
  reply: ProcessedReply;
  onClick: () => void;
  onApprove: () => void;
  onDismiss: () => void;
}

function ReplyCard({ reply, onClick, onApprove, onDismiss }: ReplyCardProps) {
  const category = reply.category as ReplyCategory;
  const categoryConfig = category ? CATEGORY_CONFIG[category] : CATEGORY_CONFIG.other;
  const leadName = [reply.lead_first_name, reply.lead_last_name].filter(Boolean).join(' ') || reply.lead_email;

  return (
    <div
      onClick={onClick}
      className="bg-white rounded-xl border border-neutral-200 p-4 hover:border-violet-300 hover:shadow-sm cursor-pointer transition-all"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2 mb-2">
            <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium border", categoryConfig.color)}>
              {categoryConfig.emoji} {categoryConfig.label}
            </span>
            {reply.category_confidence && (
              <span className="text-xs text-neutral-400">{reply.category_confidence}</span>
            )}
            {reply.sent_to_slack && (
              <span className="text-xs text-emerald-600 flex items-center gap-1"><Check className="w-3 h-3" />Slack</span>
            )}
          </div>

          {/* Lead info */}
          <div className="flex items-center gap-3 mb-1">
            <span className="font-medium text-neutral-900">{leadName}</span>
            {reply.lead_company && (
              <span className="text-sm text-neutral-500 flex items-center gap-1">
                <Building2 className="w-3 h-3" />{reply.lead_company}
              </span>
            )}
          </div>

          {/* Subject + snippet */}
          <div className="text-sm text-neutral-600 mb-1">
            <strong>Subject:</strong> {reply.email_subject || '(no subject)'}
          </div>
          <div className="text-sm text-neutral-500 line-clamp-2">
            {reply.email_body || reply.reply_text || '(empty)'}
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-1 flex-shrink-0">
          {reply.approval_status === 'approved' && (
            <span className="px-2 py-1 text-xs font-medium bg-emerald-100 text-emerald-700 rounded-lg flex items-center gap-1"><CheckCircle className="w-3 h-3" />Sent</span>
          )}
          {reply.approval_status === 'approved_dry_run' && (
            <span className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-700 rounded-lg flex items-center gap-1"><CheckCircle className="w-3 h-3" />Dry Run</span>
          )}
          {reply.approval_status === 'approved_test' && (
            <span className="px-2 py-1 text-xs font-medium bg-amber-100 text-amber-700 rounded-lg flex items-center gap-1"><CheckCircle className="w-3 h-3" />Test Sent</span>
          )}
          {reply.approval_status === 'dismissed' && (
            <span className="px-2 py-1 text-xs font-medium bg-neutral-100 text-neutral-500 rounded-lg flex items-center gap-1"><XCircle className="w-3 h-3" />Skipped</span>
          )}
          {(!reply.approval_status || reply.approval_status === 'pending') && reply.draft_reply && (
            <button onClick={(e) => { e.stopPropagation(); onApprove(); }} className="px-3 py-1.5 text-xs font-semibold bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg flex items-center gap-1" title="Approve & send">
              <CheckCircle className="w-3.5 h-3.5" />OK
            </button>
          )}
          {(!reply.approval_status || reply.approval_status === 'pending') && (
            <button onClick={(e) => { e.stopPropagation(); onDismiss(); }} className="px-2 py-1.5 text-xs text-neutral-400 hover:text-red-500 hover:bg-red-50 rounded-lg" title="Skip">
              <XCircle className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center gap-4 mt-3 pt-3 border-t border-neutral-100 text-xs text-neutral-400">
        <span className="flex items-center gap-1">
          <Calendar className="w-3 h-3" />
          {reply.received_at ? new Date(reply.received_at).toLocaleDateString() : 'Unknown'}
        </span>
        {reply.campaign_name && (
          <span className="flex items-center gap-1"><Hash className="w-3 h-3" />{reply.campaign_name}</span>
        )}
      </div>
    </div>
  );
}

// ---------- Reply Detail Panel ----------
interface ReplyDetailPanelProps {
  reply: ProcessedReply;
  onClose: () => void;
  onCopyDraft: () => void;
  onApprove: () => void;
  onDismiss: () => void;
}

function ReplyDetailPanel({ reply, onClose, onCopyDraft, onApprove, onDismiss }: ReplyDetailPanelProps) {
  const category = reply.category as ReplyCategory;
  const categoryConfig = category ? CATEGORY_CONFIG[category] : CATEGORY_CONFIG.other;
  const leadName = [reply.lead_first_name, reply.lead_last_name].filter(Boolean).join(' ') || reply.lead_email;

  // Conversation thread
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [loadingConversation, setLoadingConversation] = useState(false);

  useEffect(() => {
    setLoadingConversation(true);
    repliesApi.getConversation(reply.id)
      .then(data => setMessages(data.messages || []))
      .catch(() => setMessages([]))
      .finally(() => setLoadingConversation(false));
  }, [reply.id]);

  return (
    <div className="fixed inset-y-0 right-0 w-[520px] bg-white shadow-2xl border-l border-neutral-200 z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200">
        <h2 className="text-lg font-semibold">Reply Details</h2>
        <button onClick={onClose} className="p-2 hover:bg-neutral-100 rounded-lg"><X className="w-4 h-4" /></button>
      </div>

      <div className="flex-1 overflow-auto p-6 space-y-5">
        {/* Category */}
        <div className="flex items-center gap-2">
          <span className={cn("px-3 py-1 rounded-full text-sm font-medium border", categoryConfig.color)}>
            {categoryConfig.emoji} {categoryConfig.label}
          </span>
          {reply.category_confidence && <span className="text-sm text-neutral-500">{reply.category_confidence}</span>}
        </div>

        {/* Lead info */}
        <div className="p-4 bg-neutral-50 rounded-xl">
          <div className="font-medium text-neutral-900">{leadName}</div>
          <div className="text-sm text-neutral-600 mt-1">{reply.lead_email}</div>
          {reply.lead_company && (
            <div className="text-sm text-neutral-500 flex items-center gap-1 mt-1"><Building2 className="w-3 h-3" />{reply.lead_company}</div>
          )}
          {reply.inbox_link && (
            <a href={reply.inbox_link} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-1 text-sm text-violet-600 hover:underline">
              <ExternalLink className="w-3 h-3" />Open in Smartlead
            </a>
          )}
        </div>

        {/* Conversation Thread */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide flex items-center gap-1.5">
            <MessageCircle className="w-3.5 h-3.5" />Conversation
          </h4>
          {loadingConversation ? (
            <div className="flex items-center justify-center py-4">
              <RefreshCw className="w-4 h-4 animate-spin text-neutral-400" />
              <span className="ml-2 text-sm text-neutral-400">Loading...</span>
            </div>
          ) : messages.length === 0 ? (
            <div className="p-3 bg-neutral-50 rounded-lg text-sm text-neutral-400">No conversation history found</div>
          ) : (
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {messages.map((msg, i) => {
                const isInbound = msg.direction === 'inbound';
                return (
                  <div key={i} className={cn("flex", isInbound ? "justify-start" : "justify-end")}>
                    <div className={cn(
                      "max-w-[85%] rounded-xl px-3 py-2 text-sm",
                      isInbound
                        ? "bg-blue-50 border border-blue-100 text-blue-900"
                        : "bg-neutral-100 border border-neutral-200 text-neutral-800"
                    )}>
                      {msg.subject && <div className="font-medium text-xs mb-1 opacity-70">{msg.subject}</div>}
                      <div className="whitespace-pre-wrap text-sm leading-relaxed">{msg.body || '(no content)'}</div>
                      <div className="text-xs mt-1 opacity-50">
                        {msg.activity_at ? new Date(msg.activity_at).toLocaleString() : ''}
                        {msg.channel && ` · ${msg.channel}`}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Original reply */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">Original Reply</h4>
          <div className="p-4 bg-neutral-50 rounded-xl">
            <div className="text-sm font-medium text-neutral-700 mb-2">{reply.email_subject || '(no subject)'}</div>
            <div className="text-sm text-neutral-600 whitespace-pre-wrap">{reply.email_body || reply.reply_text || '(empty)'}</div>
          </div>
        </div>

        {/* AI Analysis */}
        {reply.classification_reasoning && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">AI Analysis</h4>
            <div className="p-4 bg-violet-50 rounded-xl border border-violet-100">
              <div className="text-sm text-violet-800">{reply.classification_reasoning}</div>
            </div>
          </div>
        )}

        {/* Draft reply */}
        {reply.draft_reply && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">Suggested Draft</h4>
              <button onClick={onCopyDraft} className="btn btn-secondary btn-sm"><Copy className="w-3 h-3" />Copy</button>
            </div>
            <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-100">
              {reply.draft_subject && <div className="text-sm font-medium text-emerald-800 mb-2">{reply.draft_subject}</div>}
              <div className="text-sm text-emerald-700 whitespace-pre-wrap">{reply.draft_reply}</div>
            </div>
          </div>
        )}

        {/* Metadata */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">Info</h4>
          <div className="text-sm space-y-1.5 text-neutral-600">
            <div className="flex justify-between"><span>Campaign:</span><span className="font-medium">{reply.campaign_name || reply.campaign_id || 'Unknown'}</span></div>
            <div className="flex justify-between"><span>Received:</span><span className="font-medium">{reply.received_at ? new Date(reply.received_at).toLocaleString() : 'Unknown'}</span></div>
            <div className="flex justify-between"><span>Processed:</span><span className="font-medium">{new Date(reply.processed_at).toLocaleString()}</span></div>
          </div>
        </div>
      </div>

      {/* Actions footer */}
      <div className="p-4 border-t border-neutral-200 space-y-2">
        {reply.approval_status === 'approved' && (
          <div className="flex items-center gap-2 px-3 py-2 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700 font-medium">
            <CheckCircle className="w-4 h-4" />Reply sent
            {reply.approved_at && <span className="text-xs text-emerald-500 ml-auto">{new Date(reply.approved_at).toLocaleString()}</span>}
          </div>
        )}
        {reply.approval_status === 'approved_dry_run' && (
          <div className="flex items-center gap-2 px-3 py-2 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700 font-medium">
            <CheckCircle className="w-4 h-4" />Approved (dry run)
          </div>
        )}
        {reply.approval_status === 'approved_test' && (
          <div className="flex items-center gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700 font-medium">
            <CheckCircle className="w-4 h-4" />Test sent to pn@getsally.io
            {reply.approved_at && <span className="text-xs text-amber-500 ml-auto">{new Date(reply.approved_at).toLocaleString()}</span>}
          </div>
        )}
        {reply.approval_status === 'dismissed' && (
          <div className="flex items-center gap-2 px-3 py-2 bg-neutral-50 border border-neutral-200 rounded-lg text-sm text-neutral-500 font-medium">
            <XCircle className="w-4 h-4" />Skipped
          </div>
        )}
        <div className="flex gap-2">
          {(!reply.approval_status || reply.approval_status === 'pending') && reply.draft_reply && (
            <button onClick={onApprove} className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-500 hover:bg-emerald-600 text-white rounded-lg font-semibold transition-colors">
              <CheckCircle className="w-4 h-4" />Approve & Send
            </button>
          )}
          {(!reply.approval_status || reply.approval_status === 'pending') && (
            <button onClick={onDismiss} className="flex items-center justify-center gap-2 px-4 py-2.5 border border-neutral-200 hover:border-red-300 hover:text-red-600 text-neutral-500 rounded-lg font-medium transition-colors">
              <XCircle className="w-4 h-4" />Skip
            </button>
          )}
          {reply.draft_reply && (
            <button onClick={onCopyDraft} className="btn btn-secondary flex-1"><Copy className="w-4 h-4" />Copy Draft</button>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------- Send Confirmation Dialog ----------
interface SendConfirmDialogProps {
  reply: ProcessedReply;
  isSending: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

function SendConfirmDialog({ reply, isSending, onConfirm, onCancel }: SendConfirmDialogProps) {
  const leadName = [reply.lead_first_name, reply.lead_last_name].filter(Boolean).join(' ') || reply.lead_email;
  const isLocal = typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1');

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onCancel} />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-neutral-200">
          <div className="flex items-center gap-3">
            <div className={cn("w-10 h-10 rounded-full flex items-center justify-center", isLocal ? "bg-amber-100" : "bg-emerald-100")}>
              <Send className={cn("w-5 h-5", isLocal ? "text-amber-600" : "text-emerald-600")} />
            </div>
            <div>
              <h3 className="font-semibold text-neutral-900">Confirm Send Reply</h3>
              {isLocal ? (
                <p className="text-xs text-amber-600 font-medium">TEST MODE — will send to pn@getsally.io, not the real lead</p>
              ) : (
                <p className="text-xs text-neutral-500">This will send a real email via Smartlead</p>
              )}
            </div>
          </div>
          <button onClick={onCancel} className="p-2 hover:bg-neutral-100 rounded-lg">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-4 max-h-[60vh] overflow-y-auto">
          {/* Recipient */}
          <div className="p-3 bg-neutral-50 rounded-xl">
            <div className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-1">Sending to</div>
            <div className="font-medium text-neutral-900">{leadName}</div>
            <div className="text-sm text-neutral-600">{reply.lead_email}</div>
            {reply.campaign_name && (
              <div className="text-xs text-neutral-400 mt-1 flex items-center gap-1">
                <Hash className="w-3 h-3" />{reply.campaign_name}
              </div>
            )}
          </div>

          {/* Draft preview */}
          <div>
            <div className="text-xs font-semibold text-neutral-500 uppercase tracking-wide mb-2">Draft reply that will be sent</div>
            <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-200">
              {reply.draft_subject && (
                <div className="text-sm font-semibold text-emerald-800 mb-2 pb-2 border-b border-emerald-200">
                  {reply.draft_subject}
                </div>
              )}
              <div className="text-sm text-emerald-700 whitespace-pre-wrap leading-relaxed max-h-[200px] overflow-y-auto">
                {reply.draft_reply || '(no draft)'}
              </div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3 p-5 border-t border-neutral-200">
          <button
            onClick={onCancel}
            disabled={isSending}
            className="px-4 py-2.5 border border-neutral-200 text-neutral-600 hover:bg-neutral-50 rounded-lg font-medium transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isSending}
            className="flex items-center gap-2 px-5 py-2.5 bg-emerald-500 hover:bg-emerald-600 disabled:bg-emerald-300 text-white rounded-lg font-semibold transition-colors"
          >
            {isSending ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Sending...
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                Send Reply
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default RepliesPage;
