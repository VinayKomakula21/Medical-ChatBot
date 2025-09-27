import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
  Settings,
  Upload,
  MessageSquare,
  Moon,
  Sun,
  Trash2
} from 'lucide-react';
import { useTheme } from 'next-themes';

interface HeaderProps {
  onUploadClick: () => void;
  onSettingsClick: () => void;
  onClearChat: () => void;
  wsConnected: boolean;
}

export function Header({ onUploadClick, onSettingsClick, onClearChat, wsConnected }: HeaderProps) {
  const { theme, setTheme } = useTheme();

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-16 items-center px-4">
        <div className="flex items-center space-x-2">
          <MessageSquare className="h-6 w-6 text-primary" />
          <h1 className="text-xl font-bold">Medical ChatBot</h1>
        </div>

        <div className="flex-1" />

        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-2 mr-4">
            <div className={`h-2 w-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-red-500'} animate-pulse`} />
            <span className="text-sm text-muted-foreground">
              {wsConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>

          <Button
            variant="ghost"
            size="icon"
            onClick={onClearChat}
            title="Clear conversation"
          >
            <Trash2 className="h-4 w-4" />
          </Button>

          <Button
            variant="ghost"
            size="icon"
            onClick={onUploadClick}
            title="Upload document"
          >
            <Upload className="h-4 w-4" />
          </Button>

          <Button
            variant="ghost"
            size="icon"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            title="Toggle theme"
          >
            {theme === 'dark' ? (
              <Sun className="h-4 w-4" />
            ) : (
              <Moon className="h-4 w-4" />
            )}
          </Button>

          <Button
            variant="ghost"
            size="icon"
            onClick={onSettingsClick}
            title="Settings"
          >
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  );
}