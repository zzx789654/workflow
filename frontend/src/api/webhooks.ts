import { api } from './client'

export interface Webhook {
  id: string
  project_id: string
  url: string
  events: string[]
  is_active: boolean
  created_at: string
}

export const webhooksApi = {
  list: (projectId: string) => api.get<Webhook[]>(`/projects/${projectId}/webhooks`),
  create: (projectId: string, data: { url: string; events: string[]; is_active?: boolean }) =>
    api.post<Webhook>(`/projects/${projectId}/webhooks`, data),
  update: (projectId: string, id: string, data: Partial<{ url: string; events: string[]; is_active: boolean }>) =>
    api.patch<Webhook>(`/projects/${projectId}/webhooks/${id}`, data),
  delete: (projectId: string, id: string) =>
    api.delete(`/projects/${projectId}/webhooks/${id}`),
  test: (projectId: string, id: string) =>
    api.post<{ success: boolean; status_code: number | null; detail: string }>(`/projects/${projectId}/webhooks/${id}/test`),
}
