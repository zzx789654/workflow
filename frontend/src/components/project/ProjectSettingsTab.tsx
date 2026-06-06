import { useEffect, useState } from 'react'
import { customFieldsApi } from '../../api/customFields'
import { projectsApi } from '../../api/projects'
import { toast } from '../../stores/toastStore'
import type { Project, ProjectField } from '../../types'

interface Props {
  projectId: string
  project: Project | null
  onProjectUpdate: (p: Project) => void
}

const FIELD_TYPES = [
  { value: 'text', label: '文字' },
  { value: 'number', label: '數字' },
  { value: 'date', label: '日期' },
  { value: 'select', label: '下拉選單' },
]

const RECURRENCE_OPTIONS = [
  { value: '', label: '不重複' },
  { value: 'daily', label: '每天' },
  { value: 'weekly', label: '每週' },
  { value: 'monthly', label: '每月' },
]

const MAX_FIELDS = 5

export default function ProjectSettingsTab({ projectId, project, onProjectUpdate }: Props) {
  const [fields, setFields] = useState<ProjectField[]>([])
  const [loadingFields, setLoadingFields] = useState(true)
  const [fieldName, setFieldName] = useState('')
  const [fieldType, setFieldType] = useState('text')
  const [optionsRaw, setOptionsRaw] = useState('')
  const [creatingField, setCreatingField] = useState(false)
  const [fieldError, setFieldError] = useState('')

  const [recurrenceRule, setRecurrenceRule] = useState(project?.recurrence_rule ?? '')
  const [savingRecurrence, setSavingRecurrence] = useState(false)

  useEffect(() => {
    setRecurrenceRule(project?.recurrence_rule ?? '')
  }, [project?.recurrence_rule])

  useEffect(() => {
    customFieldsApi.listFields(projectId)
      .then(r => setFields(r.data))
      .finally(() => setLoadingFields(false))
  }, [projectId])

  const handleSaveRecurrence = async () => {
    setSavingRecurrence(true)
    try {
      const res = await projectsApi.update(projectId, { recurrence_rule: recurrenceRule || null })
      onProjectUpdate(res.data)
      toast.success('重複排程已儲存')
    } catch {
      toast.error('儲存失敗')
    } finally { setSavingRecurrence(false) }
  }

  const handleCreateField = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!fieldName.trim()) return
    if (fields.length >= MAX_FIELDS) {
      setFieldError(`最多只能建立 ${MAX_FIELDS} 個自訂欄位`)
      return
    }
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

  return (
    <div className="max-w-xl space-y-8">

      {/* 重複排程 */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-1">重複排程</h2>
        <p className="text-sm text-gray-500 mb-4">設定此專案的週期性重複規則，到期後自動建立下一輪專案。</p>
        <div className="flex items-center gap-3">
          <select
            className="input text-sm flex-1"
            value={recurrenceRule}
            onChange={e => setRecurrenceRule(e.target.value)}
          >
            {RECURRENCE_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <button
            onClick={handleSaveRecurrence}
            disabled={savingRecurrence}
            className="btn-primary text-sm px-4"
          >
            {savingRecurrence ? '儲存中…' : '儲存'}
          </button>
        </div>
        {recurrenceRule && (
          <p className="text-xs text-indigo-500 mt-2">
            此專案設定為「{RECURRENCE_OPTIONS.find(o => o.value === recurrenceRule)?.label}」重複。
          </p>
        )}
      </section>

      {/* 自訂欄位 */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-1">自訂欄位</h2>
        <p className="text-sm text-gray-500 mb-4">
          為此專案的任務新增自訂欄位（最多 {MAX_FIELDS} 個），由 Manager 以上角色管理。
        </p>

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
            <p className="text-xs text-gray-400 text-right">{fields.length} / {MAX_FIELDS} 個欄位</p>
          </div>
        )}

        {fields.length < MAX_FIELDS && (
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
    </div>
  )
}
