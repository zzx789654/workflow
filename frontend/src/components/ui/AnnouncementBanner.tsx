import React, { useState, useEffect } from 'react'
import { api } from '../../api/client'

interface Announcement {
  id: string
  title: string
  content: string
  read_at: string | null
}

export default function AnnouncementBanner() {
  const [announcement, setAnnouncement] = useState<Announcement | null>(null)

  useEffect(() => {
    api
      .get<Announcement[]>('/announcements/')
      .then((res) => {
        const unread = res.data.find((a) => !a.read_at)
        setAnnouncement(unread ?? null)
      })
      .catch(() => {
        // silently ignore errors — banner is non-critical
      })
  }, [])

  const handleClose = async () => {
    if (!announcement) return
    try {
      await api.post(`/announcements/${announcement.id}/read`)
    } catch {
      // best-effort mark-as-read
    }
    setAnnouncement(null)
  }

  if (!announcement) return null

  const preview =
    announcement.content.length > 120
      ? announcement.content.slice(0, 120) + '…'
      : announcement.content

  return (
    <div className="bg-amber-50 border-b border-amber-200 text-amber-800 px-6 py-2 text-sm flex items-start gap-3">
      <span className="flex-shrink-0 mt-0.5">📢</span>
      <div className="flex-1 min-w-0">
        <span className="font-semibold mr-2">{announcement.title}</span>
        <span className="text-amber-700">{preview}</span>
      </div>
      <button
        onClick={handleClose}
        className="flex-shrink-0 text-amber-600 hover:text-amber-900 transition-colors font-medium"
        aria-label="關閉公告"
      >
        ✕ 關閉
      </button>
    </div>
  )
}
