import { useEffect, useRef } from 'react'
import { useNotificationStore } from '../stores/notificationStore'
import { wsBase } from '../lib/ws'

export function useNotificationWs() {
  const bump = useNotificationStore((s) => s.bump)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) return

    const connect = () => {
      const ws = new WebSocket(`${wsBase()}/ws/notifications?token=${encodeURIComponent(token)}`)
      wsRef.current = ws

      ws.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data)
          if (event.type === 'notification') bump()
        } catch { /* ignore */ }
      }

      ws.onclose = () => {
        // 斷線後 5 秒重連
        setTimeout(connect, 5000)
      }
    }

    connect()
    return () => {
      wsRef.current?.close()
    }
  }, [])
}
