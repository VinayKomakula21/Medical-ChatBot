import { useState, useCallback, useRef, useEffect } from 'react';
import { ChatMessage, ChatRequest, StreamingChatResponse } from '@/types';
import { apiService } from '@/services/api';
import { wsService } from '@/services/websocket';

export const useChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const currentStreamingMessage = useRef<string>('');

  useEffect(() => {
    const handleConnection = (connected: boolean) => {
      setWsConnected(connected);
    };

    wsService.onConnectionChange(handleConnection);

    return () => {
      wsService.offConnectionChange(handleConnection);
    };
  }, []);

  const sendMessage = useCallback(async (content: string, streamMode: boolean, temperature: number, maxTokens: number) => {
    const userMessage: ChatMessage = {
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setLoading(true);

    try {
      const request: ChatRequest = {
        message: content,
        conversation_id: conversationId || undefined,
        stream: streamMode,
        temperature,
        max_tokens: maxTokens,
      };

      if (streamMode) {
        await wsService.connect();

        currentStreamingMessage.current = '';
        const assistantMessage: ChatMessage = {
          role: 'assistant',
          content: '',
          timestamp: new Date(),
        };

        setMessages(prev => [...prev, assistantMessage]);
        const messageIndex = messages.length + 1;

        const handleStreamingResponse = (data: StreamingChatResponse) => {
          if (data.chunk) {
            currentStreamingMessage.current += data.chunk;
            setMessages(prev => {
              const newMessages = [...prev];
              if (newMessages[messageIndex]) {
                newMessages[messageIndex] = {
                  ...newMessages[messageIndex],
                  content: currentStreamingMessage.current,
                };
              }
              return newMessages;
            });
          }

          if (data.is_final) {
            if (data.sources && data.sources.length > 0) {
              setMessages(prev => {
                const newMessages = [...prev];
                if (newMessages[messageIndex]) {
                  newMessages[messageIndex] = {
                    ...newMessages[messageIndex],
                    sources: data.sources,
                  };
                }
                return newMessages;
              });
            }
            wsService.offMessage('chat');
            setLoading(false);
          }

          if (data.conversation_id) {
            setConversationId(data.conversation_id);
          }
        };

        wsService.onMessage('chat', handleStreamingResponse);
        await wsService.sendMessage(request);
      } else {
        const response = await apiService.sendMessage(request);

        const assistantMessage: ChatMessage = {
          role: 'assistant',
          content: response.response,
          timestamp: new Date(),
          sources: response.sources,
        };

        setMessages(prev => [...prev, assistantMessage]);
        setConversationId(response.conversation_id);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: 'Sorry, an error occurred. Please try again.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      if (!streamMode) {
        setLoading(false);
      }
    }
  }, [conversationId, messages.length]);

  const clearConversation = useCallback(async () => {
    if (conversationId) {
      try {
        await apiService.clearConversation(conversationId);
      } catch (error) {
        console.error('Failed to clear conversation:', error);
      }
    }
    setMessages([]);
    setConversationId(null);
  }, [conversationId]);

  return {
    messages,
    loading,
    wsConnected,
    sendMessage,
    clearConversation,
    conversationId,
  };
};