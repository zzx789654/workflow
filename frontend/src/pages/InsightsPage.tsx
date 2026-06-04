import { useEffect, useState } from 'react'
import { insightsApi } from '../api/insights'

const DOW_ORDER = ['日', '一', '二', '三', '四', '五', '六']

export default function InsightsPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    insightsApi.get().then(r => setData(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-center text-gray-400">載入中…</div>

  const maxDone = Math.max(...(data?.done_trend?.map((d: any) => d.count) ?? [1]), 1)
  const maxDow = Math.max(...(data?.productivity_by_dow?.map((d: any) => d.total_minutes) ?? [1]), 1)

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-xl font-bold text-gray-900">個人效率分析</h1>

      {/* 任務概況 */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: '待辦', count: data?.task_summary?.todo ?? 0, color: 'bg-gray-50 text-gray-700' },
          { label: '進行中', count: data?.task_summary?.in_progress ?? 0, color: 'bg-blue-50 text-blue-700' },
          { label: '審查中', count: data?.task_summary?.review ?? 0, color: 'bg-yellow-50 text-yellow-700' },
          { label: '已完成', count: data?.task_summary?.done ?? 0, color: 'bg-green-50 text-green-700' },
        ].map(item => (
          <div key={item.label} className={`${item.color} border rounded-xl p-4 text-center`} style={{ borderColor: 'transparent' }}>
            <div className="text-2xl font-bold">{item.count}</div>
            <div className="text-xs mt-1 opacity-70">{item.label}</div>
          </div>
        ))}
      </div>

      {/* 平均完成時間 */}
      <div className="bg-white border border-gray-200 rounded-xl p-4">
        <p className="text-xs font-medium text-gray-500 mb-1">平均任務完成時間（近 30 天）</p>
        <p className="text-2xl font-bold text-primary-700">{data?.avg_completion_hours ?? 0} 小時</p>
      </div>

      {/* 30 天完成趨勢 */}
      {data?.done_trend?.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-xs font-medium text-gray-500 mb-3">近 30 天完成趨勢</p>
          <div className="flex items-end gap-1 h-24">
            {data.done_trend.map((d: any, i: number) => (
              <div key={i} className="flex-1 flex flex-col items-center gap-1">
                <div
                  className="w-full bg-primary-400 rounded-t"
                  style={{ height: `${Math.max((d.count / maxDone) * 88, 4)}px` }}
                  title={`${d.date}: ${d.count} 項`}
                />
              </div>
            ))}
          </div>
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>{data.done_trend[0]?.date?.slice(5)}</span>
            <span>{data.done_trend[data.done_trend.length - 1]?.date?.slice(5)}</span>
          </div>
        </div>
      )}

      {/* 星期分佈 */}
      {data?.productivity_by_dow?.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          <p className="text-xs font-medium text-gray-500 mb-3">按星期工時分佈（近 30 天）</p>
          <div className="space-y-2">
            {data.productivity_by_dow.map((d: any) => (
              <div key={d.dow} className="flex items-center gap-3">
                <span className="text-xs text-gray-500 w-4">週{d.dow}</span>
                <div className="flex-1 h-3 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary-400 rounded-full"
                    style={{ width: `${(d.total_minutes / maxDow) * 100}%` }}
                  />
                </div>
                <span className="text-xs text-gray-500 w-12 text-right">
                  {Math.floor(d.total_minutes / 60)}h{d.total_minutes % 60}m
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
