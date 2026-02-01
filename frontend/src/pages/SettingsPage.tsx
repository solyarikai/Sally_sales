import { useEffect, useState } from 'react';
import { Key, Check, AlertCircle, Loader2, Zap, Link2, Send, RefreshCw, ChevronRight, Mail, Search } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { settingsApi, integrationsApi } from '../api';
import type { IntegrationStatus, InstantlyDetails, SmartleadDetails, FindymailDetails, MillionVerifierDetails } from '../api/integrations';
import { cn } from '../lib/utils';

type Tab = 'openai' | 'integrations';

// Campaign type used for Smartlead integration
// Removed unused interface - campaigns are loaded dynamically from API

// Integration card definitions
const integrationCards = [
  {
    id: 'instantly',
    name: 'Instantly.ai',
    description: 'Cold email automation platform',
    icon: Send,
    color: 'from-blue-500 to-purple-600',
    image: '/instantly.png',
  },
  {
    id: 'smartlead',
    name: 'Smartlead',
    description: 'Cold outreach & email warmup',
    icon: Send,
    color: 'from-indigo-500 to-blue-600',
    image: '/smartlead.png',
  },
  {
    id: 'findymail',
    name: 'Findymail',
    description: 'Email finder by name/LinkedIn',
    icon: Search,
    color: 'from-emerald-500 to-teal-600',
    image: '/findymail.png',
  },
  {
    id: 'millionverifier',
    name: 'MillionVerifier',
    description: 'Email verification service',
    icon: Check,
    color: 'from-green-500 to-emerald-600',
    image: '/millionverifier.png',
  },
];

export function SettingsPage() {
  const { openaiSettings, setOpenAISettings } = useAppStore();
  const [activeTab, setActiveTab] = useState<Tab>('openai');
  
  // OpenAI state
  const [apiKey, setApiKey] = useState('');
  const [selectedModel, setSelectedModel] = useState('gpt-4o-mini');
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Integrations state
  const [integrations, setIntegrations] = useState<IntegrationStatus[]>([]);
  const [selectedIntegration, setSelectedIntegration] = useState<string | null>(null);
  const [isLoadingIntegrations, setIsLoadingIntegrations] = useState(false);
  const [integrationMessage, setIntegrationMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  
  // Instantly state
  const [instantlyKey, setInstantlyKey] = useState('');
  const [instantlyDetails, setInstantlyDetails] = useState<InstantlyDetails | null>(null);
  
  // Smartlead state
  const [smartleadKey, setSmartleadKey] = useState('');
  const [smartleadDetails, setSmartleadDetails] = useState<SmartleadDetails | null>(null);
  
  // Findymail state
  const [findymailKey, setFindymailKey] = useState('');
  const [findymailDetails, setFindymailDetails] = useState<FindymailDetails | null>(null);
  
  // MillionVerifier state
  const [millionverifierKey, setMillionverifierKey] = useState('');
  const [millionverifierDetails, setMillionverifierDetails] = useState<MillionVerifierDetails | null>(null);

  useEffect(() => {
    loadSettings();
    loadIntegrations();
  }, []);

  const loadSettings = async () => {
    try {
      const settings = await settingsApi.getOpenAI();
      setOpenAISettings(settings);
      setSelectedModel(settings.default_model);
    } catch (err) {
      console.error('Failed to load settings:', err);
    }
  };

  const loadIntegrations = async () => {
    try {
      const data = await integrationsApi.getAll();
      setIntegrations(data.integrations);
    } catch (err) {
      console.error('Failed to load integrations:', err);
    }
  };

  const loadInstantlyDetails = async () => {
    setIsLoadingIntegrations(true);
    try {
      const details = await integrationsApi.getInstantly();
      setInstantlyDetails(details);
    } catch (err) {
      console.error('Failed to load Instantly details:', err);
    } finally {
      setIsLoadingIntegrations(false);
    }
  };

  const loadSmartleadDetails = async () => {
    setIsLoadingIntegrations(true);
    try {
      const details = await integrationsApi.getSmartlead();
      setSmartleadDetails(details);
    } catch (err) {
      console.error('Failed to load Smartlead details:', err);
    } finally {
      setIsLoadingIntegrations(false);
    }
  };

  const loadFindymailDetails = async () => {
    setIsLoadingIntegrations(true);
    try {
      const details = await integrationsApi.getFindymail();
      setFindymailDetails(details);
    } catch (err) {
      console.error('Failed to load Findymail details:', err);
    } finally {
      setIsLoadingIntegrations(false);
    }
  };

  const loadMillionverifierDetails = async () => {
    setIsLoadingIntegrations(true);
    try {
      const details = await integrationsApi.getMillionverifier();
      setMillionverifierDetails(details);
    } catch (err) {
      console.error('Failed to load MillionVerifier details:', err);
    } finally {
      setIsLoadingIntegrations(false);
    }
  };

  const handleSelectIntegration = (id: string) => {
    setSelectedIntegration(id);
    setIntegrationMessage(null);
    
    if (id === 'instantly') {
      loadInstantlyDetails();
    } else if (id === 'smartlead') {
      loadSmartleadDetails();
    } else if (id === 'findymail') {
      loadFindymailDetails();
    } else if (id === 'millionverifier') {
      loadMillionverifierDetails();
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setMessage(null);

    try {
      const settings = await settingsApi.updateOpenAI(apiKey || undefined, selectedModel);
      setOpenAISettings(settings);
      setApiKey('');
      setMessage({ type: 'success', text: 'Settings saved successfully!' });
    } catch (err: any) {
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to save settings',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const handleTest = async () => {
    setIsTesting(true);
    setMessage(null);

    try {
      await settingsApi.testOpenAI();
      setMessage({ type: 'success', text: 'Connection successful!' });
    } catch (err: any) {
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Connection failed',
      });
    } finally {
      setIsTesting(false);
    }
  };

  const handleResetCost = () => {
    localStorage.setItem('total_api_cost', '0');
    window.location.reload();
  };

  const handleConnectInstantly = async () => {
    if (!instantlyKey) return;
    
    setIsLoadingIntegrations(true);
    setIntegrationMessage(null);

    try {
      const details = await integrationsApi.connectInstantly(instantlyKey);
      setInstantlyDetails(details);
      setInstantlyKey('');
      setIntegrationMessage({ type: 'success', text: 'Instantly connected successfully!' });
      loadIntegrations();
    } catch (err: any) {
      setIntegrationMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to connect to Instantly',
      });
    } finally {
      setIsLoadingIntegrations(false);
    }
  };

  const handleDisconnectInstantly = async () => {
    setIsLoadingIntegrations(true);
    try {
      await integrationsApi.disconnectInstantly();
      setInstantlyDetails({ connected: false, campaigns: [] });
      loadIntegrations();
      setIntegrationMessage({ type: 'success', text: 'Instantly disconnected' });
    } catch (err) {
      console.error('Failed to disconnect:', err);
    } finally {
      setIsLoadingIntegrations(false);
    }
  };

  const handleConnectSmartlead = async () => {
    if (!smartleadKey) return;
    
    setIsLoadingIntegrations(true);
    setIntegrationMessage(null);

    try {
      const details = await integrationsApi.connectSmartlead(smartleadKey);
      setSmartleadDetails(details);
      setSmartleadKey('');
      setIntegrationMessage({ type: 'success', text: 'Smartlead connected successfully!' });
      loadIntegrations();
    } catch (err: any) {
      setIntegrationMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to connect to Smartlead',
      });
    } finally {
      setIsLoadingIntegrations(false);
    }
  };

  const handleDisconnectSmartlead = async () => {
    setIsLoadingIntegrations(true);
    try {
      await integrationsApi.disconnectSmartlead();
      setSmartleadDetails({ connected: false, campaigns: [] });
      loadIntegrations();
      setIntegrationMessage({ type: 'success', text: 'Smartlead disconnected' });
    } catch (err) {
      console.error('Failed to disconnect:', err);
    } finally {
      setIsLoadingIntegrations(false);
    }
  };

  const handleConnectFindymail = async () => {
    if (!findymailKey) return;
    
    setIsLoadingIntegrations(true);
    setIntegrationMessage(null);

    try {
      const details = await integrationsApi.connectFindymail(findymailKey);
      setFindymailDetails(details);
      setFindymailKey('');
      setIntegrationMessage({ type: 'success', text: 'Findymail connected successfully!' });
      loadIntegrations();
    } catch (err: any) {
      setIntegrationMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to connect to Findymail',
      });
    } finally {
      setIsLoadingIntegrations(false);
    }
  };

  const handleDisconnectFindymail = async () => {
    setIsLoadingIntegrations(true);
    try {
      await integrationsApi.disconnectFindymail();
      setFindymailDetails({ connected: false, credits: null });
      loadIntegrations();
      setIntegrationMessage({ type: 'success', text: 'Findymail disconnected' });
    } catch (err) {
      console.error('Failed to disconnect:', err);
    } finally {
      setIsLoadingIntegrations(false);
    }
  };

  const handleConnectMillionverifier = async () => {
    if (!millionverifierKey) return;
    
    setIsLoadingIntegrations(true);
    setIntegrationMessage(null);

    try {
      const details = await integrationsApi.connectMillionverifier(millionverifierKey);
      setMillionverifierDetails(details);
      setMillionverifierKey('');
      setIntegrationMessage({ type: 'success', text: 'MillionVerifier connected successfully!' });
      loadIntegrations();
    } catch (err: any) {
      setIntegrationMessage({
        type: 'error',
        text: err.response?.data?.detail || 'Failed to connect to MillionVerifier',
      });
    } finally {
      setIsLoadingIntegrations(false);
    }
  };

  const handleDisconnectMillionverifier = async () => {
    setIsLoadingIntegrations(true);
    try {
      await integrationsApi.disconnectMillionverifier();
      setMillionverifierDetails({ connected: false, credits: null });
      loadIntegrations();
      setIntegrationMessage({ type: 'success', text: 'MillionVerifier disconnected' });
    } catch (err) {
      console.error('Failed to disconnect:', err);
    } finally {
      setIsLoadingIntegrations(false);
    }
  };

  const handleRefreshCampaigns = async () => {
    setIsLoadingIntegrations(true);
    try {
      const campaigns = await integrationsApi.getInstantlyCampaigns();
      setInstantlyDetails(prev => prev ? { ...prev, campaigns } : null);
    } catch (err) {
      console.error('Failed to refresh campaigns:', err);
    } finally {
      setIsLoadingIntegrations(false);
    }
  };

  const getIntegrationStatus = (id: string): boolean => {
    const integration = integrations.find(i => i.name === id);
    return integration?.connected || false;
  };

  const models = [
    { id: 'gpt-4o-mini', name: 'GPT-4o Mini', desc: 'Fast & affordable', price: '$0.00015/1K' },
    { id: 'gpt-4o', name: 'GPT-4o', desc: 'Most capable', price: '$0.005/1K' },
    { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', desc: '128K context', price: '$0.01/1K' },
    { id: 'gpt-4', name: 'GPT-4', desc: 'Original GPT-4', price: '$0.03/1K' },
    { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', desc: 'Fast & cheap', price: '$0.0005/1K' },
    { id: 'o1', name: 'o1', desc: 'Deep reasoning', price: '$0.015/1K' },
    { id: 'o1-mini', name: 'o1-mini', desc: 'Fast reasoning', price: '$0.003/1K' },
    { id: 'o3-mini', name: 'o3-mini', desc: 'Latest reasoning', price: '$0.002/1K' },
  ];

  const tabs = [
    { id: 'openai' as Tab, label: 'OpenAI', icon: Zap },
    { id: 'integrations' as Tab, label: 'Integrations', icon: Link2 },
  ];

  const selectedCard = integrationCards.find(c => c.id === selectedIntegration);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-neutral-900">Settings</h1>
        <p className="text-sm text-neutral-500 mt-1">Configure your AI and integrations</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-8 border-b border-neutral-200 pb-4">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => { setActiveTab(tab.id); setSelectedIntegration(null); }}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all',
              activeTab === tab.id
                ? 'bg-black text-white'
                : 'text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100'
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* OpenAI Tab */}
      {activeTab === 'openai' && (
        <div className="space-y-8 animate-fade-in">
          {/* API Key Status */}
          <div className={cn(
            'flex items-center gap-4 p-4 rounded-xl border-2',
            openaiSettings?.has_api_key 
              ? 'bg-emerald-50 border-emerald-200' 
              : 'bg-amber-50 border-amber-200'
          )}>
            <div className={cn(
              'w-12 h-12 rounded-xl flex items-center justify-center',
              openaiSettings?.has_api_key ? 'bg-emerald-100' : 'bg-amber-100'
            )}>
              {openaiSettings?.has_api_key ? (
                <Check className="w-6 h-6 text-emerald-600" />
              ) : (
                <AlertCircle className="w-6 h-6 text-amber-600" />
              )}
            </div>
            <div>
              <p className={cn(
                'text-sm font-semibold',
                openaiSettings?.has_api_key ? 'text-emerald-900' : 'text-amber-900'
              )}>
                {openaiSettings?.has_api_key ? 'API Key Configured' : 'No API Key'}
              </p>
              <p className={cn(
                'text-sm',
                openaiSettings?.has_api_key ? 'text-emerald-700' : 'text-amber-700'
              )}>
                {openaiSettings?.has_api_key
                  ? 'Your OpenAI API key is set and ready to use'
                  : 'Add your OpenAI API key to enable enrichment'}
              </p>
            </div>
          </div>

          {/* API Key Input */}
          <div className="card p-5">
            <label className="label">OpenAI API Key</label>
            <div className="relative">
              <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={openaiSettings?.has_api_key ? '••••••••••••••••' : 'sk-proj-...'}
                className="input pl-10"
              />
            </div>
            <p className="mt-2 text-xs text-neutral-500">
              Your API key is stored securely and never exposed to the frontend
            </p>
          </div>

          {/* Model Selection */}
          <div className="card p-5">
            <label className="label">Default AI Model</label>
            <div className="grid grid-cols-2 gap-3">
              {models.map((model) => (
                <button
                  key={model.id}
                  onClick={() => setSelectedModel(model.id)}
                  className={cn(
                    'p-4 rounded-xl border-2 text-left transition-all',
                    selectedModel === model.id
                      ? 'border-black bg-neutral-50'
                      : 'border-neutral-200 hover:border-neutral-300'
                  )}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <Zap className={cn(
                      'w-4 h-4',
                      selectedModel === model.id ? 'text-black' : 'text-neutral-400'
                    )} />
                    <span className="text-sm font-semibold text-neutral-900">{model.name}</span>
                  </div>
                  <div className="text-xs text-neutral-500">{model.desc}</div>
                  <div className="text-xs text-neutral-400 mt-1">{model.price}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Cost Reset */}
          <div className="card p-5">
            <label className="label">API Cost Tracking</label>
            <p className="text-sm text-neutral-600 mb-3">
              Reset the API cost counter to start fresh.
            </p>
            <button
              onClick={handleResetCost}
              className="btn btn-secondary btn-sm"
            >
              Reset Cost Counter
            </button>
          </div>

          {/* Message */}
          {message && (
            <div className={cn(
              'p-4 rounded-xl flex items-center gap-3',
              message.type === 'success'
                ? 'bg-emerald-50 border border-emerald-200 text-emerald-700'
                : 'bg-red-50 border border-red-200 text-red-700'
            )}>
              {message.type === 'success' ? (
                <Check className="w-5 h-5" />
              ) : (
                <AlertCircle className="w-5 h-5" />
              )}
              <span className="text-sm font-medium">{message.text}</span>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={handleTest}
              disabled={isTesting || !openaiSettings?.has_api_key}
              className="btn btn-secondary"
            >
              {isTesting ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Check className="w-4 h-4" />
              )}
              <span>Test Connection</span>
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="btn btn-primary flex-1"
            >
              {isSaving && <Loader2 className="w-4 h-4 animate-spin" />}
              <span>Save Settings</span>
            </button>
          </div>
        </div>
      )}

      {/* Integrations Tab */}
      {activeTab === 'integrations' && !selectedIntegration && (
        <div className="space-y-6 animate-fade-in">
          {/* Integration Cards Grid */}
          <div className="grid grid-cols-2 gap-4">
            {integrationCards.map((card) => {
              const isConnected = getIntegrationStatus(card.id);
              return (
                <button
                  key={card.id}
                  onClick={() => handleSelectIntegration(card.id)}
                  className="card card-hover p-5 text-left group"
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className={cn(
                      'w-12 h-12 rounded-xl flex items-center justify-center overflow-hidden',
                      !card.image && `bg-gradient-to-br ${card.color}`
                    )}>
                      {card.image ? (
                        <img src={card.image} alt={card.name} className="w-12 h-12 object-cover" />
                      ) : (
                        <card.icon className="w-6 h-6 text-white" />
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        'px-2 py-1 rounded-full text-xs font-medium',
                        isConnected
                          ? 'bg-emerald-100 text-emerald-700'
                          : 'bg-neutral-100 text-neutral-500'
                      )}>
                        {isConnected ? 'Connected' : 'Not connected'}
                      </span>
                      <ChevronRight className="w-4 h-4 text-neutral-400 group-hover:text-neutral-600 transition-colors" />
                    </div>
                  </div>
                  <h3 className="text-base font-semibold text-neutral-900 mb-1">{card.name}</h3>
                  <p className="text-sm text-neutral-500">{card.description}</p>
                </button>
              );
            })}
          </div>

          {/* Coming Soon */}
          <div className="card p-6 border-dashed">
            <div className="text-center">
              <Link2 className="w-8 h-8 text-neutral-300 mx-auto mb-3" />
              <h3 className="text-sm font-semibold text-neutral-600 mb-1">More Integrations Coming Soon</h3>
              <p className="text-xs text-neutral-500">
                GetSales, HubSpot, Salesforce, Apollo, and more...
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Integration Detail View */}
      {activeTab === 'integrations' && selectedIntegration && selectedCard && (
        <div className="space-y-6 animate-fade-in">
          {/* Back button */}
          <button
            onClick={() => setSelectedIntegration(null)}
            className="flex items-center gap-2 text-sm text-neutral-500 hover:text-neutral-900 transition-colors"
          >
            <ChevronRight className="w-4 h-4 rotate-180" />
            Back to integrations
          </button>

          {/* Header */}
          <div className="card p-6">
            <div className="flex items-center gap-4 mb-6">
              <div className={cn(
                'w-14 h-14 rounded-xl flex items-center justify-center overflow-hidden',
                !selectedCard.image && `bg-gradient-to-br ${selectedCard.color}`
              )}>
                {selectedCard.image ? (
                  <img src={selectedCard.image} alt={selectedCard.name} className="w-14 h-14 object-cover" />
                ) : (
                  <selectedCard.icon className="w-7 h-7 text-white" />
                )}
              </div>
              <div className="flex-1">
                <h2 className="text-xl font-semibold text-neutral-900">{selectedCard.name}</h2>
                <p className="text-sm text-neutral-500">{selectedCard.description}</p>
              </div>
              {selectedIntegration === 'instantly' && instantlyDetails?.connected && (
                <span className="px-3 py-1 rounded-full text-sm font-medium bg-emerald-100 text-emerald-700">
                  Connected
                </span>
              )}
              {selectedIntegration === 'smartlead' && smartleadDetails?.connected && (
                <span className="px-3 py-1 rounded-full text-sm font-medium bg-indigo-100 text-indigo-700">
                  Connected
                </span>
              )}
              {selectedIntegration === 'findymail' && findymailDetails?.connected && (
                <span className="px-3 py-1 rounded-full text-sm font-medium bg-emerald-100 text-emerald-700">
                  Connected
                </span>
              )}
              {selectedIntegration === 'millionverifier' && millionverifierDetails?.connected && (
                <span className="px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-700">
                  Connected
                </span>
              )}
            </div>

            {/* Instantly Content */}
            {selectedIntegration === 'instantly' && (
              <>
                {!instantlyDetails?.connected ? (
                  <>
                    <div className="mb-4">
                      <label className="label">Instantly API Key</label>
                      <div className="relative">
                        <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
                        <input
                          type="password"
                          value={instantlyKey}
                          onChange={(e) => setInstantlyKey(e.target.value)}
                          placeholder="Enter your API key"
                          className="input pl-10"
                        />
                      </div>
                      <p className="mt-2 text-xs text-neutral-500">
                        Get your API key from{' '}
                        <a
                          href="https://app.instantly.ai/app/settings/integrations"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:underline"
                        >
                          Instantly Settings → Integrations → API Keys
                        </a>
                      </p>
                    </div>
                    <button
                      onClick={handleConnectInstantly}
                      disabled={isLoadingIntegrations || !instantlyKey}
                      className="btn btn-primary"
                    >
                      {isLoadingIntegrations ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Link2 className="w-4 h-4" />
                      )}
                      <span>Connect Instantly</span>
                    </button>
                  </>
                ) : (
                  <>
                    {/* Campaigns */}
                    <div className="border-t border-neutral-200 pt-6">
                      <div className="flex items-center justify-between mb-4">
                        <label className="label mb-0">Available Campaigns</label>
                        <button
                          onClick={handleRefreshCampaigns}
                          disabled={isLoadingIntegrations}
                          className="btn btn-ghost btn-sm"
                        >
                          <RefreshCw className={cn('w-4 h-4', isLoadingIntegrations && 'animate-spin')} />
                        </button>
                      </div>
                      
                      {instantlyDetails.campaigns.length === 0 ? (
                        <p className="text-sm text-neutral-500">No campaigns found</p>
                      ) : (
                        <div className="space-y-2">
                          {instantlyDetails.campaigns.slice(0, 5).map((campaign) => (
                            <div
                              key={campaign.id}
                              className="flex items-center justify-between p-3 bg-neutral-50 rounded-xl"
                            >
                              <div>
                                <p className="text-sm font-medium text-neutral-900">{campaign.name}</p>
                                <p className="text-xs text-neutral-500">ID: {campaign.id}</p>
                              </div>
                              {campaign.status && (
                                <span className={cn(
                                  'px-2 py-1 rounded-full text-xs font-medium',
                                  campaign.status === 'active'
                                    ? 'bg-emerald-100 text-emerald-700'
                                    : 'bg-neutral-200 text-neutral-600'
                                )}>
                                  {campaign.status}
                                </span>
                              )}
                            </div>
                          ))}
                          {instantlyDetails.campaigns.length > 5 && (
                            <p className="text-xs text-neutral-500 text-center py-2">
                              +{instantlyDetails.campaigns.length - 5} more campaigns available
                            </p>
                          )}
                        </div>
                      )}

                      <p className="mt-4 text-xs text-neutral-500">
                        To send leads to a campaign, use the Export feature on your dataset and select "Send to Instantly"
                      </p>
                    </div>

                    {/* Disconnect */}
                    <div className="border-t border-neutral-200 pt-6 mt-6">
                      <button
                        onClick={handleDisconnectInstantly}
                        disabled={isLoadingIntegrations}
                        className="btn btn-danger btn-sm"
                      >
                        Disconnect Instantly
                      </button>
                    </div>
                  </>
                )}
              </>
            )}

            {/* Smartlead Content */}
            {selectedIntegration === 'smartlead' && (
              <>
                {!smartleadDetails?.connected ? (
                  <>
                    <div className="mb-4">
                      <label className="label">Smartlead API Key</label>
                      <div className="relative">
                        <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
                        <input
                          type="password"
                          value={smartleadKey}
                          onChange={(e) => setSmartleadKey(e.target.value)}
                          placeholder="Enter your API key"
                          className="input pl-10"
                        />
                      </div>
                      <p className="mt-2 text-xs text-neutral-500">
                        Get your API key from{' '}
                        <a
                          href="https://app.smartlead.ai/app/settings"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:underline"
                        >
                          Smartlead → Settings → API
                        </a>
                      </p>
                    </div>
                    <button
                      onClick={handleConnectSmartlead}
                      disabled={isLoadingIntegrations || !smartleadKey}
                      className="btn btn-primary"
                    >
                      {isLoadingIntegrations ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Link2 className="w-4 h-4" />
                      )}
                      <span>Connect Smartlead</span>
                    </button>
                  </>
                ) : (
                  <>
                    {/* Campaigns */}
                    {smartleadDetails.campaigns && smartleadDetails.campaigns.length > 0 && (
                      <div className="border-t border-neutral-200 pt-6">
                        <label className="label mb-4">Available Campaigns</label>
                        <div className="space-y-2 max-h-64 overflow-y-auto">
                          {smartleadDetails.campaigns.map((campaign: any) => (
                            <div
                              key={campaign.id}
                              className="p-3 bg-neutral-50 rounded-lg flex items-center justify-between"
                            >
                              <div>
                                <p className="font-medium text-neutral-900">{campaign.name}</p>
                                {campaign.status && (
                                  <p className="text-xs text-neutral-500 capitalize">{campaign.status}</p>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Features */}
                    <div className="border-t border-neutral-200 pt-6 mt-6">
                      <label className="label mb-3">Available Features</label>
                      <div className="space-y-2">
                        <div className="flex items-center gap-2 text-sm text-neutral-600">
                          <div className="w-2 h-2 rounded-full bg-emerald-500" />
                          <span>Export leads to campaigns</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm text-neutral-600">
                          <div className="w-2 h-2 rounded-full bg-emerald-500" />
                          <span>Automated cold email outreach</span>
                        </div>
                        <div className="flex items-center gap-2 text-sm text-neutral-600">
                          <div className="w-2 h-2 rounded-full bg-emerald-500" />
                          <span>Email warmup & deliverability</span>
                        </div>
                      </div>
                      <p className="mt-4 text-xs text-neutral-500">
                        Use Export → Smartlead to send leads to your campaigns
                      </p>
                    </div>

                    {/* Disconnect */}
                    <div className="border-t border-neutral-200 pt-6 mt-6">
                      <button
                        onClick={handleDisconnectSmartlead}
                        disabled={isLoadingIntegrations}
                        className="btn btn-danger btn-sm"
                      >
                        Disconnect Smartlead
                      </button>
                    </div>
                  </>
                )}
              </>
            )}

            {/* Findymail Content */}
            {selectedIntegration === 'findymail' && (
              <>
                {!findymailDetails?.connected ? (
                  <>
                    <div className="mb-4">
                      <label className="label">Findymail API Token</label>
                      <div className="relative">
                        <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
                        <input
                          type="password"
                          value={findymailKey}
                          onChange={(e) => setFindymailKey(e.target.value)}
                          placeholder="Enter your API token"
                          className="input pl-10"
                        />
                      </div>
                      <p className="mt-2 text-xs text-neutral-500">
                        Get your API token from{' '}
                        <a
                          href="https://app.findymail.com/user/api-tokens"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:underline"
                        >
                          Findymail → API Tokens
                        </a>
                      </p>
                    </div>
                    <button
                      onClick={handleConnectFindymail}
                      disabled={isLoadingIntegrations || !findymailKey}
                      className="btn btn-primary"
                    >
                      {isLoadingIntegrations ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Link2 className="w-4 h-4" />
                      )}
                      <span>Connect Findymail</span>
                    </button>
                  </>
                ) : (
                  <>
                    {/* Credits */}
                    {findymailDetails.credits && (
                      <div className="border-t border-neutral-200 pt-6">
                        <label className="label mb-4">Account Credits</label>
                        <div className="grid grid-cols-2 gap-4">
                          <div className="p-4 bg-neutral-50 rounded-xl">
                            <div className="flex items-center gap-2 mb-2">
                              <Search className="w-4 h-4 text-neutral-500" />
                              <span className="text-sm font-medium text-neutral-700">Email Finder</span>
                            </div>
                            <p className="text-2xl font-semibold text-neutral-900">
                              {findymailDetails.credits.finder_credits ?? findymailDetails.credits.credits ?? 'N/A'}
                            </p>
                          </div>
                          <div className="p-4 bg-neutral-50 rounded-xl">
                            <div className="flex items-center gap-2 mb-2">
                              <Check className="w-4 h-4 text-neutral-500" />
                              <span className="text-sm font-medium text-neutral-700">Verifier</span>
                            </div>
                            <p className="text-2xl font-semibold text-neutral-900">
                              {findymailDetails.credits.verifier_credits ?? 'N/A'}
                            </p>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Features */}
                    <div className="border-t border-neutral-200 pt-6 mt-6">
                      <label className="label mb-3">Available Features</label>
                      <div className="space-y-2">
                        <div className="flex items-center gap-3 p-3 bg-neutral-50 rounded-xl">
                          <Mail className="w-5 h-5 text-emerald-600" />
                          <div>
                            <p className="text-sm font-medium text-neutral-900">Find Email by Name</p>
                            <p className="text-xs text-neutral-500">Find verified email using name + company domain</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3 p-3 bg-neutral-50 rounded-xl">
                          <Check className="w-5 h-5 text-emerald-600" />
                          <div>
                            <p className="text-sm font-medium text-neutral-900">Email Verification</p>
                            <p className="text-xs text-neutral-500">Verify emails to reduce bounce rates</p>
                          </div>
                        </div>
                      </div>
                      <p className="mt-4 text-xs text-neutral-500">
                        Use Findymail for enrichment by creating a custom prompt template or using the built-in email finder template
                      </p>
                    </div>

                    {/* Disconnect */}
                    <div className="border-t border-neutral-200 pt-6 mt-6">
                      <button
                        onClick={handleDisconnectFindymail}
                        disabled={isLoadingIntegrations}
                        className="btn btn-danger btn-sm"
                      >
                        Disconnect Findymail
                      </button>
                    </div>
                  </>
                )}
              </>
            )}

            {/* MillionVerifier Content */}
            {selectedIntegration === 'millionverifier' && (
              <>
                {!millionverifierDetails?.connected ? (
                  <>
                    <div className="mb-4">
                      <label className="label">MillionVerifier API Key</label>
                      <div className="relative">
                        <Key className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
                        <input
                          type="password"
                          value={millionverifierKey}
                          onChange={(e) => setMillionverifierKey(e.target.value)}
                          placeholder="Enter your API key"
                          className="input pl-10"
                        />
                      </div>
                      <p className="mt-2 text-xs text-neutral-500">
                        Get your API key from{' '}
                        <a
                          href="https://app.millionverifier.com/api"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:underline"
                        >
                          MillionVerifier → API Settings
                        </a>
                      </p>
                    </div>
                    <button
                      onClick={handleConnectMillionverifier}
                      disabled={isLoadingIntegrations || !millionverifierKey}
                      className="btn btn-primary"
                    >
                      {isLoadingIntegrations ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Link2 className="w-4 h-4" />
                      )}
                      <span>Connect MillionVerifier</span>
                    </button>
                  </>
                ) : (
                  <>
                    {/* Credits */}
                    {millionverifierDetails.credits && (
                      <div className="border-t border-neutral-200 pt-6">
                        <label className="label mb-4">Account Credits</label>
                        <div className="p-4 bg-neutral-50 rounded-xl">
                          <div className="flex items-center gap-2 mb-2">
                            <Check className="w-4 h-4 text-green-500" />
                            <span className="text-sm font-medium text-neutral-700">Verification Credits</span>
                          </div>
                          <p className="text-2xl font-semibold text-neutral-900">
                            {millionverifierDetails.credits.credits?.toLocaleString() ?? 'N/A'}
                          </p>
                        </div>
                      </div>
                    )}

                    {/* Features */}
                    <div className="border-t border-neutral-200 pt-6 mt-6">
                      <label className="label mb-3">Verification Results</label>
                      <div className="space-y-2 text-sm text-neutral-600">
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-green-500" />
                          <span><strong>ok</strong> - Valid email, safe to send</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-yellow-500" />
                          <span><strong>catch_all</strong> - Accepts all emails</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-orange-500" />
                          <span><strong>unknown</strong> - Unable to verify</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-red-500" />
                          <span><strong>invalid</strong> - Email doesn't exist</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="w-2 h-2 rounded-full bg-purple-500" />
                          <span><strong>disposable</strong> - Temporary email</span>
                        </div>
                      </div>
                      <p className="mt-4 text-xs text-neutral-500">
                        Use MillionVerifier to validate emails before sending campaigns. Pricing: ~$0.0004/email
                      </p>
                    </div>

                    {/* Disconnect */}
                    <div className="border-t border-neutral-200 pt-6 mt-6">
                      <button
                        onClick={handleDisconnectMillionverifier}
                        disabled={isLoadingIntegrations}
                        className="btn btn-danger btn-sm"
                      >
                        Disconnect MillionVerifier
                      </button>
                    </div>
                  </>
                )}
              </>
            )}
          </div>

          {/* Integration Message */}
          {integrationMessage && (
            <div className={cn(
              'p-4 rounded-xl flex items-center gap-3',
              integrationMessage.type === 'success'
                ? 'bg-emerald-50 border border-emerald-200 text-emerald-700'
                : 'bg-red-50 border border-red-200 text-red-700'
            )}>
              {integrationMessage.type === 'success' ? (
                <Check className="w-5 h-5" />
              ) : (
                <AlertCircle className="w-5 h-5" />
              )}
              <span className="text-sm font-medium">{integrationMessage.text}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
