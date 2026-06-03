import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { webhooksApi, type Webhook } from '../api/webhooks'

const ALL_EVENTS = ['task.created', 'task.updated', 'task.deleted', 'milestone.completed', 'member.added']

export default function WebhookSettingsPage() {
  const { projectId = '' } = useParams()
  const [webhooks, setWebhooks] = useState<Webhook[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [url, setUrl] = useState('')
  const [events, setEvents] = useState<string[]>(['task.created', 'task.updated'])
  const [saving, setSaving] = useState(false)
  const [testResults, setTestResults] = useState<Record<string, string>>({})

  const load = () => {
    setLoading(true)
    webhooksApi.list(projectId)
      .then((r) => setWebhooks(r.data))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [projectId])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim() || events.length === 0) return
    setSaving(true)
    try {
      await webhooksApi.create(projectId, { url, events, is_active: true })
      setUrl('')
      setEvents(['task.created', 'task.updated'])
      setShowForm(false)
      load()
    } finally {
      setSaving(false)
    }
  }

  const handleToggle = async (wh: Webhook) => {
    await webhooksApi.update(projectId, wh.id, { is_active: !wh.is_active })
    load()
  }

  const handleDelete = async (id: string) => {
    if (!confirm('確定要刪除此 Webhook？')) return
    await webhooksApi.delete(projectId, id)
    load()
  }

  const handleTest = async (id: string) => {
    setTestResults((r) => ({ ...r, [id]: '測試中…' }))
    try {
      const res = await webhooksApi.test(projectId, id)
      const { success, status_code, detail } = res.data
      setTestResults((r) => ({
        ...r,
        [id]: success ? `✅ 成功 (${status_code})` : `❌ 失敗 (${status_code}) — ${detail}`,
      }))
    } catch {
      setTestResults((r) => ({ ...r, [id]: '❌ 請求失敗' }))
    }
  }

  const toggleEvent = (ev: string) => {
    setEvents((prev) =>
      prev.includes(ev) ? prev.filter((e) => e !== ev) : [...prev, ev]
    )
  }

  if (loading) return <div className="text-center py-20 text-gray-400">載入中…</div>

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Webhook 設定</h1>
          <p className="text-sm text-gray-400 mt-0.5">任務/里程碑事件觸發時自動 POST 到指定 URL</p>
        </div>
        <button onClick={() => setShowForm((s) => !s)} className="btn-primary">
          {showForm ? '取消' : '+ 新增 Webhook'}
        </button>
      </div>

      {showForm && (
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">新增 Webhook</h2>
          <form onSubmit={handleCreate} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">目標 URL</label>
              <input
                className="input"
                type="url"
                placeholder="https://hooks.example.com/..."
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">訂閱事件</label>
              <div className="flex flex-wrap gap-2">
                {ALL_EVENTS.map((ev) => (
                  <label key={ev} className="flex items-center gap-1.5 text-sm cursor-pointer">
                    <input
                      type="checkbox"
                      checked={events.includes(ev)}
                      onChange={() => toggleEvent(ev)}
                      className="rounded"
                    />
                    <span className="font-mono text-xs bg-gray-100 px-2 py-0.5 rounded">{ev}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="flex gap-3">
              <button type="submit" disabled={saving || events.length === 0} className="btn-primary">
                {saving ? '儲存中…' : '儲存'}
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">取消</button>
            </div>
          </form>
        </div>
      )}

      {webhooks.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg mb-2">尚無 Webhook</p>
          <p className="text-sm">點擊「新增 Webhook」開始設定</p>
        </div>
      ) : (
        <div className="space-y-3">
          {webhooks.map((wh) => (
            <div key={wh.id} className="card">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`w-2 h-2 rounded-full flex-shrink-0 ${wh.is_active ? 'bg-green-500' : 'bg-gray-300'}`} />
                    <p className="text-sm font-mono text-gray-800 truncate">{wh.url}</p>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {wh.events.map((ev) => (
                      <span key={ev} className="text-xs font-mono bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                        {ev}
                      </span>
                    ))}
                  </div>
                  {testResults[wh.id] && (
                    <p className="text-xs mt-2 text-gray-600">{testResults[wh.id]}</p>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={() => handleToggle(wh)}
                    className={`text-xs px-2.5 py-1 rounded-full border transition-colors ${
                      wh.is_active
                        ? 'border-green-300 text-green-700 hover:bg-green-50'
                        : 'border-gray-300 text-gray-500 hover:bg-gray-50'
                    }`}
                  >
                    {wh.is_active ? '啟用中' : '已停用'}
                  </button>
                  <button
                    onClick={() => handleTest(wh.id)}
                    className="text-xs px-2.5 py-1 rounded border border-gray-300 text-gray-600 hover:bg-gray-50"
                  >
                    測試
                  </button>
                  <button
                    onClick={() => handleDelete(wh.id)}
                    className="text-xs text-red-400 hover:text-red-600"
                  >
                    刪除
                  </button>
                </div>
              </div>
              <p className="text-xs text-gray-400 mt-2">
                建立於 {new Date(wh.created_at).toLocaleString('zh-TW')}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
