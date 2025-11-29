/**
 * Sidebar Component
 * Persistent navigation sidebar with logo, search, nav menu, conversations, and user profile
 */

import { useState } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  Trash2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
  Loader2,
  Plus,
  Upload
} from 'lucide-react';
import MedibotIcon from '@/assets/medibot-icon.svg';
import { cn } from '@/lib/utils';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/services/apiClient';
import type { Conversation } from '@/types';

interface SidebarProps {
  conversations: Conversation[];
  currentConversationId: string | null;
  onSelectConversation: (id: string | null) => void;
  onNewChat: () => void;
  onSettingsClick: () => void;
  onUploadClick: () => void;
  isOpen: boolean;
  onToggle: () => void;
  isCollapsed?: boolean;
  onCollapse?: () => void;
}

type DateGroup = 'Today' | 'Yesterday' | 'Previous 7 days' | 'Older';

export function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewChat,
  onSettingsClick,
  onUploadClick,
  isOpen,
  onToggle,
  isCollapsed = false,
  onCollapse
}: SidebarProps) {
  const { user } = useAuth();
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const getInitials = (name: string | null, email: string) => {
    if (name) {
      return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
    }
    return email[0].toUpperCase();
  };

  const getDateGroup = (dateString: string | null): DateGroup => {
    if (!dateString) return 'Older';
    const date = new Date(dateString);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays <= 7) return 'Previous 7 days';
    return 'Older';
  };

  const groupConversations = (convs: Conversation[]) => {
    const groups: Record<DateGroup, Conversation[]> = {
      'Today': [],
      'Yesterday': [],
      'Previous 7 days': [],
      'Older': []
    };

    convs.forEach(conv => {
      const group = getDateGroup(conv.updated_at);
      groups[group].push(conv);
    });

    return groups;
  };

  const handleDelete = async (e: React.MouseEvent, conversationId: string) => {
    e.stopPropagation();
    if (!confirm('Delete this conversation?')) return;

    try {
      setDeletingId(conversationId);
      await api.delete(`/api/v1/chat/history/${conversationId}`);
      if (currentConversationId === conversationId) {
        onNewChat();
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    } finally {
      setDeletingId(null);
    }
  };

  const groupedConversations = groupConversations(conversations);

  return (
    <>
      {/* Mobile Toggle Button */}
      <button
        onClick={onToggle}
        className={cn(
          "md:hidden fixed top-3 left-3 z-50 p-2 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-md",
          isOpen && "hidden"
        )}
      >
        <Menu className="h-5 w-5 text-slate-600 dark:text-slate-400" />
      </button>

      {/* Overlay for mobile */}
      {isOpen && (
        <div
          className="md:hidden fixed inset-0 bg-black/20 z-40"
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed md:relative z-40 h-screen flex flex-col bg-[#FAFAFA] dark:bg-slate-900 border-r border-gray-200 dark:border-slate-800 transition-all duration-300",
          isOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
          isCollapsed ? "w-[72px]" : "w-[280px]"
        )}
      >
        {/* Logo Section */}
        <div className={cn("flex items-center p-4", isCollapsed ? "justify-center" : "justify-between")}>
          <div className={cn("flex items-center", isCollapsed ? "gap-0" : "gap-2.5")}>
            <img src={MedibotIcon} alt="MediBot" className="w-9 h-9" />
            {!isCollapsed && <span className="text-lg font-semibold text-gray-800 dark:text-slate-100">MediBot</span>}
          </div>
          <button
            onClick={onToggle}
            className={cn("md:hidden p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-800", isCollapsed && "hidden")}
          >
            <X className="h-5 w-5 text-gray-600 dark:text-slate-400" />
          </button>
        </div>

        {/* Collapse Button - Desktop only */}
        {onCollapse && (
          <button
            onClick={onCollapse}
            className="hidden md:flex absolute -right-3 top-7 w-6 h-6 items-center justify-center bg-white dark:bg-slate-800 border border-gray-200 dark:border-slate-700 rounded-full shadow-sm hover:bg-gray-50 dark:hover:bg-slate-700 transition-colors z-50"
          >
            {isCollapsed ? (
              <ChevronRight className="h-4 w-4 text-gray-600 dark:text-slate-400" />
            ) : (
              <ChevronLeft className="h-4 w-4 text-gray-600 dark:text-slate-400" />
            )}
          </button>
        )}

        {/* New Chat Button */}
        <div className={cn("px-3 pb-2", isCollapsed && "px-2")}>
          <button
            onClick={onNewChat}
            className={cn(
              "w-full flex items-center gap-2 px-3 py-2.5 rounded-xl bg-[#7C3AED] hover:bg-[#6D28D9] text-white font-medium transition-colors",
              isCollapsed && "justify-center px-2"
            )}
          >
            <Plus className="h-5 w-5" />
            {!isCollapsed && <span>New Chat</span>}
          </button>
        </div>

        {/* Conversations List - hide when collapsed */}
        {!isCollapsed && (
          <ScrollArea className="flex-1 px-3 mt-2">
            <div className="py-2 space-y-4">
              {(['Today', 'Yesterday', 'Previous 7 days', 'Older'] as DateGroup[]).map((group) => {
                const convs = groupedConversations[group];
                if (convs.length === 0) return null;

                // Map group names to BeeBot style
                const groupLabel = group === 'Previous 7 days' ? '7 Days Ago' : group;

                return (
                  <div key={group}>
                    <h3 className="text-[11px] font-medium text-gray-400 dark:text-slate-500 mb-2 px-2">
                      {groupLabel}
                    </h3>
                    <div className="space-y-0.5">
                      {convs.map((conv) => (
                        <button
                          key={conv.id}
                          onClick={() => onSelectConversation(conv.id)}
                          className={cn(
                            "w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-colors group",
                            currentConversationId === conv.id
                              ? "bg-gray-100 dark:bg-slate-800 text-gray-900 dark:text-slate-100"
                              : "text-gray-500 dark:text-slate-400 hover:bg-gray-100 dark:hover:bg-slate-800"
                          )}
                        >
                          <span className="flex-1 text-sm truncate">
                            {conv.title || 'New Conversation'}
                          </span>
                          <button
                            onClick={(e) => handleDelete(e, conv.id)}
                            disabled={deletingId === conv.id}
                            className={cn(
                              "p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity",
                              "hover:bg-red-100 dark:hover:bg-red-900/30 text-red-500 dark:text-red-400"
                            )}
                          >
                            {deletingId === conv.id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Trash2 className="h-3.5 w-3.5" />
                            )}
                          </button>
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}

              {conversations.length === 0 && (
                <div className="text-center py-8 text-sm text-gray-400 dark:text-slate-500">
                  No conversations yet
                </div>
              )}
            </div>
          </ScrollArea>
        )}

        {/* Spacer when collapsed */}
        {isCollapsed && <div className="flex-1" />}

        {/* Upload Documents Button */}
        <div className={cn("px-3 py-2", isCollapsed && "px-2")}>
          <button
            onClick={onUploadClick}
            title={isCollapsed ? "Upload Documents" : undefined}
            className={cn(
              "w-full flex items-center gap-2 px-3 py-2.5 rounded-xl border border-gray-200 dark:border-slate-700 text-gray-700 dark:text-slate-300 hover:bg-gray-100 dark:hover:bg-slate-800 transition-colors",
              isCollapsed && "justify-center px-2"
            )}
          >
            <Upload className="h-5 w-5" />
            {!isCollapsed && <span className="text-sm font-medium">Upload Documents</span>}
          </button>
        </div>

        {/* User Profile Section */}
        <div className={cn("border-t border-gray-200 dark:border-slate-800", isCollapsed ? "p-2" : "p-3")}>
          <button
            onClick={onSettingsClick}
            title={isCollapsed ? user?.name || 'User' : undefined}
            className={cn(
              "w-full flex items-center rounded-lg hover:bg-gray-100 dark:hover:bg-slate-800 cursor-pointer",
              isCollapsed ? "justify-center p-2" : "gap-3 p-2"
            )}
          >
            <Avatar className={cn(isCollapsed ? "h-10 w-10" : "h-9 w-9")}>
              <AvatarImage src={user?.avatar_url || undefined} alt={user?.name || 'User'} />
              <AvatarFallback className="bg-violet-100 dark:bg-violet-900 text-violet-700 dark:text-violet-300 text-sm font-medium">
                {user ? getInitials(user.name, user.email) : 'U'}
              </AvatarFallback>
            </Avatar>
            {!isCollapsed && (
              <>
                <div className="flex-1 min-w-0 text-left">
                  <p className="text-sm font-medium text-gray-800 dark:text-slate-100 truncate">
                    {user?.name || 'User'}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-slate-400 truncate">
                    {user?.email}
                  </p>
                </div>
                <ChevronDown className="h-4 w-4 text-gray-400 dark:text-slate-500" />
              </>
            )}
          </button>
        </div>
      </aside>
    </>
  );
}
