import axios from 'axios';
import type { AxiosInstance } from 'axios';
import type {
  ChatRequest,
  ChatResponse,
  DocumentUploadResponse
} from '@/types';

class ApiService {
  private api: AxiosInstance;

  constructor() {
    this.api = axios.create({
      baseURL: 'http://localhost:8000/api/v1',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.api.interceptors.response.use(
      response => response,
      error => {
        console.error('API Error:', error);
        return Promise.reject(error);
      }
    );
  }

  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await this.api.post('/chat/message', request);
    return response.data;
  }

  async uploadDocument(file: File, onProgress?: (progress: number) => void): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await this.api.post('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total) {
          const progress = (progressEvent.loaded / progressEvent.total) * 100;
          onProgress?.(progress);
        }
      },
    });

    return response.data;
  }

  async getConversationHistory(conversationId: string): Promise<any[]> {
    const response = await this.api.get(`/chat/history/${conversationId}`);
    return response.data;
  }

  async clearConversation(conversationId: string): Promise<void> {
    await this.api.delete(`/chat/history/${conversationId}`);
  }

  async listDocuments(page: number = 1, pageSize: number = 20): Promise<any> {
    const response = await this.api.get('/documents/', {
      params: { page, page_size: pageSize }
    });
    return response.data;
  }

  async deleteDocument(documentId: string): Promise<void> {
    await this.api.delete(`/documents/${documentId}`);
  }
}

export const apiService = new ApiService();