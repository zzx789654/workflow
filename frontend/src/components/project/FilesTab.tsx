import { useEffect, useState } from 'react'
import { api } from '../../api/client'

interface ProjectFile {
  id: string
  task_id: string
  task_title: string
  user_id: string
  uploader_name: string
  filename: string
  content_type: string
  file_size: number
  created_at: string
}

interface Props { projectId: string }

const ICON: Record<string, string> = {
  'image/jpeg': '🖼️',
  'image/png': '🖼️',
  'image/gif': '🖼️',
  'image/webp': '🖼️',
  'application/pdf': '📄',
  'text/plain': '📝',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '📝',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '📊',
  'application/zip': '🗜️',
}

const fmtSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString('zh-TW', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })

export default function FilesTab({ projectId }: Props) {
  const [files, setFiles] = useState<ProjectFile[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('all')

  const load = async () => {
    setLoading(true)
    try {
      const res = await api.get<ProjectFile[]>(`/projects/${projectId}/files/`)
      setFiles(res.data)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [projectId])

  const handleDownload = (file: ProjectFile) => {
    const url = `/api/v1/projects/${projectId}/tasks/${file.task_id}/attachments/${file.id}/download`
    const a = document.createElement('a')
    a.href = url
    a.download = file.filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  // 類型分組選項
  const typeGroups = [
    { key: 'all', label: '全部' },
    { key: 'image', label: '圖片' },
    { key: 'document', label: '文件' },
    { key: 'sheet', label: '試算表' },
    { key: 'other', label: '其他' },
  ]

  const getTypeGroup = (ct: string) => {
    if (ct.startsWith('image/')) return 'image'
    if (ct === 'application/pdf' || ct.includes('word') || ct === 'text/plain') return 'document'
    if (ct.includes('sheet')) return 'sheet'
    return 'other'
  }

  const filtered = files.filter(f => {
    const matchSearch = !search || f.filename.toLowerCase().includes(search.toLowerCase()) ||
      f.task_title.toLowerCase().includes(search.toLowerCase()) ||
      f.uploader_name.toLowerCase().includes(search.toLowerCase())
    const matchType = typeFilter === 'all' || getTypeGroup(f.content_type) === typeFilter
    return matchSearch && matchType
  })

  // 統計摘要
  const totalSize = files.reduce((s, f) => s + f.file_size, 0)

  if (loading) return <div className="text-center py-16 text-gray-400">載入中…</div>

  return (
    <div>
      {/* 標題與統計 */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-gray-800">專案檔案</h2>
          <p className="text-xs text-gray-400 mt-0.5">所有任務的附件集中管理</p>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <span className="bg-gray-100 px-2.5 py-1 rounded-full">{files.length} 個檔案</span>
          <span className="bg-gray-100 px-2.5 py-1 rounded-full">共 {fmtSize(totalSize)}</span>
        </div>
      </div>

      {/* 搜尋 + 類型篩選 */}
      <div className="flex flex-wrap gap-2 mb-4 items-center">
        <input
          type="text"
          placeholder="搜尋檔名、任務、上傳者…"
          className="input flex-1 min-w-48 text-sm"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <div className="flex gap-1">
          {typeGroups.map(g => (
            <button
              key={g.key}
              onClick={() => setTypeFilter(g.key)}
              className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
                typeFilter === g.key
                  ? 'bg-primary-600 text-white border-primary-600'
                  : 'bg-white text-gray-600 border-gray-200 hover:border-gray-300'
              }`}
            >
              {g.label}
            </button>
          ))}
        </div>
      </div>

      {files.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-4xl mb-3">📎</p>
          <p className="text-base mb-1">尚無附件</p>
          <p className="text-sm">在任務詳情中上傳附件，即會顯示於此</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-gray-400 text-sm">沒有符合條件的檔案</div>
      ) : (
        <div className="space-y-2">
          {/* 表頭 */}
          <div className="hidden sm:grid grid-cols-12 gap-3 px-3 py-1.5 text-xs font-medium text-gray-400 uppercase tracking-wide border-b border-gray-100">
            <span className="col-span-4">檔案名稱</span>
            <span className="col-span-3">所屬任務</span>
            <span className="col-span-2">上傳者</span>
            <span className="col-span-1 text-right">大小</span>
            <span className="col-span-2 text-right">上傳時間</span>
          </div>

          {filtered.map(file => (
            <div
              key={file.id}
              className="grid grid-cols-1 sm:grid-cols-12 gap-1 sm:gap-3 items-center px-3 py-2.5 rounded-lg hover:bg-gray-50 border border-transparent hover:border-gray-100 transition-colors"
            >
              {/* 檔案名稱 + 下載 */}
              <div className="col-span-4 flex items-center gap-2 min-w-0">
                <span className="text-base flex-shrink-0">{ICON[file.content_type] ?? '📎'}</span>
                <div className="min-w-0 flex-1">
                  <button
                    onClick={() => handleDownload(file)}
                    className="text-sm font-medium text-primary-600 hover:text-primary-800 truncate block w-full text-left"
                    title={`下載 ${file.filename}`}
                  >
                    {file.filename}
                  </button>
                  <p className="text-xs text-gray-400">{file.content_type.split('/').pop()?.toUpperCase()}</p>
                </div>
              </div>

              {/* 所屬任務 */}
              <div className="col-span-3 min-w-0">
                <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded truncate block max-w-full">
                  {file.task_title}
                </span>
              </div>

              {/* 上傳者 */}
              <div className="col-span-2 flex items-center gap-1.5 min-w-0">
                <span className="w-5 h-5 rounded-full bg-primary-100 text-primary-600 flex-shrink-0 flex items-center justify-center text-[10px] font-bold">
                  {file.uploader_name.charAt(0).toUpperCase()}
                </span>
                <span className="text-xs text-gray-600 truncate">{file.uploader_name}</span>
              </div>

              {/* 大小 */}
              <div className="col-span-1 text-right">
                <span className="text-xs text-gray-400">{fmtSize(file.file_size)}</span>
              </div>

              {/* 時間 */}
              <div className="col-span-2 text-right">
                <span className="text-xs text-gray-400">{fmtDate(file.created_at)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
