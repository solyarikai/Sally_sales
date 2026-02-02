import { useEffect, useState, useCallback } from 'react';
import { 
  MessageSquare, Search, RefreshCw, Plus, Settings2, 
  Send, Bell, X, Copy, Check, AlertCircle,
  Zap, Hash, Calendar, Mail, Building2,
  TestTube2, FileSpreadsheet, SkipForward, ExternalLink, Pencil
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
  type SimulateReplyResponse,
  type GoogleSheetsStatus
} from '../api/replies';
import { cn, formatNumber } from '../lib/utils';
import { ConfirmDialog } from '../components/ConfirmDialog';

// Category configuration
// Helper function to extract Google Sheet ID from URL
const extractSheetId = (url: string): string => {
  if (!url) return "";
  const match = url.match(/spreadsheets\/d\/([a-zA-Z0-9-_]+)/);
  if (match) return match[1];
  if (url.match(/^[a-zA-Z0-9-_]+$/)) return url;
  return url;
};

// Helper function to extract gid (tab ID) from Google Sheet URL
const extractSheetGid = (url: string): string | null => {
  if (!url) return null;
  const match = url.match(/[?&#]gid=(\d+)/);
  return match ? match[1] : null;
};

// Helper to create sheet name with gid for storage (format: "TabName#gid")
const createSheetNameWithGid = (url: string): string | undefined => {
  const gid = extractSheetGid(url);
  return gid ? `Replies#${gid}` : undefined;  // Default tab name + gid
};

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
  const [editingAutomation, setEditingAutomation] = useState<ReplyAutomation | null>(null);
  const [isEditMode, setIsEditMode] = useState(false);
  const [editGoogleSheetUrl, setEditGoogleSheetUrl] = useState('');
  const [editNewChannelName, setEditNewChannelName] = useState('');
  const [editCreatingChannel, setEditCreatingChannel] = useState(false);
  const [editCreatingSheet, setEditCreatingSheet] = useState(false);
  const [editSheetName, setEditSheetName] = useState('');
  const [editSlackChannel, setEditSlackChannel] = useState('');
  const [editCampaigns, setEditCampaigns] = useState<string[]>([]);
  const [editCampaignSearch, setEditCampaignSearch] = useState('');
  const [editClassificationPrompt, setEditClassificationPrompt] = useState('');
  const [editReplyPrompt, setEditReplyPrompt] = useState('');
  const [slackChannelsEdit, setSlackChannelsEdit] = useState<Array<{id: string, name: string}>>([]);
  const [promptTestText, setPromptTestText] = useState('');
  const [promptTestResult, setPromptTestResult] = useState<{category?: string, reply?: string} | null>(null);
  const [testingPrompt, setTestingPrompt] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);
  const [showTestModal, setShowTestModal] = useState(false);
  const [showTestFlowModal, setShowTestFlowModal] = useState(false);
  const [testFlowStep, setTestFlowStep] = useState(1);
  const [testEmailAccounts, setTestEmailAccounts] = useState<Array<{id: number, email: string, name: string, remaining: number}>>([]);
  const [selectedEmailAccount, setSelectedEmailAccount] = useState<number | null>(null);
  const [testUserEmail, setTestUserEmail] = useState('');
  const [testUserName, setTestUserName] = useState('');
  const [testCampaignResult, setTestCampaignResult] = useState<{campaign_id?: string, campaign_name?: string, message?: string} | null>(null);
  const [testFlowLoading, setTestFlowLoading] = useState(false);
  const [testCampaigns, setTestCampaigns] = useState<Array<{id: string, name: string, status: string}>>([]);
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

  const loadSlackChannels = useCallback(async () => {
    try {
      const response = await repliesApi.getSlackChannels();
      setSlackChannelsEdit(response.channels || []);
    } catch (err) {
      console.error("Failed to load slack channels:", err);
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
    loadSlackChannels();  // Load for channel name display in sidebar
    loadCampaigns();  // Load for campaign name display in sidebar
  }, [loadAutomations, loadSlackChannels, loadCampaigns]);

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
            <button onClick={async () => {
              setShowTestFlowModal(true);
              setTestFlowStep(1);
              try {
                const [accountsData, campaignsData] = await Promise.all([
                  repliesApi.getTestEmailAccounts(),
                  repliesApi.getTestCampaigns()
                ]);
                setTestEmailAccounts(accountsData.accounts || []);
                setTestCampaigns(campaignsData.campaigns || []);
              } catch (e) { console.error(e); }
            }} className="btn btn-secondary">
              <TestTube2 className="w-4 h-4" />
              Test Flow
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
                      <div 
                        className="text-xs text-neutral-500 mt-1 cursor-help relative group"
                        title={automation.campaign_ids.map(id => campaigns.find(c => String(c.id) === String(id))?.name || id).join(', ')}
                      >
                        {automation.campaign_ids.length} campaign{automation.campaign_ids.length !== 1 ? 's' : ''}
                        {/* Hover tooltip with campaign names */}
                        <div className="absolute left-0 top-full mt-1 z-50 hidden group-hover:block bg-neutral-800 text-white text-xs rounded-lg py-2 px-3 shadow-lg min-w-[200px] max-w-[300px]">
                          <div className="font-medium mb-1">Campaigns:</div>
                          {automation.campaign_ids.map(id => (
                            <div key={id} className="truncate py-0.5">{campaigns.find(c => String(c.id) === String(id))?.name || id}</div>
                          ))}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => { e.stopPropagation(); setEditingAutomation(automation); setEditCampaigns(automation.campaign_ids?.map(String) || []); setEditSlackChannel(automation.slack_channel || ""); setEditGoogleSheetUrl(automation.google_sheet_id ? `https://docs.google.com/spreadsheets/d/${automation.google_sheet_id}${automation.google_sheet_name?.includes('#') ? '/edit?gid=' + automation.google_sheet_name.split('#')[1] + '#gid=' + automation.google_sheet_name.split('#')[1] : ''}` : ""); setEditClassificationPrompt(automation.classification_prompt || ""); setEditReplyPrompt(automation.reply_prompt || ""); setIsEditMode(true); loadCampaigns(); loadSlackChannels(); }}
                        className="p-1.5 rounded-lg text-neutral-400 hover:bg-violet-50 hover:text-violet-600"
                        title="Edit"
                      >
                        <Pencil className="w-4 h-4" />
                      </button>
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
                  {automation.google_sheet_id && (
                    <div className="flex items-center gap-1 text-xs text-neutral-500 mt-2">
                      <FileSpreadsheet className="w-3 h-3" />
                      <a href={`https://docs.google.com/spreadsheets/d/${automation.google_sheet_id}${automation.google_sheet_name?.includes('#') ? '/edit?gid=' + automation.google_sheet_name.split('#')[1] + '#gid=' + automation.google_sheet_name.split('#')[1] : ''}`} target="_blank" rel="noopener" className="text-green-600 hover:underline truncate max-w-[180px]">
                        {automation.google_sheet_name?.split('#')[0] || "Google Sheet"}
                      </a>
                    </div>
                  )}
                  {(automation.slack_webhook_url || automation.slack_channel) && (
                    <div className="flex items-center gap-1 text-xs text-neutral-500 mt-2">
                      <Bell className="w-3 h-3" />
                      {automation.slack_channel ? `#${slackChannelsEdit.find((c: {id: string, name: string}) => c.id === automation.slack_channel)?.name || automation.slack_channel}` : "Slack notifications enabled"}
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
      {/* Edit Automation Modal */}
      {editingAutomation && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={() => setEditingAutomation(null)} />
          <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
                  <Zap className="w-5 h-5 text-violet-600" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold">{editingAutomation.name}</h2>
                  <p className="text-sm text-neutral-500">{editingAutomation.campaign_ids?.length || 0} campaigns</p>
                </div>
              </div>
              <button onClick={() => setEditingAutomation(null)} className="p-2 hover:bg-neutral-100 rounded-lg">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6 space-y-4 overflow-y-auto max-h-[60vh]">
              {/* Google Sheets */}
              <div className="p-4 bg-neutral-50 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <FileSpreadsheet className="w-4 h-4 text-green-600" />
                  <span className="text-sm font-medium">Google Sheet</span>
                </div>
                {isEditMode ? (
                  <div className="space-y-2">
                    <input
                      type="text"
                      placeholder="Paste Google Sheet URL (include #gid= for specific tab)..."
                      value={editGoogleSheetUrl}
                      onChange={(e) => setEditGoogleSheetUrl(e.target.value)}
                      className="input w-full text-sm"
                    />
                    <div className="text-xs text-neutral-400">Or create a new sheet:</div>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        placeholder="New sheet name..."
                        value={editSheetName}
                        onChange={(e) => setEditSheetName(e.target.value)}
                        className="input flex-1 text-sm"
                      />
                      <button
                        onClick={async () => {
                          if (!editSheetName) return;
                          setEditCreatingSheet(true);
                          try {
                            const result = await repliesApi.createGoogleSheet(editSheetName);
                            if (result.sheet_url) {
                              setEditGoogleSheetUrl(result.sheet_url);
                              setEditSheetName('');
                            }
                          } catch (err) {
                            alert('Failed to create sheet');
                          } finally {
                            setEditCreatingSheet(false);
                          }
                        }}
                        disabled={!editSheetName || editCreatingSheet}
                        className="btn btn-sm bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                      >
                        {editCreatingSheet ? 'Creating...' : 'Create'}
                      </button>
                    </div>
                  </div>
                ) : editingAutomation.google_sheet_id ? (
                  <a 
                    href={`https://docs.google.com/spreadsheets/d/${editingAutomation.google_sheet_id}${editingAutomation.google_sheet_name?.includes('#') ? '/edit?gid=' + editingAutomation.google_sheet_name.split('#')[1] + '#gid=' + editingAutomation.google_sheet_name.split('#')[1] : ''}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-green-600 hover:underline break-all"
                  >
                    {editingAutomation.google_sheet_name?.split('#')[0] || 'Google Sheet'}
                  </a>
                ) : (
                  <span className="text-sm text-neutral-400">Not configured</span>
                )}
              </div>
              
              {/* Slack */}
              <div className="p-4 bg-neutral-50 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <Bell className="w-4 h-4 text-blue-600" />
                  <span className="text-sm font-medium">Slack Notifications</span>
                </div>
                {isEditMode ? (
                  <div className="space-y-2">
                    <select
                      value={editSlackChannel}
                      onChange={(e) => setEditSlackChannel(e.target.value)}
                      className="input w-full text-sm"
                    >
                      <option value="">Select channel...</option>
                      {slackChannelsEdit.map(ch => (
                        <option key={ch.id} value={ch.id}>#{ch.name}</option>
                      ))}
                    </select>
                    {slackChannelsEdit.length === 0 && (
                      <div className="text-xs text-neutral-400">Loading channels...</div>
                    )}
                    <div className="text-xs text-neutral-400">Or create a new channel:</div>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        placeholder="new-channel-name"
                        value={editNewChannelName}
                        onChange={(e) => setEditNewChannelName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-'))}
                        className="input flex-1 text-sm"
                      />
                      <button
                        onClick={async () => {
                          if (!editNewChannelName) return;
                          setEditCreatingChannel(true);
                          try {
                            const result = await repliesApi.createSlackChannel(editNewChannelName);
                            if (result.channel) {
                              const ch = result.channel;
                              setSlackChannelsEdit(prev => [...prev, { id: ch.id, name: ch.name }]);
                              setEditSlackChannel(ch.id);
                              setEditNewChannelName('');
                            }
                          } catch (err) {
                            alert('Failed to create channel');
                          } finally {
                            setEditCreatingChannel(false);
                          }
                        }}
                        disabled={!editNewChannelName || editCreatingChannel}
                        className="btn btn-sm bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        {editCreatingChannel ? 'Creating...' : 'Create'}
                      </button>
                    </div>
                  </div>
                ) : editingAutomation.slack_channel ? (
                  <span className="text-sm text-blue-600">#{slackChannelsEdit.find(c => c.id === editingAutomation.slack_channel)?.name || editingAutomation.slack_channel}</span>
                ) : editingAutomation.slack_webhook_url ? (
                  <span className="text-sm text-blue-600">Webhook configured</span>
                ) : (
                  <span className="text-sm text-neutral-400">Not configured</span>
                )}
              </div>
              
              {/* Campaigns */}
              <div className="p-4 bg-neutral-50 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <Mail className="w-4 h-4 text-violet-600" />
                  <span className="text-sm font-medium">Campaigns</span>
                </div>
                {isEditMode ? (
                  <div className="space-y-2">
                    {/* Selected campaigns - always visible */}
                    {editCampaigns.length > 0 && (
                      <div className="space-y-1 pb-2 border-b border-neutral-200">
                        <div className="text-xs text-emerald-600 font-medium">Selected:</div>
                        {editCampaigns.map(id => {
                          const campaign = campaigns.find(c => String(c.id) === String(id));
                          return (
                            <label key={id} className="flex items-center gap-2 p-1 bg-emerald-50 hover:bg-emerald-100 rounded cursor-pointer">
                              <input
                                type="checkbox"
                                checked={true}
                                onChange={() => setEditCampaigns(editCampaigns.filter(cid => cid !== id))}
                                className="rounded text-emerald-600"
                              />
                              <span className="text-sm truncate text-emerald-700">{campaign?.name || id}</span>
                            </label>
                          );
                        })}
                      </div>
                    )}
                    <input
                      type="text"
                      placeholder="Search campaigns to add..."
                      value={editCampaignSearch}
                      onChange={(e) => setEditCampaignSearch(e.target.value)}
                      className="input w-full text-sm"
                    />
                    <div className="max-h-32 overflow-y-auto space-y-1">
                      {campaigns
                        .filter(c => !editCampaigns.includes(String(c.id)))  /* Hide already selected */
                        .filter(c => !editCampaignSearch || c.name?.toLowerCase().includes(editCampaignSearch.toLowerCase()))
                        .slice(0, 10)
                        .map(c => (
                          <label key={c.id} className="flex items-center gap-2 p-1 hover:bg-neutral-100 rounded cursor-pointer">
                            <input
                              type="checkbox"
                              checked={false}
                              onChange={() => setEditCampaigns([...editCampaigns, String(c.id)])}
                              className="rounded"
                            />
                            <span className="text-sm truncate">{c.name}</span>
                          </label>
                        ))}
                    </div>
                    <div className="text-xs text-neutral-400">{editCampaigns.length} campaign{editCampaigns.length !== 1 ? 's' : ''} selected</div>
                  </div>
                ) : (
                  <div className="space-y-1">
                    {editingAutomation.campaign_ids?.map(id => (
                      <div key={id} className="text-sm text-neutral-600">{campaigns.find(c => String(c.id) === String(id))?.name || id}</div>
                    ))}
                  </div>
                )}
              </div>
              
              {/* AI Features */}
              <div className="p-4 bg-neutral-50 rounded-xl">
                <div className="flex items-center gap-2 mb-2">
                  <Zap className="w-4 h-4 text-amber-500" />
                  <span className="text-sm font-medium">AI Features</span>
                </div>
                <div className="space-y-1 text-sm">
                  <div className="flex items-center gap-2">
                    {editingAutomation.auto_classify ? <Check className="w-4 h-4 text-emerald-500" /> : <X className="w-4 h-4 text-neutral-300" />}
                    <span>Auto-classify replies</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {editingAutomation.auto_generate_reply ? <Check className="w-4 h-4 text-emerald-500" /> : <X className="w-4 h-4 text-neutral-300" />}
                    <span>Generate draft replies</span>
                  </div>
                </div>
              </div>
              
              {/* Custom Prompts - Beautiful Editor */}
              {isEditMode && (
                <div className="space-y-4">
                  {/* Classification Prompt */}
                  <div className="rounded-xl border-2 border-violet-200 overflow-hidden">
                    <div className="bg-violet-100 px-4 py-3 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">🏷️</span>
                        <div>
                          <div className="font-medium text-violet-900">Classification Prompt</div>
                          <div className="text-xs text-violet-600">How AI categorizes replies</div>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setEditClassificationPrompt('')}
                        className="text-xs text-violet-600 hover:text-violet-800 underline"
                      >
                        Reset to default
                      </button>
                    </div>
                    <div className="p-4 bg-white">
                      <textarea
                        placeholder="Leave empty to use default prompt.

Example custom prompt:
Classify this email reply into one of these categories:
- interested: Shows buying interest
- meeting_request: Wants to schedule a call
- not_interested: Declined or rejected
- out_of_office: Auto-reply or OOO
- other: Everything else

Consider the tone and specific words used."
                        value={editClassificationPrompt}
                        onChange={(e) => setEditClassificationPrompt(e.target.value)}
                        className="w-full text-sm h-32 p-3 border border-violet-200 rounded-lg focus:border-violet-400 focus:ring-1 focus:ring-violet-400 resize-none font-mono"
                      />
                      {!editClassificationPrompt && (
                        <div className="mt-2 p-2 bg-violet-50 rounded-lg">
                          <div className="text-xs text-violet-700 flex items-center gap-1">
                            <span>✨</span> Using smart default prompt
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Reply Generation Prompt */}
                  <div className="rounded-xl border-2 border-emerald-200 overflow-hidden">
                    <div className="bg-emerald-100 px-4 py-3 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">✍️</span>
                        <div>
                          <div className="font-medium text-emerald-900">Reply Generation Prompt</div>
                          <div className="text-xs text-emerald-600">How AI writes draft responses</div>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setEditReplyPrompt('')}
                        className="text-xs text-emerald-600 hover:text-emerald-800 underline"
                      >
                        Reset to default
                      </button>
                    </div>
                    <div className="p-4 bg-white">
                      <textarea
                        placeholder="Leave empty to use default prompt.

Example custom prompt:
Write a professional reply to this email.
- Be friendly but concise
- If interested: suggest next steps
- If meeting request: propose times
- Keep it under 100 words
- Sign off as the sales team"
                        value={editReplyPrompt}
                        onChange={(e) => setEditReplyPrompt(e.target.value)}
                        className="w-full text-sm h-32 p-3 border border-emerald-200 rounded-lg focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400 resize-none font-mono"
                      />
                      {!editReplyPrompt && (
                        <div className="mt-2 p-2 bg-emerald-50 rounded-lg">
                          <div className="text-xs text-emerald-700 flex items-center gap-1">
                            <span>✨</span> Using smart default prompt
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Tips */}
                  <div className="p-3 bg-amber-50 rounded-xl border border-amber-100">
                    <div className="flex items-start gap-2">
                      <span className="text-lg">💡</span>
                      <div className="text-xs text-amber-800">
                        <strong>Tips:</strong> Custom prompts let you fine-tune how AI handles your specific business. Leave empty to use battle-tested defaults. You can use variables like {"{lead_name}"}, {"{company}"}, {"{campaign_name}"} in your prompts.
                      </div>
                    </div>
                  </div>

                  {/* Prompt Debug Section */}
                  <div className="rounded-xl border-2 border-cyan-200 overflow-hidden">
                    <div className="bg-cyan-100 px-4 py-3 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">🧪</span>
                        <div>
                          <div className="font-medium text-cyan-900">Test Your Prompts</div>
                          <div className="text-xs text-cyan-600">Paste any email text to see how AI will classify and reply</div>
                        </div>
                      </div>
                    </div>
                    <div className="p-4 bg-white space-y-3">
                      <textarea
                        placeholder="Paste email text here to test...

Example:
Hi, thanks for reaching out. We're definitely interested in learning more about your solution. Could we schedule a call next week?"
                        value={promptTestText}
                        onChange={(e) => setPromptTestText(e.target.value)}
                        className="w-full text-sm h-24 p-3 border border-cyan-200 rounded-lg focus:border-cyan-400 focus:ring-1 focus:ring-cyan-400 resize-none"
                      />
                      <button
                        onClick={async () => {
                          if (!promptTestText.trim()) return;
                          setTestingPrompt(true);
                          setPromptTestResult(null);
                          try {
                            const result = await repliesApi.simulateReply({
                              email_body: promptTestText,
                              classification_prompt: editClassificationPrompt || undefined,
                              reply_prompt: editReplyPrompt || undefined,
                            });
                            setPromptTestResult({
                              category: result.category,
                              reply: result.draft_reply,
                            });
                          } catch (err) {
                            setPromptTestResult({ category: 'Error: Failed to test' });
                          } finally {
                            setTestingPrompt(false);
                          }
                        }}
                        disabled={testingPrompt || !promptTestText.trim()}
                        className="btn btn-secondary w-full"
                      >
                        {testingPrompt ? 'Testing...' : '🚀 Test Prompts'}
                      </button>
                      {promptTestResult && (
                        <div className="space-y-2">
                          <div className="p-3 bg-cyan-50 rounded-lg">
                            <div className="text-xs font-medium text-cyan-700 mb-1">Classification Result:</div>
                            <div className="text-sm font-semibold text-cyan-900">{promptTestResult.category}</div>
                          </div>
                          {promptTestResult.reply && (
                            <div className="p-3 bg-emerald-50 rounded-lg">
                              <div className="text-xs font-medium text-emerald-700 mb-1">Generated Reply:</div>
                              <div className="text-sm text-emerald-900 whitespace-pre-wrap">{promptTestResult.reply}</div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
            <div className="px-6 py-4 border-t border-neutral-200 flex gap-2">
              <button
                onClick={() => { setEditingAutomation(null); setIsEditMode(false); }}
                className="btn btn-secondary flex-1"
              >
                Cancel
              </button>
              {isEditMode ? (
                <button 
                  onClick={async () => {
                    setSavingEdit(true);
                    try {
                      await repliesApi.updateAutomation(editingAutomation.id, {
                        google_sheet_id: editGoogleSheetUrl ? extractSheetId(editGoogleSheetUrl) : undefined,
                        google_sheet_name: editGoogleSheetUrl ? createSheetNameWithGid(editGoogleSheetUrl) : undefined,
                        slack_channel: editSlackChannel || undefined,
                        campaign_ids: editCampaigns.length > 0 ? editCampaigns : undefined,
                        classification_prompt: editClassificationPrompt || undefined,
                        reply_prompt: editReplyPrompt || undefined,
                      });
                      await loadAutomations();
                      setIsEditMode(false);
                      setEditingAutomation(null);
                    } catch (err) {
                      alert('Failed to save');
                    } finally {
                      setSavingEdit(false);
                    }
                  }}
                  disabled={savingEdit}
                  className="btn btn-primary flex-1"
                >
                  {savingEdit ? 'Saving...' : 'Save Changes'}
                </button>
              ) : (
                <button 
                  onClick={() => {
                    setIsEditMode(true);
                    setEditGoogleSheetUrl(editingAutomation.google_sheet_id ? `https://docs.google.com/spreadsheets/d/\${editingAutomation.google_sheet_id}` : '');
                    setEditSlackChannel(editingAutomation.slack_channel || '');
                  }}
                  className="btn btn-primary flex-1"
                >
                  Edit
                </button>
              )}
            </div>
          </div>
        </div>
      )}

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


      {/* Test Flow Modal */}
      {showTestFlowModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={() => setShowTestFlowModal(false)} />
          <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
            <div className="p-6 border-b border-neutral-100">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-emerald-100 flex items-center justify-center">
                    <TestTube2 className="w-5 h-5 text-emerald-600" />
                  </div>
                  <div>
                    <h2 className="text-lg font-semibold">Test Auto-Reply Flow</h2>
                    <p className="text-sm text-neutral-500">Step {testFlowStep} of 3</p>
                  </div>
                </div>
                <button onClick={() => setShowTestFlowModal(false)} className="p-2 hover:bg-neutral-100 rounded-lg">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
            
            <div className="p-6 overflow-y-auto flex-1">
              {testFlowStep === 1 && (
                <div className="space-y-4">
                  <div className="p-4 bg-emerald-50 rounded-xl">
                    <p className="text-sm text-emerald-800">
                      <strong>Step 1:</strong> Create a test campaign and send yourself an email.
                      Reply to it to test the full automation flow!
                    </p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-1">Your Email</label>
                    <input
                      type="email"
                      value={testUserEmail}
                      onChange={(e) => setTestUserEmail(e.target.value)}
                      placeholder="your@email.com"
                      className="input w-full"
                    />
                    <p className="text-xs text-neutral-400 mt-1">You'll receive a test email here</p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-1">Your Name</label>
                    <input
                      type="text"
                      value={testUserName}
                      onChange={(e) => setTestUserName(e.target.value)}
                      placeholder="John Doe"
                      className="input w-full"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-1">Send From (Email Account)</label>
                    <select
                      value={selectedEmailAccount || ''}
                      onChange={(e) => setSelectedEmailAccount(e.target.value ? Number(e.target.value) : null)}
                      className="input w-full"
                    >
                      <option value="">Auto-select best account</option>
                      {testEmailAccounts.map(acc => (
                        <option key={acc.id} value={acc.id}>
                          {acc.email} ({acc.remaining} emails remaining today)
                        </option>
                      ))}
                    </select>
                    {testEmailAccounts.length === 0 && (
                      <p className="text-xs text-amber-600 mt-1">Loading email accounts...</p>
                    )}
                  </div>
                  
                  {testCampaigns.length > 0 && (
                    <div className="p-3 bg-neutral-50 rounded-lg">
                      <p className="text-xs text-neutral-500 mb-2">Existing test campaigns:</p>
                      <div className="space-y-1">
                        {testCampaigns.slice(0, 3).map(c => (
                          <div key={c.id} className="text-xs text-neutral-600">{c.name} ({c.status})</div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
              
              {testFlowStep === 2 && testCampaignResult && (
                <div className="space-y-4">
                  <div className="p-4 bg-emerald-50 rounded-xl">
                    <p className="text-sm text-emerald-800 font-medium">Campaign Created!</p>
                    <p className="text-sm text-emerald-700 mt-1">{testCampaignResult.message}</p>
                  </div>
                  
                  <div className="p-4 bg-amber-50 rounded-xl">
                    <p className="text-sm text-amber-800 font-medium">Now set up an automation:</p>
                    <ol className="text-sm text-amber-700 mt-2 space-y-1 list-decimal list-inside">
                      <li>Click "New Automation" button</li>
                      <li>Select campaign: <strong>{testCampaignResult.campaign_name}</strong></li>
                      <li>Connect a Google Sheet</li>
                      <li>Connect a Slack channel</li>
                    </ol>
                  </div>
                  
                  <div className="p-3 bg-neutral-100 rounded-lg">
                    <p className="text-xs text-neutral-500">Campaign ID (for reference):</p>
                    <code className="text-sm font-mono">{testCampaignResult.campaign_id}</code>
                  </div>
                </div>
              )}
              
              {testFlowStep === 3 && (
                <div className="space-y-4">
                  <div className="p-4 bg-blue-50 rounded-xl">
                    <p className="text-sm text-blue-800 font-medium">Final Step: Test the flow!</p>
                    <ol className="text-sm text-blue-700 mt-2 space-y-1 list-decimal list-inside">
                      <li>Check your email for the test message</li>
                      <li>Reply to it with any message</li>
                      <li>Watch it appear in your Google Sheet and Slack!</li>
                    </ol>
                  </div>
                  
                  <div className="p-4 bg-neutral-50 rounded-xl">
                    <p className="text-sm text-neutral-600">
                      <strong>Tip:</strong> Try different reply types:
                    </p>
                    <ul className="text-sm text-neutral-500 mt-2 space-y-1">
                      <li>• "Yes, I'm interested!" → Interested</li>
                      <li>• "Can we schedule a call?" → Meeting Request</li>
                      <li>• "Not interested, thanks" → Not Interested</li>
                    </ul>
                  </div>
                </div>
              )}
            </div>
            
            <div className="p-6 border-t border-neutral-100 flex justify-between">
              {testFlowStep > 1 ? (
                <button onClick={() => setTestFlowStep(s => s - 1)} className="btn btn-secondary">
                  Back
                </button>
              ) : (
                <div />
              )}
              
              {testFlowStep === 1 && (
                <button
                  onClick={async () => {
                    if (!testUserEmail) { alert('Please enter your email'); return; }
                    setTestFlowLoading(true);
                    try {
                      const result = await repliesApi.createTestCampaign(
                        testUserEmail,
                        testUserName || 'Test User',
                        selectedEmailAccount || undefined
                      );
                      if (result.success) {
                        setTestCampaignResult(result);
                        setTestFlowStep(2);
                      } else {
                        alert(result.error || 'Failed to create campaign');
                      }
                    } catch (e: any) {
                      alert(e.response?.data?.detail || 'Failed to create campaign');
                    } finally {
                      setTestFlowLoading(false);
                    }
                  }}
                  disabled={testFlowLoading || !testUserEmail}
                  className="btn btn-primary"
                >
                  {testFlowLoading ? 'Creating...' : 'Create Test Campaign'}
                </button>
              )}
              
              {testFlowStep === 2 && (
                <button
                  onClick={() => {
                    setShowTestFlowModal(false);
                    loadCampaigns();
                    setShowCreateModal(true);
                  }}
                  className="btn btn-primary"
                >
                  Create Automation Now
                </button>
              )}
              
              {testFlowStep === 3 && (
                <button onClick={() => setShowTestFlowModal(false)} className="btn btn-primary">
                  Done
                </button>
              )}
            </div>
          </div>
        </div>
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
            {reply.inbox_link && (
              <a 
                href={reply.inbox_link}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-1 text-sm text-violet-600 hover:text-violet-700 hover:underline"
              >
                <ExternalLink className="w-3 h-3" />
                Open in Smartlead Inbox
              </a>
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

// Create Automation Modal - Chat-Style 4-Step Wizard
interface CreateAutomationModalProps {
  campaigns: SmartleadCampaign[];
  campaignsLoading: boolean;
  smartleadError: string | null;
  onClose: () => void;
  onCreated: () => void;
  onRetryCampaigns: () => void;
}

// Step indicator component
function WizardSteps({ currentStep, totalSteps }: { currentStep: number; totalSteps: number }) {
  const stepNames = ['Campaigns', 'Google Sheet', 'Slack', 'Review'];

  return (
    <div className="flex items-center justify-center gap-1 px-4 py-2 bg-neutral-50">
      {Array.from({ length: totalSteps }).map((_, i) => {
        const stepNum = i + 1;
        const isComplete = stepNum < currentStep;
        const isCurrent = stepNum === currentStep;
        return (
          <div key={stepNum} className="flex items-center gap-1">
            <div className={cn(
              "w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium transition-colors",
              isComplete && "bg-emerald-500 text-white",
              isCurrent && "bg-violet-600 text-white",
              !isComplete && !isCurrent && "bg-neutral-200 text-neutral-500"
            )}>
              {isComplete ? <Check className="w-4 h-4" /> : stepNum}
            </div>
            <span className={cn(
              "text-xs hidden sm:block",
              isCurrent && "text-violet-600 font-medium",
              !isCurrent && "text-neutral-400"
            )}>
              {stepNames[i]}
            </span>
            {stepNum < totalSteps && (
              <div className={cn(
                "w-6 h-0.5 mx-1",
                stepNum < currentStep ? "bg-emerald-500" : "bg-neutral-200"
              )} />
            )}
          </div>
        );
      })}
    </div>
  );
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
  const TOTAL_STEPS = 4;
  
  // Step 1: Campaign selection
  const [name, setName] = useState('');
  const [selectedCampaigns, setSelectedCampaigns] = useState<string[]>([]);
  const [searchCampaigns, setSearchCampaigns] = useState('');
  
  // Fetch Slack channels when entering step 3
  useEffect(() => {
    if (step === 3 && slackChannels.length === 0 && !loadingSlackChannels) {
      setLoadingSlackChannels(true);
      repliesApi.getSlackChannels()
        .then(res => {
          if (res.channels) {
            setSlackChannels(res.channels.map(c => ({ id: c.id, name: c.name })));
          }
        })
        .catch(err => console.error('Failed to load Slack channels:', err))
        .finally(() => setLoadingSlackChannels(false));
    }
  }, [step]);

  // Step 2: Google Sheets
  const [createGoogleSheet, setCreateGoogleSheet] = useState(false);
  const [useExistingSheet, setUseExistingSheet] = useState(false);
  const [existingSheetUrl, setExistingSheetUrl] = useState('');
  const [shareSheetEmail, setShareSheetEmail] = useState('');
  const [sheetsStatus, setSheetsStatus] = useState<GoogleSheetsStatus | null>(null);
  const [loadingSheetsStatus, setLoadingSheetsStatus] = useState(false);
  
  // Step 3: Slack
  // Removed: webhook not needed when using channel selection
  const [slackChannel, setSlackChannel] = useState('');
  const [slackChannels, setSlackChannels] = useState<Array<{id: string, name: string}>>([]);
  const [slackSearch, setSlackSearch] = useState('');
  const [showChannelDropdown, setShowChannelDropdown] = useState(false);
  const [loadingSlackChannels, setLoadingSlackChannels] = useState(false);
  const [newChannelName, setNewChannelName] = useState('');
  const [creatingChannel, setCreatingChannel] = useState(false);
  const [testingChannel, setTestingChannel] = useState(false);
  const [testResult, setTestResult] = useState<{success: boolean; message: string} | null>(null);
  
  // Step 4: Review settings
  const [autoClassify, setAutoClassify] = useState(true);
  const [autoGenerateReply, setAutoGenerateReply] = useState(true);
  const [isCreating, setIsCreating] = useState(false);

  // Load Google Sheets status when entering step 2
  useEffect(() => {
    if (step === 2 && !sheetsStatus && !loadingSheetsStatus) {
      setLoadingSheetsStatus(true);
      repliesApi.getGoogleSheetsStatus()
        .then(setSheetsStatus)
        .catch(err => {
          console.error('Failed to get Google Sheets status:', err);
          setSheetsStatus({ configured: false, service_account_email: null, message: 'Failed to check status' });
        })
        .finally(() => setLoadingSheetsStatus(false));
    }
  }, [step, sheetsStatus, loadingSheetsStatus]);

  const filteredCampaigns = campaigns.filter(c => 
    c.name?.toLowerCase().includes(searchCampaigns.toLowerCase()) ||
    String(c.id || "").toLowerCase().includes(searchCampaigns.toLowerCase())
  );

  const handleCreate = async () => {
    if (!name || selectedCampaigns.length === 0) return;
    
    setIsCreating(true);
    try {
      const data: ReplyAutomationCreate = {
        name,
        campaign_ids: selectedCampaigns,
        // slack_webhook_url: not needed when using channel ID
        slack_channel: slackChannel || undefined,
        create_google_sheet: createGoogleSheet && !useExistingSheet,
        google_sheet_id: useExistingSheet ? extractSheetId(existingSheetUrl) : undefined,
        google_sheet_name: useExistingSheet ? createSheetNameWithGid(existingSheetUrl) || 'Existing Sheet' : undefined,
        share_sheet_with_email: shareSheetEmail || undefined,
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



  const handleCreateChannel = async () => {
    if (!newChannelName) return;
    setCreatingChannel(true);
    setTestResult(null);
    try {
      const result = await repliesApi.createSlackChannel(newChannelName);
      if (result.channel) {
        const ch = result.channel;
        setSlackChannels(prev => [...prev, { id: ch.id, name: ch.name }]);
        setSlackChannel(ch.id);
        setNewChannelName('');
        setTestResult({ success: true, message: `Channel #${ch.name} created!` });
      }
    } catch (err: any) {
      setTestResult({ success: false, message: err.response?.data?.detail || 'Failed to create channel' });
    } finally {
      setCreatingChannel(false);
    }
  };

  const handleTestSlackChannel = async () => {
    if (!slackChannel) return;
    setTestingChannel(true);
    setTestResult(null);
    try {
      const result = await repliesApi.testSlackChannel(slackChannel);
      setTestResult(result);
    } catch (err: any) {
      setTestResult({ success: false, message: err.response?.data?.detail || 'Failed to send test message' });
    } finally {
      setTestingChannel(false);
    }
  };

  const canProceed = () => {
    switch (step) {
      case 1: return name.trim() && selectedCampaigns.length > 0;
      case 2: return true; // Optional step
      case 3: return true; // Optional step
      case 4: return true;
      default: return false;
    }
  };

  const getSelectedCampaignNames = () => {
    return selectedCampaigns
      .map(id => campaigns.find(c => c.id === id)?.name || id)
      .slice(0, 3)
      .join(', ') + (selectedCampaigns.length > 3 ? ` +${selectedCampaigns.length - 3} more` : '');
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
              <p className="text-sm text-neutral-500">Configure your automation</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-neutral-100 rounded-lg">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Step indicator */}
        <WizardSteps currentStep={step} totalSteps={TOTAL_STEPS} />

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {/* Step 1: Select Campaigns */}
          {step === 1 && (
            <div className="space-y-4">
              <div className="bg-violet-50 border border-violet-100 rounded-xl p-4 mb-4">
                <div className="flex items-start gap-3">
                  <MessageSquare className="w-5 h-5 text-violet-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm text-violet-800 font-medium">Which campaigns should I monitor?</p>
                    <p className="text-xs text-violet-600 mt-1">Select the Smartlead campaigns to track for incoming replies.</p>
                  </div>
                </div>
              </div>

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
                  Select Campaigns
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
                    
                    <div className="border border-neutral-200 rounded-xl max-h-48 overflow-auto">
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
                              checked={selectedCampaigns.includes(String(campaign.id))}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setSelectedCampaigns([...selectedCampaigns, String(campaign.id)]);
                                } else {
                                  setSelectedCampaigns(selectedCampaigns.filter(id => id !== String(campaign.id)));
                                }
                              }}
                              className="rounded text-violet-600"
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
                      <div className="text-sm text-violet-600 mt-2 font-medium">
                        {selectedCampaigns.length} campaign{selectedCampaigns.length !== 1 ? 's' : ''} selected
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          )}

          {/* Step 2: Google Sheets */}
          {step === 2 && (
            <div className="space-y-4">
              <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4 mb-4">
                <div className="flex items-start gap-3">
                  <FileSpreadsheet className="w-5 h-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm text-emerald-800 font-medium">Want to log replies to a Google Sheet?</p>
                    <p className="text-xs text-emerald-600 mt-1">I can create a new sheet and automatically log every reply for you.</p>
                  </div>
                </div>
              </div>

              {loadingSheetsStatus ? (
                <div className="flex items-center justify-center py-8">
                  <RefreshCw className="w-5 h-5 animate-spin text-neutral-400" />
                  <span className="ml-2 text-sm text-neutral-500">Checking Google Sheets status...</span>
                </div>
              ) : !sheetsStatus?.configured ? (
                <div className="p-4 bg-amber-50 border border-amber-100 rounded-xl">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm text-amber-800 font-medium">Google Sheets not configured</p>
                      <p className="text-xs text-amber-600 mt-1">
                        {sheetsStatus?.message || 'Set up service account credentials to enable this feature.'}
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Choice cards */}
                  <div 
                    onClick={() => { setCreateGoogleSheet(true); setUseExistingSheet(false); }}
                    className={cn(
                      "p-4 rounded-xl border-2 cursor-pointer transition-all",
                      createGoogleSheet 
                        ? "border-emerald-500 bg-emerald-50" 
                        : "border-neutral-200 hover:border-emerald-300"
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-5 h-5 rounded-full border-2 flex items-center justify-center",
                        createGoogleSheet ? "border-emerald-500 bg-emerald-500" : "border-neutral-300"
                      )}>
                        {createGoogleSheet && <Check className="w-3 h-3 text-white" />}
                      </div>
                      <div className="flex-1">
                        <p className="font-medium text-neutral-900">Create new Google Sheet</p>
                        <p className="text-xs text-neutral-500 mt-0.5">Automatically log all replies to a spreadsheet</p>
                      </div>
                      <FileSpreadsheet className="w-5 h-5 text-emerald-500" />
                    </div>
                  </div>

                  {/* Use existing sheet option */}
                  <div 
                    onClick={() => { setCreateGoogleSheet(false); setUseExistingSheet(true); }}
                    className={cn(
                      "p-4 rounded-xl border-2 cursor-pointer transition-all",
                      useExistingSheet 
                        ? "border-blue-500 bg-blue-50" 
                        : "border-neutral-200 hover:border-blue-300"
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-5 h-5 rounded-full border-2 flex items-center justify-center",
                        useExistingSheet ? "border-blue-500 bg-blue-500" : "border-neutral-300"
                      )}>
                        {useExistingSheet && <Check className="w-3 h-3 text-white" />}
                      </div>
                      <div className="flex-1">
                        <p className="font-medium text-neutral-900">Use existing Google Sheet</p>
                        <p className="text-xs text-neutral-500 mt-0.5">Paste a sheet URL to log replies there</p>
                      </div>
                      <FileSpreadsheet className="w-5 h-5 text-blue-500" />
                    </div>
                  </div>

                  {/* Existing sheet URL input */}
                  {useExistingSheet && (
                    <div className="mt-4 p-4 bg-blue-50 rounded-xl">
                      <label className="block text-sm font-medium text-neutral-700 mb-1">
                        Google Sheet URL or ID
                      </label>
                      <input
                        type="text"
                        placeholder="https://docs.google.com/spreadsheets/d/..."
                        value={existingSheetUrl}
                        onChange={(e) => setExistingSheetUrl(e.target.value)}
                        className="input w-full text-sm"
                      />
                      <p className="text-xs text-neutral-400 mt-1">
                        Paste the full URL or just the sheet ID
                      </p>
                      {existingSheetUrl && (
                        <p className="text-xs text-blue-600 mt-2">
                          Sheet ID: {extractSheetId(existingSheetUrl)}
                        </p>
                      )}
                    </div>
                  )}

                  {/* Skip option */}
                  <div 
                    onClick={() => { setCreateGoogleSheet(false); setUseExistingSheet(false); }}
                    className={cn(
                      "p-4 rounded-xl border-2 cursor-pointer transition-all",
                      !createGoogleSheet && !useExistingSheet
                        ? "border-violet-500 bg-violet-50" 
                        : "border-neutral-200 hover:border-violet-300"
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-5 h-5 rounded-full border-2 flex items-center justify-center",
                        !createGoogleSheet && !useExistingSheet ? "border-violet-500 bg-violet-500" : "border-neutral-300"
                      )}>
                        {!createGoogleSheet && !useExistingSheet && <Check className="w-3 h-3 text-white" />}
                      </div>
                      <div className="flex-1">
                        <p className="font-medium text-neutral-900">Skip for now</p>
                        <p className="text-xs text-neutral-500 mt-0.5">You can add a sheet later</p>
                      </div>
                      <SkipForward className="w-5 h-5 text-violet-500" />
                    </div>
                  </div>

                  {/* Share email input - only show if creating sheet */}
                  {createGoogleSheet && (
                    <div className="mt-4 p-4 bg-neutral-50 rounded-xl">
                      <label className="block text-sm font-medium text-neutral-700 mb-1">
                        Share sheet with (optional)
                      </label>
                      <input
                        type="email"
                        placeholder="team@yourcompany.com"
                        value={shareSheetEmail}
                        onChange={(e) => setShareSheetEmail(e.target.value)}
                        className="input w-full text-sm"
                      />
                      <p className="text-xs text-neutral-400 mt-1">
                        The sheet will be shared with editor access
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Step 3: Slack */}
          {step === 3 && (
            <div className="space-y-4">
              <div className="bg-blue-50 border border-blue-100 rounded-xl p-4 mb-4">
                <div className="flex items-start gap-3">
                  <Bell className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm text-blue-800 font-medium">Where should I send notifications?</p>
                    <p className="text-xs text-blue-600 mt-1">Get instant Slack alerts when new replies come in with approve/reject buttons.</p>
                  </div>
                </div>
              </div>

              {/* Channel Selection with Search */}
              <div className="relative">
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Select Slack Channel
                </label>
                {loadingSlackChannels ? (
                  <div className="text-sm text-neutral-500 py-2">Loading channels...</div>
                ) : (
                  <div className="relative">
                    <div className="relative">
                      <Hash className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
                      <input
                        type="text"
                        placeholder="Search channels..."
                        value={slackSearch || (slackChannel ? slackChannels.find(c => c.id === slackChannel)?.name || '' : '')}
                        onChange={(e) => { setSlackSearch(e.target.value); setShowChannelDropdown(true); }}
                        onFocus={() => setShowChannelDropdown(true)}
                        className="input pl-9 w-full"
                      />
                    </div>
                    {showChannelDropdown && (
                      <div className="absolute z-10 mt-1 w-full bg-white border border-neutral-200 rounded-xl shadow-lg max-h-48 overflow-auto">
                        {slackChannels
                          .filter(ch => !slackSearch || ch.name.toLowerCase().includes(slackSearch.toLowerCase()))
                          .map(ch => (
                            <div
                              key={ch.id}
                              onClick={() => { setSlackChannel(ch.id); setSlackSearch(''); setShowChannelDropdown(false); }}
                              className={cn(
                                "px-4 py-2 cursor-pointer hover:bg-neutral-50 flex items-center gap-2",
                                slackChannel === ch.id && "bg-violet-50 text-violet-700"
                              )}
                            >
                              <Hash className="w-3 h-3" />
                              {ch.name}
                              {slackChannel === ch.id && <Check className="w-4 h-4 ml-auto" />}
                            </div>
                          ))}
                        {slackChannels.filter(ch => !slackSearch || ch.name.toLowerCase().includes(slackSearch.toLowerCase())).length === 0 && (
                          <div className="px-4 py-2 text-sm text-neutral-500">No channels found</div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Create New Channel */}
              <div className="border-t border-neutral-100 pt-4">
                <p className="text-sm font-medium text-neutral-700 mb-2">Or create a new channel</p>
                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Hash className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
                    <input
                      type="text"
                      placeholder="new-channel-name"
                      value={newChannelName}
                      onChange={(e) => setNewChannelName(e.target.value.toLowerCase().replace(/[^a-z0-9-_]/g, "-"))}
                      className="input pl-9 w-full"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleCreateChannel}
                    disabled={!newChannelName || creatingChannel}
                    className="btn btn-secondary whitespace-nowrap"
                  >
                    {creatingChannel ? "Creating..." : "Create Channel"}
                  </button>
                </div>
              </div>

              {/* Test Message */}
              {slackChannel && (
                <div className="border-t border-neutral-100 pt-4">
                  <button
                    type="button"
                    onClick={handleTestSlackChannel}
                    disabled={testingChannel}
                    className="btn btn-secondary w-full"
                  >
                    {testingChannel ? "Sending..." : "Send Test Message"}
                  </button>
                </div>
              )}

              {/* Test Result */}
              {testResult && (
                <div className={cn(
                  "p-3 rounded-xl text-sm flex items-center gap-2",
                  testResult.success ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
                )}>
                  {testResult.success ? <Check className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                  {testResult.message}
                </div>
              )}

              {!slackChannel && (
                <div className="p-3 bg-neutral-50 rounded-xl">
                  <p className="text-xs text-neutral-500">
                    <strong>Tip:</strong> You can skip this step and add Slack later. Replies will still be classified and stored.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Step 4: Review & Activate */}
          {step === 4 && (
            <div className="space-y-4">
              <div className="bg-violet-50 border border-violet-100 rounded-xl p-4 mb-4">
                <div className="flex items-start gap-3">
                  <Check className="w-5 h-5 text-violet-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm text-violet-800 font-medium">Ready to activate!</p>
                    <p className="text-xs text-violet-600 mt-1">Review your settings and create the automation.</p>
                  </div>
                </div>
              </div>

              {/* Summary */}
              <div className="border border-neutral-200 rounded-xl divide-y divide-neutral-100">
                <div className="p-4">
                  <div className="text-xs text-neutral-500 uppercase tracking-wide mb-1">Name</div>
                  <div className="font-medium">{name}</div>
                </div>
                <div className="p-4">
                  <div className="text-xs text-neutral-500 uppercase tracking-wide mb-1">Campaigns</div>
                  <div className="font-medium text-sm">{getSelectedCampaignNames()}</div>
                </div>
                <div className="p-4 flex items-center justify-between">
                  <div>
                    <div className="text-xs text-neutral-500 uppercase tracking-wide mb-1">Google Sheet</div>
                    <div className="font-medium">{createGoogleSheet ? 'Create new sheet' : 'Not configured'}</div>
                  </div>
                  <FileSpreadsheet className={cn("w-5 h-5", createGoogleSheet ? "text-emerald-500" : "text-neutral-300")} />
                </div>
                <div className="p-4 flex items-center justify-between">
                  <div>
                    <div className="text-xs text-neutral-500 uppercase tracking-wide mb-1">Slack Notifications</div>
                    <div className="font-medium">{slackChannel ? `#${slackChannels.find(c => c.id === slackChannel)?.name || slackChannel}` : "Not configured"}</div>
                  </div>
                  <Bell className={cn("w-5 h-5", slackChannel ? "text-blue-500" : "text-neutral-300")} />
                </div>
              </div>

              {/* AI Features toggles */}
              <div className="space-y-2">
                <p className="text-xs text-neutral-500 uppercase tracking-wide">AI Features</p>
                <label className="flex items-center justify-between p-3 bg-neutral-50 rounded-xl cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Zap className="w-4 h-4 text-amber-500" />
                    <span className="text-sm font-medium">Auto-classify replies</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={autoClassify}
                    onChange={(e) => setAutoClassify(e.target.checked)}
                    className="rounded text-violet-600"
                  />
                </label>
                
                <label className="flex items-center justify-between p-3 bg-neutral-50 rounded-xl cursor-pointer">
                  <div className="flex items-center gap-2">
                    <Mail className="w-4 h-4 text-cyan-500" />
                    <span className="text-sm font-medium">Generate draft replies</span>
                  </div>
                  <input
                    type="checkbox"
                    checked={autoGenerateReply}
                    onChange={(e) => setAutoGenerateReply(e.target.checked)}
                    className="rounded text-violet-600"
                  />
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
              className="btn btn-secondary"
            >
              Back
            </button>
          )}
          <div className="flex-1" />
          {step < TOTAL_STEPS ? (
            <button 
              onClick={() => setStep(s => s + 1)}
              disabled={!canProceed()}
              className="btn btn-primary"
            >
              Continue
            </button>
          ) : (
            <button 
              onClick={handleCreate}
              disabled={isCreating}
              className="btn btn-primary"
            >
              {isCreating ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Zap className="w-4 h-4" />
                  Activate Automation
                </>
              )}
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
