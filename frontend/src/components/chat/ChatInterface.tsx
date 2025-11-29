import { useRef, useEffect, useState } from 'react';
import { MessageBubble } from './MessageBubble';
import { MessageInput } from './MessageInput';
import type { ChatMessage } from '@/types';
import { Sparkles, ArrowDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { TypingAnimation } from '@/components/ui/typing-animation';
import { BlurFade } from '@/components/ui/blur-fade';
import { cn } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';

interface ChatInterfaceProps {
  messages: ChatMessage[];
  loading: boolean;
  onSendMessage: (message: string) => void;
  wsConnected?: boolean;
}

export function ChatInterface({ messages, loading, onSendMessage }: ChatInterfaceProps) {
  const { user } = useAuth();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [userScrolledUp, setUserScrolledUp] = useState(false);

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good Morning';
    if (hour < 17) return 'Good Afternoon';
    return 'Good Evening';
  };

  const getFirstName = () => {
    if (user?.name) {
      return user.name.split(' ')[0];
    }
    return 'there';
  };

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

  return (
    <div className="flex flex-col h-full bg-white dark:bg-slate-950">
      {/* Connection Status Indicator - removed for cleaner look */}

      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto p-2 sm:p-4 scroll-smooth"
        style={{ scrollBehavior: 'smooth' }}
        onScroll={handleScroll}
      >
        {messages.length === 0 ? (
          <div className="relative flex flex-col items-center justify-center h-full text-center py-8 sm:py-12 space-y-8 animate-fade-in px-4 overflow-hidden">
            {/* Subtle gradient background */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
              <div className="absolute top-[15%] left-1/2 -translate-x-1/2 w-[600px] h-[500px] bg-gradient-to-b from-violet-200/50 via-purple-100/40 to-transparent dark:from-violet-900/30 dark:via-purple-900/20 blur-3xl" />
              <div className="absolute top-[10%] left-[40%] w-[400px] h-[400px] bg-gradient-to-br from-blue-100/40 to-transparent dark:from-blue-900/20 blur-3xl" />
            </div>

            {/* Personalized Greeting */}
            <div className="space-y-3 relative z-10">
              <BlurFade delay={0.1} inView>
                <h1 className="text-3xl sm:text-4xl lg:text-5xl font-semibold text-gray-900 dark:text-slate-100">
                  <TypingAnimation
                    text={`${getGreeting()}, ${getFirstName()}`}
                    duration={50}
                    className="text-gray-900 dark:text-slate-100"
                  />
                </h1>
              </BlurFade>
              <BlurFade delay={0.3} inView>
                <p className="text-lg sm:text-xl text-gray-500 dark:text-slate-400">
                  How Can I <span className="bg-gradient-to-r from-[#7C3AED] to-[#3B82F6] bg-clip-text text-transparent font-semibold">Assist You Today?</span>
                </p>
              </BlurFade>
            </div>

            {/* Message Input */}
            <BlurFade delay={0.5} inView>
              <div className="w-full max-w-4xl relative z-10 px-4">
                <MessageInput
                  onSendMessage={onSendMessage}
                  loading={loading}
                  isWelcomeScreen={true}
                />
              </div>
            </BlurFade>

            {/* Suggested Prompts */}
            <BlurFade delay={0.7} inView>
              <div className="relative z-10 w-full max-w-4xl px-4">
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { icon: '🩺', title: 'Common Symptoms', desc: 'Check symptoms and get advice' },
                    { icon: '💊', title: 'Medication Info', desc: 'Learn about medications' },
                    { icon: '🏥', title: 'First Aid Tips', desc: 'Emergency care guidance' },
                    { icon: '🥗', title: 'Health & Wellness', desc: 'Nutrition and lifestyle tips' },
                  ].map((item, i) => (
                    <button
                      key={i}
                      onClick={() => onSendMessage(item.title)}
                      className="flex items-start gap-3 p-4 bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm rounded-xl border border-gray-200/60 dark:border-slate-700/60 hover:border-[#7C3AED]/50 hover:shadow-md transition-all text-left group"
                    >
                      <span className="text-2xl">{item.icon}</span>
                      <div>
                        <p className="font-medium text-gray-900 dark:text-slate-100 group-hover:text-[#7C3AED] transition-colors">{item.title}</p>
                        <p className="text-sm text-gray-500 dark:text-slate-400">{item.desc}</p>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </BlurFade>
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

            {/* Typing Indicator - Enhanced */}
            {loading && messages[messages.length - 1]?.role === 'user' && (
              <BlurFade delay={0} inView>
                <div className="flex gap-2 sm:gap-3 items-start">
                  <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-full gradient-purple-blue flex items-center justify-center flex-shrink-0 shadow-md animate-pulse">
                    <Sparkles className="h-4 w-4 sm:h-5 sm:w-5 text-white" />
                  </div>
                  <div className="bg-white dark:bg-slate-800 rounded-2xl px-4 py-3 shadow-sm border border-slate-200 dark:border-slate-700">
                    <div className="flex items-center gap-3">
                      <div className="flex gap-1.5">
                        <span className="w-2 h-2 bg-[#7C3AED] rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-2 h-2 bg-[#8B5CF6] rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-2 h-2 bg-[#3B82F6] rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                      <span className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 font-medium">
                        <TypingAnimation text="Analyzing your query..." duration={40} className="text-slate-500 dark:text-slate-400" />
                      </span>
                    </div>
                  </div>
                </div>
              </BlurFade>
            )}

            <div ref={messagesEndRef} className="h-1" />
          </div>
        )}
      </div>

      {/* Scroll to Bottom Button - only show when there are messages and user scrolled up */}
      {showScrollButton && messages.length > 0 && (
        <Button
          onClick={() => scrollToBottom()}
          size="icon"
          className="absolute bottom-20 right-4 sm:bottom-24 sm:right-6 h-10 w-10 sm:h-11 sm:w-11 rounded-full shadow-lg animate-in fade-in-0 slide-in-from-bottom-2 gradient-purple-blue hover:shadow-xl"
        >
          <ArrowDown className="h-4 w-4 animate-bounce text-white" />
        </Button>
      )}

      {/* Only show bottom input when there are messages */}
      {messages.length > 0 && (
        <div className="border-t bg-background/95 backdrop-blur">
          <MessageInput
            onSendMessage={onSendMessage}
            loading={loading}
          />
        </div>
      )}
    </div>
  );
}