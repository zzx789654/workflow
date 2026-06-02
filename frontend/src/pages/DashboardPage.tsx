import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { projectsApi } from '../api/projects'
import { dashboardApi, type DashboardSummary } from '../api/dashboard'
import type { Project } from '../types'

const PRIORITY_COLOR: Record<string, string> = {
  urgent: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  medium: 'bg-blue-100 text-blue-700',
  low: 'bg-gray-100 text-gray-500',
}
const PRIORITY_LABEL: Record<string, string> = {
  urgent: '緊急', high: '高', medium: '中', low: '低',
}

function TrendBar({ trend }: { trend: { date: string; count: number }[] }) {
  const max = Math.max(...trend.map((d) => d.count), 1)
  return (
    <div className="flex items-end gap-1 h-16">
      {trend.map((d) => {
        const h = Math.round((d.count / max) * 56)
        const label = d.date.slice(5) // MM-DD
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

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [creating, setCreating] = useState(false)

  const loadAll = async () => {
    setLoading(true)
    try {
      const [pRes, sRes] = await Promise.all([
        projectsApi.list(),
        dashboardApi.summary(),
      ])
      setProjects(pRes.data)
      setSummary(sRes.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadAll() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setCreating(true)
    try {
      await projectsApi.create({ name })
      setName('')
      setShowCreate(false)
      await loadAll()
    } finally {
      setCreating(false)
    }
  }

  if (loading) return <div className="text-center py-20 text-gray-400">載入中…</div>

  const kpi = summary?.kpi
  const trend = summary?.trend ?? []
  const actionRequired = summary?.action_required ?? []

  return (
    <div className="max-w-6xl mx-auto space-y-6">

      {/* KPI 卡片 */}
      {kpi && (
        <div className="grid grid-cols-3 gap-4">
          <div className="card text-center">
            <p className="text-3xl font-bold text-primary-600">{kpi.todo}</p>
            <p className="text-sm text-gray-500 mt-1">待辦任務</p>
          </div>
          <div className="card text-center">
            <p className={`text-3xl font-bold ${kpi.overdue > 0 ? 'text-red-600' : 'text-gray-400'}`}>
              {kpi.overdue}
            </p>
            <p className="text-sm text-gray-500 mt-1">已延遲</p>
          </div>
          <div className="card text-center">
            <p className="text-3xl font-bold text-green-600">{kpi.completed_this_week}</p>
            <p className="text-sm text-gray-500 mt-1">本週完成</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 7 天完成趨勢 */}
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">過去 7 天完成趨勢</h2>
          <TrendBar trend={trend} />
        </div>

        {/* 需我處理 */}
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">需我處理</h2>
          {actionRequired.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">目前沒有待處理任務 🎉</p>
          ) : (
            <ul className="space-y-2 max-h-48 overflow-y-auto">
              {actionRequired.map((t) => (
                <li key={t.id}>
                  <Link
                    to={`/projects/${t.project_id}`}
                    className="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-50 transition-colors group"
                  >
                    <span className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${PRIORITY_COLOR[t.priority] ?? 'bg-gray-100 text-gray-500'}`}>
                      {PRIORITY_LABEL[t.priority] ?? t.priority}
                    </span>
                    <span className="flex-1 text-sm text-gray-700 group-hover:text-primary-600 truncate">{t.title}</span>
                    {t.due_date && (
                      <span className="text-xs text-gray-400 flex-shrink-0">{t.due_date}</span>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* 專案列表 */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-gray-900">我的專案</h2>
          <button onClick={() => setShowCreate(true)} className="btn-primary">+ 新增專案</button>
        </div>

        {showCreate && (
          <form onSubmit={handleCreate} className="card mb-4 flex gap-3">
            <input
              className="input flex-1"
              placeholder="專案名稱"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              required
            />
            <button type="submit" disabled={creating} className="btn-primary">
              {creating ? '建立中…' : '建立'}
            </button>
            <button type="button" onClick={() => setShowCreate(false)} className="btn-secondary">取消</button>
          </form>
        )}

        {projects.length === 0 ? (
          <div className="text-center py-16 text-gray-400">尚無專案，點擊上方「新增專案」開始</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((p) => (
              <Link key={p.id} to={`/projects/${p.id}`} className="card hover:shadow-md transition-shadow group">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: p.color }} />
                  <h3 className="font-semibold text-gray-900 group-hover:text-primary-600 transition-colors truncate">
                    {p.name}
                  </h3>
                </div>
                {p.description && (
                  <p className="text-sm text-gray-500 mb-3 line-clamp-2">{p.description}</p>
                )}
                <div className="flex items-center gap-4 text-xs text-gray-400">
                  <span>{p.member_count} 位成員</span>
                  {p.is_archived && <span className="text-amber-500">已封存</span>}
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
