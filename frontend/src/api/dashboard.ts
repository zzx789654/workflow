import { api } from './client'

export interface DashboardTask {
  id: string
  title: string
  status: string
  priority: string
  due_date: string | null
  project_id: string | null
  project_name: string | null
  item_type: 'task' | 'daily'
  work_minutes?: number
}

export interface DeadlineProject {
  id: string
  name: string
  color: string
  end_date: string
  days_left: number
  task_total: number
  task_done: number
}

export interface DashboardSummary {
  kpi: {
    todo: number
    overdue: number
    completed_this_week: number
  }
  today_due: DashboardTask[]
  action_required: DashboardTask[]
  upcoming: DashboardTask[]
  deadline_projects: DeadlineProject[]
}

export const dashboardApi = {
  summary: () => api.get<DashboardSummary>('/dashboard/summary'),
}
