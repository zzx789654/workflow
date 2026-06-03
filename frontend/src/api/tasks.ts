import { api } from './client'
import type { Task, TaskComment, TaskStatus } from '../types'

export const tasksApi = {
  list: (projectId: string) => api.get<Task[]>(`/projects/${projectId}/tasks/`),
  get: (projectId: string, taskId: string) => api.get<Task>(`/projects/${projectId}/tasks/${taskId}`),
  create: (projectId: string, data: {
    title: string; description?: string; status?: TaskStatus
    priority?: string; milestone_id?: string; due_date?: string
    start_date?: string; end_date?: string; assignee_ids?: string[]
    recurrence_rule?: string; recurrence_end_date?: string
  }) => api.post<Task>(`/projects/${projectId}/tasks/`, data),
  update: (projectId: string, taskId: string, data: Partial<Task & { assignee_ids: string[] }>) =>
    api.patch<Task>(`/projects/${projectId}/tasks/${taskId}`, data),
  move: (projectId: string, taskId: string, status: TaskStatus, position: number) =>
    api.patch<Task>(`/projects/${projectId}/tasks/${taskId}/move`, { status, position }),
  delete: (projectId: string, taskId: string) => api.delete(`/projects/${projectId}/tasks/${taskId}`),
  addComment: (projectId: string, taskId: string, content: string) =>
    api.post<TaskComment>(`/projects/${projectId}/tasks/${taskId}/comments`, { content }),
}
