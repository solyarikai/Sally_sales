import { useEffect, useState, useCallback } from 'react';
import { 
  MessageSquare, Search, RefreshCw, Plus, Settings2, 
  Send, Bell, X, Copy, ChevronDown, Check, AlertCircle,
  Zap, Hash, Calendar, Clock, ExternalLink, Mail, Building2,
  TestTube2
} from 'lucide-react';
import { 
  repliesApi, 
  type ProcessedReply, 
  type ProcessedReplyStats, 
  type ReplyAutomation,
  type ReplyCategory,
  type SmartleadCampaign,
  type ReplyAutomationCreate,
  type SimulateReplyPayload,
  type SimulateReplyResponse
} from '../api/replies';
import { cn, formatNumber } from '../lib/utils';
import { ConfirmDialog } from '../components/ConfirmDialog';

// Category configuration
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
  // Data state
  const [replies, setReplies] = useState<ProcessedReply[]>([]);
  const [stats, setStats] = useState<ProcessedReplyStats | null>(null);
  const [automations, setAutomations] = useState<ReplyAutomation[]>([]);
  const [campaigns, setCampaigns] = useState<SmartleadCampaign[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [campaignsLoading, setCampaignsLoading] = useState(false);
  const [smartleadError, setSmartleadError] = useState<string | null>(null);
  
  // Filters
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<ReplyCategory | null>(null);
  const [automationFilter, setAutomationFilter] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);
  
  // UI state
  const [selectedReply, setSelectedReply] = useState<ProcessedReply | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showTestModal, setShowTestModal] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({ isOpen: false, title: '', message: '', onConfirm: () => {} });

  // Load data
  const loadReplies = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await repliesApi.getReplies({
        automation_id: automationFilter || undefined,
        category: categoryFilter || undefined,
        page,
        page_size: pageSize,
      });
      setReplies(response.replies);
      setTotal(response.total);
    } catch (err) {
      console.error('Failed to load replies:', err);
    } finally {
      setIsLoading(false);
    }
  }, [automationFilter, categoryFilter, page, pageSize]);

  const loadStats = useCallback(async () => {
    try {
      const data = await repliesApi.getReplyStats({
        automation_id: automationFilter || undefined,
      });
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  }, [automationFilter]);

  const loadAutomations = useCallback(async () => {
    try {
      const data = await repliesApi.getAutomations(false);
      setAutomations(data);
    } catch (err) {
      console.error('Failed to load automations:', err);
    }
  }, []);

  const loadCampaigns = useCallback(async () => {
    setCampaignsLoading(true);
    setSmartleadError(null);
    try {
      const data = await repliesApi.getSmartleadCampaigns();
      setCampaigns(data);
    } catch (err: any) {
      console.error('Failed to load campaigns:', err);
      setSmartleadError(err.response?.data?.detail || 'Failed to load Smartlead campaigns. Check API key in Settings.');
    } finally {
      setCampaignsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadReplies();
    loadStats();
  }, [loadReplies, loadStats]);

  useEffect(() => {
    loadAutomations();
  }, [loadAutomations]);

  const handleRefresh = () => {
    loadReplies();
    loadStats();
    loadAutomations();
  };

  const handleCopyDraft = async (reply: ProcessedReply) => {
    if (reply.draft_reply) {
      await navigator.clipboard.writeText(reply.draft_reply);
      alert('Draft copied to clipboard!');
    }
  };

  const handleResendNotification = async (replyId: number) => {
    try {
      const result = await repliesApi.resendNotification(replyId);
      if (result.success) {
        alert('Notification sent!');
        loadReplies();
      } else {
        alert(`Failed: ${result.message}`);
      }
    } catch (err) {
      console.error('Failed to resend notification:', err);
      alert('Failed to send notification');
    }
  };

  const handleDeleteAutomation = async (automation: ReplyAutomation) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Delete Automation',
      message: `Are you sure you want to delete "${automation.name}"? This cannot be undone.`,
      onConfirm: async () => {
        try {
          await repliesApi.deleteAutomation(automation.id);
          loadAutomations();
        } catch (err) {
          console.error('Failed to delete automation:', err);
        }
        setConfirmDialog(prev => ({ ...prev, isOpen: false }));
      }
    });
  };

  const handleToggleAutomation = async (automation: ReplyAutomation) => {
    try {
      await repliesApi.updateAutomation(automation.id, { active: !automation.active });
      loadAutomations();
    } catch (err) {
      console.error('Failed to toggle automation:', err);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  // Filter replies by search
  const filteredReplies = replies.filter(reply => {
    if (!search) return true;
    const searchLower = search.toLowerCase();
    return (
      reply.lead_email?.toLowerCase().includes(searchLower) ||
      reply.lead_first_name?.toLowerCase().includes(searchLower) ||
      reply.lead_last_name?.toLowerCase().includes(searchLower) ||
      reply.lead_company?.toLowerCase().includes(searchLower) ||
      reply.email_subject?.toLowerCase().includes(searchLower)
    );
  });

  return (
    <div className="h-full flex flex-col bg-neutral-50">
      {/* Header */}
      <div className="bg-white border-b border-neutral-200 px-6 py-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
              <MessageSquare className="w-5 h-5 text-violet-600" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-neutral-900">Email Replies</h1>
              <p className="text-sm text-neutral-500">
                {formatNumber(total)} replies processed
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button onClick={handleRefresh} className="btn btn-secondary btn-sm">
              <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
            </button>
            <button onClick={() => setShowTestModal(true)} className="btn btn-secondary">
              <TestTube2 className="w-4 h-4" />
              Test Reply
            </button>
            <button onClick={() => { loadCampaigns(); setShowCreateModal(true); }} className="btn btn-primary">
              <Plus className="w-4 h-4" />
              New Automation
            </button>
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="flex items-center gap-2 flex-wrap mb-4">
            <StatCard label="Total" value={formatNumber(stats.total)} />
            <StatCard label="Today" value={formatNumber(stats.today)} color="blue" />
            <StatCard label="This Week" value={formatNumber(stats.this_week)} color="purple" />
            {Object.entries(stats.by_category).slice(0, 5).map(([cat, count]) => {
              const config = CATEGORY_CONFIG[cat as ReplyCategory];
              return (
                <StatCard 
                  key={cat} 
                  label={config?.label || cat} 
                  value={formatNumber(count)} 
                  emoji={config?.emoji}
                />
              );
            })}
          </div>
        )}

        {/* Filters */}
        <div className="flex items-center gap-3">
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
            value={automationFilter || ''}
            onChange={(e) => { setAutomationFilter(e.target.value ? parseInt(e.target.value) : null); setPage(1); }}
            className="input text-sm"
          >
            <option value="">All Automations</option>
            {automations.map(a => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Content - 2 columns: Automations + Replies */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left sidebar - Automations */}
        <div className="w-80 border-r border-neutral-200 bg-white overflow-auto">
          <div className="p-4 border-b border-neutral-200">
            <h2 className="text-sm font-semibold text-neutral-700 flex items-center gap-2">
              <Zap className="w-4 h-4" />
              Reply Automations
            </h2>
          </div>
          
          {automations.length === 0 ? (
            <div className="p-6 text-center">
              <div className="w-12 h-12 rounded-xl bg-neutral-100 flex items-center justify-center mx-auto mb-3">
                <Settings2 className="w-6 h-6 text-neutral-400" />
              </div>
              <p className="text-sm text-neutral-500 mb-3">No automations yet</p>
              <button 
                onClick={() => { loadCampaigns(); setShowCreateModal(true); }}
                className="btn btn-primary btn-sm"
              >
                <Plus className="w-4 h-4" />
                Create First
              </button>
            </div>
          ) : (
            <div className="divide-y divide-neutral-100">
              {automations.map(automation => (
                <div 
                  key={automation.id} 
                  className={cn(
                    "p-4 hover:bg-neutral-50 cursor-pointer",
                    automationFilter === automation.id && "bg-violet-50"
                  )}
                  onClick={() => setAutomationFilter(automationFilter === automation.id ? null : automation.id)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={cn(
                          "w-2 h-2 rounded-full",
                          automation.active ? "bg-emerald-500" : "bg-neutral-300"
                        )} />
                        <span className="font-medium text-sm truncate">{automation.name}</span>
                      </div>
                      <div className="text-xs text-neutral-500 mt-1">
                        {automation.campaign_ids.length} campaign{automation.campaign_ids.length !== 1 ? 's' : ''}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleToggleAutomation(automation); }}
                        className={cn(
                          "p-1.5 rounded-lg transition-colors",
                          automation.active ? "text-emerald-600 hover:bg-emerald-50" : "text-neutral-400 hover:bg-neutral-100"
                        )}
                        title={automation.active ? 'Deactivate' : 'Activate'}
                      >
                        <Zap className="w-4 h-4" />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteAutomation(automation); }}
                        className="p-1.5 rounded-lg text-neutral-400 hover:bg-red-50 hover:text-red-500"
                        title="Delete"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  {automation.slack_webhook_url && (
                    <div className="flex items-center gap-1 text-xs text-neutral-500 mt-2">
                      <Bell className="w-3 h-3" />
                      Slack notifications enabled
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Main content - Replies list */}
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
                Replies will appear here when your campaigns receive responses
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredReplies.map(reply => (
                <ReplyCard 
                  key={reply.id} 
                  reply={reply}
                  onClick={() => setSelectedReply(reply)}
                  onCopyDraft={() => handleCopyDraft(reply)}
                  onResend={() => handleResendNotification(reply.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="bg-white border-t border-neutral-200 px-6 py-3 flex items-center justify-between">
          <div className="text-sm text-neutral-500">
            Page {page} of {totalPages}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn btn-secondary btn-sm"
            >
              Prev
            </button>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="btn btn-secondary btn-sm"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Reply Detail Panel */}
      {selectedReply && (
        <ReplyDetailPanel 
          reply={selectedReply} 
          onClose={() => setSelectedReply(null)}
          onCopyDraft={() => handleCopyDraft(selectedReply)}
          onResend={() => handleResendNotification(selectedReply.id)}
        />
      )}

      {/* Create Automation Modal */}
      {showCreateModal && (
        <CreateAutomationModal
          campaigns={campaigns}
          campaignsLoading={campaignsLoading}
          smartleadError={smartleadError}
          onClose={() => setShowCreateModal(false)}
          onCreated={() => {
            setShowCreateModal(false);
            loadAutomations();
          }}
          onRetryCampaigns={loadCampaigns}
        />
      )}

      {/* Test Reply Modal */}
      {showTestModal && (
        <TestReplyModal
          onClose={() => setShowTestModal(false)}
          onSuccess={() => {
            setShowTestModal(false);
            handleRefresh();
          }}
        />
      )}

      {/* Confirm Dialog */}
      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        title={confirmDialog.title}
        message={confirmDialog.message}
        onConfirm={confirmDialog.onConfirm}
        onCancel={() => setConfirmDialog(prev => ({ ...prev, isOpen: false }))}
      />
    </div>
  );
}

// Stat card component
function StatCard({ label, value, color, emoji }: { label: string; value: string; color?: string; emoji?: string }) {
  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-50 border-blue-200',
    purple: 'bg-purple-50 border-purple-200',
    green: 'bg-emerald-50 border-emerald-200',
  };
  
  return (
    <div className={cn(
      "rounded-lg px-3 py-2 border",
      color ? colorClasses[color] || 'bg-neutral-50 border-neutral-100' : 'bg-neutral-50 border-neutral-100'
    )}>
      <div className="flex items-center gap-2">
        {emoji && <span className="text-lg">{emoji}</span>}
        <div className="text-lg font-semibold text-neutral-900">{value}</div>
      </div>
      <div className="text-xs text-neutral-500">{label}</div>
    </div>
  );
}

// Reply card component
interface ReplyCardProps {
  reply: ProcessedReply;
  onClick: () => void;
  onCopyDraft: () => void;
  onResend: () => void;
}

function ReplyCard({ reply, onClick, onCopyDraft, onResend }: ReplyCardProps) {
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
          {/* Header row */}
          <div className="flex items-center gap-2 mb-2">
            <span className={cn(
              "px-2 py-0.5 rounded-full text-xs font-medium border",
              categoryConfig.color
            )}>
              {categoryConfig.emoji} {categoryConfig.label}
            </span>
            {reply.category_confidence && (
              <span className="text-xs text-neutral-400">
                {reply.category_confidence} confidence
              </span>
            )}
            {reply.sent_to_slack && (
              <span className="text-xs text-emerald-600 flex items-center gap-1">
                <Check className="w-3 h-3" />
                Slack sent
              </span>
            )}
          </div>
          
          {/* Lead info */}
          <div className="flex items-center gap-3 mb-1">
            <span className="font-medium text-neutral-900">{leadName}</span>
            {reply.lead_company && (
              <span className="text-sm text-neutral-500 flex items-center gap-1">
                <Building2 className="w-3 h-3" />
                {reply.lead_company}
              </span>
            )}
          </div>
          
          {/* Subject */}
          <div className="text-sm text-neutral-600 mb-2">
            <strong>Subject:</strong> {reply.email_subject || '(no subject)'}
          </div>
          
          {/* Body preview */}
          <div className="text-sm text-neutral-500 line-clamp-2">
            {reply.email_body || reply.reply_text || '(empty)'}
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-1">
          {reply.draft_reply && (
            <button
              onClick={(e) => { e.stopPropagation(); onCopyDraft(); }}
              className="btn btn-secondary btn-sm"
              title="Copy draft reply"
            >
              <Copy className="w-4 h-4" />
            </button>
          )}
          {!reply.sent_to_slack && (
            <button
              onClick={(e) => { e.stopPropagation(); onResend(); }}
              className="btn btn-secondary btn-sm"
              title="Send to Slack"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="flex items-center gap-4 mt-3 pt-3 border-t border-neutral-100 text-xs text-neutral-400">
        <span className="flex items-center gap-1">
          <Calendar className="w-3 h-3" />
          {reply.received_at ? new Date(reply.received_at).toLocaleDateString() : 'Unknown date'}
        </span>
        {reply.campaign_name && (
          <span className="flex items-center gap-1">
            <Hash className="w-3 h-3" />
            {reply.campaign_name}
          </span>
        )}
      </div>
    </div>
  );
}

// Reply detail panel
interface ReplyDetailPanelProps {
  reply: ProcessedReply;
  onClose: () => void;
  onCopyDraft: () => void;
  onResend: () => void;
}

function ReplyDetailPanel({ reply, onClose, onCopyDraft, onResend }: ReplyDetailPanelProps) {
  const category = reply.category as ReplyCategory;
  const categoryConfig = category ? CATEGORY_CONFIG[category] : CATEGORY_CONFIG.other;
  const leadName = [reply.lead_first_name, reply.lead_last_name].filter(Boolean).join(' ') || reply.lead_email;

  return (
    <div className="fixed inset-y-0 right-0 w-[500px] bg-white shadow-2xl border-l border-neutral-200 z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200">
        <h2 className="text-lg font-semibold">Reply Details</h2>
        <button onClick={onClose} className="p-2 hover:bg-neutral-100 rounded-lg">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-auto p-6 space-y-6">
        {/* Category badge */}
        <div className="flex items-center gap-2">
          <span className={cn(
            "px-3 py-1 rounded-full text-sm font-medium border",
            categoryConfig.color
          )}>
            {categoryConfig.emoji} {categoryConfig.label}
          </span>
          {reply.category_confidence && (
            <span className="text-sm text-neutral-500">
              {reply.category_confidence} confidence
            </span>
          )}
        </div>

        {/* Lead info */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">From</h4>
          <div className="p-4 bg-neutral-50 rounded-xl">
            <div className="font-medium text-neutral-900">{leadName}</div>
            <div className="text-sm text-neutral-600 mt-1">{reply.lead_email}</div>
            {reply.lead_company && (
              <div className="text-sm text-neutral-500 flex items-center gap-1 mt-1">
                <Building2 className="w-3 h-3" />
                {reply.lead_company}
              </div>
            )}
          </div>
        </div>

        {/* Original message */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">Original Reply</h4>
          <div className="p-4 bg-neutral-50 rounded-xl">
            <div className="text-sm font-medium text-neutral-700 mb-2">
              {reply.email_subject || '(no subject)'}
            </div>
            <div className="text-sm text-neutral-600 whitespace-pre-wrap">
              {reply.email_body || reply.reply_text || '(empty)'}
            </div>
          </div>
        </div>

        {/* AI Classification reasoning */}
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
              <button onClick={onCopyDraft} className="btn btn-secondary btn-sm">
                <Copy className="w-3 h-3" />
                Copy
              </button>
            </div>
            <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-100">
              {reply.draft_subject && (
                <div className="text-sm font-medium text-emerald-800 mb-2">
                  {reply.draft_subject}
                </div>
              )}
              <div className="text-sm text-emerald-700 whitespace-pre-wrap">
                {reply.draft_reply}
              </div>
            </div>
          </div>
        )}

        {/* Metadata */}
        <div className="space-y-2">
          <h4 className="text-xs font-semibold text-neutral-500 uppercase tracking-wide">Info</h4>
          <div className="text-sm space-y-2 text-neutral-600">
            <div className="flex justify-between">
              <span>Campaign:</span>
              <span className="font-medium">{reply.campaign_name || reply.campaign_id || 'Unknown'}</span>
            </div>
            <div className="flex justify-between">
              <span>Received:</span>
              <span className="font-medium">
                {reply.received_at ? new Date(reply.received_at).toLocaleString() : 'Unknown'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Processed:</span>
              <span className="font-medium">
                {new Date(reply.processed_at).toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Slack:</span>
              <span className={cn("font-medium", reply.sent_to_slack ? "text-emerald-600" : "text-neutral-400")}>
                {reply.sent_to_slack ? 'Sent' : 'Not sent'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="p-4 border-t border-neutral-200 flex gap-2">
        {reply.draft_reply && (
          <button onClick={onCopyDraft} className="btn btn-primary flex-1">
            <Copy className="w-4 h-4" />
            Copy Draft
          </button>
        )}
        {!reply.sent_to_slack && (
          <button onClick={onResend} className="btn btn-secondary flex-1">
            <Send className="w-4 h-4" />
            Send to Slack
          </button>
        )}
      </div>
    </div>
  );
}

// Create Automation Modal
interface CreateAutomationModalProps {
  campaigns: SmartleadCampaign[];
  campaignsLoading: boolean;
  smartleadError: string | null;
  onClose: () => void;
  onCreated: () => void;
  onRetryCampaigns: () => void;
}

function CreateAutomationModal({ 
  campaigns, 
  campaignsLoading, 
  smartleadError,
  onClose, 
  onCreated,
  onRetryCampaigns 
}: CreateAutomationModalProps) {
  const [step, setStep] = useState(1);
  const [name, setName] = useState('');
  const [selectedCampaigns, setSelectedCampaigns] = useState<string[]>([]);
  const [slackWebhook, setSlackWebhook] = useState('');
  const [slackChannel, setSlackChannel] = useState('');
  const [autoClassify, setAutoClassify] = useState(true);
  const [autoGenerateReply, setAutoGenerateReply] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [searchCampaigns, setSearchCampaigns] = useState('');
  const [testResult, setTestResult] = useState<{success: boolean; message: string} | null>(null);

  const filteredCampaigns = campaigns.filter(c => 
    c.name?.toLowerCase().includes(searchCampaigns.toLowerCase()) ||
    c.id?.toLowerCase().includes(searchCampaigns.toLowerCase())
  );

  const handleCreate = async () => {
    if (!name || selectedCampaigns.length === 0) return;
    
    setIsCreating(true);
    try {
      const data: ReplyAutomationCreate = {
        name,
        campaign_ids: selectedCampaigns,
        slack_webhook_url: slackWebhook || undefined,
        slack_channel: slackChannel || undefined,
        auto_classify: autoClassify,
        auto_generate_reply: autoGenerateReply,
        active: true,
      };
      
      await repliesApi.createAutomation(data);
      onCreated();
    } catch (err) {
      console.error('Failed to create automation:', err);
      alert('Failed to create automation');
    } finally {
      setIsCreating(false);
    }
  };

  const handleTestWebhook = async () => {
    if (!slackWebhook) return;
    
    // For testing, we need to create a temporary automation or call test endpoint directly
    // For now, just validate the URL format
    if (!slackWebhook.startsWith('https://hooks.slack.com/')) {
      setTestResult({ success: false, message: 'Invalid Slack webhook URL format' });
      return;
    }
    setTestResult({ success: true, message: 'URL format looks valid. Test after creation.' });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
              <Zap className="w-5 h-5 text-violet-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">Create Reply Automation</h2>
              <p className="text-sm text-neutral-500">Step {step} of 3</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-neutral-100 rounded-lg">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {step === 1 && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Automation Name
                </label>
                <input
                  type="text"
                  placeholder="e.g., Sales Campaign Replies"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="input w-full"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Select Smartlead Campaigns
                </label>
                
                {smartleadError ? (
                  <div className="p-4 bg-red-50 border border-red-100 rounded-xl">
                    <div className="flex items-start gap-3">
                      <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                      <div>
                        <p className="text-sm text-red-700">{smartleadError}</p>
                        <button 
                          onClick={onRetryCampaigns}
                          className="text-sm text-red-600 underline mt-2"
                        >
                          Retry
                        </button>
                      </div>
                    </div>
                  </div>
                ) : campaignsLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <RefreshCw className="w-5 h-5 animate-spin text-neutral-400" />
                    <span className="ml-2 text-sm text-neutral-500">Loading campaigns...</span>
                  </div>
                ) : (
                  <>
                    <div className="relative mb-2">
                      <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
                      <input
                        type="text"
                        placeholder="Search campaigns..."
                        value={searchCampaigns}
                        onChange={(e) => setSearchCampaigns(e.target.value)}
                        className="input pl-9 w-full text-sm"
                      />
                    </div>
                    
                    <div className="border border-neutral-200 rounded-xl max-h-60 overflow-auto">
                      {filteredCampaigns.length === 0 ? (
                        <div className="p-4 text-center text-neutral-500 text-sm">
                          No campaigns found
                        </div>
                      ) : (
                        filteredCampaigns.map(campaign => (
                          <label 
                            key={campaign.id}
                            className="flex items-center gap-3 p-3 hover:bg-neutral-50 cursor-pointer border-b border-neutral-100 last:border-b-0"
                          >
                            <input
                              type="checkbox"
                              checked={selectedCampaigns.includes(campaign.id)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedCampaigns([...selectedCampaigns, campaign.id]);
                                } else {
                                  setSelectedCampaigns(selectedCampaigns.filter(id => id !== campaign.id));
                                }
                              }}
                              className="rounded"
                            />
                            <div className="flex-1 min-w-0">
                              <div className="text-sm font-medium truncate">{campaign.name || campaign.id}</div>
                              {campaign.status && (
                                <div className="text-xs text-neutral-400">{campaign.status}</div>
                              )}
                            </div>
                          </label>
                        ))
                      )}
                    </div>
                    {selectedCampaigns.length > 0 && (
                      <div className="text-sm text-neutral-500 mt-2">
                        {selectedCampaigns.length} campaign{selectedCampaigns.length !== 1 ? 's' : ''} selected
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Slack Webhook URL (optional)
                </label>
                <input
                  type="url"
                  placeholder="https://hooks.slack.com/services/..."
                  value={slackWebhook}
                  onChange={(e) => { setSlackWebhook(e.target.value); setTestResult(null); }}
                  className="input w-full"
                />
                <p className="text-xs text-neutral-400 mt-1">
                  Get this from Slack App settings &gt; Incoming Webhooks
                </p>
                {slackWebhook && (
                  <button 
                    onClick={handleTestWebhook}
                    className="text-sm text-violet-600 mt-2"
                  >
                    Test webhook
                  </button>
                )}
                {testResult && (
                  <div className={cn(
                    "mt-2 text-sm",
                    testResult.success ? "text-emerald-600" : "text-red-600"
                  )}>
                    {testResult.message}
                  </div>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Slack Channel (optional)
                </label>
                <input
                  type="text"
                  placeholder="#sales-replies"
                  value={slackChannel}
                  onChange={(e) => setSlackChannel(e.target.value)}
                  className="input w-full"
                />
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-6">
              <div className="text-center py-4">
                <div className="w-16 h-16 rounded-xl bg-violet-100 flex items-center justify-center mx-auto mb-4">
                  <Check className="w-8 h-8 text-violet-600" />
                </div>
                <h3 className="text-lg font-semibold mb-2">Review & Create</h3>
              </div>

              <div className="space-y-4 p-4 bg-neutral-50 rounded-xl">
                <div className="flex justify-between">
                  <span className="text-neutral-600">Name</span>
                  <span className="font-medium">{name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">Campaigns</span>
                  <span className="font-medium">{selectedCampaigns.length} selected</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-neutral-600">Slack</span>
                  <span className="font-medium">{slackWebhook ? 'Enabled' : 'Not configured'}</span>
                </div>
              </div>

              <div className="space-y-3">
                <label className="flex items-center gap-3 p-3 bg-neutral-50 rounded-xl cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoClassify}
                    onChange={(e) => setAutoClassify(e.target.checked)}
                    className="rounded"
                  />
                  <div>
                    <div className="text-sm font-medium">Auto-classify replies</div>
                    <div className="text-xs text-neutral-500">Use AI to categorize incoming replies</div>
                  </div>
                </label>
                
                <label className="flex items-center gap-3 p-3 bg-neutral-50 rounded-xl cursor-pointer">
                  <input
                    type="checkbox"
                    checked={autoGenerateReply}
                    onChange={(e) => setAutoGenerateReply(e.target.checked)}
                    className="rounded"
                  />
                  <div>
                    <div className="text-sm font-medium">Generate draft replies</div>
                    <div className="text-xs text-neutral-500">AI will suggest response drafts</div>
                  </div>
                </label>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-neutral-200 flex gap-3">
          {step > 1 && (
            <button 
              onClick={() => setStep(s => s - 1)}
              className="btn btn-secondary flex-1"
            >
              Back
            </button>
          )}
          {step < 3 ? (
            <button 
              onClick={() => setStep(s => s + 1)}
              disabled={step === 1 && (!name || selectedCampaigns.length === 0)}
              className="btn btn-primary flex-1"
            >
              Continue
            </button>
          ) : (
            <button 
              onClick={handleCreate}
              disabled={isCreating}
              className="btn btn-primary flex-1"
            >
              {isCreating ? 'Creating...' : 'Create Automation'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// Test Reply Modal
interface TestReplyModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

function TestReplyModal({ onClose, onSuccess }: TestReplyModalProps) {
  const [formData, setFormData] = useState<SimulateReplyPayload>({
    lead_email: 'test@example.com',
    first_name: 'John',
    last_name: 'Doe',
    company_name: 'Acme Corp',
    email_subject: 'Re: Your offer',
    email_body: "I'm interested in learning more about your services. Could you tell me more about pricing?"
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<SimulateReplyResponse | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.lead_email || !formData.email_body) return;

    setIsSubmitting(true);
    setResult(null);
    
    try {
      const response = await repliesApi.simulateReply(formData);
      setResult(response);
    } catch (err: any) {
      setResult({ 
        success: false, 
        error: err.response?.data?.detail || err.message || 'Failed to simulate reply'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const categoryConfig = result?.category ? CATEGORY_CONFIG[result.category] : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-100 flex items-center justify-center">
              <TestTube2 className="w-5 h-5 text-cyan-600" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">Test Reply Classification</h2>
              <p className="text-sm text-neutral-500">Simulate an incoming email reply</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-neutral-100 rounded-lg">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Email *
                </label>
                <input
                  type="email"
                  value={formData.lead_email}
                  onChange={(e) => setFormData(prev => ({ ...prev, lead_email: e.target.value }))}
                  className="input w-full"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Company
                </label>
                <input
                  type="text"
                  value={formData.company_name || ''}
                  onChange={(e) => setFormData(prev => ({ ...prev, company_name: e.target.value }))}
                  className="input w-full"
                />
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  First Name
                </label>
                <input
                  type="text"
                  value={formData.first_name || ''}
                  onChange={(e) => setFormData(prev => ({ ...prev, first_name: e.target.value }))}
                  className="input w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Last Name
                </label>
                <input
                  type="text"
                  value={formData.last_name || ''}
                  onChange={(e) => setFormData(prev => ({ ...prev, last_name: e.target.value }))}
                  className="input w-full"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">
                Subject
              </label>
              <input
                type="text"
                value={formData.email_subject || ''}
                onChange={(e) => setFormData(prev => ({ ...prev, email_subject: e.target.value }))}
                className="input w-full"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">
                Reply Body *
              </label>
              <textarea
                value={formData.email_body}
                onChange={(e) => setFormData(prev => ({ ...prev, email_body: e.target.value }))}
                className="input w-full h-32 resize-none"
                placeholder="Enter the email reply text to classify..."
                required
              />
            </div>

            {/* Quick test examples */}
            <div className="flex flex-wrap gap-2">
              <span className="text-xs text-neutral-500">Quick tests:</span>
              <button
                type="button"
                onClick={() => setFormData(prev => ({ 
                  ...prev, 
                  email_body: "I'm interested in learning more about your services. Could you send me pricing information?"
                }))}
                className="text-xs px-2 py-1 bg-emerald-50 text-emerald-600 rounded hover:bg-emerald-100"
              >
                Interested
              </button>
              <button
                type="button"
                onClick={() => setFormData(prev => ({ 
                  ...prev, 
                  email_body: "Can we schedule a call this week? I'd like to discuss this further."
                }))}
                className="text-xs px-2 py-1 bg-blue-50 text-blue-600 rounded hover:bg-blue-100"
              >
                Meeting Request
              </button>
              <button
                type="button"
                onClick={() => setFormData(prev => ({ 
                  ...prev, 
                  email_body: "Thanks for reaching out, but we're not interested at this time."
                }))}
                className="text-xs px-2 py-1 bg-red-50 text-red-600 rounded hover:bg-red-100"
              >
                Not Interested
              </button>
              <button
                type="button"
                onClick={() => setFormData(prev => ({ 
                  ...prev, 
                  email_body: "I'm currently out of the office until next Monday. I'll respond when I return."
                }))}
                className="text-xs px-2 py-1 bg-amber-50 text-amber-600 rounded hover:bg-amber-100"
              >
                Out of Office
              </button>
              <button
                type="button"
                onClick={() => setFormData(prev => ({ 
                  ...prev, 
                  email_body: "Please remove me from your mailing list. Unsubscribe."
                }))}
                className="text-xs px-2 py-1 bg-neutral-100 text-neutral-600 rounded hover:bg-neutral-200"
              >
                Unsubscribe
              </button>
            </div>

            <button 
              type="submit"
              disabled={isSubmitting || !formData.email_body}
              className="btn btn-primary w-full"
            >
              {isSubmitting ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <TestTube2 className="w-4 h-4" />
                  Classify Reply
                </>
              )}
            </button>
          </form>

          {/* Results */}
          {result && (
            <div className="mt-6 space-y-4">
              <div className="border-t border-neutral-200 pt-4">
                <h3 className="font-semibold text-neutral-900 mb-3">Classification Result</h3>
                
                {result.success ? (
                  <div className="space-y-4">
                    {/* Category badge */}
                    <div className="flex items-center gap-3">
                      <span className={cn(
                        "px-3 py-1.5 rounded-full text-sm font-medium border",
                        categoryConfig?.color || 'bg-neutral-100'
                      )}>
                        {categoryConfig?.emoji} {categoryConfig?.label || result.category}
                      </span>
                      <span className="text-sm text-neutral-500">
                        {result.confidence} confidence
                      </span>
                    </div>

                    {/* Reasoning */}
                    {result.reasoning && (
                      <div className="p-3 bg-violet-50 rounded-xl border border-violet-100">
                        <div className="text-xs font-medium text-violet-600 mb-1">AI Reasoning</div>
                        <div className="text-sm text-violet-800">{result.reasoning}</div>
                      </div>
                    )}

                    {/* Draft reply */}
                    {result.draft_reply && (
                      <div className="p-3 bg-emerald-50 rounded-xl border border-emerald-100">
                        <div className="text-xs font-medium text-emerald-600 mb-1">Suggested Draft</div>
                        {result.draft_subject && (
                          <div className="text-sm font-medium text-emerald-800 mb-1">{result.draft_subject}</div>
                        )}
                        <div className="text-sm text-emerald-700 whitespace-pre-wrap">{result.draft_reply}</div>
                      </div>
                    )}

                    <div className="flex items-center justify-between text-sm text-neutral-500">
                      <span>Reply ID: {result.reply_id}</span>
                      {result.sent_to_slack && (
                        <span className="flex items-center gap-1 text-emerald-600">
                          <Check className="w-3 h-3" />
                          Sent to Slack
                        </span>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="p-4 bg-red-50 border border-red-100 rounded-xl">
                    <div className="flex items-start gap-3">
                      <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                      <div>
                        <div className="font-medium text-red-700">Classification Failed</div>
                        <div className="text-sm text-red-600">{result.error || result.message}</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-neutral-200 flex gap-3">
          <button onClick={onClose} className="btn btn-secondary flex-1">
            Close
          </button>
          {result?.success && (
            <button onClick={onSuccess} className="btn btn-primary flex-1">
              View in Dashboard
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default RepliesPage;
