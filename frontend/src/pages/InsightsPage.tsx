import { useEffect, useState } from 'react'
import { insightsApi, type InsightsData } from '../api/insights'

function DayBar({ data }: { data: { date: string; count: number }[] }) {
  const max = Math.max(...data.map((d) => d.count), 1)
  return (
    <div className="flex items-end gap-1 h-20">
      {data.map((d) => {
        const h = Math.round((d.count / max) * 64)
        const label = d.date.slice(5)
        return (
          <div key={d.date} className="flex flex-col items-center gap-0.5 flex-1">
            <span className="text-xs text-gray-400 leading-none">{d.count || ''}</span>
            <div
              className="w-full rounded-t bg-primary-400 transition-all"
              style={{ height: `${Math.max(h, d.count > 0 ? 4 : 2)}px` }}
              title={`${d.date}: ${d.count} 件`}
            />
            <span className="text-[10px] text-gray-400 leading-none">{label}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function InsightsPage() {
  const [data, setData] = useState<InsightsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    insightsApi.getMe()
      .then((res) => setData(res.data))
      .catch(() => setError('載入失敗，請稍後再試'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-20 text-gray-400">載入中…</div>
  if (error) return <div className="text-center py-10 text-red-500">{error}</div>
  if (!data) return null

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-xl font-bold text-gray-900">個人分析</h1>

      <div className="grid grid-cols-3 gap-4">
        <div className="card text-center">
          <p className="text-3xl font-bold text-primary-600">{data.total_completed}</p>
          <p className="text-sm text-gray-500 mt-1">累計完成</p>
        </div>
        <div className="card text-center">
          <p className="text-3xl font-bold text-primary-600">
            {data.avg_completion_days.toFixed(1)}
          </p>
          <p className="text-sm text-gray-500 mt-1">平均完成天數</p>
        </div>
        <div className="card text-center">
          <p className="text-3xl font-bold text-primary-600">{data.busiest_hour}:00</p>
          <p className="text-sm text-gray-500 mt-1">最忙時段</p>
        </div>
      </div>

      <div className="card">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">每日完成趨勢</h2>
        {data.completion_by_day.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-6">暫無資料</p>
        ) : (
          <DayBar data={data.completion_by_day} />
        )}
      </div>
    </div>
  )
}
