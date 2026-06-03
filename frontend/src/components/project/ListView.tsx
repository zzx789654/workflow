import React, { useState } from 'react'
import type { Task, TaskStatus, TaskPriority } from '../../types'

interface Props {
  tasks: Task[]
  onTaskClick: (task: Task) => void
}

type SortKey = 'title' | 'status' | 'priority' | 'due_date' | 'assignees'
type SortDir = 'asc' | 'desc'

const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: '待辦',
  in_progress: '進行中',
  review: '審查中',
  done: '完成',
}

const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: '低',
  medium: '中',
  high: '高',
  urgent: '緊急',
}

const STATUS_ORDER: Record<TaskStatus, number> = {
  todo: 0,
  in_progress: 1,
  review: 2,
  done: 3,
}

const PRIORITY_ORDER: Record<TaskPriority, number> = {
  low: 0,
  medium: 1,
  high: 2,
  urgent: 3,
}

const STATUS_COLOR: Record<TaskStatus, string> = {
  todo: 'bg-gray-100 text-gray-600',
  in_progress: 'bg-blue-100 text-blue-700',
  review: 'bg-purple-100 text-purple-700',
  done: 'bg-green-100 text-green-700',
}

const PRIORITY_COLOR: Record<TaskPriority, string> = {
  low: 'bg-gray-100 text-gray-500',
  medium: 'bg-blue-100 text-blue-700',
  high: 'bg-orange-100 text-orange-700',
  urgent: 'bg-red-100 text-red-700',
}

export default function ListView({ tasks, onTaskClick }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('title')
  const [sortDir, setSortDir] = useState<SortDir>('asc')

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  const sorted = [...tasks].sort((a, b) => {
    let cmp = 0
    switch (sortKey) {
      case 'title':
        cmp = a.title.localeCompare(b.title, 'zh-TW')
        break
      case 'status':
        cmp = STATUS_ORDER[a.status] - STATUS_ORDER[b.status]
        break
      case 'priority':
        cmp = PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]
        break
      case 'due_date': {
        const da = a.due_date ?? '9999-99-99'
        const db = b.due_date ?? '9999-99-99'
        cmp = da.localeCompare(db)
        break
      }
      case 'assignees':
        cmp = (a.assignees[0]?.display_name ?? '').localeCompare(
          b.assignees[0]?.display_name ?? '',
          'zh-TW'
        )
        break
    }
    return sortDir === 'asc' ? cmp : -cmp
  })

  const SortIcon = ({ col }: { col: SortKey }) => {
    if (sortKey !== col) return <span className="text-gray-300 ml-1">↕</span>
    return <span className="text-indigo-500 ml-1">{sortDir === 'asc' ? '↑' : '↓'}</span>
  }

  const thClass =
    'px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 select-none whitespace-nowrap'

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200 bg-white rounded-lg shadow">
        <thead className="bg-gray-50">
          <tr>
            <th className={thClass} onClick={() => handleSort('title')}>
              任務名稱<SortIcon col="title" />
            </th>
            <th className={thClass} onClick={() => handleSort('status')}>
              狀態<SortIcon col="status" />
            </th>
            <th className={thClass} onClick={() => handleSort('priority')}>
              優先度<SortIcon col="priority" />
            </th>
            <th className={thClass} onClick={() => handleSort('due_date')}>
              截止日<SortIcon col="due_date" />
            </th>
            <th className={thClass} onClick={() => handleSort('assignees')}>
              指派人<SortIcon col="assignees" />
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {sorted.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-4 py-10 text-center text-sm text-gray-400">
                尚無任務
              </td>
            </tr>
          ) : (
            sorted.map((task) => (
              <tr
                key={task.id}
                className="hover:bg-gray-50 cursor-pointer transition-colors"
                onClick={() => onTaskClick(task)}
              >
                <td className="px-4 py-3 text-sm font-medium text-gray-900 max-w-xs truncate">
                  {task.title}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLOR[task.status]}`}
                  >
                    {STATUS_LABELS[task.status]}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium ${PRIORITY_COLOR[task.priority]}`}
                  >
                    {PRIORITY_LABELS[task.priority]}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-500 whitespace-nowrap">
                  {task.due_date ?? '—'}
                </td>
                <td className="px-4 py-3">
                  {task.assignees.length === 0 ? (
                    <span className="text-sm text-gray-400">—</span>
                  ) : (
                    <div className="flex items-center gap-1">
                      {task.assignees.slice(0, 3).map((u) => (
                        <div
                          key={u.id}
                          className="w-6 h-6 rounded-full bg-indigo-500 text-white text-xs flex items-center justify-center flex-shrink-0"
                          title={u.display_name}
                        >
                          {u.display_name.charAt(0)}
                        </div>
                      ))}
                      {task.assignees.length > 3 && (
                        <span className="text-xs text-gray-400">
                          +{task.assignees.length - 3}
                        </span>
                      )}
                    </div>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
