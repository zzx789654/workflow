import { useEffect, useRef, useState } from 'react'
import type { Task, SubTask, ProjectField, FieldValue, TaskDependency, TimeLog, User } from '../../types'
import { tasksApi } from '../../api/tasks'
import { subtasksApi } from '../../api/subtasks'
import { customFieldsApi } from '../../api/customFields'
import { recurringApi, type RecurrenceRule } from '../../api/recurring'
import { dependenciesApi } from '../../api/dependencies'
import { timeLogsApi } from '../../api/timeLogs'
import { reactionsApi } from '../../api/reactions'
import { attachmentsApi } from '../../api/attachments'
import { checkinsApi } from '../../api/checkins'
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

// 子任務三狀態循環：待開始 → 執行中 → 已完成 → 待開始
const SUBTASK_STATUSES = ['todo', 'in_progress', 'done'] as const
const SUBTASK_STATUS_LABELS: Record<string, string> = { todo: '待開始', in_progress: '執行中', done: '已完成' }
const SUBTASK_STATUS_COLORS: Record<string, string> = {
  todo: 'bg-gray-100 text-gray-500',
  in_progress: 'bg-blue-100 text-blue-600',
  done: 'bg-green-100 text-green-600',
}

function nextSubtaskStatus(current: string): typeof SUBTASK_STATUSES[number] {
  const idx = SUBTASK_STATUSES.indexOf(current as typeof SUBTASK_STATUSES[number])
  return SUBTASK_STATUSES[(idx + 1) % SUBTASK_STATUSES.length]
}

export default function TaskDetailPanel({ task, projectId, onClose }: Props) {
  // 子任務
  const [subtasks, setSubtasks] = useState<SubTask[]>([])
  const [newSubtask, setNewSubtask] = useState('')
  const [expandedSubtask, setExpandedSubtask] = useState<string | null>(null)
  const [subtaskWorkHours, setSubtaskWorkHours] = useState<Record<string, string>>({})
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
  // F15 Check-in
  const [checkins, setCheckins] = useState<any[]>([])
  const [checkinContent, setCheckinContent] = useState('')
  const [checkinProgress, setCheckinProgress] = useState(0)
  const [addingCheckin, setAddingCheckin] = useState(false)
  // F07 時間追蹤
  const [timeLogs, setTimeLogs] = useState<TimeLog[]>([])
  const [runningLog, setRunningLog] = useState<TimeLog | null>(null)
  const [timerElapsed, setTimerElapsed] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [manualMinutes, setManualMinutes] = useState('')
  const [manualNote, setManualNote] = useState('')
  const [addingManual, setAddingManual] = useState(false)
  const [timerNote, setTimerNote] = useState('')
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

  // F10 重複排程
  const [recurrenceRule, setRecurrenceRule] = useState<RecurrenceRule | ''>(
    (task.recurrence_rule as RecurrenceRule) ?? ''
  )
  const [savingRecurrence, setSavingRecurrence] = useState(false)

  // 複製
  const [copying, setCopying] = useState(false)

  const fetchTasks = useTaskStore((s) => s.fetchTasks)
  const deleteTask  = useTaskStore((s) => s.deleteTask)
  const createTask  = useTaskStore((s) => s.createTask)
  const storeTasks  = useTaskStore((s) => s.tasks)

  useEffect(() => {
    subtasksApi.list(projectId, task.id).then(r => setSubtasks(r.data))
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
    timeLogsApi.list(projectId, task.id).then(r => {
      setTimeLogs(r.data)
      const running = r.data.find((l: TimeLog) => !l.ended_at) ?? null
      setRunningLog(running)
      if (running) {
        const elapsed = Math.floor((Date.now() - new Date(running.started_at).getTime()) / 60000)
        setTimerElapsed(elapsed)
      }
    }).catch(() => {})
    attachmentsApi.list(projectId, task.id).then(r => setAttachments(r.data)).catch(() => {})
    checkinsApi.list(projectId, task.id).then(r => setCheckins(r.data)).catch(() => {})
    setAllTasks(storeTasks.filter(t => t.id !== task.id))
    setSelectedAssignees(task.assignees.map(u => u.id))
  }, [task.id, projectId])

  // 計時器 tick
  useEffect(() => {
    if (runningLog) {
      timerRef.current = setInterval(() => {
        setTimerElapsed(Math.floor((Date.now() - new Date(runningLog.started_at).getTime()) / 60000))
      }, 30000)
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [runningLog])

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

  // ── 子任務 ────────────────────────────────
  const handleAddSubtask = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newSubtask.trim()) return
    const res = await subtasksApi.create(projectId, task.id, newSubtask.trim())
    setSubtasks(s => [...s, res.data])
    setNewSubtask('')
    fetchTasks(projectId)
  }

  const handleSubtaskStatusCycle = async (st: SubTask) => {
    const next = nextSubtaskStatus(st.status)
    const res = await subtasksApi.update(projectId, task.id, st.id, { status: next })
    setSubtasks(s => s.map(x => x.id === st.id ? res.data : x))
    fetchTasks(projectId)
  }

  const handleSubtaskProgress = async (st: SubTask, progress: number) => {
    const res = await subtasksApi.update(projectId, task.id, st.id, { progress })
    setSubtasks(s => s.map(x => x.id === st.id ? res.data : x))
  }

  const handleSubtaskDelete = async (st: SubTask) => {
    await subtasksApi.delete(projectId, task.id, st.id)
    setSubtasks(s => s.filter(x => x.id !== st.id))
    fetchTasks(projectId)
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

  // ── F15 Check-in ─────────────────────────
  const handleAddCheckin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!checkinContent.trim()) return
    setAddingCheckin(true)
    try {
      const res = await checkinsApi.create(projectId, task.id, checkinContent, checkinProgress)
      setCheckins(c => [res.data, ...c])
      setCheckinContent('')
      setCheckinProgress(0)
    } finally { setAddingCheckin(false) }
  }

  // ── F07 時間追蹤 ─────────────────────────
  const handleStartTimer = async () => {
    const res = await timeLogsApi.start(projectId, task.id, timerNote || undefined)
    setRunningLog(res.data)
    setTimerElapsed(0)
    setTimeLogs(l => [res.data, ...l])
    setTimerNote('')
  }

  const handleStopTimer = async () => {
    if (!runningLog) return
    const res = await timeLogsApi.stop(projectId, task.id, runningLog.id)
    setRunningLog(null)
    setTimeLogs(l => l.map(x => x.id === res.data.id ? res.data : x))
  }

  const handleManualLog = async (e: React.FormEvent) => {
    e.preventDefault()
    const mins = parseInt(manualMinutes)
    if (!mins || mins < 1) return
    setAddingManual(true)
    try {
      const res = await timeLogsApi.manual(projectId, task.id, mins, manualNote || undefined)
      setTimeLogs(l => [res.data, ...l])
      setManualMinutes('')
      setManualNote('')
    } finally { setAddingManual(false) }
  }

  const handleDeleteLog = async (logId: string) => {
    await timeLogsApi.delete(projectId, task.id, logId)
    setTimeLogs(l => l.filter(x => x.id !== logId))
  }

  const totalMinutes = timeLogs.filter(l => l.ended_at).reduce((s, l) => s + (l.minutes ?? 0), 0)
  const fmtMins = (m: number) => m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${m}m`

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

  // ── F10 重複排程 ──────────────────────────
  const handleSaveRecurrence = async () => {
    setSavingRecurrence(true)
    try {
      if (recurrenceRule) {
        await recurringApi.set(projectId, task.id, recurrenceRule)
      } else {
        await recurringApi.remove(projectId, task.id)
      }
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? '儲存失敗')
    } finally { setSavingRecurrence(false) }
  }

  const handleSpawnNext = async () => {
    if (!confirm('確定要立即產生下一筆重複任務？')) return
    try {
      await recurringApi.spawnNext(projectId, task.id)
      toast.success('已產生下一筆任務！')
      fetchTasks(projectId)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? '產生失敗')
    }
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
            {task.subtask_count > 0 && (
              <span className="bg-purple-100 text-purple-600 px-3 py-1 rounded-full">
                子任務 {task.subtask_done_count}/{task.subtask_count}
              </span>
            )}
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

          {/* ── 子任務（可展開編輯）──────────────────────── */}
          <div className="border-t border-gray-100 pt-4">
            <p className="text-xs font-medium text-gray-500 mb-3">
              細項任務（{subtasks.length}）
            </p>
            <div className="space-y-2 mb-3">
              {subtasks.map(st => (
                <div key={st.id} className="border border-gray-100 rounded-xl overflow-hidden">
                  {/* 摘要列 */}
                  <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 hover:bg-gray-100 transition-colors">
                    {/* 狀態循環按鈕 */}
                    <button
                      type="button"
                      onClick={() => handleSubtaskStatusCycle(st)}
                      className={`flex-shrink-0 text-xs px-2 py-0.5 rounded-full font-medium border-0 transition-colors ${SUBTASK_STATUS_COLORS[st.status] ?? 'bg-gray-100 text-gray-500'}`}
                      title="點擊切換狀態"
                    >
                      {SUBTASK_STATUS_LABELS[st.status] ?? st.status}
                    </button>
                    <span
                      className={`flex-1 text-sm cursor-pointer select-none ${st.status === 'done' ? 'line-through text-gray-400' : 'text-gray-700'}`}
                      onClick={() => setExpandedSubtask(expandedSubtask === st.id ? null : st.id)}
                    >
                      {st.title}
                    </span>
                    {/* 進度快覽 */}
                    {st.progress > 0 && st.status !== 'done' && (
                      <span className="text-xs text-gray-400 flex-shrink-0">{st.progress}%</span>
                    )}
                    <button
                      onClick={() => setExpandedSubtask(expandedSubtask === st.id ? null : st.id)}
                      className="text-gray-400 text-xs flex-shrink-0"
                    >
                      {expandedSubtask === st.id ? '▲' : '▼'}
                    </button>
                  </div>

                  {/* 展開區：進度 + 工時 + 刪除 */}
                  {expandedSubtask === st.id && (
                    <div className="px-3 py-3 space-y-3 bg-white border-t border-gray-100">
                      {/* 執行進度 */}
                      <div>
                        <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                          <span>執行進度</span>
                          <span className="font-medium">{st.progress}%</span>
                        </div>
                        <input
                          type="range" min={0} max={100} value={st.progress}
                          className="w-full accent-primary-500"
                          onChange={e => handleSubtaskProgress(st, +e.target.value)}
                        />
                        <div className="flex justify-between text-xs text-gray-400">
                          <span>0%</span><span>50%</span><span>100%</span>
                        </div>
                      </div>

                      {/* 工時填寫 */}
                      <div>
                        <label className="text-xs text-gray-500 block mb-1">工時紀錄（分鐘）</label>
                        <input
                          type="number" min={0} placeholder="輸入實際工時（分鐘）"
                          className="input w-full text-sm"
                          value={subtaskWorkHours[st.id] ?? ''}
                          onChange={e => setSubtaskWorkHours(h => ({ ...h, [st.id]: e.target.value }))}
                        />
                      </div>

                      {/* 狀態快速設定 */}
                      <div>
                        <label className="text-xs text-gray-500 block mb-1">執行狀態</label>
                        <div className="flex gap-2">
                          {SUBTASK_STATUSES.map(s => (
                            <button
                              key={s}
                              type="button"
                              onClick={() => {
                                if (st.status !== s) {
                                  subtasksApi.update(projectId, task.id, st.id, { status: s }).then(r => {
                                    setSubtasks(prev => prev.map(x => x.id === st.id ? r.data : x))
                                    fetchTasks(projectId)
                                  })
                                }
                              }}
                              className={`flex-1 text-xs py-1.5 rounded-lg border font-medium transition-colors ${
                                st.status === s
                                  ? SUBTASK_STATUS_COLORS[s]
                                  : 'bg-white text-gray-400 border-gray-200 hover:border-gray-300'
                              }`}
                            >
                              {SUBTASK_STATUS_LABELS[s]}
                            </button>
                          ))}
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => handleSubtaskDelete(st)}
                        className="text-xs text-red-400 hover:text-red-600"
                      >
                        刪除細項
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>

            <form onSubmit={handleAddSubtask} className="flex gap-2">
              <input
                className="input flex-1 text-sm"
                placeholder="新增細項任務…"
                value={newSubtask}
                onChange={e => setNewSubtask(e.target.value)}
              />
              <button type="submit" className="btn-secondary px-3 text-sm">+</button>
            </form>
          </div>

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

          {/* ── F07 時間追蹤 ─────────────────────────── */}
          <div className="border-t border-gray-100 pt-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-medium text-gray-500">時間追蹤</p>
              {totalMinutes > 0 && (
                <span className="text-xs text-primary-600 font-medium">累計 {fmtMins(totalMinutes)}</span>
              )}
            </div>

            {/* 計時器區塊 */}
            {runningLog ? (
              <div className="flex items-center gap-3 p-3 bg-green-50 border border-green-200 rounded-xl mb-3">
                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse flex-shrink-0" />
                <span className="text-sm text-green-700 font-medium flex-1">計時中 {fmtMins(timerElapsed)}</span>
                <button onClick={handleStopTimer} className="text-xs bg-red-500 text-white px-3 py-1 rounded-lg hover:bg-red-600">
                  停止
                </button>
              </div>
            ) : (
              <div className="flex gap-2 mb-3">
                <input
                  type="text"
                  className="input flex-1 text-sm"
                  placeholder="備註（選填）"
                  value={timerNote}
                  onChange={e => setTimerNote(e.target.value)}
                />
                <button onClick={handleStartTimer} className="btn-primary text-sm px-3 whitespace-nowrap">
                  ▶ 開始
                </button>
              </div>
            )}

            {/* 手動登錄 */}
            <form onSubmit={handleManualLog} className="flex gap-2 mb-3">
              <input
                type="number" min={1} max={1440}
                className="input w-20 text-sm"
                placeholder="分鐘"
                value={manualMinutes}
                onChange={e => setManualMinutes(e.target.value)}
              />
              <input
                type="text"
                className="input flex-1 text-sm"
                placeholder="備註（手動登錄）"
                value={manualNote}
                onChange={e => setManualNote(e.target.value)}
              />
              <button type="submit" disabled={addingManual || !manualMinutes} className="btn-secondary text-sm px-3 whitespace-nowrap">
                {addingManual ? '…' : '+ 手動'}
              </button>
            </form>

            {/* 工時記錄列表 */}
            {timeLogs.filter(l => l.ended_at).length > 0 && (
              <div className="space-y-1 max-h-36 overflow-y-auto">
                {timeLogs.filter(l => l.ended_at).map(l => (
                  <div key={l.id} className="flex items-center gap-2 text-xs text-gray-500 py-1 border-b border-gray-50">
                    <span className="font-medium text-gray-700 w-10">{fmtMins(l.minutes)}</span>
                    <span className="text-gray-400">{new Date(l.started_at).toLocaleDateString('zh-TW')}</span>
                    {l.note && <span className="flex-1 truncate text-gray-500">{l.note}</span>}
                    <button onClick={() => handleDeleteLog(l.id)} className="text-red-300 hover:text-red-500 ml-auto">✕</button>
                  </div>
                ))}
              </div>
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

          {/* ── F15 Check-in ─────────────────────────── */}
          <div className="border-t border-gray-100 pt-4">
            <p className="text-xs font-medium text-gray-500 mb-3">每日 Check-in（{checkins.length}）</p>
            {checkins.slice(0, 3).map(ci => (
              <div key={ci.id} className="mb-2 p-2 bg-gray-50 rounded-lg text-sm">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs text-gray-400">{new Date(ci.checked_at).toLocaleDateString('zh-TW')}</span>
                  <span className="text-xs bg-primary-100 text-primary-700 px-1.5 rounded-full">{ci.progress}%</span>
                </div>
                <p className="text-gray-700 text-xs">{ci.content}</p>
              </div>
            ))}
            <form onSubmit={handleAddCheckin} className="space-y-2">
              <textarea
                className="input w-full text-sm min-h-[60px]"
                placeholder="今天做了什麼？"
                value={checkinContent}
                onChange={e => setCheckinContent(e.target.value)}
              />
              <div className="flex items-center gap-2">
                <label className="text-xs text-gray-500">進度</label>
                <input
                  type="range" min={0} max={100} value={checkinProgress}
                  className="flex-1 accent-primary-500"
                  onChange={e => setCheckinProgress(+e.target.value)}
                />
                <span className="text-xs text-gray-600 w-8">{checkinProgress}%</span>
                <button type="submit" disabled={addingCheckin || !checkinContent.trim()} className="btn-secondary text-xs px-3">
                  {addingCheckin ? '…' : '提交'}
                </button>
              </div>
            </form>
          </div>

          {/* ── F10 重複排程 ─────────────────────── */}
          <div className="border-t border-gray-100 pt-4">
            <p className="text-xs font-medium text-gray-500 mb-2">重複排程</p>
            <div className="flex items-center gap-2 flex-wrap">
              <select
                className="input text-sm flex-1"
                value={recurrenceRule}
                onChange={e => setRecurrenceRule(e.target.value as RecurrenceRule | '')}
              >
                <option value="">不重複</option>
                <option value="daily">每天</option>
                <option value="weekly">每週</option>
                <option value="monthly">每月</option>
              </select>
              <button
                onClick={handleSaveRecurrence}
                disabled={savingRecurrence}
                className="btn-secondary text-xs px-3"
              >
                {savingRecurrence ? '…' : '儲存'}
              </button>
              {recurrenceRule && (
                <button
                  onClick={handleSpawnNext}
                  className="text-xs text-blue-500 hover:text-blue-700"
                  title="立即產生下一筆重複任務"
                >
                  ▶ 產生下一筆
                </button>
              )}
            </div>
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
