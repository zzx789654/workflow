import { api } from './client'
import type { Project, ProjectMember, ProjectOverviewItem } from '../types'

export const projectsApi = {
  list: () => api.get<Project[]>('/projects/'),
  listArchived: () => api.get<Project[]>('/projects/?archived=true'),
  overview: () => api.get<ProjectOverviewItem[]>('/projects/overview'),
  get: (id: string) => api.get<Project>(`/projects/${id}`),
  create: (data: { name: string; description?: string; color?: string; start_date?: string; end_date?: string }) =>
    api.post<Project>('/projects/', data),
  update: (id: string, data: Partial<{ name: string; description: string; color: string; is_archived: boolean; recurrence_rule: string | null; start_date: string; end_date: string }>) =>
    api.patch<Project>(`/projects/${id}`, data),
  applyDeadline: (id: string) => api.post(`/projects/${id}/apply-deadline`, {}),
  delete: (id: string) => api.delete(`/projects/${id}`),
  listMembers: (id: string) => api.get<ProjectMember[]>(`/projects/${id}/members`),
  addMember: (id: string, user_id: string, role: string) =>
    api.post<ProjectMember>(`/projects/${id}/members`, { user_id, role }),
  removeMember: (id: string, userId: string) => api.delete(`/projects/${id}/members/${userId}`),
}
