import { api } from './client'
import type { ProjectField, FieldValue } from '../types'

export const customFieldsApi = {
  listFields: (projectId: string) =>
    api.get<ProjectField[]>(`/projects/${projectId}/fields`),
  createField: (projectId: string, data: { name: string; field_type: string; options?: string[] }) =>
    api.post<ProjectField>(`/projects/${projectId}/fields`, data),
  deleteField: (projectId: string, fieldId: string) =>
    api.delete(`/projects/${projectId}/fields/${fieldId}`),
  getFieldValues: (projectId: string, taskId: string) =>
    api.get<FieldValue[]>(`/projects/${projectId}/tasks/${taskId}/field-values`),
  setFieldValues: (projectId: string, taskId: string, values: { field_id: string; value: string | null }[]) =>
    api.put(`/projects/${projectId}/tasks/${taskId}/field-values`, values),
}
