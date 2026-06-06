import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { dashboardApi, type DashboardSummary, type DashboardTask, type DeadlineProject } from '../api/dashboard'
import { announcementsApi } from '../api/announcements'
import { workloadApi } from '../api/workload'
import { useAuthStore } from '../stores/authStore'

const PRIORITY_COLOR: Record<string, string> = {
  urgent: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  medium: 'bg-blue-100 text-blue-700',
  low: 'bg-gray-100 text-gray-500',
}
const PRIORITY_LABEL: Record<string, string> = {
  urgent: '緊急', high: '高', medium: '中', low: '低',
}

function TaskRow({ t }: { t: DashboardTask }) {
  const isOverdue = t.due_date && new Date(t.due_date) < new Date()
  const daysLeft = t.due_date
    ? Math.ceil((new Date(t.due_date).getTime() - Date.now()) / 86400000)
    : null

  return (
    <li>
      <Link
        to={`/projects/${t.project_id}`}
        className="flex items-center gap-2 p-2 rounded-lg hover:bg-gray-50 transition-colors group"
      >
        <span className={`text-xs px-2 py-0.5 rounded-full flex-shrink-0 ${PRIORITY_COLOR[t.priority] ?? 'bg-gray-100 text-gray-500'}`}>
          {PRIORITY_LABEL[t.priority] ?? t.priority}
        </span>
        <span className="flex-1 text-sm text-gray-700 group-hover:text-primary-600 truncate">{t.title}</span>
        {t.due_date && (
          <span className={`text-xs flex-shrink-0 ${isOverdue ? 'text-red-500 font-medium' : daysLeft !== null && daysLeft <= 3 ? 'text-amber-500 font-medium' : 'text-gray-400'}`}>
            {isOverdue ? `逾期 ${Math.abs(daysLeft!)} 天` : daysLeft === 0 ? '今天到期' : `${daysLeft} 天後`}
          </span>
        )}
      </Link>
    </li>
  )
}

function DeadlineCard({ p }: { p: DeadlineProject }) {
  const pct = p.task_total === 0 ? 0 : Math.round((p.task_done / p.task_total) * 100)
  const urgent = p.days_left <= 3
  const warning = p.days_left <= 7

  return (
    <Link to={`/projects/${p.id}`} className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-50 group">
      <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: p.color }} />
      <span className="flex-1 text-sm text-gray-700 group-hover:text-primary-600 truncate">{p.name}</span>
      <div className="flex items-center gap-2 flex-shrink-0">
        <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full ${pct === 100 ? 'bg-green-400' : 'bg-primary-400'}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="text-xs text-gray-400 w-8">{pct}%</span>
        <span className={`text-xs font-medium w-16 text-right ${urgent ? 'text-red-500' : warning ? 'text-amber-500' : 'text-gray-400'}`}>
          {p.days_left < 0 ? `逾期 ${Math.abs(p.days_left)} 天` : p.days_left === 0 ? '今天截止' : `剩 ${p.days_left} 天`}
        </span>
      </div>
    </Link>
  )
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [announcement, setAnnouncement] = useState<any | null>(null)
  const [workload, setWorkload] = useState<any | null>(null)
  const [loading, setLoading] = useState(true)
  const currentUser = useAuthStore(s => s.user)
  const isAdmin = currentUser?.role === 'admin'

  const loadAll = async () => {
    setLoading(true)
    try {
      const sRes = await dashboardApi.summary()
      setSummary(sRes.data)

      announcementsApi.list()
        .then(r => {
          const active = (r.data ?? []).filter((a: any) => a.is_active)
          if (active.length > 0) setAnnouncement(active[0])
        })
        .catch(() => {})

      if (currentUser?.role === 'admin') {
        workloadApi.get('week')
          .then(r => setWorkload(r.data))
          .catch(() => {})
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadAll() }, [])

  const dismissAnnouncement = async () => {
    if (!announcement) return
    await announcementsApi.markRead(announcement.id).catch(() => {})
    setAnnouncement(null)
  }

  if (loading) return <div className="text-center py-20 text-gray-400">載入中…</div>

  const kpi = summary?.kpi
  const todayDue = summary?.today_due ?? []
  const actionRequired = summary?.action_required ?? []
  const upcoming = summary?.upcoming ?? []
  const deadlineProjects = summary?.deadline_projects ?? []

  return (
    <div className="max-w-6xl mx-auto space-y-5">

      {/* 公告橫幅 */}
      {announcement && (
        <div className="flex items-start gap-3 bg-blue-50 border border-blue-200 rounded-xl px-4 py-3">
          <span className="text-blue-500 text-lg flex-shrink-0">📢</span>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-blue-800">{announcement.title}</p>
            <p className="text-sm text-blue-700 mt-0.5 line-clamp-2">{announcement.content}</p>
          </div>
          <button
            onClick={dismissAnnouncement}
            className="text-blue-400 hover:text-blue-600 text-lg flex-shrink-0 leading-none"
            title="關閉"
          >×</button>
        </div>
      )}

      {/* KPI */}
      {kpi && (
        <div className="grid grid-cols-3 gap-3">
          <div className="card text-center py-3">
            <p className="text-2xl font-bold text-primary-600">{kpi.todo}</p>
            <p className="text-xs text-gray-500 mt-0.5">未完成任務</p>
          </div>
          <div className="card text-center py-3">
            <p className={`text-2xl font-bold ${kpi.overdue > 0 ? 'text-red-600' : 'text-gray-400'}`}>
              {kpi.overdue}
            </p>
            <p className="text-xs text-gray-500 mt-0.5">已逾期</p>
          </div>
          <div className="card text-center py-3">
            <p className="text-2xl font-bold text-green-600">{kpi.completed_this_week}</p>
            <p className="text-xs text-gray-500 mt-0.5">本週已完成</p>
          </div>
        </div>
      )}

      {/* 今日到期 + 需我處理 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">今日到期</h2>
          {todayDue.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">今天沒有到期任務 🎉</p>
          ) : (
            <ul className="space-y-1 max-h-52 overflow-y-auto">
              {todayDue.map(t => <TaskRow key={t.id} t={t} />)}
            </ul>
          )}
        </div>
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">需我處理</h2>
          {actionRequired.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">沒有待處理任務 🎉</p>
          ) : (
            <ul className="space-y-1 max-h-52 overflow-y-auto">
              {actionRequired.map(t => <TaskRow key={t.id} t={t} />)}
            </ul>
          )}
        </div>
      </div>

      {/* 即將到期（7天內）+ 專案截止預警 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 即將到期任務 */}
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700">即將到期（7 天內）</h2>
            {upcoming.length > 0 && (
              <span className="text-xs bg-amber-100 text-amber-600 px-2 py-0.5 rounded-full">{upcoming.length} 件</span>
            )}
          </div>
          {upcoming.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">7 天內沒有到期任務</p>
          ) : (
            <ul className="space-y-1 max-h-52 overflow-y-auto">
              {upcoming.map(t => <TaskRow key={t.id} t={t} />)}
            </ul>
          )}
        </div>

        {/* 專案截止預警 */}
        <div className="card">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700">專案截止預警</h2>
            <Link to="/overview" className="text-xs text-primary-500 hover:text-primary-700">
              查看所有專案 →
            </Link>
          </div>
          {deadlineProjects.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-6">近期無專案截止</p>
          ) : (
            <div className="space-y-1 max-h-52 overflow-y-auto">
              {deadlineProjects.map(p => <DeadlineCard key={p.id} p={p} />)}
            </div>
          )}
        </div>
      </div>

      {/* 團隊工作量（admin 限定） */}
      {isAdmin && workload?.members && workload.members.length > 0 && (
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">本週團隊工作量</h2>
          <div className="space-y-2">
            {workload.members.slice(0, 8).map((m: any) => {
              const overloaded = m.task_count > 5
              return (
                <div key={m.user_id} className="flex items-center gap-3">
                  <span className="text-sm text-gray-700 w-24 truncate flex-shrink-0">{m.username}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${overloaded ? 'bg-red-400' : 'bg-primary-400'}`}
                      style={{ width: `${Math.min((m.task_count / 10) * 100, 100)}%` }}
                    />
                  </div>
                  <span className={`text-xs w-12 text-right flex-shrink-0 ${overloaded ? 'text-red-500 font-medium' : 'text-gray-500'}`}>
                    {m.task_count} 件{overloaded ? ' ⚠️' : ''}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
