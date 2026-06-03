import { api } from './client'

export interface Attachment {
  id: string
  filename: string
  content_type: string
  size: number
  url: string
  created_at: string
}

export const attachmentsApi = {
  list: (project_id: string, task_id: string) =>
    api.get<Attachment[]>(`/projects/${project_id}/tasks/${task_id}/attachments`),
  upload: (project_id: string, task_id: string, formData: FormData) =>
    api.post<Attachment>(`/projects/${project_id}/tasks/${task_id}/attachments`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  delete: (project_id: string, task_id: string, id: string) =>
    api.delete(`/projects/${project_id}/tasks/${task_id}/attachments/${id}`),
}
