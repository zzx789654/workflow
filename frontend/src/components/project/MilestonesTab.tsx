import { useEffect, useState } from 'react'
import { milestonesApi } from '../../api/milestones'
import type { MilestoneLog } from '../../types'

interface Props { projectId: string }

const fmtHours = (minutes: number) => {
  if (!minutes) return '—'
  const h = minutes / 60
  return `${h % 1 === 0 ? h.toFixed(0) : h.toFixed(1)} h`
}

const hoursTomMinutes = (hours: string) => {
  const h = parseFloat(hours)
  return isNaN(h) || h <= 0 ? 0 : Math.round(h * 60)
}

const minutesToHours = (minutes: number) => {
  if (!minutes) return ''
  const h = minutes / 60
  return h % 1 === 0 ? String(h) : h.toFixed(1)
}

export default function MilestonesTab({ projectId }: Props) {
  const [logs, setLogs] = useState<MilestoneLog[]>([])
  const [loading, setLoading] = useState(true)
  const [rowValues, setRowValues] = useState<Record<string, { hours: string; note: string }>>({})
  const [saving, setSaving] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await milestonesApi.list(projectId)
      const data = res.data as unknown as MilestoneLog[]
      setLogs(data)
      const init: Record<string, { hours: string; note: string }> = {}
      for (const l of data) {
        init[l.id] = { hours: minutesToHours(l.work_minutes), note: l.note ?? '' }
      }
      setRowValues(init)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [projectId])

  const updateRow = (id: string, patch: Partial<{ hours: string; note: string }>) =>
    setRowValues(v => ({ ...v, [id]: { ...v[id], ...patch } }))

  const handleSave = async (log: MilestoneLog) => {
    const row = rowValues[log.id]
    if (!row) return
    setSaving(log.id)
    try {
      await milestonesApi.update(projectId, log.id, {
        work_minutes: hoursTomMinutes(row.hours),
        note: row.note || undefined,
      })
      load()
    } finally { setSaving(null) }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('確定刪除此完成記錄？')) return
    await milestonesApi.delete(projectId, id)
    setLogs(l => l.filter(x => x.id !== id))
  }

  if (loading) return <div className="text-center py-16 text-gray-400">載入中…</div>

  const totalMinutes = logs.reduce((sum, l) => sum + (l.work_minutes ?? 0), 0)
  const totalDailyMinutes = logs.reduce((sum, l) => sum + (l.daily_task_minutes ?? 0), 0)
  const filledCount  = logs.filter(l => l.work_minutes > 0).length

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-gray-800">完成記錄</h2>
          <p className="text-xs text-gray-400 mt-0.5">當專案中任何任務完成時自動記錄，可直接在此填寫工時。</p>
        </div>
        <span className="text-sm text-gray-500 bg-gray-100 px-3 py-1 rounded-full">{logs.length} 筆</span>
      </div>

      {logs.length > 0 && (
        <div className="grid grid-cols-4 gap-3 mb-5">
          <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-3 text-center">
            <p className="text-lg font-bold text-indigo-600">{fmtHours(totalMinutes)}</p>
            <p className="text-xs text-indigo-400 mt-0.5">手填工時</p>
          </div>
          <div className="bg-violet-50 border border-violet-100 rounded-xl p-3 text-center">
            <p className="text-lg font-bold text-violet-600">{fmtHours(totalDailyMinutes)}</p>
            <p className="text-xs text-violet-400 mt-0.5">日常任務時數</p>
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
          {logs.map(log => {
            const row = rowValues[log.id] ?? { hours: '', note: '' }
            const isSaving = saving === log.id
            return (
              <div key={log.id} className="card border border-gray-100 hover:border-gray-200 transition-colors">
                <div className="flex items-start gap-3 mb-3">
                  <div className="w-8 h-8 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-sm flex-shrink-0 font-bold mt-0.5">✓</div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 truncate">{log.task_title}</p>
                    <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-0.5 text-xs text-gray-400">
                      {log.completed_by_name && (
                        <span className="flex items-center gap-1">
                          <span className="w-4 h-4 rounded-full bg-primary-100 text-primary-600 inline-flex items-center justify-center text-[10px] font-bold">
                            {log.completed_by_name.charAt(0).toUpperCase()}
                          </span>
                          {log.completed_by_name}
                        </span>
                      )}
                      <span>{new Date(log.completed_at).toLocaleString('zh-TW', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                  </div>
                  <button onClick={() => handleDelete(log.id)} className="text-xs text-red-400 hover:text-red-600 flex-shrink-0">刪除</button>
                </div>

                {/* 日常任務時數加總 */}
                {log.daily_task_minutes > 0 && (
                  <div className="flex items-center gap-1.5 mb-2 text-xs text-violet-600 bg-violet-50 border border-violet-100 rounded-lg px-2.5 py-1 w-fit">
                    <span>📋 日常任務時數</span>
                    <span className="font-semibold">{fmtHours(log.daily_task_minutes)}</span>
                  </div>
                )}

                {/* 內聯工時欄位 */}
                <div className="flex gap-2 items-end">
                  <div className="flex-1">
                    <label className="text-xs text-gray-500 block mb-1">工時（小時）</label>
                    <input
                      type="number" min={0} step={0.5} placeholder="例：1.5"
                      className="input w-full text-sm"
                      value={row.hours}
                      onChange={e => updateRow(log.id, { hours: e.target.value })}
                      onBlur={() => handleSave(log)}
                    />
                    {row.hours && parseFloat(row.hours) > 0 && (
                      <p className="text-xs text-gray-400 mt-0.5">= {fmtHours(hoursTomMinutes(row.hours))}</p>
                    )}
                  </div>
                  <div className="flex-[2]">
                    <label className="text-xs text-gray-500 block mb-1">備註（選填）</label>
                    <input
                      type="text" placeholder="補充說明"
                      className="input w-full text-sm"
                      value={row.note}
                      onChange={e => updateRow(log.id, { note: e.target.value })}
                      onBlur={() => handleSave(log)}
                    />
                  </div>
                  <button
                    onClick={() => handleSave(log)}
                    disabled={isSaving}
                    className="btn-primary text-sm px-4 mb-0.5"
                  >
                    {isSaving ? '…' : '儲存'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
