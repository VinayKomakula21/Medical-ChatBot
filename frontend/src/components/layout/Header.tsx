import { Button } from '@/components/ui/button';
import {
  Settings,
  Upload,
  Moon,
  Sun,
  Trash2,
  Sparkles
} from 'lucide-react';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';

interface HeaderProps {
  onUploadClick: () => void;
  onSettingsClick: () => void;
  onClearChat: () => void;
  wsConnected: boolean;
}

export function Header({ onUploadClick, onSettingsClick, onClearChat, wsConnected }: HeaderProps) {
  const { theme, setTheme } = useTheme();

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200 bg-white/95 backdrop-blur-sm">
      <div className="container flex h-14 items-center px-4">
        {/* Logo and Title */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full gradient-purple-blue flex items-center justify-center shadow-sm">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <h1 className="text-lg font-semibold text-slate-800">MediBot</h1>
        </div>

        <div className="flex-1" />

        {/* Right side actions */}
        <div className="flex items-center gap-1">
          {/* Connection status badge - minimal */}
          {wsConnected !== undefined && (
            <div className={cn(
              "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium mr-2",
              wsConnected
                ? "bg-green-50 text-green-700 border border-green-200"
                : "bg-red-50 text-red-700 border border-red-200"
            )}>
              <div className={cn(
                "w-1.5 h-1.5 rounded-full",
                wsConnected ? "bg-green-500" : "bg-red-500"
              )} />
              <span>{wsConnected ? 'Connected' : 'Offline'}</span>
            </div>
          )}

          <Button
            size="icon"
            onClick={onClearChat}
            title="Clear conversation"
            className="h-9 w-9 rounded-lg hover:bg-slate-100 transition-colors"
            variant="ghost"
          >
            <Trash2 className="h-4 w-4 text-slate-600" />
          </Button>

          <Button
            size="icon"
            onClick={onUploadClick}
            title="Upload document"
            className="h-9 w-9 rounded-lg hover:bg-slate-100 transition-colors"
            variant="ghost"
          >
            <Upload className="h-4 w-4 text-slate-600" />
          </Button>

          <Button
            size="icon"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            title="Toggle theme"
            className="h-9 w-9 rounded-lg hover:bg-slate-100 transition-colors"
            variant="ghost"
          >
            {theme === 'dark' ? (
              <Sun className="h-4 w-4 text-slate-600" />
            ) : (
              <Moon className="h-4 w-4 text-slate-600" />
            )}
          </Button>

          <Button
            size="icon"
            onClick={onSettingsClick}
            title="Settings"
            className="h-9 w-9 rounded-lg hover:bg-slate-100 transition-colors"
            variant="ghost"
          >
            <Settings className="h-4 w-4 text-slate-600" />
          </Button>
        </div>
      </div>
    </header>
  );
}