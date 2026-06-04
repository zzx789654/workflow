import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client'

const STATUS_LABELS: Record<string, string> = {
  todo: '待辦', in_progress: '進行中', review: '審查中', done: '完成'
}
const STATUS_COLORS: Record<string, string> = {
  todo: 'bg-gray-100 text-gray-600',
  in_progress: 'bg-blue-100 text-blue-700',
  review: 'bg-yellow-100 text-yellow-700',
  done: 'bg-green-100 text-green-700',
}

export default function PublicProjectPage() {
  const { token } = useParams<{ token: string }>()
  const [data, setData] = useState<any>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/api/v1/public/projects/${token}`)
      .then(r => setData(r.data))
      .catch(e => setError(e?.response?.data?.detail ?? '無法載入此分享連結'))
      .finally(() => setLoading(false))
  }, [token])

  if (loading) return <div className="p-16 text-center text-gray-400">載入中…</div>
  if (error) return <div className="p-16 text-center text-red-500">{error}</div>

  const donePct = data.tasks.length > 0
    ? Math.round(data.tasks.filter((t: any) => t.status === 'done').length / data.tasks.length * 100)
    : 0

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-2xl mx-auto">
        <div className="bg-white border border-gray-200 rounded-2xl p-6 mb-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-4 h-4 rounded-full" style={{ backgroundColor: data.project.color }} />
            <h1 className="text-xl font-bold text-gray-900">{data.project.name}</h1>
          </div>
          {data.project.description && (
            <p className="text-sm text-gray-500 mb-4">{data.project.description}</p>
          )}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
              <div className="h-full bg-green-500 rounded-full" style={{ width: `${donePct}%` }} />
            </div>
            <span className="text-sm font-medium text-gray-700">{donePct}% 完成</span>
          </div>
        </div>

        <div className="space-y-2">
          {data.tasks.map((t: any) => (
            <div key={t.id} className="bg-white border border-gray-200 rounded-xl px-4 py-3 flex items-center gap-3">
              <span className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${STATUS_COLORS[t.status]}`}>
                {STATUS_LABELS[t.status]}
              </span>
              <span className={`text-sm flex-1 ${t.status === 'done' ? 'line-through text-gray-400' : 'text-gray-800'}`}>
                {t.title}
              </span>
              {t.due_date && <span className="text-xs text-gray-400">{t.due_date}</span>}
            </div>
          ))}
        </div>

        <p className="text-xs text-center text-gray-400 mt-6">
          此為唯讀分享視圖 · WorkFlow
        </p>
      </div>
    </div>
  )
}
