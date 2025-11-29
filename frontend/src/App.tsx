import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from 'next-themes';
import { Toaster } from '@/components/ui/sonner';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { AuthProvider } from '@/contexts/AuthContext';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { LoginPage } from '@/pages/LoginPage';
import { AuthCallback } from '@/pages/AuthCallback';
import { DocumentsPage } from '@/pages/DocumentsPage';
import { Sidebar } from '@/components/layout/Sidebar';
import { MainHeader } from '@/components/layout/MainHeader';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { DocumentUpload } from '@/components/upload/DocumentUpload';
import { Settings as SettingsPanel } from '@/components/settings/Settings';
import { useChat } from '@/hooks/useChat';
import { api } from '@/services/apiClient';
import type { Settings, Conversation } from '@/types';

function MainApp() {
  const [uploadOpen, setUploadOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [settings, setSettings] = useState<Settings>(() => {
    const saved = localStorage.getItem('chatSettings');
    if (saved) {
      return JSON.parse(saved);
    }
    return {
      temperature: 0.5,
      maxTokens: 200,
      streamMode: false,
      theme: 'system',
    };
  });

  const {
    messages,
    loading,
    wsConnected,
    sendMessage,
    loadConversation,
    startNewChat,
    conversationId,
  } = useChat();

  // Fetch conversations
  useEffect(() => {
    fetchConversations();
  }, []);

  // Refresh conversations when a new message is sent
  useEffect(() => {
    if (messages.length > 0) {
      fetchConversations();
    }
  }, [messages.length]);

  const fetchConversations = async () => {
    try {
      const data = await api.get<Conversation[]>('/api/v1/chat/conversations');
      setConversations(data);
    } catch (error) {
      console.error('Failed to fetch conversations:', error);
    }
  };

  useEffect(() => {
    localStorage.setItem('chatSettings', JSON.stringify(settings));
  }, [settings]);

  const handleSendMessage = (message: string) => {
    sendMessage(
      message,
      settings.streamMode,
      settings.temperature,
      settings.maxTokens
    );
  };

  const handleSelectConversation = (convId: string | null) => {
    loadConversation(convId);
    // On mobile, close sidebar after selection
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  };

  const handleNewChat = () => {
    startNewChat();
    // On mobile, close sidebar after new chat
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  };

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <ErrorBoundary>
        <Sidebar
          conversations={conversations}
          currentConversationId={conversationId}
          onSelectConversation={handleSelectConversation}
          onNewChat={handleNewChat}
          onSettingsClick={() => setSettingsOpen(true)}
          onUploadClick={() => setUploadOpen(true)}
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
          isCollapsed={sidebarCollapsed}
          onCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        />
      </ErrorBoundary>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <ErrorBoundary>
          <MainHeader
            onNewChat={handleNewChat}
            onSettingsClick={() => setSettingsOpen(true)}
            wsConnected={wsConnected}
          />
        </ErrorBoundary>

        <main className="flex-1 overflow-hidden">
          <ErrorBoundary>
            <ChatInterface
              messages={messages}
              loading={loading}
              onSendMessage={handleSendMessage}
              wsConnected={wsConnected}
            />
          </ErrorBoundary>
        </main>
      </div>

      <ErrorBoundary>
        <DocumentUpload
          open={uploadOpen}
          onOpenChange={setUploadOpen}
        />
      </ErrorBoundary>

      <ErrorBoundary>
        <SettingsPanel
          open={settingsOpen}
          onOpenChange={setSettingsOpen}
          settings={settings}
          onSettingsChange={setSettings}
        />
      </ErrorBoundary>
    </div>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <AuthProvider>
            <Routes>
              {/* Public routes */}
              <Route path="/login" element={<LoginPage />} />
              <Route path="/auth/callback" element={<AuthCallback />} />

              {/* Protected routes */}
              <Route
                path="/documents"
                element={
                  <ProtectedRoute>
                    <DocumentsPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/*"
                element={
                  <ProtectedRoute>
                    <MainApp />
                  </ProtectedRoute>
                }
              />
            </Routes>
            <Toaster richColors position="bottom-right" />
          </AuthProvider>
        </ThemeProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
