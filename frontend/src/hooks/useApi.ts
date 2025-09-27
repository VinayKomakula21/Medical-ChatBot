/**
 * Custom hook for API calls with loading and error states
 */

import { useState, useCallback } from 'react';
import type { ApiError } from '@/types/api.types';

interface UseApiOptions {
  onSuccess?: (data: any) => void;
  onError?: (error: ApiError) => void;
  initialLoading?: boolean;
}

export function useApi<T>(options: UseApiOptions = {}) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(options.initialLoading || false);
  const [error, setError] = useState<ApiError | null>(null);

  const execute = useCallback(
    async (apiCall: Promise<T>) => {
      setLoading(true);
      setError(null);

      try {
        const result = await apiCall;
        setData(result);

        if (options.onSuccess) {
          options.onSuccess(result);
        }

        return { data: result, error: undefined };
      } catch (err) {
        const apiError = err as ApiError;
        setError(apiError);

        if (options.onError) {
          options.onError(apiError);
        }

        return { data: undefined, error: apiError };
      } finally {
        setLoading(false);
      }
    },
    [options]
  );

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return {
    data,
    loading,
    error,
    execute,
    reset,
  };
}