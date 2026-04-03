import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Send, MessageSquare, Trash2, XCircle } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useAppStore } from '../../store/appStore';
import { useTheme } from '../../hooks/useTheme';

// Fallback for non-HTTPS contexts where crypto.randomUUID is unavailable
const uuid = (): string =>
  typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`;
import { api } from '../../api/client';
import {
  ChatMessage,
  type ChatMessageData,
  StreamingMessage,
  SlashCommandMenu,
  resolveSlashCommand,
} from '../chat';

const DEFAULT_SUGGESTIONS = [
  'show knowledge',
  'show stats',
  'show targets',
  'show funnel',
];

export function KnowledgeChatPanel({ projectId }: { projectId: number }) {
  const { isDark } = useTheme();
  const { currentCompany } = useAppStore();

  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>(DEFAULT_SUGGESTIONS);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  const [slashMenuOpen, setSlashMenuOpen] = useState(false);
  const [slashFilter, setSlashFilter] = useState('');
  const [slashSelectedIndex, setSlashSelectedIndex] = useState(0);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const liveSourceRef = useRef<EventSource | null>(null);
  const pidRef = useRef(projectId);

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isStreaming, streamingText]);

  // Load history + live updates when project changes
  useEffect(() => {
    pidRef.current = projectId;
    setMessages([]);
    setHistoryLoaded(false);
    setSuggestions(DEFAULT_SUGGESTIONS);
    setIsLoading(false);
    setIsStreaming(false);
    setStreamingText('');

    loadChatHistory();
    setupLiveUpdates();

    return () => {
      liveSourceRef.current?.close();
      eventSourceRef.current?.close();
    };
  }, [projectId]);

  async function loadChatHistory() {
    try {
      const response = await api.get(`/search/chat/messages/${projectId}`, {
        params: { limit: 200 },
      });
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
      if (pidRef.current === projectId) {
        // Mark "started" messages as completed if a done/error exists later
        const doneTypes = new Set<string>();
        for (const m of msgs) {
          const at = m.action_type || '';
          if (at.includes('done') || at.includes('error') || at.includes('completed')) {
            doneTypes.add(at.split('_done')[0].split('_error')[0].split('_completed')[0]);
          }
        }
        const fixed = msgs.map((m) => {
          if (m.action_data?.status === 'started' && m.action_type) {
            const prefix = m.action_type;
            if (doneTypes.has(prefix)) {
              return { ...m, action_data: { ...m.action_data, status: 'completed' } };
            }
          }
          return m;
        });
        setMessages(fixed);
        setHistoryLoaded(true);
        // If the pipeline already finished, ensure no loading/streaming state lingers
        const lastSystem = [...fixed].reverse().find((m) => m.role === 'system' && m.action_type);
        const lastAt = lastSystem?.action_type || '';
        if (lastAt.includes('done') || lastAt.includes('error') || lastAt.includes('completed')) {
          setIsLoading(false);
          setIsStreaming(false);
        }
        const lastWithSuggestions = [...fixed]
          .reverse()
          .find((m) => m.role === 'assistant' && m.suggestions?.length);
        if (lastWithSuggestions?.suggestions) {
          setSuggestions(lastWithSuggestions.suggestions);
        }
      }
    } catch (err) {
      console.error('Failed to load chat history:', err);
      setHistoryLoaded(true);
    }
  }

  function setupLiveUpdates() {
    liveSourceRef.current?.close();
    const baseUrl = import.meta.env.VITE_API_URL || '';
    const es = new EventSource(
      `${baseUrl}/api/search/chat/live/${projectId}?after_id=0`
    );
    liveSourceRef.current = es;

    es.addEventListener('message', (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.role === 'system' && pidRef.current === projectId) {
          setMessages((prev) => {
            if (prev.some((m) => m.id === data.id)) return prev;
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
            return [
              ...updated,
              {
                id: data.id,
                role: data.role,
                content: data.content,
                timestamp: data.timestamp,
                action_type: data.action_type,
                action_data: data.action_data,
                suggestions: data.suggestions,
              },
            ];
          });
          if (data.suggestions?.length) setSuggestions(data.suggestions);
          // Clear loading/streaming when pipeline finishes via live update
          const at2 = data.action_type || '';
          if (at2.includes('done') || at2.includes('error') || at2.includes('completed')) {
            setIsLoading(false);
            setIsStreaming(false);
          }
        }
      } catch {
        /* ignore */
      }
    });

    let reconnects = 0;
    es.onerror = () => {
      es.close();
      if (reconnects < 5 && pidRef.current === projectId) {
        reconnects++;
        setTimeout(() => setupLiveUpdates(), 10000 * reconnects);
      }
    };
  }

  const handleFeedback = async (
    messageId: string | number,
    feedback: 'positive' | 'negative'
  ) => {
    try {
      await api.patch(
        `/search/chat/messages/${projectId}/${messageId}/feedback`,
        { feedback }
      );
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, feedback } : m))
      );
    } catch (err) {
      console.error('Failed to save feedback:', err);
    }
  };

  const handleSendSSE = useCallback(
    async (text?: string) => {
      let msg = (text || query).trim();
      if (!msg || isLoading || isStreaming) return;

      const resolved = resolveSlashCommand(msg);
      if (resolved) msg = resolved;

      const userMsg: ChatMessageData = {
        id: uuid(),
        role: 'user',
        content: text || query.trim(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setQuery('');
      setSlashMenuOpen(false);
      setIsStreaming(true);
      setStreamingText('');

      if (textareaRef.current) textareaRef.current.style.height = 'auto';

      const companyId = currentCompany?.id;
      if (!companyId) {
        setMessages((prev) => [
          ...prev,
          { id: uuid(), role: 'system', content: 'No company selected.' },
        ]);
        setIsStreaming(false);
        return;
      }

      const baseUrl = import.meta.env.VITE_API_URL || '';
      const params = new URLSearchParams({
        message: msg,
        project_id: String(projectId),
        company_id: String(companyId),
      });

      eventSourceRef.current?.close();
      const es = new EventSource(
        `${baseUrl}/api/search/chat/stream?${params}`
      );
      eventSourceRef.current = es;
      let accumulated = '';
      let doneReceived = false;

      es.addEventListener('token', (event) => {
        try {
          const data = JSON.parse(event.data);
          accumulated += data.text;
          setStreamingText(accumulated);
        } catch {
          /* ignore */
        }
      });

      es.addEventListener('chunk', (event) => {
        try {
          const data = JSON.parse(event.data);
          accumulated = data.text;
          setStreamingText(accumulated);
        } catch {
          /* ignore */
        }
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
          setMessages((prev) => [...prev, assistantMsg]);
          setStreamingText('');
          setIsStreaming(false);
          if (data.suggestions?.length) setSuggestions(data.suggestions);
        } catch {
          setIsStreaming(false);
          setStreamingText('');
        }
      });

      es.addEventListener('error', (event) => {
        if (!doneReceived) {
          try {
            const data = JSON.parse((event as any).data);
            setMessages((prev) => [
              ...prev,
              { id: uuid(), role: 'system', content: `Error: ${data.message}` },
            ]);
          } catch {
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
          handleSendPOST(msg);
        }
      };
    },
    [query, projectId, isLoading, isStreaming, currentCompany]
  );

  async function handleSendPOST(msg: string) {
    setIsStreaming(false);
    setStreamingText('');
    setIsLoading(true);
    try {
      const response = await api.post('/search/chat', {
        message: msg,
        project_id: projectId,
        max_queries: 500,
        target_goal: 200,
      });
      const data = response.data;
      setMessages((prev) => [
        ...prev,
        {
          id: uuid(),
          role: 'assistant',
          content: data.reply,
          action_type: data.action,
          action_data: data.data,
          suggestions: data.suggestions,
        },
      ]);
      if (data.suggestions?.length) setSuggestions(data.suggestions);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: uuid(),
          role: 'system',
          content: 'Failed to get response. Please try again.',
        },
      ]);
    } finally {
      setIsLoading(false);
      textareaRef.current?.focus();
    }
  }

  function handleQueryChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value;
    setQuery(val);
    const ta = e.target;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 150) + 'px';
    if (val.startsWith('/')) {
      setSlashMenuOpen(true);
      setSlashFilter(val.split(/\s/)[0]);
      setSlashSelectedIndex(0);
    } else {
      setSlashMenuOpen(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (slashMenuOpen) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSlashSelectedIndex((p) => p + 1);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSlashSelectedIndex((p) => Math.max(0, p - 1));
        return;
      }
      if (e.key === 'Escape') {
        setSlashMenuOpen(false);
        return;
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendSSE();
    }
  }

  function handleSlashSelect(cmd: { command: string; example: string }) {
    setQuery(cmd.command + ' ');
    setSlashMenuOpen(false);
    textareaRef.current?.focus();
  }

  const isBusy = isLoading || isStreaming;

  const handleClearChat = async () => {
    if (!currentCompany?.id) return;
    try {
      await api.post(`/search/chat/${projectId}/clear`);
      setMessages([]);
      setSuggestions(DEFAULT_SUGGESTIONS);
    } catch (err) {
      console.error('Failed to clear chat:', err);
    }
  };

  const handleCancelPipeline = async () => {
    if (!currentCompany?.id) return;
    try {
      await api.post(`/search/chat/${projectId}/cancel`);
      setMessages((prev) => [
        ...prev,
        { id: uuid(), role: 'system', content: 'Pipeline cancelled by operator.', action_type: 'error' },
      ]);
    } catch (err) {
      console.error('Failed to cancel pipeline:', err);
    }
  };

  const lastMsg = messages[messages.length - 1];
  // Check if the last message is a substep/progress that is NOT from a completed pipeline
  const lastIsProgressType = lastMsg?.role === 'system' &&
    (lastMsg.action_type?.includes('substep') || lastMsg.action_type?.includes('progress')) &&
    !lastMsg.action_type?.includes('done') && !lastMsg.action_type?.includes('completed') && !lastMsg.action_type?.includes('error');
  // Also verify no done/error/completed message exists anywhere for the same pipeline prefix
  const pipelineDone = lastIsProgressType && messages.some((m) => {
    const at = m.action_type || '';
    return at.includes('done') || at.includes('error') || at.includes('completed');
  });
  const hasRunningPipeline = lastIsProgressType && !pipelineDone;

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {historyLoaded && messages.length === 0 && !isBusy && (
          <div
            className="flex flex-col items-center justify-center h-full text-center"
            style={{ color: isDark ? '#858585' : '#9ca3af' }}
          >
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center mb-3"
              style={{ background: isDark ? '#2d2d2d' : '#f3f4f6' }}
            >
              <MessageSquare className="w-7 h-7 opacity-40" />
            </div>
            <p className="text-sm font-medium mb-1">Project Chat</p>
            <p className="text-xs max-w-sm">
              Manage searches, gather TAM, update knowledge, or get stats.
              Type{' '}
              <span
                className="font-mono px-1 py-0.5 rounded"
                style={{ background: isDark ? '#2d2d2d' : '#f3f4f6' }}
              >
                /
              </span>{' '}
              for commands.
            </p>
          </div>
        )}

        {messages.map((message, i) => (
          <ChatMessage
            key={message.id}
            message={message}
            projectId={projectId}
            onFeedback={handleFeedback}
            isLast={i === messages.length - 1 && !pipelineDone}
          />
        ))}

        {isStreaming && <StreamingMessage text={streamingText} isStreaming />}
        {isLoading && !isStreaming && <StreamingMessage text="" isStreaming />}
        <div ref={messagesEndRef} />
      </div>

      {/* Suggestion chips */}
      <div
        className={cn(
          'px-5 pb-2 flex flex-wrap gap-2',
          messages.length === 0 && 'justify-center'
        )}
      >
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => handleSendSSE(s)}
            disabled={isBusy}
            className="px-3 py-1.5 text-xs rounded-lg transition-all duration-200 disabled:opacity-50"
            style={{
              background: isDark ? '#2d2d2d' : '#fff',
              border: `1px solid ${isDark ? '#3c3c3c' : '#e5e7eb'}`,
              color: isDark ? '#b0b0b0' : '#4b5563',
            }}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Input */}
      <div
        className="px-4 py-3 border-t"
        style={{
          borderColor: isDark ? '#333' : '#f3f4f6',
          background: isDark ? '#252526' : '#fff',
        }}
      >
        <div className="flex items-end gap-2">
          {/* Clear chat button */}
          {messages.length > 0 && (
            <button
              onClick={handleClearChat}
              title="Clear chat history"
              className={cn(
                "flex-shrink-0 p-2.5 rounded-xl transition-all duration-200",
                isDark
                  ? "text-gray-400 hover:text-gray-200 hover:bg-[#333] border border-[#3c3c3c]"
                  : "text-gray-400 hover:text-gray-600 hover:bg-gray-100 border border-gray-200"
              )}
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
          {/* Cancel pipeline button */}
          {hasRunningPipeline && (
            <button
              onClick={handleCancelPipeline}
              title="Cancel running pipeline"
              className={cn(
                "flex-shrink-0 p-2.5 rounded-xl transition-all duration-200",
                isDark
                  ? "text-red-400 hover:text-red-300 hover:bg-red-900/30 border border-red-800/40"
                  : "text-red-400 hover:text-red-600 hover:bg-red-50 border border-red-200"
              )}
            >
              <XCircle className="w-4 h-4" />
            </button>
          )}
          {/* Text input */}
          <div className="relative flex-1">
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
                'w-full px-4 py-3 pr-14 rounded-xl transition-all duration-200 resize-none overflow-hidden text-[13px]',
                isDark
                  ? 'bg-[#1e1e1e] border border-[#3c3c3c] text-[#d4d4d4] placeholder-[#666] focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20'
                  : 'border border-gray-200 focus:outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10'
              )}
              style={{ minHeight: '44px', maxHeight: '150px' }}
            />
            <button
              onClick={() => handleSendSSE()}
              disabled={!query.trim() || isBusy}
              className="absolute right-2 bottom-2 p-2 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-lg hover:shadow-lg hover:shadow-indigo-500/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
