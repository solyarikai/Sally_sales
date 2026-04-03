import { create } from 'zustand';

export type ThemeMode = 'dark' | 'light';

const STORAGE_KEY = 'leadgen-theme';

function getInitialTheme(): ThemeMode {
  if (typeof window === 'undefined') return 'dark';
  const stored = localStorage.getItem(STORAGE_KEY);
  return stored === 'light' ? 'light' : 'dark';
}

function applyTheme(mode: ThemeMode) {
  if (mode === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
  localStorage.setItem(STORAGE_KEY, mode);
}

interface ThemeState {
  mode: ThemeMode;
  isDark: boolean;
  toggle: () => void;
  setMode: (m: ThemeMode) => void;
}

// Shared zustand store — same state across all components
export const useTheme = create<ThemeState>((set, get) => {
  const initial = getInitialTheme();
  // Apply on store creation (module load)
  if (typeof window !== 'undefined') applyTheme(initial);

  return {
    mode: initial,
    isDark: initial === 'dark',
    toggle: () => {
      const next: ThemeMode = get().mode === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      set({ mode: next, isDark: next === 'dark' });
    },
    setMode: (m: ThemeMode) => {
      applyTheme(m);
      set({ mode: m, isDark: m === 'dark' });
    },
  };
});
