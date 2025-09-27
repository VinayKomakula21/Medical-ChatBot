/**
 * Reusable loading component with different variants
 */

import React from 'react';
import { cn } from '@/lib/utils';

interface LoadingProps {
  variant?: 'spinner' | 'dots' | 'pulse' | 'skeleton';
  size?: 'sm' | 'md' | 'lg';
  text?: string;
  className?: string;
}

export const Loading: React.FC<LoadingProps> = ({
  variant = 'spinner',
  size = 'md',
  text,
  className,
}) => {
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-8 h-8',
    lg: 'w-12 h-12',
  };

  const renderLoading = () => {
    switch (variant) {
      case 'spinner':
        return (
          <div
            className={cn(
              'animate-spin rounded-full border-2 border-gray-300 border-t-blue-600',
              sizeClasses[size],
              className
            )}
          />
        );

      case 'dots':
        return (
          <div className="flex space-x-1">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className={cn(
                  'rounded-full bg-blue-600 animate-pulse',
                  size === 'sm' ? 'w-2 h-2' : size === 'md' ? 'w-3 h-3' : 'w-4 h-4',
                  className
                )}
                style={{
                  animationDelay: `${i * 150}ms`,
                }}
              />
            ))}
          </div>
        );

      case 'pulse':
        return (
          <div className={cn('space-y-2', className)}>
            <div className="h-4 bg-gray-200 rounded animate-pulse" />
            <div className="h-4 bg-gray-200 rounded animate-pulse w-3/4" />
            <div className="h-4 bg-gray-200 rounded animate-pulse w-1/2" />
          </div>
        );

      case 'skeleton':
        return (
          <div className={cn('animate-pulse', className)}>
            <div className="flex space-x-4">
              <div className="rounded-full bg-gray-200 h-10 w-10" />
              <div className="flex-1 space-y-2 py-1">
                <div className="h-3 bg-gray-200 rounded" />
                <div className="space-y-2">
                  <div className="h-3 bg-gray-200 rounded w-5/6" />
                  <div className="h-3 bg-gray-200 rounded w-4/6" />
                </div>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col items-center justify-center space-y-2">
      {renderLoading()}
      {text && (
        <p className={cn('text-sm text-gray-600 dark:text-gray-400', className)}>
          {text}
        </p>
      )}
    </div>
  );
};

// Specialized loading components
export const SpinnerLoading: React.FC<Omit<LoadingProps, 'variant'>> = (props) => (
  <Loading variant="spinner" {...props} />
);

export const DotsLoading: React.FC<Omit<LoadingProps, 'variant'>> = (props) => (
  <Loading variant="dots" {...props} />
);

export const PulseLoading: React.FC<Omit<LoadingProps, 'variant'>> = (props) => (
  <Loading variant="pulse" {...props} />
);

export const SkeletonLoading: React.FC<Omit<LoadingProps, 'variant'>> = (props) => (
  <Loading variant="skeleton" {...props} />
);