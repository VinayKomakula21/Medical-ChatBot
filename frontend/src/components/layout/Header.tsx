import { Button } from '@/components/ui/button';
import {
  Settings,
  Upload,
  Moon,
  Sun,
  Trash2,
  Sparkles,
  LogOut,
  User
} from 'lucide-react';
import { useTheme } from 'next-themes';
import { cn } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';

interface HeaderProps {
  onUploadClick: () => void;
  onSettingsClick: () => void;
  onClearChat: () => void;
  wsConnected: boolean;
}

export function Header({ onUploadClick, onSettingsClick, onClearChat, wsConnected }: HeaderProps) {
  const { theme, setTheme } = useTheme();
  const { user, logout } = useAuth();

  const getInitials = (name: string | null, email: string) => {
    if (name) {
      return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
    }
    return email[0].toUpperCase();
  };

  return (
    <header className="sticky top-0 z-50 w-full border-b border-slate-200 dark:border-slate-800 bg-white/95 dark:bg-slate-900/95 backdrop-blur-sm">
      <div className="container flex h-12 sm:h-14 items-center px-3 sm:px-4">
        {/* Logo and Title */}
        <div className="flex items-center gap-2 sm:gap-2.5">
          <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-full gradient-purple-blue flex items-center justify-center shadow-sm">
            <Sparkles className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-white" />
          </div>
          <h1 className="text-base sm:text-lg font-semibold text-slate-800 dark:text-slate-100">MediBot</h1>
        </div>

        <div className="flex-1" />

        {/* Right side actions */}
        <div className="flex items-center gap-0.5 sm:gap-1">
          {/* Connection status badge - hidden on mobile */}
          {wsConnected !== undefined && (
            <div className={cn(
              "hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium mr-2",
              wsConnected
                ? "bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800"
                : "bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800"
            )}>
              <div className={cn(
                "w-1.5 h-1.5 rounded-full",
                wsConnected ? "bg-green-500" : "bg-red-500"
              )} />
              <span>{wsConnected ? 'Connected' : 'Offline'}</span>
            </div>
          )}

          {/* Show connection dot on mobile */}
          {wsConnected !== undefined && (
            <div className={cn(
              "sm:hidden flex items-center justify-center h-8 w-8 mr-1",
            )}>
              <div className={cn(
                "w-2 h-2 rounded-full",
                wsConnected ? "bg-green-500" : "bg-red-500 animate-pulse"
              )} />
            </div>
          )}

          <Button
            size="icon"
            onClick={onClearChat}
            title="Clear conversation"
            className="h-8 w-8 sm:h-9 sm:w-9 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            variant="ghost"
          >
            <Trash2 className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-slate-600 dark:text-slate-400" />
          </Button>

          <Button
            size="icon"
            onClick={onUploadClick}
            title="Upload document"
            className="hidden sm:flex h-9 w-9 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            variant="ghost"
          >
            <Upload className="h-4 w-4 text-slate-600 dark:text-slate-400" />
          </Button>

          <Button
            size="icon"
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
            title="Toggle theme"
            className="hidden sm:flex h-9 w-9 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            variant="ghost"
          >
            {theme === 'dark' ? (
              <Sun className="h-4 w-4 text-slate-600 dark:text-slate-400" />
            ) : (
              <Moon className="h-4 w-4 text-slate-600 dark:text-slate-400" />
            )}
          </Button>

          <Button
            size="icon"
            onClick={onSettingsClick}
            title="Settings"
            className="h-8 w-8 sm:h-9 sm:w-9 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            variant="ghost"
          >
            <Settings className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-slate-600 dark:text-slate-400" />
          </Button>

          {/* User Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                className="h-8 w-8 sm:h-9 sm:w-9 rounded-full p-0 ml-1"
              >
                <Avatar className="h-8 w-8 sm:h-9 sm:w-9">
                  <AvatarImage src={user?.avatar_url || undefined} alt={user?.name || 'User'} />
                  <AvatarFallback className="bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-300 text-sm font-medium">
                    {user ? getInitials(user.name, user.email) : <User className="h-4 w-4" />}
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <div className="flex items-center gap-2 p-2">
                <Avatar className="h-10 w-10">
                  <AvatarImage src={user?.avatar_url || undefined} alt={user?.name || 'User'} />
                  <AvatarFallback className="bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-300">
                    {user ? getInitials(user.name, user.email) : <User className="h-4 w-4" />}
                  </AvatarFallback>
                </Avatar>
                <div className="flex flex-col">
                  <span className="text-sm font-medium text-slate-800 dark:text-slate-100">
                    {user?.name || 'User'}
                  </span>
                  <span className="text-xs text-slate-500 dark:text-slate-400 truncate max-w-[160px]">
                    {user?.email}
                  </span>
                </div>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={logout}
                className="text-red-600 dark:text-red-400 cursor-pointer"
              >
                <LogOut className="mr-2 h-4 w-4" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
