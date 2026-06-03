import { api } from './client'
import type { TaskDependency } from '../types'

export const dependenciesApi = {
  list: (projectId: string, taskId: string) =>
    api.get<TaskDependency[]>(`/projects/${projectId}/tasks/${taskId}/dependencies/`),
  add: (projectId: string, taskId: string, toTaskId: string, depType = 'finish_to_start') =>
    api.post<TaskDependency>(`/projects/${projectId}/tasks/${taskId}/dependencies/`, {
      to_task_id: toTaskId,
      dep_type: depType,
    }),
  remove: (projectId: string, taskId: string, depId: string) =>
    api.delete(`/projects/${projectId}/tasks/${taskId}/dependencies/${depId}`),
}
