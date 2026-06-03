import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client'

interface AISuggestedTask {
  id: string
  title: string
  reason: string
  score: number
  project_id: string
}

function ScoreBadge({ score }: { score: number }) {
  let colorClass = 'bg-green-100 text-green-700'
  if (score < 60) colorClass = 'bg-red-100 text-red-700'
  else if (score < 80) colorClass = 'bg-yellow-100 text-yellow-700'

  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded-full flex-shrink-0 ${colorClass}`}>
      {score}
    </span>
  )
}

export default function AISuggestCard() {
  const [tasks, setTasks] = useState<AISuggestedTask[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    api
      .get<AISuggestedTask[]>('/dashboard/ai-suggest')
      .then((res) => {
        setTasks(res.data.slice(0, 5))
      })
      .catch(() => {
        setError(true)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [])

  return (
    <div className="card">
      <h2 className="text-sm font-semibold text-gray-700 mb-3">AI 優先度建議</h2>

      {loading && (
        <p className="text-sm text-gray-400 text-center py-6">分析中…</p>
      )}

      {error && (
        <p className="text-sm text-gray-400 text-center py-6">無法載入建議</p>
      )}

      {!loading && !error && tasks.length === 0 && (
        <p className="text-sm text-gray-400 text-center py-6">目前無建議任務 ✨</p>
      )}

      {!loading && !error && tasks.length > 0 && (
        <ul className="space-y-2">
          {tasks.map((t) => (
            <li key={t.id}>
              <Link
                to={`/projects/${t.project_id}`}
                className="flex items-start gap-3 p-2 rounded-lg hover:bg-gray-50 transition-colors group"
              >
                <ScoreBadge score={t.score} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800 group-hover:text-indigo-600 transition-colors font-medium truncate">
                    {t.title}
                  </p>
                  <p className="text-xs text-gray-400 truncate">{t.reason}</p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
