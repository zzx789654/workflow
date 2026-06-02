import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { templatesApi } from '../api/templates'
import { projectsApi } from '../api/projects'
import type { ProjectTemplate, Project } from '../types'

function TemplateCard({ tmpl, onApply, onDelete }: {
  tmpl: ProjectTemplate
  onApply: (t: ProjectTemplate) => void
  onDelete: (id: string) => void
}) {
  return (
    <div className="card hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: tmpl.color }} />
          <h3 className="font-semibold text-gray-900">{tmpl.name}</h3>
        </div>
        <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">{tmpl.tasks.length} 個任務</span>
      </div>
      {tmpl.description && <p className="text-sm text-gray-500 mb-3 line-clamp-2">{tmpl.description}</p>}
      <div className="space-y-1 mb-4 max-h-32 overflow-y-auto">
        {tmpl.tasks.slice(0, 5).map(t => (
          <div key={t.id} className="flex items-center gap-2 text-xs text-gray-600">
            <span className="text-gray-300">•</span>
            <span>{t.title}</span>
            {t.day_offset_end != null && (
              <span className="text-gray-400">({t.day_offset_start}~{t.day_offset_end}天)</span>
            )}
          </div>
        ))}
        {tmpl.tasks.length > 5 && <p className="text-xs text-gray-400 pl-3">…還有 {tmpl.tasks.length - 5} 個</p>}
      </div>
      <div className="flex gap-2">
        <button className="btn-primary flex-1 text-sm" onClick={() => onApply(tmpl)}>套用到新專案</button>
        <button className="btn-secondary text-sm px-3" onClick={() => onDelete(tmpl.id)}>刪除</button>
      </div>
    </div>
  )
}

function CreateTemplateModal({ onClose, onSave }: { onClose: () => void; onSave: () => void }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [color, setColor] = useState('#6366f1')
  const [taskLines, setTaskLines] = useState('任務一\n任務二\n任務三')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    const tasks = taskLines.split('\n').filter(Boolean).map((title, i) => ({
      title: title.trim(), position: i, day_offset_start: i * 3, day_offset_end: i * 3 + 2,
    }))
    try {
      await templatesApi.create({ name, description: description || undefined, color, tasks })
      onSave()
    } finally { setLoading(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md" onClick={e => e.stopPropagation()}>
        <div className="p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-4">建立專案範本</h2>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div><label className="text-sm font-medium text-gray-700">範本名稱</label>
              <input className="input mt-1" value={name} onChange={e => setName(e.target.value)} required autoFocus /></div>
            <div><label className="text-sm font-medium text-gray-700">說明</label>
              <input className="input mt-1" value={description} onChange={e => setDescription(e.target.value)} /></div>
            <div><label className="text-sm font-medium text-gray-700">顏色</label>
              <div className="flex gap-2 mt-1">
                <input className="input flex-1" value={color} onChange={e => setColor(e.target.value)} pattern="^#[0-9a-fA-F]{6}$" />
                <input type="color" value={color} onChange={e => setColor(e.target.value)} className="h-10 w-10 rounded cursor-pointer" />
              </div></div>
            <div>
              <label className="text-sm font-medium text-gray-700">任務清單（每行一個）</label>
              <textarea className="input mt-1 resize-none font-mono text-sm" rows={6} value={taskLines} onChange={e => setTaskLines(e.target.value)} placeholder="任務一&#10;任務二" />
            </div>
            <div className="flex gap-3 pt-2">
              <button type="submit" disabled={loading} className="btn-primary flex-1">{loading ? '建立中…' : '建立範本'}</button>
              <button type="button" onClick={onClose} className="btn-secondary flex-1">取消</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

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

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md" onClick={e => e.stopPropagation()}>
        <div className="p-6">
          <h2 className="text-lg font-bold text-gray-900 mb-1">套用範本：{tmpl.name}</h2>
          <p className="text-sm text-gray-500 mb-4">將會建立含 {tmpl.tasks.length} 個任務的新專案</p>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div><label className="text-sm font-medium text-gray-700">專案名稱</label>
              <input className="input mt-1" value={name} onChange={e => setName(e.target.value)} required autoFocus /></div>
            <div><label className="text-sm font-medium text-gray-700">說明（選填）</label>
              <input className="input mt-1" value={description} onChange={e => setDescription(e.target.value)} /></div>
            <div><label className="text-sm font-medium text-gray-700">起始日期（任務時間軸基準）</label>
              <input className="input mt-1" type="date" value={startDate} onChange={e => setStartDate(e.target.value)} /></div>
            <div className="flex gap-3 pt-2">
              <button type="submit" disabled={loading} className="btn-primary flex-1">{loading ? '建立中…' : '建立專案'}</button>
              <button type="button" onClick={onClose} className="btn-secondary flex-1">取消</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<ProjectTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
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
        <button className="btn-primary" onClick={() => setShowCreate(true)}>+ 建立範本</button>
      </div>

      {loading ? (
        <div className="text-center py-16 text-gray-400">載入中…</div>
      ) : templates.length === 0 ? (
        <div className="text-center py-16 text-gray-400">尚無範本，點擊「建立範本」新增</div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map(t => (
            <TemplateCard key={t.id} tmpl={t} onApply={setApplying} onDelete={handleDelete} />
          ))}
        </div>
      )}

      {showCreate && (
        <CreateTemplateModal onClose={() => setShowCreate(false)} onSave={() => { setShowCreate(false); load() }} />
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
