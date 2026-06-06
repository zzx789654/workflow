import { useEffect, useState } from 'react'
import type { Task, ProjectField, FieldValue, TaskDependency, User, DailyTask } from '../../types'
import { tasksApi } from '../../api/tasks'
import { dailyTasksApi } from '../../api/dailyTasks'
import { customFieldsApi } from '../../api/customFields'
import { dependenciesApi } from '../../api/dependencies'
import { reactionsApi } from '../../api/reactions'
import { attachmentsApi } from '../../api/attachments'
import { projectsApi } from '../../api/projects'
import { useTaskStore } from '../../stores/taskStore'
import { toast } from '../../stores/toastStore'

const EMOJI_OPTIONS = ['👍', '❤️', '🎉', '🚀', '👀', '🔥', '✅', '💯']

interface Props {
  task: Task
  projectId: string
  onClose: () => void
}

const PRIORITY_LABELS: Record<string, string> = { low: '低', medium: '中', high: '高', urgent: '緊急' }
const STATUS_LABELS: Record<string, string> = { todo: '待辦', in_progress: '進行中', review: '審查中', done: '完成' }

export default function TaskDetailPanel({ task, projectId, onClose }: Props) {
  // 人員
  const [members, setMembers] = useState<User[]>([])
  const [editingAssignees, setEditingAssignees] = useState(false)
  const [selectedAssignees, setSelectedAssignees] = useState<string[]>(task.assignees.map(u => u.id))
  const [savingAssignees, setSavingAssignees] = useState(false)
  // 評論
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  // F05 自訂欄位
  const [fields, setFields] = useState<ProjectField[]>([])
  const [fieldValues, setFieldValues] = useState<Record<string, string>>({})
  const [savingFields, setSavingFields] = useState(false)
  // F06 依賴
  const [deps, setDeps] = useState<TaskDependency[]>([])
  const [allTasks, setAllTasks] = useState<Task[]>([])
  const [depTargetId, setDepTargetId] = useState('')
  const [addingDep, setAddingDep] = useState(false)
  // F11 附件
  const [attachments, setAttachments] = useState<any[]>([])
  const [uploadingFile, setUploadingFile] = useState(false)
  // F14 Emoji 反應（comment_id -> summary）
  const [reactionSummary, setReactionSummary] = useState<Record<string, Record<string, string[]>>>({})
  // 日期編輯
  const [editingDates, setEditingDates] = useState(false)
  const [draftStart, setDraftStart] = useState(task.start_date ?? '')
  const [draftEnd,   setDraftEnd]   = useState(task.end_date   ?? '')
  const [draftDue,   setDraftDue]   = useState(task.due_date   ?? '')
  const [savingDates, setSavingDates] = useState(false)

  const handleSaveDates = async () => {
    setSavingDates(true)
    try {
      await tasksApi.update(projectId, task.id, {
        start_date: draftStart || undefined,
        end_date:   draftEnd   || undefined,
        due_date:   draftDue   || undefined,
      })
      await fetchTasks(projectId)
      setEditingDates(false)
    } finally { setSavingDates(false) }
  }

  // 複製
  const [copying, setCopying] = useState(false)

  // 關聯日常任務
  const [linkedDailyTasks, setLinkedDailyTasks] = useState<DailyTask[]>([])

  const fetchTasks = useTaskStore((s) => s.fetchTasks)
  const deleteTask  = useTaskStore((s) => s.deleteTask)
  const createTask  = useTaskStore((s) => s.createTask)
  const storeTasks  = useTaskStore((s) => s.tasks)

  useEffect(() => {
    dailyTasksApi.listByTask(task.id).then(r => setLinkedDailyTasks(r.data)).catch(() => {})
    projectsApi.listMembers(projectId).then(r =>
      setMembers(r.data.map((m: { user: User }) => m.user))
    )
    customFieldsApi.listFields(projectId).then(r => {
      setFields(r.data)
      return customFieldsApi.getFieldValues(projectId, task.id)
    }).then(r => {
      const map: Record<string, string> = {}
      for (const fv of (r as { data: FieldValue[] }).data) map[fv.field_id] = fv.value ?? ''
      setFieldValues(map)
    }).catch(() => {})
    dependenciesApi.list(projectId, task.id).then(r => setDeps(r.data)).catch(() => {})
    attachmentsApi.list(projectId, task.id).then(r => setAttachments(r.data)).catch(() => {})
    setAllTasks(storeTasks.filter(t => t.id !== task.id))
    setSelectedAssignees(task.assignees.map(u => u.id))
  }, [task.id, projectId])

  // ── 人員 ──────────────────────────────────
  const toggleAssignee = (id: string) =>
    setSelectedAssignees(ids => ids.includes(id) ? ids.filter(x => x !== id) : [...ids, id])

  const handleSaveAssignees = async () => {
    setSavingAssignees(true)
    try {
      await tasksApi.update(projectId, task.id, { assignee_ids: selectedAssignees })
      await fetchTasks(projectId)
      setEditingAssignees(false)
    } finally { setSavingAssignees(false) }
  }

  // ── 評論 ──────────────────────────────────
  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!comment.trim()) return
    setSubmitting(true)
    try {
      await tasksApi.addComment(projectId, task.id, comment)
      setComment('')
      fetchTasks(projectId)
    } finally { setSubmitting(false) }
  }

  // ── F05 自訂欄位 ─────────────────────────
  const handleSaveFields = async () => {
    setSavingFields(true)
    try {
      await customFieldsApi.setFieldValues(projectId, task.id,
        fields.map(f => ({ field_id: f.id, value: fieldValues[f.id] ?? null }))
      )
    } catch { } finally { setSavingFields(false) }
  }

  // ── F11 附件 ─────────────────────────────
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadingFile(true)
    try {
      const res = await attachmentsApi.upload(projectId, task.id, file)
      setAttachments(a => [res.data, ...a])
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? '上傳失敗')
    } finally { setUploadingFile(false); e.target.value = '' }
  }

  const handleDeleteAttachment = async (id: string) => {
    await attachmentsApi.delete(projectId, task.id, id)
    setAttachments(a => a.filter(x => x.id !== id))
  }

  // ── F14 Emoji 反應 ──────────────────────
  const handleToggleReaction = async (commentId: string, emoji: string) => {
    const res = await reactionsApi.toggle(projectId, task.id, commentId, emoji)
    setReactionSummary(s => ({ ...s, [commentId]: res.data.summary }))
  }

  const loadReactions = async (commentId: string) => {
    if (reactionSummary[commentId]) return
    const res = await reactionsApi.list(projectId, task.id, commentId)
    const summary: Record<string, string[]> = {}
    for (const r of res.data) summary[r.emoji] = [...(summary[r.emoji] ?? []), r.user_id]
    setReactionSummary(s => ({ ...s, [commentId]: summary }))
  }

  // ── F06 依賴 ──────────────────────────────
  const handleAddDep = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!depTargetId) return
    setAddingDep(true)
    try {
      const res = await dependenciesApi.add(projectId, task.id, depTargetId)
      setDeps(d => [...d, res.data])
      setDepTargetId('')
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? '新增依賴失敗')
    } finally { setAddingDep(false) }
  }

  const handleRemoveDep = async (depId: string) => {
    await dependenciesApi.remove(projectId, task.id, depId)
    setDeps(d => d.filter(x => x.id !== depId))
  }

  // ── 複製 / 刪除 ───────────────────────────
  const handleCopy = async () => {
    setCopying(true)
    try {
      await createTask(projectId, {
        title: `${task.title}（副本）`,
        description: task.description ?? undefined,
        priority: task.priority,
        status: 'todo',
        due_date: task.due_date ?? undefined,
        start_date: task.start_date ?? undefined,
        end_date: task.end_date ?? undefined,
        assignee_ids: task.assignees.map(u => u.id),
      })
      onClose()
    } finally { setCopying(false) }
  }

  const handleDelete = async () => {
    if (!confirm('確定要刪除此任務？')) return
    await deleteTask(projectId, task.id)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex justify-end" onClick={onClose}>
      <div className="w-full max-w-lg bg-white h-full overflow-y-auto shadow-xl" onClick={e => e.stopPropagation()}>
        <div className="p-6 space-y-5">

          {/* 標題 */}
          <div className="flex items-start justify-between">
            <h2 className="text-xl font-bold text-gray-900 flex-1 pr-4">{task.title}</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
          </div>

          {/* 狀態 / 優先度 badges */}
          <div className="flex gap-2 flex-wrap text-sm">
            <span className="bg-gray-100 text-gray-600 px-3 py-1 rounded-full">{STATUS_LABELS[task.status]}</span>
            <span className="bg-blue-100 text-blue-600 px-3 py-1 rounded-full">{PRIORITY_LABELS[task.priority]}</span>
            {task.due_date && <span className="bg-orange-100 text-orange-600 px-3 py-1 rounded-full">截止 {task.due_date}</span>}
          </div>

          {/* 描述 */}
          {task.description && (
            <div className="p-3 bg-gray-50 rounded-lg text-sm text-gray-700 whitespace-pre-wrap">{task.description}</div>
          )}

          {/* ── 日期（起始/結束/截止，可行內編輯）─────── */}
          <div className="border-t border-gray-100 pt-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium text-gray-500">日期</p>
              <button
                className="text-xs text-primary-600 hover:underline"
                onClick={() => {
                  setDraftStart(task.start_date ?? '')
                  setDraftEnd(task.end_date ?? '')
                  setDraftDue(task.due_date ?? '')
                  setEditingDates(v => !v)
                }}
              >
                {editingDates ? '取消' : '編輯'}
              </button>
            </div>
            {editingDates ? (
              <div className="space-y-2">
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">開始日期</label>
                    <input type="date" className="input w-full text-sm"
                      value={draftStart} onChange={e => setDraftStart(e.target.value)} />
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">結束日期</label>
                    <input type="date" className="input w-full text-sm"
                      value={draftEnd} onChange={e => setDraftEnd(e.target.value)} />
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">截止日期</label>
                    <input type="date" className="input w-full text-sm"
                      value={draftDue} onChange={e => setDraftDue(e.target.value)} />
                  </div>
                </div>
                <button onClick={handleSaveDates} disabled={savingDates} className="btn-primary text-sm px-4">
                  {savingDates ? '儲存中…' : '確認'}
                </button>
              </div>
            ) : (
              <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                {task.start_date
                  ? <span className="flex items-center gap-1"><span className="text-gray-400">開始</span><span className="font-medium text-gray-700">{task.start_date}</span></span>
                  : <span className="text-gray-300">開始日期未設定</span>
                }
                {task.end_date
                  ? <span className="flex items-center gap-1"><span className="text-gray-400">結束</span><span className="font-medium text-gray-700">{task.end_date}</span></span>
                  : <span className="text-gray-300">結束日期未設定</span>
                }
                {task.due_date
                  ? <span className="flex items-center gap-1"><span className="text-gray-400">截止</span><span className="font-medium text-orange-600">{task.due_date}</span></span>
                  : <span className="text-gray-300">截止日期未設定</span>
                }
              </div>
            )}
          </div>

          {/* ── 施作人員（可多選編輯）──────────────────── */}
          <div className="border-t border-gray-100 pt-4">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium text-gray-500">施作人員</p>
              <button
                className="text-xs text-primary-600 hover:underline"
                onClick={() => { setEditingAssignees(v => !v); setSelectedAssignees(task.assignees.map(u => u.id)) }}
              >
                {editingAssignees ? '取消' : '編輯'}
              </button>
            </div>

            {!editingAssignees ? (
              task.assignees.length === 0
                ? <p className="text-sm text-gray-400">尚未指派人員</p>
                : (
                  <div className="flex gap-2 flex-wrap">
                    {task.assignees.map(u => (
                      <div key={u.id} className="flex items-center gap-1.5 text-sm bg-gray-100 rounded-full px-3 py-1">
                        <div className="w-5 h-5 rounded-full bg-primary-500 text-white text-xs flex items-center justify-center font-medium">
                          {u.display_name.charAt(0).toUpperCase()}
                        </div>
                        <span>{u.display_name}</span>
                      </div>
                    ))}
                  </div>
                )
            ) : (
              <div className="space-y-2">
                <div className="flex flex-wrap gap-2 p-2 bg-gray-50 border border-gray-200 rounded-lg">
                  {members.map(m => {
                    const sel = selectedAssignees.includes(m.id)
                    return (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => toggleAssignee(m.id)}
                        className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm border transition-colors ${
                          sel ? 'bg-primary-500 text-white border-primary-500' : 'bg-white text-gray-600 border-gray-200 hover:border-primary-300'
                        }`}
                      >
                        <div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold ${sel ? 'bg-white/30' : 'bg-primary-100 text-primary-600'}`}>
                          {m.display_name.charAt(0).toUpperCase()}
                        </div>
                        {m.display_name}
                        {sel && <span className="text-xs opacity-80">✓</span>}
                      </button>
                    )
                  })}
                </div>
                <button
                  onClick={handleSaveAssignees}
                  disabled={savingAssignees}
                  className="btn-primary text-sm px-4"
                >
                  {savingAssignees ? '儲存中…' : '確認指派'}
                </button>
              </div>
            )}
          </div>

          {/* ── 關聯日常任務 ──────────────────────────── */}
          {linkedDailyTasks.length > 0 && (
            <div className="border-t border-gray-100 pt-4">
              <p className="text-xs font-medium text-gray-500 mb-3">
                🔗 關聯日常任務（{linkedDailyTasks.length}）
              </p>
              <div className="space-y-1.5">
                {linkedDailyTasks.map(dt => {
                  const statusColor: Record<string, string> = {
                    pending: 'bg-gray-100 text-gray-500',
                    in_progress: 'bg-blue-100 text-blue-600',
                    done: 'bg-green-100 text-green-600',
                    cancelled: 'bg-red-100 text-red-400',
                  }
                  const statusLabel: Record<string, string> = {
                    pending: '待辦', in_progress: '進行中', done: '完成', cancelled: '已取消',
                  }
                  return (
                    <div key={dt.id} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-violet-50 border border-violet-100">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium flex-shrink-0 ${statusColor[dt.status]}`}>
                        {statusLabel[dt.status]}
                      </span>
                      <span className={`flex-1 text-sm truncate ${dt.status === 'done' ? 'line-through text-gray-400' : 'text-gray-700'}`}>
                        {dt.title}
                      </span>
                      <span className="text-xs text-gray-400 flex-shrink-0">{dt.date}</span>
                      {dt.work_minutes > 0 && (
                        <span className="text-xs text-violet-500 flex-shrink-0">
                          {Math.round(dt.work_minutes / 60 * 10) / 10}h
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
              {/* 工時加總 */}
              {linkedDailyTasks.some(dt => dt.work_minutes > 0) && (
                <p className="text-xs text-gray-400 mt-2 text-right">
                  累計工時：{Math.round(linkedDailyTasks.reduce((s, dt) => s + dt.work_minutes, 0) / 60 * 10) / 10}h
                </p>
              )}
            </div>
          )}

          {/* ── F05 自訂欄位 ──────────────────────────── */}
          {fields.length > 0 && (
            <div className="border-t border-gray-100 pt-4">
              <p className="text-xs font-medium text-gray-500 mb-3">自訂欄位</p>
              <div className="space-y-2">
                {fields.map(f => (
                  <div key={f.id} className="flex items-center gap-2">
                    <label className="text-xs text-gray-500 w-24 flex-shrink-0 truncate">{f.name}</label>
                    {f.field_type === 'select' && f.options?.choices ? (
                      <select className="input flex-1 text-sm" value={fieldValues[f.id] ?? ''} onChange={e => setFieldValues(v => ({ ...v, [f.id]: e.target.value }))}>
                        <option value="">— 請選擇 —</option>
                        {f.options.choices.map(c => <option key={c} value={c}>{c}</option>)}
                      </select>
                    ) : f.field_type === 'date' ? (
                      <input type="date" className="input flex-1 text-sm" value={fieldValues[f.id] ?? ''} onChange={e => setFieldValues(v => ({ ...v, [f.id]: e.target.value }))} />
                    ) : f.field_type === 'number' ? (
                      <input type="number" className="input flex-1 text-sm" value={fieldValues[f.id] ?? ''} onChange={e => setFieldValues(v => ({ ...v, [f.id]: e.target.value }))} />
                    ) : (
                      <input type="text" className="input flex-1 text-sm" value={fieldValues[f.id] ?? ''} onChange={e => setFieldValues(v => ({ ...v, [f.id]: e.target.value }))} />
                    )}
                  </div>
                ))}
              </div>
              <button onClick={handleSaveFields} disabled={savingFields} className="mt-2 btn-secondary text-xs px-3">
                {savingFields ? '儲存中…' : '儲存欄位值'}
              </button>
            </div>
          )}

          {/* ── F06 任務依賴 ──────────────────────────── */}
          <div className="border-t border-gray-100 pt-4">
            <p className="text-xs font-medium text-gray-500 mb-3">前置任務</p>
            {deps.length === 0
              ? <p className="text-xs text-gray-400 mb-2">尚無設定</p>
              : (
                <ul className="space-y-1 mb-3">
                  {deps.map(dep => {
                    const t = allTasks.find(x => x.id === dep.to_task_id)
                    return (
                      <li key={dep.id} className="flex items-center gap-2 text-sm">
                        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${t?.status === 'done' ? 'bg-green-500' : 'bg-orange-400'}`} />
                        <span className={`flex-1 truncate ${t?.status === 'done' ? 'text-gray-400 line-through' : 'text-gray-700'}`}>{t?.title ?? dep.to_task_id}</span>
                        <button className="text-xs text-red-400 hover:text-red-600" onClick={() => handleRemoveDep(dep.id)}>✕</button>
                      </li>
                    )
                  })}
                </ul>
              )
            }
            {allTasks.length > 0 && (
              <form onSubmit={handleAddDep} className="flex gap-2">
                <select className="input flex-1 text-sm" value={depTargetId} onChange={e => setDepTargetId(e.target.value)}>
                  <option value="">選擇前置任務…</option>
                  {allTasks.filter(t => !deps.some(d => d.to_task_id === t.id)).map(t => (
                    <option key={t.id} value={t.id}>{t.title}</option>
                  ))}
                </select>
                <button type="submit" disabled={addingDep || !depTargetId} className="btn-secondary px-3 text-sm">
                  {addingDep ? '…' : '+ 新增'}
                </button>
              </form>
            )}
          </div>

          {/* ── 評論 ────────────────────────────────── */}
          <div className="border-t border-gray-100 pt-4">
            <p className="text-xs font-medium text-gray-500 mb-3">評論 ({task.comments.length})</p>
            <div className="space-y-3 mb-4">
              {task.comments.map(c => (
                <div key={c.id} className="flex gap-2">
                  <div className="w-7 h-7 rounded-full bg-primary-500 text-white text-xs flex items-center justify-center flex-shrink-0 font-medium">
                    {c.author.display_name.charAt(0).toUpperCase()}
                  </div>
                  <div className="flex-1">
                    <p className="text-xs font-medium text-gray-700">{c.author.display_name}</p>
                    <p className="text-sm text-gray-600 whitespace-pre-wrap">{c.content}</p>
                    <p className="text-xs text-gray-400">{new Date(c.created_at).toLocaleString('zh-TW')}</p>
                    {/* F14 Emoji 反應 */}
                    <div className="flex flex-wrap items-center gap-1 mt-1">
                      {Object.entries(reactionSummary[c.id] ?? {}).map(([emoji, users]) => (
                        <button
                          key={emoji}
                          onClick={() => handleToggleReaction(c.id, emoji)}
                          className="flex items-center gap-0.5 text-xs bg-gray-100 hover:bg-primary-50 border border-gray-200 rounded-full px-1.5 py-0.5"
                        >
                          <span>{emoji}</span>
                          <span className="text-gray-600">{users.length}</span>
                        </button>
                      ))}
                      <div className="flex gap-0.5 ml-1">
                        {EMOJI_OPTIONS.map(e => (
                          <button
                            key={e}
                            onClick={() => handleToggleReaction(c.id, e)}
                            className="text-sm hover:scale-125 transition-transform opacity-40 hover:opacity-100"
                          >
                            {e}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <form onSubmit={handleAddComment} className="flex gap-2">
              <input
                className="input flex-1"
                placeholder="新增評論（@名稱 可 mention）…"
                value={comment}
                onChange={e => setComment(e.target.value)}
              />
              <button type="submit" disabled={submitting} className="btn-primary px-3">送出</button>
            </form>
          </div>

          {/* ── F11 附件 ────────────────────────────── */}
          <div className="border-t border-gray-100 pt-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-medium text-gray-500">附件（{attachments.length}）</p>
              <label className={`text-xs cursor-pointer ${uploadingFile ? 'text-gray-400' : 'text-primary-600 hover:text-primary-800'}`}>
                {uploadingFile ? '上傳中…' : '+ 上傳檔案'}
                <input
                  type="file"
                  className="hidden"
                  disabled={uploadingFile}
                  onChange={handleFileUpload}
                  accept="image/*,.pdf,.txt,.docx,.xlsx,.zip"
                />
              </label>
            </div>
            {attachments.length > 0 && (
              <div className="space-y-1">
                {attachments.map(a => (
                  <div key={a.id} className="flex items-center gap-2 text-xs text-gray-600 py-1">
                    <span className="flex-1 truncate">{a.filename}</span>
                    <span className="text-gray-400">{Math.round(a.file_size / 1024)}KB</span>
                    <a
                      href={attachmentsApi.downloadUrl(projectId, task.id, a.id)}
                      className="text-primary-600 hover:underline"
                      download={a.filename}
                    >下載</a>
                    <button onClick={() => handleDeleteAttachment(a.id)} className="text-red-300 hover:text-red-500">✕</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* ── 複製 / 刪除 ─────────────────────────── */}
          <div className="border-t border-gray-100 pt-4 flex items-center justify-between">
            <button onClick={handleCopy} disabled={copying} className="text-sm text-blue-500 hover:text-blue-700 disabled:opacity-50">
              {copying ? '複製中…' : '📋 複製任務'}
            </button>
            <button onClick={handleDelete} className="text-sm text-red-500 hover:text-red-700">刪除任務</button>
          </div>
        </div>
      </div>
    </div>
  )
}
