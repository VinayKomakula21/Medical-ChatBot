/**
 * Global application context for state management
 */

import React, { createContext, useContext, useState, useCallback } from 'react';
import type { ReactNode } from 'react';
import type { Settings } from '@/types';
import type { DocumentMetadata } from '@/types/api.types';

interface AppContextType {
  // Settings
  settings: Settings;
  updateSettings: (settings: Partial<Settings>) => void;

  // Conversation
  currentConversationId: string | undefined;
  setCurrentConversationId: (id: string | undefined) => void;

  // UI State
  isSidebarOpen: boolean;
  toggleSidebar: () => void;
  isUploadModalOpen: boolean;
  setUploadModalOpen: (open: boolean) => void;
  isSettingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;

  // Documents
  selectedDocuments: DocumentMetadata[];
  setSelectedDocuments: (docs: DocumentMetadata[]) => void;

  // Notifications
  notifications: Notification[];
  addNotification: (notification: Notification) => void;
  removeNotification: (id: string) => void;

  // Theme
  theme: 'light' | 'dark' | 'system';
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
}

interface Notification {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  message: string;
  duration?: number;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within AppProvider');
  }
  return context;
};

interface AppProviderProps {
  children: ReactNode;
}

export const AppProvider: React.FC<AppProviderProps> = ({ children }) => {
  // Load initial settings from localStorage
  const loadSettings = (): Settings => {
    const saved = localStorage.getItem('chatSettings');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        console.error('Failed to load settings:', e);
      }
    }
    return {
      temperature: 0.5,
      maxTokens: 512,
      streamMode: false,
      theme: 'system',
    };
  };

  const [settings, setSettings] = useState<Settings>(loadSettings());
  const [currentConversationId, setCurrentConversationId] = useState<string | undefined>();
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isUploadModalOpen, setUploadModalOpen] = useState(false);
  const [isSettingsOpen, setSettingsOpen] = useState(false);
  const [selectedDocuments, setSelectedDocuments] = useState<DocumentMetadata[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>(settings.theme);

  const updateSettings = useCallback((newSettings: Partial<Settings>) => {
    setSettings((prev) => {
      const updated = { ...prev, ...newSettings };
      localStorage.setItem('chatSettings', JSON.stringify(updated));
      return updated;
    });
  }, []);

  const toggleSidebar = useCallback(() => {
    setIsSidebarOpen((prev) => !prev);
  }, []);

  const addNotification = useCallback((notification: Omit<Notification, 'id'> & { id?: string }) => {
    const id = notification.id || Date.now().toString();
    const newNotification: Notification = {
      ...notification,
      id,
      duration: notification.duration || 5000,
    };

    setNotifications((prev) => [...prev, newNotification]);

    // Auto-remove after duration
    if (newNotification.duration && newNotification.duration > 0) {
      setTimeout(() => {
        removeNotification(id);
      }, newNotification.duration);
    }
  }, []);

  const removeNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const handleThemeChange = useCallback((newTheme: 'light' | 'dark' | 'system') => {
    setTheme(newTheme);
    updateSettings({ theme: newTheme });

    // Apply theme to document root
    const root = window.document.documentElement;
    root.classList.remove('light', 'dark');

    if (newTheme === 'system') {
      const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
      root.classList.add(systemTheme);
    } else {
      root.classList.add(newTheme);
    }
  }, [updateSettings]);

  const value: AppContextType = {
    settings,
    updateSettings,
    currentConversationId,
    setCurrentConversationId,
    isSidebarOpen,
    toggleSidebar,
    isUploadModalOpen,
    setUploadModalOpen,
    isSettingsOpen,
    setSettingsOpen,
    selectedDocuments,
    setSelectedDocuments,
    notifications,
    addNotification,
    removeNotification,
    theme,
    setTheme: handleThemeChange,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};