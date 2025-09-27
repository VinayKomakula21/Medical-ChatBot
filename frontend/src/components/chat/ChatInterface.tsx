import { useRef, useEffect } from 'react';
import { MessageBubble } from './MessageBubble';
import { MessageInput } from './MessageInput';
import { ChatMessage } from '@/types';
import { MessageSquare } from 'lucide-react';

interface ChatInterfaceProps {
  messages: ChatMessage[];
  loading: boolean;
  onSendMessage: (message: string) => void;
}

export function ChatInterface({ messages, loading, onSendMessage }: ChatInterfaceProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
    // Also try direct container scroll as fallback
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight;
    }
  };

  useEffect(() => {
    // Scroll immediately and after a short delay to ensure content is rendered
    scrollToBottom();
    const timer = setTimeout(scrollToBottom, 100);
    return () => clearTimeout(timer);
  }, [messages, loading]);

  return (
    <div className="flex flex-col h-full">
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto p-4 scroll-smooth"
        style={{ scrollBehavior: 'smooth' }}
      >
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center min-h-[400px] text-center py-12">
            <MessageSquare className="h-12 w-12 text-muted-foreground mb-4" />
            <h2 className="text-2xl font-semibold mb-2">Welcome to Medical ChatBot</h2>
            <p className="text-muted-foreground max-w-md">
              Ask me any medical questions or upload documents for analysis.
              I'm here to help with medical information and guidance.
            </p>
          </div>
        ) : (
          <div className="space-y-4 max-w-4xl mx-auto pb-4">
            {messages.map((message, index) => (
              <MessageBubble
                key={index}
                message={message}
                isStreaming={loading && index === messages.length - 1 && message.role === 'assistant'}
              />
            ))}
            <div ref={messagesEndRef} className="h-1" />
          </div>
        )}
      </div>

      <MessageInput
        onSendMessage={onSendMessage}
        loading={loading}
      />
    </div>
  );
}