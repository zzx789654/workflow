import { useEffect, useRef, useState } from 'react'
import { notificationsApi } from '../../api/notifications'
import type { Notification } from '../../types'

export default function NotificationBell() {
  const [unread, setUnread] = useState(0)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [open, setOpen] = useState(false)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = async () => {
    try {
      const res = await notificationsApi.list()
      setUnread(res.data.unread)
      setNotifications(res.data.notifications)
    } catch { /* ignore */ }
  }

  useEffect(() => {
    load()
    timerRef.current = setInterval(load, 30_000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [])

  const handleOpen = () => {
    setOpen((v) => !v)
  }

  const handleMarkAll = async () => {
    await notificationsApi.markAllRead()
    setUnread(0)
    setNotifications((ns) => ns.map((n) => ({ ...n, read_at: new Date().toISOString() })))
  }

  const handleMarkOne = async (id: string) => {
    await notificationsApi.markRead(id)
    setNotifications((ns) => ns.map((n) => n.id === id ? { ...n, read_at: new Date().toISOString() } : n))
    setUnread((u) => Math.max(u - 1, 0))
  }

  return (
    <div className="relative">
      <button
        className="relative p-1.5 rounded-lg hover:bg-gray-100 transition-colors text-gray-500"
        onClick={handleOpen}
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
        <div
          className="absolute right-0 top-full mt-2 w-80 bg-white border border-gray-200 rounded-xl shadow-lg z-50"
          onBlur={() => setOpen(false)}
        >
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
                className={`px-4 py-3 hover:bg-gray-50 cursor-pointer transition-colors ${!n.read_at ? 'bg-blue-50/50' : ''}`}
                onClick={() => !n.read_at && handleMarkOne(n.id)}
              >
                <p className="text-sm text-gray-700">{n.message}</p>
                <p className="text-xs text-gray-400 mt-0.5">{new Date(n.created_at).toLocaleString('zh-TW')}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
