import type { ChatMessage } from '@/types';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Card } from '@/components/ui/card';
import { User, FileText, Clock, CheckCheck, Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';

interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

export function MessageBubble({ message, isStreaming }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={cn(
      "flex gap-2 sm:gap-3 items-start",
      isUser ? 'flex-row-reverse' : ''
    )}>
      {!isUser && (
        <Avatar className="h-8 w-8 sm:h-10 sm:w-10 shrink-0 gradient-purple-blue shadow-sm">
          <AvatarFallback className="text-white bg-transparent">
            <Sparkles className="h-4 w-4 sm:h-5 sm:w-5" />
          </AvatarFallback>
        </Avatar>
      )}
      {isUser && (
        <Avatar className="h-8 w-8 sm:h-10 sm:w-10 shrink-0 gradient-purple-blue shadow-sm">
          <AvatarFallback className="text-white bg-transparent">
            <User className="h-4 w-4 sm:h-5 sm:w-5" />
          </AvatarFallback>
        </Avatar>
      )}

      <div className={cn(
        "flex flex-col gap-1 max-w-[85%] sm:max-w-[75%] md:max-w-[70%]",
        isUser ? 'items-end' : 'items-start'
      )}>
        <Card className={cn(
          "relative transition-all duration-200 shadow-sm",
          isUser
            ? 'gradient-purple-blue text-white rounded-2xl sm:rounded-3xl px-3 py-2 sm:px-4 sm:py-3 border-0'
            : 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl sm:rounded-2xl px-3 py-2.5 sm:px-5 sm:py-4 hover:shadow-md'
        )}>
          {/* Chat bubble tail removed for cleaner look like reference */}

          {isUser ? (
            <p className="text-xs sm:text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
          ) : (
            <div className="space-y-1.5 sm:space-y-2 text-slate-700 dark:text-slate-300">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    // Paragraphs with proper spacing
                    p: ({children}) => (
                      <p className="text-xs sm:text-sm leading-relaxed mb-1.5 sm:mb-2 last:mb-0 text-slate-700 dark:text-slate-300">{children}</p>
                    ),
                    // Lists with better formatting
                    ul: ({children}) => (
                      <ul className="list-disc list-inside space-y-1 sm:space-y-1.5 my-1.5 sm:my-2 ml-0.5 sm:ml-1">{children}</ul>
                    ),
                    ol: ({children}) => (
                      <ol className="list-decimal list-inside space-y-1 sm:space-y-1.5 my-1.5 sm:my-2 ml-0.5 sm:ml-1">{children}</ol>
                    ),
                    li: ({children}) => (
                      <li className="text-xs sm:text-sm leading-relaxed text-slate-700 dark:text-slate-300">
                        <span className="ml-0.5 sm:ml-1">{children}</span>
                      </li>
                    ),
                    // Strong text (bold)
                    strong: ({children}) => (
                      <strong className="font-semibold text-slate-900 dark:text-slate-100 text-xs sm:text-sm">{children}</strong>
                    ),
                    // Emphasized text
                    em: ({children}) => (
                      <em className="italic text-slate-600 dark:text-slate-400">{children}</em>
                    ),
                    // Code blocks
                    code: ({children, ...props}: any) => {
                      const inline = !props.className;
                      return inline ? (
                        <code className="bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 rounded text-xs font-mono text-slate-800 dark:text-slate-200">{children}</code>
                      ) : (
                        <pre className="bg-slate-100 dark:bg-slate-700 p-3 rounded-lg overflow-x-auto my-2">
                          <code className="text-xs font-mono text-slate-800 dark:text-slate-200">{children}</code>
                        </pre>
                      );
                    },
                    // Headings
                    h1: ({children}) => (
                      <h1 className="text-lg font-bold mt-4 mb-2">{children}</h1>
                    ),
                    h2: ({children}) => (
                      <h2 className="text-base font-semibold mt-3 mb-2">{children}</h2>
                    ),
                    h3: ({children}) => (
                      <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>
                    ),
                    // Blockquotes
                    blockquote: ({children}) => (
                      <blockquote className="border-l-4 border-primary/30 pl-4 my-3 italic">
                        {children}
                      </blockquote>
                    ),
                    // Horizontal rules
                    hr: () => <hr className="my-4 border-border" />,
                    // Links
                    a: ({children, href}) => (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary hover:underline"
                      >
                        {children}
                      </a>
                    ),
                  }}
                >
                  {message.content}
                </ReactMarkdown>
                {isStreaming && message.content && (
                  <span className="inline-block w-1.5 h-4 ml-1 bg-slate-400 animate-pulse rounded" />
                )}
              </div>
            )}
        </Card>

        {/* Timestamp below message */}
        <div className={cn(
          "flex items-center gap-1 sm:gap-1.5 px-1 sm:px-2 text-[10px] sm:text-xs text-slate-500 dark:text-slate-400",
          isUser ? 'justify-end' : 'justify-start'
        )}>
          <Clock className="h-2.5 w-2.5 sm:h-3 sm:w-3" />
          <span>{message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
          {isUser && <CheckCheck className="h-2.5 w-2.5 sm:h-3 sm:w-3" />}
        </div>

        {message.sources && message.sources.length > 0 && (
          <div className={cn("flex flex-wrap gap-1.5 sm:gap-2 mt-1", isUser ? 'justify-end' : 'justify-start')}>
            {message.sources.map((source, index) => (
              <div key={index} className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg px-2 py-1.5 sm:px-3 sm:py-2 shadow-sm flex items-center gap-1.5 sm:gap-2 text-[10px] sm:text-xs">
                <FileText className="h-2.5 w-2.5 sm:h-3 sm:w-3 text-slate-500 dark:text-slate-400 flex-shrink-0" />
                <span className="text-slate-700 dark:text-slate-300 font-medium truncate max-w-[120px] sm:max-w-none">{source.filename || source.document || `Source ${index + 1}`}</span>
                {source.score && (
                  <span className="text-slate-500 dark:text-slate-400 flex-shrink-0">
                    {(source.score * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}