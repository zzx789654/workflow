import { api } from './client'
import type { Milestone, MilestoneStatus } from '../types'

export const milestonesApi = {
  list: (projectId: string) => api.get<Milestone[]>(`/projects/${projectId}/milestones/`),
  create: (projectId: string, data: { name: string; description?: string; due_date?: string; status?: MilestoneStatus }) =>
    api.post<Milestone>(`/projects/${projectId}/milestones/`, data),
  update: (projectId: string, id: string, data: Partial<Milestone>) =>
    api.patch<Milestone>(`/projects/${projectId}/milestones/${id}`, data),
  delete: (projectId: string, id: string) => api.delete(`/projects/${projectId}/milestones/${id}`),
}
