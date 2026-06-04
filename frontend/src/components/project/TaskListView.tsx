import { useState } from 'react'
import type { Task } from '../../types'
import { api } from '../../api/client'
import { useTaskStore } from '../../stores/taskStore'

interface Props {
  tasks: Task[]
  projectId: string
  onSelect: (task: Task) => void
}

const STATUS_LABELS: Record<string, string> = {
  todo: '待辦', in_progress: '進行中', review: '審查中', done: '完成'
}
const PRIORITY_LABELS: Record<string, string> = {
  low: '低', medium: '中', high: '高', urgent: '緊急'
}
const PRIORITY_COLORS: Record<string, string> = {
  urgent: 'text-red-600', high: 'text-orange-500', medium: 'text-yellow-500', low: 'text-gray-400'
}

export default function TaskListView({ tasks, projectId, onSelect }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [sortBy, setSortBy] = useState<'priority' | 'due_date' | 'status'>('priority')
  const [bulkStatus, setBulkStatus] = useState('')
  const [undoAction, setUndoAction] = useState<null | { ids: string[]; prevStatuses: Record<string, string> }>(null)
  const [undoTimeout, setUndoTimeout] = useState<ReturnType<typeof setTimeout> | null>(null)
  const fetchTasks = useTaskStore(s => s.fetchTasks)

  const sorted = [...tasks].sort((a, b) => {
    if (sortBy === 'priority') {
      const ord = { urgent: 0, high: 1, medium: 2, low: 3 }
      return (ord[a.priority as keyof typeof ord] ?? 4) - (ord[b.priority as keyof typeof ord] ?? 4)
    }
    if (sortBy === 'due_date') {
      return (a.due_date ?? '9999') < (b.due_date ?? '9999') ? -1 : 1
    }
    return a.status.localeCompare(b.status)
  })

  const toggleSelect = (id: string) => {
    setSelected(s => {
      const n = new Set(s)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  }

  const handleBulkUpdate = async () => {
    if (!bulkStatus || !selected.size) return
    const ids = [...selected]
    const prevStatuses = Object.fromEntries(tasks.filter(t => ids.includes(t.id)).map(t => [t.id, t.status]))
    await api.patch(`/api/v1/projects/${projectId}/tasks/bulk`, {
      task_ids: ids,
      status: bulkStatus,
    })
    await fetchTasks(projectId)
    setSelected(new Set())
    setBulkStatus('')
    // Undo
    setUndoAction({ ids, prevStatuses })
    const t = setTimeout(() => setUndoAction(null), 5000)
    setUndoTimeout(t)
  }

  const handleUndo = async () => {
    if (!undoAction) return
    if (undoTimeout) clearTimeout(undoTimeout)
    for (const [id, status] of Object.entries(undoAction.prevStatuses)) {
      await api.patch(`/api/v1/projects/${projectId}/tasks/bulk`, {
        task_ids: [id],
        status,
      })
    }
    await fetchTasks(projectId)
    setUndoAction(null)
  }

  const handleBulkDelete = async () => {
    if (!selected.size || !confirm(`確定刪除 ${selected.size} 個任務？`)) return
    await api.delete(`/api/v1/projects/${projectId}/tasks/bulk`, {
      data: { task_ids: [...selected] },
    })
    await fetchTasks(projectId)
    setSelected(new Set())
  }

  return (
    <div>
      {/* Undo toast */}
      {undoAction && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 bg-gray-900 text-white text-sm px-4 py-2 rounded-xl flex items-center gap-3 z-50 shadow-lg">
          <span>已更新 {undoAction.ids.length} 個任務</span>
          <button onClick={handleUndo} className="underline text-primary-300 hover:text-primary-100">Undo</button>
        </div>
      )}

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 p-3 bg-primary-50 border border-primary-100 rounded-xl mb-4">
          <span className="text-sm font-medium text-primary-700">已選 {selected.size} 項</span>
          <select
            className="input text-sm w-32"
            value={bulkStatus}
            onChange={e => setBulkStatus(e.target.value)}
          >
            <option value="">更改狀態…</option>
            <option value="todo">待辦</option>
            <option value="in_progress">進行中</option>
            <option value="review">審查中</option>
            <option value="done">完成</option>
          </select>
          <button
            disabled={!bulkStatus}
            onClick={handleBulkUpdate}
            className="btn-primary text-sm px-3 disabled:opacity-50"
          >
            套用
          </button>
          <button onClick={handleBulkDelete} className="text-sm text-red-500 hover:text-red-700">刪除</button>
          <button onClick={() => setSelected(new Set())} className="text-sm text-gray-400 hover:text-gray-600 ml-auto">取消選取</button>
        </div>
      )}

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
        {sorted.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">無任務</div>
        ) : (
          sorted.map(t => (
            <div
              key={t.id}
              className={`flex items-center gap-3 px-4 py-3 border-b border-gray-100 last:border-0 hover:bg-gray-50 transition-colors ${
                selected.has(t.id) ? 'bg-primary-50' : ''
              }`}
            >
              <input
                type="checkbox"
                checked={selected.has(t.id)}
                onChange={() => toggleSelect(t.id)}
                className="w-4 h-4 accent-primary-600 flex-shrink-0"
                onClick={e => e.stopPropagation()}
              />
              <button className="flex-1 text-left min-w-0" onClick={() => onSelect(t)}>
                <div className="flex items-center gap-2 min-w-0">
                  <span className={`text-sm font-medium ${t.status === 'done' ? 'line-through text-gray-400' : 'text-gray-800'} truncate`}>
                    {t.title}
                  </span>
                  {t.subtask_count > 0 && (
                    <span className="text-xs text-gray-400 flex-shrink-0">{t.subtask_done_count}/{t.subtask_count}</span>
                  )}
                </div>
              </button>
              <span className={`text-xs font-medium flex-shrink-0 ${PRIORITY_COLORS[t.priority]}`}>
                {PRIORITY_LABELS[t.priority]}
              </span>
              <span className="text-xs text-gray-400 flex-shrink-0 w-20 text-right">
                {t.due_date ?? '—'}
              </span>
              <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full flex-shrink-0">
                {STATUS_LABELS[t.status]}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
