import { api } from './client'
import type { Notification } from '../types'

export const notificationsApi = {
  list: () => api.get<{ unread: number; notifications: Notification[] }>('/notifications/'),
  markRead: (id: string) => api.patch(`/notifications/${id}/read`),
  markAllRead: () => api.patch('/notifications/read-all'),
}
