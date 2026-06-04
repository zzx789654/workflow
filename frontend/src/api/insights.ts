import { api } from './client'

export const insightsApi = {
  get: () => api.get<any>('/insights'),
}
