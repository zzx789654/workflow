import { useEffect, useState } from 'react'
import { workloadApi } from '../api/workload'
import { projectsApi } from '../api/projects'
import type { Project } from '../types'

export default function WorkloadPage() {
  const [period, setPeriod] = useState<'week' | 'month'>('week')
  const [projectId, setProjectId] = useState('')
  const [projects, setProjects] = useState<Project[]>([])
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    projectsApi.list().then(r => setProjects(r.data))
  }, [])

  useEffect(() => {
    setLoading(true)
    workloadApi.get(period, projectId || undefined)
      .then(r => setData(r.data))
      .finally(() => setLoading(false))
  }, [period, projectId])

  const maxTasks = Math.max(...(data?.members?.map((m: any) => m.task_count) ?? [1]), 1)

  return (
    <div className="max-w-3xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">工作量視圖</h1>
        <div className="flex gap-2">
          <select className="input text-sm w-36" value={projectId} onChange={e => setProjectId(e.target.value)}>
            <option value="">所有專案</option>
            {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
            <button
              className={`px-3 py-1.5 ${period === 'week' ? 'bg-primary-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
              onClick={() => setPeriod('week')}
            >本週</button>
            <button
              className={`px-3 py-1.5 ${period === 'month' ? 'bg-primary-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
              onClick={() => setPeriod('month')}
            >本月</button>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="p-8 text-center text-gray-400">載入中…</div>
      ) : !data?.members?.length ? (
        <div className="p-8 text-center text-gray-400">目前無工作量資料</div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-100 bg-gray-50 text-xs text-gray-500 grid grid-cols-[1fr_auto_auto_auto] gap-4">
            <span>成員</span>
            <span className="text-right w-16">任務數</span>
            <span className="text-right w-16">工時</span>
            <span className="text-right w-16">狀態</span>
          </div>
          <div className="divide-y divide-gray-100">
            {data.members.map((m: any) => (
              <div key={m.user_id} className="px-4 py-3">
                <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 items-center mb-1.5">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-full bg-primary-500 text-white text-xs flex items-center justify-center font-medium flex-shrink-0">
                      {m.display_name.charAt(0).toUpperCase()}
                    </div>
                    <span className="text-sm font-medium text-gray-700">{m.display_name}</span>
                  </div>
                  <span className={`text-sm font-medium w-16 text-right ${m.overloaded ? 'text-red-600' : 'text-gray-700'}`}>
                    {m.task_count}
                  </span>
                  <span className="text-sm text-gray-500 w-16 text-right">{m.logged_hours}h</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full w-16 text-center ${
                    m.overloaded ? 'bg-red-100 text-red-600' : 'bg-green-100 text-green-600'
                  }`}>
                    {m.overloaded ? '超載' : '正常'}
                  </span>
                </div>
                {/* 橫條圖 */}
                <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${m.overloaded ? 'bg-red-400' : 'bg-primary-400'}`}
                    style={{ width: `${Math.min((m.task_count / maxTasks) * 100, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
