import { create } from 'zustand'
import type { User } from '../types'
import { authApi } from '../api/auth'

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, displayName: string, password: string) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  // 若 localStorage 有 token，初始設為 true 避免 RequireAuth 在 fetchMe 完成前就跳轉 /login
  loading: !!localStorage.getItem('access_token'),

  login: async (email, password) => {
    const res = await authApi.login(email, password)
    localStorage.setItem('access_token', res.data.access_token)
    localStorage.setItem('refresh_token', res.data.refresh_token)
    const me = await authApi.me()
    set({ user: me.data })
  },

  register: async (email, displayName, password) => {
    await authApi.register(email, displayName, password)
  },

  logout: () => {
    localStorage.clear()
    set({ user: null })
  },

  fetchMe: async () => {
    set({ loading: true })
    try {
      const res = await authApi.me()
      set({ user: res.data })
    } catch {
      set({ user: null })
    } finally {
      set({ loading: false })
    }
  },
}))
