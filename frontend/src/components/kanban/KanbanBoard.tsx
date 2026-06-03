import { useEffect, useState } from 'react'
import {
  DndContext,
  DragEndEvent,
  DragOverEvent,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCenter,
  DragOverlay,
} from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import type { Task, TaskDependency, TaskStatus } from '../../types'
import KanbanColumn from './KanbanColumn'
import TaskCard from './TaskCard'
import { useTaskStore } from '../../stores/taskStore'
import { dependenciesApi } from '../../api/dependencies'

const COLUMNS: { id: TaskStatus; label: string; color: string }[] = [
  { id: 'todo', label: '待辦', color: 'bg-gray-100' },
  { id: 'in_progress', label: '進行中', color: 'bg-blue-50' },
  { id: 'review', label: '審查中', color: 'bg-yellow-50' },
  { id: 'done', label: '完成', color: 'bg-green-50' },
]

interface Props {
  projectId: string
  onTaskClick: (task: Task) => void
  filterFn?: (task: Task) => boolean
}

export default function KanbanBoard({ projectId, onTaskClick, filterFn }: Props) {
  const tasks = useTaskStore((s) => s.tasks)
  const moveTask = useTaskStore((s) => s.moveTask)
  const wsConnected = useTaskStore((s) => s.wsConnected)
  const [activeTask, setActiveTask] = useState<Task | null>(null)
  const [allDeps, setAllDeps] = useState<TaskDependency[]>([])

  // 載入所有依賴，計算被阻擋的任務
  useEffect(() => {
    if (!tasks.length) return
    Promise.all(
      tasks.map((t) =>
        dependenciesApi.list(projectId, t.id)
          .then((r) => r.data)
          .catch(() => [] as TaskDependency[])
      )
    ).then((results) => setAllDeps(results.flat()))
  }, [projectId, tasks.length])

  // 有未完成前置任務的 task id 集合
  const blockedTaskIds = new Set<string>(
    allDeps
      .filter((d) => {
        const fromTask = tasks.find((t) => t.id === d.from_task_id)
        return fromTask && fromTask.status !== 'done'
      })
      .map((d) => d.to_task_id)
  )

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  const tasksByStatus = (status: TaskStatus) =>
    tasks
      .filter((t) => t.status === status && (filterFn ? filterFn(t) : true))
      .sort((a, b) => a.position - b.position)

  const handleDragStart = (e: DragStartEvent) => {
    setActiveTask(tasks.find((t) => t.id === e.active.id) ?? null)
  }

  const handleDragEnd = async (e: DragEndEvent) => {
    const { active, over } = e
    setActiveTask(null)
    if (!over) return

    const taskId = active.id as string
    const overId = over.id as string

    // Determine target column
    const targetColumn = COLUMNS.find((c) => c.id === overId)
    if (targetColumn) {
      const colTasks = tasksByStatus(targetColumn.id)
      const newPosition = colTasks.length
      await moveTask(projectId, taskId, targetColumn.id, newPosition)
      return
    }

    // Dropped onto another task
    const overTask = tasks.find((t) => t.id === overId)
    const draggedTask = tasks.find((t) => t.id === taskId)
    if (!overTask || !draggedTask) return

    const newStatus = overTask.status
    const colTasks = tasksByStatus(newStatus).filter((t) => t.id !== taskId)
    const overIndex = colTasks.findIndex((t) => t.id === overId)
    await moveTask(projectId, taskId, newStatus, overIndex)
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-4 text-xs text-gray-400">
        <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-400' : 'bg-gray-300'}`} />
        <span>{wsConnected ? '即時同步中' : '離線'}</span>
      </div>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
        <div className="grid grid-cols-4 gap-4">
          {COLUMNS.map((col) => {
            const colTasks = tasksByStatus(col.id)
            return (
              <KanbanColumn key={col.id} column={col} tasks={colTasks} onTaskClick={onTaskClick} projectId={projectId} blockedTaskIds={blockedTaskIds} />
            )
          })}
        </div>
        <DragOverlay>
          {activeTask && <TaskCard task={activeTask} isDragging onClick={() => {}} />}
        </DragOverlay>
      </DndContext>
    </div>
  )
}
