import { useDroppable } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import type { Task, TaskStatus } from '../../types'
import TaskCard from './TaskCard'

interface Props {
  column: { id: TaskStatus; label: string; color: string }
  tasks: Task[]
  onTaskClick: (task: Task) => void
}

export default function KanbanColumn({ column, tasks, onTaskClick }: Props) {
  const { setNodeRef, isOver } = useDroppable({ id: column.id })

  return (
    <div
      ref={setNodeRef}
      className={`rounded-xl p-3 min-h-[500px] transition-colors ${column.color} ${isOver ? 'ring-2 ring-primary-400' : ''}`}
    >
      <div className="flex items-center justify-between mb-3 px-1">
        <h3 className="font-semibold text-gray-700 text-sm">{column.label}</h3>
        <span className="text-xs text-gray-400 bg-white rounded-full px-2 py-0.5">{tasks.length}</span>
      </div>
      <SortableContext items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
        <div className="space-y-2">
          {tasks.map((task) => (
            <TaskCard key={task.id} task={task} onClick={() => onTaskClick(task)} />
          ))}
        </div>
      </SortableContext>
    </div>
  )
}
