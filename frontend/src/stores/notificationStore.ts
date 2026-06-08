import { create } from 'zustand'

interface NotificationState {
  refreshTick: number
  bump: () => void
}

export const useNotificationStore = create<NotificationState>((set) => ({
  refreshTick: 0,
  bump: () => set((s) => ({ refreshTick: s.refreshTick + 1 })),
}))
