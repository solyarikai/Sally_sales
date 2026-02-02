import { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Play, Save, History, Trash2, ChevronDown, Zap, Copy, Loader2, Edit3
} from 'lucide-react';
import { cn } from '../lib/utils';
import toast, { Toaster } from 'react-hot-toast';

interface PromptTemplate {
  id?: number;
  name: string;
  prompt_type: 'classification' | 'reply';
  prompt_text: string;
  is_default: boolean;
}

interface RunHistoryItem {
  id: string;
  timestamp: Date;
  prompt: string;
  input: string;
  result: string;
}

interface SearchResult {
  email: string;
  campaign_name?: string;
  campaign_id?: string;
}

const DEFAULT_CLASSIFICATION_PROMPT = `Analyze the email reply and classify it into one of these categories:

Categories:
- interested: Lead shows interest in the product/service
- not_interested: Lead explicitly declines or shows no interest
- meeting_request: Lead wants to schedule a call or meeting
- question: Lead has questions but hasn't decided
- out_of_office: Auto-reply or out of office message
- unsubscribe: Request to be removed from list
- other: Doesn't fit other categories

Respond with ONLY the category name, nothing else.`;

const DEFAULT_REPLY_PROMPT = `You are a helpful sales assistant. Generate a professional, friendly reply to continue the conversation.

Context:
- We help companies with lead generation and sales automation
- Keep the reply concise (2-3 sentences max)
- Be professional but warm
- If they're interested, suggest a call
- If they have questions, answer briefly and offer more details

Generate a reply:`;

export default function PromptDebugPage() {
  // Template management
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<PromptTemplate | null>({ name: 'Default Classification', prompt_type: 'classification', prompt_text: '', is_default: true });
  const [templateDropdownOpen, setTemplateDropdownOpen] = useState(false);
  const [templateSearch, setTemplateSearch] = useState('');
  const [editingTemplateName, setEditingTemplateName] = useState(false);
  const [tempTemplateName, setTempTemplateName] = useState('');
  
  // Editor state
  const [promptText, setPromptText] = useState(DEFAULT_CLASSIFICATION_PROMPT);
  const [conversationInput, setConversationInput] = useState('');
  const [result, setResult] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  
  // Lead search with autocomplete
  const [leadSearch, setLeadSearch] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchInputRef = useRef<HTMLDivElement>(null);
  
  // Run history (saved in localStorage)
  const [runHistory, setRunHistory] = useState<RunHistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  
  // Debounced search
  const searchLeads = useCallback(async (query: string) => {
    if (!query || query.length < 2) {
      setSearchResults([]);
      return;
    }
    
    setIsSearching(true);
    try {
      const resp = await fetch(`/api/replies/smartlead/search-leads?q=${encodeURIComponent(query)}`);
      const data = await resp.json();
      setSearchResults(data.results || []);
      setShowSearchDropdown(true);
    } catch (e) {
      console.error('Search failed', e);
    } finally {
      setIsSearching(false);
    }
  }, []);
  
  const handleSearchInputChange = (value: string) => {
    setLeadSearch(value);
    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    searchTimeoutRef.current = setTimeout(() => searchLeads(value), 300);
  };
  
  const handleSelectLead = async (email: string) => {
    setLeadSearch(email);
    setShowSearchDropdown(false);
    setIsSearching(true);
    
    try {
      const resp = await fetch(`/api/replies/smartlead/lead-conversations/${encodeURIComponent(email)}`);
      const data = await resp.json();
      
      if (data.messages && data.messages.length > 0) {
        const formatted = data.messages.map((m: any) => 
          `${m.type === 'SENT' ? 'bdm' : 'lead'}: ${m.body || m.text || ''}`
        ).join('\n\n');
        setConversationInput(formatted);
        toast.success(`Loaded ${data.messages.length} messages`);
      } else {
        toast.error(data.message || 'No conversations found');
      }
    } catch (e) {
      toast.error('Failed to load conversation');
    } finally {
      setIsSearching(false);
    }
  };
  
  // Load from localStorage and URL params on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const inputFromUrl = params.get('input');
    
    if (inputFromUrl) {
      setConversationInput(decodeURIComponent(inputFromUrl));
    }
    
    const saved = localStorage.getItem('promptDebugState');
    if (saved) {
      try {
        const state = JSON.parse(saved);
        if (state.promptText) setPromptText(state.promptText);
        if (!inputFromUrl && state.conversationInput) setConversationInput(state.conversationInput);
        if (state.runHistory) setRunHistory(state.runHistory);
      } catch (e) {}
    }
    loadTemplates();
    
    const handleClickOutside = (e: MouseEvent) => {
      if (searchInputRef.current && !searchInputRef.current.contains(e.target as Node)) {
        setShowSearchDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  
  useEffect(() => {
    localStorage.setItem('promptDebugState', JSON.stringify({
      promptText,
      conversationInput,
      runHistory
    }));
  }, [promptText, conversationInput, runHistory]);
  
  const loadTemplates = async () => {
    try {
      const resp = await fetch('/api/replies/prompt-templates');
      const data = await resp.json();
      setTemplates(data.templates || []);
    } catch (e) {
      console.error('Failed to load templates', e);
    }
  };
  
  const handleRun = async () => {
    if (!promptText || !conversationInput) {
      toast.error('Please enter both prompt and conversation');
      return;
    }
    
    setIsRunning(true);
    setResult('');
    
    const isClassification = promptText.toLowerCase().includes('classify') || 
                            promptText.toLowerCase().includes('category') ||
                            promptText.toLowerCase().includes('categories');
    
    try {
      const resp = await fetch('/api/replies/prompt-debug/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: promptText,
          conversation_history: conversationInput,
          prompt_type: isClassification ? 'classification' : 'reply'
        })
      });
      
      const data = await resp.json();
      setResult(data.result || 'No result');
      
      const historyItem: RunHistoryItem = {
        id: Date.now().toString(),
        timestamp: new Date(),
        prompt: promptText,
        input: conversationInput,
        result: data.result || ''
      };
      setRunHistory(prev => [historyItem, ...prev.slice(0, 49)]);
      
      toast.success('Prompt executed!');
    } catch (e: any) {
      toast.error(e.message || 'Failed to run prompt');
    } finally {
      setIsRunning(false);
    }
  };
  
  const handleSaveTemplate = async () => {
    const now = new Date();
    const defaultName = `${now.toLocaleDateString('en-GB')} ${now.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`;
    const name = prompt('Template name:', selectedTemplate?.name || defaultName);
    if (!name) return;
    
    const isClassification = promptText.toLowerCase().includes('classify') || 
                            promptText.toLowerCase().includes('category');
    
    try {
      if (selectedTemplate?.id) {
        // Update existing
        const resp = await fetch(`/api/replies/prompt-templates/${selectedTemplate.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name,
            prompt_type: isClassification ? 'classification' : 'reply',
            prompt_text: promptText
          })
        });
        if (resp.ok) {
          toast.success('Template updated!');
          loadTemplates();
        }
      } else {
        // Create new
        const resp = await fetch('/api/replies/prompt-templates', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name,
            prompt_type: isClassification ? 'classification' : 'reply',
            prompt_text: promptText,
            is_default: false
          })
        });
        if (resp.ok) {
          toast.success('Template saved!');
          loadTemplates();
        }
      }
    } catch (e) {
      toast.error('Failed to save template');
    }
  };
  
  const handleSelectTemplate = (template: PromptTemplate | null, defaultType?: 'classification' | 'reply') => {
    if (template) {
      setSelectedTemplate(template);
      setPromptText(template.prompt_text);
    } else if (defaultType === 'classification') {
      setSelectedTemplate({ name: 'Default Classification', prompt_type: 'classification', prompt_text: DEFAULT_CLASSIFICATION_PROMPT, is_default: true });
      setPromptText(DEFAULT_CLASSIFICATION_PROMPT);
    } else if (defaultType === 'reply') {
      setSelectedTemplate({ name: 'Default Reply', prompt_type: 'reply', prompt_text: DEFAULT_REPLY_PROMPT, is_default: true });
      setPromptText(DEFAULT_REPLY_PROMPT);
    }
    setTemplateDropdownOpen(false);
  };
  
  const handleRenameTemplate = async () => {
    if (!selectedTemplate?.id || !tempTemplateName) return;
    
    try {
      const resp = await fetch(`/api/replies/prompt-templates/${selectedTemplate.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: tempTemplateName })
      });
      if (resp.ok) {
        setSelectedTemplate({ ...selectedTemplate, name: tempTemplateName });
        toast.success('Renamed!');
        loadTemplates();
      }
    } catch (e) {
      toast.error('Failed to rename');
    }
    setEditingTemplateName(false);
  };
  
  const handleLoadHistoryItem = (item: RunHistoryItem) => {
    setPromptText(item.prompt);
    setSelectedTemplate(null); // Reset when loading from history
    setConversationInput(item.input);
    setResult(item.result);
    setShowHistory(false);
  };
  
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success('Copied!');
  };

  return (
    <div className="h-full flex flex-col bg-neutral-50">
      <Toaster position="top-center" />
      
      {/* Header */}
      <div className="bg-white border-b border-neutral-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-100 flex items-center justify-center">
              <Zap className="w-5 h-5 text-violet-600" />
            </div>
            <div>
              <h1 className="text-xl font-semibold">Prompt Debug</h1>
              <p className="text-sm text-neutral-500">Test and refine your prompts</p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className={cn(
                "btn btn-secondary",
                showHistory && "bg-violet-100 text-violet-700"
              )}
            >
              <History className="w-4 h-4" />
              History ({runHistory.length})
            </button>
          </div>
        </div>
      </div>
      
      <div className="flex-1 p-6 overflow-auto">
        <div className="max-w-6xl mx-auto">
          {/* Template selector with clear indication */}
          <div className="mb-6 bg-white rounded-xl border border-neutral-200 p-4">
            <div className="flex items-center gap-4">
              <div className="relative flex-1">
                <label className="block text-xs text-neutral-500 mb-1">Current Template</label>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setTemplateDropdownOpen(!templateDropdownOpen)}
                    className="btn btn-secondary flex-1 justify-between text-left"
                  >
                    <span className={cn(
                      "font-medium",
                      selectedTemplate ? "text-violet-700" : "text-neutral-500"
                    )}>
                      {selectedTemplate?.name || 'Custom (edited)'}
                    </span>
                    <ChevronDown className="w-4 h-4" />
                  </button>
                  
                  {selectedTemplate?.id && (
                    <button
                      onClick={() => {
                        setTempTemplateName(selectedTemplate.name);
                        setEditingTemplateName(true);
                      }}
                      className="btn btn-secondary p-2"
                      title="Rename template"
                    >
                      <Edit3 className="w-4 h-4" />
                    </button>
                  )}
                </div>
                
                {templateDropdownOpen && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => { setTemplateDropdownOpen(false); setTemplateSearch(''); }} />
                    <div className="absolute top-full left-0 mt-1 w-full bg-white border border-neutral-200 rounded-xl shadow-lg z-20 max-h-80 overflow-hidden">
                      <div className="p-2 border-b">
                        <input
                          type="text"
                          value={templateSearch}
                          onChange={(e) => setTemplateSearch(e.target.value)}
                          placeholder="Search templates..."
                          className="input w-full text-sm"
                          autoFocus
                        />
                      </div>
                      <div className="max-h-64 overflow-auto">
                        {(!templateSearch || 'default classification'.includes(templateSearch.toLowerCase())) && (
                          <div
                            onClick={() => { handleSelectTemplate(null, 'classification'); setTemplateSearch(''); }}
                            className="px-4 py-2 hover:bg-violet-50 cursor-pointer border-b"
                          >
                            <div className="font-medium">Default Classification</div>
                            <div className="text-xs text-neutral-500">Built-in • Categorizes replies</div>
                          </div>
                        )}
                        {(!templateSearch || 'default reply'.includes(templateSearch.toLowerCase())) && (
                          <div
                            onClick={() => { handleSelectTemplate(null, 'reply'); setTemplateSearch(''); }}
                            className="px-4 py-2 hover:bg-violet-50 cursor-pointer border-b"
                          >
                            <div className="font-medium">Default Reply</div>
                            <div className="text-xs text-neutral-500">Built-in • Generates responses</div>
                          </div>
                        )}
                        {templates.filter(t => !templateSearch || t.name.toLowerCase().includes(templateSearch.toLowerCase())).map(t => (
                          <div
                            key={t.id}
                            onClick={() => { handleSelectTemplate(t); setTemplateSearch(''); }}
                            className="px-4 py-2 hover:bg-violet-50 cursor-pointer"
                          >
                            <div className="font-medium">{t.name}</div>
                            <div className="text-xs text-neutral-500">{t.prompt_type}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </div>
              
              <button onClick={handleSaveTemplate} className="btn btn-primary">
                <Save className="w-4 h-4" />
                {selectedTemplate?.id ? 'Update' : 'Save as New'}
              </button>
            </div>
            
            {/* Rename modal */}
            {editingTemplateName && (
              <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                <div className="bg-white rounded-xl p-6 w-96">
                  <h3 className="font-semibold mb-4">Rename Template</h3>
                  <input
                    type="text"
                    value={tempTemplateName}
                    onChange={(e) => setTempTemplateName(e.target.value)}
                    className="input w-full mb-4"
                    autoFocus
                  />
                  <div className="flex justify-end gap-2">
                    <button onClick={() => setEditingTemplateName(false)} className="btn btn-secondary">Cancel</button>
                    <button onClick={handleRenameTemplate} className="btn btn-primary">Save</button>
                  </div>
                </div>
              </div>
            )}
          </div>
          
          <div className="grid grid-cols-2 gap-6">
            {/* Left: Input */}
            <div className="space-y-4">
              {/* Lead search */}
              <div className="bg-white rounded-xl border border-neutral-200 p-4">
                <label className="block text-sm font-medium mb-2">Search Lead Conversation</label>
                <div className="relative" ref={searchInputRef}>
                  <input
                    type="text"
                    value={leadSearch}
                    onChange={(e) => handleSearchInputChange(e.target.value)}
                    onFocus={() => searchResults.length > 0 && setShowSearchDropdown(true)}
                    placeholder="Type email to search..."
                    className="input w-full pr-8"
                  />
                  {isSearching && (
                    <Loader2 className="w-4 h-4 absolute right-3 top-1/2 -translate-y-1/2 animate-spin text-neutral-400" />
                  )}
                  
                  {showSearchDropdown && searchResults.length > 0 && (
                    <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-neutral-200 rounded-lg shadow-lg z-20 max-h-48 overflow-auto">
                      {searchResults.map((r, i) => (
                        <div
                          key={i}
                          onClick={() => handleSelectLead(r.email)}
                          className="px-3 py-2 hover:bg-neutral-50 cursor-pointer"
                        >
                          <div className="text-sm font-medium">{r.email}</div>
                          {r.campaign_name && (
                            <div className="text-xs text-neutral-500">{r.campaign_name}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              
              {/* Conversation input */}
              <div className="bg-white rounded-xl border border-neutral-200 p-4">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium">Conversation History</label>
                  <button onClick={() => copyToClipboard(conversationInput)} className="text-xs text-neutral-500 hover:text-neutral-700">
                    <Copy className="w-3 h-3" />
                  </button>
                </div>
                <textarea
                  value={conversationInput}
                  onChange={(e) => setConversationInput(e.target.value)}
                  placeholder="Paste conversation or search for a lead above..."
                  className="w-full h-40 p-3 border border-neutral-200 rounded-lg text-sm font-mono resize-none"
                />
                <p className="text-xs text-neutral-400 mt-1">Conversation is automatically added to your prompt</p>
              </div>
              
              {/* Result */}
              <div className="bg-white rounded-xl border border-neutral-200 p-4">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium">Result</label>
                  {result && (
                    <button onClick={() => copyToClipboard(result)} className="text-xs text-neutral-500 hover:text-neutral-700">
                      <Copy className="w-3 h-3" />
                    </button>
                  )}
                </div>
                <div className={cn(
                  "w-full min-h-[100px] p-3 rounded-lg text-sm whitespace-pre-wrap",
                  result ? "bg-emerald-50 border border-emerald-200" : "bg-neutral-50 border border-neutral-200"
                )}>
                  {result || <span className="text-neutral-400">Result will appear here...</span>}
                </div>
              </div>
            </div>
            
            {/* Right: Prompt */}
            <div className="space-y-4">
              <div className="bg-white rounded-xl border border-neutral-200 p-4 h-full flex flex-col">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium">Prompt Template</label>
                  <span className="text-xs text-neutral-400">Conversation added automatically</span>
                </div>
                <textarea
                  value={promptText}
                  onChange={(e) => {
                    setPromptText(e.target.value);
                    // If user edits, clear selected template (it's now custom)
                    if (selectedTemplate && e.target.value !== selectedTemplate.prompt_text) {
                      setSelectedTemplate(null);
                    }
                  }}
                  className="flex-1 w-full p-3 border border-neutral-200 rounded-lg text-sm font-mono resize-none min-h-[400px]"
                />
                
                <button
                  onClick={handleRun}
                  disabled={isRunning}
                  className="btn btn-primary mt-4 w-full"
                >
                  {isRunning ? 'Running...' : (
                    <>
                      <Play className="w-4 h-4" />
                      Run Prompt
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
          
          {/* History panel */}
          {showHistory && runHistory.length > 0 && (
            <div className="mt-6 bg-white rounded-xl border border-neutral-200 p-4">
              <h3 className="font-medium mb-3">Run History</h3>
              <div className="space-y-2 max-h-64 overflow-auto">
                {runHistory.map(item => (
                  <div
                    key={item.id}
                    onClick={() => handleLoadHistoryItem(item)}
                    className="p-3 bg-neutral-50 rounded-lg cursor-pointer hover:bg-neutral-100"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium truncate">{item.result.slice(0, 50)}...</span>
                      <span className="text-xs text-neutral-400">
                        {new Date(item.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="text-xs text-neutral-500 truncate mt-1">{item.input.slice(0, 80)}...</p>
                  </div>
                ))}
              </div>
              <button
                onClick={() => { setRunHistory([]); toast.success('History cleared'); }}
                className="btn btn-secondary mt-3 text-sm"
              >
                <Trash2 className="w-3 h-3" />
                Clear History
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
