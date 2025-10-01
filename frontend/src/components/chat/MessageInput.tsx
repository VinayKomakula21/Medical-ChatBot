import { useState, useRef, useEffect } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Send, Loader2, Mic, Paperclip, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MessageInputProps {
  onSendMessage: (message: string) => void;
  loading: boolean;
  disabled?: boolean;
  wsConnected?: boolean;
}

export function MessageInput({ onSendMessage, loading, disabled, wsConnected }: MessageInputProps) {
  const [message, setMessage] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [charCount, setCharCount] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const maxChars = 2000;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (message.trim() && !loading && !disabled) {
      onSendMessage(message.trim());
      setMessage('');
      setCharCount(0);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newMessage = e.target.value;
    if (newMessage.length <= maxChars) {
      setMessage(newMessage);
      setCharCount(newMessage.length);
      setIsTyping(newMessage.length > 0);
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  }, [message]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsTyping(false);
    }, 1000);
    return () => clearTimeout(timer);
  }, [message]);

  // Suggested prompts for quick access
  const suggestedPrompts = [
    "Symptoms of flu",
    "Headache remedies",
    "First aid tips"
  ];

  const handleSuggestedPrompt = (prompt: string) => {
    setMessage(prompt);
    setCharCount(prompt.length);
    textareaRef.current?.focus();
  };

  return (
    <div className="p-4 space-y-2">
      {/* Suggested prompts - show when input is empty */}
      {message.length === 0 && !loading && (
        <div className="flex gap-2 flex-wrap items-center">
          {suggestedPrompts.map((prompt, index) => (
            <button
              key={index}
              className="px-3 py-1.5 text-xs font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-full transition-colors border border-slate-200"
              onClick={() => handleSuggestedPrompt(prompt)}
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="bg-white rounded-3xl shadow-md border border-slate-200 p-3">
        <div className="relative flex gap-3 items-end">
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="h-10 w-10 rounded-full hover:bg-slate-100 flex-shrink-0"
            disabled={loading}
            title="Attach file (coming soon)"
          >
            <Paperclip className="h-5 w-5 text-slate-500" />
          </Button>

          <Textarea
            ref={textareaRef}
            value={message}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask, write or search for anything..."
            className={cn(
              "min-h-[40px] max-h-[200px] resize-none border-0 transition-all bg-transparent focus:ring-0 focus:outline-none px-0 text-sm",
              "placeholder:text-slate-400",
              charCount > maxChars * 0.9 && "text-orange-600"
            )}
            disabled={loading || disabled}
            rows={1}
          />

          <Button
            type="submit"
            size="icon"
            disabled={!message.trim() || loading || disabled}
            className={cn(
              "h-10 w-10 rounded-full flex-shrink-0 transition-all",
              message.trim() && !loading
                ? "bg-slate-900 hover:bg-slate-800 text-white"
                : "bg-slate-200 text-slate-400"
            )}
          >
            {loading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </Button>
        </div>
      </form>

      {/* Connection status - minimal */}
      {wsConnected !== undefined && !wsConnected && (
        <div className="flex items-center justify-center">
          <div className="flex items-center gap-2 text-xs text-red-600 bg-red-50 px-3 py-1.5 rounded-full border border-red-200">
            <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
            <span className="font-medium">Disconnected</span>
          </div>
        </div>
      )}
    </div>
  );
}