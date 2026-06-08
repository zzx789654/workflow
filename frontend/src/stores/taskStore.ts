import { create } from 'zustand'
import type { Task, TaskStatus, WsEvent } from '../types'
import { tasksApi } from '../api/tasks'


interface TaskState {
  tasks: Task[]
  loading: boolean
  wsConnected: boolean
  fetchTasks: (projectId: string) => Promise<void>
  moveTask: (projectId: string, taskId: string, status: TaskStatus, position: number) => Promise<void>
  createTask: (projectId: string, data: Parameters<typeof tasksApi.create>[1]) => Promise<void>
  deleteTask: (projectId: string, taskId: string) => Promise<void>
  applyWsEvent: (event: WsEvent, projectId: string) => void
  setWsConnected: (v: boolean) => void
}

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  loading: false,
  wsConnected: false,

  fetchTasks: async (projectId) => {
    set({ loading: true })
    try {
      const res = await tasksApi.list(projectId)
      set({ tasks: res.data })
    } finally {
      set({ loading: false })
    }
  },

  moveTask: async (projectId, taskId, status, position) => {
    set((s) => ({
      tasks: s.tasks.map((t) => t.id === taskId ? { ...t, status, position } : t),
    }))
    await tasksApi.move(projectId, taskId, status, position)
  },

  createTask: async (projectId, data) => {
    const res = await tasksApi.create(projectId, data)
    set((s) => ({ tasks: [...s.tasks, res.data] }))
  },

  deleteTask: async (projectId, taskId) => {
    await tasksApi.delete(projectId, taskId)
    set((s) => ({ tasks: s.tasks.filter((t) => t.id !== taskId) }))
  },

  applyWsEvent: (event, projectId) => {
    const { tasks } = get()
    if (event.type === 'task_moved') {
      set({
        tasks: tasks.map((t) =>
          t.id === event.task_id ? { ...t, status: event.status, position: event.position } : t
        ),
      })
    } else if (event.type === 'task_deleted') {
      set({ tasks: tasks.filter((t) => t.id !== event.task_id) })
    } else if (event.type === 'task_created' || event.type === 'task_updated' || event.type === 'comment_added') {
      tasksApi.list(projectId).then((res) => set({ tasks: res.data }))
    }
  },

  setWsConnected: (v) => set({ wsConnected: v }),
}))
