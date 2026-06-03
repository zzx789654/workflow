import { useEffect, useState, useRef } from 'react'
import type { Task, SubTask, TimeLog } from '../../types'
import { tasksApi } from '../../api/tasks'
import { subtasksApi } from '../../api/subtasks'
import { timeLogsApi } from '../../api/timeLogs'
import { useTaskStore } from '../../stores/taskStore'
import ReactionsSection from './ReactionsSection'
import CheckinPanel from './CheckinPanel'
import AttachmentList from './AttachmentList'

interface Props {
  task: Task
  projectId: string
  onClose: () => void
}

const PRIORITY_LABELS = { low: '低', medium: '中', high: '高', urgent: '緊急' }
const STATUS_LABELS = { todo: '待辦', in_progress: '進行中', review: '審查中', done: '完成' }
const STATUS_OPTS = [
  { value: 'todo', label: '待辦' },
  { value: 'in_progress', label: '進行中' },
  { value: 'review', label: '審查中' },
  { value: 'done', label: '完成' },
]

export default function TaskDetailPanel({ task, projectId, onClose }: Props) {
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [subtasks, setSubtasks] = useState<SubTask[]>([])
  const [newSubtask, setNewSubtask] = useState('')
  const [timeLogs, setTimeLogs] = useState<TimeLog[]>([])
  const [runningLog, setRunningLog] = useState<TimeLog | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const fetchTasks = useTaskStore((s) => s.fetchTasks)
  const deleteTask = useTaskStore((s) => s.deleteTask)

  useEffect(() => {
    subtasksApi.list(projectId, task.id).then((r) => setSubtasks(r.data))
    timeLogsApi.list(projectId, task.id).then((r) => {
      setTimeLogs(r.data)
      const running = r.data.find((l) => !l.ended_at)
      setRunningLog(running ?? null)
    })
  }, [task.id, projectId])

  useEffect(() => {
    if (!runningLog) { if (timerRef.current) clearInterval(timerRef.current); return }
    const start = new Date(runningLog.started_at).getTime()
    timerRef.current = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 60000))
    }, 1000)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [runningLog])

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!comment.trim()) return
    setSubmitting(true)
    try {
      await tasksApi.addComment(projectId, task.id, comment)
      setComment('')
      await fetchTasks(projectId)
    } finally { setSubmitting(false) }
  }

  const handleDelete = async () => {
    if (!confirm('確定要刪除此任務？')) return
    await deleteTask(projectId, task.id)
    onClose()
  }

  const handleAddSubtask = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newSubtask.trim()) return
    const res = await subtasksApi.create(projectId, task.id, newSubtask.trim())
    setSubtasks((s) => [...s, res.data])
    setNewSubtask('')
    await fetchTasks(projectId)
  }

  const handleSubtaskStatus = async (st: SubTask) => {
    const nextStatus = st.status === 'done' ? 'todo' : 'done'
    const res = await subtasksApi.update(projectId, task.id, st.id, { status: nextStatus })
    setSubtasks((s) => s.map((x) => x.id === st.id ? res.data : x))
    await fetchTasks(projectId)
  }

  const handleStartTimer = async () => {
    try {
      const res = await timeLogsApi.start(projectId, task.id)
      setRunningLog(res.data)
      setTimeLogs((l) => [res.data, ...l])
    } catch (e: any) {
      alert(e?.response?.data?.detail ?? '計時器啟動失敗')
    }
  }

  const handleStopTimer = async () => {
    if (!runningLog) return
    const res = await timeLogsApi.stop(projectId, task.id, runningLog.id)
    setRunningLog(null)
    setTimeLogs((l) => l.map((x) => x.id === runningLog.id ? res.data : x))
  }

  const totalMinutes = timeLogs.reduce((sum, l) => sum + l.minutes, 0)

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex justify-end" onClick={onClose}>
      <div className="w-full max-w-lg bg-white h-full overflow-y-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="p-6 space-y-5">
          {/* 標題 */}
          <div className="flex items-start justify-between">
            <h2 className="text-xl font-bold text-gray-900 flex-1 pr-4">{task.title}</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl">✕</button>
          </div>

          {/* 狀態/優先度 badges */}
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

          {/* 指派人 */}
          {task.assignees.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 mb-2">指派給</p>
              <div className="flex gap-2 flex-wrap">
                {task.assignees.map((u) => (
                  <div key={u.id} className="flex items-center gap-1 text-sm bg-gray-100 rounded-full px-3 py-1">
                    <div className="w-5 h-5 rounded-full bg-primary-500 text-white text-xs flex items-center justify-center">
                      {u.display_name.charAt(0)}
                    </div>
                    <span>{u.display_name}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 子任務 */}
          <div className="border-t border-gray-100 pt-4">
            <p className="text-xs font-medium text-gray-500 mb-3">子任務 ({subtasks.length})</p>
            <ul className="space-y-1.5 mb-3">
              {subtasks.map((st) => (
                <li key={st.id} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={st.status === 'done'}
                    onChange={() => handleSubtaskStatus(st)}
                    className="rounded"
                  />
                  <span className={`text-sm flex-1 ${st.status === 'done' ? 'line-through text-gray-400' : 'text-gray-700'}`}>
                    {st.title}
                  </span>
                </li>
              ))}
            </ul>
            <form onSubmit={handleAddSubtask} className="flex gap-2">
              <input
                className="input flex-1 text-sm"
                placeholder="新增子任務…"
                value={newSubtask}
                onChange={(e) => setNewSubtask(e.target.value)}
              />
              <button type="submit" className="btn-secondary px-3 text-sm">+</button>
            </form>
          </div>

          {/* 時間追蹤 */}
          <div className="border-t border-gray-100 pt-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-medium text-gray-500">時間追蹤</p>
              <span className="text-xs text-gray-400">總計 {totalMinutes} 分鐘</span>
            </div>
            {runningLog ? (
              <div className="flex items-center gap-3">
                <span className="text-sm text-green-600 font-medium">⏱ {elapsed} 分鐘</span>
                <button onClick={handleStopTimer} className="btn-secondary text-sm px-3">停止</button>
              </div>
            ) : (
              <button onClick={handleStartTimer} className="btn-secondary text-sm px-3">▶ 開始計時</button>
            )}
            {timeLogs.filter((l) => l.ended_at).slice(0, 3).map((l) => (
              <div key={l.id} className="text-xs text-gray-400 mt-1">
                {new Date(l.started_at).toLocaleDateString('zh-TW')} — {l.minutes} 分鐘{l.note ? ` · ${l.note}` : ''}
              </div>
            ))}
          </div>

          {/* 附件 */}
          <div className="border-t border-gray-100 pt-4">
            <p className="text-xs font-medium text-gray-500 mb-3">附件</p>
            <AttachmentList projectId={projectId} taskId={task.id} />
          </div>

          {/* Check-in */}
          <div className="border-t border-gray-100 pt-4">
            <CheckinPanel projectId={projectId} taskId={task.id} />
          </div>

          {/* 評論 */}
          <div className="border-t border-gray-100 pt-4">
            <p className="text-xs font-medium text-gray-500 mb-3">評論 ({task.comments.length})</p>
            <div className="space-y-3 mb-4">
              {task.comments.map((c) => (
                <div key={c.id} className="flex gap-2">
                  <div className="w-7 h-7 rounded-full bg-primary-500 text-white text-xs flex items-center justify-center flex-shrink-0">
                    {c.author.display_name.charAt(0)}
                  </div>
                  <div className="flex-1">
                    <p className="text-xs font-medium text-gray-700">{c.author.display_name}</p>
                    <p className="text-sm text-gray-600 whitespace-pre-wrap">{c.content}</p>
                    <p className="text-xs text-gray-400">{new Date(c.created_at).toLocaleString('zh-TW')}</p>
                    <ReactionsSection projectId={projectId} taskId={task.id} commentId={c.id} />
                  </div>
                </div>
              ))}
            </div>
            <form onSubmit={handleAddComment} className="flex gap-2">
              <input
                className="input flex-1"
                placeholder="新增評論（@名稱 可 mention）…"
                value={comment}
                onChange={(e) => setComment(e.target.value)}
              />
              <button type="submit" disabled={submitting} className="btn-primary px-3">送出</button>
            </form>
          </div>

          {/* 刪除 */}
          <div className="border-t border-gray-100 pt-4">
            <button onClick={handleDelete} className="text-sm text-red-500 hover:text-red-700">刪除任務</button>
          </div>
        </div>
      </div>
    </div>
  )
}
