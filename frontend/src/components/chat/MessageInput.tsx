import { useState, useRef, useEffect } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Send, Loader2, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MessageInputProps {
  onSendMessage: (message: string) => void;
  loading: boolean;
  disabled?: boolean;
  wsConnected?: boolean;
  isWelcomeScreen?: boolean;
}

export function MessageInput({ onSendMessage, loading, disabled, wsConnected, isWelcomeScreen = false }: MessageInputProps) {
  const [message, setMessage] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const maxChars = 2000;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (message.trim() && !loading && !disabled) {
      onSendMessage(message.trim());
      setMessage('');
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
    }
  };

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px';
    }
  }, [message]);


  return (
    <div className={cn(isWelcomeScreen ? "p-0" : "p-3 sm:p-4")}>
      <form onSubmit={handleSubmit} className={cn(
        "bg-white dark:bg-slate-800 border",
        isWelcomeScreen
          ? "rounded-2xl p-4 border-gray-200 dark:border-slate-700 shadow-lg shadow-gray-200/50 dark:shadow-slate-900/50"
          : "rounded-2xl sm:rounded-3xl p-2 sm:p-3 shadow-lg border-gray-200 dark:border-slate-700"
      )}>
        {isWelcomeScreen ? (
          /* Large input layout for welcome screen */
          <div className="flex items-center gap-3">
            <Sparkles className="h-5 w-5 text-[#7C3AED] flex-shrink-0" />
            <input
              type="text"
              value={message}
              onChange={(e) => {
                if (e.target.value.length <= maxChars) {
                  setMessage(e.target.value);
                }
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e as any);
                }
              }}
              placeholder="Ask me anything about health, symptoms, medications..."
              className="flex-1 bg-transparent border-0 outline-none text-[15px] text-gray-900 dark:text-slate-100 placeholder:text-gray-400 dark:placeholder:text-slate-500"
              disabled={loading || disabled}
            />
            <Button
              type="submit"
              size="icon"
              disabled={!message.trim() || loading}
              className={cn(
                "h-10 w-10 rounded-xl transition-all flex-shrink-0",
                message.trim() && !loading
                  ? "bg-[#7C3AED] hover:bg-[#6D28D9] text-white shadow-sm hover:shadow-md"
                  : "bg-gray-100 dark:bg-slate-700 text-gray-400 dark:text-slate-500"
              )}
            >
              {loading ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Send className="h-5 w-5" />
              )}
            </Button>
          </div>
        ) : (
          /* Compact input layout for chat */
          <div className="flex items-center gap-3">
            <Sparkles className="h-5 w-5 text-[#7C3AED] flex-shrink-0" />
            <textarea
              ref={textareaRef}
              value={message}
              onChange={handleChange}
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              className={cn(
                "flex-1 resize-none bg-transparent border-0 outline-none text-sm py-2",
                "placeholder:text-gray-400 dark:placeholder:text-slate-500",
                "text-gray-900 dark:text-slate-100",
                "min-h-[40px] max-h-[150px]"
              )}
              disabled={loading || disabled}
              rows={1}
            />
            <Button
              type="submit"
              size="icon"
              disabled={!message.trim() || loading || disabled}
              className={cn(
                "h-9 w-9 sm:h-10 sm:w-10 rounded-full flex-shrink-0 transition-all",
                message.trim() && !loading
                  ? "bg-[#7C3AED] hover:bg-[#6D28D9] text-white"
                  : "bg-gray-200 dark:bg-slate-700 text-gray-400 dark:text-slate-500"
              )}
            >
              {loading ? (
                <Loader2 className="h-4 w-4 sm:h-5 sm:w-5 animate-spin" />
              ) : (
                <Send className="h-4 w-4 sm:h-5 sm:w-5" />
              )}
            </Button>
          </div>
        )}
      </form>

      {/* Connection status - minimal, only when disconnected */}
      {wsConnected !== undefined && !wsConnected && (
        <div className="flex items-center justify-center">
          <div className="flex items-center gap-1.5 sm:gap-2 text-[10px] sm:text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950 px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-full border border-red-200 dark:border-red-800">
            <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
            <span className="font-medium">Disconnected</span>
          </div>
        </div>
      )}
    </div>
  );
}