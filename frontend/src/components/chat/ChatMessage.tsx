import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Bot, User, Zap, ThumbsUp, ThumbsDown, Copy, Check,
  ExternalLink, BarChart3, Users, ArrowRight, AlertTriangle, RefreshCw,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { cn } from '../../lib/utils';
import { useTheme } from '../../hooks/useTheme';


export interface ChatMessageData {
  id: string | number;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: string;
  action_type?: string;
  action_data?: Record<string, any>;
  suggestions?: string[];
  feedback?: 'positive' | 'negative' | null;
  tokens_used?: number;
  duration_ms?: number;
}

interface ChatMessageProps {
  message: ChatMessageData;
  projectId?: number;
  onFeedback?: (messageId: string | number, feedback: 'positive' | 'negative') => void;
  isLast?: boolean;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const { isDark } = useTheme();

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className={cn(
        "p-1 rounded transition-colors opacity-0 group-hover:opacity-100",
        isDark ? "hover:bg-[#3c3c3c] text-[#858585]" : "hover:bg-gray-100 text-gray-400"
      )}
      title="Copy"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

function ActionButtons({ action_type, action_data }: { action_type?: string; action_data?: Record<string, any> }) {
  const navigate = useNavigate();
  const { isDark } = useTheme();

  if (!action_type || !action_data) return null;

  const btnClass = cn(
    "inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors mt-2 mr-2",
    isDark
      ? "bg-indigo-600/20 text-indigo-400 hover:bg-indigo-600/30 border border-indigo-500/30"
      : "bg-indigo-50 text-indigo-600 hover:bg-indigo-100 border border-indigo-200"
  );

  const buttons: React.ReactElement[] = [];

  if (action_type === 'show_contacts' && action_data.crm_url) {
    buttons.push(
      <button key="crm" onClick={() => navigate(action_data.crm_url)} className={btnClass}>
        <Users className="w-3.5 h-3.5" /> Open in CRM
      </button>
    );
  }

  if (action_type === 'pipeline_started' || action_type === 'push_started') {
    buttons.push(
      <button key="progress" onClick={() => navigate('/pipeline')} className={btnClass}>
        <ArrowRight className="w-3.5 h-3.5" /> View Progress
      </button>
    );
  }

  if (action_type === 'stats' || action_type === 'show_stats') {
    buttons.push(
      <button key="export" className={btnClass} title="Coming soon">
        <BarChart3 className="w-3.5 h-3.5" /> Export to Sheet
      </button>
    );
  }

  if (action_type === 'show_targets') {
    buttons.push(
      <button key="pipeline" onClick={() => navigate('/pipeline')} className={btnClass}>
        <ExternalLink className="w-3.5 h-3.5" /> Open Pipeline
      </button>
    );
  }

  if ((action_type === 'clay_export_done' || action_type === 'clay_export') && action_data.sheet_url) {
    buttons.push(
      <a key="sheet" href={action_data.sheet_url} target="_blank" rel="noopener noreferrer" className={btnClass}>
        <ExternalLink className="w-3.5 h-3.5" /> Open Google Sheet
      </a>
    );
  }

  if (action_type === 'clay_export' && action_data.status === 'started') {
    buttons.push(
      <span key="loading" className={cn(btnClass, "cursor-default opacity-70")}>
        <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Clay export in progress...
      </span>
    );
  }

  if ((action_type === 'clay_gather_done' || action_type === 'clay_people_done') && action_data.crm_url) {
    buttons.push(
      <button key="crm" onClick={() => navigate(action_data.crm_url)} className={btnClass}>
        <Users className="w-3.5 h-3.5" /> Open in CRM
      </button>
    );
  }

  if ((action_type === 'clay_gather' || action_type === 'clay_people') && action_data.status === 'started') {
    const label = action_type === 'clay_gather'
      ? `Running pipeline for "${action_data.segment || 'segment'}" — see progress below`
      : 'Searching contacts in Clay...';
    buttons.push(
      <span key="loading" className={cn(btnClass, "cursor-default opacity-70")}>
        <RefreshCw className="w-3.5 h-3.5 animate-spin" /> {label}
      </span>
    );
  }

  if ((action_type === 'clay_people_done') && action_data.sheet_url) {
    buttons.push(
      <a key="sheet" href={action_data.sheet_url} target="_blank" rel="noopener noreferrer" className={btnClass}>
        <ExternalLink className="w-3.5 h-3.5" /> Open Google Sheet
      </a>
    );
  }

  if (buttons.length === 0) return null;

  return <div className="flex flex-wrap">{buttons}</div>;
}

function SystemMarkdown({ content, isDark }: { content: string; isDark: boolean }) {
  return (
    <div className="text-sm leading-relaxed prose-sm max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a
              href={href}
              target={href?.startsWith('/') ? undefined : '_blank'}
              rel="noopener noreferrer"
              className="underline cursor-pointer font-medium opacity-90 hover:opacity-100"
            >
              {children}
            </a>
          ),
          p: ({ children }) => <p className="mb-1 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="list-disc pl-4 mb-1 space-y-0.5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-4 mb-1 space-y-0.5">{children}</ol>,
          li: ({ children }) => <li className="text-sm">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          code: ({ children }) => (
            <code className={cn(
              "px-1 py-0.5 rounded text-xs",
              isDark ? "bg-black/20" : "bg-black/5"
            )}>{children}</code>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function SystemBanner({ message }: { message: ChatMessageData }) {
  const { isDark } = useTheme();
  const action = message.action_type;

  // Substep — compact inline status line
  if (action?.includes('substep')) {
    return (
      <div className={cn(
        "rounded-lg px-3 py-1.5 border text-xs flex items-center gap-2",
        isDark ? "bg-[#1e1e2e] border-indigo-800/30 text-indigo-300/80" : "bg-indigo-50/50 border-indigo-100 text-indigo-600/80"
      )}>
        <RefreshCw className={cn("w-3 h-3 animate-spin flex-shrink-0", isDark ? "text-indigo-500/60" : "text-indigo-400/60")} />
        <span>{message.content}</span>
      </div>
    );
  }

  // Progress — blue/indigo with spinner
  if (action?.includes('progress')) {
    return (
      <div className={cn(
        "rounded-xl px-4 py-3 border",
        isDark ? "bg-indigo-900/20 border-indigo-700/30 text-indigo-200" : "bg-indigo-50 border-indigo-200 text-indigo-900"
      )}>
        <div className="flex gap-2.5">
          <RefreshCw className={cn("w-4 h-4 flex-shrink-0 mt-0.5 animate-spin", isDark ? "text-indigo-400" : "text-indigo-500")} />
          <SystemMarkdown content={message.content} isDark={isDark} />
        </div>
      </div>
    );
  }

  // Pipeline completion
  if (action?.includes('completed') || action?.includes('done')) {
    return (
      <div className={cn(
        "rounded-xl px-4 py-3 border",
        isDark ? "bg-green-900/20 border-green-700/30 text-green-300" : "bg-green-50 border-green-200 text-green-800"
      )}>
        <div className="flex gap-2.5">
          <Check className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <SystemMarkdown content={message.content} isDark={isDark} />
        </div>
      </div>
    );
  }

  // Budget warning
  if (action?.includes('budget') || action?.includes('warning')) {
    return (
      <div className={cn(
        "rounded-xl px-4 py-3 border",
        isDark ? "bg-amber-900/20 border-amber-700/30 text-amber-300" : "bg-amber-50 border-amber-200 text-amber-800"
      )}>
        <div className="flex gap-2.5">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <SystemMarkdown content={message.content} isDark={isDark} />
        </div>
      </div>
    );
  }

  // Error
  if (action?.includes('error')) {
    return (
      <div className={cn(
        "rounded-xl px-4 py-3 border",
        isDark ? "bg-red-900/20 border-red-700/30 text-red-300" : "bg-red-50 border-red-200 text-red-800"
      )}>
        <div className="flex gap-2.5">
          <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
          <SystemMarkdown content={message.content} isDark={isDark} />
        </div>
      </div>
    );
  }

  // Default system message
  return (
    <div className={cn(
      "rounded-xl px-4 py-3 border",
      isDark ? "bg-[#2a2a2e] border-[#3c3c3c] text-[#c0c0c0]" : "bg-gray-50 border-gray-200 text-gray-700"
    )}>
      <div className="flex gap-2.5">
        <Zap className="w-4 h-4 flex-shrink-0 mt-0.5 opacity-60" />
        <SystemMarkdown content={message.content} isDark={isDark} />
      </div>
    </div>
  );
}

export function ChatMessage({ message, onFeedback }: ChatMessageProps) {
  const { isDark } = useTheme();
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  if (isSystem) {
    return (
      <div className="flex justify-center px-4">
        <div className="max-w-[90%] w-full">
          <SystemBanner message={message} />
        </div>
      </div>
    );
  }

  return (
    <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div className="flex items-start gap-3 max-w-[85%] group">
        {!isUser && (
          <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg shadow-indigo-500/30">
            <Bot className="w-4 h-4 text-white" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className={cn(
            'rounded-2xl px-5 py-3.5 shadow-sm',
            isUser
              ? 'bg-gradient-to-r from-indigo-600 to-purple-600 text-white'
              : isDark ? 'bg-[#2d2d2d] border border-[#3c3c3c] text-[#d4d4d4]' : 'bg-white border border-gray-100 text-gray-900'
          )}>
            {isUser ? (
              <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
            ) : (
              <div className="text-sm leading-relaxed prose-sm max-w-none">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    table: ({ children }) => (
                      <div className="overflow-x-auto my-2 relative group/table">
                        <table className={cn(
                          "min-w-full text-xs border-collapse",
                          isDark ? "border-[#3c3c3c]" : "border-gray-200"
                        )}>
                          {children}
                        </table>
                      </div>
                    ),
                    thead: ({ children }) => (
                      <thead className={isDark ? "bg-[#37373d]" : "bg-gray-50"}>
                        {children}
                      </thead>
                    ),
                    th: ({ children }) => (
                      <th className={cn(
                        "px-3 py-1.5 text-left font-semibold border",
                        isDark ? "border-[#4a4a4a] text-[#d4d4d4]" : "border-gray-200 text-gray-700"
                      )}>
                        {children}
                      </th>
                    ),
                    td: ({ children }) => (
                      <td className={cn(
                        "px-3 py-1.5 border",
                        isDark ? "border-[#3c3c3c] text-[#b0b0b0]" : "border-gray-100 text-gray-600"
                      )}>
                        {children}
                      </td>
                    ),
                    tr: ({ children, ...props }) => (
                      <tr className={cn(
                        isDark ? "even:bg-[#2a2a2a]" : "even:bg-gray-50/50"
                      )} {...props}>
                        {children}
                      </tr>
                    ),
                    a: ({ href, children }) => (
                      <a
                        href={href}
                        target={href?.startsWith('/') ? undefined : '_blank'}
                        rel="noopener noreferrer"
                        className="text-indigo-400 hover:text-indigo-300 underline cursor-pointer font-medium"
                      >
                        {children}
                      </a>
                    ),
                    code: ({ children, className }) => {
                      const isInline = !className;
                      if (isInline) {
                        return (
                          <code className={cn(
                            "px-1.5 py-0.5 rounded text-xs",
                            isDark ? "bg-[#37373d] text-[#ce9178]" : "bg-gray-100 text-pink-600"
                          )}>
                            {children}
                          </code>
                        );
                      }
                      return (
                        <div className="relative group/code my-2">
                          <div className="absolute right-2 top-2">
                            <CopyButton text={String(children)} />
                          </div>
                          <code className={cn(
                            "block p-3 rounded-lg text-xs overflow-x-auto",
                            isDark ? "bg-[#1e1e1e] text-[#d4d4d4]" : "bg-gray-50 text-gray-800"
                          )}>
                            {children}
                          </code>
                        </div>
                      );
                    },
                    p: ({ children }) => <p className="mb-1.5 last:mb-0">{children}</p>,
                    ul: ({ children }) => <ul className="list-disc pl-4 mb-1.5 space-y-0.5">{children}</ul>,
                    ol: ({ children }) => <ol className="list-decimal pl-4 mb-1.5 space-y-0.5">{children}</ol>,
                    li: ({ children }) => <li className="text-sm">{children}</li>,
                    strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                    h1: ({ children }) => <h1 className="text-base font-bold mt-2 mb-1">{children}</h1>,
                    h2: ({ children }) => <h2 className="text-sm font-bold mt-2 mb-1">{children}</h2>,
                    h3: ({ children }) => <h3 className="text-sm font-semibold mt-1.5 mb-0.5">{children}</h3>,
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
          </div>

          {/* Action buttons */}
          {!isUser && message.action_data && (
            <ActionButtons action_type={message.action_type} action_data={message.action_data} />
          )}

          {/* Metadata + feedback row */}
          {!isUser && (
            <div className="flex items-center gap-2 mt-1.5 px-1">
              {/* Action type badge */}
              {message.action_type && (
                <span className={cn(
                  "text-[10px] px-1.5 py-0.5 rounded font-medium",
                  isDark ? "bg-[#37373d] text-[#858585]" : "bg-gray-100 text-gray-500"
                )}>
                  {message.action_type}
                </span>
              )}
              {/* Duration */}
              {message.duration_ms && (
                <span className={cn("text-[10px]", isDark ? "text-[#666]" : "text-gray-400")}>
                  {message.duration_ms < 1000
                    ? `${message.duration_ms}ms`
                    : `${(message.duration_ms / 1000).toFixed(1)}s`}
                </span>
              )}
              {/* Spacer */}
              <div className="flex-1" />
              {/* Feedback buttons */}
              {onFeedback && (
                <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => onFeedback(message.id, 'positive')}
                    className={cn(
                      "p-1 rounded transition-colors",
                      message.feedback === 'positive'
                        ? "text-green-500"
                        : isDark ? "text-[#666] hover:text-[#999]" : "text-gray-300 hover:text-gray-500"
                    )}
                    title="Good response"
                  >
                    <ThumbsUp className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => onFeedback(message.id, 'negative')}
                    className={cn(
                      "p-1 rounded transition-colors",
                      message.feedback === 'negative'
                        ? "text-red-500"
                        : isDark ? "text-[#666] hover:text-[#999]" : "text-gray-300 hover:text-gray-500"
                    )}
                    title="Bad response"
                  >
                    <ThumbsDown className="w-3.5 h-3.5" />
                  </button>
                  <CopyButton text={message.content} />
                </div>
              )}
            </div>
          )}
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
