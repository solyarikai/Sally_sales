import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Send, Bot, User, BookOpen, Target, Layers, ChevronRight, ChevronDown,
  RefreshCw, Zap, BarChart3, MessageSquare,
} from 'lucide-react';
import { cn } from '../lib/utils';
import { useAppStore } from '../store/appStore';
import { useTheme } from '../hooks/useTheme';
import { api } from '../api/client';
import { knowledgeApi, type KnowledgeGrouped } from '../api/knowledge';

// ---- Types ----
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
}

interface ChatResponse {
  action: string;
  reply: string;
  project_id?: number;
  job_id?: number;
  suggestions?: string[];
  data?: any;
}

// ---- Small components ----

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1.5 px-3 py-2">
      <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
      <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
      <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const { isDark } = useTheme();

  return (
    <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div className="flex items-start gap-3 max-w-[85%]">
        {!isUser && (
          <div className={cn(
            "w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0",
            isSystem
              ? "bg-amber-100 dark:bg-amber-900/30"
              : "bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg shadow-indigo-500/30"
          )}>
            {isSystem ? (
              <Zap className="w-4 h-4 text-amber-600 dark:text-amber-400" />
            ) : (
              <Bot className="w-4 h-4 text-white" />
            )}
          </div>
        )}
        <div className={cn(
          'rounded-2xl px-5 py-3.5 shadow-sm',
          isUser
            ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white'
            : isSystem
            ? isDark ? 'bg-amber-900/20 border border-amber-700/30 text-amber-300' : 'bg-amber-50 border border-amber-200 text-amber-800'
            : isDark ? 'bg-[#2d2d2d] border border-[#3c3c3c] text-[#d4d4d4]' : 'bg-white border border-gray-100 text-gray-900'
        )}>
          <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
        </div>
        {isUser && (
          <div className={cn(
            "w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0",
            isDark ? "bg-[#37373d]" : "bg-gray-100"
          )}>
            <User className={cn("w-4 h-4", isDark ? "text-[#b0b0b0]" : "text-gray-600")} />
          </div>
        )}
      </div>
    </div>
  );
}

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
      {/* Header */}
      <div className={cn("px-4 py-3 border-b", isDark ? "border-[#333]" : "border-gray-200")}>
        <h3 className={cn("text-sm font-semibold truncate", isDark ? "text-[#d4d4d4]" : "text-gray-800")}>
          {projectName}
        </h3>
        <p className={cn("text-xs mt-0.5", isDark ? "text-[#858585]" : "text-gray-500")}>Knowledge Base</p>
      </div>

      {/* KB sections */}
      <div className="flex-1 overflow-y-auto py-2">
        {categories.length === 0 && !loading && (
          <div className={cn("px-4 py-6 text-center text-xs", isDark ? "text-[#858585]" : "text-gray-400")}>
            No knowledge yet.
            <br />
            <button
              onClick={onSync}
              className={cn("mt-2 text-indigo-500 hover:text-indigo-400 underline")}
            >
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

      {/* Sync button */}
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
  const { currentProject, projects, setCurrentProject } = useAppStore();

  const pid = projectId ? parseInt(projectId, 10) : currentProject?.id;

  // Resolve project name
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
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([
    'show knowledge', 'show stats', 'show targets', 'show funnel',
  ]);
  const [knowledge, setKnowledge] = useState<KnowledgeGrouped>({});
  const [kbLoading, setKbLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Load chat history + knowledge on mount
  useEffect(() => {
    if (!pid) return;
    loadChatHistory();
    loadKnowledge();
  }, [pid]);

  const loadChatHistory = async () => {
    if (!pid) return;
    try {
      const response = await api.get(`/search/chat/messages/${pid}`, { params: { limit: 200 } });
      const msgs: ChatMessage[] = response.data.map((m: any) => ({
        id: m.id?.toString() || crypto.randomUUID(),
        role: m.role,
        content: m.content,
        timestamp: m.timestamp,
      }));
      setMessages(msgs);
    } catch (err) {
      console.error('Failed to load chat history:', err);
    }
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

  const handleSend = useCallback(async (text?: string) => {
    const msg = (text || query).trim();
    if (!msg || !pid || isLoading) return;

    // Add user message
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: msg,
    };
    setMessages((prev) => [...prev, userMsg]);
    setQuery('');
    setIsLoading(true);

    try {
      const response = await api.post('/search/chat', {
        message: msg,
        project_id: pid,
        max_queries: 500,
        target_goal: 200,
      });
      const data: ChatResponse = response.data;

      // Add assistant reply
      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: data.reply,
      };
      setMessages((prev) => [...prev, assistantMsg]);

      if (data.suggestions && data.suggestions.length > 0) {
        setSuggestions(data.suggestions);
      }

      // Reload knowledge if it was modified
      if (['knowledge_updated', 'show_knowledge'].includes(data.action)) {
        loadKnowledge();
      }
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: 'system',
        content: 'Failed to get response. Please try again.',
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  }, [query, pid, isLoading]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleCategoryClick = (cat: string) => {
    handleSend(`show ${cat} knowledge`);
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
          {messages.length === 0 && !isLoading && (
            <div className={cn("flex flex-col items-center justify-center h-full text-center", isDark ? "text-[#858585]" : "text-gray-400")}>
              <div className={cn(
                "w-16 h-16 rounded-2xl flex items-center justify-center mb-4",
                isDark ? "bg-[#2d2d2d]" : "bg-gray-100"
              )}>
                <MessageSquare className="w-8 h-8 opacity-40" />
              </div>
              <p className="text-sm font-medium mb-1">Chat with {projectName}</p>
              <p className="text-xs max-w-sm">
                Ask questions, manage searches, update knowledge base, or get stats. Try one of the suggestions below.
              </p>
            </div>
          )}

          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div className={cn(
                  "rounded-2xl px-5 py-3.5 shadow-sm",
                  isDark ? "bg-[#2d2d2d] border border-[#3c3c3c]" : "bg-white border border-gray-100"
                )}>
                  <TypingIndicator />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion chips */}
        <div className={cn("px-5 pb-2 flex flex-wrap gap-2", messages.length === 0 && "justify-center")}>
          {suggestions.map((s) => (
            <button
              key={s}
              onClick={() => handleSend(s)}
              disabled={isLoading}
              className={cn(
                "px-3 py-1.5 text-xs rounded-lg transition-colors disabled:opacity-50",
                isDark
                  ? "bg-[#2d2d2d] border border-[#3c3c3c] text-[#b0b0b0] hover:bg-[#37373d]"
                  : "bg-white border border-gray-200 text-gray-600 hover:bg-gray-50"
              )}
            >
              {s}
            </button>
          ))}
        </div>

        {/* Input */}
        <div className={cn("p-4 border-t", isDark ? "border-[#333] bg-[#252526]" : "border-gray-100 bg-white")}>
          <div className="relative">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message..."
              className={cn(
                "w-full px-4 py-3.5 pr-14 rounded-xl transition-all duration-200",
                isDark
                  ? "bg-[#1e1e1e] border border-[#3c3c3c] text-[#d4d4d4] placeholder-[#666] focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20"
                  : "border border-gray-200 focus:outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10"
              )}
            />
            <button
              onClick={() => handleSend()}
              disabled={!query.trim() || isLoading}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-lg hover:shadow-lg hover:shadow-indigo-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
