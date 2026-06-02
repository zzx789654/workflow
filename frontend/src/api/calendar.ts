import { api } from './client'
import type { CalendarEvent } from '../types'

export const calendarApi = {
  getEvents: (year: number, month: number, label?: string) =>
    api.get<CalendarEvent[]>('/calendar/', { params: { year, month, label } }),
}
