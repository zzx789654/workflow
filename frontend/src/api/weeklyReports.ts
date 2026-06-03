import { api } from './client'

export interface WeeklyReport {
  id: string
  week_start: string
  week_end: string
  completed_tasks: { id: string; title: string; project_id: string }[]
  delayed_tasks: { id: string; title: string; project_id: string }[]
  next_week_plan: string
  generated_at: string | null
}

export const weeklyReportsApi = {
  getCurrent: () => api.get<WeeklyReport>('/reports/current-week'),
  generate: () => api.post<WeeklyReport>('/reports/generate'),
}
