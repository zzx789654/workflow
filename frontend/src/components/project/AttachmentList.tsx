import React, { useState, useEffect, useRef } from 'react'
import { api } from '../../api/client'

interface Attachment {
  id: string
  filename: string
  size: number
  created_at: string
}

interface Props {
  projectId: string
  taskId: string
}

const MAX_SIZE_BYTES = 10 * 1024 * 1024 // 10MB

export default function AttachmentList({ projectId, taskId }: Props) {
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const baseUrl = `/projects/${projectId}/tasks/${taskId}/attachments`

  const fetchAttachments = async () => {
    setLoading(true)
    try {
      const res = await api.get<Attachment[]>(baseUrl)
      setAttachments(res.data)
    } catch {
      // silently handle fetch error
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAttachments()
  }, [projectId, taskId])

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (file.size > MAX_SIZE_BYTES) {
      alert('檔案大小不可超過 10MB')
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await api.post<Attachment>(baseUrl, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setAttachments((prev) => [res.data, ...prev])
    } catch {
      alert('上傳失敗，請稍後再試')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('確定要刪除此附件？')) return
    try {
      await api.delete(`${baseUrl}/${id}`)
      setAttachments((prev) => prev.filter((a) => a.id !== id))
    } catch {
      alert('刪除失敗，請稍後再試')
    }
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    return `${(bytes / 1024).toFixed(1)} KB`
  }

  return (
    <div className="border-t border-gray-100 pt-4 space-y-3">
      <p className="text-xs font-medium text-gray-500">附件</p>

      {/* Upload area */}
      <div
        className="border-2 border-dashed border-gray-200 rounded-lg p-4 text-center hover:border-indigo-300 transition-colors cursor-pointer"
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={handleFileChange}
          disabled={uploading}
        />
        {uploading ? (
          <p className="text-sm text-gray-400">上傳中…</p>
        ) : (
          <>
            <p className="text-sm text-gray-500">點擊上傳檔案</p>
            <p className="text-xs text-gray-400 mt-1">最大 10MB</p>
          </>
        )}
      </div>

      {/* Attachment list */}
      {loading ? (
        <p className="text-sm text-gray-400 text-center py-2">載入中…</p>
      ) : attachments.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-2">尚無附件</p>
      ) : (
        <ul className="space-y-2">
          {attachments.map((a) => (
            <li
              key={a.id}
              className="flex items-center gap-3 p-2 bg-gray-50 rounded-lg text-sm"
            >
              <span className="text-gray-400 text-base">📎</span>
              <div className="flex-1 min-w-0">
                <a
                  href={`/api/v1/attachments/${a.id}/file`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-indigo-600 hover:text-indigo-800 truncate block font-medium"
                >
                  {a.filename}
                </a>
                <p className="text-xs text-gray-400">{formatSize(a.size)}</p>
              </div>
              <button
                onClick={() => handleDelete(a.id)}
                className="text-gray-300 hover:text-red-500 transition-colors flex-shrink-0 text-xs"
                title="刪除"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
