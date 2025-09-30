import { useRef, useEffect, useState } from 'react';
import { MessageBubble } from './MessageBubble';
import { MessageInput } from './MessageInput';
import type { ChatMessage } from '@/types';
import { Sparkles, Heart, Stethoscope, Activity, ArrowDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface ChatInterfaceProps {
  messages: ChatMessage[];
  loading: boolean;
  onSendMessage: (message: string) => void;
  wsConnected?: boolean;
}

export function ChatInterface({ messages, loading, onSendMessage, wsConnected }: ChatInterfaceProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [userScrolledUp, setUserScrolledUp] = useState(false);

  const scrollToBottom = (smooth = true) => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({
        behavior: smooth ? 'smooth' : 'instant',
        block: 'end'
      });
    }
    // Also try direct container scroll as fallback
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
    setUserScrolledUp(false);
  };

  const handleScroll = () => {
    if (scrollContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollContainerRef.current;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
      setShowScrollButton(!isNearBottom);
      setUserScrolledUp(!isNearBottom);
    }
  };

  useEffect(() => {
    // Only auto-scroll if user hasn't manually scrolled up
    if (!userScrolledUp) {
      scrollToBottom();
      const timer = setTimeout(() => scrollToBottom(), 100);
      return () => clearTimeout(timer);
    }
  }, [messages, loading, userScrolledUp]);

  const quickActions = [
    { icon: Heart, label: "Common symptoms", query: "What are common symptoms of flu?" },
    { icon: Stethoscope, label: "First aid", query: "Basic first aid for minor cuts" },
    { icon: Activity, label: "Health tips", query: "Daily health tips for better lifestyle" }
  ];

  const handleQuickAction = (query: string) => {
    onSendMessage(query);
  };

  return (
    <div className="flex flex-col h-full bg-gradient-to-br from-background to-muted/10">
      {/* Connection Status Indicator */}
      {wsConnected !== undefined && (
        <div className={cn(
          "h-1 transition-all duration-500",
          wsConnected ? "bg-gradient-to-r from-green-500/50 to-emerald-500/50" : "bg-gradient-to-r from-red-500/50 to-orange-500/50"
        )} />
      )}

      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto p-4 scroll-smooth"
        style={{ scrollBehavior: 'smooth' }}
        onScroll={handleScroll}
      >
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-[400px] text-center py-12 space-y-6">
            <div className="relative">
              <div className="absolute inset-0 animate-pulse bg-primary/20 rounded-full blur-3xl" />
              <Sparkles className="h-16 w-16 text-primary relative animate-pulse" />
            </div>
            <div className="space-y-2">
              <h2 className="text-3xl font-bold bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
                Medical ChatBot
              </h2>
              <p className="text-muted-foreground max-w-md text-sm">
                Your AI-powered health assistant. Ask medical questions or upload documents for analysis.
              </p>
            </div>

            {/* Quick Action Buttons */}
            <div className="flex flex-wrap gap-2 justify-center max-w-lg">
              {quickActions.map((action, index) => (
                <Button
                  key={index}
                  variant="outline"
                  size="sm"
                  onClick={() => handleQuickAction(action.query)}
                  className="group hover:scale-105 transition-all duration-200"
                >
                  <action.icon className="h-4 w-4 mr-2 group-hover:text-primary transition-colors" />
                  {action.label}
                </Button>
              ))}
            </div>

            {/* Tips */}
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="secondary" className="animate-in fade-in-0 slide-in-from-bottom-2">
                💡 Tip: Upload medical documents for better context
              </Badge>
            </div>
          </div>
        ) : (
          <div className="space-y-4 max-w-4xl mx-auto pb-4">
            {/* Header for conversation */}
            <div className="text-center py-2 sticky top-0 bg-background/80 backdrop-blur-sm z-10 border-b">
              <p className="text-xs text-muted-foreground flex items-center justify-center gap-2">
                <Activity className="h-3 w-3" />
                Medical Information Assistant
                {wsConnected && <span className="text-green-500">• Connected</span>}
              </p>
            </div>

            {messages.map((message, index) => (
              <div
                key={index}
                className={cn(
                  "animate-in fade-in-0 slide-in-from-bottom-2 duration-300",
                  index === 0 && "mt-4"
                )}
              >
                <MessageBubble
                  message={message}
                  isStreaming={loading && index === messages.length - 1 && message.role === 'assistant'}
                />
              </div>
            ))}

            {/* Typing Indicator */}
            {loading && messages[messages.length - 1]?.role === 'user' && (
              <div className="flex gap-3">
                <div className="h-8 w-8" />
                <div className="flex items-center gap-2 px-4 py-2 bg-muted rounded-lg">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                  <span className="text-xs text-muted-foreground">Medical Bot is typing...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} className="h-1" />
          </div>
        )}
      </div>

      {/* Scroll to Bottom Button */}
      {showScrollButton && (
        <Button
          onClick={() => scrollToBottom()}
          size="icon"
          className="absolute bottom-24 right-6 rounded-full shadow-lg animate-in fade-in-0 slide-in-from-bottom-2"
          variant="secondary"
        >
          <ArrowDown className="h-4 w-4 animate-bounce" />
        </Button>
      )}

      <div className="border-t bg-background/95 backdrop-blur">
        <MessageInput
          onSendMessage={onSendMessage}
          loading={loading}
        />
      </div>
    </div>
  );
}