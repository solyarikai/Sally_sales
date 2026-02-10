import toast, { Toaster } from 'react-hot-toast';
import { useEffect, useState, useCallback } from 'react';
import {
  MessageSquare, Search, RefreshCw, Plus, Settings2,
  Send, Bell, X, Copy, Check, AlertCircle,
  Zap, Hash, Calendar, Mail, Building2,
  TestTube2, FileSpreadsheet, ExternalLink, Pencil,
  CheckCircle, XCircle, Shield
} from 'lucide-react';
import {
  repliesApi,
  type ReplyAutomation,
  type SmartleadCampaign,
  type ReplyAutomationCreate,
  type SimulateReplyPayload,
  type SimulateReplyResponse,
  type GoogleSheetsStatus
} from '../api/replies';
import { cn } from '../lib/utils';
import { ConfirmDialog } from '../components/ConfirmDialog';

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
  return gid ? `Replies#${gid}` : undefined;
};

export function AutomationsPage() {
  const [automations, setAutomations] = useState<ReplyAutomation[]>([]);
  const [campaigns, setCampaigns] = useState<SmartleadCampaign[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [campaignsLoading, setCampaignsLoading] = useState(false);
  const [smartleadError, setSmartleadError] = useState<string | null>(null);

  // UI state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedCampaignsForCreate, setSelectedCampaignsForCreate] = useState<string[]>([]);
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
  const [editClassificationTemplate, setEditClassificationTemplate] = useState<string>('default');
  const [editReplyTemplate, setEditReplyTemplate] = useState<string>('default');
  const [editPromptTemplates, setEditPromptTemplates] = useState<any[]>([]);
  const [slackChannelsEdit, setSlackChannelsEdit] = useState<Array<{ id: string, name: string }>>([]);
  const [promptTestText, setPromptTestText] = useState('');
  const [promptTestResult, setPromptTestResult] = useState<{ category?: string, reply?: string } | null>(null);
  const [testingPrompt, setTestingPrompt] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);
  const [showTestFlowModal, setShowTestFlowModal] = useState(false);
  const [testFlowStep, setTestFlowStep] = useState(1);
  const [testEmailAccounts, setTestEmailAccounts] = useState<Array<{ id: number, email: string, name: string, remaining: number }>>([]);
  const [selectedEmailAccount, setSelectedEmailAccount] = useState<number | null>(null);
  const [testUserEmail, setTestUserEmail] = useState('');
  const [testCampaignResult, setTestCampaignResult] = useState<{ campaign_id?: string, campaign_name?: string, message?: string } | null>(null);
  const [testFlowLoading, setTestFlowLoading] = useState(false);
  const [testCampaigns, setTestCampaigns] = useState<Array<{ id: string, name: string, status: string }>>([]);
  const [testCampaignStatus, setTestCampaignStatus] = useState<string | null>(null);
  const [launchingCampaign, setLaunchingCampaign] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({ isOpen: false, title: '', message: '', onConfirm: () => { } });

  const loadAutomations = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await repliesApi.getAutomations(false);
      setAutomations(data);
    } catch (err) {
      console.error('Failed to load automations:', err);
    } finally {
      setIsLoading(false);
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
      setSmartleadError(err.response?.data?.detail || 'Failed to load Smartlead campaigns.');
    } finally {
      setCampaignsLoading(false);
    }
  }, []);

  const loadEditTemplates = async () => {
    try {
      const resp = await fetch("/api/replies/prompt-templates");
      const data = await resp.json();
      setEditPromptTemplates(data.templates || []);
    } catch (e) {
      console.error("Failed to load templates", e);
    }
  };

  useEffect(() => {
    loadAutomations();
    loadSlackChannels();
    loadCampaigns();
  }, [loadAutomations, loadSlackChannels, loadCampaigns]);

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

  return (
    <div className="h-full flex flex-col bg-neutral-50">
      <Toaster position="top-center" />
      {/* Header */}
      <div className="bg-white border-b border-neutral-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
              <Settings2 className="w-5 h-5 text-violet-600" />
            </div>
            <div>
              <h1 className="text-xl font-semibold text-neutral-900">Reply Automations</h1>
              <p className="text-sm text-neutral-500">
                {automations.length} automation{automations.length !== 1 ? 's' : ''} configured
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={loadAutomations} className="btn btn-secondary btn-sm">
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
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <RefreshCw className="w-6 h-6 animate-spin text-neutral-400" />
          </div>
        ) : automations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="w-16 h-16 rounded-xl bg-neutral-100 flex items-center justify-center mb-4">
              <Settings2 className="w-8 h-8 text-neutral-400" />
            </div>
            <p className="text-neutral-500 mb-1">No automations yet</p>
            <p className="text-sm text-neutral-400 mb-4">Create your first automation to start monitoring replies</p>
            <button
              onClick={() => { loadCampaigns(); setShowCreateModal(true); }}
              className="btn btn-primary"
            >
              <Plus className="w-4 h-4" />
              Create First Automation
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {automations.map(automation => (
              <div
                key={automation.id}
                className="bg-white rounded-xl border border-neutral-200 p-5 hover:border-violet-300 hover:shadow-sm transition-all"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={cn(
                      "w-2.5 h-2.5 rounded-full flex-shrink-0",
                      automation.active ? "bg-emerald-500" : "bg-neutral-300"
                    )} />
                    <span className="font-semibold text-neutral-900 truncate">{automation.name}</span>
                  </div>
                  <div className="flex items-center gap-1 flex-shrink-0">
                    <button
                      onClick={async () => {
                        const count = automation.campaign_ids?.length || 0;
                        if (!confirm(`Launch ${count} campaign${count !== 1 ? 's' : ''}?`)) return;
                        const toastId = toast.loading('Launching...');
                        try {
                          for (const cid of automation.campaign_ids || []) {
                            await repliesApi.launchCampaign(String(cid));
                          }
                          toast.success('Launched!', { id: toastId });
                        } catch (err: any) {
                          toast.error(err?.response?.data?.detail || 'Launch failed', { id: toastId });
                        }
                      }}
                      className="p-1.5 rounded-lg text-emerald-500 hover:bg-emerald-50"
                      title="Launch campaigns"
                    >
                      <Send className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => {
                        setEditingAutomation(automation);
                        setEditCampaigns(automation.campaign_ids?.map(String) || []);
                        setEditSlackChannel(automation.slack_channel || "");
                        setEditGoogleSheetUrl(automation.google_sheet_id ? `https://docs.google.com/spreadsheets/d/${automation.google_sheet_id}` : "");
                        setEditClassificationPrompt(automation.classification_prompt || "");
                        setEditReplyPrompt(automation.reply_prompt || "");
                        setIsEditMode(true);
                        loadCampaigns();
                        loadSlackChannels();
                        loadEditTemplates();
                        setEditClassificationTemplate(automation.classification_prompt ? 'custom' : 'default');
                        setEditReplyTemplate(automation.reply_prompt ? 'custom' : 'default');
                      }}
                      className="p-1.5 rounded-lg text-neutral-400 hover:bg-violet-50 hover:text-violet-600"
                      title="Edit"
                    >
                      <Pencil className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleToggleAutomation(automation)}
                      className={cn(
                        "p-1.5 rounded-lg transition-colors",
                        automation.active ? "text-emerald-600 hover:bg-emerald-50" : "text-neutral-400 hover:bg-neutral-100"
                      )}
                      title={automation.active ? 'Deactivate' : 'Activate'}
                    >
                      <Zap className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDeleteAutomation(automation)}
                      className="p-1.5 rounded-lg text-neutral-400 hover:bg-red-50 hover:text-red-500"
                      title="Delete"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="text-sm text-neutral-500 mb-3">
                  {automation.campaign_ids.length} campaign{automation.campaign_ids.length !== 1 ? 's' : ''}
                </div>

                <div className="space-y-2">
                  {automation.google_sheet_id && (
                    <div className="flex items-center gap-1.5 text-xs text-neutral-500">
                      <FileSpreadsheet className="w-3.5 h-3.5 text-green-600" />
                      <a
                        href={`https://docs.google.com/spreadsheets/d/${automation.google_sheet_id}${automation.google_sheet_name?.includes('#') ? '/edit?gid=' + automation.google_sheet_name.split('#')[1] + '#gid=' + automation.google_sheet_name.split('#')[1] : ''}`}
                        target="_blank"
                        rel="noopener"
                        className="text-green-600 hover:underline truncate"
                      >
                        {automation.google_sheet_name?.split('#')[0] || "Google Sheet"}
                      </a>
                    </div>
                  )}
                  {(automation.slack_webhook_url || automation.slack_channel) && (
                    <div className="flex items-center gap-1.5 text-xs text-neutral-500">
                      <Bell className="w-3.5 h-3.5 text-blue-600" />
                      {automation.slack_channel
                        ? `#${slackChannelsEdit.find(c => c.id === automation.slack_channel)?.name || automation.slack_channel}`
                        : "Slack notifications enabled"}
                    </div>
                  )}
                  <div className="flex items-center gap-1.5 text-xs text-neutral-500">
                    <Zap className="w-3.5 h-3.5 text-amber-500" />
                    {automation.auto_classify ? 'Auto-classify' : 'Manual'} {automation.auto_generate_reply ? '+ draft replies' : ''}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

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
                    <input type="text" placeholder="Paste Google Sheet URL..." value={editGoogleSheetUrl} onChange={(e) => setEditGoogleSheetUrl(e.target.value)} className="input w-full text-sm" />
                    <div className="text-xs text-neutral-400">Or create a new sheet:</div>
                    <div className="flex gap-2">
                      <input type="text" placeholder="New sheet name..." value={editSheetName} onChange={(e) => setEditSheetName(e.target.value)} className="input flex-1 text-sm" />
                      <button onClick={async () => { if (!editSheetName) return; setEditCreatingSheet(true); try { const result = await repliesApi.createGoogleSheet(editSheetName); if (result.sheet_url) { setEditGoogleSheetUrl(result.sheet_url); setEditSheetName(''); } } catch { alert('Failed to create sheet'); } finally { setEditCreatingSheet(false); } }} disabled={!editSheetName || editCreatingSheet} className="btn btn-sm bg-green-600 text-white hover:bg-green-700 disabled:opacity-50">{editCreatingSheet ? 'Creating...' : 'Create'}</button>
                    </div>
                  </div>
                ) : editingAutomation.google_sheet_id ? (
                  <a href={`https://docs.google.com/spreadsheets/d/${editingAutomation.google_sheet_id}`} target="_blank" rel="noopener noreferrer" className="text-sm text-green-600 hover:underline break-all">
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
                    <select value={editSlackChannel} onChange={(e) => setEditSlackChannel(e.target.value)} className="input w-full text-sm">
                      <option value="">Select channel...</option>
                      {slackChannelsEdit.map(ch => (<option key={ch.id} value={ch.id}>#{ch.name}</option>))}
                    </select>
                    <div className="text-xs text-neutral-400">Or create a new channel:</div>
                    <div className="flex gap-2">
                      <input type="text" placeholder="new-channel-name" value={editNewChannelName} onChange={(e) => setEditNewChannelName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '-'))} className="input flex-1 text-sm" />
                      <button onClick={async () => { if (!editNewChannelName) return; setEditCreatingChannel(true); try { const result = await repliesApi.createSlackChannel(editNewChannelName); if (result.channel) { setSlackChannelsEdit(prev => [...prev, { id: result.channel!.id, name: result.channel!.name }]); setEditSlackChannel(result.channel.id); setEditNewChannelName(''); } } catch { alert('Failed to create channel'); } finally { setEditCreatingChannel(false); } }} disabled={!editNewChannelName || editCreatingChannel} className="btn btn-sm bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">{editCreatingChannel ? 'Creating...' : 'Create'}</button>
                    </div>
                  </div>
                ) : editingAutomation.slack_channel ? (
                  <span className="text-sm text-blue-600">#{slackChannelsEdit.find(c => c.id === editingAutomation.slack_channel)?.name || editingAutomation.slack_channel}</span>
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
                    {editCampaigns.length > 0 && (
                      <div className="space-y-1 pb-2 border-b border-neutral-200">
                        <div className="text-xs text-emerald-600 font-medium">Selected:</div>
                        {editCampaigns.map(id => {
                          const campaign = campaigns.find(c => String(c.id) === String(id));
                          return (
                            <label key={id} className="flex items-center gap-2 p-1 bg-emerald-50 hover:bg-emerald-100 rounded cursor-pointer">
                              <input type="checkbox" checked={true} onChange={() => setEditCampaigns(editCampaigns.filter(cid => cid !== id))} className="rounded text-emerald-600" />
                              <span className="text-sm truncate text-emerald-700">{campaign?.name || id}</span>
                            </label>
                          );
                        })}
                      </div>
                    )}
                    <input type="text" placeholder="Search campaigns to add..." value={editCampaignSearch} onChange={(e) => setEditCampaignSearch(e.target.value)} className="input w-full text-sm" />
                    <div className="max-h-32 overflow-y-auto space-y-1">
                      {campaigns.filter(c => !editCampaigns.includes(String(c.id))).filter(c => !editCampaignSearch || c.name?.toLowerCase().includes(editCampaignSearch.toLowerCase())).slice(0, 10).map(c => (
                        <label key={c.id} className="flex items-center gap-2 p-1 hover:bg-neutral-100 rounded cursor-pointer">
                          <input type="checkbox" checked={false} onChange={() => setEditCampaigns([...editCampaigns, String(c.id)])} className="rounded" />
                          <span className="text-sm truncate">{c.name}</span>
                        </label>
                      ))}
                    </div>
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

              {/* Prompt Templates */}
              {isEditMode && (
                <div className="space-y-4">
                  <div className="text-sm font-medium text-neutral-700">Prompt Templates</div>
                  <div className="space-y-2">
                    <label className="text-sm text-neutral-600">Classification Prompt</label>
                    <select value={editClassificationTemplate} onChange={(e) => { setEditClassificationTemplate(e.target.value); if (e.target.value === 'default') setEditClassificationPrompt(''); else if (e.target.value !== 'custom') { const tpl = editPromptTemplates.find(t => t.id?.toString() === e.target.value); if (tpl) setEditClassificationPrompt(tpl.prompt_text); } }} className="w-full px-3 py-2 border border-neutral-200 rounded-lg text-sm">
                      <option value="default">Default Classification</option>
                      {editPromptTemplates.filter(t => !t.is_default).map(t => (<option key={t.id} value={t.id?.toString()}>{t.name}</option>))}
                      <option value="custom">Custom (paste below)</option>
                    </select>
                    {editClassificationTemplate === 'custom' && (
                      <textarea placeholder="Paste your classification prompt..." value={editClassificationPrompt} onChange={(e) => setEditClassificationPrompt(e.target.value)} className="w-full h-24 p-3 border border-neutral-200 rounded-lg text-sm font-mono resize-none" />
                    )}
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm text-neutral-600">Reply Prompt</label>
                    <select value={editReplyTemplate} onChange={(e) => { setEditReplyTemplate(e.target.value); if (e.target.value === 'default') setEditReplyPrompt(''); else if (e.target.value !== 'custom') { const tpl = editPromptTemplates.find(t => t.id?.toString() === e.target.value); if (tpl) setEditReplyPrompt(tpl.prompt_text); } }} className="w-full px-3 py-2 border border-neutral-200 rounded-lg text-sm">
                      <option value="default">Default Reply</option>
                      {editPromptTemplates.filter(t => !t.is_default).map(t => (<option key={t.id} value={t.id?.toString()}>{t.name}</option>))}
                      <option value="custom">Custom (paste below)</option>
                    </select>
                    {editReplyTemplate === 'custom' && (
                      <textarea placeholder="Paste your reply prompt..." value={editReplyPrompt} onChange={(e) => setEditReplyPrompt(e.target.value)} className="w-full h-24 p-3 border border-neutral-200 rounded-lg text-sm font-mono resize-none" />
                    )}
                  </div>

                  {/* Prompt Test */}
                  <div className="rounded-xl border-2 border-cyan-200 overflow-hidden">
                    <div className="bg-cyan-100 px-4 py-3">
                      <div className="font-medium text-cyan-900">Test Your Prompts</div>
                      <div className="text-xs text-cyan-600">Paste any email text to see how AI will classify and reply</div>
                    </div>
                    <div className="p-4 bg-white space-y-3">
                      <textarea placeholder="Paste email text here to test..." value={promptTestText} onChange={(e) => setPromptTestText(e.target.value)} className="w-full text-sm h-24 p-3 border border-cyan-200 rounded-lg resize-none" />
                      <button onClick={async () => { if (!promptTestText.trim()) return; setTestingPrompt(true); setPromptTestResult(null); try { const result = await repliesApi.simulateReply({ email_body: promptTestText, classification_prompt: editClassificationPrompt || undefined, reply_prompt: editReplyPrompt || undefined }); setPromptTestResult({ category: result.category, reply: result.draft_reply }); } catch { setPromptTestResult({ category: 'Error: Failed to test' }); } finally { setTestingPrompt(false); } }} disabled={testingPrompt || !promptTestText.trim()} className="btn btn-secondary w-full">{testingPrompt ? 'Testing...' : 'Test Prompts'}</button>
                      {promptTestResult && (
                        <div className="space-y-2">
                          <div className="p-3 bg-cyan-50 rounded-lg">
                            <div className="text-xs font-medium text-cyan-700 mb-1">Classification:</div>
                            <div className="text-sm font-semibold text-cyan-900">{promptTestResult.category}</div>
                          </div>
                          {promptTestResult.reply && (
                            <div className="p-3 bg-emerald-50 rounded-lg">
                              <div className="text-xs font-medium text-emerald-700 mb-1">Reply:</div>
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
              <button onClick={() => { setEditingAutomation(null); setIsEditMode(false); }} className="btn btn-secondary flex-1">Cancel</button>
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
                        classification_prompt: editClassificationTemplate !== 'default' ? editClassificationPrompt : undefined,
                        reply_prompt: editReplyTemplate !== 'default' ? editReplyPrompt : undefined,
                      });
                      await loadAutomations();
                      setIsEditMode(false);
                      setEditingAutomation(null);
                    } catch { alert('Failed to save'); } finally { setSavingEdit(false); }
                  }}
                  disabled={savingEdit}
                  className="btn btn-primary flex-1"
                >{savingEdit ? 'Saving...' : 'Save Changes'}</button>
              ) : (
                <button onClick={() => setIsEditMode(true)} className="btn btn-primary flex-1">Edit</button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Create Automation Modal */}
      {showCreateModal && (
        <CreateAutomationModal
          campaigns={campaigns}
          campaignsLoading={campaignsLoading}
          smartleadError={smartleadError}
          onClose={() => { setShowCreateModal(false); setSelectedCampaignsForCreate([]); }}
          onCreated={() => { setShowCreateModal(false); setSelectedCampaignsForCreate([]); loadAutomations(); }}
          onRetryCampaigns={loadCampaigns}
          initialSelectedCampaigns={selectedCampaignsForCreate}
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
                <button onClick={() => setShowTestFlowModal(false)} className="p-2 hover:bg-neutral-100 rounded-lg"><X className="w-4 h-4" /></button>
              </div>
            </div>
            <div className="p-6 overflow-y-auto flex-1">
              {testFlowStep === 1 && (
                <div className="space-y-4">
                  <div className="p-4 bg-emerald-50 rounded-xl"><p className="text-sm text-emerald-800"><strong>Step 1:</strong> Create a test campaign and send yourself an email.</p></div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Your Email</label>
                    <input type="email" value={testUserEmail} onChange={(e) => setTestUserEmail(e.target.value)} placeholder="your@email.com" className="input w-full" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Send From (Email Account)</label>
                    <select value={selectedEmailAccount || ''} onChange={(e) => setSelectedEmailAccount(e.target.value ? Number(e.target.value) : null)} className="input w-full">
                      <option value="">Auto-select best account</option>
                      {testEmailAccounts.map(acc => (<option key={acc.id} value={acc.id}>{acc.email} ({acc.remaining} remaining)</option>))}
                    </select>
                  </div>
                </div>
              )}
              {testFlowStep === 2 && testCampaignResult && (
                <div className="space-y-4">
                  <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-200">
                    <p className="text-sm font-medium text-emerald-900">{testCampaignResult.campaign_name}</p>
                    <p className="text-xs text-emerald-600 mt-1">Will send to: {testUserEmail}</p>
                  </div>
                </div>
              )}
              {testFlowStep === 3 && (
                <div className="space-y-4">
                  {testCampaignResult && (
                    <div className="p-4 bg-blue-50 rounded-xl flex items-center justify-between">
                      <div>
                        <p className="text-sm text-blue-800 font-medium">Campaign: {testCampaignResult.campaign_name}</p>
                        <p className="text-xs text-blue-600">Status: {testCampaignStatus || 'Checking...'}</p>
                      </div>
                      {testCampaignStatus !== 'ACTIVE' && (
                        <button onClick={async () => { if (!testCampaignResult?.campaign_id) return; setLaunchingCampaign(true); try { await repliesApi.launchCampaign(testCampaignResult.campaign_id); setTestCampaignStatus('ACTIVE'); } catch (e) { console.error(e); } setLaunchingCampaign(false); }} disabled={launchingCampaign} className="btn btn-sm bg-emerald-500 text-white hover:bg-emerald-600">{launchingCampaign ? 'Launching...' : 'Launch'}</button>
                      )}
                    </div>
                  )}
                  <div className="p-4 bg-emerald-50 rounded-xl">
                    <p className="text-sm text-emerald-800 font-medium">Test the flow:</p>
                    <ol className="text-sm text-emerald-700 mt-2 space-y-2 list-decimal list-inside">
                      <li><strong>Check your email</strong> ({testUserEmail})</li>
                      <li><strong>Reply to the email</strong> with any message</li>
                      <li><strong>Watch it appear</strong> in Google Sheet and Slack!</li>
                    </ol>
                  </div>
                </div>
              )}
            </div>
            <div className="p-6 border-t border-neutral-100 flex justify-between">
              {testFlowStep > 1 ? (<button onClick={() => setTestFlowStep(s => s - 1)} className="btn btn-secondary">Back</button>) : <div />}
              {testFlowStep === 1 && (
                <button onClick={async () => {
                  if (!testUserEmail) { toast.error('Enter your email'); return; }
                  setTestFlowLoading(true);
                  const toastId = toast.loading('Creating test campaign...');
                  try {
                    const result = await repliesApi.createTestCampaign(testUserEmail, testUserEmail.split('@')[0] || 'Test', selectedEmailAccount || undefined);
                    if (result.success) {
                      toast.success('Campaign created!', { id: toastId });
                      setTestCampaignResult(result);
                      if (result.campaign_id) setSelectedCampaignsForCreate([result.campaign_id]);
                      setShowTestFlowModal(false);
                      loadCampaigns();
                      setShowCreateModal(true);
                    } else {
                      toast.error(result.error || 'Failed', { id: toastId });
                    }
                  } catch (e: any) { toast.error(e.response?.data?.detail || 'Failed', { id: toastId }); } finally { setTestFlowLoading(false); }
                }} disabled={testFlowLoading || !testUserEmail} className="btn btn-primary">{testFlowLoading ? 'Creating...' : 'Create Test Campaign'}</button>
              )}
              {testFlowStep === 2 && (
                <button onClick={async () => { setShowTestFlowModal(false); await loadCampaigns(); if (testCampaignResult?.campaign_id) setSelectedCampaignsForCreate([testCampaignResult.campaign_id]); setShowCreateModal(true); }} className="btn btn-primary">Set Up Automation</button>
              )}
              {testFlowStep === 3 && (
                <button onClick={() => setShowTestFlowModal(false)} className="btn btn-primary">Done</button>
              )}
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog isOpen={confirmDialog.isOpen} title={confirmDialog.title} message={confirmDialog.message} onConfirm={confirmDialog.onConfirm} onCancel={() => setConfirmDialog(prev => ({ ...prev, isOpen: false }))} />
    </div>
  );
}

// ============= Create Automation Modal =============
interface CreateAutomationModalProps {
  campaigns: SmartleadCampaign[];
  campaignsLoading: boolean;
  smartleadError: string | null;
  onClose: () => void;
  onCreated: () => void;
  onRetryCampaigns: () => void;
  initialSelectedCampaigns?: string[];
}

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
            <div className={cn("w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium transition-colors", isComplete && "bg-emerald-500 text-white", isCurrent && "bg-violet-600 text-white", !isComplete && !isCurrent && "bg-neutral-200 text-neutral-500")}>{isComplete ? <Check className="w-4 h-4" /> : stepNum}</div>
            <span className={cn("text-xs hidden sm:block", isCurrent && "text-violet-600 font-medium", !isCurrent && "text-neutral-400")}>{stepNames[i]}</span>
            {stepNum < totalSteps && <div className={cn("w-6 h-0.5 mx-1", stepNum < currentStep ? "bg-emerald-500" : "bg-neutral-200")} />}
          </div>
        );
      })}
    </div>
  );
}

function CreateAutomationModal({ campaigns, campaignsLoading, smartleadError, onClose, onCreated, onRetryCampaigns, initialSelectedCampaigns = [] }: CreateAutomationModalProps) {
  const [step, setStep] = useState(1);
  const TOTAL_STEPS = 4;
  const [name, setName] = useState('');
  const [selectedCampaigns, setSelectedCampaigns] = useState<string[]>(initialSelectedCampaigns);
  const [searchCampaigns, setSearchCampaigns] = useState('');
  const [createGoogleSheet, setCreateGoogleSheet] = useState(true);
  const [useExistingSheet, setUseExistingSheet] = useState(false);
  const [existingSheetUrl, setExistingSheetUrl] = useState('');
  const [shareSheetEmail, setShareSheetEmail] = useState('');
  const [sheetsStatus, setSheetsStatus] = useState<GoogleSheetsStatus | null>(null);
  const [loadingSheetsStatus, setLoadingSheetsStatus] = useState(false);
  const [slackChannel, setSlackChannel] = useState('');
  const [slackChannels, setSlackChannels] = useState<Array<{ id: string, name: string }>>([]);
  const [slackSearch, setSlackSearch] = useState('');
  const [showChannelDropdown, setShowChannelDropdown] = useState(false);
  const [loadingSlackChannels, setLoadingSlackChannels] = useState(false);
  const [newChannelName, setNewChannelName] = useState('');
  const [creatingChannel, setCreatingChannel] = useState(false);
  const [testingChannel, setTestingChannel] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [autoClassify, setAutoClassify] = useState(true);
  const [autoGenerateReply, setAutoGenerateReply] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [classificationTemplate, setClassificationTemplate] = useState<string>('default');
  const [replyTemplate, setReplyTemplate] = useState<string>('default');
  const [customClassificationPrompt, setCustomClassificationPrompt] = useState('');
  const [customReplyPrompt, setCustomReplyPrompt] = useState('');
  const [promptTemplates, setPromptTemplates] = useState<Array<{ id: number, name: string, prompt_type?: string, is_default?: boolean }>>([]);

  useEffect(() => {
    if (initialSelectedCampaigns.length > 0) {
      const now = new Date();
      setName(`Demo reply automation ${String(now.getDate()).padStart(2, '0')}/${String(now.getMonth() + 1).padStart(2, '0')}`);
    }
  }, [initialSelectedCampaigns]);

  useEffect(() => {
    if (initialSelectedCampaigns.length > 0 && campaigns.length > 0 && selectedCampaigns.length === 0) {
      const matchingIds = initialSelectedCampaigns.filter(id => campaigns.some(c => c.id === id));
      if (matchingIds.length > 0) setSelectedCampaigns(matchingIds);
    }
  }, [campaigns, initialSelectedCampaigns]);

  useEffect(() => {
    if (step === 2 && !sheetsStatus && !loadingSheetsStatus) {
      setLoadingSheetsStatus(true);
      repliesApi.getGoogleSheetsStatus().then(setSheetsStatus).catch(() => setSheetsStatus({ configured: false, service_account_email: null, message: 'Failed' })).finally(() => setLoadingSheetsStatus(false));
    }
  }, [step, sheetsStatus, loadingSheetsStatus]);

  useEffect(() => {
    if (step === 3 && slackChannels.length === 0 && !loadingSlackChannels) {
      setLoadingSlackChannels(true);
      repliesApi.getSlackChannels().then(res => { if (res.channels) setSlackChannels(res.channels.map(c => ({ id: c.id, name: c.name }))); }).catch(console.error).finally(() => setLoadingSlackChannels(false));
    }
  }, [step]);

  useEffect(() => {
    if (step === 4 && promptTemplates.length === 0) {
      fetch('/api/replies/prompt-templates').then(res => res.json()).then(data => setPromptTemplates(data.templates || [])).catch(console.error);
    }
  }, [step, promptTemplates.length]);

  const filteredCampaigns = campaigns.filter(c => c.name?.toLowerCase().includes(searchCampaigns.toLowerCase()) || String(c.id || "").includes(searchCampaigns.toLowerCase()));

  const handleCreate = async () => {
    if (!name || selectedCampaigns.length === 0) return;
    setIsCreating(true);
    try {
      const data: ReplyAutomationCreate = {
        name,
        campaign_ids: selectedCampaigns,
        slack_channel: slackChannel || undefined,
        create_google_sheet: createGoogleSheet && !useExistingSheet,
        google_sheet_id: useExistingSheet ? extractSheetId(existingSheetUrl) : undefined,
        google_sheet_name: useExistingSheet ? createSheetNameWithGid(existingSheetUrl) || 'Existing Sheet' : undefined,
        share_sheet_with_email: shareSheetEmail || undefined,
        auto_classify: autoClassify,
        auto_generate_reply: autoGenerateReply,
        classification_prompt: classificationTemplate === 'custom' && customClassificationPrompt ? customClassificationPrompt : undefined,
        reply_prompt: replyTemplate === 'custom' && customReplyPrompt ? customReplyPrompt : undefined,
        active: true,
      };
      await repliesApi.createAutomation(data);
      onCreated();
    } catch (err: any) {
      alert(`Failed: ${err?.response?.data?.detail || err?.message || 'Unknown error'}`);
    } finally {
      setIsCreating(false);
    }
  };

  const canProceed = () => { if (step === 1) return name.trim() && selectedCampaigns.length > 0; return true; };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center"><Zap className="w-5 h-5 text-violet-600" /></div>
            <div><h2 className="text-lg font-semibold">Create Reply Automation</h2><p className="text-sm text-neutral-500">Step {step} of {TOTAL_STEPS}</p></div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-neutral-100 rounded-lg"><X className="w-4 h-4" /></button>
        </div>
        <WizardSteps currentStep={step} totalSteps={TOTAL_STEPS} />
        <div className="flex-1 overflow-auto p-6">
          {step === 1 && (
            <div className="space-y-4">
              <div><label className="block text-sm font-medium text-neutral-700 mb-1">Automation Name</label><input type="text" placeholder="e.g., Sales Campaign Replies" value={name} onChange={(e) => setName(e.target.value)} className="input w-full" autoFocus /></div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">Select Campaigns</label>
                {smartleadError ? (
                  <div className="p-4 bg-red-50 border border-red-100 rounded-xl"><p className="text-sm text-red-700">{smartleadError}</p><button onClick={onRetryCampaigns} className="text-sm text-red-600 underline mt-2">Retry</button></div>
                ) : campaignsLoading ? (
                  <div className="flex items-center justify-center py-8"><RefreshCw className="w-5 h-5 animate-spin text-neutral-400" /><span className="ml-2 text-sm text-neutral-500">Loading...</span></div>
                ) : (
                  <>
                    <div className="relative mb-2"><Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" /><input type="text" placeholder="Search campaigns..." value={searchCampaigns} onChange={(e) => setSearchCampaigns(e.target.value)} className="input pl-9 w-full text-sm" /></div>
                    <div className="border border-neutral-200 rounded-xl max-h-48 overflow-auto">
                      {filteredCampaigns.length === 0 ? (<div className="p-4 text-center text-neutral-500 text-sm">No campaigns found</div>) : filteredCampaigns.map(campaign => (
                        <label key={campaign.id} className="flex items-center gap-3 p-3 hover:bg-neutral-50 cursor-pointer border-b border-neutral-100 last:border-b-0">
                          <input type="checkbox" checked={selectedCampaigns.includes(String(campaign.id))} onChange={(e) => e.target.checked ? setSelectedCampaigns([...selectedCampaigns, String(campaign.id)]) : setSelectedCampaigns(selectedCampaigns.filter(id => id !== String(campaign.id)))} className="rounded text-violet-600" />
                          <div className="flex-1 min-w-0"><div className="text-sm font-medium truncate">{campaign.name || campaign.id}</div></div>
                        </label>
                      ))}
                    </div>
                    {selectedCampaigns.length > 0 && <div className="text-sm text-violet-600 mt-2 font-medium">{selectedCampaigns.length} selected</div>}
                  </>
                )}
              </div>
            </div>
          )}
          {step === 2 && (
            <div className="space-y-4">
              <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4"><p className="text-sm text-emerald-800 font-medium">Log replies to a Google Sheet?</p></div>
              {loadingSheetsStatus ? (<div className="text-center py-8"><RefreshCw className="w-5 h-5 animate-spin text-neutral-400 mx-auto" /></div>) : !sheetsStatus?.configured ? (<div className="p-4 bg-amber-50 rounded-xl"><p className="text-sm text-amber-700">Google Sheets not configured</p></div>) : (
                <div className="space-y-4">
                  <div onClick={() => { setCreateGoogleSheet(true); setUseExistingSheet(false); }} className={cn("p-4 rounded-xl border-2 cursor-pointer", createGoogleSheet ? "border-emerald-500 bg-emerald-50" : "border-neutral-200 hover:border-emerald-300")}><p className="font-medium">Create new Google Sheet</p></div>
                  <div onClick={() => { setCreateGoogleSheet(false); setUseExistingSheet(true); }} className={cn("p-4 rounded-xl border-2 cursor-pointer", useExistingSheet ? "border-blue-500 bg-blue-50" : "border-neutral-200 hover:border-blue-300")}><p className="font-medium">Use existing Google Sheet</p></div>
                  {useExistingSheet && (<div className="p-4 bg-blue-50 rounded-xl"><input type="text" placeholder="https://docs.google.com/spreadsheets/d/..." value={existingSheetUrl} onChange={(e) => setExistingSheetUrl(e.target.value)} className="input w-full text-sm" /></div>)}
                  {createGoogleSheet && (<div className="p-4 bg-neutral-50 rounded-xl"><label className="block text-sm font-medium mb-1">Share with (optional)</label><input type="email" placeholder="team@company.com" value={shareSheetEmail} onChange={(e) => setShareSheetEmail(e.target.value)} className="input w-full text-sm" /></div>)}
                </div>
              )}
            </div>
          )}
          {step === 3 && (
            <div className="space-y-4">
              <div className="bg-blue-50 border border-blue-100 rounded-xl p-4"><p className="text-sm text-blue-800 font-medium">Where should I send notifications?</p></div>
              <div>
                <label className="block text-sm font-medium mb-1">Slack Channel</label>
                {loadingSlackChannels ? <div className="text-sm text-neutral-500 py-2">Loading...</div> : (
                  <select value={slackChannel} onChange={(e) => setSlackChannel(e.target.value)} className="input w-full">
                    <option value="">Select channel...</option>
                    {slackChannels.map(ch => <option key={ch.id} value={ch.id}>#{ch.name}</option>)}
                  </select>
                )}
              </div>
              <div className="border-t border-neutral-100 pt-4">
                <p className="text-sm font-medium mb-2">Or create a new channel</p>
                <div className="flex gap-2">
                  <input type="text" placeholder="new-channel-name" value={newChannelName} onChange={(e) => setNewChannelName(e.target.value.toLowerCase().replace(/[^a-z0-9-_]/g, "-"))} className="input flex-1" />
                  <button onClick={async () => { if (!newChannelName) return; setCreatingChannel(true); try { const result = await repliesApi.createSlackChannel(newChannelName); if (result.channel) { setSlackChannels(prev => [...prev, { id: result.channel!.id, name: result.channel!.name }]); setSlackChannel(result.channel.id); setNewChannelName(''); } } catch { } finally { setCreatingChannel(false); } }} disabled={!newChannelName || creatingChannel} className="btn btn-secondary">{creatingChannel ? 'Creating...' : 'Create'}</button>
                </div>
              </div>
              {slackChannel && (<button onClick={async () => { setTestingChannel(true); setTestResult(null); try { const result = await repliesApi.testSlackChannel(slackChannel); setTestResult(result); } catch (err: any) { setTestResult({ success: false, message: 'Failed' }); } finally { setTestingChannel(false); } }} disabled={testingChannel} className="btn btn-secondary w-full">{testingChannel ? 'Sending...' : 'Send Test Message'}</button>)}
              {testResult && (<div className={cn("p-3 rounded-xl text-sm", testResult.success ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700")}>{testResult.message}</div>)}
            </div>
          )}
          {step === 4 && (
            <div className="space-y-4">
              <div className="border border-neutral-200 rounded-xl divide-y divide-neutral-100">
                <div className="p-4"><div className="text-xs text-neutral-500 uppercase mb-1">Name</div><div className="font-medium">{name}</div></div>
                <div className="p-4"><div className="text-xs text-neutral-500 uppercase mb-1">Campaigns</div><div className="text-sm">{selectedCampaigns.length} selected</div></div>
                <div className="p-4"><div className="text-xs text-neutral-500 uppercase mb-1">Google Sheet</div><div className="font-medium">{createGoogleSheet ? 'Create new' : useExistingSheet ? 'Existing' : 'Skip'}</div></div>
                <div className="p-4"><div className="text-xs text-neutral-500 uppercase mb-1">Slack</div><div className="font-medium">{slackChannel ? `#${slackChannels.find(c => c.id === slackChannel)?.name || slackChannel}` : 'Skip'}</div></div>
              </div>
              <label className="flex items-center justify-between p-3 bg-neutral-50 rounded-xl cursor-pointer"><div className="flex items-center gap-2"><Zap className="w-4 h-4 text-amber-500" /><span className="text-sm font-medium">Auto-classify</span></div><input type="checkbox" checked={autoClassify} onChange={(e) => setAutoClassify(e.target.checked)} className="rounded text-violet-600" /></label>
              <label className="flex items-center justify-between p-3 bg-neutral-50 rounded-xl cursor-pointer"><div className="flex items-center gap-2"><Mail className="w-4 h-4 text-cyan-500" /><span className="text-sm font-medium">Draft replies</span></div><input type="checkbox" checked={autoGenerateReply} onChange={(e) => setAutoGenerateReply(e.target.checked)} className="rounded text-violet-600" /></label>
            </div>
          )}
        </div>
        <div className="px-6 py-4 border-t border-neutral-200 flex gap-3">
          {step > 1 && <button onClick={() => setStep(s => s - 1)} className="btn btn-secondary">Back</button>}
          <div className="flex-1" />
          {step < TOTAL_STEPS ? (
            <button onClick={() => setStep(s => s + 1)} disabled={!canProceed()} className="btn btn-primary">Continue</button>
          ) : (
            <button onClick={handleCreate} disabled={isCreating} className="btn btn-primary">{isCreating ? 'Creating...' : 'Activate Automation'}</button>
          )}
        </div>
      </div>
    </div>
  );
}

export default AutomationsPage;
