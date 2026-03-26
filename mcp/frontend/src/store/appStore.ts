// Stub — matches Zustand selector pattern
export function useAppStore(selector?: any): any {
  const state = {
    activeProject: null as any,
    currentProject: null as any,
    setActiveProject: (_p: any) => {},
    setCurrentProject: (_p: any) => {},
  }
  if (typeof selector === 'function') return selector(state)
  return state
}
