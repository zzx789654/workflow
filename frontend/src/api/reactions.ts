import { api } from './client'

export const reactionsApi = {
  list: (projectId: string, taskId: string, commentId: string) =>
    api.get<any[]>(`/projects/${projectId}/tasks/${taskId}/comments/${commentId}/reactions/`),
  toggle: (projectId: string, taskId: string, commentId: string, emoji: string) =>
    api.post<any>(`/projects/${projectId}/tasks/${taskId}/comments/${commentId}/reactions/toggle`, { emoji }),
}
