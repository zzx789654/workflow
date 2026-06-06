import { useEffect, useRef, useState } from 'react'
import { addDays, differenceInDays, format, startOfDay, parseISO, isValid } from 'date-fns'
import { tasksApi } from '../../api/tasks'
import { dependenciesApi } from '../../api/dependencies'
import type { Task, TaskDependency } from '../../types'

const PRIORITY_COLORS: Record<string, string> = {
  low: '#94a3b8', medium: '#6366f1', high: '#f97316', urgent: '#ef4444',
}
const STATUS_LABELS: Record<string, string> = {
  todo: '待辦', in_progress: '進行中', review: '審查', done: '完成',
}

const DAY_PX = 24
const ROW_H = 48
const NAME_W = 224  // 任務名稱欄寬 (px)

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

// 收集一個任務的所有依賴（跨任務）
async function loadAllDeps(tasks: Task[], projectId: string): Promise<TaskDependency[]> {
  const all: TaskDependency[] = []
  await Promise.all(
    tasks.map((t) =>
      dependenciesApi.list(projectId, t.id)
        .then((r) => all.push(...r.data))
        .catch(() => {})
    )
  )
  return all
}

interface Props { projectId: string }

export default function GanttTab({ projectId }: Props) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [deps, setDeps] = useState<TaskDependency[]>([])
  const [loading, setLoading] = useState(true)
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    tasksApi.list(projectId).then(async (r) => {
      const taskList = r.data
      setTasks(taskList)
      const allDeps = await loadAllDeps(taskList, projectId)
      setDeps(allDeps)
    }).finally(() => setLoading(false))
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

  // 計算每條任務橫條的 x, y 中心（用於繪製箭頭）
  const barInfo: Record<string, { x: number; y: number; right: number }> = {}
  withDates.forEach((task, idx) => {
    const sDate = task.start_date ? parseISO(task.start_date) : task.due_date ? parseISO(task.due_date) : null
    const eDate = task.end_date ? parseISO(task.end_date) : task.due_date ? parseISO(task.due_date) : null
    if (!sDate || !eDate) return
    const left = differenceInDays(sDate, start) * DAY_PX
    const width = Math.max((differenceInDays(eDate, sDate) + 1) * DAY_PX, DAY_PX)
    const y = idx * ROW_H + ROW_H / 2 + 32  // 32 = header height
    barInfo[task.id] = { x: left, y, right: left + width }
  })

  // 篩選出 from 和 to 都在 withDates 裡的依賴
  const visibleDeps = deps.filter(
    (d) => barInfo[d.from_task_id] && barInfo[d.to_task_id]
  )

  return (
    <div className="overflow-x-auto">
      <div className="min-w-max relative">
        {/* 標題列 */}
        <div className="flex border-b border-gray-200">
          <div className="flex-shrink-0 text-xs font-medium text-gray-500 px-3 py-2 bg-gray-50" style={{ width: NAME_W }}>任務</div>
          <div className="relative bg-gray-50" style={{ width: totalW }}>
            {months.map(m => (
              <div key={m.label}
                className="absolute top-0 border-l border-gray-200 text-xs text-gray-500 px-2 py-2 overflow-hidden whitespace-nowrap"
                style={{ left: m.offset * DAY_PX, width: m.width }}
              >{m.label}</div>
            ))}
          </div>
        </div>

        {/* 任務列 */}
        {withDates.map((task) => {
          const sDate = task.start_date ? parseISO(task.start_date) : task.due_date ? parseISO(task.due_date) : null
          const eDate = task.end_date ? parseISO(task.end_date) : task.due_date ? parseISO(task.due_date) : null
          if (!sDate || !eDate) return null

          const left = differenceInDays(sDate, start) * DAY_PX
          const width = Math.max((differenceInDays(eDate, sDate) + 1) * DAY_PX, DAY_PX)
          const color = PRIORITY_COLORS[task.priority] ?? '#6366f1'
          const done = task.status === 'done'
          // F06: 判斷是否有未完成的前置任務（被鎖定）
          const blockedByDep = deps.some(
            (d) => d.to_task_id === task.id &&
              tasks.find((t) => t.id === d.from_task_id)?.status !== 'done'
          )

          return (
            <div key={task.id} className="flex border-b border-gray-100 hover:bg-gray-50 group">
              {/* 任務名稱欄 */}
              <div className="flex-shrink-0 px-3 py-2 flex items-center gap-2 min-w-0" style={{ width: NAME_W }}>
                <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
                <div className="min-w-0 flex-1">
                  <p className={`text-sm truncate ${done ? 'line-through text-gray-400' : 'text-gray-800'}`}>{task.title}</p>
                  <p className="text-xs text-gray-400 flex items-center gap-1">
                    {STATUS_LABELS[task.status]}
                    {blockedByDep && <span className="text-orange-500" title="有未完成前置任務">🔒</span>}
                  </p>
                </div>
              </div>

              {/* 時間軸 */}
              <div className="relative" style={{ width: totalW, height: ROW_H }}>
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

        {/* F06 依賴箭頭 SVG 疊加層 */}
        {visibleDeps.length > 0 && (
          <svg
            ref={svgRef}
            className="absolute top-0 left-0 pointer-events-none z-20"
            style={{ width: NAME_W + totalW, height: withDates.length * ROW_H + 32 }}
          >
            <defs>
              <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                <path d="M0,0 L0,6 L6,3 z" fill="#94a3b8" />
              </marker>
            </defs>
            {visibleDeps.map((dep) => {
              const from = barInfo[dep.from_task_id]
              const to = barInfo[dep.to_task_id]
              if (!from || !to) return null
              const x1 = NAME_W + from.right
              const y1 = from.y
              const x2 = NAME_W + to.x
              const y2 = to.y
              const elbow = 10
              // 直角折線：右出 elbow → 垂直到目標行 → 水平入左端
              // 若 to 在 from 左側或空間不足，向下繞行
              const path = x1 + elbow <= x2 - elbow
                ? `M${x1},${y1} H${x1 + elbow} V${y2} H${x2}`
                : `M${x1},${y1} h${elbow} V${y1 + ROW_H * 0.45} H${x2 - elbow} V${y2} H${x2}`
              const fromTitle = tasks.find(t => t.id === dep.from_task_id)?.title ?? ''
              const toTitle   = tasks.find(t => t.id === dep.to_task_id)?.title ?? ''
              return (
                <g key={dep.id}>
                  {/* 加粗透明路徑提升 hover 命中區域 */}
                  <path d={path} fill="none" stroke="transparent" strokeWidth="10" />
                  <path
                    d={path}
                    fill="none"
                    stroke="#94a3b8"
                    strokeWidth="1.5"
                    strokeDasharray="5 3"
                    markerEnd="url(#arrow)"
                    opacity="0.55"
                  >
                    <title>{fromTitle} → {toTitle}</title>
                  </path>
                </g>
              )
            })}
          </svg>
        )}
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
        <span className="flex items-center gap-1">
          <svg width="24" height="12"><path d="M2,6 H10 V6 H22" stroke="#94a3b8" strokeWidth="1.5" strokeDasharray="5 3" fill="none" markerEnd="url(#arrow)" /></svg>
          任務依賴
        </span>
        <span className="flex items-center gap-1">
          🔒 被阻擋（有未完成前置任務）
        </span>
      </div>
    </div>
  )
}
