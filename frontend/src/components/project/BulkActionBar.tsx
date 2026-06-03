import { useState } from 'react'
import { api } from '../../api/client'

interface Props {
  selectedIds: string[]
  projectId: string
  onDone: () => void
}

export default function BulkActionBar({ selectedIds, projectId, onDone }: Props) {
  const [toast, setToast] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  if (selectedIds.length === 0) return null

  const showToast = (msg: string) => {
    setToast(msg)
    setTimeout(() => setToast(null), 3000)
  }

  const bulkAction = async (action: string) => {
    if (action === 'delete' && !confirm(`確定要刪除 ${selectedIds.length} 個任務？`)) return
    setLoading(true)
    try {
      await api.post(`/projects/${projectId}/tasks/bulk`, { task_ids: selectedIds, action })
      showToast(`已更新 ${selectedIds.length} 個任務 ✓`)
      onDone()
    } catch {
      showToast('操作失敗，請重試')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      {toast && (
        <div className="fixed bottom-20 left-1/2 -translate-x-1/2 z-50 bg-gray-900 text-white text-sm px-4 py-2 rounded-lg shadow-lg">
          {toast}
        </div>
      )}
      <div className="fixed bottom-0 left-52 right-0 z-40 bg-white border-t border-gray-200 shadow-lg px-6 py-3 flex items-center gap-4">
        <span className="text-sm font-medium text-gray-700">{selectedIds.length} 個任務已選取</span>
        <div className="flex gap-2 ml-auto">
          <button onClick={() => bulkAction('complete')} disabled={loading} className="btn-secondary text-sm px-3 py-1.5">標記完成</button>
          <button onClick={() => bulkAction('todo')} disabled={loading} className="btn-secondary text-sm px-3 py-1.5">標記待辦</button>
          <button onClick={() => bulkAction('delete')} disabled={loading}
            className="text-sm px-3 py-1.5 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 transition-colors">
            刪除
          </button>
        </div>
      </div>
    </>
  )
}
