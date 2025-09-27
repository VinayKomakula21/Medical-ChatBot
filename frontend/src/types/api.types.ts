/**
 * API-related type definitions
 */

export interface ApiError {
  error: string;
  detail?: string;
  request_id?: string;
  status_code: number;
}

export interface ApiResponse<T> {
  data?: T;
  error?: ApiError;
  loading?: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface HealthCheckResponse {
  status: 'healthy' | 'unhealthy';
  timestamp: number;
  version?: string;
}

export interface DocumentListResponse {
  documents: DocumentMetadata[];
  total: number;
  page: number;
  page_size: number;
}

export interface DocumentMetadata {
  id: string;
  filename: string;
  file_path?: string;
  content_type: string;
  size: number;
  chunks_count: number;
  tags: string[];
  metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
  indexed: boolean;
  index_status: 'pending' | 'completed' | 'failed';
}

export interface DocumentSearchRequest {
  query: string;
  top_k?: number;
  filter_tags?: string[];
}

export interface DocumentSearchResult {
  content: string;
  metadata: Record<string, any>;
  score: number;
  document_id: string;
  document?: DocumentMetadata;
}