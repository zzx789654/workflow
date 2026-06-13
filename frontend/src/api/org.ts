import { api } from './client'
import type { OrgUnit, AdSyncResult } from '../types'

export const orgApi = {
  list: () => api.get<OrgUnit[]>('/org-units/'),
  syncAd: () => api.post<AdSyncResult>('/org-units/sync-ad'),
  create: (data: { name: string; parent_id?: string | null; manager_user_id?: string | null }) =>
    api.post<OrgUnit>('/org-units/', data),
  update: (
    id: string,
    data: { name?: string; parent_id?: string | null; manager_user_id?: string | null },
  ) => api.patch<OrgUnit>(`/org-units/${id}`, data),
  remove: (id: string) => api.delete(`/org-units/${id}`),
}
