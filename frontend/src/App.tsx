import { useState, useEffect } from 'react';
import { ThemeProvider } from 'next-themes';
import { Toaster } from '@/components/ui/sonner';
import { Header } from '@/components/layout/Header';
import { ChatInterface } from '@/components/chat/ChatInterface';
import { DocumentUpload } from '@/components/upload/DocumentUpload';
import { Settings as SettingsPanel } from '@/components/settings/Settings';
import { useChat } from '@/hooks/useChat';
import { Settings } from '@/types';

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
      maxTokens: 512,
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
    <ThemeProvider attribute="class" defaultTheme={settings.theme} enableSystem>
      <div className="flex flex-col h-screen bg-background">
        <Header
          onUploadClick={() => setUploadOpen(true)}
          onSettingsClick={() => setSettingsOpen(true)}
          onClearChat={handleClearChat}
          wsConnected={wsConnected}
        />

        <main className="flex-1 overflow-hidden">
          <ChatInterface
            messages={messages}
            loading={loading}
            onSendMessage={handleSendMessage}
          />
        </main>

        <DocumentUpload
          open={uploadOpen}
          onOpenChange={setUploadOpen}
        />

        <SettingsPanel
          open={settingsOpen}
          onOpenChange={setSettingsOpen}
          settings={settings}
          onSettingsChange={setSettings}
        />

        <Toaster richColors position="bottom-right" />
      </div>
    </ThemeProvider>
  );
}

export default App
