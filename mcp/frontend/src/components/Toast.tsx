// Stub toast
export function useToast() {
  return {
    toast: (msg: string, type?: string) => console.log(`[toast:${type}] ${msg}`),
    success: (msg: string) => console.log(`[success] ${msg}`),
    error: (msg: string) => console.error(`[error] ${msg}`),
  }
}
