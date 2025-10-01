import type { ChatMessage } from '@/types';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { User, FileText, Clock, CheckCheck, AlertCircle, Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '@/lib/utils';

interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

export function MessageBubble({ message, isStreaming }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isUrgent = message.content.toLowerCase().includes('urgent') ||
                   message.content.toLowerCase().includes('emergency') ||
                   message.content.toLowerCase().includes('pain');

  return (
    <div className={cn(
      "flex gap-3 items-start",
      isUser ? 'flex-row-reverse' : ''
    )}>
      {!isUser && (
        <Avatar className="h-10 w-10 shrink-0 gradient-purple-blue shadow-sm">
          <AvatarFallback className="text-white bg-transparent">
            <Sparkles className="h-5 w-5" />
          </AvatarFallback>
        </Avatar>
      )}
      {isUser && (
        <Avatar className="h-10 w-10 shrink-0 gradient-purple-blue shadow-sm">
          <AvatarFallback className="text-white bg-transparent">
            <User className="h-5 w-5" />
          </AvatarFallback>
        </Avatar>
      )}

      <div className={cn(
        "flex flex-col gap-1 max-w-[70%]",
        isUser ? 'items-end' : 'items-start'
      )}>
        <Card className={cn(
          "relative transition-all duration-200 shadow-sm",
          isUser
            ? 'gradient-purple-blue text-white rounded-3xl px-4 py-3 border-0'
            : 'bg-white border border-slate-200 rounded-2xl px-5 py-4 hover:shadow-md'
        )}>
          {/* Chat bubble tail removed for cleaner look like reference */}

          {isUser ? (
            <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
          ) : (
            <div className="space-y-2 text-slate-700">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    // Paragraphs with proper spacing
                    p: ({children}) => (
                      <p className="text-sm leading-relaxed mb-2 last:mb-0 text-slate-700">{children}</p>
                    ),
                    // Lists with better formatting
                    ul: ({children}) => (
                      <ul className="list-disc list-inside space-y-1.5 my-2 ml-1">{children}</ul>
                    ),
                    ol: ({children}) => (
                      <ol className="list-decimal list-inside space-y-1.5 my-2 ml-1">{children}</ol>
                    ),
                    li: ({children}) => (
                      <li className="text-sm leading-relaxed text-slate-700">
                        <span className="ml-1">{children}</span>
                      </li>
                    ),
                    // Strong text (bold)
                    strong: ({children}) => (
                      <strong className="font-semibold text-slate-900">{children}</strong>
                    ),
                    // Emphasized text
                    em: ({children}) => (
                      <em className="italic text-slate-600">{children}</em>
                    ),
                    // Code blocks
                    code: ({children, ...props}: any) => {
                      const inline = !props.className;
                      return inline ? (
                        <code className="bg-slate-100 px-1.5 py-0.5 rounded text-xs font-mono text-slate-800">{children}</code>
                      ) : (
                        <pre className="bg-slate-100 p-3 rounded-lg overflow-x-auto my-2">
                          <code className="text-xs font-mono text-slate-800">{children}</code>
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
          "flex items-center gap-1.5 px-2 text-xs text-slate-500",
          isUser ? 'justify-end' : 'justify-start'
        )}>
          <Clock className="h-3 w-3" />
          <span>{message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
          {isUser && <CheckCheck className="h-3 w-3" />}
        </div>

        {message.sources && message.sources.length > 0 && (
          <div className={cn("flex flex-wrap gap-2 mt-1", isUser ? 'justify-end' : 'justify-start')}>
            {message.sources.map((source, index) => (
              <div key={index} className="bg-white border border-slate-200 rounded-lg px-3 py-2 shadow-sm flex items-center gap-2 text-xs">
                <FileText className="h-3 w-3 text-slate-500" />
                <span className="text-slate-700 font-medium">{source.filename || source.document || `Source ${index + 1}`}</span>
                {source.score && (
                  <span className="text-slate-500">
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