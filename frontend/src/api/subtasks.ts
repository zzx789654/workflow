import { api } from './client'
import type { SubTask } from '../types'

export const subtasksApi = {
  list: (projectId: string, taskId: string) =>
    api.get<SubTask[]>(`/projects/${projectId}/tasks/${taskId}/subtasks/`),
  create: (projectId: string, taskId: string, title: string, description?: string) =>
    api.post<SubTask>(`/projects/${projectId}/tasks/${taskId}/subtasks/`, { title, description }),
  update: (projectId: string, taskId: string, subtaskId: string, data: Partial<SubTask>) =>
    api.patch<SubTask>(`/projects/${projectId}/tasks/${taskId}/subtasks/${subtaskId}`, data),
  delete: (projectId: string, taskId: string, subtaskId: string) =>
    api.delete(`/projects/${projectId}/tasks/${taskId}/subtasks/${subtaskId}`),
}
