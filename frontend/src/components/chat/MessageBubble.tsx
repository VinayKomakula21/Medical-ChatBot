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
      "flex gap-3 group",
      isUser ? 'flex-row-reverse' : ''
    )}>
      <Avatar className={cn(
        "h-10 w-10 shrink-0 border-2 transition-all duration-300",
        isUser ? 'border-primary/20' : 'border-secondary',
        "group-hover:scale-105"
      )}>
        <AvatarFallback className={cn(
          isUser ? 'bg-gradient-to-br from-primary to-primary/80' : 'bg-gradient-to-br from-blue-500 to-cyan-500',
          "text-white"
        )}>
          {isUser ? <User className="h-5 w-5" /> : <Sparkles className="h-5 w-5" />}
        </AvatarFallback>
      </Avatar>

      <div className={cn(
        "flex flex-col gap-2 max-w-[75%]",
        isUser ? 'items-end' : 'items-start'
      )}>
        <div className="flex items-center gap-2 px-1">
          <span className="text-xs font-medium text-muted-foreground">
            {isUser ? 'You' : '🏥 Medical Assistant'}
          </span>
          <Clock className="h-3 w-3 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">
            {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
          {isUser && (
            <CheckCheck className="h-3 w-3 text-muted-foreground" />
          )}
          {isUrgent && !isUser && (
            <AlertCircle className="h-3 w-3 text-orange-500 animate-pulse" />
          )}
        </div>

        <Card className={cn(
          "relative transition-shadow duration-200",
          isUser
            ? 'bg-gradient-to-br from-primary to-primary/90 text-primary-foreground border-primary/20'
            : 'bg-card hover:shadow-lg border border-border'
        )}>
          {/* Decorative gradient overlay */}
          {!isUser && (
            <div className="absolute top-0 left-0 w-full h-0.5 bg-gradient-to-r from-blue-500/30 via-cyan-500/30 to-blue-500/30" />
          )}

          <div className="px-4 py-3">
            {isUser ? (
              <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
            ) : (
              <div className="space-y-3 text-foreground">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={{
                    // Paragraphs with proper spacing
                    p: ({children}) => (
                      <p className="text-sm leading-relaxed mb-3 last:mb-0">{children}</p>
                    ),
                    // Lists with better formatting
                    ul: ({children}) => (
                      <ul className="list-disc list-inside space-y-2 my-3 ml-2">{children}</ul>
                    ),
                    ol: ({children}) => (
                      <ol className="list-decimal list-inside space-y-2 my-3 ml-2">{children}</ol>
                    ),
                    li: ({children}) => (
                      <li className="text-sm leading-relaxed">
                        <span className="ml-2">{children}</span>
                      </li>
                    ),
                    // Strong text (bold)
                    strong: ({children}) => (
                      <strong className="font-semibold text-foreground">{children}</strong>
                    ),
                    // Emphasized text
                    em: ({children}) => (
                      <em className="italic text-muted-foreground">{children}</em>
                    ),
                    // Code blocks
                    code: ({children, ...props}: any) => {
                      const inline = !props.className;
                      return inline ? (
                        <code className="bg-muted px-1.5 py-0.5 rounded text-xs font-mono">{children}</code>
                      ) : (
                        <pre className="bg-muted p-3 rounded-lg overflow-x-auto">
                          <code className="text-xs font-mono">{children}</code>
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
                  <span className="inline-block w-2 h-4 ml-1 bg-primary/60 animate-pulse rounded" />
                )}
              </div>
            )}
          </div>
        </Card>

        {message.sources && message.sources.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {message.sources.map((source, index) => (
              <Badge key={index} variant="secondary" className="text-xs">
                <FileText className="h-3 w-3 mr-1" />
                {source.filename || source.document || `Source ${index + 1}`}
                {source.score && (
                  <span className="ml-1 opacity-70">
                    ({(source.score * 100).toFixed(0)}%)
                  </span>
                )}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}