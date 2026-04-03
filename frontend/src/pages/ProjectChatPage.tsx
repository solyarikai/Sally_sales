import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

// Fallback for non-HTTPS contexts where crypto.randomUUID is unavailable
const uuid = (): string =>
  typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
import {
  Send, BookOpen, Target, Layers, ChevronRight, ChevronDown,
  RefreshCw, BarChart3, MessageSquare, User,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useAppStore } from '../store/appStore';
import { useTheme } from '../hooks/useTheme';
import { api } from '../api/client';
import { knowledgeApi, type KnowledgeGrouped } from '../api/knowledge';
import { ChatMessage, type ChatMessageData, StreamingMessage, SlashCommandMenu, resolveSlashCommand } from '../components/chat';

// ---- Category labels ----
const CATEGORY_META: Record<string, { label: string; icon: typeof Target }> = {
  icp: { label: 'ICP', icon: Target },
  search: { label: 'Search', icon: BarChart3 },
  outreach: { label: 'Outreach', icon: MessageSquare },
  contacts: { label: 'Contacts', icon: User },
  gtm: { label: 'GTM', icon: Layers },
  notes: { label: 'Notes', icon: BookOpen },
};

// ---- Control Panel ----

function ControlPanel({
  projectName,
  knowledge,
  loading,
  onSync,
  onCategoryClick,
}: {
  projectName: string;
  knowledge: KnowledgeGrouped;
  loading: boolean;
  onSync: () => void;
  onCategoryClick: (cat: string) => void;
}) {
  const { isDark } = useTheme();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggleCat = (cat: string) => {
    setExpanded((prev) => ({ ...prev, [cat]: !prev[cat] }));
  };

  const categories = Object.keys(knowledge);

  return (
    <div className={cn(
      "w-64 flex-shrink-0 border-r flex flex-col overflow-hidden",
      isDark ? "bg-[#252526] border-[#333]" : "bg-gray-50 border-gray-200"
    )}>
      <div className={cn("px-4 py-3 border-b", isDark ? "border-[#333]" : "border-gray-200")}>
        <h3 className={cn("text-sm font-semibold truncate", isDark ? "text-[#d4d4d4]" : "text-gray-800")}>
          {projectName}
        </h3>
        <p className={cn("text-xs mt-0.5", isDark ? "text-[#858585]" : "text-gray-500")}>Knowledge Base</p>
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        {categories.length === 0 && !loading && (
          <div className={cn("px-4 py-6 text-center text-xs", isDark ? "text-[#858585]" : "text-gray-400")}>
            No knowledge yet.
            <br />
            <button onClick={onSync} className="mt-2 text-indigo-500 hover:text-indigo-400 underline">
              Sync from existing data
            </button>
          </div>
        )}
        {categories.map((cat) => {
          const meta = CATEGORY_META[cat] || { label: cat, icon: BookOpen };
          const Icon = meta.icon;
          const entries = knowledge[cat] || [];
          const isExpanded = expanded[cat];

          return (
            <div key={cat}>
              <button
                onClick={() => toggleCat(cat)}
                className={cn(
                  "w-full flex items-center gap-2 px-4 py-2 text-left text-xs font-medium transition-colors",
                  isDark ? "text-[#b0b0b0] hover:bg-[#2d2d2d]" : "text-gray-600 hover:bg-gray-100"
                )}
              >
                {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                <Icon className="w-3.5 h-3.5" />
                <span className="flex-1 uppercase tracking-wide">{meta.label}</span>
                <span className={cn("text-[10px] px-1.5 py-0.5 rounded", isDark ? "bg-[#37373d] text-[#858585]" : "bg-gray-200 text-gray-500")}>
                  {entries.length}
                </span>
              </button>
              {isExpanded && entries.map((entry) => (
                <button
                  key={entry.id}
                  onClick={() => onCategoryClick(cat)}
                  className={cn(
                    "w-full pl-10 pr-4 py-1.5 text-left text-xs truncate transition-colors",
                    isDark ? "text-[#969696] hover:bg-[#2d2d2d] hover:text-[#d4d4d4]" : "text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                  )}
                  title={entry.title || entry.key}
                >
                  {entry.title || entry.key}
                </button>
              ))}
            </div>
          );
        })}
      </div>

      <div className={cn("px-3 py-2 border-t", isDark ? "border-[#333]" : "border-gray-200")}>
        <button
          onClick={onSync}
          disabled={loading}
          className={cn(
            "w-full flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs rounded-lg transition-colors",
            isDark
              ? "bg-[#37373d] text-[#b0b0b0] hover:bg-[#3c3c3c] disabled:opacity-50"
              : "bg-gray-200 text-gray-600 hover:bg-gray-300 disabled:opacity-50"
          )}
        >
          <RefreshCw className={cn("w-3 h-3", loading && "animate-spin")} />
          Sync Knowledge
        </button>
      </div>
    </div>
  );
}

// ---- Main Page ----

export function ProjectChatPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { isDark } = useTheme();
  const { currentProject, projects, setCurrentProject, currentCompany } = useAppStore();

  const pid = projectId ? parseInt(projectId, 10) : currentProject?.id;
  const project = projects.find((p) => p.id === pid) || currentProject;
  const projectName = project?.name || `Project ${pid}`;

  // Set current project in store if navigated via URL
  useEffect(() => {
    if (pid && (!currentProject || currentProject.id !== pid)) {
      const p = projects.find((pr) => pr.id === pid);
      if (p) setCurrentProject(p);
    }
  }, [pid, projects]);

  // State
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([
    'show knowledge', 'show stats', 'show targets', 'show funnel',
  ]);
  const [knowledge, setKnowledge] = useState<KnowledgeGrouped>({});
  const [kbLoading, setKbLoading] = useState(false);

  // Slash command menu state
  const [slashMenuOpen, setSlashMenuOpen] = useState(false);
  const [slashFilter, setSlashFilter] = useState('');
  const [slashSelectedIndex, setSlashSelectedIndex] = useState(0);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const liveSourceRef = useRef<EventSource | null>(null);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming, streamingText]);

  // Load chat history + knowledge on mount
  useEffect(() => {
    if (!pid) return;
    loadChatHistory();
    loadKnowledge();
    setupLiveUpdates();

    return () => {
      liveSourceRef.current?.close();
      eventSourceRef.current?.close();
    };
  }, [pid]);

  const loadChatHistory = async () => {
    if (!pid) return;
    try {
      const response = await api.get(`/search/chat/messages/${pid}`, { params: { limit: 200 } });
      const msgs: ChatMessageData[] = response.data.map((m: any) => ({
        id: m.id ?? uuid(),
        role: m.role,
        content: m.content,
        timestamp: m.timestamp,
        action_type: m.action_type,
        action_data: m.action_data,
        suggestions: m.suggestions,
        feedback: m.feedback,
        tokens_used: m.tokens_used,
        duration_ms: m.duration_ms,
      }));
      setMessages(msgs);

      // Restore last suggestions
      const lastAssistant = [...msgs].reverse().find(m => m.role === 'assistant' && m.suggestions?.length);
      if (lastAssistant?.suggestions) {
        setSuggestions(lastAssistant.suggestions);
      }
    } catch (err) {
      console.error('Failed to load chat history:', err);
    }
  };

  const setupLiveUpdates = () => {
    if (!pid) return;
    const baseUrl = import.meta.env.VITE_API_URL || '';
    const lastMsg = messages[messages.length - 1];
    const afterId = typeof lastMsg?.id === 'number' ? lastMsg.id : 0;

    const es = new EventSource(`${baseUrl}/api/search/chat/live/${pid}?after_id=${afterId}`);
    liveSourceRef.current = es;

    es.addEventListener('message', (event) => {
      try {
        const data = JSON.parse(event.data);
        // Only add if we don't already have this message and it's a system message from bg tasks
        if (data.role === 'system') {
          setMessages(prev => {
            if (prev.some(m => m.id === data.id)) return prev;
            let updated = [...prev];
            // When a pipeline finishes, mark the initial "started" message as completed
            const at = data.action_type || '';
            if (at.includes('done') || at.includes('error') || at.includes('completed')) {
              const prefix = at.split('_done')[0].split('_error')[0].split('_completed')[0];
              updated = updated.map((m) =>
                m.action_data?.status === 'started' &&
                m.action_type?.startsWith(prefix)
                  ? { ...m, action_data: { ...m.action_data, status: 'completed' } }
                  : m
              );
            }
            return [...updated, {
              id: data.id,
              role: data.role,
              content: data.content,
              timestamp: data.timestamp,
              action_type: data.action_type,
              action_data: data.action_data,
              suggestions: data.suggestions,
            }];
          });
          if (data.suggestions?.length) {
            setSuggestions(data.suggestions);
          }
        }
      } catch (e) {
        // ignore parse errors
      }
    });

    let reconnectAttempts = 0;
    es.onerror = () => {
      es.close();
      if (reconnectAttempts < 5) {
        reconnectAttempts++;
        setTimeout(() => setupLiveUpdates(), 10000 * reconnectAttempts);
      }
    };
  };

  const loadKnowledge = async () => {
    if (!pid) return;
    setKbLoading(true);
    try {
      const data = await knowledgeApi.getAll(pid);
      setKnowledge(data.knowledge);
    } catch (err) {
      console.error('Failed to load knowledge:', err);
    } finally {
      setKbLoading(false);
    }
  };

  const handleSync = async () => {
    if (!pid) return;
    setKbLoading(true);
    try {
      await knowledgeApi.sync(pid);
      await loadKnowledge();
    } catch (err) {
      console.error('Failed to sync knowledge:', err);
    } finally {
      setKbLoading(false);
    }
  };

  const handleFeedback = async (messageId: string | number, feedback: 'positive' | 'negative') => {
    if (!pid) return;
    try {
      await api.patch(`/search/chat/messages/${pid}/${messageId}/feedback`, { feedback });
      setMessages(prev => prev.map(m => m.id === messageId ? { ...m, feedback } : m));
    } catch (err) {
      console.error('Failed to save feedback:', err);
    }
  };

  const handleSendSSE = useCallback(async (text?: string) => {
    let msg = (text || query).trim();
    if (!msg || !pid || isLoading || isStreaming) return;

    // Resolve slash commands
    const resolved = resolveSlashCommand(msg);
    if (resolved) {
      msg = resolved;
    }

    // Add user message locally
    const userMsg: ChatMessageData = {
      id: uuid(),
      role: 'user',
      content: text || query.trim(), // Show original text (including slash command)
    };
    setMessages(prev => [...prev, userMsg]);
    setQuery('');
    setSlashMenuOpen(false);
    setIsStreaming(true);
    setStreamingText('');

    // Auto-resize textarea back to single line
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }

    const companyId = currentCompany?.id;
    if (!companyId) {
      setMessages(prev => [...prev, { id: uuid(), role: 'system', content: 'No company selected.' }]);
      setIsStreaming(false);
      return;
    }

    const baseUrl = import.meta.env.VITE_API_URL || '';
    const params = new URLSearchParams({
      message: msg,
      project_id: String(pid),
      company_id: String(companyId),
    });

    // Close any existing SSE connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    const es = new EventSource(`${baseUrl}/api/search/chat/stream?${params}`);
    eventSourceRef.current = es;
    let accumulated = '';
    let doneReceived = false;

    es.addEventListener('intent', () => {
      // Intent parsed — could show a preview, but we just let the stream flow
    });

    es.addEventListener('token', (event) => {
      try {
        const data = JSON.parse(event.data);
        accumulated += data.text;
        setStreamingText(accumulated);
      } catch (e) { /* ignore */ }
    });

    es.addEventListener('chunk', (event) => {
      try {
        const data = JSON.parse(event.data);
        accumulated = data.text;
        setStreamingText(accumulated);
      } catch (e) { /* ignore */ }
    });

    es.addEventListener('done', (event) => {
      doneReceived = true;
      es.close();
      try {
        const data = JSON.parse(event.data);
        const assistantMsg: ChatMessageData = {
          id: uuid(),
          role: 'assistant',
          content: data.reply || accumulated,
          action_type: data.action,
          action_data: data.data,
          suggestions: data.suggestions,
          duration_ms: data.duration_ms,
        };

        setMessages(prev => [...prev, assistantMsg]);
        setStreamingText('');
        setIsStreaming(false);

        if (data.suggestions?.length) {
          setSuggestions(data.suggestions);
        }

        // Reload knowledge if relevant
        if (['knowledge_updated', 'show_knowledge'].includes(data.action)) {
          loadKnowledge();
        }
      } catch (e) {
        setIsStreaming(false);
        setStreamingText('');
      }
    });

    es.addEventListener('error', (event) => {
      if (!doneReceived) {
        try {
          const data = JSON.parse((event as any).data);
          setMessages(prev => [...prev, {
            id: uuid(),
            role: 'system',
            content: `Error: ${data.message}`,
          }]);
        } catch (e) {
          // SSE connection error — fall back to POST
          es.close();
          handleSendPOST(msg);
          return;
        }
      }
      es.close();
      setIsStreaming(false);
      setStreamingText('');
    });

    es.onerror = () => {
      if (!doneReceived) {
        es.close();
        // Fall back to POST on connection failure
        handleSendPOST(msg);
      }
    };
  }, [query, pid, isLoading, isStreaming, currentCompany]);

  // POST fallback for when SSE fails
  const handleSendPOST = async (msg: string) => {
    setIsStreaming(false);
    setStreamingText('');
    setIsLoading(true);

    try {
      const response = await api.post('/search/chat', {
        message: msg,
        project_id: pid,
        max_queries: 500,
        target_goal: 200,
      });
      const data = response.data;

      setMessages(prev => [...prev, {
        id: uuid(),
        role: 'assistant',
        content: data.reply,
        action_type: data.action,
        action_data: data.data,
        suggestions: data.suggestions,
      }]);

      if (data.suggestions?.length) {
        setSuggestions(data.suggestions);
      }
      if (['knowledge_updated', 'show_knowledge'].includes(data.action)) {
        loadKnowledge();
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        id: uuid(),
        role: 'system',
        content: 'Failed to get response. Please try again.',
      }]);
    } finally {
      setIsLoading(false);
      textareaRef.current?.focus();
    }
  };

  // Handle textarea input changes
  const handleQueryChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setQuery(val);

    // Auto-grow textarea
    const ta = e.target;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 150) + 'px';

    // Slash command menu
    if (val.startsWith('/')) {
      setSlashMenuOpen(true);
      setSlashFilter(val.split(/\s/)[0]);
      setSlashSelectedIndex(0);
    } else {
      setSlashMenuOpen(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Slash menu navigation
    if (slashMenuOpen) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSlashSelectedIndex(prev => prev + 1);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSlashSelectedIndex(prev => Math.max(0, prev - 1));
        return;
      }
      if (e.key === 'Escape') {
        setSlashMenuOpen(false);
        return;
      }
    }

    // Enter to send (shift+enter for newline)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendSSE();
    }
  };

  const handleSlashSelect = (cmd: { command: string; example: string }) => {
    setQuery(cmd.command + ' ');
    setSlashMenuOpen(false);
    textareaRef.current?.focus();
  };

  const handleCategoryClick = (cat: string) => {
    handleSendSSE(`show ${cat} knowledge`);
  };

  // Redirect if no project
  if (!pid) {
    return (
      <div className={cn("flex items-center justify-center h-full", isDark ? "text-[#858585]" : "text-gray-500")}>
        <div className="text-center">
          <BookOpen className="w-12 h-12 mx-auto mb-4 opacity-30" />
          <p className="text-lg font-medium mb-2">No project selected</p>
          <button
            onClick={() => navigate('/projects')}
            className="text-indigo-500 hover:text-indigo-400 text-sm underline"
          >
            Go to Projects
          </button>
        </div>
      </div>
    );
  }

  const isBusy = isLoading || isStreaming;

  return (
    <div className={cn("flex h-full overflow-hidden", isDark ? "bg-[#1e1e1e]" : "bg-white")}>
      {/* Left: Control Panel */}
      <ControlPanel
        projectName={projectName}
        knowledge={knowledge}
        loading={kbLoading}
        onSync={handleSync}
        onCategoryClick={handleCategoryClick}
      />

      {/* Right: Chat */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {messages.length === 0 && !isBusy && (
            <div className={cn("flex flex-col items-center justify-center h-full text-center", isDark ? "text-[#858585]" : "text-gray-400")}>
              <div className={cn(
                "w-16 h-16 rounded-2xl flex items-center justify-center mb-4",
                isDark ? "bg-[#2d2d2d]" : "bg-gray-100"
              )}>
                <MessageSquare className="w-8 h-8 opacity-40" />
              </div>
              <p className="text-sm font-medium mb-1">Chat with {projectName}</p>
              <p className="text-xs max-w-sm">
                Ask questions, manage searches, update knowledge base, or get stats. Type <span className={cn("font-mono px-1 py-0.5 rounded", isDark ? "bg-[#2d2d2d]" : "bg-gray-100")}>/</span> for commands.
              </p>
            </div>
          )}

          {messages.map((message, i) => (
            <ChatMessage
              key={message.id}
              message={message}
              projectId={pid}
              onFeedback={handleFeedback}
              isLast={i === messages.length - 1}
            />
          ))}

          {/* Streaming message */}
          {isStreaming && (
            <StreamingMessage text={streamingText} isStreaming={true} />
          )}

          {/* Loading indicator for POST fallback */}
          {isLoading && !isStreaming && (
            <StreamingMessage text="" isStreaming={true} />
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion chips */}
        <div className={cn("px-5 pb-2 flex flex-wrap gap-2", messages.length === 0 && "justify-center")}>
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => handleSendSSE(s)}
              disabled={isBusy}
              className={cn(
                "px-3 py-1.5 text-xs rounded-lg transition-all duration-200 disabled:opacity-50",
                isDark
                  ? "bg-[#2d2d2d] border border-[#3c3c3c] text-[#b0b0b0] hover:bg-[#37373d] hover:border-[#4a4a4a]"
                  : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50 hover:border-gray-300"
              )}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Input */}
        <div className={cn("p-4 border-t", isDark ? "border-[#333] bg-[#252526]" : "border-gray-100 bg-white")}>
          <div className="relative">
            {/* Slash command menu */}
            <SlashCommandMenu
              isOpen={slashMenuOpen}
              filter={slashFilter}
              onSelect={handleSlashSelect}
              onClose={() => setSlashMenuOpen(false)}
              selectedIndex={slashSelectedIndex}
            />

            <textarea
              ref={textareaRef}
              value={query}
              onChange={handleQueryChange}
              onKeyDown={handleKeyDown}
              placeholder="Type a message or / for commands..."
              rows={1}
              className={cn(
                "w-full px-4 py-3.5 pr-14 rounded-xl transition-all duration-200 resize-none overflow-hidden",
                isDark
                  ? "bg-[#1e1e1e] border border-[#3c3c3c] text-[#d4d4d4] placeholder-[#666] focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                  : "border border-gray-200 focus:outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10"
              )}
              style={{ minHeight: '48px', maxHeight: '150px' }}
            />
            <button
              onClick={() => handleSendSSE()}
              disabled={!query.trim() || isBusy}
              className="absolute right-2 bottom-2.5 p-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-lg hover:shadow-lg hover:shadow-indigo-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
