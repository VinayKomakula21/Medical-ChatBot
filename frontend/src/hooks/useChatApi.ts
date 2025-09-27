/**
 * Custom hook for chat API operations
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { api } from '@/services/apiClient';
import type { ChatMessage, ChatRequest, ChatResponse, StreamingChatResponse } from '@/types';
import { useApi } from './useApi';

interface UseChatApiOptions {
  conversationId?: string;
  onMessage?: (message: ChatMessage) => void;
  onStreamChunk?: (chunk: string) => void;
  enablePersistence?: boolean;
}

export function useChatApi(options: UseChatApiOptions = {}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>(options.conversationId);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const { execute: sendMessage, loading, error } = useApi<ChatResponse>({
    onSuccess: (response) => {
      setConversationId(response.conversation_id);

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.response,
        timestamp: new Date(),
        sources: response.sources,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      if (options.onMessage) {
        options.onMessage(assistantMessage);
      }

      // Persist to localStorage if enabled
      if (options.enablePersistence) {
        persistMessages([...messages, assistantMessage]);
      }
    },
  });

  const { execute: fetchHistory } = useApi<ChatMessage[]>();
  const { execute: clearHistoryApi } = useApi<{ status: string }>();

  // Load persisted messages on mount
  useEffect(() => {
    if (options.enablePersistence) {
      const saved = localStorage.getItem('chat_messages');
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          setMessages(parsed);
        } catch (e) {
          console.error('Failed to load chat history:', e);
        }
      }
    }
  }, [options.enablePersistence]);

  const persistMessages = useCallback((msgs: ChatMessage[]) => {
    if (options.enablePersistence) {
      localStorage.setItem('chat_messages', JSON.stringify(msgs));
    }
  }, [options.enablePersistence]);

  const send = useCallback(
    async (message: string, streamMode = false, temperature?: number, maxTokens?: number) => {
      // Add user message immediately
      const userMessage: ChatMessage = {
        role: 'user',
        content: message,
        timestamp: new Date(),
      };

      setMessages((prev) => {
        const updated = [...prev, userMessage];
        if (options.enablePersistence) {
          persistMessages(updated);
        }
        return updated;
      });

      if (streamMode && wsRef.current?.readyState === WebSocket.OPEN) {
        // Send via WebSocket for streaming
        const request: ChatRequest = {
          message,
          conversation_id: conversationId,
          stream: true,
          temperature,
          max_tokens: maxTokens,
        };

        wsRef.current.send(JSON.stringify(request));
      } else {
        // Send via regular API
        const request: ChatRequest = {
          message,
          conversation_id: conversationId,
          stream: false,
          temperature,
          max_tokens: maxTokens,
        };

        await sendMessage(api.post<ChatResponse>('/api/v1/chat/message', request));
      }
    },
    [conversationId, sendMessage, options.enablePersistence, persistMessages]
  );

  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const ws = api.ws('/api/v1/chat/ws');

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data: StreamingChatResponse = JSON.parse(event.data);

        if (options.onStreamChunk) {
          options.onStreamChunk(data.chunk);
        }

        if (data.is_final) {
          const assistantMessage: ChatMessage = {
            role: 'assistant',
            content: data.chunk,
            timestamp: new Date(),
            sources: data.sources,
          };

          setMessages((prev) => {
            const updated = [...prev, assistantMessage];
            if (options.enablePersistence) {
              persistMessages(updated);
            }
            return updated;
          });

          if (options.onMessage) {
            options.onMessage(assistantMessage);
          }
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsConnected(false);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);

      // Reconnect after 3 seconds
      setTimeout(() => {
        if (wsRef.current === ws) {
          connectWebSocket();
        }
      }, 3000);
    };

    wsRef.current = ws;
  }, [options, persistMessages]);

  const disconnectWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
      setIsConnected(false);
    }
  }, []);

  const loadHistory = useCallback(async () => {
    if (!conversationId) return;

    const result = await fetchHistory(
      api.get<ChatMessage[]>(`/api/v1/chat/history/${conversationId}`)
    );

    if (result.data) {
      setMessages(result.data);
      if (options.enablePersistence) {
        persistMessages(result.data);
      }
    }
  }, [conversationId, fetchHistory, options.enablePersistence, persistMessages]);

  const clearHistory = useCallback(async () => {
    if (conversationId) {
      await clearHistoryApi(
        api.delete(`/api/v1/chat/history/${conversationId}`)
      );
    }

    setMessages([]);
    setConversationId(undefined);

    if (options.enablePersistence) {
      localStorage.removeItem('chat_messages');
    }
  }, [conversationId, clearHistoryApi, options.enablePersistence]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return {
    messages,
    conversationId,
    loading,
    error,
    isConnected,
    send,
    loadHistory,
    clearHistory,
    connectWebSocket,
    disconnectWebSocket,
  };
}