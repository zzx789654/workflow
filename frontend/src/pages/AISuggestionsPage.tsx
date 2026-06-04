import { useEffect, useState } from 'react'
import { aiAssistApi } from '../api/aiAssist'

const PRIORITY_COLORS: Record<string, string> = {
  urgent: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low: 'bg-gray-100 text-gray-500',
}

export default function AISuggestionsPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    aiAssistApi.getSuggestions().then(r => setData(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-center text-gray-400">分析中…</div>

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">AI 優先度建議</h1>
        <div className="flex items-center gap-1.5 text-xs text-gray-400 bg-gray-100 px-2.5 py-1 rounded-full">
          <span>🤖</span>
          <span>規則引擎 v1</span>
        </div>
      </div>

      {data?.suggestions?.length === 0 ? (
        <div className="p-8 text-center text-gray-400">目前無待辦任務</div>
      ) : (
        <div className="space-y-3">
          {data?.suggestions?.map((s: any, i: number) => (
            <div key={s.task_id} className="bg-white border border-gray-200 rounded-xl p-4 flex gap-3">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 ${
                i === 0 ? 'bg-red-500 text-white' : i === 1 ? 'bg-orange-400 text-white' : 'bg-gray-200 text-gray-600'
              }`}>
                {i + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-gray-900 text-sm truncate">{s.title}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${PRIORITY_COLORS[s.priority]}`}>
                    {s.priority}
                  </span>
                </div>
                <p className="text-xs text-gray-500">{s.reason}</p>
                <div className="flex items-center gap-3 mt-1.5 text-xs text-gray-400">
                  {s.due_date && <span>截止 {s.due_date}</span>}
                  <span className="font-medium text-primary-600">urgency {s.urgency_score}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-gray-400 text-center mt-6">
        {data?.generated_at && `產生於 ${new Date(data.generated_at).toLocaleString('zh-TW')}`}
      </p>
    </div>
  )
}
