import { api } from './client'
import type { MilestoneLog } from '../types'

export const milestonesApi = {
  list: (projectId: string) =>
    api.get<MilestoneLog[]>(`/projects/${projectId}/milestones/`),

  update: (projectId: string, logId: string, data: { work_minutes?: number; note?: string }) =>
    api.patch<MilestoneLog>(`/projects/${projectId}/milestones/${logId}`, data),

  delete: (projectId: string, logId: string) =>
    api.delete(`/projects/${projectId}/milestones/${logId}`),
}
