import { useEffect, useState } from 'react'
import { useParams, Routes, Route, NavLink } from 'react-router-dom'
import { toast } from '../stores/toastStore'
import { projectsApi } from '../api/projects'
import { templatesApi } from '../api/templates'
import type { Project, Task, User } from '../types'
import { useTaskStore } from '../stores/taskStore'
import { useProjectWs } from '../hooks/useProjectWs'
import KanbanBoard from '../components/kanban/KanbanBoard'
import KanbanFilterBar, { applyKanbanFilter, type KanbanFilter } from '../components/kanban/KanbanFilterBar'
import TaskDetailPanel from '../components/project/TaskDetailPanel'
import TaskListView from '../components/project/TaskListView'
import CreateTaskModal from '../components/project/CreateTaskModal'
import MilestonesTab from '../components/project/MilestonesTab'
import FilesTab from '../components/project/FilesTab'
import MembersTab from '../components/project/MembersTab'
import GanttTab from '../components/project/GanttTab'
import ProjectSettingsTab from '../components/project/ProjectSettingsTab'

export default function ProjectPage() {
  const { projectId = '' } = useParams()
  const [project, setProject] = useState<Project | null>(null)
  const [members, setMembers] = useState<User[]>([])
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [savingTemplate, setSavingTemplate] = useState(false)
  const [filter, setFilter] = useState<KanbanFilter>({ assigneeId: '', priority: '', status: '', keyword: '' })
  const [viewMode, setViewMode] = useState<'board' | 'list'>('board')
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
      toast.success('已儲存為範本！')
    } catch {
      toast.error('儲存失敗')
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
          {tasks.length > 0 && (() => {
            const overdue = tasks.filter(t => t.status !== 'done' && t.due_date && new Date(t.due_date) < new Date()).length
            const ratio = overdue / tasks.length
            const [label, cls] = ratio < 0.1
              ? ['🟢 健康', 'bg-green-100 text-green-700']
              : ratio < 0.3
              ? ['🟡 注意', 'bg-yellow-100 text-yellow-700']
              : ['🔴 警示', 'bg-red-100 text-red-700']
            return (
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${cls}`}
                title={`逾期任務比例：${Math.round(ratio * 100)}%`}>
                {label}
              </span>
            )
          })()}
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
        <NavLink to="files" className={navClass}>檔案</NavLink>
        <NavLink to="members" className={navClass}>成員</NavLink>
        <NavLink to="settings" className={navClass}>設定</NavLink>
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
                <div className="flex items-center gap-2">
                  {/* 視圖切換 */}
                  <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
                    <button
                      className={`px-3 py-1.5 ${viewMode === 'board' ? 'bg-primary-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
                      onClick={() => setViewMode('board')}
                      title="看板視圖"
                    >
                      ▤ 看板
                    </button>
                    <button
                      className={`px-3 py-1.5 ${viewMode === 'list' ? 'bg-primary-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
                      onClick={() => setViewMode('list')}
                      title="列表視圖"
                    >
                      ≡ 列表
                    </button>
                  </div>
                  <button onClick={() => setShowCreate(true)} className="btn-primary flex-shrink-0">+ 新增任務</button>
                </div>
              </div>
              {viewMode === 'board' ? (
                <KanbanBoard projectId={projectId} onTaskClick={setSelectedTask} filterFn={(t) => applyKanbanFilter([t], filter).length > 0} />
              ) : (
                <TaskListView
                  tasks={applyKanbanFilter(tasks, filter)}
                  projectId={projectId}
                  onSelect={setSelectedTask}
                />
              )}
            </div>
          }
        />
        <Route path="/gantt" element={<GanttTab projectId={projectId} />} />
        <Route path="/milestones" element={<MilestonesTab projectId={projectId} />} />
        <Route path="/files" element={<FilesTab projectId={projectId} />} />
        <Route path="/members" element={<MembersTab projectId={projectId} />} />
        <Route path="/settings" element={<ProjectSettingsTab projectId={projectId} project={project} onProjectUpdate={setProject} />} />
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
