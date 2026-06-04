import { create } from 'zustand'

interface ThemeStore {
  dark: boolean
  toggle: () => void
  init: () => void
}

export const useThemeStore = create<ThemeStore>((set) => ({
  dark: localStorage.getItem('theme') === 'dark',
  toggle: () =>
    set((s) => {
      const next = !s.dark
      localStorage.setItem('theme', next ? 'dark' : 'light')
      document.documentElement.classList.toggle('dark', next)
      return { dark: next }
    }),
  init: () => {
    const isDark = localStorage.getItem('theme') === 'dark'
    document.documentElement.classList.toggle('dark', isDark)
  },
}))
