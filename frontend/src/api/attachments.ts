import { api } from './client'

export const attachmentsApi = {
  list: (projectId: string, taskId: string) =>
    api.get<any[]>(`/projects/${projectId}/tasks/${taskId}/attachments/`),
  upload: (projectId: string, taskId: string, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return api.post<any>(`/projects/${projectId}/tasks/${taskId}/attachments/`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  downloadUrl: (projectId: string, taskId: string, attachmentId: string) =>
    `/api/v1/projects/${projectId}/tasks/${taskId}/attachments/${attachmentId}/download`,
  delete: (projectId: string, taskId: string, attachmentId: string) =>
    api.delete(`/projects/${projectId}/tasks/${taskId}/attachments/${attachmentId}`),
}
