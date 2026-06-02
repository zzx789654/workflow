import { api } from './client'

export interface DashboardSummary {
  kpi: {
    todo: number
    overdue: number
    completed_this_week: number
  }
  trend: { date: string; count: number }[]
  action_required: {
    id: string
    title: string
    status: string
    priority: string
    due_date: string | null
    project_id: string
  }[]
}

export const dashboardApi = {
  summary: () => api.get<DashboardSummary>('/dashboard/summary'),
}
