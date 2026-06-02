import { api } from './client'
import type { Project, ProjectMember } from '../types'

export const projectsApi = {
  list: () => api.get<Project[]>('/projects/'),
  get: (id: string) => api.get<Project>(`/projects/${id}`),
  create: (data: { name: string; description?: string; color?: string }) =>
    api.post<Project>('/projects/', data),
  update: (id: string, data: Partial<{ name: string; description: string; color: string; is_archived: boolean }>) =>
    api.patch<Project>(`/projects/${id}`, data),
  delete: (id: string) => api.delete(`/projects/${id}`),
  listMembers: (id: string) => api.get<ProjectMember[]>(`/projects/${id}/members`),
  addMember: (id: string, user_id: string, role: string) =>
    api.post<ProjectMember>(`/projects/${id}/members`, { user_id, role }),
  removeMember: (id: string, userId: string) => api.delete(`/projects/${id}/members/${userId}`),
}
