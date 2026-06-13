import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { dailyTasksApi } from '../api/dailyTasks'
import { confirm } from '../stores/confirmStore'
import { usersApi } from '../api/users'
import { useAuthStore } from '../stores/authStore'
import { toast } from '../stores/toastStore'

type ArchiveMode = 'done_immediately' | 'done_1month' | 'done_3months' | 'done_custom'

const ARCHIVE_MODE_LABELS: Record<ArchiveMode, string> = {
  done_immediately: '完成即整理（所有已完成）',
  done_1month: '1 個月前完成',
  done_3months: '3 個月前完成',
  done_custom: '自訂日期之前',
}

export default function ArchivedProjectsPage() {
  const user = useAuthStore(s => s.user)
  const fetchMe = useAuthStore(s => s.fetchMe)
  const [archiveMode, setArchiveMode] = useState<ArchiveMode>('done_1month')
  const [customDate, setCustomDate] = useState('')
  const [archiving, setArchiving] = useState(false)
  const [preview, setPreview] = useState<{ count: number; cutoff: string } | null>(null)
  const [previewing, setPreviewing] = useState(false)

  // 自動整理設定
  const [autoDays, setAutoDays] = useState<number>(user?.auto_archive_days ?? 0)
  const [savingAuto, setSavingAuto] = useState(false)

  useEffect(() => {
    setAutoDays(user?.auto_archive_days ?? 0)
  }, [user?.auto_archive_days])

  // 切換模式時重設預覽
  useEffect(() => { setPreview(null) }, [archiveMode, customDate])

  const handlePreview = async () => {
    if (archiveMode === 'done_custom' && !customDate) {
      toast.error('請選擇自訂整理日期')
      return
    }
    setPreviewing(true)
    try {
      const res = await dailyTasksApi.archivePreview({
        mode: archiveMode,
        before_date: archiveMode === 'done_custom' ? customDate : undefined,
      })
      setPreview(res.data)
    } catch {
      toast.error('預覽失敗，請重試')
    } finally { setPreviewing(false) }
  }

  const handleArchiveDaily = async () => {
    if (archiveMode === 'done_custom' && !customDate) {
      toast.error('請選擇自訂整理日期')
      return
    }
    if (preview?.count === 0) {
      toast.error('目前無符合條件的作業可整理')
      return
    }
    const label = ARCHIVE_MODE_LABELS[archiveMode]
    const countHint = preview ? `（共 ${preview.count} 筆）` : ''
    if (!(await confirm({ title: '移至封存', message: `確定要將「${label}」${countHint}的已完成日常作業移至歷史封存區？` }))) return
    setArchiving(true)
    try {
      const res = await dailyTasksApi.archive({
        mode: archiveMode,
        before_date: archiveMode === 'done_custom' ? customDate : undefined,
      })
      if (res.data.archived === 0) {
        toast.error('沒有符合條件的作業（可能已被封存，或關聯的專案任務尚未完成）')
      } else {
        toast.success(`已整理 ${res.data.archived} 筆日常作業至歷史封存區`)
      }
      setPreview(null)
    } catch {
      toast.error('整理失敗，請重試')
    } finally { setArchiving(false) }
  }

  const handleSaveAutoSetting = async () => {
    setSavingAuto(true)
    try {
      await usersApi.updateMe({ auto_archive_days: autoDays })
      await fetchMe()
      toast.success(autoDays === 0 ? '已關閉自動整理' : `已設定：完成 ${autoDays} 天後自動整理`)
    } catch {
      toast.error('儲存失敗')
    } finally { setSavingAuto(false) }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">日常任務整理</h1>
          <p className="text-sm text-gray-500 mt-0.5">將已完成的日常作業移至歷史封存區，降低列表資料量</p>
        </div>
        <Link
          to="/history"
          className="text-sm text-primary-600 hover:underline"
        >
          查看歷史記錄 →
        </Link>
      </div>

      {/* 手動整理 */}
      <div className="card border border-gray-200 space-y-4">
        <div>
          <h2 className="text-base font-semibold text-gray-800">手動整理</h2>
          <p className="text-xs text-gray-400 mt-0.5">立即將指定範圍的已完成日常作業搬移至歷史封存區</p>
        </div>

        <div>
          <label className="text-sm font-medium text-gray-700 block mb-2">整理時間範圍</label>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {(Object.keys(ARCHIVE_MODE_LABELS) as ArchiveMode[]).map(mode => (
              <label key={mode} className={`flex items-center gap-2.5 p-3 rounded-lg border cursor-pointer transition-colors ${
                archiveMode === mode
                  ? 'border-primary-400 bg-primary-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}>
                <input
                  type="radio"
                  name="archiveMode"
                  value={mode}
                  checked={archiveMode === mode}
                  onChange={() => setArchiveMode(mode)}
                  className="text-primary-600"
                />
                <span className="text-sm text-gray-700">{ARCHIVE_MODE_LABELS[mode]}</span>
              </label>
            ))}
          </div>
        </div>

        {archiveMode === 'done_custom' && (
          <div>
            <label className="text-sm font-medium text-gray-700 block mb-1">
              整理此日期之前完成的作業
            </label>
            <input
              type="date"
              className="input w-48"
              value={customDate}
              onChange={e => setCustomDate(e.target.value)}
              max={new Date().toISOString().split('T')[0]}
            />
          </div>
        )}

        <div className="pt-2 border-t border-gray-100 space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <button
              onClick={handlePreview}
              disabled={previewing || archiving}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-gray-50 text-gray-700 border border-gray-200 hover:bg-gray-100 transition-colors disabled:opacity-50"
            >
              {previewing ? '查詢中…' : '🔍 預覽筆數'}
            </button>
            <button
              onClick={handleArchiveDaily}
              disabled={archiving || previewing || preview?.count === 0}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-amber-50 text-amber-700 border border-amber-200 hover:bg-amber-100 transition-colors disabled:opacity-50"
            >
              {archiving ? '整理中…' : '📦 執行整理'}
            </button>
            {preview !== null && (
              <span className={`text-sm font-medium ${preview.count === 0 ? 'text-gray-400' : 'text-amber-700'}`}>
                {preview.count === 0
                  ? `截止 ${preview.cutoff} 前無可整理的作業`
                  : `將整理 ${preview.count} 筆（截止 ${preview.cutoff}）`}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400">先點「預覽筆數」確認數量，再執行整理。符合條件的已完成作業將從列表移除，可在「歷史記錄」查詢。</p>
        </div>
      </div>

      {/* 自動整理設定 */}
      <div className="card border border-gray-200 space-y-4">
        <div>
          <h2 className="text-base font-semibold text-gray-800">自動整理設定</h2>
          <p className="text-xs text-gray-400 mt-0.5">系統每日 00:05 自動將超過設定天數的已完成日常作業移至歷史封存區</p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700">完成後</label>
            <input
              type="number"
              className="input w-24 text-center"
              min={0}
              max={3650}
              value={autoDays}
              onChange={e => setAutoDays(Number(e.target.value))}
              placeholder="0"
            />
            <label className="text-sm font-medium text-gray-700">天後自動整理</label>
          </div>
          <button
            onClick={handleSaveAutoSetting}
            disabled={savingAuto}
            className="px-3 py-1.5 text-sm font-medium rounded-lg bg-primary-50 text-primary-600 border border-primary-200 hover:bg-primary-100 transition-colors disabled:opacity-50"
          >
            {savingAuto ? '儲存中…' : '儲存'}
          </button>
        </div>
        <p className="text-xs text-gray-400">
          {autoDays === 0
            ? '目前：關閉（設為 0 表示不自動整理）'
            : `目前：完成 ${autoDays} 天後自動整理`}
        </p>
      </div>
    </div>
  )
}
