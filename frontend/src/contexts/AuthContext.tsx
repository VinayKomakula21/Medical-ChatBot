/**
 * Authentication Context
 * Manages user authentication state, login/logout, and token management
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import type { User } from '@/types';
import { api } from '@/services/apiClient';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: () => void;
  logout: () => void;
  setToken: (token: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(() => {
    return localStorage.getItem('auth_token');
  });
  const [isLoading, setIsLoading] = useState(true);

  // Fetch user data when token exists
  const fetchUser = useCallback(async () => {
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      const userData = await api.get<User>('/api/v1/auth/me');
      setUser(userData);
    } catch (error) {
      console.error('Failed to fetch user:', error);
      // Token is invalid, clear it
      localStorage.removeItem('auth_token');
      setTokenState(null);
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  // Check auth on mount and when token changes
  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  // Redirect to Google OAuth login
  const login = useCallback(() => {
    window.location.href = `${API_URL}/api/v1/auth/google/login`;
  }, []);

  // Logout and clear state
  const logout = useCallback(async () => {
    try {
      await api.post('/api/v1/auth/logout');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      localStorage.removeItem('auth_token');
      setTokenState(null);
      setUser(null);
    }
  }, []);

  // Set token after OAuth callback
  const setToken = useCallback(async (newToken: string) => {
    localStorage.setItem('auth_token', newToken);
    setTokenState(newToken);
    setIsLoading(true);

    try {
      const userData = await api.get<User>('/api/v1/auth/me');
      setUser(userData);
    } catch (error) {
      console.error('Failed to fetch user after login:', error);
      localStorage.removeItem('auth_token');
      setTokenState(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const value: AuthContextType = {
    user,
    token,
    isAuthenticated: !!user && !!token,
    isLoading,
    login,
    logout,
    setToken,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
