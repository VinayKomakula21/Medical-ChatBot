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
    <div className="flex flex-col h-full bg-gradient-to-br from-slate-100 via-purple-50 to-slate-100 dark:from-slate-950 dark:via-slate-900 dark:to-slate-950">
      {/* Connection Status Indicator - removed for cleaner look */}

      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto p-2 sm:p-4 scroll-smooth"
        style={{ scrollBehavior: 'smooth' }}
        onScroll={handleScroll}
      >
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-[400px] sm:min-h-[500px] text-center py-8 sm:py-16 space-y-6 sm:space-y-8 animate-fade-in px-4">
            <div className="relative">
              <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full gradient-purple-blue flex items-center justify-center shadow-lg">
                <Sparkles className="h-8 w-8 sm:h-10 sm:w-10 text-white" />
              </div>
            </div>
            <div className="space-y-2 sm:space-y-3">
              <h2 className="text-2xl sm:text-3xl font-bold text-slate-800 dark:text-slate-100">
                Medical ChatBot
              </h2>
              <p className="text-slate-600 dark:text-slate-400 max-w-md text-sm sm:text-base leading-relaxed px-4">
                Your AI-powered health assistant. Ask any medical question.
              </p>
            </div>

            {/* Quick Action Pills */}
            <div className="flex flex-wrap gap-2 sm:gap-3 justify-center max-w-full sm:max-w-2xl px-2">
              {quickActions.map((action, index) => (
                <Button
                  key={index}
                  variant="outline"
                  onClick={() => handleQuickAction(action.query)}
                  className="rounded-full px-3 py-3 sm:px-5 sm:py-5 text-xs sm:text-sm font-medium bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:border-purple-300 dark:hover:border-purple-600 hover:bg-purple-50 dark:hover:bg-slate-700 transition-all duration-200"
                >
                  <action.icon className="h-3 w-3 sm:h-4 sm:w-4 mr-1.5 sm:mr-2 text-purple-600 dark:text-purple-400" />
                  <span className="whitespace-nowrap dark:text-slate-200">{action.label}</span>
                </Button>
              ))}
            </div>

            {/* Tips */}
            <div className="flex flex-col items-center gap-3 text-xs sm:text-sm text-slate-500 dark:text-slate-400">
              <div className="flex items-center gap-2 px-3 py-1.5 sm:px-4 sm:py-2 bg-white dark:bg-slate-800 rounded-full border border-slate-200 dark:border-slate-700 shadow-sm">
                <span className="text-purple-600 dark:text-purple-400">💡</span>
                <span className="text-center dark:text-slate-300">Upload medical documents for personalized insights</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-3 sm:space-y-4 max-w-full px-2 sm:max-w-4xl sm:mx-auto pb-4">
            {/* Header for conversation - removed */}

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
              <div className="flex gap-2 sm:gap-3 items-start">
                <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-full gradient-purple-blue flex items-center justify-center flex-shrink-0 shadow-sm">
                  <Sparkles className="h-4 w-4 sm:h-5 sm:w-5 text-white" />
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 sm:w-2 sm:h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 sm:w-2 sm:h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 sm:w-2 sm:h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                  <span className="text-xs sm:text-sm text-slate-500 dark:text-slate-400">Analyzing data...</span>
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
          className="absolute bottom-20 right-4 sm:bottom-24 sm:right-6 h-10 w-10 sm:h-11 sm:w-11 rounded-full shadow-lg animate-in fade-in-0 slide-in-from-bottom-2 gradient-purple-blue hover:shadow-xl"
        >
          <ArrowDown className="h-4 w-4 animate-bounce text-white" />
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