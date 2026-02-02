import { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Play, Save, History, Trash2, ChevronDown, Zap, Copy, Loader2
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

const DEFAULT_CLASSIFICATION_PROMPT = `Analyze the following email reply and classify it into one of these categories:

Categories:
- interested: Lead shows interest in the product/service
- not_interested: Lead explicitly declines or shows no interest
- meeting_request: Lead wants to schedule a call or meeting
- question: Lead has questions but hasn't decided
- out_of_office: Auto-reply or out of office message
- unsubscribe: Request to be removed from list
- other: Doesn't fit other categories

Email conversation:
{{conversation}}

Respond with ONLY the category name, nothing else.`;

const DEFAULT_REPLY_PROMPT = `You are a helpful sales assistant. Generate a professional, friendly reply to continue the conversation.

Context:
- We help companies with lead generation and sales automation
- Keep the reply concise (2-3 sentences max)
- Be professional but warm
- If they're interested, suggest a call
- If they have questions, answer briefly and offer more details

Conversation history:
{{conversation}}

Generate a reply:`;

export default function PromptDebugPage() {
  // Template management
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<PromptTemplate | null>(null);
  const [templateDropdownOpen, setTemplateDropdownOpen] = useState(false);
  
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
    
    // Clear previous timeout
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    
    // Debounce search
    searchTimeoutRef.current = setTimeout(() => {
      searchLeads(value);
    }, 300);
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
    
    // Click outside handler for search dropdown
    const handleClickOutside = (e: MouseEvent) => {
      if (searchInputRef.current && !searchInputRef.current.contains(e.target as Node)) {
        setShowSearchDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);
  
  // Save to localStorage on change
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
    
    // Detect prompt type from content
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
    const name = prompt('Template name:', selectedTemplate?.name || 'My Template');
    if (!name) return;
    
    const isClassification = promptText.toLowerCase().includes('classify') || 
                            promptText.toLowerCase().includes('category');
    
    try {
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
    } catch (e) {
      toast.error('Failed to save template');
    }
  };
  
  const handleSelectTemplate = (template: PromptTemplate) => {
    setSelectedTemplate(template);
    setPromptText(template.prompt_text);
    setTemplateDropdownOpen(false);
  };
  
  const handleLoadHistoryItem = (item: RunHistoryItem) => {
    setPromptText(item.prompt);
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
          {/* Template selector */}
          <div className="mb-6">
            <div className="flex items-center gap-4">
              <div className="relative">
                <button
                  onClick={() => setTemplateDropdownOpen(!templateDropdownOpen)}
                  className="btn btn-secondary min-w-[200px] justify-between"
                >
                  <span>{selectedTemplate?.name || 'Select template...'}</span>
                  <ChevronDown className="w-4 h-4" />
                </button>
                
                {templateDropdownOpen && (
                  <>
                    <div className="fixed inset-0 z-10" onClick={() => setTemplateDropdownOpen(false)} />
                    <div className="absolute top-full left-0 mt-1 w-64 bg-white border border-neutral-200 rounded-xl shadow-lg z-20 max-h-64 overflow-auto">
                      <div
                        onClick={() => { setPromptText(DEFAULT_CLASSIFICATION_PROMPT); setSelectedTemplate(null); setTemplateDropdownOpen(false); }}
                        className="px-4 py-2 hover:bg-neutral-50 cursor-pointer border-b"
                      >
                        <div className="font-medium">Default Classification</div>
                        <div className="text-xs text-neutral-500">Built-in template</div>
                      </div>
                      <div
                        onClick={() => { setPromptText(DEFAULT_REPLY_PROMPT); setSelectedTemplate(null); setTemplateDropdownOpen(false); }}
                        className="px-4 py-2 hover:bg-neutral-50 cursor-pointer border-b"
                      >
                        <div className="font-medium">Default Reply</div>
                        <div className="text-xs text-neutral-500">Built-in template</div>
                      </div>
                      {templates.map(t => (
                        <div
                          key={t.id}
                          onClick={() => handleSelectTemplate(t)}
                          className="px-4 py-2 hover:bg-neutral-50 cursor-pointer"
                        >
                          <div className="font-medium">{t.name}</div>
                          <div className="text-xs text-neutral-500">{t.prompt_type}</div>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
              
              <button onClick={handleSaveTemplate} className="btn btn-secondary">
                <Save className="w-4 h-4" />
                Save Template
              </button>
            </div>
          </div>
          
          <div className="grid grid-cols-2 gap-6">
            {/* Left: Input */}
            <div className="space-y-4">
              {/* Lead search with autocomplete */}
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
                  
                  {/* Autocomplete dropdown */}
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
                  placeholder="lead: Hi, I'm interested in learning more...&#10;bdm: Thanks for reaching out! ..."
                  className="w-full h-40 p-3 border border-neutral-200 rounded-lg text-sm font-mono resize-none"
                />
                <p className="text-xs text-neutral-400 mt-1">Format: lead: message / bdm: message</p>
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
                  "w-full min-h-[100px] p-3 rounded-lg text-sm",
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
                  <span className="text-xs text-neutral-400">Use {"{{conversation}}"} placeholder</span>
                </div>
                <textarea
                  value={promptText}
                  onChange={(e) => setPromptText(e.target.value)}
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
