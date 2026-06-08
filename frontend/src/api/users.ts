import { api } from './client'
import type { User } from '../types'

export const usersApi = {
  me: () => api.get<User>('/users/me'),

  updateMe: (data: { display_name?: string; avatar_url?: string | null; auto_archive_days?: number }) =>
    api.patch<User>('/users/me', data),

  list: () => api.get<User[]>('/users/'),
}
