import { api } from './client'

export interface HealthScoreData {
  score: number
  details: {
    overdue_ratio: number
    milestone_rate: number
    activity_score: number
  }
}

export const healthScoreApi = {
  get: (project_id: string) =>
    api.get<HealthScoreData>(`/projects/${project_id}/health-score`),
}
