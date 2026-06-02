import { useEffect, useState } from 'react'
import { milestonesApi } from '../../api/milestones'
import type { Milestone, MilestoneStatus } from '../../types'

const STATUS_LABELS: Record<MilestoneStatus, string> = {
  planned: '規劃中', in_progress: '進行中', completed: '已完成', cancelled: '已取消',
}
const STATUS_COLORS: Record<MilestoneStatus, string> = {
  planned: 'bg-gray-100 text-gray-600',
  in_progress: 'bg-blue-100 text-blue-600',
  completed: 'bg-green-100 text-green-600',
  cancelled: 'bg-red-100 text-red-600',
}

interface Props { projectId: string }

export default function MilestonesTab({ projectId }: Props) {
  const [milestones, setMilestones] = useState<Milestone[]>([])
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [creating, setCreating] = useState(false)

  const load = async () => {
    const res = await milestonesApi.list(projectId)
    setMilestones(res.data)
  }

  useEffect(() => { load() }, [projectId])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    setCreating(true)
    try {
      await milestonesApi.create(projectId, { name, due_date: dueDate || undefined })
      setName(''); setDueDate(''); setShowCreate(false)
      await load()
    } finally {
      setCreating(false)
    }
  }

  const updateStatus = async (id: string, status: MilestoneStatus) => {
    await milestonesApi.update(projectId, id, { status })
    await load()
  }

  return (
    <div>
      <div className="flex justify-end mb-4">
        <button onClick={() => setShowCreate(true)} className="btn-primary">+ 新增里程碑</button>
      </div>

      {showCreate && (
        <form onSubmit={handleCreate} className="card mb-4 flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700 mb-1">名稱</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">截止日</label>
            <input className="input" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </div>
          <button type="submit" disabled={creating} className="btn-primary">{creating ? '建立中…' : '建立'}</button>
          <button type="button" onClick={() => setShowCreate(false)} className="btn-secondary">取消</button>
        </form>
      )}

      {milestones.length === 0 ? (
        <div className="text-center py-16 text-gray-400">尚無里程碑</div>
      ) : (
        <div className="space-y-3">
          {milestones.map((m) => (
            <div key={m.id} className="card flex items-center justify-between">
              <div>
                <p className="font-medium text-gray-900">{m.name}</p>
                <div className="flex gap-3 text-xs text-gray-400 mt-1">
                  {m.due_date && <span>截止 {m.due_date}</span>}
                  <span>{m.task_count} 個任務</span>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs px-3 py-1 rounded-full font-medium ${STATUS_COLORS[m.status]}`}>
                  {STATUS_LABELS[m.status]}
                </span>
                <select
                  className="text-xs border border-gray-200 rounded px-2 py-1"
                  value={m.status}
                  onChange={(e) => updateStatus(m.id, e.target.value as MilestoneStatus)}
                >
                  <option value="planned">規劃中</option>
                  <option value="in_progress">進行中</option>
                  <option value="completed">已完成</option>
                  <option value="cancelled">已取消</option>
                </select>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
