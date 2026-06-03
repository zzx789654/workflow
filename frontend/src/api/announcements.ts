import { api } from './client'

export interface Announcement {
  id: string
  title: string
  content: string
  created_at: string
}

export const announcementsApi = {
  list: () => api.get<Announcement[]>('/announcements/'),
  markRead: (id: string) => api.post(`/announcements/${id}/read`),
}
