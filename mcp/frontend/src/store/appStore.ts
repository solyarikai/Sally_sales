// Stub app store — main app uses Zustand but we don't need full store for MCP
export function useAppStore() {
  return {
    activeProject: null,
    setActiveProject: () => {},
  }
}
