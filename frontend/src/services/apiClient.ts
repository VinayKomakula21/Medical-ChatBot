/**
 * Enhanced API client with proper error handling and TypeScript support
 */

import axios from 'axios';
import type { AxiosInstance, AxiosError, AxiosRequestConfig } from 'axios';
import type { ApiError } from '@/types/api.types';

class ApiClient {
  private client: AxiosInstance;
  private baseURL: string;

  constructor() {
    this.baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

    this.client = axios.create({
      baseURL: this.baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        // Add auth token if available
        const token = localStorage.getItem('auth_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }

        // Add request ID for tracking
        config.headers['X-Request-ID'] = this.generateRequestId();

        // Log request in development
        if (import.meta.env.DEV) {
          console.log(`🚀 ${config.method?.toUpperCase()} ${config.url}`, config.data);
        }

        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => {
        if (import.meta.env.DEV) {
          console.log(`✅ Response from ${response.config.url}:`, response.data);
        }
        return response;
      },
      (error: AxiosError<ApiError>) => {
        const apiError = this.handleError(error);

        if (import.meta.env.DEV) {
          console.error(`❌ API Error:`, apiError);
        }

        // Handle specific error cases
        if (error.response?.status === 401) {
          // Clear auth and redirect to login if needed
          localStorage.removeItem('auth_token');
          // window.location.href = '/login';
        }

        return Promise.reject(apiError);
      }
    );
  }

  private generateRequestId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  private handleError(error: AxiosError<ApiError>): ApiError {
    if (error.response?.data) {
      return {
        error: error.response.data.error || 'An error occurred',
        detail: error.response.data.detail,
        request_id: error.response.data.request_id,
        status_code: error.response.status,
      };
    }

    if (error.code === 'ECONNABORTED') {
      return {
        error: 'Request timeout',
        detail: 'The request took too long to complete',
        status_code: 408,
      };
    }

    if (!error.response) {
      return {
        error: 'Network error',
        detail: 'Unable to connect to the server',
        status_code: 0,
      };
    }

    return {
      error: 'Unknown error',
      detail: error.message,
      status_code: error.response?.status || 500,
    };
  }

  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.get<T>(url, config);
    return response.data;
  }

  async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.post<T>(url, data, config);
    return response.data;
  }

  async put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.put<T>(url, data, config);
    return response.data;
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.delete<T>(url, config);
    return response.data;
  }

  async upload<T>(url: string, file: File, onProgress?: (progress: number) => void): Promise<T> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await this.client.post<T>(url, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = (progressEvent.loaded / progressEvent.total) * 100;
          onProgress(progress);
        }
      },
    });

    return response.data;
  }

  // WebSocket connection helper
  createWebSocket(path: string): WebSocket {
    const wsUrl = this.baseURL.replace('http', 'ws') + path;
    return new WebSocket(wsUrl);
  }
}

// Singleton instance
export const apiClient = new ApiClient();

// Export convenience methods
export const api = {
  get: <T>(url: string, config?: AxiosRequestConfig) => apiClient.get<T>(url, config),
  post: <T>(url: string, data?: any, config?: AxiosRequestConfig) => apiClient.post<T>(url, data, config),
  put: <T>(url: string, data?: any, config?: AxiosRequestConfig) => apiClient.put<T>(url, data, config),
  delete: <T>(url: string, config?: AxiosRequestConfig) => apiClient.delete<T>(url, config),
  upload: <T>(url: string, file: File, onProgress?: (progress: number) => void) => apiClient.upload<T>(url, file, onProgress),
  ws: (path: string) => apiClient.createWebSocket(path),
};