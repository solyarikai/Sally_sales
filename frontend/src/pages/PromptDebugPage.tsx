import { useState, useEffect } from 'react';
import { 
  Play, Save, Search, History, Trash2, ChevronDown, Zap, Copy
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
  const [promptType, setPromptType] = useState<'classification' | 'reply'>('classification');
  
  // Editor state
  const [promptText, setPromptText] = useState(DEFAULT_CLASSIFICATION_PROMPT);
  const [conversationInput, setConversationInput] = useState('');
  const [result, setResult] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  
  // Lead search
  const [leadSearch, setLeadSearch] = useState('');
  // Search results not used yet
  const [isSearching, setIsSearching] = useState(false);
  
  // Run history (saved in localStorage)
  const [runHistory, setRunHistory] = useState<RunHistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  
  // Load from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem('promptDebugState');
    if (saved) {
      try {
        const state = JSON.parse(saved);
        if (state.promptText) setPromptText(state.promptText);
        if (state.conversationInput) setConversationInput(state.conversationInput);
        if (state.promptType) setPromptType(state.promptType);
        if (state.runHistory) setRunHistory(state.runHistory);
      } catch (e) {}
    }
    loadTemplates();
  }, []);
  
  // Save to localStorage on change
  useEffect(() => {
    localStorage.setItem('promptDebugState', JSON.stringify({
      promptText,
      conversationInput,
      promptType,
      runHistory
    }));
  }, [promptText, conversationInput, promptType, runHistory]);
  
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
    
    try {
      const resp = await fetch('/api/replies/prompt-debug/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: promptText,
          conversation_history: conversationInput,
          prompt_type: promptType
        })
      });
      
      const data = await resp.json();
      setResult(data.result || 'No result');
      
      // Save to history
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
    
    try {
      const resp = await fetch('/api/replies/prompt-templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          prompt_type: promptType,
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
    setPromptType(template.prompt_type);
    setTemplateDropdownOpen(false);
  };
  
  const handleSearchLead = async () => {
    if (!leadSearch) return;
    
    setIsSearching(true);
    try {
      const resp = await fetch(`/api/replies/smartlead/lead-conversations/${encodeURIComponent(leadSearch)}`);
      const data = await resp.json();
      
      if (data.messages && data.messages.length > 0) {
        // Format conversation
        const formatted = data.messages.map((m: any) => 
          `${m.type === 'SENT' ? 'bdm' : 'lead'}: ${m.body || m.text || ''}`
        ).join('\n\n');
        setConversationInput(formatted);
        toast.success(`Found ${data.messages.length} messages`);
      } else {
        toast.error(data.message || 'No conversations found');
      }
    } catch (e) {
      toast.error('Search failed');
    } finally {
      setIsSearching(false);
    }
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
                        onClick={() => { setPromptText(DEFAULT_CLASSIFICATION_PROMPT); setPromptType('classification'); setSelectedTemplate(null); setTemplateDropdownOpen(false); }}
                        className="px-4 py-2 hover:bg-neutral-50 cursor-pointer border-b"
                      >
                        <div className="font-medium">Default Classification</div>
                        <div className="text-xs text-neutral-500">Built-in template</div>
                      </div>
                      <div
                        onClick={() => { setPromptText(DEFAULT_REPLY_PROMPT); setPromptType('reply'); setSelectedTemplate(null); setTemplateDropdownOpen(false); }}
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
              
              <div className="flex items-center gap-2 bg-neutral-100 rounded-lg p-1">
                <button
                  onClick={() => setPromptType('classification')}
                  className={cn(
                    "px-3 py-1 rounded-md text-sm transition-colors",
                    promptType === 'classification' ? "bg-white shadow text-violet-700" : "text-neutral-600"
                  )}
                >
                  Classification
                </button>
                <button
                  onClick={() => setPromptType('reply')}
                  className={cn(
                    "px-3 py-1 rounded-md text-sm transition-colors",
                    promptType === 'reply' ? "bg-white shadow text-violet-700" : "text-neutral-600"
                  )}
                >
                  Reply
                </button>
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
              {/* Lead search */}
              <div className="bg-white rounded-xl border border-neutral-200 p-4">
                <label className="block text-sm font-medium mb-2">Search Lead Conversation</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={leadSearch}
                    onChange={(e) => setLeadSearch(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearchLead()}
                    placeholder="Enter lead email..."
                    className="input flex-1"
                  />
                  <button
                    onClick={handleSearchLead}
                    disabled={isSearching}
                    className="btn btn-secondary"
                  >
                    {isSearching ? '...' : <Search className="w-4 h-4" />}
                  </button>
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
                  placeholder="lead: Hi, I'm interested in learning more...\nbdm: Thanks for reaching out! ..."
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
