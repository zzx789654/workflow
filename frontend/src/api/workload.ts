import { api } from './client'

export const workloadApi = {
  get: (period: 'week' | 'month' = 'week', projectId?: string) => {
    const params = new URLSearchParams({ period })
    if (projectId) params.set('project_id', projectId)
    return api.get<any>(`/workload?${params}`)
  },
}
