import { useState, useEffect } from 'react';
import { ThemeProvider } from 'next-themes';
import { Toaster } from '@/components/ui/sonner';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Header } from '@/components/layout/Header';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { DocumentUpload } from '@/components/upload/DocumentUpload';
import { Settings as SettingsPanel } from '@/components/settings/Settings';
import { useChat } from '@/hooks/useChat';
import type { Settings } from '@/types';

function App() {
  const [uploadOpen, setUploadOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
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
    clearConversation,
  } = useChat();

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

  const handleClearChat = () => {
    if (confirm('Are you sure you want to clear the conversation?')) {
      clearConversation();
    }
  };

  return (
    <ErrorBoundary>
      <ThemeProvider attribute="class" defaultTheme={settings.theme} enableSystem>
        <div className="flex flex-col h-screen bg-background">
          <ErrorBoundary>
            <Header
              onUploadClick={() => setUploadOpen(true)}
              onSettingsClick={() => setSettingsOpen(true)}
              onClearChat={handleClearChat}
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

          <Toaster richColors position="bottom-right" />
        </div>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App
