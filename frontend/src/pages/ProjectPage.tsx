import { useEffect, useState } from 'react'
import { useParams, Routes, Route, NavLink } from 'react-router-dom'
import { projectsApi } from '../api/projects'
import { templatesApi } from '../api/templates'
import type { Project, Task, User } from '../types'
import { useTaskStore } from '../stores/taskStore'
import { useProjectWs } from '../hooks/useProjectWs'
import KanbanBoard from '../components/kanban/KanbanBoard'
import KanbanFilterBar, { applyKanbanFilter, type KanbanFilter } from '../components/kanban/KanbanFilterBar'
import TaskDetailPanel from '../components/project/TaskDetailPanel'
import CreateTaskModal from '../components/project/CreateTaskModal'
import MilestonesTab from '../components/project/MilestonesTab'
import MembersTab from '../components/project/MembersTab'
import GanttTab from '../components/project/GanttTab'

export default function ProjectPage() {
  const { projectId = '' } = useParams()
  const [project, setProject] = useState<Project | null>(null)
  const [members, setMembers] = useState<User[]>([])
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [savingTemplate, setSavingTemplate] = useState(false)
  const [filter, setFilter] = useState<KanbanFilter>({ assigneeId: '', priority: '', status: '', keyword: '' })
  const fetchTasks = useTaskStore((s) => s.fetchTasks)
  const tasks = useTaskStore((s) => s.tasks)
  useProjectWs(projectId)

  useEffect(() => {
    if (!projectId) return
    projectsApi.get(projectId).then((r) => setProject(r.data))
    projectsApi.listMembers(projectId).then((r) => setMembers(r.data.map((m: { user: User }) => m.user)))
    fetchTasks(projectId)
  }, [projectId])

  const handleSaveAsTemplate = async () => {
    if (!project) return
    const name = prompt('範本名稱：', `${project.name} 範本`)
    if (!name) return
    setSavingTemplate(true)
    try {
      await templatesApi.createFromProject(projectId, name)
      alert('已儲存為範本！')
    } catch {
      alert('儲存失敗')
    } finally { setSavingTemplate(false) }
  }

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
      isActive ? 'border-primary-600 text-primary-600' : 'border-transparent text-gray-500 hover:text-gray-700'
    }`

  if (!project) return <div className="text-center py-20 text-gray-400">載入中…</div>

  return (
    <div className="max-w-7xl mx-auto">
      <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-4 h-4 rounded-full flex-shrink-0" style={{ backgroundColor: project.color }} />
          <h1 className="text-2xl font-bold text-gray-900 truncate">{project.name}</h1>
          {project.description && <span className="text-sm text-gray-500 truncate">{project.description}</span>}
        </div>
        <button
          onClick={handleSaveAsTemplate}
          disabled={savingTemplate}
          className="btn-secondary text-sm flex-shrink-0"
        >
          {savingTemplate ? '儲存中…' : '🗂️ 另存為範本'}
        </button>
      </div>

      <nav className="flex gap-2 border-b border-gray-200 mb-6">
        <NavLink to="" end className={navClass}>看板</NavLink>
        <NavLink to="gantt" className={navClass}>甘特圖</NavLink>
        <NavLink to="milestones" className={navClass}>里程碑</NavLink>
        <NavLink to="members" className={navClass}>成員</NavLink>
      </nav>

      <Routes>
        <Route
          path="/"
          element={
            <div>
              <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                <KanbanFilterBar
                  tasks={tasks}
                  members={members}
                  filter={filter}
                  onChange={setFilter}
                />
                <button onClick={() => setShowCreate(true)} className="btn-primary flex-shrink-0">+ 新增任務</button>
              </div>
              <KanbanBoard projectId={projectId} onTaskClick={setSelectedTask} filterFn={(t) => applyKanbanFilter([t], filter).length > 0} />
            </div>
          }
        />
        <Route path="/gantt" element={<GanttTab projectId={projectId} />} />
        <Route path="/milestones" element={<MilestonesTab projectId={projectId} />} />
        <Route path="/members" element={<MembersTab projectId={projectId} />} />
      </Routes>

      {selectedTask && (
        <TaskDetailPanel task={selectedTask} projectId={projectId} onClose={() => setSelectedTask(null)} />
      )}
      {showCreate && (
        <CreateTaskModal projectId={projectId} onClose={() => setShowCreate(false)} />
      )}
    </div>
  )
}
