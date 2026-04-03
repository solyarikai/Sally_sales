import { cn } from '../lib/utils';
import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  text?: string;
}

const sizeClasses = {
  sm: 'w-4 h-4',
  md: 'w-6 h-6',
  lg: 'w-8 h-8',
};

export function LoadingSpinner({ size = 'md', className, text }: LoadingSpinnerProps) {
  return (
    <div className={cn('flex items-center justify-center gap-2', className)}>
      <Loader2 className={cn('animate-spin text-violet-600', sizeClasses[size])} />
      {text && <span className="text-sm text-neutral-500">{text}</span>}
    </div>
  );
}

// Full page loading overlay
interface LoadingOverlayProps {
  text?: string;
}

export function LoadingOverlay({ text = 'Loading...' }: LoadingOverlayProps) {
  return (
    <div className="fixed inset-0 bg-white/80 backdrop-blur-sm z-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-lg p-8 flex flex-col items-center">
        <LoadingSpinner size="lg" />
        <p className="mt-4 text-neutral-600 font-medium">{text}</p>
      </div>
    </div>
  );
}

// Inline loading placeholder
interface LoadingPlaceholderProps {
  text?: string;
  className?: string;
}

export function LoadingPlaceholder({ text = 'Loading...', className }: LoadingPlaceholderProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center py-12', className)}>
      <LoadingSpinner size="lg" />
      <p className="mt-4 text-sm text-neutral-500">{text}</p>
    </div>
  );
}

// Button loading state
interface ButtonSpinnerProps {
  className?: string;
}

export function ButtonSpinner({ className }: ButtonSpinnerProps) {
  return <Loader2 className={cn('w-4 h-4 animate-spin', className)} />;
}

export default LoadingSpinner;
