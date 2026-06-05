import { create } from 'zustand'

export type ToastType = 'success' | 'error' | 'info' | 'warning'

export interface Toast {
  id: string
  type: ToastType
  message: string
  duration?: number
}

interface ToastState {
  toasts: Toast[]
  add: (type: ToastType, message: string, duration?: number) => void
  remove: (id: string) => void
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  add: (type, message, duration = 3500) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`
    set(s => ({ toasts: [...s.toasts, { id, type, message, duration }] }))
    setTimeout(() => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })), duration)
  },
  remove: (id) => set(s => ({ toasts: s.toasts.filter(t => t.id !== id) })),
}))

// Convenience helpers (callable outside React)
export const toast = {
  success: (msg: string, ms?: number) => useToastStore.getState().add('success', msg, ms),
  error:   (msg: string, ms?: number) => useToastStore.getState().add('error',   msg, ms),
  info:    (msg: string, ms?: number) => useToastStore.getState().add('info',    msg, ms),
  warning: (msg: string, ms?: number) => useToastStore.getState().add('warning', msg, ms),
}
