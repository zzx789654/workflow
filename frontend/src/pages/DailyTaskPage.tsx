import { useEffect, useRef, useState } from 'react'
import { format } from 'date-fns'
import { dailyTasksApi } from '../api/dailyTasks'
import type { DailyTask, DailyTaskStatus } from '../types'

const STATUS_LABELS: Record<DailyTaskStatus, string> = {
  pending: '待辦', in_progress: '進行中', done: '完成', cancelled: '已取消',
}
const STATUS_COLORS: Record<DailyTaskStatus, string> = {
  pending: 'bg-gray-100 text-gray-600',
  in_progress: 'bg-blue-100 text-blue-600',
  done: 'bg-green-100 text-green-600',
  cancelled: 'bg-red-100 text-red-500',
}

const NOTIFY_OPTIONS = [
  { value: '', label: '不需要' },
  { value: '1', label: '1 天前' },
  { value: '3', label: '3 天前' },
  { value: '7', label: '7 天前' },
]

const today = () => format(new Date(), 'yyyy-MM-dd')

// Compute notify_at datetime from due date + days-before offset
function computeNotifyAt(date: string, daysBefore: string): string | undefined {
  if (!date || !daysBefore) return undefined
  const d = new Date(date)
  d.setDate(d.getDate() - parseInt(daysBefore))
  return `${format(d, 'yyyy-MM-dd')}T09:00:00`
}

function DailyTaskModal({
  task, onClose, onSave,
}: { task?: DailyTask | null; onClose: () => void; onSave: (keepOpen?: boolean) => void }) {
  const isNew = !task
  const [title, setTitle] = useState(task?.title ?? '')
  const [description, setDescription] = useState(task?.description ?? '')
  const [status, setStatus] = useState<DailyTaskStatus>(task?.status ?? 'pending')
  const [date, setDate] = useState(task?.date ?? today())
  // Notify: derive days-before from existing notify_at if available
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
  const [loading, setLoading] = useState(false)
  const [continuous, setContinuous] = useState(false)
  const [addedCount, setAddedCount] = useState(0)
  const titleRef = useRef<HTMLInputElement>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    const labels = labelsStr.split(',').map(s => s.trim()).filter(Boolean)
    const notify_at = computeNotifyAt(date, notifyDays)
    const payload = {
      title,
      description: description || undefined,
      status,
      progress: 0,
      date,
      work_minutes: Math.round(workHours * 60),
      labels,
      notify_at,
      started_at: undefined,
      ended_at: undefined,
    }
    try {
      if (task) {
        await dailyTasksApi.update(task.id, payload)
        onSave()
      } else {
        await dailyTasksApi.create({ ...payload, date })
        if (continuous) {
          setTitle('')
          setAddedCount(c => c + 1)
          onSave(true)
          setTimeout(() => titleRef.current?.focus(), 50)
        } else {
          onSave()
        }
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
              <input ref={titleRef} className="input mt-1 w-full" value={title} onChange={e => setTitle(e.target.value)} required autoFocus />
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">說明</label>
              <textarea className="input mt-1 w-full resize-none" rows={2} value={description} onChange={e => setDescription(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-gray-700">日期</label>
                <input className="input mt-1 w-full" type="date" value={date} onChange={e => setDate(e.target.value)} required />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">狀態</label>
                <select className="input mt-1 w-full" value={status} onChange={e => setStatus(e.target.value as DailyTaskStatus)}>
                  {(Object.keys(STATUS_LABELS) as DailyTaskStatus[]).map(s => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-gray-700">通知時間</label>
                <select className="input mt-1 w-full" value={notifyDays} onChange={e => setNotifyDays(e.target.value)}>
                  {NOTIFY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">工作時數</label>
                <input
                  className="input mt-1 w-full"
                  type="number"
                  min={0}
                  step={0.5}
                  value={workHours}
                  onChange={e => setWorkHours(+e.target.value)}
                  placeholder="例：1.5"
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">標籤（逗號分隔）</label>
              <input className="input mt-1 w-full" placeholder="例：開發, 會議, 文件" value={labelsStr} onChange={e => setLabelsStr(e.target.value)} />
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

interface ImportResult {
  created: number
  errors: string[]
  total_rows: number
}

export default function DailyTaskPage() {
  const [tasks, setTasks] = useState<DailyTask[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedDate, setSelectedDate] = useState(today())
  const [filterLabel, setFilterLabel] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<DailyTask | null>(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await dailyTasksApi.list({ date: selectedDate, label: filterLabel || undefined })
      setTasks(res.data)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [selectedDate, filterLabel])

  const handleDelete = async (id: string) => {
    if (!confirm('確定刪除？')) return
    await dailyTasksApi.delete(id)
    load()
  }

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

  const allLabels = Array.from(new Set(tasks.flatMap(t => t.labels)))

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-gray-900">日常作業</h1>
        <div className="flex items-center gap-2 flex-wrap">
          <button className="btn-secondary text-sm" onClick={handleDownloadTemplate} title="下載 Excel 範本">
            下載範本
          </button>
          <label className={`btn-secondary text-sm cursor-pointer ${importing ? 'opacity-50 pointer-events-none' : ''}`}>
            {importing ? '匯入中…' : '匯入 Excel'}
            <input ref={fileInputRef} type="file" accept=".xlsx" className="hidden" onChange={handleImportFile} disabled={importing} />
          </label>
          <button className="btn-primary text-sm" onClick={() => { setEditing(null); setShowModal(true) }}>+ 新增作業</button>
        </div>
      </div>

      {/* 匯入結果提示 */}
      {importResult && (
        <div className={`mb-5 p-4 rounded-xl border text-sm ${importResult.created > 0 ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
          <div className="flex items-start justify-between">
            <div>
              <p className={`font-medium ${importResult.created > 0 ? 'text-green-700' : 'text-red-700'}`}>
                {importResult.created > 0
                  ? `成功匯入 ${importResult.created} / ${importResult.total_rows} 筆`
                  : '匯入失敗'}
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

      {/* 篩選列 */}
      <div className="flex gap-3 mb-5 flex-wrap">
        <input type="date" className="input w-40" value={selectedDate} onChange={e => setSelectedDate(e.target.value)} />
        <select className="input w-36" value={filterLabel} onChange={e => setFilterLabel(e.target.value)}>
          <option value="">全部標籤</option>
          {allLabels.map(l => <option key={l} value={l}>{l}</option>)}
        </select>
        <button className="btn-secondary text-sm" onClick={() => setSelectedDate(today())}>今天</button>
      </div>

      {/* 統計卡 */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {(['pending', 'in_progress', 'done', 'cancelled'] as DailyTaskStatus[]).map(s => (
          <div key={s} className="card text-center">
            <p className="text-2xl font-bold text-gray-900">{tasks.filter(t => t.status === s).length}</p>
            <p className="text-xs text-gray-500 mt-1">{STATUS_LABELS[s]}</p>
          </div>
        ))}
      </div>

      {/* 任務列表 */}
      {loading ? (
        <div className="text-center py-12 text-gray-400">載入中…</div>
      ) : tasks.length === 0 ? (
        <div className="text-center py-12 text-gray-400">當日無作業，點擊「新增作業」開始記錄</div>
      ) : (
        <div className="space-y-3">
          {tasks.map(t => (
            <div key={t.id} className="card hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[t.status]}`}>
                      {STATUS_LABELS[t.status]}
                    </span>
                    {t.labels.map(l => (
                      <span key={l} className="text-xs bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full">{l}</span>
                    ))}
                  </div>
                  <p className="font-semibold text-gray-900 truncate">{t.title}</p>
                  {t.description && <p className="text-sm text-gray-500 mt-0.5 line-clamp-1">{t.description}</p>}
                  <div className="flex items-center gap-4 mt-2 text-xs text-gray-400 flex-wrap">
                    {t.work_minutes > 0 && (
                      <span>{Math.round(t.work_minutes / 60 * 10) / 10}h</span>
                    )}
                    {t.notify_at && (
                      <span>通知 {t.notify_at.slice(0, 10)}</span>
                    )}
                  </div>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <button className="text-xs text-blue-500 hover:text-blue-700" onClick={() => { setEditing(t); setShowModal(true) }}>編輯</button>
                  <button className="text-xs text-red-400 hover:text-red-600" onClick={() => handleDelete(t.id)}>刪除</button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <DailyTaskModal
          task={editing}
          onClose={() => { setShowModal(false); setEditing(null) }}
          onSave={(keepOpen) => {
            load()
            if (!keepOpen) { setShowModal(false); setEditing(null) }
          }}
        />
      )}
    </div>
  )
}
