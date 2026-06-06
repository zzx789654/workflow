import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { aiAssistApi } from '../api/aiAssist'

const PRIORITY_LABEL: Record<string, string> = {
  urgent: '緊急', high: '高', medium: '中', low: '低',
}

export default function AISuggestionsPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    aiAssistApi.getSuggestions().then(r => setData(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-center text-gray-400">分析中…</div>

  const aiEnabled = data?.ai_enabled
  const model = data?.model
  const suggestions = (data?.suggestions ?? []).slice(0, 3)

  return (
    <div className="max-w-xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-bold text-gray-900">今日 AI 建議</h1>
        <span className={`text-xs px-2.5 py-1 rounded-full ${aiEnabled && model !== 'rule_engine_v1' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-500'}`}>
          {aiEnabled && model !== 'rule_engine_v1' ? '✨ Claude AI' : '規則引擎'}
        </span>
      </div>

      {!aiEnabled && (
        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded-xl text-sm text-yellow-700">
          設定 <code className="font-mono bg-yellow-100 px-1 rounded">ANTHROPIC_API_KEY</code> 後可啟用 Claude AI 建議。
        </div>
      )}

      {suggestions.length === 0 ? (
        <div className="p-10 text-center text-gray-400">目前沒有待辦任務</div>
      ) : (
        <div className="space-y-3">
          {suggestions.map((s: any, i: number) => (
            <Link key={s.task_id} to={`/projects/${s.project_id}`}
              className="block bg-white border border-gray-200 rounded-xl p-4 hover:border-primary-300 hover:shadow-sm transition-all">
              <div className="flex items-start gap-3">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 ${
                  i === 0 ? 'bg-red-500 text-white' : i === 1 ? 'bg-orange-400 text-white' : 'bg-blue-400 text-white'
                }`}>
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="font-medium text-gray-900 text-sm truncate">{s.title}</span>
                    <span className="text-xs text-gray-400 flex-shrink-0">{PRIORITY_LABEL[s.priority] ?? s.priority}</span>
                  </div>
                  <p className="text-sm text-gray-600">{s.reason}</p>
                  {s.due_date && (
                    <p className="text-xs text-gray-400 mt-1">截止 {s.due_date}</p>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {data?.generated_at && (
        <p className="text-xs text-gray-400 text-center mt-4">
          產生於 {new Date(data.generated_at).toLocaleString('zh-TW')}
        </p>
      )}
    </div>
  )
}
