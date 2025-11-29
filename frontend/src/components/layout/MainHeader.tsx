/**
 * Main Header Component
 * Clean header with model selector, new chat button, and user avatar
 */

import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Plus,
  ChevronDown,
  Moon,
  Sun,
  User
} from 'lucide-react';
import { useTheme } from 'next-themes';
import { useAuth } from '@/contexts/AuthContext';
import MedibotIcon from '@/assets/medibot-icon.svg';

interface MainHeaderProps {
  onNewChat: () => void;
  onSettingsClick: () => void;
  wsConnected?: boolean;
}

export function MainHeader({ onNewChat, onSettingsClick }: MainHeaderProps) {
  const { theme, setTheme } = useTheme();
  const { user } = useAuth();

  const getInitials = (name: string | null, email: string) => {
    if (name) {
      return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
    }
    return email[0].toUpperCase();
  };

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between h-14 sm:h-16 px-3 sm:px-4 md:px-6 bg-white dark:bg-slate-950">
      {/* Left side - Model Selector */}
      <div className="flex items-center">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="h-10 px-4 gap-2 text-sm font-medium text-gray-700 dark:text-slate-300 bg-gray-100 dark:bg-slate-800 hover:bg-gray-200 dark:hover:bg-slate-700 rounded-lg"
            >
              <img src={MedibotIcon} alt="MediBot" className="w-6 h-6" />
              iMediBot 4o
              <ChevronDown className="h-4 w-4 text-gray-400 ml-1" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-48">
            <DropdownMenuItem className="gap-2">
              <img src={MedibotIcon} alt="MediBot" className="w-4 h-4" />
              iMediBot 4o
            </DropdownMenuItem>
            <DropdownMenuItem className="gap-2 opacity-50" disabled>
              <img src={MedibotIcon} alt="MediBot" className="w-4 h-4 grayscale" />
              MediBot Basic
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Right side - Actions */}
      <div className="flex items-center gap-3">
        {/* New Chat Button */}
        <Button
          onClick={onNewChat}
          className="h-10 px-4 gap-2 bg-[#7C3AED] hover:bg-[#6D28D9] text-white rounded-lg font-medium"
        >
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">New Chat</span>
        </Button>

        {/* Theme Toggle - subtle */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          className="h-9 w-9 rounded-full hover:bg-gray-100 dark:hover:bg-slate-800"
        >
          {theme === 'dark' ? (
            <Sun className="h-4 w-4 text-gray-500 dark:text-slate-400" />
          ) : (
            <Moon className="h-4 w-4 text-gray-500 dark:text-slate-400" />
          )}
        </Button>

        {/* User Avatar - simple, no dropdown */}
        <Avatar className="h-9 w-9 cursor-pointer" onClick={onSettingsClick}>
          <AvatarImage src={user?.avatar_url || undefined} alt={user?.name || 'User'} />
          <AvatarFallback className="bg-amber-100 dark:bg-amber-900 text-amber-700 dark:text-amber-300 text-sm font-medium">
            {user ? getInitials(user.name, user.email) : <User className="h-4 w-4" />}
          </AvatarFallback>
        </Avatar>
      </div>
    </header>
  );
}
