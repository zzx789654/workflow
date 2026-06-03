import { useRef, useState } from 'react'
import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import type { Task, TaskStatus } from '../../types'
import TaskCard from './TaskCard'
import { useTaskStore } from '../../stores/taskStore'

interface Props {
  column: { id: TaskStatus; label: string; color: string }
  tasks: Task[]
  onTaskClick: (task: Task) => void
  projectId: string
  blockedTaskIds?: Set<string>
}

export default function KanbanColumn({ column, tasks, onTaskClick, projectId, blockedTaskIds }: Props) {
  const { setNodeRef, isOver } = useDroppable({ id: column.id })
  const [quickTitle, setQuickTitle] = useState('')
  const [adding, setAdding] = useState(false)
  const [showInput, setShowInput] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const createTask = useTaskStore((s) => s.createTask)

  const handleQuickAdd = async () => {
    const title = quickTitle.trim()
    if (!title) { setShowInput(false); return }
    setAdding(true)
    try {
      await createTask(projectId, { title, status: column.id, priority: 'medium' })
      setQuickTitle('')
      // 保持輸入框開啟，讓使用者連續輸入
      setTimeout(() => inputRef.current?.focus(), 50)
    } finally {
      setAdding(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') { e.preventDefault(); handleQuickAdd() }
    if (e.key === 'Escape') { setShowInput(false); setQuickTitle('') }
  }

  return (
    <div
      ref={setNodeRef}
      className={`rounded-xl p-3 min-h-[500px] transition-colors flex flex-col ${column.color} ${isOver ? 'ring-2 ring-primary-400' : ''}`}
    >
      <div className="flex items-center justify-between mb-3 px-1">
        <h3 className="font-semibold text-gray-700 text-sm">{column.label}</h3>
        <span className="text-xs text-gray-400 bg-white rounded-full px-2 py-0.5">{tasks.length}</span>
      </div>

      <SortableContext items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
        <div className="space-y-2 flex-1">
          {tasks.map((task) => (
            <TaskCard
              key={task.id}
              task={task}
              onClick={() => onTaskClick(task)}
              isBlocked={blockedTaskIds?.has(task.id) ?? false}
            />
          ))}
        </div>
      </SortableContext>

      {/* 快速新增任務區 */}
      <div className="mt-2">
        {showInput ? (
          <div className="bg-white rounded-lg p-2 shadow-sm border border-primary-200">
            <input
              ref={inputRef}
              autoFocus
              className="w-full text-sm text-gray-800 outline-none placeholder-gray-400"
              placeholder="任務標題，Enter 新增…"
              value={quickTitle}
              onChange={(e) => setQuickTitle(e.target.value)}
              onKeyDown={handleKeyDown}
              onBlur={() => { if (!quickTitle.trim()) { setShowInput(false) } }}
              disabled={adding}
            />
            <div className="flex items-center justify-between mt-1.5">
              <span className="text-xs text-gray-400">Enter 新增 · Esc 取消</span>
              <button
                onClick={handleQuickAdd}
                disabled={adding || !quickTitle.trim()}
                className="text-xs text-primary-600 hover:text-primary-800 font-medium disabled:opacity-40"
              >
                {adding ? '新增中…' : '新增'}
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => { setShowInput(true); setQuickTitle('') }}
            className="w-full text-left text-xs text-gray-400 hover:text-gray-600 hover:bg-white/60 rounded-lg px-2 py-1.5 transition-colors flex items-center gap-1"
          >
            <span className="text-base leading-none">+</span>
            <span>快速新增任務</span>
          </button>
        )}
      </div>
    </div>
  )
}
