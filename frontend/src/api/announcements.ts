import { api } from './client'

export const announcementsApi = {
  list: () => api.get<any[]>('/announcements/'),
  create: (title: string, content: string, expiresAt?: string) =>
    api.post<any>('/announcements/', { title, content, expires_at: expiresAt }),
  markRead: (id: string) => api.post(`/announcements/${id}/read`),
  deactivate: (id: string) => api.delete(`/announcements/${id}`),
}
