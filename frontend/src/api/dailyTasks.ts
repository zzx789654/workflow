import { api } from './client'
import type { ArchiveHistoryResponse, DailyTask, DailyTaskStatus } from '../types'

export const dailyTasksApi = {
  list: (params?: { date?: string; label?: string; pending_only?: boolean }) =>
    api.get<DailyTask[]>('/daily-tasks/', { params }),

  get: (id: string) => api.get<DailyTask>(`/daily-tasks/${id}`),

  listByTask: (taskId: string) =>
    api.get<DailyTask[]>(`/daily-tasks/by-task/${taskId}`),

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
    linked_task_id?: string | null
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
    linked_task_id: string | null
  }>) => api.patch<DailyTask>(`/daily-tasks/${id}`, data),

  delete: (id: string) => api.delete(`/daily-tasks/${id}`),

  archivePreview: (data: {
    mode: 'done_immediately' | 'done_1month' | 'done_3months' | 'done_custom'
    before_date?: string
  }) => api.post<{ count: number; cutoff: string }>('/daily-tasks/archive/preview', data),

  archive: (data: {
    mode: 'done_immediately' | 'done_1month' | 'done_3months' | 'done_custom'
    before_date?: string
  }) => api.post<{ archived: number }>('/daily-tasks/archive', data),

  getArchiveHistory: (params?: { date_from?: string; date_to?: string; linked_task_id?: string }) =>
    api.get<ArchiveHistoryResponse>('/daily-tasks/archive/history', { params }),

  exportArchiveHistoryCsv: (params?: { date_from?: string; date_to?: string; linked_task_id?: string }) =>
    api.get('/daily-tasks/archive/history/export', { params, responseType: 'blob' }),

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
