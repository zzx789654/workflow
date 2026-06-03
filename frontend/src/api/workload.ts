import { api } from './client'

export interface WorkloadMember {
  user_id: string
  display_name: string
  task_count: number
  total_minutes: number
  is_overloaded: boolean
}

export interface WorkloadData {
  members: WorkloadMember[]
}

export type WorkloadPeriod = 'week' | 'month'

export const workloadApi = {
  get: (period: WorkloadPeriod) =>
    api.get<WorkloadData>('/workload/', { params: { period } }),
}
