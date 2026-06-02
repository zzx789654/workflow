import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
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
}

export default function TaskCard({ task, onClick, isDragging = false }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging: sortableDragging } = useSortable({ id: task.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: sortableDragging ? 0.4 : 1,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onClick={onClick}
      className={`bg-white rounded-lg p-3 shadow-sm border border-gray-100 cursor-pointer hover:shadow-md transition-shadow ${isDragging ? 'shadow-xl rotate-2' : ''}`}
    >
      <p className="text-sm font-medium text-gray-800 mb-2 line-clamp-2">{task.title}</p>
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
      {task.due_date && (
        <p className="text-xs text-gray-400 mt-1">截止 {task.due_date}</p>
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
