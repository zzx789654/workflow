import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { projectsApi } from '../api/projects'
import { useAuthStore } from '../stores/authStore'
import type { Project } from '../types'

export default function ArchivedProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const isAdmin = useAuthStore(s => s.user?.role === 'admin')

  const load = async () => {
    setLoading(true)
    try {
      const res = await projectsApi.listArchived()
      setProjects(res.data)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleUnarchive = async (p: Project) => {
    await projectsApi.update(p.id, { is_archived: false })
    load()
  }

  const handleDelete = async (p: Project) => {
    if (!confirm(`確定永久刪除「${p.name}」？此操作無法復原。`)) return
    await projectsApi.delete(p.id)
    load()
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">封存專案</h1>
          <p className="text-sm text-gray-500 mt-0.5">已完成或暫停的專案，可取消封存恢復使用</p>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-20 text-gray-400">載入中…</div>
      ) : projects.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400 space-y-2">
          <span className="text-4xl">🗄️</span>
          <p className="text-sm">目前沒有封存的專案</p>
          <Link to="/" className="text-sm text-primary-500 hover:underline mt-1">← 返回首頁</Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p) => (
            <div key={p.id} className="card group relative opacity-75 hover:opacity-100 transition-opacity">
              <div className="flex items-center gap-3 mb-2">
                <div className="w-3 h-3 rounded-full flex-shrink-0 grayscale" style={{ backgroundColor: p.color }} />
                <h3 className="font-semibold text-gray-700 truncate pr-2">{p.name}</h3>
              </div>
              {p.description && (
                <p className="text-sm text-gray-400 mb-2 line-clamp-2">{p.description}</p>
              )}
              <div className="flex items-center justify-between text-xs text-gray-400 mb-3">
                <span>{p.member_count} 位成員</span>
                {p.end_date && <span>截止 {p.end_date}</span>}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleUnarchive(p)}
                  className="flex-1 text-xs py-1.5 rounded-lg bg-primary-50 text-primary-600 hover:bg-primary-100 font-medium transition-colors"
                >
                  取消封存
                </button>
                <Link
                  to={`/projects/${p.id}`}
                  className="text-xs px-3 py-1.5 rounded-lg bg-gray-50 text-gray-500 hover:bg-gray-100 transition-colors"
                >
                  查看
                </Link>
                {isAdmin && (
                  <button
                    onClick={() => handleDelete(p)}
                    className="text-xs px-3 py-1.5 rounded-lg bg-red-50 text-red-500 hover:bg-red-100 transition-colors"
                  >
                    刪除
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
