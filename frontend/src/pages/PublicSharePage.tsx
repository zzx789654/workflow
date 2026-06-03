import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { publicShareApi, type PublicProject, type PublicTask } from '../api/publicShare'

const STATUS_LABEL: Record<string, string> = {
  todo: '待辦',
  in_progress: '進行中',
  done: '完成',
  blocked: '阻塞',
}

const STATUS_ORDER = ['todo', 'in_progress', 'blocked', 'done']

function groupByStatus(tasks: PublicTask[]): Record<string, PublicTask[]> {
  return tasks.reduce<Record<string, PublicTask[]>>((acc, t) => {
    const key = t.status || 'todo'
    if (!acc[key]) acc[key] = []
    acc[key].push(t)
    return acc
  }, {})
}

const PRIORITY_COLOR: Record<string, string> = {
  urgent: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  medium: 'bg-blue-100 text-blue-700',
  low: 'bg-gray-100 text-gray-500',
}
const PRIORITY_LABEL: Record<string, string> = {
  urgent: '緊急', high: '高', medium: '中', low: '低',
}

export default function PublicSharePage() {
  const { token } = useParams<{ token: string }>()
  const [project, setProject] = useState<PublicProject | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    publicShareApi.getPublic(token)
      .then((res) => setProject(res.data))
      .catch(() => setError('找不到此分享連結，或連結已失效'))
      .finally(() => setLoading(false))
  }, [token])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-400">
        載入中…
      </div>
    )
  }

  if (error || !project) {
    return (
      <div className="min-h-screen flex items-center justify-center text-red-500">
        {error || '發生錯誤'}
      </div>
    )
  }

  const grouped = groupByStatus(project.tasks)
  const columns = [...STATUS_ORDER, ...Object.keys(grouped).filter((s) => !STATUS_ORDER.includes(s))]

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center gap-3">
          <h1 className="text-lg font-bold text-gray-900">{project.name}</h1>
          <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-medium">
            只讀模式
          </span>
        </div>
        {project.description && (
          <p className="max-w-6xl mx-auto text-sm text-gray-500 mt-1">{project.description}</p>
        )}
      </header>

      <main className="max-w-6xl mx-auto px-6 py-6">
        <div className="flex gap-4 overflow-x-auto pb-4">
          {columns.map((status) => {
            const tasks = grouped[status] ?? []
            return (
              <div key={status} className="flex-shrink-0 w-64">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-sm font-semibold text-gray-700">
                    {STATUS_LABEL[status] ?? status}
                  </span>
                  <span className="text-xs bg-gray-200 text-gray-500 rounded-full px-1.5 py-0.5">
                    {tasks.length}
                  </span>
                </div>
                <div className="space-y-2">
                  {tasks.length === 0 ? (
                    <div className="text-xs text-gray-400 text-center py-6 bg-white rounded-lg border border-dashed border-gray-200">
                      無任務
                    </div>
                  ) : (
                    tasks.map((t) => (
                      <div key={t.id} className="bg-white rounded-lg shadow-sm p-3 border border-gray-100">
                        <p className="text-sm text-gray-800 leading-snug">{t.title}</p>
                        <div className="flex items-center gap-2 mt-2">
                          {t.priority && (
                            <span className={`text-xs px-1.5 py-0.5 rounded-full ${PRIORITY_COLOR[t.priority] ?? 'bg-gray-100 text-gray-500'}`}>
                              {PRIORITY_LABEL[t.priority] ?? t.priority}
                            </span>
                          )}
                          {t.due_date && (
                            <span className="text-xs text-gray-400">{t.due_date}</span>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </main>
    </div>
  )
}
