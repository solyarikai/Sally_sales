import * as ToastPrimitive from '@radix-ui/react-toast';
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';
import { cn } from '../lib/utils';

// Toast types
type ToastType = 'success' | 'error' | 'warning' | 'info';

interface Toast {
  id: string;
  type: ToastType;
  title: string;
  description?: string;
  duration?: number;
}

interface ToastContextValue {
  toasts: Toast[];
  toast: (toast: Omit<Toast, 'id'>) => void;
  success: (title: string, description?: string) => void;
  error: (title: string, description?: string) => void;
  warning: (title: string, description?: string) => void;
  info: (title: string, description?: string) => void;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

// Toast icons and colors by type
const toastConfig: Record<ToastType, { icon: typeof CheckCircle; className: string }> = {
  success: {
    icon: CheckCircle,
    className: 'bg-emerald-50 border-emerald-200 text-emerald-800',
  },
  error: {
    icon: AlertCircle,
    className: 'bg-red-50 border-red-200 text-red-800',
  },
  warning: {
    icon: AlertTriangle,
    className: 'bg-amber-50 border-amber-200 text-amber-800',
  },
  info: {
    icon: Info,
    className: 'bg-blue-50 border-blue-200 text-blue-800',
  },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((toast: Omit<Toast, 'id'>) => {
    const id = Math.random().toString(36).substring(7);
    setToasts((prev) => [...prev, { ...toast, id }]);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const success = useCallback(
    (title: string, description?: string) => {
      addToast({ type: 'success', title, description, duration: 4000 });
    },
    [addToast]
  );

  const error = useCallback(
    (title: string, description?: string) => {
      addToast({ type: 'error', title, description, duration: 6000 });
    },
    [addToast]
  );

  const warning = useCallback(
    (title: string, description?: string) => {
      addToast({ type: 'warning', title, description, duration: 5000 });
    },
    [addToast]
  );

  const info = useCallback(
    (title: string, description?: string) => {
      addToast({ type: 'info', title, description, duration: 4000 });
    },
    [addToast]
  );

  return (
    <ToastContext.Provider value={{ toasts, toast: addToast, success, error, warning, info, dismiss }}>
      <ToastPrimitive.Provider swipeDirection="right">
        {children}
        
        {toasts.map((t) => {
          const config = toastConfig[t.type];
          const Icon = config.icon;
          
          return (
            <ToastPrimitive.Root
              key={t.id}
              duration={t.duration || 5000}
              onOpenChange={(open) => {
                if (!open) dismiss(t.id);
              }}
              className={cn(
                'group pointer-events-auto relative flex w-full items-center justify-between space-x-4 overflow-hidden rounded-xl border p-4 shadow-lg transition-all',
                'data-[state=open]:animate-in data-[state=closed]:animate-out data-[swipe=end]:animate-out',
                'data-[state=closed]:fade-out-80 data-[state=closed]:slide-out-to-right-full',
                'data-[state=open]:slide-in-from-top-full data-[state=open]:sm:slide-in-from-bottom-full',
                config.className
              )}
            >
              <div className="flex items-start gap-3">
                <Icon className="w-5 h-5 flex-shrink-0 mt-0.5" />
                <div className="grid gap-1">
                  <ToastPrimitive.Title className="text-sm font-semibold">
                    {t.title}
                  </ToastPrimitive.Title>
                  {t.description && (
                    <ToastPrimitive.Description className="text-sm opacity-90">
                      {t.description}
                    </ToastPrimitive.Description>
                  )}
                </div>
              </div>
              <ToastPrimitive.Close className="absolute right-2 top-2 rounded-md p-1 opacity-0 transition-opacity hover:opacity-100 focus:opacity-100 group-hover:opacity-100">
                <X className="w-4 h-4" />
              </ToastPrimitive.Close>
            </ToastPrimitive.Root>
          );
        })}
        
        <ToastPrimitive.Viewport className="fixed bottom-0 right-0 z-[100] flex max-h-screen w-full flex-col-reverse p-4 sm:bottom-0 sm:right-0 sm:top-auto sm:flex-col md:max-w-[420px]" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}

// Hook to use toast
export function useToast() {
  const context = useContext(ToastContext);
  if (context === undefined) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
}

// Export a standalone toast for use outside of React components
let toastFunction: ToastContextValue['toast'] | null = null;

export function setToastFunction(fn: ToastContextValue['toast']) {
  toastFunction = fn;
}

export const toast = {
  success: (title: string, description?: string) => {
    if (toastFunction) toastFunction({ type: 'success', title, description, duration: 4000 });
  },
  error: (title: string, description?: string) => {
    if (toastFunction) toastFunction({ type: 'error', title, description, duration: 6000 });
  },
  warning: (title: string, description?: string) => {
    if (toastFunction) toastFunction({ type: 'warning', title, description, duration: 5000 });
  },
  info: (title: string, description?: string) => {
    if (toastFunction) toastFunction({ type: 'info', title, description, duration: 4000 });
  },
};
