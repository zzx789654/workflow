import { useState } from 'react'
import { useTaskStore } from '../../stores/taskStore'
import type { TaskStatus, TaskPriority } from '../../types'

interface Props {
  projectId: string
  onClose: () => void
}

export default function CreateTaskModal({ projectId, onClose }: Props) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<TaskPriority>('medium')
  const [status, setStatus] = useState<TaskStatus>('todo')
  const [dueDate, setDueDate] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [recurrenceRule, setRecurrenceRule] = useState('')
  const [recurrenceEndDate, setRecurrenceEndDate] = useState('')
  const [loading, setLoading] = useState(false)
  const createTask = useTaskStore((s) => s.createTask)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    setLoading(true)
    try {
      await createTask(projectId, {
        title,
        description: description || undefined,
        priority,
        status,
        due_date: dueDate || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        recurrence_rule: recurrenceRule || undefined,
        recurrence_end_date: recurrenceEndDate || undefined,
      })
      onClose()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <div className="p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">新增任務</h2>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">標題</label>
              <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} required autoFocus placeholder="任務名稱" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
              <textarea className="input resize-none" rows={2} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="（選填）" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">狀態</label>
                <select className="input" value={status} onChange={(e) => setStatus(e.target.value as TaskStatus)}>
                  <option value="todo">待辦</option>
                  <option value="in_progress">進行中</option>
                  <option value="review">審查中</option>
                  <option value="done">完成</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">優先度</label>
                <select className="input" value={priority} onChange={(e) => setPriority(e.target.value as TaskPriority)}>
                  <option value="low">低</option>
                  <option value="medium">中</option>
                  <option value="high">高</option>
                  <option value="urgent">緊急</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">開始日期</label>
                <input className="input" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">結束日期</label>
                <input className="input" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">截止日期（Due）</label>
              <input className="input" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            </div>
            <div className="border-t border-gray-100 pt-3">
              <p className="text-xs font-medium text-gray-500 mb-2">🔁 重複排程（選填）</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-600 mb-1">重複規則</label>
                  <select className="input text-sm" value={recurrenceRule} onChange={(e) => setRecurrenceRule(e.target.value)}>
                    <option value="">不重複</option>
                    <option value="daily">每天</option>
                    <option value="weekly">每週</option>
                    <option value="monthly">每月</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">重複結束日</label>
                  <input
                    className="input text-sm"
                    type="date"
                    value={recurrenceEndDate}
                    onChange={(e) => setRecurrenceEndDate(e.target.value)}
                    disabled={!recurrenceRule}
                  />
                </div>
              </div>
              {recurrenceRule && (
                <p className="text-xs text-amber-600 mt-1.5">
                  ⚠️ 自動建立下一筆任務需後端 worker 服務支援（已儲存規則，排程待啟用）
                </p>
              )}
            </div>
            <div className="flex gap-3 pt-2">
              <button type="submit" disabled={loading} className="btn-primary flex-1">
                {loading ? '建立中…' : '建立任務'}
              </button>
              <button type="button" onClick={onClose} className="btn-secondary flex-1">取消</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
