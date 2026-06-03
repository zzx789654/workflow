import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { differenceInCalendarDays, parseISO } from 'date-fns'
import type { Task } from '../../types'

const PRIORITY_COLORS = {
  low: 'bg-gray-100 text-gray-500',
  medium: 'bg-blue-100 text-blue-600',
  high: 'bg-orange-100 text-orange-600',
  urgent: 'bg-red-100 text-red-600',
}

const PRIORITY_LABELS = { low: '低', medium: '中', high: '高', urgent: '緊急' }

interface Props {
  task: Task
  onClick: () => void
  isDragging?: boolean
  isBlocked?: boolean
}

function getDueDateUrgency(dueDate: string | null, status: string): 'overdue' | 'today' | 'tomorrow' | null {
  if (!dueDate || status === 'done') return null
  const diff = differenceInCalendarDays(parseISO(dueDate), new Date())
  if (diff < 0) return 'overdue'
  if (diff === 0) return 'today'
  if (diff === 1) return 'tomorrow'
  return null
}

const URGENCY_STYLES = {
  overdue:  'bg-red-50 border-red-200',
  today:    'bg-orange-50 border-orange-200',
  tomorrow: 'bg-yellow-50 border-yellow-200',
}
const URGENCY_LABEL = {
  overdue:  { text: '已逾期', cls: 'text-red-600' },
  today:    { text: '今日截止', cls: 'text-orange-600' },
  tomorrow: { text: '明日截止', cls: 'text-yellow-600' },
}

export default function TaskCard({ task, onClick, isDragging = false, isBlocked = false }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging: sortableDragging } = useSortable({ id: task.id })
  const urgency = getDueDateUrgency(task.due_date, task.status)

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: sortableDragging ? 0.4 : 1,
  }

  const cardBase = urgency ? URGENCY_STYLES[urgency] : 'bg-white border-gray-100'

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={onClick}
      className={`${cardBase} rounded-lg p-3 shadow-sm border cursor-pointer hover:shadow-md transition-shadow ${isDragging ? 'shadow-xl rotate-2' : ''}`}
    >
      <div className="flex items-start gap-1 mb-2">
        {isBlocked && (
          <span className="text-orange-400 flex-shrink-0 text-sm" title="有未完成的前置任務">🔒</span>
        )}
        <p className="text-sm font-medium text-gray-800 line-clamp-2">{task.title}</p>
      </div>
      <div className="flex items-center justify-between">
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${PRIORITY_COLORS[task.priority]}`}>
          {PRIORITY_LABELS[task.priority]}
        </span>
        {task.assignees.length > 0 && (
          <div className="flex -space-x-1">
            {task.assignees.slice(0, 3).map((u) => (
              <div key={u.id} className="w-6 h-6 rounded-full bg-primary-500 text-white text-xs flex items-center justify-center border-2 border-white font-medium" title={u.display_name}>
                {u.display_name.charAt(0).toUpperCase()}
              </div>
            ))}
          </div>
        )}
      </div>
      {(task.start_date || task.end_date) && (
        <p className="text-xs text-gray-400 mt-1">
          {task.start_date && <span>開始 {task.start_date}</span>}
          {task.start_date && task.end_date && <span className="mx-1">→</span>}
          {task.end_date && <span>結束 {task.end_date}</span>}
        </p>
      )}
      {task.due_date && (
        <p className={`text-xs mt-1 flex items-center gap-1 ${urgency ? URGENCY_LABEL[urgency].cls : 'text-gray-400'}`}>
          <span>截止 {task.due_date}</span>
          {urgency && <span className="font-medium">· {URGENCY_LABEL[urgency].text}</span>}
        </p>
      )}
      {task.subtask_count > 0 && (
        <div className="mt-2">
          <div className="flex items-center justify-between text-xs text-gray-400 mb-0.5">
            <span>子任務 {task.subtask_done_count}/{task.subtask_count}</span>
            <span>{task.subtask_count > 0 ? Math.round(task.subtask_done_count / task.subtask_count * 100) : 0}%</span>
          </div>
          <div className="h-1 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-primary-400 rounded-full transition-all"
              style={{ width: `${task.subtask_count > 0 ? task.subtask_done_count / task.subtask_count * 100 : 0}%` }}
            />
          </div>
        </div>
      )}
      {task.comments.length > 0 && (
        <p className="text-xs text-gray-400 mt-1">{task.comments.length} 則評論</p>
      )}
    </div>
  )
}
