import { useEffect, useState } from 'react'
import { customFieldsApi } from '../../api/customFields'
import { webhooksApi, type WebhookOut, type WebhookCreate } from '../../api/webhooks'
import type { ProjectField } from '../../types'

interface Props { projectId: string }

const FIELD_TYPES = [
  { value: 'text', label: '文字' },
  { value: 'number', label: '數字' },
  { value: 'date', label: '日期' },
  { value: 'select', label: '下拉選單' },
]

const VALID_EVENTS = [
  { value: 'task.created', label: '任務建立' },
  { value: 'task.updated', label: '任務更新' },
  { value: 'task.completed', label: '任務完成' },
  { value: 'milestone.completed', label: '里程碑完成' },
  { value: 'comment.created', label: '評論新增' },
]

export default function ProjectSettingsTab({ projectId }: Props) {
  // ── 自訂欄位 ──────────────────────────────
  const [fields, setFields] = useState<ProjectField[]>([])
  const [loadingFields, setLoadingFields] = useState(true)
  const [fieldName, setFieldName] = useState('')
  const [fieldType, setFieldType] = useState('text')
  const [optionsRaw, setOptionsRaw] = useState('')
  const [creatingField, setCreatingField] = useState(false)
  const [fieldError, setFieldError] = useState('')

  // ── Webhooks ──────────────────────────────
  const [webhooks, setWebhooks] = useState<WebhookOut[]>([])
  const [loadingWebhooks, setLoadingWebhooks] = useState(true)
  const [whName, setWhName] = useState('')
  const [whUrl, setWhUrl] = useState('')
  const [whSecret, setWhSecret] = useState('')
  const [whEvents, setWhEvents] = useState<string[]>([])
  const [creatingWh, setCreatingWh] = useState(false)
  const [whError, setWhError] = useState('')

  useEffect(() => {
    customFieldsApi.listFields(projectId)
      .then(r => setFields(r.data))
      .finally(() => setLoadingFields(false))
    webhooksApi.list(projectId)
      .then(r => setWebhooks(r.data))
      .catch(() => setWebhooks([]))
      .finally(() => setLoadingWebhooks(false))
  }, [projectId])

  const handleCreateField = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!fieldName.trim()) return
    setFieldError('')
    setCreatingField(true)
    try {
      const options = fieldType === 'select'
        ? optionsRaw.split(',').map(s => s.trim()).filter(Boolean)
        : undefined
      const res = await customFieldsApi.createField(projectId, { name: fieldName.trim(), field_type: fieldType, options })
      setFields(f => [...f, res.data])
      setFieldName('')
      setOptionsRaw('')
      setFieldType('text')
    } catch (err: any) {
      setFieldError(err?.response?.data?.detail ?? '建立失敗')
    } finally { setCreatingField(false) }
  }

  const handleDeleteField = async (fieldId: string) => {
    if (!confirm('確定刪除此自訂欄位？所有任務的此欄位值將一併移除。')) return
    await customFieldsApi.deleteField(projectId, fieldId)
    setFields(f => f.filter(x => x.id !== fieldId))
  }

  const toggleWhEvent = (ev: string) =>
    setWhEvents(prev => prev.includes(ev) ? prev.filter(x => x !== ev) : [...prev, ev])

  const handleCreateWebhook = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!whName.trim() || !whUrl.trim()) return
    setWhError('')
    setCreatingWh(true)
    try {
      const data: WebhookCreate = {
        name: whName.trim(),
        url: whUrl.trim(),
        events: whEvents,
        ...(whSecret.trim() ? { secret: whSecret.trim() } : {}),
      }
      const res = await webhooksApi.create(projectId, data)
      setWebhooks(w => [...w, res.data])
      setWhName('')
      setWhUrl('')
      setWhSecret('')
      setWhEvents([])
    } catch (err: any) {
      setWhError(err?.response?.data?.detail ?? '建立失敗')
    } finally { setCreatingWh(false) }
  }

  const handleDeleteWebhook = async (webhookId: string) => {
    if (!confirm('確定刪除此 Webhook？')) return
    await webhooksApi.delete(projectId, webhookId)
    setWebhooks(w => w.filter(x => x.id !== webhookId))
  }

  return (
    <div className="max-w-xl space-y-8">
      {/* ── 自訂欄位 ── */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-1">自訂欄位</h2>
        <p className="text-sm text-gray-500 mb-4">為此專案的任務新增自訂欄位（最多 10 個），由 Manager 以上角色管理。</p>

        {loadingFields ? (
          <div className="text-center py-8 text-gray-400 text-sm">載入中…</div>
        ) : fields.length === 0 ? (
          <div className="text-sm text-gray-400 py-6 text-center border border-dashed border-gray-200 rounded-xl">
            尚無自訂欄位
          </div>
        ) : (
          <div className="space-y-2 mb-4">
            {fields.map(f => (
              <div key={f.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl border border-gray-100">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800">{f.name}</p>
                  <p className="text-xs text-gray-400">
                    {FIELD_TYPES.find(t => t.value === f.field_type)?.label ?? f.field_type}
                    {f.options?.choices && f.options.choices.length > 0
                      ? `：${f.options.choices.join('、')}`
                      : ''}
                  </p>
                </div>
                <button onClick={() => handleDeleteField(f.id)} className="text-xs text-red-400 hover:text-red-600 flex-shrink-0">
                  刪除
                </button>
              </div>
            ))}
            <p className="text-xs text-gray-400 text-right">{fields.length} / 10 個欄位</p>
          </div>
        )}

        {fields.length < 10 && (
          <form onSubmit={handleCreateField} className="card space-y-3">
            <p className="text-sm font-medium text-gray-700">新增欄位</p>
            {fieldError && <p className="text-xs text-red-500">{fieldError}</p>}
            <div className="flex gap-2">
              <input
                className="input flex-1 text-sm"
                placeholder="欄位名稱"
                value={fieldName}
                onChange={e => setFieldName(e.target.value)}
                required
                maxLength={100}
              />
              <select
                className="input w-32 text-sm"
                value={fieldType}
                onChange={e => { setFieldType(e.target.value); setOptionsRaw('') }}
              >
                {FIELD_TYPES.map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            {fieldType === 'select' && (
              <input
                className="input w-full text-sm"
                placeholder="選項（逗號分隔，例：待確認,進行中,已完成）"
                value={optionsRaw}
                onChange={e => setOptionsRaw(e.target.value)}
              />
            )}
            <button type="submit" disabled={creatingField} className="btn-primary text-sm">
              {creatingField ? '建立中…' : '+ 新增欄位'}
            </button>
          </form>
        )}
      </section>

      {/* ── Webhooks ── */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-1">Webhook 整合</h2>
        <p className="text-sm text-gray-500 mb-4">設定對外 Webhook，在專案事件發生時通知外部服務。需 Manager 以上角色。</p>

        {loadingWebhooks ? (
          <div className="text-center py-8 text-gray-400 text-sm">載入中…</div>
        ) : webhooks.length === 0 ? (
          <div className="text-sm text-gray-400 py-6 text-center border border-dashed border-gray-200 rounded-xl">
            尚無 Webhook
          </div>
        ) : (
          <div className="space-y-2 mb-4">
            {webhooks.map(wh => (
              <div key={wh.id} className="p-3 bg-gray-50 rounded-xl border border-gray-100">
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800">{wh.name}</p>
                    <p className="text-xs text-gray-500 truncate">{wh.url}</p>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {wh.events.map(ev => (
                        <span key={ev} className="text-xs bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded-full">
                          {VALID_EVENTS.find(e => e.value === ev)?.label ?? ev}
                        </span>
                      ))}
                    </div>
                    {wh.last_triggered_at && (
                      <p className="text-xs text-gray-400 mt-1">
                        上次觸發：{new Date(wh.last_triggered_at).toLocaleString('zh-TW')}
                      </p>
                    )}
                  </div>
                  <button onClick={() => handleDeleteWebhook(wh.id)} className="text-xs text-red-400 hover:text-red-600 flex-shrink-0">
                    刪除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={handleCreateWebhook} className="card space-y-3">
          <p className="text-sm font-medium text-gray-700">新增 Webhook</p>
          {whError && <p className="text-xs text-red-500">{whError}</p>}
          <input
            className="input w-full text-sm"
            placeholder="名稱（例：Slack 通知）"
            value={whName}
            onChange={e => setWhName(e.target.value)}
            required
            maxLength={200}
          />
          <input
            className="input w-full text-sm"
            placeholder="Endpoint URL（https://...）"
            value={whUrl}
            onChange={e => setWhUrl(e.target.value)}
            required
            type="url"
          />
          <input
            className="input w-full text-sm"
            placeholder="簽名密鑰（選填，用於 HMAC-SHA256 驗證）"
            type="password"
            autoComplete="new-password"
            value={whSecret}
            onChange={e => setWhSecret(e.target.value)}
            maxLength={200}
          />
          <div>
            <p className="text-xs text-gray-600 mb-1.5">訂閱事件（至少選一）</p>
            <div className="flex flex-wrap gap-2">
              {VALID_EVENTS.map(ev => (
                <label key={ev.value} className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={whEvents.includes(ev.value)}
                    onChange={() => toggleWhEvent(ev.value)}
                    className="accent-primary-500"
                  />
                  <span className="text-xs text-gray-700">{ev.label}</span>
                </label>
              ))}
            </div>
          </div>
          <button
            type="submit"
            disabled={creatingWh || whEvents.length === 0}
            className="btn-primary text-sm"
          >
            {creatingWh ? '建立中…' : '+ 新增 Webhook'}
          </button>
        </form>
      </section>
    </div>
  )
}
