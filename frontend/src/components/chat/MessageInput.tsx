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
        <div className="flex gap-2 flex-wrap">
          <span className="text-xs text-muted-foreground">Try asking:</span>
          {suggestedPrompts.map((prompt, index) => (
            <Badge
              key={index}
              variant="outline"
              className="cursor-pointer hover:bg-primary/10 transition-colors text-xs"
              onClick={() => handleSuggestedPrompt(prompt)}
            >
              <Sparkles className="h-3 w-3 mr-1" />
              {prompt}
            </Badge>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <Textarea
            ref={textareaRef}
            value={message}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="Ask your medical question... (Shift+Enter for new line)"
            className={cn(
              "min-h-[56px] max-h-[200px] resize-none pr-12 transition-all",
              "focus:ring-2 focus:ring-primary/20",
              isTyping && "border-primary/50",
              charCount > maxChars * 0.9 && "border-orange-500/50"
            )}
            disabled={loading || disabled}
            rows={1}
          />

          {/* Character counter */}
          <div className="absolute bottom-2 right-2 flex items-center gap-2">
            {message.length > 0 && (
              <span className={cn(
                "text-xs",
                charCount > maxChars * 0.9 ? "text-orange-500" : "text-muted-foreground"
              )}>
                {charCount}/{maxChars}
              </span>
            )}
          </div>

          {/* Typing indicator in input */}
          {isTyping && (
            <div className="absolute -top-6 left-0">
              <Badge variant="secondary" className="text-xs animate-in fade-in-0 slide-in-from-bottom-1">
                <Sparkles className="h-3 w-3 mr-1 animate-pulse" />
                Composing...
              </Badge>
            </div>
          )}
        </div>

        {/* Additional action buttons */}
        <div className="flex gap-1">
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="h-[56px] w-[56px]"
            disabled={loading}
            title="Attach file (coming soon)"
          >
            <Paperclip className="h-4 w-4 text-muted-foreground" />
          </Button>

          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="h-[56px] w-[56px]"
            disabled={loading}
            title="Voice input (coming soon)"
          >
            <Mic className="h-4 w-4 text-muted-foreground" />
          </Button>

          <Button
            type="submit"
            size="icon"
            disabled={!message.trim() || loading || disabled}
            className={cn(
              "h-[56px] w-[56px] transition-all",
              message.trim() && !loading && "bg-primary hover:bg-primary/90 scale-105"
            )}
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className={cn(
                "h-4 w-4 transition-transform",
                message.trim() && "rotate-[-15deg]"
              )} />
            )}
          </Button>
        </div>
      </form>

      {/* Connection status */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {wsConnected !== undefined && (
            <>
              <div className={cn(
                "w-2 h-2 rounded-full",
                wsConnected ? "bg-green-500 animate-pulse" : "bg-red-500"
              )} />
              <span>{wsConnected ? "Connected" : "Disconnected"}</span>
            </>
          )}
        </div>
        <span className="text-xs text-muted-foreground">
          Press Enter to send • Shift+Enter for new line
        </span>
      </div>
    </div>
  );
}