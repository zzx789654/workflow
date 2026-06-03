import { api } from './client'
import type { ProjectTemplate, Project } from '../types'

export const templatesApi = {
  list: () => api.get<ProjectTemplate[]>('/project-templates/'),

  get: (id: string) => api.get<ProjectTemplate>(`/project-templates/${id}`),

  create: (data: {
    name: string
    description?: string
    color?: string
    tasks?: Array<{
      title: string
      description?: string
      priority?: string
      day_offset_start?: number
      day_offset_end?: number
      position?: number
    }>
  }) => api.post<ProjectTemplate>('/project-templates/', data),

  update: (id: string, data: Partial<{ name: string; description: string; color: string }>) =>
    api.patch<ProjectTemplate>(`/project-templates/${id}`, data),

  replaceTasks: (id: string, tasks: Array<{
    title: string; description?: string; priority?: string
    day_offset_start: number; day_offset_end?: number; position?: number
  }>) => api.put<ProjectTemplate>(`/project-templates/${id}/tasks`, tasks),

  delete: (id: string) => api.delete(`/project-templates/${id}`),

  apply: (id: string, data: { project_name: string; project_description?: string; start_date?: string }) =>
    api.post<Project>(`/project-templates/${id}/apply`, data),

  createFromProject: (projectId: string, name: string) =>
    api.post<ProjectTemplate>(`/project-templates/from-project/${projectId}`, null, { params: { name } }),
}
