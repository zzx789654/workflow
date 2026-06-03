import { useEffect, useState } from 'react'
import { workloadApi, type WorkloadMember, type WorkloadPeriod } from '../api/workload'

function HorizBar({ value, max, overloaded }: { value: number; max: number; overloaded: boolean }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="w-full bg-gray-100 rounded-full h-3">
      <div
        className={`h-3 rounded-full transition-all ${overloaded ? 'bg-red-400' : 'bg-primary-400'}`}
        style={{ width: `${Math.max(pct, value > 0 ? 2 : 0)}%` }}
      />
    </div>
  )
}

export default function WorkloadPage() {
  const [period, setPeriod] = useState<WorkloadPeriod>('week')
  const [members, setMembers] = useState<WorkloadMember[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    workloadApi.get(period)
      .then((res) => setMembers(res.data.members))
      .catch(() => setError('載入失敗，請稍後再試'))
      .finally(() => setLoading(false))
  }, [period])

  const maxTasks = Math.max(...members.map((m) => m.task_count), 1)

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">團隊工作量</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setPeriod('week')}
            className={period === 'week' ? 'btn-primary' : 'btn-secondary'}
          >
            本週
          </button>
          <button
            onClick={() => setPeriod('month')}
            className={period === 'month' ? 'btn-primary' : 'btn-secondary'}
          >
            本月
          </button>
        </div>
      </div>

      {loading && <div className="text-center py-20 text-gray-400">載入中…</div>}
      {error && <div className="text-center py-10 text-red-500">{error}</div>}

      {!loading && !error && (
        <div className="card space-y-5">
          {members.length === 0 ? (
            <p className="text-center text-gray-400 py-8">暫無資料</p>
          ) : (
            members.map((m) => (
              <div key={m.user_id}>
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span className={`text-sm font-medium ${m.is_overloaded ? 'text-red-600' : 'text-gray-800'}`}>
                      {m.display_name}
                    </span>
                    {m.is_overloaded && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-600">超載</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 flex gap-3">
                    <span>{m.task_count} 件任務</span>
                    <span>{Math.round(m.total_minutes / 60)} 小時</span>
                  </div>
                </div>
                <HorizBar value={m.task_count} max={maxTasks} overloaded={m.is_overloaded} />
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
