import { api } from './client'
import type { User, Token } from '../types'

export const authApi = {
  register: (email: string, display_name: string, password: string) =>
    api.post<User>('/auth/register', { email, display_name, password }),

  login: (email: string, password: string) =>
    api.post<Token>('/auth/login', { email, password }),

  me: () => api.get<User>('/users/me'),
}
