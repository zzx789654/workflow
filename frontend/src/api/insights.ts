import { api } from './client'

export interface InsightsData {
  total_completed: number
  avg_completion_days: number
  completion_by_day: { date: string; count: number }[]
  busiest_hour: number
}

export const insightsApi = {
  getMe: () => api.get<InsightsData>('/insights/me'),
}
