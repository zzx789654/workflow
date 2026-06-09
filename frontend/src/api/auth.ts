import { api } from './client'
import type { User, Token } from '../types'

export const authApi = {
  register: (username: string, display_name: string, password: string, email?: string) =>
    api.post<User>('/auth/register', { username, display_name, password, email: email || undefined }),

  login: (username: string, password: string) =>
    api.post<Token>('/auth/login', { username, password }),

  me: () => api.get<User>('/users/me'),
}
