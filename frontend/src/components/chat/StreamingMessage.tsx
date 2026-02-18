import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useTheme } from '../../hooks/useTheme';

interface StreamingMessageProps {
  text: string;
  isStreaming: boolean;
}

export function StreamingMessage({ text, isStreaming }: StreamingMessageProps) {
  const { isDark } = useTheme();

  return (
    <div className="flex justify-start">
      <div className="flex items-start gap-3 max-w-[85%]">
        <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg shadow-indigo-500/30">
          <Bot className="w-4 h-4 text-white" />
        </div>
        <div className={cn(
          'rounded-2xl px-5 py-3.5 shadow-sm min-w-[40px]',
          isDark ? 'bg-[#2d2d2d] border border-[#3c3c3c] text-[#d4d4d4]' : 'bg-white border border-gray-100 text-gray-900'
        )}>
          {text ? (
            <div className="text-sm leading-relaxed prose-sm max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  table: ({ children }) => (
                    <div className="overflow-x-auto my-2">
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
                    <tr className={cn(isDark ? "even:bg-[#2a2a2a]" : "even:bg-gray-50/50")} {...props}>
                      {children}
                    </tr>
                  ),
                  a: ({ href, children }) => (
                    <a href={href} target="_blank" rel="noopener noreferrer"
                      className="text-indigo-400 hover:text-indigo-300 underline">
                      {children}
                    </a>
                  ),
                  p: ({ children }) => <p className="mb-1.5 last:mb-0">{children}</p>,
                  ul: ({ children }) => <ul className="list-disc pl-4 mb-1.5 space-y-0.5">{children}</ul>,
                  ol: ({ children }) => <ol className="list-decimal pl-4 mb-1.5 space-y-0.5">{children}</ol>,
                  li: ({ children }) => <li className="text-sm">{children}</li>,
                  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                }}
              >
                {text}
              </ReactMarkdown>
              {isStreaming && (
                <span className="inline-block w-2 h-4 ml-0.5 bg-indigo-400 animate-pulse rounded-sm" />
              )}
            </div>
          ) : (
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
