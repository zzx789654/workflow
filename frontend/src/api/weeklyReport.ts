import { api } from './client'

export const weeklyReportApi = {
  get: () => api.get<any>('/weekly-report'),
}
