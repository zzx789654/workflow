import { api } from './client'

export interface Checkin {
  id: string
  content: string
  progress: number
  created_at: string
  user_id: string
}

export const checkinsApi = {
  list: (project_id: string, task_id: string) =>
    api.get<Checkin[]>(`/projects/${project_id}/tasks/${task_id}/checkins`),
  create: (project_id: string, task_id: string, body: { content: string; progress: number }) =>
    api.post<Checkin>(`/projects/${project_id}/tasks/${task_id}/checkins`, body),
}
