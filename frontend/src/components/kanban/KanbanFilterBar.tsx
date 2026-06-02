import type { Task, User } from '../../types'

export interface KanbanFilter {
  assigneeId: string
  priority: string
  status: string
  keyword: string
}

interface Props {
  tasks: Task[]
  members: User[]
  filter: KanbanFilter
  onChange: (f: KanbanFilter) => void
}

const PRIORITIES: { value: string; label: string }[] = [
  { value: '', label: '所有優先度' },
  { value: 'urgent', label: '緊急' },
  { value: 'high', label: '高' },
  { value: 'medium', label: '中' },
  { value: 'low', label: '低' },
]

const STATUSES: { value: string; label: string }[] = [
  { value: '', label: '所有狀態' },
  { value: 'todo', label: '待辦' },
  { value: 'in_progress', label: '進行中' },
  { value: 'review', label: '審查中' },
  { value: 'done', label: '完成' },
]

export function applyKanbanFilter(tasks: Task[], f: KanbanFilter): Task[] {
  return tasks.filter((t) => {
    if (f.assigneeId && !t.assignees.some((a) => a.id === f.assigneeId)) return false
    if (f.priority && t.priority !== f.priority) return false
    if (f.status && t.status !== f.status) return false
    if (f.keyword) {
      const kw = f.keyword.toLowerCase()
      if (!t.title.toLowerCase().includes(kw) && !(t.description?.toLowerCase().includes(kw))) return false
    }
    return true
  })
}

export default function KanbanFilterBar({ members, filter, onChange }: Props) {
  const set = (patch: Partial<KanbanFilter>) => onChange({ ...filter, ...patch })

  const hasFilter = filter.assigneeId || filter.priority || filter.status || filter.keyword

  return (
    <div className="flex flex-wrap items-center gap-2 mb-4">
      <input
        className="input text-sm w-40"
        placeholder="關鍵字篩選…"
        value={filter.keyword}
        onChange={(e) => set({ keyword: e.target.value })}
      />

      <select
        className="input text-sm w-32"
        value={filter.priority}
        onChange={(e) => set({ priority: e.target.value })}
      >
        {PRIORITIES.map((p) => (
          <option key={p.value} value={p.value}>{p.label}</option>
        ))}
      </select>

      <select
        className="input text-sm w-32"
        value={filter.status}
        onChange={(e) => set({ status: e.target.value })}
      >
        {STATUSES.map((s) => (
          <option key={s.value} value={s.value}>{s.label}</option>
        ))}
      </select>

      <select
        className="input text-sm w-36"
        value={filter.assigneeId}
        onChange={(e) => set({ assigneeId: e.target.value })}
      >
        <option value="">所有指派人</option>
        {members.map((m) => (
          <option key={m.id} value={m.id}>{m.display_name}</option>
        ))}
      </select>

      {hasFilter && (
        <button
          className="text-xs text-gray-400 hover:text-gray-600 px-2 py-1"
          onClick={() => onChange({ assigneeId: '', priority: '', status: '', keyword: '' })}
        >
          清除篩選
        </button>
      )}
    </div>
  )
}
