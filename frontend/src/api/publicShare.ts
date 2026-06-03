import axios from 'axios'
import { api } from './client'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export interface PublicTask {
  id: string
  title: string
  status: string
  priority: string
  due_date: string | null
}

export interface PublicProject {
  id: string
  name: string
  description: string | null
  tasks: PublicTask[]
}

export interface ShareLink {
  token: string
  url: string
  created_at: string
}

export const publicShareApi = {
  getPublic: (token: string) =>
    axios.get<PublicProject>(`${API_BASE}/api/v1/public/projects/${token}`),
  create: (project_id: string) =>
    api.post<ShareLink>(`/projects/${project_id}/share`),
  get: (project_id: string) =>
    api.get<ShareLink>(`/projects/${project_id}/share`),
}
