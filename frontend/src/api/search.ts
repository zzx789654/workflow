import { api } from './client'

export interface SearchResult {
  type: 'project' | 'task' | 'daily'
  id: string
  title: string
  description: string | null
  project_id: string | null
  project_name: string | null
  status: string | null
  priority: string | null
}

export const searchApi = {
  search: (q: string, type = 'all') =>
    api.get<{ results: SearchResult[]; total: number }>('/search/', { params: { q, type } }),
}
