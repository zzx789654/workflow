import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { templatesApi } from '../api/templates'
import { projectsApi } from '../api/projects'
import type { ProjectTemplate, Project, TemplateTask } from '../types'

// ─── 任務編輯列 ──────────────────────────────────────────────
interface EditableTask {
  id?: string           // 已存在的任務 id（編輯時）
  title: string
  description: string
  priority: string
  day_offset_start: number
  day_offset_end: number | null
}

const PRIORITY_OPTS = [
  { value: 'low', label: '低' },
  { value: 'medium', label: '中' },
  { value: 'high', label: '高' },
  { value: 'urgent', label: '緊急' },
]

function TaskRow({
  task, idx, onChange, onRemove, onMoveUp, onMoveDown, isFirst, isLast,
}: {
  task: EditableTask; idx: number
  onChange: (t: EditableTask) => void
  onRemove: () => void
  onMoveUp: () => void
  onMoveDown: () => void
  isFirst: boolean; isLast: boolean
}) {
  return (
    <div className="border border-gray-200 rounded-xl p-3 space-y-2 bg-white">
      {/* 行頂：順序控制 + 標題 + 刪除 */}
      <div className="flex items-center gap-2">
        <div className="flex flex-col gap-0.5 flex-shrink-0">
          <button type="button" onClick={onMoveUp} disabled={isFirst}
            className="text-gray-300 hover:text-gray-500 disabled:opacity-20 text-xs leading-none">▲</button>
          <span className="text-xs text-gray-400 text-center">{idx + 1}</span>
          <button type="button" onClick={onMoveDown} disabled={isLast}
            className="text-gray-300 hover:text-gray-500 disabled:opacity-20 text-xs leading-none">▼</button>
        </div>
        <input
          className="input flex-1 text-sm"
          placeholder="任務標題（必填）"
          value={task.title}
          onChange={e => onChange({ ...task, title: e.target.value })}
          required
        />
        <button type="button" onClick={onRemove}
          className="text-red-400 hover:text-red-600 text-lg flex-shrink-0 px-1">✕</button>
      </div>

      {/* 說明 */}
      <input
        className="input w-full text-sm"
        placeholder="說明（選填）"
        value={task.description}
        onChange={e => onChange({ ...task, description: e.target.value })}
      />

      {/* 優先度 + 天數 */}
      <div className="flex gap-2 flex-wrap">
        <select
          className="input text-sm w-24"
          value={task.priority}
          onChange={e => onChange({ ...task, priority: e.target.value })}
        >
          {PRIORITY_OPTS.map(p => <option key={p.value} value={p.value}>{p.label}優先</option>)}
        </select>

        <div className="flex items-center gap-1 text-sm">
          <label className="text-gray-500 whitespace-nowrap">開始第</label>
          <input
            type="number" min={0} max={365}
            className="input w-16 text-sm text-center"
            value={task.day_offset_start}
            onChange={e => onChange({ ...task, day_offset_start: Math.max(0, +e.target.value) })}
          />
          <label className="text-gray-500">天</label>
        </div>

        <div className="flex items-center gap-1 text-sm">
          <label className="text-gray-500 whitespace-nowrap">截止第</label>
          <input
            type="number" min={0} max={365}
            className="input w-16 text-sm text-center"
            placeholder="—"
            value={task.day_offset_end ?? ''}
            onChange={e => onChange({
              ...task,
              day_offset_end: e.target.value === '' ? null : Math.max(0, +e.target.value),
            })}
          />
          <label className="text-gray-500">天</label>
        </div>

        {/* 預覽：工期 */}
        {task.day_offset_end != null && task.day_offset_end >= task.day_offset_start && (
          <span className="text-xs text-indigo-500 self-center">
            工期 {task.day_offset_end - task.day_offset_start + 1} 天
          </span>
        )}
      </div>
    </div>
  )
}

// ─── 範本編輯 Modal ───────────────────────────────────────────
function TemplateEditModal({
  template, onClose, onSaved,
}: {
  template?: ProjectTemplate      // undefined = 新建
  onClose: () => void
  onSaved: () => void
}) {
  const isNew = !template
  const [name, setName] = useState(template?.name ?? '')
  const [description, setDescription] = useState(template?.description ?? '')
  const [color, setColor] = useState(template?.color ?? '#6366f1')
  const [tasks, setTasks] = useState<EditableTask[]>(
    template?.tasks.map(t => ({
      id: t.id,
      title: t.title,
      description: t.description ?? '',
      priority: t.priority,
      day_offset_start: t.day_offset_start,
      day_offset_end: t.day_offset_end ?? null,
    })) ?? [{ title: '', description: '', priority: 'medium', day_offset_start: 0, day_offset_end: null }]
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const addTask = () => {
    const last = tasks[tasks.length - 1]
    const nextStart = last ? (last.day_offset_end ?? last.day_offset_start) + 1 : 0
    setTasks(t => [...t, {
      title: '', description: '', priority: 'medium',
      day_offset_start: nextStart, day_offset_end: nextStart + 2,
    }])
  }

  const updateTask = (idx: number, val: EditableTask) =>
    setTasks(t => t.map((x, i) => i === idx ? val : x))

  const removeTask = (idx: number) =>
    setTasks(t => t.filter((_, i) => i !== idx))

  const moveTask = (idx: number, dir: -1 | 1) =>
    setTasks(t => {
      const a = [...t]
      ;[a[idx], a[idx + dir]] = [a[idx + dir], a[idx]]
      return a
    })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (tasks.some(t => !t.title.trim())) { setError('所有任務都需要填寫標題'); return }
    setError(''); setLoading(true)
    const taskPayload = tasks.map((t, i) => ({
      title: t.title.trim(),
      description: t.description.trim() || undefined,
      priority: t.priority,
      day_offset_start: t.day_offset_start,
      day_offset_end: t.day_offset_end ?? undefined,
      position: i,
    }))
    try {
      if (isNew) {
        await templatesApi.create({ name, description: description || undefined, color, tasks: taskPayload })
      } else {
        await templatesApi.update(template.id, { name, description: description || undefined, color })
        await templatesApi.replaceTasks(template.id, taskPayload)
      }
      onSaved()
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? '操作失敗')
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col"
        onClick={e => e.stopPropagation()}>

        {/* 標題 */}
        <div className="px-6 pt-6 pb-3 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">{isNew ? '建立專案範本' : `編輯：${template.name}`}</h2>
        </div>

        {/* 內容（可捲動） */}
        <form onSubmit={handleSubmit} className="flex flex-col flex-1 overflow-hidden">
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            {error && <p className="text-sm text-red-500">{error}</p>}

            {/* 基本資訊 */}
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2 sm:col-span-1">
                <label className="text-sm font-medium text-gray-700">範本名稱</label>
                <input className="input mt-1 w-full" value={name}
                  onChange={e => setName(e.target.value)} required autoFocus />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">顏色</label>
                <div className="flex gap-2 mt-1">
                  <input className="input flex-1" value={color}
                    onChange={e => setColor(e.target.value)} pattern="^#[0-9a-fA-F]{6}$" />
                  <input type="color" value={color} onChange={e => setColor(e.target.value)}
                    className="h-10 w-10 rounded cursor-pointer border border-gray-200" />
                </div>
              </div>
              <div className="col-span-2">
                <label className="text-sm font-medium text-gray-700">說明（選填）</label>
                <input className="input mt-1 w-full" value={description}
                  onChange={e => setDescription(e.target.value)} />
              </div>
            </div>

            {/* 任務清單 */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-gray-700">任務清單（{tasks.length} 個）</label>
                <span className="text-xs text-gray-400">天數以「起始日期」為第 0 天計算</span>
              </div>
              <div className="space-y-2">
                {tasks.map((t, i) => (
                  <TaskRow
                    key={i} task={t} idx={i}
                    onChange={val => updateTask(i, val)}
                    onRemove={() => removeTask(i)}
                    onMoveUp={() => moveTask(i, -1)}
                    onMoveDown={() => moveTask(i, 1)}
                    isFirst={i === 0}
                    isLast={i === tasks.length - 1}
                  />
                ))}
              </div>
              <button type="button" onClick={addTask}
                className="mt-2 w-full border-2 border-dashed border-gray-200 rounded-xl py-2 text-sm text-gray-400 hover:border-primary-300 hover:text-primary-500 transition-colors">
                + 新增任務
              </button>
            </div>
          </div>

          {/* 底部按鈕 */}
          <div className="px-6 py-4 border-t border-gray-100 flex gap-3">
            <button type="submit" disabled={loading} className="btn-primary flex-1">
              {loading ? '儲存中…' : isNew ? '建立範本' : '儲存變更'}
            </button>
            <button type="button" onClick={onClose} className="btn-secondary flex-1">取消</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── 套用 Modal ───────────────────────────────────────────────
function ApplyModal({ tmpl, onClose, onApplied }: {
  tmpl: ProjectTemplate; onClose: () => void; onApplied: (p: Project) => void
}) {
  const [name, setName] = useState(`${tmpl.name} - 新專案`)
  const [description, setDescription] = useState('')
  const [startDate, setStartDate] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await templatesApi.apply(tmpl.id, {
        project_name: name,
        project_description: description || undefined,
        start_date: startDate || undefined,
      })
      onApplied(res.data)
    } finally { setLoading(false) }
  }

  // 計算總工期
  const duration = tmpl.tasks.length > 0
    ? Math.max(...tmpl.tasks.map(t => t.day_offset_end ?? t.day_offset_start)) + 1
    : 0

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md" onClick={e => e.stopPropagation()}>
        <div className="p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-1">套用範本：{tmpl.name}</h2>
          <p className="text-sm text-gray-500 mb-4">
            建立含 {tmpl.tasks.length} 個任務的新專案
            {duration > 0 && `，總工期約 ${duration} 天`}
          </p>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div><label className="text-sm font-medium text-gray-700">專案名稱</label>
              <input className="input mt-1 w-full" value={name}
                onChange={e => setName(e.target.value)} required autoFocus /></div>
            <div><label className="text-sm font-medium text-gray-700">說明（選填）</label>
              <input className="input mt-1 w-full" value={description}
                onChange={e => setDescription(e.target.value)} /></div>
            <div>
              <label className="text-sm font-medium text-gray-700">起始日期（任務時間軸基準，第 0 天）</label>
              <input className="input mt-1 w-full" type="date" value={startDate}
                onChange={e => setStartDate(e.target.value)} />
            </div>
            <div className="flex gap-3 pt-2">
              <button type="submit" disabled={loading} className="btn-primary flex-1">
                {loading ? '建立中…' : '建立專案'}
              </button>
              <button type="button" onClick={onClose} className="btn-secondary flex-1">取消</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

// ─── 範本卡片 ─────────────────────────────────────────────────
function TemplateCard({ tmpl, onApply, onEdit, onDelete }: {
  tmpl: ProjectTemplate
  onApply: (t: ProjectTemplate) => void
  onEdit: (t: ProjectTemplate) => void
  onDelete: (id: string) => void
}) {
  const duration = tmpl.tasks.length > 0
    ? Math.max(...tmpl.tasks.map(t => t.day_offset_end ?? t.day_offset_start)) + 1
    : 0

  const PRIORITY_COLOR: Record<string, string> = {
    low: 'text-gray-400', medium: 'text-blue-500', high: 'text-orange-500', urgent: 'text-red-500',
  }

  return (
    <div className="card hover:shadow-md transition-shadow flex flex-col">
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: tmpl.color }} />
          <h3 className="font-semibold text-gray-900 truncate">{tmpl.name}</h3>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0 ml-2">
          <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">{tmpl.tasks.length} 個任務</span>
          {duration > 0 && (
            <span className="text-xs bg-indigo-50 text-indigo-600 px-2 py-0.5 rounded-full">{duration} 天</span>
          )}
        </div>
      </div>

      {tmpl.description && <p className="text-sm text-gray-500 mb-2 line-clamp-2">{tmpl.description}</p>}

      {/* 任務預覽 */}
      <div className="space-y-1 mb-4 flex-1 max-h-40 overflow-y-auto">
        {tmpl.tasks.map(t => (
          <div key={t.id} className="flex items-center gap-2 text-xs">
            <span className={`flex-shrink-0 ${PRIORITY_COLOR[t.priority] ?? 'text-gray-400'}`}>●</span>
            <span className="text-gray-700 truncate flex-1">{t.title}</span>
            <span className="text-gray-400 flex-shrink-0 whitespace-nowrap">
              第 {t.day_offset_start}{t.day_offset_end != null ? `~${t.day_offset_end}` : ''} 天
            </span>
          </div>
        ))}
      </div>

      <div className="flex gap-2 flex-wrap">
        <button className="btn-primary flex-1 text-sm" onClick={() => onApply(tmpl)}>套用</button>
        <button className="btn-secondary text-sm px-3" onClick={() => onEdit(tmpl)}>編輯</button>
        <button className="text-sm text-red-400 hover:text-red-600 px-2" onClick={() => onDelete(tmpl.id)}>刪除</button>
      </div>
    </div>
  )
}

// ─── 主頁面 ───────────────────────────────────────────────────
export default function TemplatesPage() {
  const [templates, setTemplates] = useState<ProjectTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [editTarget, setEditTarget] = useState<ProjectTemplate | null | 'new'>()
  const [applying, setApplying] = useState<ProjectTemplate | null>(null)
  const navigate = useNavigate()

  const load = async () => {
    setLoading(true)
    try { const res = await templatesApi.list(); setTemplates(res.data) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleDelete = async (id: string) => {
    if (!confirm('確定刪除此範本？')) return
    await templatesApi.delete(id)
    load()
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">專案範本</h1>
        <button className="btn-primary" onClick={() => setEditTarget('new')}>+ 建立範本</button>
      </div>

      {loading ? (
        <div className="text-center py-16 text-gray-400">載入中…</div>
      ) : templates.length === 0 ? (
        <div className="text-center py-16 text-gray-400">尚無範本，點擊「建立範本」新增</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map(t => (
            <TemplateCard
              key={t.id} tmpl={t}
              onApply={setApplying}
              onEdit={tmpl => setEditTarget(tmpl)}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}

      {editTarget != null && (
        <TemplateEditModal
          template={editTarget === 'new' ? undefined : editTarget}
          onClose={() => setEditTarget(undefined)}
          onSaved={() => { setEditTarget(undefined); load() }}
        />
      )}

      {applying && (
        <ApplyModal
          tmpl={applying}
          onClose={() => setApplying(null)}
          onApplied={p => { setApplying(null); navigate(`/projects/${p.id}`) }}
        />
      )}
    </div>
  )
}
