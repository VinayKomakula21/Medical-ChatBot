/**
 * User Profile Component
 * Displays user information and account actions
 */

import { useAuth } from '@/contexts/AuthContext';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  User,
  Mail,
  Calendar,
  LogOut,
  Shield
} from 'lucide-react';

export function UserProfile() {
  const { user, logout } = useAuth();

  if (!user) {
    return (
      <div className="text-center py-8 text-slate-500 dark:text-slate-400">
        <User className="h-12 w-12 mx-auto mb-4 text-slate-300 dark:text-slate-600" />
        <p>Not signed in</p>
      </div>
    );
  }

  const getInitials = (name: string | null, email: string) => {
    if (name) {
      return name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
    }
    return email[0].toUpperCase();
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  return (
    <div className="space-y-6">
      {/* Profile Header */}
      <div className="flex items-center gap-4">
        <Avatar className="h-16 w-16">
          <AvatarImage src={user.avatar_url || undefined} alt={user.name || 'User'} />
          <AvatarFallback className="bg-purple-100 dark:bg-purple-900 text-purple-700 dark:text-purple-300 text-xl font-semibold">
            {getInitials(user.name, user.email)}
          </AvatarFallback>
        </Avatar>
        <div>
          <h3 className="text-lg font-semibold text-slate-800 dark:text-slate-100">
            {user.name || 'User'}
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            {user.email}
          </p>
        </div>
      </div>

      <Separator />

      {/* Account Details */}
      <div className="space-y-4">
        <h4 className="text-sm font-medium text-slate-800 dark:text-slate-100">
          Account Details
        </h4>

        <div className="space-y-3">
          <div className="flex items-center gap-3 text-sm">
            <Mail className="h-4 w-4 text-slate-400" />
            <div>
              <div className="text-slate-500 dark:text-slate-400">Email</div>
              <div className="text-slate-800 dark:text-slate-100">{user.email}</div>
            </div>
          </div>

          <div className="flex items-center gap-3 text-sm">
            <Calendar className="h-4 w-4 text-slate-400" />
            <div>
              <div className="text-slate-500 dark:text-slate-400">Member since</div>
              <div className="text-slate-800 dark:text-slate-100">
                {formatDate(user.created_at)}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3 text-sm">
            <Shield className="h-4 w-4 text-slate-400" />
            <div>
              <div className="text-slate-500 dark:text-slate-400">Account Status</div>
              <div className="flex items-center gap-2">
                <span className={user.is_active ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}>
                  {user.is_active ? "Active" : "Inactive"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <Separator />

      {/* Account Actions */}
      <div className="space-y-4">
        <h4 className="text-sm font-medium text-slate-800 dark:text-slate-100">
          Account Actions
        </h4>

        <Button
          variant="outline"
          className="w-full justify-start text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950 border-red-200 dark:border-red-800"
          onClick={logout}
        >
          <LogOut className="h-4 w-4 mr-2" />
          Sign Out
        </Button>
      </div>

      {/* Footer Note */}
      <p className="text-xs text-slate-400 dark:text-slate-500 text-center">
        Signed in with Google OAuth
      </p>
    </div>
  );
}
