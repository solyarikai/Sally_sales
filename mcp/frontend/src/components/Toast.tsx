export function useToast() {
  return {
    toast: (...args: any[]) => console.log('[toast]', ...args),
    success: (...args: any[]) => console.log('[success]', ...args),
    error: (...args: any[]) => console.error('[error]', ...args),
    warning: (...args: any[]) => console.warn('[warning]', ...args),
    info: (...args: any[]) => console.info('[info]', ...args),
  }
}
