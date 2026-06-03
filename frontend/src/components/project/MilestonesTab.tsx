import { useEffect, useState } from 'react'
import { milestonesApi } from '../../api/milestones'
import type { MilestoneLog } from '../../types'

interface Props { projectId: string }

// 分鐘 → 小時（固定顯示，保留一位小數）
const fmtHours = (minutes: number) => {
  if (!minutes) return '—'
  const h = minutes / 60
  return `${h % 1 === 0 ? h.toFixed(0) : h.toFixed(1)} h`
}

// 小時 → 分鐘（存入後端用）
const hoursTomMinutes = (hours: string) => {
  const h = parseFloat(hours)
  return isNaN(h) || h <= 0 ? 0 : Math.round(h * 60)
}

// 分鐘 → 小時字串（供輸入框初始值）
const minutesToHours = (minutes: number) => {
  if (!minutes) return ''
  const h = minutes / 60
  return h % 1 === 0 ? String(h) : h.toFixed(1)
}

export default function MilestonesTab({ projectId }: Props) {
  const [logs, setLogs] = useState<MilestoneLog[]>([])
  const [loading, setLoading] = useState(true)
  const [editId, setEditId] = useState<string | null>(null)
  const [editHours, setEditHours] = useState('')
  const [editNote, setEditNote] = useState('')
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await milestonesApi.list(projectId)
      setLogs(res.data as unknown as MilestoneLog[])
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [projectId])

  const startEdit = (log: MilestoneLog) => {
    setEditId(log.id)
    setEditHours(minutesToHours(log.work_minutes))
    setEditNote(log.note ?? '')
  }

  const handleSave = async (log: MilestoneLog) => {
    setSaving(true)
    try {
      await milestonesApi.update(projectId, log.id, {
        work_minutes: hoursTomMinutes(editHours),
        note: editNote || undefined,
      })
      setEditId(null)
      load()
    } finally { setSaving(false) }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('確定刪除此完成記錄？')) return
    await milestonesApi.delete(projectId, id)
    setLogs(l => l.filter(x => x.id !== id))
  }

  if (loading) return <div className="text-center py-16 text-gray-400">載入中…</div>

  const totalMinutes = logs.reduce((sum, l) => sum + (l.work_minutes ?? 0), 0)
  const filledCount  = logs.filter(l => l.work_minutes > 0).length

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-gray-800">完成記錄</h2>
          <p className="text-xs text-gray-400 mt-0.5">當專案中任何任務完成時自動記錄，可在此補填工時。</p>
        </div>
        <span className="text-sm text-gray-500 bg-gray-100 px-3 py-1 rounded-full">{logs.length} 筆</span>
      </div>

      {/* 工時加總統計卡 */}
      {logs.length > 0 && (
        <div className="grid grid-cols-3 gap-3 mb-5">
          <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-3 text-center">
            <p className="text-lg font-bold text-indigo-600">{fmtHours(totalMinutes)}</p>
            <p className="text-xs text-indigo-400 mt-0.5">總工時</p>
          </div>
          <div className="bg-green-50 border border-green-100 rounded-xl p-3 text-center">
            <p className="text-lg font-bold text-green-600">{logs.length}</p>
            <p className="text-xs text-green-400 mt-0.5">已完成任務</p>
          </div>
          <div className="bg-amber-50 border border-amber-100 rounded-xl p-3 text-center">
            <p className="text-lg font-bold text-amber-600">{filledCount}/{logs.length}</p>
            <p className="text-xs text-amber-400 mt-0.5">已填工時</p>
          </div>
        </div>
      )}

      {logs.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg mb-1">尚無完成記錄</p>
          <p className="text-sm">將任務狀態設為「完成」即會自動出現在此</p>
        </div>
      ) : (
        <div className="space-y-3">
          {logs.map(log => (
            <div key={log.id} className="card border border-gray-100 hover:border-gray-200 transition-colors">
              {editId === log.id ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center text-sm flex-shrink-0">✓</div>
                    <p className="font-medium text-gray-900">{log.task_title}</p>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs text-gray-500 block mb-1">工時（小時）</label>
                      <input
                        type="number" min={0} step={0.5} placeholder="例：1.5"
                        className="input w-full text-sm"
                        value={editHours}
                        onChange={e => setEditHours(e.target.value)}
                      />
                      {editHours && parseFloat(editHours) > 0 && (
                        <p className="text-xs text-gray-400 mt-0.5">
                          = {fmtHours(hoursTomMinutes(editHours))}
                        </p>
                      )}
                    </div>
                    <div>
                      <label className="text-xs text-gray-500 block mb-1">備註</label>
                      <input
                        type="text" placeholder="補充說明（選填）"
                        className="input w-full text-sm"
                        value={editNote}
                        onChange={e => setEditNote(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => handleSave(log)} disabled={saving} className="btn-primary text-sm px-4">
                      {saving ? '儲存中…' : '儲存'}
                    </button>
                    <button onClick={() => setEditId(null)} className="btn-secondary text-sm px-4">取消</button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-sm flex-shrink-0 font-bold mt-0.5">✓</div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 truncate">{log.task_title}</p>
                    <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-1 text-xs text-gray-400">
                      {log.completed_by_name && (
                        <span className="flex items-center gap-1">
                          <span className="w-4 h-4 rounded-full bg-primary-100 text-primary-600 inline-flex items-center justify-center text-[10px] font-bold">
                            {log.completed_by_name.charAt(0).toUpperCase()}
                          </span>
                          {log.completed_by_name}
                        </span>
                      )}
                      <span>{new Date(log.completed_at).toLocaleString('zh-TW', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                      <span className={log.work_minutes > 0 ? 'text-indigo-500 font-medium' : ''}>
                        工時：{fmtHours(log.work_minutes)}
                      </span>
                      {log.note && <span className="text-gray-500 italic">「{log.note}」</span>}
                    </div>
                  </div>
                  <div className="flex gap-2 flex-shrink-0">
                    <button onClick={() => startEdit(log)} className="text-xs text-blue-500 hover:text-blue-700">
                      {log.work_minutes === 0 ? '填寫工時' : '編輯'}
                    </button>
                    <button onClick={() => handleDelete(log.id)} className="text-xs text-red-400 hover:text-red-600">刪除</button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
