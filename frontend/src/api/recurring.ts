import { api } from './client'

export type RecurrenceRule = 'daily' | 'weekly' | 'monthly'

export const recurringApi = {
  set: (projectId: string, taskId: string, rule: RecurrenceRule) =>
    api.put(`/projects/${projectId}/tasks/${taskId}/recurrence`, { rule }),
  remove: (projectId: string, taskId: string) =>
    api.delete(`/projects/${projectId}/tasks/${taskId}/recurrence`),
  spawnNext: (projectId: string, taskId: string) =>
    api.post(`/projects/${projectId}/tasks/${taskId}/recurrence/spawn`, {}),
}
