import { useEffect, useRef } from 'react'
import type { WsEvent } from '../types'
import { useTaskStore } from '../stores/taskStore'

const WS_BASE = import.meta.env.VITE_WS_URL ?? ''

export function useProjectWs(projectId: string) {
  const ws = useRef<WebSocket | null>(null)
  const applyWsEvent = useTaskStore((s) => s.applyWsEvent)
  const setWsConnected = useTaskStore((s) => s.setWsConnected)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token || !projectId) return

    const url = `${WS_BASE}/ws/${projectId}?token=${encodeURIComponent(token)}`
    ws.current = new WebSocket(url)

    ws.current.onopen = () => setWsConnected(true)
    ws.current.onclose = () => setWsConnected(false)
    ws.current.onerror = () => setWsConnected(false)
    ws.current.onmessage = (e) => {
      try {
        const event: WsEvent = JSON.parse(e.data)
        applyWsEvent(event, projectId)
      } catch {
        // ignore malformed messages
      }
    }

    return () => {
      ws.current?.close()
      setWsConnected(false)
    }
  }, [projectId])
}
