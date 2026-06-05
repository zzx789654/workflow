import { api } from './client'

export interface WebhookOut {
  id: string
  project_id: string
  name: string
  url: string
  events: string[]
  is_active: boolean
  last_triggered_at: string | null
  created_at: string
}

export interface WebhookCreate {
  name: string
  url: string
  secret?: string
  events: string[]
}

export const webhooksApi = {
  list: (projectId: string) =>
    api.get<WebhookOut[]>(`/projects/${projectId}/webhooks/`),
  create: (projectId: string, data: WebhookCreate) =>
    api.post<WebhookOut>(`/projects/${projectId}/webhooks/`, data),
  delete: (projectId: string, webhookId: string) =>
    api.delete(`/projects/${projectId}/webhooks/${webhookId}`),
}
