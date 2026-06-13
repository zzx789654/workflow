import { useState } from 'react'
import type { Task, TaskStatus } from '../../types'
import { api } from '../../api/client'
import { useTaskStore } from '../../stores/taskStore'

interface Props {
  tasks: Task[]
  projectId: string
  onSelect: (task: Task) => void
}

const STATUS_COLORS: Record<string, string> = {
  todo: 'bg-gray-100 text-gray-600',
  in_progress: 'bg-blue-100 text-blue-700',
  review: 'bg-yellow-100 text-yellow-700',
  done: 'bg-green-100 text-green-700',
}
const PRIORITY_LABELS: Record<string, string> = {
  low: '低', medium: '中', high: '高', urgent: '緊急'
}
const PRIORITY_COLORS: Record<string, string> = {
  urgent: 'text-red-600', high: 'text-orange-500', medium: 'text-yellow-500', low: 'text-gray-400'
}

export default function TaskListView({ tasks, projectId, onSelect }: Props) {
  const [sortBy, setSortBy] = useState<'priority' | 'due_date' | 'status'>('priority')
  const fetchTasks = useTaskStore(s => s.fetchTasks)

  const sortFn = (a: Task, b: Task) => {
    if (sortBy === 'priority') {
      const ord = { urgent: 0, high: 1, medium: 2, low: 3 }
      return (ord[a.priority as keyof typeof ord] ?? 4) - (ord[b.priority as keyof typeof ord] ?? 4)
    }
    if (sortBy === 'due_date') {
      return (a.due_date ?? '9999') < (b.due_date ?? '9999') ? -1 : 1
    }
    return a.status.localeCompare(b.status)
  }

  // Build tree: top-level tasks sorted, each with sorted children
  const childMap = new Map<string, Task[]>()
  const roots: Task[] = []
  for (const t of tasks) {
    if (t.parent_task_id) {
      const arr = childMap.get(t.parent_task_id) ?? []
      arr.push(t)
      childMap.set(t.parent_task_id, arr)
    } else {
      roots.push(t)
    }
  }
  roots.sort(sortFn)
  childMap.forEach(v => v.sort(sortFn))

  // Flatten in tree order: [parent, ...children, next parent, ...]
  const treeRows: { task: Task; depth: number }[] = []
  const flatten = (t: Task, depth: number) => {
    treeRows.push({ task: t, depth })
    const children = childMap.get(t.id) ?? []
    for (const c of children) flatten(c, depth + 1)
  }
  for (const r of roots) flatten(r, 0)

  const handleStatusChange = async (task: Task, status: TaskStatus) => {
    await api.patch(`/projects/${projectId}/tasks/${task.id}`, { status })
    await fetchTasks(projectId)
  }

  return (
    <div>
      {/* Sort controls */}
      <div className="flex items-center gap-2 mb-3 text-sm">
        <span className="text-xs text-gray-500">排序：</span>
        {(['priority', 'due_date', 'status'] as const).map(key => (
          <button
            key={key}
            onClick={() => setSortBy(key)}
            className={`px-2 py-1 rounded text-xs ${sortBy === key ? 'bg-primary-100 text-primary-700 font-medium' : 'text-gray-500 hover:bg-gray-100'}`}
          >
            {{ priority: '優先度', due_date: '截止日', status: '狀態' }[key]}
          </button>
        ))}
      </div>

      {/* Task list */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        {/* Column header */}
        <div className="hidden sm:flex items-center gap-3 px-4 py-2 border-b border-gray-100 bg-gray-50 text-xs text-gray-400 font-medium">
          <div className="flex-1">任務</div>
          <div className="w-16 text-center flex-shrink-0">優先度</div>
          <div className="w-28 flex-shrink-0">負責人</div>
          <div className="w-24 flex-shrink-0">截止日</div>
          <div className="w-28 flex-shrink-0">狀態</div>
        </div>

        {treeRows.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">無任務</div>
        ) : (
          treeRows.map(({ task: t, depth }) => (
            <div
              key={t.id}
              className="flex items-center gap-3 px-4 py-3 border-b border-gray-100 last:border-0 hover:bg-gray-50 transition-colors"
              style={{ paddingLeft: depth > 0 ? `${(depth * 20) + 16}px` : undefined }}
            >
              {/* Title */}
              <button className="flex-1 text-left min-w-0" onClick={() => onSelect(t)}>
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`text-sm font-medium ${t.status === 'done' ? 'line-through text-gray-400' : 'text-gray-800'} truncate`}>
                    {t.title}
                  </span>
                  {t.subtask_count > 0 && (
                    <span className="text-xs text-gray-400 flex-shrink-0">{t.subtask_done_count}/{t.subtask_count}</span>
                  )}
                  {t.attachment_count > 0 && (
                    <span className="text-xs text-gray-400 flex-shrink-0">📎 {t.attachment_count}</span>
                  )}
                </div>
              </button>

              {/* Priority */}
              <span className={`hidden sm:block text-xs font-medium flex-shrink-0 w-16 text-center ${PRIORITY_COLORS[t.priority]}`}>
                {PRIORITY_LABELS[t.priority]}
              </span>

              {/* Assignees */}
              <div className="hidden sm:flex items-center gap-1 w-28 flex-shrink-0 min-w-0">
                {t.assignees.length === 0 ? (
                  <span className="text-xs text-gray-300">—</span>
                ) : (
                  <>
                    {t.assignees.slice(0, 2).map(u => (
                      <span
                        key={u.id}
                        title={u.display_name}
                        className="w-6 h-6 rounded-full bg-primary-100 text-primary-600 text-[10px] font-bold flex items-center justify-center flex-shrink-0"
                      >
                        {u.display_name.charAt(0).toUpperCase()}
                      </span>
                    ))}
                    {t.assignees.length > 0 && (
                      <span className="text-xs text-gray-500 truncate ml-1">
                        {t.assignees[0].display_name.split(' ')[0]}
                        {t.assignees.length > 1 ? ` +${t.assignees.length - 1}` : ''}
                      </span>
                    )}
                  </>
                )}
              </div>

              {/* Due date */}
              <span className="hidden sm:block text-xs text-gray-400 flex-shrink-0 w-24">
                {t.due_date ?? '—'}
              </span>

              {/* Status inline dropdown */}
              <div className="flex-shrink-0 w-28" onClick={e => e.stopPropagation()}>
                <select
                  value={t.status}
                  onChange={e => handleStatusChange(t, e.target.value as TaskStatus)}
                  className={`text-xs px-2 py-1 rounded-full font-medium cursor-pointer w-full border-0 outline-none ${STATUS_COLORS[t.status]}`}
                >
                  <option value="todo">待辦</option>
                  <option value="in_progress">進行中</option>
                  <option value="review">審查中</option>
                  <option value="done">完成</option>
                </select>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
