import { api } from './client'

export const aiAssistApi = {
  getSuggestions: () => api.get<any>('/ai/priority-suggestions'),
}
