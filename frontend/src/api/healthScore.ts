import { api } from './client'

export const healthScoreApi = {
  get: (projectId: string) => api.get<any>(`/projects/${projectId}/health`),
}
