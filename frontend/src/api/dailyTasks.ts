import { api } from './client'
import type { DailyTask, DailyTaskStatus } from '../types'

export const dailyTasksApi = {
  list: (params?: { date?: string; label?: string }) =>
    api.get<DailyTask[]>('/daily-tasks/', { params }),

  get: (id: string) => api.get<DailyTask>(`/daily-tasks/${id}`),

  create: (data: {
    title: string
    description?: string
    status?: DailyTaskStatus
    progress?: number
    date: string
    started_at?: string
    ended_at?: string
    notify_at?: string
    work_minutes?: number
    labels?: string[]
  }) => api.post<DailyTask>('/daily-tasks/', data),

  update: (id: string, data: Partial<{
    title: string
    description: string
    status: DailyTaskStatus
    progress: number
    date: string
    started_at: string | null
    ended_at: string | null
    notify_at: string | null
    work_minutes: number
    labels: string[]
  }>) => api.patch<DailyTask>(`/daily-tasks/${id}`, data),

  delete: (id: string) => api.delete(`/daily-tasks/${id}`),

  downloadTemplate: () =>
    api.get('/daily-tasks/import/template', { responseType: 'blob' }),

  importExcel: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<{ created: number; errors: string[]; total_rows: number }>(
      '/daily-tasks/import/excel',
      form,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
  },
}
