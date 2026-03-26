import { useState, useEffect } from 'react'

export function useTheme() {
  const [isDark, setIsDark] = useState(() => localStorage.getItem('mcp-theme') !== 'light')

  const toggle = () => {
    setIsDark(d => {
      const next = !d
      localStorage.setItem('mcp-theme', next ? 'dark' : 'light')
      document.documentElement.classList.toggle('dark', next)
      return next
    })
  }

  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDark)
  }, [])

  return { isDark, toggle, setMode: (mode: 'dark' | 'light') => setIsDark(mode === 'dark') }
}
