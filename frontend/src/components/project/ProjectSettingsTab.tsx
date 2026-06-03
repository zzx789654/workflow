import { useEffect, useState } from 'react'
import { customFieldsApi } from '../../api/customFields'
import type { ProjectField } from '../../types'
import { useAuthStore } from '../../stores/authStore'

interface Props { projectId: string }

const FIELD_TYPES = [
  { value: 'text', label: '文字' },
  { value: 'number', label: '數字' },
  { value: 'date', label: '日期' },
  { value: 'select', label: '下拉選單' },
]

export default function ProjectSettingsTab({ projectId }: Props) {
  const [fields, setFields] = useState<ProjectField[]>([])
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState('')
  const [fieldType, setFieldType] = useState('text')
  const [optionsRaw, setOptionsRaw] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const user = useAuthStore((s) => s.user)

  const load = async () => {
    setLoading(true)
    try {
      const res = await customFieldsApi.listFields(projectId)
      setFields(res.data)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [projectId])

  const isManager = user?.role === 'admin' ||
    // ProjectRole 由後端控制；前端只依 user.role admin 顯示此 tab；
    // Manager check 在後端強制，前端 admin 也可操作
    user?.role === 'admin'

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    setError('')
    setCreating(true)
    try {
      const options = fieldType === 'select'
        ? optionsRaw.split(',').map((s) => s.trim()).filter(Boolean)
        : undefined
      const res = await customFieldsApi.createField(projectId, { name: name.trim(), field_type: fieldType, options })
      setFields((f) => [...f, res.data])
      setName('')
      setOptionsRaw('')
      setFieldType('text')
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? '建立失敗')
    } finally { setCreating(false) }
  }

  const handleDelete = async (fieldId: string) => {
    if (!confirm('確定刪除此自訂欄位？所有任務的此欄位值將一併移除。')) return
    await customFieldsApi.deleteField(projectId, fieldId)
    setFields((f) => f.filter((x) => x.id !== fieldId))
  }

  if (loading) return <div className="text-center py-16 text-gray-400">載入中…</div>

  return (
    <div className="max-w-xl space-y-6">
      <div>
        <h2 className="text-base font-semibold text-gray-800 mb-1">自訂欄位</h2>
        <p className="text-sm text-gray-500">為此專案的任務新增自訂欄位（最多 10 個），由 Manager 以上角色管理。</p>
      </div>

      {/* 現有欄位列表 */}
      {fields.length === 0 ? (
        <div className="text-sm text-gray-400 py-6 text-center border border-dashed border-gray-200 rounded-xl">
          尚無自訂欄位
        </div>
      ) : (
        <div className="space-y-2">
          {fields.map((f) => (
            <div key={f.id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl border border-gray-100">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800">{f.name}</p>
                <p className="text-xs text-gray-400">
                  {FIELD_TYPES.find((t) => t.value === f.field_type)?.label ?? f.field_type}
                  {f.options?.choices && f.options.choices.length > 0
                    ? `：${f.options.choices.join('、')}`
                    : ''}
                </p>
              </div>
              <button
                onClick={() => handleDelete(f.id)}
                className="text-xs text-red-400 hover:text-red-600 flex-shrink-0"
              >
                刪除
              </button>
            </div>
          ))}
          <p className="text-xs text-gray-400 text-right">{fields.length} / 10 個欄位</p>
        </div>
      )}

      {/* 新增欄位表單 */}
      {fields.length < 10 && (
        <form onSubmit={handleCreate} className="card space-y-3">
          <p className="text-sm font-medium text-gray-700">新增欄位</p>
          {error && <p className="text-xs text-red-500">{error}</p>}
          <div className="flex gap-2">
            <input
              className="input flex-1 text-sm"
              placeholder="欄位名稱"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={100}
            />
            <select
              className="input w-32 text-sm"
              value={fieldType}
              onChange={(e) => { setFieldType(e.target.value); setOptionsRaw('') }}
            >
              {FIELD_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          {fieldType === 'select' && (
            <input
              className="input w-full text-sm"
              placeholder="選項（逗號分隔，例：待確認,進行中,已完成）"
              value={optionsRaw}
              onChange={(e) => setOptionsRaw(e.target.value)}
            />
          )}
          <button type="submit" disabled={creating} className="btn-primary text-sm">
            {creating ? '建立中…' : '+ 新增欄位'}
          </button>
        </form>
      )}
    </div>
  )
}
