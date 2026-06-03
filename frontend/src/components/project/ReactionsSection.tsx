import React, { useState, useRef, useEffect } from 'react'
import { api } from '../../api/client'

interface Reaction {
  emoji: string
  count: number
  reacted: boolean
}

interface Props {
  projectId: string
  taskId: string
  commentId: string
  initialReactions?: Reaction[]
}

const COMMON_EMOJIS = ['👍', '❤️', '😂', '🎉', '🚀', '👀']

export default function ReactionsSection({ projectId, taskId, commentId, initialReactions = [] }: Props) {
  const [reactions, setReactions] = useState<Reaction[]>(initialReactions)
  const [pickerOpen, setPickerOpen] = useState(false)
  const pickerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setPickerOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const toggleReaction = async (emoji: string) => {
    const existing = reactions.find((r) => r.emoji === emoji)
    const alreadyReacted = existing?.reacted ?? false
    const baseUrl = `/projects/${projectId}/tasks/${taskId}/comments/${commentId}/reactions`

    try {
      if (alreadyReacted) {
        await api.delete(`${baseUrl}/${encodeURIComponent(emoji)}`)
        setReactions((prev) =>
          prev
            .map((r) =>
              r.emoji === emoji ? { ...r, count: r.count - 1, reacted: false } : r
            )
            .filter((r) => r.count > 0)
        )
      } else {
        await api.post(baseUrl, { emoji })
        setReactions((prev) => {
          const found = prev.find((r) => r.emoji === emoji)
          if (found) {
            return prev.map((r) =>
              r.emoji === emoji ? { ...r, count: r.count + 1, reacted: true } : r
            )
          }
          return [...prev, { emoji, count: 1, reacted: true }]
        })
      }
    } catch {
      // silently ignore reaction errors
    }
    setPickerOpen(false)
  }

  return (
    <div className="flex items-center gap-1 flex-wrap mt-1">
      {reactions.map((r) => (
        <button
          key={r.emoji}
          onClick={() => toggleReaction(r.emoji)}
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-sm border transition-colors ${
            r.reacted
              ? 'bg-indigo-50 border-indigo-300 text-indigo-700'
              : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'
          }`}
        >
          <span>{r.emoji}</span>
          <span className="text-xs font-medium">{r.count}</span>
        </button>
      ))}

      <div className="relative" ref={pickerRef}>
        <button
          onClick={() => setPickerOpen((o) => !o)}
          className="inline-flex items-center justify-center w-7 h-7 rounded-full border border-gray-200 text-gray-400 hover:text-gray-600 hover:bg-gray-100 text-sm transition-colors"
          title="新增回應"
        >
          +
        </button>
        {pickerOpen && (
          <div className="absolute left-0 bottom-full mb-1 bg-white border border-gray-200 rounded-lg shadow-lg p-2 flex gap-1 z-10">
            {COMMON_EMOJIS.map((emoji) => (
              <button
                key={emoji}
                onClick={() => toggleReaction(emoji)}
                className="text-lg hover:scale-125 transition-transform px-1"
                title={emoji}
              >
                {emoji}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
