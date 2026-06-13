import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { dailyTasksApi } from '../api/dailyTasks'
import { projectsApi } from '../api/projects'
import { useAuthStore } from '../stores/authStore'
import { toast } from '../stores/toastStore'
import { confirm } from '../stores/confirmStore'
import type { ArchiveHistoryItem, ArchiveHistoryStats, Project } from '../types'

type Tab = 'daily' | 'projects'

const STATUS_ZH: Record<string, string> = {
  pending: '待辦',
  in_progress: '進行中',
  done: '完成',
  cancelled: '已取消',
}

export default function HistoryPage() {
  const [tab, setTab] = useState<Tab>('daily')

  // ── 歷史日常任務 ──
  const [items, setItems] = useState<ArchiveHistoryItem[]>([])
  const [stats, setStats] = useState<ArchiveHistoryStats | null>(null)
  const [loading, setLoading] = useState(false)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [exporting, setExporting] = useState(false)

  // ── 封存專案 ──
  const [projects, setProjects] = useState<Project[]>([])
  const [projLoading, setProjLoading] = useState(true)
  const isAdmin = useAuthStore(s => s.user?.role === 'admin')

  const loadHistory = async () => {
    setLoading(true)
    try {
      const res = await dailyTasksApi.getArchiveHistory({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      })
      setItems(res.data.items)
      setStats(res.data.stats)
    } catch {
      toast.error('載入歷史記錄失敗')
    } finally {
      setLoading(false)
    }
  }

  const loadProjects = async () => {
    setProjLoading(true)
    try {
      const res = await projectsApi.listArchived()
      setProjects(res.data)
    } finally {
      setProjLoading(false) }
  }

  useEffect(() => { loadHistory() }, [])
  useEffect(() => { if (tab === 'projects') loadProjects() }, [tab])

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await dailyTasksApi.exportArchiveHistoryCsv({
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      })
      const url = URL.createObjectURL(new Blob([res.data], { type: 'text/csv;charset=utf-8-sig;' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `daily_history_${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('匯出失敗')
    } finally {
      setExporting(false)
    }
  }

  const handleUnarchive = async (p: Project) => {
    try {
      await projectsApi.update(p.id, { is_archived: false })
      loadProjects()
    } catch (err: any) {
      const msg = err?.response?.data?.detail
      toast.error(msg || '取消封存失敗，請重試')
    }
  }

  const handleDeleteProject = async (p: Project) => {
    if (!(await confirm({ title: '刪除專案', message: `確定永久刪除「${p.name}」？此操作無法復原。`, confirmLabel: '刪除', danger: true }))) return
    await projectsApi.delete(p.id)
    loadProjects()
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">歷史紀錄</h1>
        <p className="text-sm text-gray-500 mt-0.5">查詢已封存的日常任務與封存專案</p>
      </div>

      {/* Tab 切換 */}
      <div className="flex gap-1 border-b border-gray-200">
        <button
          onClick={() => setTab('daily')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
            tab === 'daily'
              ? 'border-primary-500 text-primary-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          歷史日常任務
        </button>
        <button
          onClick={() => setTab('projects')}
          className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
            tab === 'projects'
              ? 'border-primary-500 text-primary-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          封存專案
        </button>
      </div>

      {/* ── Tab A：歷史日常任務 ── */}
      {tab === 'daily' && (
        <div className="space-y-4">
          {/* 篩選列 */}
          <div className="card flex flex-wrap items-end gap-3">
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">開始日期</label>
              <input
                type="date"
                className="input text-sm"
                value={dateFrom}
                onChange={e => setDateFrom(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 block mb-1">結束日期</label>
              <input
                type="date"
                className="input text-sm"
                value={dateTo}
                onChange={e => setDateTo(e.target.value)}
              />
            </div>
            <button
              onClick={loadHistory}
              disabled={loading}
              className="btn-primary text-sm px-4 py-2"
            >
              {loading ? '查詢中…' : '查詢'}
            </button>
            <button
              onClick={() => { setDateFrom(''); setDateTo('') }}
              className="btn-secondary text-sm px-3 py-2"
            >
              清除
            </button>
            <div className="ml-auto">
              <button
                onClick={handleExport}
                disabled={exporting || items.length === 0}
                className="px-4 py-2 text-sm font-medium rounded-lg bg-green-50 text-green-700 border border-green-200 hover:bg-green-100 transition-colors disabled:opacity-50"
              >
                {exporting ? '匯出中…' : '⬇ 匯出 CSV'}
              </button>
            </div>
          </div>

          {/* 統計摘要 */}
          {stats && (
            <div className="grid grid-cols-3 gap-3">
              <div className="card text-center">
                <p className="text-2xl font-bold text-gray-800">{stats.total_records}</p>
                <p className="text-xs text-gray-500 mt-0.5">封存筆數</p>
              </div>
              <div className="card text-center">
                <p className="text-2xl font-bold text-gray-800">{stats.total_work_minutes}</p>
                <p className="text-xs text-gray-500 mt-0.5">總工時（分鐘）</p>
              </div>
              <div className="card text-center">
                <p className="text-2xl font-bold text-primary-600">{stats.total_work_hours}</p>
                <p className="text-xs text-gray-500 mt-0.5">總工時（小時）</p>
              </div>
            </div>
          )}

          {/* 資料列表 */}
          {loading ? (
            <div className="text-center py-16 text-gray-400">載入中…</div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400 space-y-2">
              <span className="text-4xl">📦</span>
              <p className="text-sm">沒有符合條件的歷史記錄</p>
            </div>
          ) : (
            <div className="card overflow-hidden p-0">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-100">
                  <tr>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-600">日期</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-600">標題</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-600">狀態</th>
                    <th className="text-right px-4 py-2.5 font-medium text-gray-600">工時(分)</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-600">關聯專案</th>
                    <th className="text-left px-4 py-2.5 font-medium text-gray-600">封存時間</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {items.map(item => (
                    <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-2.5 text-gray-500 whitespace-nowrap">{item.date}</td>
                      <td className="px-4 py-2.5">
                        <p className="font-medium text-gray-800 truncate max-w-xs">{item.title}</p>
                        {item.linked_task_title && (
                          <p className="text-xs text-gray-400 mt-0.5 truncate">↳ {item.linked_task_title}</p>
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${
                          item.status === 'done'
                            ? 'bg-green-100 text-green-700'
                            : item.status === 'cancelled'
                            ? 'bg-gray-100 text-gray-500'
                            : 'bg-blue-100 text-blue-700'
                        }`}>
                          {STATUS_ZH[item.status] ?? item.status}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right text-gray-700 font-medium">
                        {item.work_minutes > 0 ? item.work_minutes : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-2.5 text-gray-500 text-xs">
                        {item.linked_project_id ? (
                          <Link
                            to={`/projects/${item.linked_project_id}`}
                            className="text-primary-500 hover:underline"
                          >
                            {item.linked_project_name}
                          </Link>
                        ) : '—'}
                      </td>
                      <td className="px-4 py-2.5 text-gray-400 text-xs whitespace-nowrap">
                        {new Date(item.archived_at).toLocaleDateString('zh-TW')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── Tab B：封存專案 ── */}
      {tab === 'projects' && (
        <div>
          {projLoading ? (
            <div className="text-center py-20 text-gray-400">載入中…</div>
          ) : projects.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-gray-400 space-y-2">
              <span className="text-4xl">🗄️</span>
              <p className="text-sm">目前沒有封存的專案</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((p) => (
                <div key={p.id} className="card group relative opacity-75 hover:opacity-100 transition-opacity">
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-3 h-3 rounded-full flex-shrink-0 grayscale" style={{ backgroundColor: p.color }} />
                    <h3 className="font-semibold text-gray-700 truncate pr-2">{p.name}</h3>
                  </div>
                  {p.description && (
                    <p className="text-sm text-gray-400 mb-2 line-clamp-2">{p.description}</p>
                  )}
                  <div className="flex items-center justify-between text-xs text-gray-400 mb-3">
                    <span>{p.member_count} 位成員</span>
                    {p.end_date && <span>截止 {p.end_date}</span>}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleUnarchive(p)}
                      className="flex-1 text-xs py-1.5 rounded-lg bg-primary-50 text-primary-600 hover:bg-primary-100 font-medium transition-colors"
                    >
                      取消封存
                    </button>
                    <Link
                      to={`/projects/${p.id}`}
                      className="text-xs px-3 py-1.5 rounded-lg bg-gray-50 text-gray-500 hover:bg-gray-100 transition-colors"
                    >
                      查看
                    </Link>
                    {isAdmin && (
                      <button
                        onClick={() => handleDeleteProject(p)}
                        className="text-xs px-3 py-1.5 rounded-lg bg-red-50 text-red-500 hover:bg-red-100 transition-colors"
                      >
                        刪除
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
