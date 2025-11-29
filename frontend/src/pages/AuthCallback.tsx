/**
 * OAuth Callback Page
 * Handles the redirect from Google OAuth, extracts token, and redirects to home
 */

import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Sparkles, AlertCircle } from 'lucide-react';

export function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { setToken } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handleCallback = async () => {
      const token = searchParams.get('token');
      const errorParam = searchParams.get('error');

      if (errorParam) {
        setError(decodeURIComponent(errorParam));
        return;
      }

      if (!token) {
        setError('No authentication token received');
        return;
      }

      try {
        await setToken(token);
        navigate('/', { replace: true });
      } catch (err) {
        console.error('Auth callback error:', err);
        setError('Failed to complete authentication');
      }
    };

    handleCallback();
  }, [searchParams, setToken, navigate]);

  if (error) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800 px-4">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-100 dark:bg-red-900 mb-4">
            <AlertCircle className="h-8 w-8 text-red-600 dark:text-red-400" />
          </div>
          <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-2">
            Authentication Failed
          </h1>
          <p className="text-slate-600 dark:text-slate-400 mb-6">
            {error}
          </p>
          <button
            onClick={() => navigate('/login', { replace: true })}
            className="px-6 py-2 bg-slate-800 dark:bg-slate-200 text-white dark:text-slate-800 rounded-lg hover:opacity-90 transition-opacity"
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full gradient-purple-blue shadow-lg mb-4 animate-pulse">
          <Sparkles className="h-8 w-8 text-white" />
        </div>
        <h1 className="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-2">
          Signing you in...
        </h1>
        <p className="text-slate-600 dark:text-slate-400">
          Please wait while we complete your authentication
        </p>
        <div className="mt-6">
          <div className="w-8 h-8 border-4 border-slate-200 dark:border-slate-700 border-t-purple-600 rounded-full animate-spin mx-auto" />
        </div>
      </div>
    </div>
  );
}
