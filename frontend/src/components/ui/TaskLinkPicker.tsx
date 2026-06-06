import { useEffect, useRef, useState } from 'react'
import { projectsApi } from '../../api/projects'
import { tasksApi } from '../../api/tasks'
import type { Project, Task } from '../../types'

interface Props {
  value: { taskId: string; taskTitle: string; projectName: string } | null
  onChange: (val: { taskId: string; taskTitle: string; projectName: string } | null) => void
}

export default function TaskLinkPicker({ value, onChange }: Props) {
  const [open, setOpen] = useState(false)
  const [projects, setProjects] = useState<Project[]>([])
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [search, setSearch] = useState('')
  const [loadingTasks, setLoadingTasks] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    projectsApi.list().then(r => setProjects(r.data)).catch(() => {})
  }, [open])

  useEffect(() => {
    if (!selectedProject) return
    setLoadingTasks(true)
    tasksApi.list(selectedProject.id)
      .then(r => setTasks(r.data.filter(t => !t.parent_task_id)))
      .finally(() => setLoadingTasks(false))
  }, [selectedProject])

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const filteredTasks = tasks.filter(t =>
    t.title.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div ref={ref} className="relative">
      {/* 顯示已關聯 or 按鈕 */}
      {value ? (
        <div className="flex items-center gap-2 p-2 bg-indigo-50 border border-indigo-200 rounded-lg">
          <span className="text-xs text-indigo-400 flex-shrink-0">{value.projectName}</span>
          <span className="text-xs text-indigo-700 font-medium flex-1 truncate">→ {value.taskTitle}</span>
          <button
            type="button"
            onClick={() => onChange(null)}
            className="text-indigo-300 hover:text-red-400 text-sm flex-shrink-0"
            title="移除關聯"
          >✕</button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setOpen(v => !v)}
          className="text-xs px-3 py-1.5 rounded-lg border border-dashed border-gray-300 text-gray-400 hover:border-indigo-400 hover:text-indigo-500 transition-colors w-full text-left"
        >
          + 關聯至專案任務
        </button>
      )}

      {/* Dropdown */}
      {open && (
        <div className="absolute z-50 mt-1 w-80 bg-white border border-gray-200 rounded-xl shadow-xl overflow-hidden">
          {!selectedProject ? (
            <>
              <div className="px-3 py-2 border-b border-gray-100 text-xs font-medium text-gray-500">選擇專案</div>
              <div className="max-h-56 overflow-y-auto">
                {projects.length === 0 ? (
                  <p className="px-3 py-4 text-xs text-gray-400 text-center">載入中…</p>
                ) : projects.map(p => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setSelectedProject(p)}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center gap-2"
                  >
                    <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: p.color }} />
                    <span className="truncate">{p.name}</span>
                  </button>
                ))}
              </div>
            </>
          ) : (
            <>
              <div className="px-3 py-2 border-b border-gray-100 flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => { setSelectedProject(null); setSearch(''); setTasks([]) }}
                  className="text-gray-400 hover:text-gray-600 text-sm"
                >←</button>
                <span className="text-xs font-medium text-gray-600 truncate flex-1">{selectedProject.name}</span>
              </div>
              <div className="px-3 py-2 border-b border-gray-100">
                <input
                  autoFocus
                  className="w-full text-xs border border-gray-200 rounded px-2 py-1 outline-none focus:border-indigo-400"
                  placeholder="搜尋任務…"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                />
              </div>
              <div className="max-h-56 overflow-y-auto">
                {loadingTasks ? (
                  <p className="px-3 py-4 text-xs text-gray-400 text-center">載入中…</p>
                ) : filteredTasks.length === 0 ? (
                  <p className="px-3 py-4 text-xs text-gray-400 text-center">無任務</p>
                ) : filteredTasks.map(t => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => {
                      onChange({ taskId: t.id, taskTitle: t.title, projectName: selectedProject.name })
                      setOpen(false)
                      setSelectedProject(null)
                      setSearch('')
                    }}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-indigo-50 truncate"
                  >
                    {t.title}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
