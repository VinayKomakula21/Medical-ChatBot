export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  sources?: DocumentSource[];
}

export interface DocumentSource {
  document?: string;
  filename?: string;
  page?: number;
  score?: number;
  relevance_score?: number;
  metadata?: Record<string, any>;
}

export interface ChatRequest {
  message: string;
  conversation_id?: string;
  stream?: boolean;
  temperature?: number;
  max_tokens?: number;
}

export interface ChatResponse {
  response: string;
  conversation_id: string;
  sources: DocumentSource[];
  tokens_used?: number;
  processing_time?: number;
}

export interface StreamingChatResponse {
  chunk: string;
  conversation_id: string;
  is_final: boolean;
  sources?: DocumentSource[];
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  chunks_created: number;
  processing_time?: number;
}

export interface Settings {
  temperature: number;
  maxTokens: number;
  streamMode: boolean;
  theme: 'light' | 'dark' | 'system';
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}