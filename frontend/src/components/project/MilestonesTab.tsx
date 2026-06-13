import { useEffect, useState } from 'react'
import { milestonesApi } from '../../api/milestones'
import { confirm } from '../../stores/confirmStore'
import type { MilestoneLog, MilestoneDailyTask } from '../../types'

interface Props { projectId: string }

const fmtHours = (minutes: number) => {
  if (!minutes) return '—'
  const h = minutes / 60
  return `${h % 1 === 0 ? h.toFixed(0) : h.toFixed(1)} h`
}

const fmtDate = (iso: string) => {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('zh-TW', { month: 'numeric', day: 'numeric' })
}

function DailyTaskTree({ tasks }: { tasks: MilestoneDailyTask[] }) {
  if (!tasks.length) return (
    <div className="ml-9 mt-1 text-xs text-gray-400 italic">無關聯日常任務</div>
  )
  return (
    <div className="ml-9 mt-1 space-y-0.5">
      {tasks.map((dt, idx) => (
        <div key={dt.id} className="flex items-center gap-2 text-xs text-gray-600 py-0.5">
          {/* 樹狀線 */}
          <div className="flex-shrink-0 flex items-center">
            <span className="text-gray-300 select-none">
              {idx < tasks.length - 1 ? '├' : '└'}
            </span>
          </div>
          <span className="text-gray-400 w-16 flex-shrink-0">{fmtDate(dt.date)}</span>
          <span className="flex-1 truncate">{dt.title}</span>
          <span className="flex-shrink-0 font-medium text-violet-600 bg-violet-50 rounded px-1.5 py-0.5">
            {fmtHours(dt.work_minutes)}
          </span>
        </div>
      ))}
      {/* 小計列 */}
      <div className="flex items-center gap-2 text-xs pt-1 border-t border-gray-100 mt-1">
        <div className="w-3 flex-shrink-0" />
        <span className="text-gray-400 w-16 flex-shrink-0" />
        <span className="flex-1 text-gray-400">小計</span>
        <span className="flex-shrink-0 font-semibold text-violet-700">
          {fmtHours(tasks.reduce((s, t) => s + t.work_minutes, 0))}
        </span>
      </div>
    </div>
  )
}

export default function MilestonesTab({ projectId }: Props) {
  const [logs, setLogs] = useState<MilestoneLog[]>([])
  const [loading, setLoading] = useState(true)
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const load = async () => {
    setLoading(true)
    try {
      const res = await milestonesApi.list(projectId)
      const data = res.data as unknown as MilestoneLog[]
      setLogs(data)
      const init: Record<string, string> = {}
      for (const l of data) { init[l.id] = l.note ?? '' }
      setNotes(init)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [projectId])

  const handleNoteSave = async (log: MilestoneLog) => {
    await milestonesApi.update(projectId, log.id, { note: notes[log.id] || undefined })
  }

  const handleDelete = async (id: string) => {
    if (!(await confirm({ title: '刪除記錄', message: '確定刪除此完成記錄？', confirmLabel: '刪除', danger: true }))) return
    await milestonesApi.delete(projectId, id)
    setLogs(l => l.filter(x => x.id !== id))
  }

  const toggleExpand = (id: string) =>
    setExpanded(v => ({ ...v, [id]: !v[id] }))

  if (loading) return <div className="text-center py-16 text-gray-400">載入中…</div>

  const totalDailyMinutes = logs.reduce((sum, l) => sum + (l.daily_task_minutes ?? 0), 0)

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-gray-800">完成記錄</h2>
          <p className="text-xs text-gray-400 mt-0.5">當專案中任何任務完成時自動記錄，工時來自關聯的日常任務加總。</p>
        </div>
        <span className="text-sm text-gray-500 bg-gray-100 px-3 py-1 rounded-full">{logs.length} 筆</span>
      </div>

      {logs.length > 0 && (
        <div className="grid grid-cols-3 gap-3 mb-5">
          <div className="bg-violet-50 border border-violet-100 rounded-xl p-3 text-center">
            <p className="text-lg font-bold text-violet-600">{fmtHours(totalDailyMinutes)}</p>
            <p className="text-xs text-violet-400 mt-0.5">總工時</p>
          </div>
          <div className="bg-green-50 border border-green-100 rounded-xl p-3 text-center">
            <p className="text-lg font-bold text-green-600">{logs.length}</p>
            <p className="text-xs text-green-400 mt-0.5">已完成任務</p>
          </div>
          <div className="bg-indigo-50 border border-indigo-100 rounded-xl p-3 text-center">
            <p className="text-lg font-bold text-indigo-600">{logs.filter(l => l.daily_task_minutes > 0).length}/{logs.length}</p>
            <p className="text-xs text-indigo-400 mt-0.5">有日常時數</p>
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
            const isExpanded = expanded[log.id] ?? true
            const hasDailyTasks = (log.daily_tasks ?? []).length > 0
            return (
              <div key={log.id} className="card border border-gray-100 hover:border-gray-200 transition-colors">
                {/* 任務標題列 */}
                <div className="flex items-start gap-3">
                  {/* 展開/收合按鈕 */}
                  <button
                    onClick={() => toggleExpand(log.id)}
                    className="w-8 h-8 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-sm flex-shrink-0 font-bold mt-0.5 hover:bg-green-200 transition-colors"
                    title={isExpanded ? '收合日常任務' : '展開日常任務'}
                  >
                    {isExpanded ? '▾' : '▸'}
                  </button>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="font-medium text-gray-900 truncate">{log.task_title}</p>
                      {/* 總工時標籤 */}
                      <span className="text-xs font-semibold text-violet-700 bg-violet-50 border border-violet-100 rounded px-1.5 py-0.5 flex-shrink-0">
                        {hasDailyTasks ? fmtHours(log.daily_task_minutes) : '—'}
                      </span>
                    </div>
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
                      {hasDailyTasks && (
                        <span className="text-violet-400">{log.daily_tasks.length} 筆日常任務</span>
                      )}
                    </div>
                  </div>
                  <button onClick={() => handleDelete(log.id)} className="text-xs text-red-400 hover:text-red-600 flex-shrink-0">刪除</button>
                </div>

                {/* 樹狀日常任務清單（可展開/收合） */}
                {isExpanded && (
                  <DailyTaskTree tasks={log.daily_tasks ?? []} />
                )}

                {/* 備註（onBlur 自動儲存） */}
                <div className="mt-3">
                  <input
                    type="text" placeholder="備註（選填）"
                    className="input w-full text-sm text-gray-500 placeholder-gray-300"
                    value={notes[log.id] ?? ''}
                    onChange={e => setNotes(v => ({ ...v, [log.id]: e.target.value }))}
                    onBlur={() => handleNoteSave(log)}
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
