import { useEffect, useRef } from 'react'
import type { WsEvent } from '../types'
import { useTaskStore } from '../stores/taskStore'
import { wsBase } from '../lib/ws'

export function useProjectWs(projectId: string) {
  const ws = useRef<WebSocket | null>(null)
  const applyWsEvent = useTaskStore((s) => s.applyWsEvent)
  const setWsConnected = useTaskStore((s) => s.setWsConnected)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token || !projectId) return

    const url = `${wsBase()}/ws/${projectId}?token=${encodeURIComponent(token)}`
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
