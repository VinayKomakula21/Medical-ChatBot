/**
 * Enhanced App component with proper context and error handling
 * This is an example of how to use the new components and hooks
 */

import React from 'react';
import { ThemeProvider } from 'next-themes';
import { Toaster } from '@/components/ui/sonner';
import { ErrorBoundary } from '@/components/common/ErrorBoundary';
import { Header } from '@/components/layout/Header';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { DocumentUpload } from '@/components/upload/DocumentUpload';
import { Settings as SettingsPanel } from '@/components/settings/Settings';
import { AppProvider, useAppContext } from '@/contexts/AppContext';
import { useChatApi } from '@/hooks/useChatApi';
import { useDocumentApi } from '@/hooks/useDocumentApi';
import { toast } from 'sonner';

// Main App component wrapped with providers
function AppContent() {
  const {
    settings,
    updateSettings,
    isUploadModalOpen,
    setUploadModalOpen,
    isSettingsOpen,
    setSettingsOpen,
  } = useAppContext();

  const {
    messages,
    loading,
    isConnected,
    send,
    clearHistory,
    connectWebSocket,
  } = useChatApi({
    enablePersistence: true,
    onMessage: (message) => {
      // Show notification for assistant responses
      if (message.role === 'assistant' && message.sources?.length) {
        toast.info(`Found ${message.sources.length} relevant sources`);
      }
    },
  });

  const {
    listDocuments,
  } = useDocumentApi({
    onUploadSuccess: (response) => {
      toast.success(`Document "${response.filename}" uploaded successfully!`);
      setUploadModalOpen(false);
      // Refresh document list
      listDocuments();
    },
    onUploadError: (error) => {
      toast.error(`Upload failed: ${error.message}`);
    },
  });

  // Connect WebSocket on mount if streaming is enabled
  React.useEffect(() => {
    if (settings.streamMode) {
      connectWebSocket();
    }
  }, [settings.streamMode, connectWebSocket]);

  // Load documents on mount
  React.useEffect(() => {
    listDocuments();
  }, [listDocuments]);

  const handleSendMessage = (message: string) => {
    send(
      message,
      settings.streamMode,
      settings.temperature,
      settings.maxTokens
    );
  };

  const handleClearChat = () => {
    if (confirm('Are you sure you want to clear the conversation?')) {
      clearHistory();
      toast.success('Conversation cleared');
    }
  };


  return (
    <div className="flex flex-col h-screen bg-background">
      <Header
        onUploadClick={() => setUploadModalOpen(true)}
        onSettingsClick={() => setSettingsOpen(true)}
        onClearChat={handleClearChat}
        wsConnected={isConnected}
      />

      <main className="flex-1 overflow-hidden">
        <ChatInterface
          messages={messages}
          loading={loading}
          onSendMessage={handleSendMessage}
        />
      </main>

      <DocumentUpload
        open={isUploadModalOpen}
        onOpenChange={setUploadModalOpen}
      />

      <SettingsPanel
        open={isSettingsOpen}
        onOpenChange={setSettingsOpen}
        settings={settings}
        onSettingsChange={updateSettings}
      />

      <Toaster
        position="bottom-right"
        expand={false}
        richColors
        closeButton
      />
    </div>
  );
}

// Root App component with all providers
export function App() {
  return (
    <ErrorBoundary
      onError={(error, errorInfo) => {
        // Log to error tracking service
        console.error('App Error:', error, errorInfo);
      }}
    >
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
      >
        <AppProvider>
          <AppContent />
        </AppProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;