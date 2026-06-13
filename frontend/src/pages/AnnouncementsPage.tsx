import { useEffect, useState } from 'react'
import { announcementsApi } from '../api/announcements'
import { confirm } from '../stores/confirmStore'
import { useAuthStore } from '../stores/authStore'

export default function AnnouncementsPage() {
  const user = useAuthStore(s => s.user)
  const [list, setList] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [saving, setSaving] = useState(false)

  const fetchList = () => {
    announcementsApi.list().then(r => setList(r.data)).finally(() => setLoading(false))
  }
  useEffect(() => { fetchList() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim() || !content.trim()) return
    setSaving(true)
    try {
      await announcementsApi.create(title, content)
      setTitle(''); setContent(''); setCreating(false)
      fetchList()
    } finally { setSaving(false) }
  }

  const handleRead = async (id: string) => {
    await announcementsApi.markRead(id)
    setList(l => l.map(a => a.id === id ? { ...a, is_read: true } : a))
  }

  const handleDeactivate = async (id: string) => {
    if (!(await confirm({ title: '關閉公告', message: '確定要關閉此公告？', confirmLabel: '關閉' }))) return
    await announcementsApi.deactivate(id)
    setList(l => l.filter(a => a.id !== id))
  }

  if (loading) return <div className="p-8 text-center text-gray-400">載入中…</div>

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-gray-900">公告板</h1>
        {user?.role === 'admin' && !creating && (
          <button onClick={() => setCreating(true)} className="btn-primary text-sm">+ 發布公告</button>
        )}
      </div>

      {creating && (
        <form onSubmit={handleCreate} className="bg-white border border-gray-200 rounded-xl p-4 mb-6 space-y-3">
          <input
            className="input w-full"
            placeholder="公告標題"
            value={title}
            onChange={e => setTitle(e.target.value)}
          />
          <textarea
            className="input w-full min-h-[80px]"
            placeholder="公告內容"
            value={content}
            onChange={e => setContent(e.target.value)}
          />
          <div className="flex gap-2">
            <button type="submit" disabled={saving} className="btn-primary text-sm">
              {saving ? '發布中…' : '發布'}
            </button>
            <button type="button" onClick={() => setCreating(false)} className="btn-secondary text-sm">取消</button>
          </div>
        </form>
      )}

      {list.length === 0 ? (
        <div className="p-8 text-center text-gray-400">目前無公告</div>
      ) : (
        <div className="space-y-3">
          {list.map(a => (
            <div key={a.id} className={`bg-white border rounded-xl p-4 ${a.is_read ? 'border-gray-100' : 'border-primary-200 bg-primary-50/30'}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    {!a.is_read && <span className="w-2 h-2 rounded-full bg-primary-500 flex-shrink-0" />}
                    <h3 className="font-medium text-gray-900 text-sm">{a.title}</h3>
                  </div>
                  <p className="text-sm text-gray-600 whitespace-pre-wrap">{a.content}</p>
                  <p className="text-xs text-gray-400 mt-2">
                    {new Date(a.created_at).toLocaleString('zh-TW')}
                    {a.expires_at && ` · 到期 ${new Date(a.expires_at).toLocaleDateString('zh-TW')}`}
                  </p>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  {!a.is_read && (
                    <button onClick={() => handleRead(a.id)} className="text-xs text-primary-600 hover:text-primary-800">
                      標記已讀
                    </button>
                  )}
                  {user?.role === 'admin' && (
                    <button onClick={() => handleDeactivate(a.id)} className="text-xs text-red-400 hover:text-red-600">
                      關閉
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
