import React, { useState, useEffect } from 'react'
import { api } from '../../api/client'

interface Checkin {
  id: string
  content: string
  progress: number
  created_at: string
}

interface Props {
  projectId: string
  taskId: string
}

export default function CheckinPanel({ projectId, taskId }: Props) {
  const [checkins, setCheckins] = useState<Checkin[]>([])
  const [loading, setLoading] = useState(true)
  const [content, setContent] = useState('')
  const [progress, setProgress] = useState(0)
  const [submitting, setSubmitting] = useState(false)

  const baseUrl = `/projects/${projectId}/tasks/${taskId}/checkins`

  const fetchCheckins = async () => {
    setLoading(true)
    try {
      const res = await api.get<Checkin[]>(baseUrl)
      setCheckins(res.data)
    } catch {
      // silently handle fetch error
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCheckins()
  }, [projectId, taskId])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!content.trim()) return
    setSubmitting(true)
    try {
      const res = await api.post<Checkin>(baseUrl, { content: content.trim(), progress })
      setCheckins((prev) => [res.data, ...prev])
      setContent('')
      setProgress(0)
    } catch {
      alert('打卡失敗，請稍後再試')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="border-t border-gray-100 pt-4 space-y-4">
      <p className="text-xs font-medium text-gray-500">每日打卡</p>

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-3">
        <textarea
          className="input w-full resize-none"
          rows={3}
          placeholder="今天做了什麼？"
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs text-gray-500">
            <span>進度</span>
            <span className="font-medium text-indigo-600">{progress}%</span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            value={progress}
            onChange={(e) => setProgress(Number(e.target.value))}
            className="w-full accent-indigo-600"
          />
        </div>
        <button
          type="submit"
          disabled={submitting || !content.trim()}
          className="btn-primary w-full"
        >
          {submitting ? '送出中…' : '送出打卡'}
        </button>
      </form>

      {/* History */}
      <div>
        <p className="text-xs font-medium text-gray-500 mb-2">打卡紀錄</p>
        {loading ? (
          <p className="text-sm text-gray-400 text-center py-4">載入中…</p>
        ) : checkins.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4">尚無打卡紀錄</p>
        ) : (
          <ul className="space-y-3">
            {checkins.map((c) => (
              <li key={c.id} className="p-3 bg-gray-50 rounded-lg text-sm">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-gray-400">
                    {new Date(c.created_at).toLocaleString('zh-TW')}
                  </span>
                  <span className="text-xs font-medium text-indigo-600">{c.progress}%</span>
                </div>
                <p className="text-gray-700 whitespace-pre-wrap">{c.content}</p>
                <div className="mt-2 h-1.5 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded-full transition-all"
                    style={{ width: `${c.progress}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
