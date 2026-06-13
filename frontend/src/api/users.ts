import { api } from './client'
import type { User, CalendarGrant } from '../types'

export const usersApi = {
  me: () => api.get<User>('/users/me'),

  updateMe: (data: { display_name?: string; avatar_url?: string | null; auto_archive_days?: number }) =>
    api.patch<User>('/users/me', data),

  list: () => api.get<User[]>('/users/'),

  // admin：維護使用者組織歸屬與職位
  updateOrg: (
    userId: string,
    data: { org_unit_id?: string | null; position?: string | null; set_org_unit?: boolean; set_position?: boolean },
  ) => api.patch<User>(`/users/${userId}/org`, data),

  // admin：日曆額外授權
  listGrants: (userId: string) => api.get<CalendarGrant[]>(`/users/${userId}/calendar-grants`),
  addGrant: (userId: string, orgUnitId: string) =>
    api.post<CalendarGrant>(`/users/${userId}/calendar-grants`, { org_unit_id: orgUnitId }),
  removeGrant: (userId: string, grantId: string) =>
    api.delete(`/users/${userId}/calendar-grants/${grantId}`),
}
