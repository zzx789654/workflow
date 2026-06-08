import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { notificationsApi } from '../../api/notifications'
import { useNotificationStore } from '../../stores/notificationStore'
import type { Notification } from '../../types'

export default function NotificationBell() {
  const [unread, setUnread] = useState(0)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [open, setOpen] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()
  const refreshTick = useNotificationStore((s) => s.refreshTick)

  const load = async () => {
    try {
      const res = await notificationsApi.list()
      setUnread(res.data.unread)
      setNotifications(res.data.notifications)
    } catch { /* ignore */ }
  }

  // 初始載入 + 30 秒輪詢
  useEffect(() => {
    load()
    timerRef.current = setInterval(load, 30_000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [])

  // WS 通知事件觸發即時刷新
  useEffect(() => {
    if (refreshTick > 0) load()
  }, [refreshTick])

  // 點擊外部關閉
  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const handleMarkAll = async () => {
    await notificationsApi.markAllRead()
    setUnread(0)
    setNotifications((ns) => ns.map((n) => ({ ...n, read_at: new Date().toISOString() })))
  }

  const handleClick = async (n: Notification) => {
    if (!n.read_at) {
      await notificationsApi.markRead(n.id)
      setNotifications((ns) => ns.map((x) => x.id === n.id ? { ...x, read_at: new Date().toISOString() } : x))
      setUnread((u) => Math.max(u - 1, 0))
    }
    setOpen(false)
    if (n.ref_type === 'task' && n.project_id) {
      navigate(`/projects/${n.project_id}`)
    }
  }

  const typeIcon = (type: string) => {
    if (type === 'task_progress') return '📋'
    if (type === 'mention') return '💬'
    return '🔔'
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        className="relative p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-gray-500"
        onClick={() => setOpen((v) => !v)}
        aria-label="通知"
      >
        🔔
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center font-medium px-1">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-white border border-gray-200 rounded-xl shadow-lg z-50">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100">
            <span className="text-sm font-semibold text-gray-700">通知</span>
            {unread > 0 && (
              <button className="text-xs text-primary-600 hover:underline" onClick={handleMarkAll}>
                全部已讀
              </button>
            )}
          </div>
          <ul className="max-h-72 overflow-y-auto divide-y divide-gray-50">
            {notifications.length === 0 ? (
              <li className="px-4 py-6 text-sm text-gray-400 text-center">目前沒有通知</li>
            ) : notifications.map((n) => (
              <li
                key={n.id}
                className={`px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors flex gap-2.5 items-start ${!n.read_at ? 'bg-blue-50/50' : ''}`}
                onClick={() => handleClick(n)}
              >
                <span className="text-base flex-shrink-0 mt-0.5">{typeIcon(n.type)}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-gray-700 leading-snug">{n.message}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{new Date(n.created_at).toLocaleString('zh-TW')}</p>
                </div>
                {!n.read_at && (
                  <span className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0 mt-1.5" />
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
