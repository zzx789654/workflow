import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { format } from 'date-fns'
import { dailyTasksApi } from '../api/dailyTasks'
import { confirm } from '../stores/confirmStore'
import type { DailyTask, DailyTaskStatus } from '../types'
import TaskLinkPicker from '../components/ui/TaskLinkPicker'

// ─── constants ───────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<DailyTaskStatus, string> = {
  pending: '待辦', in_progress: '進行中', done: '完成', cancelled: '已取消',
}

const STATUS_BADGE: Record<DailyTaskStatus, string> = {
  pending:     'bg-amber-100  text-amber-700  border-amber-300',
  in_progress: 'bg-blue-100   text-blue-700   border-blue-300',
  done:        'bg-emerald-100 text-emerald-700 border-emerald-300',
  cancelled:   'bg-red-100    text-red-600    border-red-300',
}

const STATUS_FILTER_ACTIVE: Record<DailyTaskStatus, string> = {
  pending:     'bg-amber-500  text-white border-amber-500',
  in_progress: 'bg-blue-500   text-white border-blue-500',
  done:        'bg-emerald-500 text-white border-emerald-500',
  cancelled:   'bg-red-500    text-white border-red-500',
}

const NOTIFY_OPTIONS = [
  { value: '', label: '不需要' },
  { value: '1', label: '1 天前' },
  { value: '3', label: '3 天前' },
  { value: '7', label: '7 天前' },
]

const PAGE_SIZE = 50

const today = () => format(new Date(), 'yyyy-MM-dd')
const todayDate = () => `${format(new Date(), 'yyyy-MM-dd')}T00:00:00`

function computeNotifyAt(date: string, daysBefore: string): string | undefined {
  if (!date || !daysBefore) return undefined
  const d = new Date(date)
  d.setDate(d.getDate() - parseInt(daysBefore))
  return `${format(d, 'yyyy-MM-dd')}T09:00:00`
}

type LinkVal = { taskId: string; taskTitle: string; projectName: string } | null

// ─── LabelInput ───────────────────────────────────────────────────────────────
// Comma-separated tag input with dropdown suggestions from existing labels.

function LabelInput({
  value, onChange, suggestions, placeholder = '標籤（逗號分隔）', className = '',
}: {
  value: string
  onChange: (v: string) => void
  suggestions: string[]
  placeholder?: string
  className?: string
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Current token being typed (after the last comma)
  const currentToken = value.split(',').pop()?.trimStart() ?? ''

  const filtered = useMemo(() => {
    if (!currentToken) return suggestions
    return suggestions.filter(s => s.toLowerCase().includes(currentToken.toLowerCase()))
  }, [currentToken, suggestions])

  // Close when clicking outside
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const selectSuggestion = (label: string) => {
    const parts = value.split(',').map(s => s.trim()).filter(Boolean)
    // Replace the last (in-progress) token with the selected suggestion
    parts.pop()
    parts.push(label)
    onChange(parts.join(', ') + ', ')
    setOpen(false)
  }

  return (
    <div ref={containerRef} className="relative">
      <input
        className={className}
        placeholder={placeholder}
        value={value}
        onChange={e => { onChange(e.target.value); setOpen(true) }}
        onFocus={() => setOpen(true)}
        autoComplete="off"
      />
      {open && filtered.length > 0 && (
        <div className="absolute left-0 top-full mt-1 z-30 bg-white border border-gray-200 rounded-lg shadow-lg min-w-full max-h-40 overflow-y-auto">
          {filtered.map(label => (
            <button
              key={label}
              type="button"
              onMouseDown={e => { e.preventDefault(); selectSuggestion(label) }}
              className="w-full text-left px-3 py-1.5 text-sm text-gray-700 hover:bg-indigo-50 hover:text-indigo-700 flex items-center gap-2"
            >
              <span className="text-xs bg-indigo-50 text-indigo-600 px-1.5 py-0.5 rounded-full border border-indigo-100">{label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── DailyTaskModal ───────────────────────────────────────────────────────────

function DailyTaskModal({
  task, onClose, onSave, labelSuggestions,
}: {
  task?: DailyTask | null
  onClose: () => void
  onSave: (keepOpen?: boolean) => void
  labelSuggestions: string[]
}) {
  const isNew = !task
  const [title, setTitle] = useState(task?.title ?? '')
  const [description, setDescription] = useState(task?.description ?? '')
  const [status, setStatus] = useState<DailyTaskStatus>(task?.status ?? 'pending')
  const [date, setDate] = useState(task?.date ?? today())
  const [notifyDays, setNotifyDays] = useState<string>(() => {
    if (!task?.notify_at || !task?.date) return ''
    const notifyDate = new Date(task.notify_at.slice(0, 10))
    const dueDate = new Date(task.date)
    const diff = Math.round((dueDate.getTime() - notifyDate.getTime()) / 86400000)
    if (diff === 1) return '1'
    if (diff === 3) return '3'
    if (diff === 7) return '7'
    return ''
  })
  const [workHours, setWorkHours] = useState(
    task?.work_minutes ? Math.round(task.work_minutes / 60 * 10) / 10 : 0
  )
  const [labelsStr, setLabelsStr] = useState(task?.labels.join(', ') ?? '')
  const [linkVal, setLinkVal] = useState<LinkVal>(
    task?.linked_task
      ? { taskId: task.linked_task.id, taskTitle: task.linked_task.title, projectName: task.linked_task.project_name }
      : null
  )
  const [loading, setLoading] = useState(false)
  const [continuous, setContinuous] = useState(false)
  const [addedCount, setAddedCount] = useState(0)
  const titleRef = useRef<HTMLInputElement>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    const labels = labelsStr.split(',').map(s => s.trim()).filter(Boolean)
    const notify_at = computeNotifyAt(date, notifyDays)
    const terminal = status === 'done' || status === 'cancelled'
    const wasTerminal = task?.status === 'done' || task?.status === 'cancelled'
    const ended_at = terminal && !wasTerminal ? todayDate() : undefined
    const payload = {
      title, description: description || undefined, status, progress: 0, date,
      work_minutes: Math.round(workHours * 60), labels, notify_at,
      started_at: undefined, ended_at,
      linked_task_id: linkVal?.taskId ?? null,
    }
    try {
      if (task) {
        await dailyTasksApi.update(task.id, payload)
        onSave()
      } else {
        await dailyTasksApi.create({ ...payload, date })
        if (continuous) {
          setTitle('')
          setLinkVal(null)
          setAddedCount(c => c + 1)
          onSave(true)
          setTimeout(() => titleRef.current?.focus(), 50)
        } else { onSave() }
      }
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg" onClick={e => e.stopPropagation()}>
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-gray-900">
              {task ? '編輯作業' : '新增日常作業'}
              {addedCount > 0 && <span className="ml-2 text-sm font-normal text-green-600">已新增 {addedCount} 筆</span>}
            </h2>
          </div>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="text-sm font-medium text-gray-700">標題</label>
              <input ref={titleRef} className="input mt-1 w-full" value={title}
                onChange={e => setTitle(e.target.value)} required autoFocus />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">說明</label>
              <textarea className="input mt-1 w-full resize-none" rows={2} value={description}
                onChange={e => setDescription(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-gray-700">日期</label>
                <input className="input mt-1 w-full" type="date" value={date}
                  onChange={e => setDate(e.target.value)} required />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">狀態</label>
                <select className="input mt-1 w-full" value={status}
                  onChange={e => setStatus(e.target.value as DailyTaskStatus)}>
                  {(Object.keys(STATUS_LABELS) as DailyTaskStatus[]).map(s =>
                    <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-gray-700">通知時間</label>
                <select className="input mt-1 w-full" value={notifyDays}
                  onChange={e => setNotifyDays(e.target.value)}>
                  {NOTIFY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">工作時數</label>
                <input className="input mt-1 w-full" type="number" min={0} step={0.5}
                  value={workHours} onChange={e => setWorkHours(+e.target.value)} placeholder="例：1.5" />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">標籤（逗號分隔）</label>
              <LabelInput
                value={labelsStr}
                onChange={setLabelsStr}
                suggestions={labelSuggestions}
                placeholder="例：開發, 會議, 文件"
                className="input w-full"
              />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-1">關聯專案任務</label>
              <TaskLinkPicker value={linkVal} onChange={setLinkVal} />
            </div>
            {isNew && (
              <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
                <input type="checkbox" checked={continuous} onChange={e => setContinuous(e.target.checked)} className="rounded" />
                連續輸入模式（新增後保持開啟，快速建立多筆）
              </label>
            )}
            <div className="flex gap-3 pt-2">
              <button type="submit" disabled={loading} className="btn-primary flex-1">
                {loading ? '儲存中…' : continuous ? '新增並繼續' : '儲存'}
              </button>
              <button type="button" onClick={onClose} className="btn-secondary flex-1">
                {addedCount > 0 ? `完成（已新增 ${addedCount} 筆）` : '取消'}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

// ─── ImportResult ─────────────────────────────────────────────────────────────

interface ImportResult { created: number; errors: string[]; total_rows: number }

// ─── TaskRow ──────────────────────────────────────────────────────────────────

function TaskRow({ task, onUpdated, onDeleted, onEdit }: {
  task: DailyTask
  onUpdated: (id: string) => void
  onDeleted: (id: string) => void
  onEdit: () => void
}) {
  const [hours, setHours] = useState(task.work_minutes ? Math.round(task.work_minutes / 60 * 10) / 10 : 0)
  const [saving, setSaving] = useState(false)
  const [linking, setLinking] = useState(false)

  const handleStatusChange = async (status: DailyTaskStatus) => {
    const terminal = status === 'done' || status === 'cancelled'
    const wasTerminal = task.status === 'done' || task.status === 'cancelled'
    const ended_at = terminal && !wasTerminal ? todayDate() : undefined
    await dailyTasksApi.update(task.id, { status, ended_at } as any)
    onUpdated(task.id)
  }

  const handleHoursBlur = async () => {
    const newMinutes = Math.round(hours * 60)
    if (newMinutes === task.work_minutes) return
    setSaving(true)
    try {
      await dailyTasksApi.update(task.id, { work_minutes: newMinutes } as any)
      onUpdated(task.id)
    } finally { setSaving(false) }
  }

  const handleLinkChange = async (val: LinkVal) => {
    await dailyTasksApi.update(task.id, { linked_task_id: val?.taskId ?? null } as any)
    onUpdated(task.id)
    setLinking(false)
  }

  const isDone = task.status === 'done'
  const isCancelled = task.status === 'cancelled'
  const dimmed = isDone || isCancelled

  return (
    <div className={`bg-white rounded-xl border px-4 py-3 hover:shadow-sm transition-shadow ${
      dimmed ? 'border-gray-100 opacity-55' : 'border-gray-200'
    }`}>
      <div className="flex items-start gap-3">
        {/* 狀態下拉 */}
        <div className="flex-shrink-0 mt-0.5">
          <select
            value={task.status}
            onChange={e => handleStatusChange(e.target.value as DailyTaskStatus)}
            className={`text-xs px-2.5 py-1 rounded-full font-semibold border cursor-pointer outline-none ${STATUS_BADGE[task.status]}`}
          >
            {(Object.keys(STATUS_LABELS) as DailyTaskStatus[]).map(s =>
              <option key={s} value={s}>{STATUS_LABELS[s]}</option>
            )}
          </select>
        </div>

        {/* 標題 + 說明 + 標籤 + 關聯 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <p className={`font-semibold text-base leading-snug ${
              dimmed ? 'line-through text-gray-400' : 'text-gray-900'
            }`}>
              {task.title}
            </p>
            <span className="text-xs text-gray-500 flex-shrink-0">{task.date}</span>
            {task.ended_at && (isDone || isCancelled) && (
              <span className={`text-xs flex-shrink-0 ${isDone ? 'text-emerald-500' : 'text-red-400'}`}>
                {isDone ? '完成於' : '取消於'} {task.ended_at.slice(0, 10)}
              </span>
            )}
          </div>
          {task.description && (
            <p className="text-sm text-gray-500 mt-0.5 line-clamp-1">{task.description}</p>
          )}

          {/* 標籤 + 關聯 */}
          <div className="flex items-center gap-2 mt-1.5 flex-wrap">
            {task.labels.map(l => (
              <span key={l} className="text-xs bg-indigo-50 text-indigo-600 font-medium px-2 py-0.5 rounded-full border border-indigo-100">{l}</span>
            ))}
            {task.linked_task ? (
              <span className="inline-flex items-center gap-1 text-xs bg-violet-50 text-violet-700 font-medium px-2 py-0.5 rounded-full border border-violet-100">
                🔗 {task.linked_task.project_name} → {task.linked_task.title}
                <button
                  type="button"
                  onClick={() => handleLinkChange(null)}
                  className="ml-0.5 text-violet-300 hover:text-red-400 leading-none"
                  title="移除關聯"
                >✕</button>
              </span>
            ) : (
              linking ? (
                <div className="w-56">
                  <TaskLinkPicker value={null} onChange={v => { handleLinkChange(v) }} />
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setLinking(true)}
                  className="text-xs text-gray-500 hover:text-indigo-500 transition-colors"
                  title="關聯專案任務"
                >+ 關聯任務</button>
              )
            )}
          </div>
        </div>

        {/* 工時 inline 輸入 */}
        <div className="flex items-center gap-1 flex-shrink-0" title="工作時數">
          <input
            type="number"
            min={0}
            step={0.5}
            value={hours}
            onChange={e => setHours(+e.target.value)}
            onBlur={handleHoursBlur}
            className={`w-14 text-sm text-center border rounded-lg px-1 py-1 outline-none focus:border-primary-400 transition-colors ${saving ? 'opacity-50' : 'border-gray-200'}`}
          />
          <span className="text-xs text-gray-400">h</span>
        </div>

        {/* 操作 */}
        <div className="flex gap-2 flex-shrink-0">
          <button className="text-xs text-blue-500 hover:text-blue-700 py-1" onClick={onEdit}>編輯</button>
          <button
            className="text-xs text-red-400 hover:text-red-600 py-1"
            onClick={async () => {
              if (!(await confirm({ title: '刪除作業', message: '確定刪除此日常作業？', confirmLabel: '刪除', danger: true }))) return
              await dailyTasksApi.delete(task.id)
              onDeleted(task.id)
            }}
          >刪除</button>
        </div>
      </div>
    </div>
  )
}

// ─── InlineAddForm ────────────────────────────────────────────────────────────

function InlineAddForm({ onAdded, labelSuggestions }: { onAdded: () => void; labelSuggestions: string[] }) {
  const [title, setTitle] = useState('')
  const [labelsStr, setLabelsStr] = useState('')
  const [linkVal, setLinkVal] = useState<LinkVal>(null)
  const [loading, setLoading] = useState(false)
  const titleRef = useRef<HTMLInputElement>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    setLoading(true)
    try {
      await dailyTasksApi.create({
        title: title.trim(),
        status: 'pending',
        progress: 0,
        date: today(),
        work_minutes: 0,
        labels: labelsStr.split(',').map(s => s.trim()).filter(Boolean),
        linked_task_id: linkVal?.taskId ?? null,
      })
      setTitle('')
      setLabelsStr('')
      setLinkVal(null)
      onAdded()
      titleRef.current?.focus()
    } finally { setLoading(false) }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white border border-dashed border-gray-300 rounded-xl px-4 py-3 mb-4 hover:border-primary-400 transition-colors">
      <div className="flex gap-2 items-center">
        <input
          ref={titleRef}
          className="flex-1 text-sm outline-none placeholder-gray-400 bg-transparent text-gray-800"
          placeholder="新增作業…"
          value={title}
          onChange={e => setTitle(e.target.value)}
          autoFocus
        />
        <LabelInput
          value={labelsStr}
          onChange={setLabelsStr}
          suggestions={labelSuggestions}
          placeholder="標籤（逗號分隔）"
          className="w-44 text-xs border border-gray-200 rounded-lg px-2 py-1 outline-none focus:border-primary-400 text-gray-700 placeholder-gray-300"
        />
        <button
          type="submit"
          disabled={loading || !title.trim()}
          className="btn-primary text-sm px-4 flex-shrink-0"
        >
          {loading ? '…' : '新增'}
        </button>
      </div>
      <div className="mt-2">
        <TaskLinkPicker value={linkVal} onChange={setLinkVal} />
      </div>
    </form>
  )
}

// ─── DailyTaskPage ────────────────────────────────────────────────────────────

export default function DailyTaskPage() {
  const [allTasks, setAllTasks] = useState<DailyTask[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [total, setTotal] = useState(0)
  const [filterLabel, setFilterLabel] = useState('')
  const [filterStatus, setFilterStatus] = useState<DailyTaskStatus | null>(null)
  const [editing, setEditing] = useState<DailyTask | null>(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  // 逐頁拉取游標：避免並發載入造成重複頁；以 ref 持有以利 observer 取最新值
  const loadingMoreRef = useRef(false)

  // 重新載入第一頁（篩選變更或匯入後）
  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await dailyTasksApi.list({
        label: filterLabel || undefined,
        limit: PAGE_SIZE,
        offset: 0,
      })
      setAllTasks(res.data)
      setTotal(Number(res.headers['x-total-count'] ?? res.data.length))
    } finally { setLoading(false) }
  }, [filterLabel])

  // 載入下一頁，累積到 allTasks
  const loadMore = useCallback(async () => {
    if (loadingMoreRef.current) return
    loadingMoreRef.current = true
    setLoadingMore(true)
    try {
      const res = await dailyTasksApi.list({
        label: filterLabel || undefined,
        limit: PAGE_SIZE,
        offset: allTasks.length,
      })
      setAllTasks(prev => [...prev, ...res.data])
      const t = res.headers['x-total-count']
      if (t != null) setTotal(Number(t))
    } finally {
      setLoadingMore(false)
      loadingMoreRef.current = false
    }
  }, [filterLabel, allTasks.length])

  // 刪除後就地移除單筆，不重抓整頁 → 捲動位置與其餘已載入資料維持不變
  const removeOne = useCallback((id: string) => {
    setAllTasks(prev => prev.filter(t => t.id !== id))
    setTotal(n => Math.max(0, n - 1))
  }, [])

  // 更新後就地替換單筆（重抓該筆以取得伺服器計算欄位如 ended_at）
  const updateOne = useCallback(async (id: string) => {
    try {
      const res = await dailyTasksApi.get(id)
      setAllTasks(prev => prev.map(t => (t.id === id ? res.data : t)))
    } catch {
      // 取不到（可能已被刪）就移除，避免殘留
      setAllTasks(prev => prev.filter(t => t.id !== id))
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!bottomRef.current) return
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && allTasks.length < total) loadMore()
      },
      { rootMargin: '200px' }
    )
    obs.observe(bottomRef.current)
    return () => obs.disconnect()
  }, [loading, allTasks.length, total, loadMore])

  const handleDownloadTemplate = async () => {
    const res = await dailyTasksApi.downloadTemplate()
    const url = URL.createObjectURL(new Blob([res.data as BlobPart]))
    const a = document.createElement('a')
    a.href = url
    a.download = 'daily_task_template.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImporting(true)
    setImportResult(null)
    try {
      const res = await dailyTasksApi.importExcel(file)
      setImportResult(res.data)
      if (res.data.created > 0) load()
    } catch (err: any) {
      setImportResult({
        created: 0,
        errors: [err?.response?.data?.detail ?? '匯入失敗，請確認檔案格式'],
        total_rows: 0,
      })
    } finally {
      setImporting(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const counts = useMemo(() => {
    const c = { pending: 0, in_progress: 0, done: 0, cancelled: 0 } as Record<DailyTaskStatus, number>
    for (const t of allTasks) c[t.status]++
    return c
  }, [allTasks])

  const totalHours = useMemo(
    () => allTasks.reduce((s, t) => s + (t.work_minutes ?? 0), 0) / 60,
    [allTasks]
  )

  // All unique labels across all tasks — used for suggestions and filter pills
  const allLabels = useMemo(
    () => Array.from(new Set(allTasks.flatMap(t => t.labels))).sort(),
    [allTasks]
  )

  const filteredTasks = useMemo(() => {
    let list = allTasks
    if (filterStatus) list = list.filter(t => t.status === filterStatus)
    if (filterLabel) list = list.filter(t => t.labels.includes(filterLabel))
    return list
  }, [allTasks, filterStatus, filterLabel])

  // 已載入的（後端分頁逐頁累積）全部顯示；是否還有更多看「已載入 < 總數」
  const visibleTasks = filteredTasks
  const hasMore = allTasks.length < total

  const hasFilter = filterStatus !== null || filterLabel !== ''

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-gray-900">日常作業</h1>
        <div className="flex items-center gap-2 flex-wrap">
          <button className="btn-secondary text-sm" onClick={handleDownloadTemplate}>下載範本</button>
          <label className={`btn-secondary text-sm cursor-pointer ${importing ? 'opacity-50 pointer-events-none' : ''}`}>
            {importing ? '匯入中…' : '匯入 Excel'}
            <input ref={fileInputRef} type="file" accept=".xlsx" className="hidden"
              onChange={handleImportFile} disabled={importing} />
          </label>
        </div>
      </div>

      {/* 匯入結果 */}
      {importResult && (
        <div className={`mb-5 p-4 rounded-xl border text-sm ${importResult.created > 0 ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
          <div className="flex items-start justify-between">
            <div>
              <p className={`font-medium ${importResult.created > 0 ? 'text-green-700' : 'text-red-700'}`}>
                {importResult.created > 0 ? `成功匯入 ${importResult.created} / ${importResult.total_rows} 筆` : '匯入失敗'}
              </p>
              {importResult.errors.length > 0 && (
                <ul className="mt-2 space-y-0.5">
                  {importResult.errors.map((e, i) => <li key={i} className="text-red-600">• {e}</li>)}
                </ul>
              )}
            </div>
            <button className="text-gray-400 hover:text-gray-600 ml-4" onClick={() => setImportResult(null)}>✕</button>
          </div>
        </div>
      )}

      {/* 標籤快速篩選列（有標籤時才顯示） */}
      {allLabels.length > 0 && (
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <span className="text-xs text-gray-400 flex-shrink-0">標籤篩選</span>
          {allLabels.map(l => (
            <button
              key={l}
              onClick={() => setFilterLabel(filterLabel === l ? '' : l)}
              className={`text-xs px-2.5 py-1 rounded-full border font-medium transition-colors ${
                filterLabel === l
                  ? 'bg-indigo-500 text-white border-indigo-500'
                  : 'bg-indigo-50 text-indigo-600 border-indigo-100 hover:bg-indigo-100'
              }`}
            >
              {l}
            </button>
          ))}
          {filterLabel && (
            <button onClick={() => setFilterLabel('')} className="text-xs text-gray-400 hover:text-gray-600">✕ 清除</button>
          )}
        </div>
      )}

      {/* 統計卡 + 狀態篩選按鈕 */}
      <div className="grid grid-cols-5 gap-3 mb-5">
        {(['pending', 'in_progress', 'done', 'cancelled'] as DailyTaskStatus[]).map(s => {
          const isActive = filterStatus === s
          return (
            <button
              key={s}
              onClick={() => setFilterStatus(isActive ? null : s)}
              className={`card text-center py-3 transition-all cursor-pointer border-2 ${
                isActive ? STATUS_FILTER_ACTIVE[s] + ' shadow-md scale-[1.03]' : 'border-transparent hover:border-gray-200'
              }`}
            >
              <p className={`text-2xl font-bold ${isActive ? 'text-white' : 'text-gray-900'}`}>{counts[s]}</p>
              <p className={`text-xs mt-1 font-medium ${isActive ? 'text-white/90' : 'text-gray-500'}`}>{STATUS_LABELS[s]}</p>
            </button>
          )
        })}
        <div className="card text-center py-3">
          <p className="text-2xl font-bold text-primary-600">{Math.round(totalHours * 10) / 10}</p>
          <p className="text-xs text-gray-500 mt-1 font-medium">工時小計(h)</p>
        </div>
      </div>

      {/* 行內新增表單 */}
      <InlineAddForm onAdded={load} labelSuggestions={allLabels} />

      {/* 任務列表 */}
      {loading ? (
        <div className="text-center py-12 text-gray-400">載入中…</div>
      ) : filteredTasks.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          {hasFilter ? '目前篩選條件無符合作業' : '目前沒有任何作業，在上方輸入標題後按新增'}
        </div>
      ) : (
        <>
          {hasFilter && (
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-gray-500">共 {filteredTasks.length} 筆</span>
              <button className="text-xs text-gray-400 hover:text-gray-600" onClick={() => { setFilterStatus(null); setFilterLabel('') }}>
                清除全部篩選 ✕
              </button>
            </div>
          )}
          <div className="space-y-2">
            {visibleTasks.map(t => (
              <TaskRow
                key={t.id}
                task={t}
                onUpdated={updateOne}
                onDeleted={removeOne}
                onEdit={() => setEditing(t)}
              />
            ))}
          </div>
          <div ref={bottomRef} className="h-4" />
          {hasMore ? (
            <div className="text-center py-4 text-sm text-gray-400">
              {loadingMore
                ? '載入更多…'
                : `已載入 ${allTasks.length} / ${total} 筆，向下捲動載入更多…`}
            </div>
          ) : total > PAGE_SIZE ? (
            <div className="text-center py-4 text-xs text-gray-400">已載入全部 {total} 筆</div>
          ) : null}
        </>
      )}

      {/* 編輯 modal */}
      {editing && (
        <DailyTaskModal
          task={editing}
          onClose={() => setEditing(null)}
          onSave={() => { updateOne(editing.id); setEditing(null) }}
          labelSuggestions={allLabels}
        />
      )}
    </div>
  )
}
