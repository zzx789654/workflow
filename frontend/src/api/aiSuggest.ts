import { api } from './client'

export interface AiSuggestion {
  task_id: string
  title: string
  project_id: string
  score: number
  reason: string
}

export const aiSuggestApi = {
  get: () => api.get<AiSuggestion[]>('/dashboard/ai-suggest'),
}
