import { api } from './client'

export const checkinsApi = {
  list: (projectId: string, taskId: string) =>
    api.get<any[]>(`/projects/${projectId}/tasks/${taskId}/checkins/`),
  create: (projectId: string, taskId: string, content: string, progress: number) =>
    api.post<any>(`/projects/${projectId}/tasks/${taskId}/checkins/`, { content, progress }),
  stale: () => api.get<any>('/tasks/stale-checkins'),
}
