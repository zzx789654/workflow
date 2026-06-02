import { api } from './client'
import type { TimeLog } from '../types'

export const timeLogsApi = {
  list: (projectId: string, taskId: string) =>
    api.get<TimeLog[]>(`/projects/${projectId}/tasks/${taskId}/time-logs/`),
  start: (projectId: string, taskId: string, note?: string) =>
    api.post<TimeLog>(`/projects/${projectId}/tasks/${taskId}/time-logs/start`, { note }),
  stop: (projectId: string, taskId: string, logId: string) =>
    api.patch<TimeLog>(`/projects/${projectId}/tasks/${taskId}/time-logs/${logId}/stop`),
  manual: (projectId: string, taskId: string, minutes: number, note?: string) =>
    api.post<TimeLog>(`/projects/${projectId}/tasks/${taskId}/time-logs/manual`, { minutes, note }),
  delete: (projectId: string, taskId: string, logId: string) =>
    api.delete(`/projects/${projectId}/tasks/${taskId}/time-logs/${logId}`),
}
