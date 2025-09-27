/**
 * Custom hook for document API operations
 */

import { useState, useCallback } from 'react';
import { api } from '@/services/apiClient';
import type { DocumentUploadResponse } from '@/types';
import type {
  DocumentListResponse,
  DocumentSearchRequest,
  DocumentSearchResult,
  DocumentMetadata
} from '@/types/api.types';
import { useApi } from './useApi';

interface UseDocumentApiOptions {
  onUploadProgress?: (progress: number) => void;
  onUploadSuccess?: (response: DocumentUploadResponse) => void;
  onUploadError?: (error: Error) => void;
}

export function useDocumentApi(options: UseDocumentApiOptions = {}) {
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [documents, setDocuments] = useState<DocumentMetadata[]>([]);
  const [searchResults, setSearchResults] = useState<DocumentSearchResult[]>([]);

  const { execute: uploadExecute, loading: uploading, error: uploadError } = useApi<DocumentUploadResponse>({
    onSuccess: (response) => {
      setUploadProgress(100);
      if (options.onUploadSuccess) {
        options.onUploadSuccess(response);
      }
      // Reset progress after a delay
      setTimeout(() => setUploadProgress(0), 1000);
    },
    onError: (error) => {
      setUploadProgress(0);
      if (options.onUploadError) {
        options.onUploadError(new Error(error.error));
      }
    },
  });

  const { execute: listExecute, loading: listLoading } = useApi<DocumentListResponse>({
    onSuccess: (response) => {
      setDocuments(response.documents);
    },
  });

  const { execute: searchExecute, loading: searching } = useApi<DocumentSearchResult[]>({
    onSuccess: (results) => {
      setSearchResults(results);
    },
  });

  const { execute: deleteExecute } = useApi<{ status: string }>();

  const uploadDocument = useCallback(
    async (file: File, tags?: string[], metadata?: Record<string, any>) => {
      setUploadProgress(0);

      const formData = new FormData();
      formData.append('file', file);

      if (tags && tags.length > 0) {
        formData.append('tags', tags.join(','));
      }

      if (metadata) {
        formData.append('custom_metadata', JSON.stringify(metadata));
      }

      return uploadExecute(
        api.post<DocumentUploadResponse>(
          '/api/v1/documents/upload',
          formData,
          {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
            onUploadProgress: (progressEvent) => {
              if (progressEvent.total) {
                const progress = Math.round((progressEvent.loaded / progressEvent.total) * 100);
                setUploadProgress(progress);

                if (options.onUploadProgress) {
                  options.onUploadProgress(progress);
                }
              }
            },
          }
        )
      );
    },
    [uploadExecute, options]
  );

  const listDocuments = useCallback(
    async (page = 1, pageSize = 20) => {
      return listExecute(
        api.get<DocumentListResponse>('/api/v1/documents', {
          params: {
            page,
            page_size: pageSize,
          },
        })
      );
    },
    [listExecute]
  );

  const searchDocuments = useCallback(
    async (query: string, topK = 5, filterTags?: string[]) => {
      const request: DocumentSearchRequest = {
        query,
        top_k: topK,
        filter_tags: filterTags,
      };

      return searchExecute(
        api.post<DocumentSearchResult[]>('/api/v1/documents/search', request)
      );
    },
    [searchExecute]
  );

  const deleteDocument = useCallback(
    async (documentId: string) => {
      const result = await deleteExecute(
        api.delete(`/api/v1/documents/${documentId}`)
      );

      if (result.data) {
        // Remove from local state
        setDocuments((prev) => prev.filter((doc) => doc.id !== documentId));
      }

      return result;
    },
    [deleteExecute]
  );

  const getDocumentById = useCallback(
    (documentId: string) => {
      return documents.find((doc) => doc.id === documentId);
    },
    [documents]
  );

  const filterDocumentsByTags = useCallback(
    (tags: string[]) => {
      return documents.filter((doc) =>
        tags.some((tag) => doc.tags.includes(tag))
      );
    },
    [documents]
  );

  return {
    // State
    documents,
    searchResults,
    uploadProgress,
    uploading,
    uploadError,
    listLoading,
    searching,

    // Actions
    uploadDocument,
    listDocuments,
    searchDocuments,
    deleteDocument,

    // Utilities
    getDocumentById,
    filterDocumentsByTags,
  };
}