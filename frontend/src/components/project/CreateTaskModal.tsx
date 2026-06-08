import { useEffect, useState } from 'react'
import { useTaskStore } from '../../stores/taskStore'
import { projectsApi } from '../../api/projects'
import type { TaskStatus, TaskPriority, User, ProjectMember } from '../../types'

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
  const [assigneeIds, setAssigneeIds] = useState<string[]>([])
  const [members, setMembers] = useState<User[]>([])
  const [loading, setLoading] = useState(false)
  const createTask = useTaskStore((s) => s.createTask)

  useEffect(() => {
    projectsApi.listMembers(projectId).then(r => {
      const memberList: ProjectMember[] = r.data
      setMembers(memberList.map((m) => m.user))
      // 預設指派給專案管理者（manager / owner）
      const managers = memberList
        .filter((m) => m.role === 'manager' || m.role === 'owner')
        .map((m) => m.user.id)
      if (managers.length > 0) setAssigneeIds(managers)
    })
  }, [projectId])

  const toggleAssignee = (id: string) =>
    setAssigneeIds(ids => ids.includes(id) ? ids.filter(x => x !== id) : [...ids, id])

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
        assignee_ids: assigneeIds.length > 0 ? assigneeIds : undefined,
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

            {/* 施作人員多選 */}
            {members.length > 0 && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  施作人員（可多選）{assigneeIds.length > 0 && <span className="ml-1 text-primary-600">已選 {assigneeIds.length} 人</span>}
                </label>
                <div className="flex flex-wrap gap-2 p-2 border border-gray-200 rounded-lg max-h-32 overflow-y-auto bg-gray-50">
                  {members.map(m => {
                    const selected = assigneeIds.includes(m.id)
                    return (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => toggleAssignee(m.id)}
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm border transition-colors ${
                          selected
                            ? 'bg-primary-500 text-white border-primary-500'
                            : 'bg-white text-gray-600 border-gray-200 hover:border-primary-300'
                        }`}
                      >
                        <div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 ${selected ? 'bg-white/30' : 'bg-primary-100 text-primary-600'}`}>
                          {m.display_name.charAt(0).toUpperCase()}
                        </div>
                        <span>{m.display_name}</span>
                        {selected && <span className="text-xs opacity-80">✓</span>}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

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
              <label className="block text-sm font-medium text-gray-700 mb-1">截止日期</label>
              <input className="input" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
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
