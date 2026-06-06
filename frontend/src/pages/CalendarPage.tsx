import { useEffect, useState } from 'react'
import { format, getDaysInMonth, startOfMonth, getDay, addMonths, subMonths, parseISO } from 'date-fns'
import { calendarApi } from '../api/calendar'
import type { CalendarEvent } from '../types'

const TYPE_COLORS: Record<string, string> = {
  task: 'bg-indigo-100 text-indigo-700',
  daily: 'bg-emerald-100 text-emerald-700',
}
const STATUS_DOT: Record<string, string> = {
  todo: 'bg-gray-400', pending: 'bg-gray-400',
  in_progress: 'bg-blue-500',
  review: 'bg-yellow-500',
  done: 'bg-green-500', cancelled: 'bg-red-400',
}

export default function CalendarPage() {
  const [viewDate, setViewDate] = useState(new Date())
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [filterLabel, setFilterLabel] = useState('')
  const [selectedDay, setSelectedDay] = useState<string | null>(null)

  const year = viewDate.getFullYear()
  const month = viewDate.getMonth() + 1

  const load = async () => {
    setLoading(true)
    try {
      const res = await calendarApi.getEvents(year, month, filterLabel || undefined)
      setEvents(res.data)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [year, month, filterLabel])

  // Calendar grid
  const daysInMonth = getDaysInMonth(viewDate)
  const firstDow = getDay(startOfMonth(viewDate))  // 0=Sun

  const cells: (number | null)[] = [...Array(firstDow).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)]
  while (cells.length % 7 !== 0) cells.push(null)

  const eventsByDay = events.reduce<Record<string, CalendarEvent[]>>((acc, e) => {
    const d = e.date
    if (!acc[d]) acc[d] = []
    acc[d].push(e)
    return acc
  }, {})

  const allLabels = Array.from(new Set(events.flatMap(e => e.labels)))

  const selectedDayEvents = selectedDay ? eventsByDay[selectedDay] ?? [] : []

  return (
    <div className="max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-gray-900">月曆</h1>
        <div className="flex items-center gap-3 flex-wrap">
          <select className="input w-40" value={filterLabel} onChange={e => setFilterLabel(e.target.value)}>
            <option value="">全部標籤</option>
            {allLabels.map(l => <option key={l} value={l}>{l}</option>)}
          </select>
          <div className="flex items-center gap-2">
            <button className="btn-secondary px-3" onClick={() => setViewDate(d => subMonths(d, 1))}>‹</button>
            <span className="text-sm font-medium text-gray-700 w-24 text-center">{format(viewDate, 'yyyy年M月')}</span>
            <button className="btn-secondary px-3" onClick={() => setViewDate(d => addMonths(d, 1))}>›</button>
          </div>
          <button className="btn-secondary text-sm" onClick={() => setViewDate(new Date())}>今月</button>
        </div>
      </div>

      {/* 月曆本體 */}
      <div>
        {/* 星期標題 */}
        <div className="grid grid-cols-7 mb-1">
          {['日', '一', '二', '三', '四', '五', '六'].map(d => (
            <div key={d} className="text-xs font-medium text-gray-400 text-center py-1">{d}</div>
          ))}
        </div>

        {/* 日期格子 */}
        <div className="grid grid-cols-7 gap-0.5">
          {cells.map((day, i) => {
            if (!day) return <div key={`e-${i}`} className="bg-gray-50 rounded-lg min-h-[80px]" />
            const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
            const dayEvents = eventsByDay[dateStr] ?? []
            const isToday = dateStr === format(new Date(), 'yyyy-MM-dd')
            const isSelected = selectedDay === dateStr

            return (
              <div
                key={dateStr}
                className={`rounded-lg min-h-[80px] p-1 cursor-pointer transition-colors ${
                  isSelected ? 'ring-2 ring-primary-500 bg-primary-50'
                  : isToday ? 'bg-indigo-50'
                  : 'bg-white hover:bg-gray-50'
                } border border-gray-100`}
                onClick={() => setSelectedDay(isSelected ? null : dateStr)}
              >
                <div className={`text-xs font-medium mb-1 w-6 h-6 flex items-center justify-center rounded-full ${
                  isToday ? 'bg-primary-600 text-white' : 'text-gray-700'
                }`}>{day}</div>
                <div className="space-y-0.5">
                  {dayEvents.slice(0, 3).map(ev => (
                    <div key={ev.id}
                      className={`text-xs px-1 py-0.5 rounded truncate flex items-center gap-1 ${TYPE_COLORS[ev.type]}`}
                      title={ev.project_name ? `[${ev.project_name}] ${ev.title}` : ev.title}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${STATUS_DOT[ev.status] ?? 'bg-gray-400'}`} />
                      <span className="truncate">
                        {ev.type === 'task' && ev.project_name && (
                          <span className="opacity-60 mr-0.5">[{ev.project_name}]</span>
                        )}
                        {ev.title}
                      </span>
                    </div>
                  ))}
                  {dayEvents.length > 3 && (
                    <p className="text-xs text-gray-400 pl-1">+{dayEvents.length - 3} 更多</p>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {/* 圖例 */}
        <div className="flex gap-4 mt-3 text-xs text-gray-400 flex-wrap">
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-indigo-100 border border-indigo-200" />專案任務</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-100 border border-emerald-200" />日常作業</span>
        </div>
      </div>

      {/* 下方：選取日期的事項清單 */}
      {selectedDay && (
        <div className="mt-6 border-t border-gray-100 pt-5">
          <h3 className="font-semibold text-gray-900 mb-4">
            {format(parseISO(selectedDay), 'M月d日')}
            <span className="text-sm font-normal text-gray-400 ml-2">{selectedDayEvents.length} 件事項</span>
          </h3>
          {selectedDayEvents.length === 0 ? (
            <p className="text-sm text-gray-400">當日無事項</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
              {selectedDayEvents.map(ev => (
                <div key={ev.id} className={`p-3 rounded-xl border ${ev.type === 'task' ? 'border-indigo-100 bg-indigo-50' : 'border-emerald-100 bg-emerald-50'}`}>
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_DOT[ev.status] ?? 'bg-gray-400'}`} />
                    <span className={`text-xs font-medium ${ev.type === 'task' ? 'text-indigo-600' : 'text-emerald-600'}`}>
                      {ev.type === 'task' ? `任務${ev.project_name ? ` · ${ev.project_name}` : ''}` : '日常作業'}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-gray-800 leading-snug">{ev.title}</p>
                  {ev.labels.length > 0 && (
                    <div className="flex gap-1 flex-wrap mt-2">
                      {ev.labels.map(l => (
                        <span key={l} className="text-xs bg-white border border-gray-200 px-1.5 py-0.5 rounded-full text-gray-500">{l}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {loading && (
        <div className="fixed inset-0 bg-white/50 flex items-center justify-center z-50">
          <div className="text-gray-400">載入中…</div>
        </div>
      )}
    </div>
  )
}
