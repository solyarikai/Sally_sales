import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Extract user-friendly error message from an API error.
 * Handles various error formats: Axios errors, fetch errors, and plain strings.
 */
export function getErrorMessage(error: unknown): string {
  // Already a string
  if (typeof error === 'string') {
    return error;
  }
  
  // Axios error with userMessage (set by our interceptor)
  if (error && typeof error === 'object') {
    const err = error as Record<string, unknown>;
    
    // Our custom user-friendly message (from API client interceptor)
    if (err.userMessage && typeof err.userMessage === 'string') {
      return err.userMessage;
    }
    
    // Response data formats
    if (err.response && typeof err.response === 'object') {
      const response = err.response as Record<string, unknown>;
      const data = response.data as Record<string, unknown> | undefined;
      
      if (data) {
        // FastAPI validation error format
        if (data.detail) {
          if (typeof data.detail === 'string') {
            return data.detail;
          }
          // Array of validation errors
          if (Array.isArray(data.detail)) {
            const messages = data.detail
              .map((d: Record<string, unknown>) => d.msg || d.message)
              .filter(Boolean);
            if (messages.length > 0) {
              return messages.join('. ');
            }
          }
        }
        
        // Other common formats
        if (data.message && typeof data.message === 'string') {
          return data.message;
        }
        if (data.error && typeof data.error === 'string') {
          return data.error;
        }
      }
      
      // Status code fallbacks
      const status = response.status as number | undefined;
      if (status === 401) return 'Please log in to continue';
      if (status === 403) return 'You do not have permission to perform this action';
      if (status === 404) return 'The requested resource was not found';
      if (status === 422) return 'Please check your input and try again';
      if (status && status >= 500) return 'Server error. Please try again later';
    }
    
    // Network error
    if (err.request && !err.response) {
      return 'Unable to connect to server. Please check your internet connection';
    }
    
    // Standard Error object
    if (err.message && typeof err.message === 'string') {
      // Clean up common technical messages
      const msg = err.message;
      if (msg.toLowerCase().includes('network error')) {
        return 'Unable to connect to server. Please check your internet connection';
      }
      if (msg.toLowerCase().includes('timeout')) {
        return 'Request timed out. Please try again';
      }
      // Don't show raw technical errors to users
      if (msg.includes('ERR_') || msg.includes('ECONNREFUSED')) {
        return 'Unable to connect to server. Please try again later';
      }
      return msg;
    }
  }
  
  return 'An unexpected error occurred. Please try again';
}

export function formatDate(date: string | null): string {
  if (!date) return '-';
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(date));
}

export function formatNumber(num: number): string {
  return new Intl.NumberFormat('en-US').format(num);
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + '...';
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'pending':
      return 'status-pending';
    case 'processing':
      return 'status-processing';
    case 'completed':
      return 'status-completed';
    case 'failed':
      return 'status-failed';
    default:
      return 'bg-gray-500/20 text-gray-400';
  }
}
