import { useState } from 'react'
import type { Task, TaskStatus, TaskPriority } from '../../types'
import { api } from '../../api/client'

interface Props {
  tasks: Task[]
  projectId: string
  onUpdate?: () => void
}

const STATUS_OPTS: { value: TaskStatus; label: string }[] = [
  { value: 'todo', label: '待辦' },
  { value: 'in_progress', label: '進行中' },
  { value: 'review', label: '審查中' },
  { value: 'done', label: '完成' },
]

const PRIORITY_OPTS: { value: TaskPriority; label: string }[] = [
  { value: 'urgent', label: '緊急' },
  { value: 'high', label: '高' },
  { value: 'medium', label: '中' },
  { value: 'low', label: '低' },
]

const STATUS_COLOR: Record<TaskStatus, string> = {
  todo: 'bg-gray-100 text-gray-600',
  in_progress: 'bg-blue-100 text-blue-700',
  review: 'bg-yellow-100 text-yellow-700',
  done: 'bg-green-100 text-green-700',
}

const PRIORITY_COLOR: Record<TaskPriority, string> = {
  urgent: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  medium: 'bg-blue-100 text-blue-700',
  low: 'bg-gray-100 text-gray-500',
}

export default function TableView({ tasks, projectId, onUpdate }: Props) {
  const [editing, setEditing] = useState<{ taskId: string; field: string } | null>(null)
  const [saving, setSaving] = useState<string | null>(null)

  const handleChange = async (taskId: string, field: string, value: string) => {
    setSaving(taskId)
    setEditing(null)
    try {
      await api.patch(`/projects/${projectId}/tasks/${taskId}`, { [field]: value })
      onUpdate?.()
    } catch {
      // silently ignore
    } finally {
      setSaving(null)
    }
  }

  if (tasks.length === 0) {
    return <div className="text-center py-16 text-gray-400">目前無任務</div>
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="text-left px-4 py-3 font-medium text-gray-600 w-1/2">任務名稱</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600 w-28">狀態</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600 w-24">優先度</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600 w-28">截止日</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">指派人</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {tasks.map((task) => (
            <tr key={task.id} className={`hover:bg-gray-50 ${saving === task.id ? 'opacity-50' : ''}`}>
              <td className="px-4 py-3 text-gray-900 font-medium">{task.title}</td>
              <td className="px-4 py-3" onClick={() => setEditing({ taskId: task.id, field: 'status' })}>
                {editing?.taskId === task.id && editing.field === 'status' ? (
                  <select
                    autoFocus
                    defaultValue={task.status}
                    onBlur={(e) => handleChange(task.id, 'status', e.target.value)}
                    onChange={(e) => handleChange(task.id, 'status', e.target.value)}
                    className="text-xs border rounded px-1 py-0.5"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {STATUS_OPTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                ) : (
                  <span className={`text-xs px-2 py-0.5 rounded-full cursor-pointer ${STATUS_COLOR[task.status]}`}>
                    {STATUS_OPTS.find((o) => o.value === task.status)?.label}
                  </span>
                )}
              </td>
              <td className="px-4 py-3" onClick={() => setEditing({ taskId: task.id, field: 'priority' })}>
                {editing?.taskId === task.id && editing.field === 'priority' ? (
                  <select
                    autoFocus
                    defaultValue={task.priority}
                    onBlur={(e) => handleChange(task.id, 'priority', e.target.value)}
                    onChange={(e) => handleChange(task.id, 'priority', e.target.value)}
                    className="text-xs border rounded px-1 py-0.5"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {PRIORITY_OPTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                ) : (
                  <span className={`text-xs px-2 py-0.5 rounded-full cursor-pointer ${PRIORITY_COLOR[task.priority]}`}>
                    {PRIORITY_OPTS.find((o) => o.value === task.priority)?.label}
                  </span>
                )}
              </td>
              <td className="px-4 py-3 text-gray-500 text-xs">{task.due_date ?? '—'}</td>
              <td className="px-4 py-3">
                <div className="flex gap-1">
                  {task.assignees.slice(0, 3).map((u) => (
                    <div key={u.id} title={u.display_name}
                      className="w-6 h-6 rounded-full bg-primary-500 text-white text-xs flex items-center justify-center">
                      {u.display_name.charAt(0)}
                    </div>
                  ))}
                  {task.assignees.length > 3 && <span className="text-xs text-gray-400">+{task.assignees.length - 3}</span>}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
