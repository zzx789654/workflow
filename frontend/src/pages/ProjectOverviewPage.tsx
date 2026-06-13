import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { projectsApi } from '../api/projects'
import { useAuthStore } from '../stores/authStore'
import { toast } from '../stores/toastStore'
import { confirm } from '../stores/confirmStore'
import type { ProjectOverviewItem } from '../types'

const COLORS = ['#6366f1', '#0ea5e9', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']

function progressPct(item: ProjectOverviewItem) {
  if (item.task_total === 0) return 0
  return Math.round((item.task_done / item.task_total) * 100)
}

function DaysLeft({ endDate }: { endDate: string | null }) {
  if (!endDate) return null
  const diff = Math.ceil((new Date(endDate).getTime() - Date.now()) / 86400000)
  if (diff < 0) return <span className="text-xs text-red-500 font-medium">已逾期 {Math.abs(diff)} 天</span>
  if (diff <= 7) return <span className="text-xs text-red-400">剩 {diff} 天</span>
  if (diff <= 14) return <span className="text-xs text-amber-500">剩 {diff} 天</span>
  return <span className="text-xs text-gray-400">截止 {endDate}</span>
}

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${pct === 100 ? 'bg-green-400' : 'bg-primary-400'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-400 w-8 text-right">{pct}%</span>
    </div>
  )
}

export default function ProjectOverviewPage() {
  const [items, setItems] = useState<ProjectOverviewItem[]>([])
  const [loading, setLoading] = useState(true)
  const currentUser = useAuthStore(s => s.user)
  const navigate = useNavigate()
  const isAdmin = currentUser?.role === 'admin'
  const canCreate = currentUser?.role === 'admin' || currentUser?.role === 'member'

  const [showCreate, setShowCreate] = useState(false)
  const [formName, setFormName] = useState('')
  const [formStart, setFormStart] = useState('')
  const [formEnd, setFormEnd] = useState('')
  const [formColor, setFormColor] = useState(COLORS[0])
  const [creating, setCreating] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const r = await projectsApi.overview()
      setItems(r.data)
    } catch {
      toast.error('載入失敗')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleArchive = async (id: string, archive: boolean) => {
    try {
      await projectsApi.update(id, { is_archived: archive })
      toast.success(archive ? '已封存' : '已取消封存')
      load()
    } catch (err: any) {
      const msg = err?.response?.data?.detail
      if (msg) toast.error(msg)
      else toast.error(archive ? '封存失敗，請重試' : '取消封存失敗，請重試')
    }
  }

  const handleDelete = async (id: string, name: string) => {
    if (!(await confirm({ title: '刪除專案', message: `確定永久刪除「${name}」？此操作無法復原。`, confirmLabel: '刪除', danger: true }))) return
    await projectsApi.delete(id)
    toast.success('已刪除')
    load()
  }

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formName.trim()) return
    setCreating(true)
    try {
      const res = await projectsApi.create({
        name: formName.trim(),
        color: formColor,
        start_date: formStart || undefined,
        end_date: formEnd || undefined,
      })
      setShowCreate(false)
      setFormName(''); setFormStart(''); setFormEnd(''); setFormColor(COLORS[0])
      toast.success('專案已建立')
      navigate(`/projects/${res.data.id}`)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? '建立失敗')
    } finally { setCreating(false) }
  }

  if (loading) return <div className="text-center py-20 text-gray-400">載入中…</div>

  const active = items.filter(i => !i.is_archived)
  const archived = items.filter(i => i.is_archived)

  return (
    <div className="max-w-5xl mx-auto">
      {/* 標題列 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">專案總覽</h1>
          <p className="text-sm text-gray-400 mt-0.5">{active.length} 個進行中・{archived.length} 個已封存</p>
        </div>
        {canCreate && (
          <button onClick={() => setShowCreate(true)} className="btn-primary text-sm">
            + 新增專案
          </button>
        )}
      </div>

      {/* 欄標題 */}
      {items.length > 0 && (
        <div className="flex items-center gap-3 px-4 mb-1 text-xs text-gray-400">
          <div className="w-3 flex-shrink-0" />
          <div className="flex-1">專案名稱</div>
          <div className="w-40 flex-shrink-0">完成度</div>
          <div className="w-16 text-right flex-shrink-0">任務</div>
          <div className="w-10 text-right flex-shrink-0">成員</div>
          <div className="w-28 text-right flex-shrink-0">截止日</div>
          <div className="w-20 flex-shrink-0" />
        </div>
      )}

      {/* 進行中專案 */}
      {active.length === 0 && archived.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400 space-y-2">
          <span className="text-4xl">📁</span>
          <p className="text-sm">還沒有任何專案</p>
          {canCreate && (
            <button onClick={() => setShowCreate(true)} className="btn-primary text-sm mt-2">
              建立第一個專案
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="space-y-2 mb-6">
            {active.map(item => {
              const pct = progressPct(item)
              return (
                <div key={item.id} className="flex items-center gap-3 px-4 py-3 bg-white border border-gray-200 rounded-xl hover:border-gray-300 group transition-colors">
                  <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
                  <Link to={`/projects/${item.id}`} className="flex-1 min-w-0">
                    <span className="font-semibold text-gray-800 hover:text-primary-600 truncate block">
                      {item.name}
                    </span>
                    {item.description && (
                      <span className="text-xs text-gray-400 truncate block">{item.description}</span>
                    )}
                  </Link>
                  <div className="w-40 flex-shrink-0">
                    <ProgressBar pct={pct} />
                  </div>
                  <span className="text-xs text-gray-400 w-16 text-right flex-shrink-0">
                    {item.task_done}/{item.task_total} 件
                  </span>
                  <span className="text-xs text-gray-400 w-10 text-right flex-shrink-0">
                    {item.member_count} 人
                  </span>
                  <div className="w-28 text-right flex-shrink-0">
                    <DaysLeft endDate={item.end_date} />
                  </div>
                  <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1 flex-shrink-0 w-20 justify-end">
                    {(isAdmin || ['owner', 'manager'].includes(item.my_role ?? '')) && (
                      <button
                        onClick={() => handleArchive(item.id, true)}
                        className="text-xs px-2 py-0.5 rounded bg-amber-50 text-amber-600 hover:bg-amber-100"
                      >封存</button>
                    )}
                    {(isAdmin || item.my_role === 'owner') && (
                      <button
                        onClick={() => handleDelete(item.id, item.name)}
                        className="text-xs px-2 py-0.5 rounded bg-red-50 text-red-500 hover:bg-red-100"
                      >刪除</button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>

          {/* 封存專案（折疊） */}
          {archived.length > 0 && (
            <details className="group">
              <summary className="cursor-pointer text-sm text-gray-400 hover:text-gray-600 mb-3 list-none flex items-center gap-2">
                <span className="group-open:rotate-90 transition-transform inline-block">▶</span>
                封存專案（{archived.length}）
              </summary>
              <div className="space-y-2 opacity-60">
                {archived.map(item => {
                  const pct = progressPct(item)
                  return (
                    <div key={item.id} className="flex items-center gap-3 px-4 py-3 bg-white border border-gray-100 rounded-xl hover:border-gray-200 group transition-colors">
                      <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
                      <Link to={`/projects/${item.id}`} className="flex-1 min-w-0">
                        <span className="font-semibold text-gray-500 hover:text-primary-600 truncate block">{item.name}</span>
                      </Link>
                      <div className="w-40 flex-shrink-0">
                        <ProgressBar pct={pct} />
                      </div>
                      <span className="text-xs text-gray-400 w-16 text-right flex-shrink-0">
                        {item.task_done}/{item.task_total} 件
                      </span>
                      <span className="text-xs text-gray-400 w-10 text-right flex-shrink-0">
                        {item.member_count} 人
                      </span>
                      <div className="w-28 text-right flex-shrink-0">
                        <DaysLeft endDate={item.end_date} />
                      </div>
                      <div className="opacity-0 group-hover:opacity-100 transition-opacity flex gap-1 flex-shrink-0 w-20 justify-end">
                        {(isAdmin || ['owner', 'manager'].includes(item.my_role ?? '')) && (
                          <button
                            onClick={() => handleArchive(item.id, false)}
                            className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600 hover:bg-gray-200"
                          >取消封存</button>
                        )}
                        {(isAdmin || item.my_role === 'owner') && (
                          <button
                            onClick={() => handleDelete(item.id, item.name)}
                            className="text-xs px-2 py-0.5 rounded bg-red-50 text-red-500 hover:bg-red-100"
                          >刪除</button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </details>
          )}
        </>
      )}

      {/* 建立專案 Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
            <h2 className="text-base font-semibold text-gray-800 mb-4">新增專案</h2>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-700">專案名稱 *</label>
                <input
                  autoFocus
                  className="input w-full mt-1"
                  placeholder="輸入專案名稱"
                  value={formName}
                  onChange={e => setFormName(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700 block mb-1">顏色</label>
                <div className="flex gap-2">
                  {COLORS.map(c => (
                    <button
                      key={c} type="button"
                      onClick={() => setFormColor(c)}
                      className={`w-6 h-6 rounded-full border-2 transition-transform ${formColor === c ? 'border-gray-800 scale-125' : 'border-transparent'}`}
                      style={{ backgroundColor: c }}
                    />
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium text-gray-700">開始日期</label>
                  <input className="input w-full mt-1" type="date" value={formStart}
                    onChange={e => setFormStart(e.target.value)} />
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">截止日期</label>
                  <input className="input w-full mt-1" type="date" value={formEnd}
                    min={formStart} onChange={e => setFormEnd(e.target.value)} />
                </div>
              </div>
              <div className="flex gap-3 pt-1">
                <button type="submit" disabled={creating} className="btn-primary flex-1">
                  {creating ? '建立中…' : '建立專案'}
                </button>
                <button type="button" onClick={() => setShowCreate(false)} className="btn-secondary">取消</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
