import { useEffect, useState } from 'react'
import { addDays, differenceInDays, format, startOfDay, parseISO, isValid } from 'date-fns'
import { tasksApi } from '../../api/tasks'
import type { Task } from '../../types'

const PRIORITY_COLORS: Record<string, string> = {
  low: '#94a3b8', medium: '#6366f1', high: '#f97316', urgent: '#ef4444',
}
const STATUS_LABELS: Record<string, string> = {
  todo: '待辦', in_progress: '進行中', review: '審查', done: '完成',
}

const DAY_PX = 24  // 每天寬度（px）

function getRange(tasks: Task[]) {
  const dates = tasks.flatMap(t => [
    t.start_date ? parseISO(t.start_date) : null,
    t.end_date ? parseISO(t.end_date) : null,
    t.due_date ? parseISO(t.due_date) : null,
  ]).filter((d): d is Date => d !== null && isValid(d))
  if (!dates.length) return { start: startOfDay(new Date()), days: 30 }
  const min = new Date(Math.min(...dates.map(d => d.getTime())))
  const max = new Date(Math.max(...dates.map(d => d.getTime())))
  const start = addDays(startOfDay(min), -2)
  const days = Math.max(differenceInDays(max, start) + 5, 30)
  return { start, days }
}

interface Props { projectId: string }

export default function GanttTab({ projectId }: Props) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    tasksApi.list(projectId).then(r => setTasks(r.data)).finally(() => setLoading(false))
  }, [projectId])

  const withDates = tasks.filter(t => t.start_date || t.end_date || t.due_date)

  if (loading) return <div className="text-center py-16 text-gray-400">載入中…</div>
  if (!withDates.length) return (
    <div className="text-center py-16 text-gray-400">
      <p className="text-lg mb-2">尚無含日期的任務</p>
      <p className="text-sm">在任務上設定「開始日期」或「結束日期」即可顯示甘特圖</p>
    </div>
  )

  const { start, days } = getRange(withDates)
  const totalW = days * DAY_PX

  const today = startOfDay(new Date())
  const todayOffset = differenceInDays(today, start)

  // 月份標籤
  const months: { label: string; offset: number; width: number }[] = []
  let cur = new Date(start)
  while (cur <= addDays(start, days)) {
    const monthStart = new Date(cur.getFullYear(), cur.getMonth(), 1)
    const monthEnd = new Date(cur.getFullYear(), cur.getMonth() + 1, 0)
    const startOff = Math.max(0, differenceInDays(monthStart < start ? start : monthStart, start))
    const endOff = Math.min(days, differenceInDays(monthEnd, start))
    months.push({ label: format(cur, 'yyyy年M月'), offset: startOff, width: (endOff - startOff + 1) * DAY_PX })
    cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1)
    if (cur > addDays(start, days)) break
  }

  return (
    <div className="overflow-x-auto">
      <div className="min-w-max">
        {/* 標題列 */}
        <div className="flex border-b border-gray-200">
          <div className="w-56 flex-shrink-0 text-xs font-medium text-gray-500 px-3 py-2 bg-gray-50">任務</div>
          <div className="relative bg-gray-50" style={{ width: totalW }}>
            {/* 月份標籤 */}
            {months.map(m => (
              <div key={m.label}
                className="absolute top-0 border-l border-gray-200 text-xs text-gray-500 px-2 py-2 overflow-hidden whitespace-nowrap"
                style={{ left: m.offset * DAY_PX, width: m.width }}
              >{m.label}</div>
            ))}
          </div>
        </div>

        {/* 任務列 */}
        {withDates.map(task => {
          const sDate = task.start_date ? parseISO(task.start_date) : task.due_date ? parseISO(task.due_date) : null
          const eDate = task.end_date ? parseISO(task.end_date) : task.due_date ? parseISO(task.due_date) : null
          if (!sDate || !eDate) return null

          const left = differenceInDays(sDate, start) * DAY_PX
          const width = Math.max((differenceInDays(eDate, sDate) + 1) * DAY_PX, DAY_PX)
          const color = PRIORITY_COLORS[task.priority] ?? '#6366f1'
          const done = task.status === 'done'

          return (
            <div key={task.id} className="flex border-b border-gray-100 hover:bg-gray-50 group">
              {/* 任務名稱欄 */}
              <div className="w-56 flex-shrink-0 px-3 py-2 flex items-center gap-2 min-w-0">
                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                <div className="min-w-0">
                  <p className={`text-sm truncate ${done ? 'line-through text-gray-400' : 'text-gray-800'}`}>{task.title}</p>
                  <p className="text-xs text-gray-400">{STATUS_LABELS[task.status]}</p>
                </div>
              </div>

              {/* 時間軸 */}
              <div className="relative" style={{ width: totalW, height: 48 }}>
                {/* 今日線 */}
                {todayOffset >= 0 && todayOffset <= days && (
                  <div className="absolute top-0 bottom-0 border-l-2 border-red-400 border-dashed z-10"
                    style={{ left: todayOffset * DAY_PX }} />
                )}

                {/* 任務橫條 */}
                <div
                  className="absolute top-3 h-6 rounded flex items-center px-2 text-white text-xs font-medium overflow-hidden whitespace-nowrap shadow-sm"
                  style={{ left, width, backgroundColor: color, opacity: done ? 0.5 : 1 }}
                  title={`${format(sDate, 'M/d')} ~ ${format(eDate, 'M/d')}`}
                >
                  {task.progress > 0 && (
                    <div className="absolute left-0 top-0 bottom-0 bg-black/20 rounded-l"
                      style={{ width: `${task.progress}%` }} />
                  )}
                  <span className="relative truncate">{task.title}</span>
                </div>

                {/* actual_end 標記 */}
                {task.actual_end_date && (() => {
                  const aDate = parseISO(task.actual_end_date)
                  const aLeft = differenceInDays(aDate, start) * DAY_PX
                  return (
                    <div className="absolute top-2 w-3 h-3 rounded-full bg-green-500 border-2 border-white z-20"
                      style={{ left: aLeft - 6 }} title={`實際完成 ${task.actual_end_date}`} />
                  )
                })()}
              </div>
            </div>
          )
        })}
      </div>

      {/* 圖例 */}
      <div className="flex items-center gap-6 mt-4 px-2 text-xs text-gray-500 flex-wrap">
        {Object.entries(PRIORITY_COLORS).map(([p, c]) => (
          <span key={p} className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-sm inline-block" style={{ backgroundColor: c }} />
            {p === 'low' ? '低' : p === 'medium' ? '中' : p === 'high' ? '高' : '緊急'} 優先
          </span>
        ))}
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-green-500 inline-block" />
          實際完成日
        </span>
        <span className="flex items-center gap-1">
          <span className="border-l-2 border-red-400 border-dashed h-3 inline-block" />
          今日
        </span>
      </div>
    </div>
  )
}
