import { useEffect } from 'react'
import { useConfirmStore } from '../../stores/confirmStore'

/**
 * 全域確認對話框，取代瀏覽器原生 confirm()（後者會顯示「Code」等來源標題）。
 * 掛在 App 根節點一次即可，透過 confirm() 呼叫。
 */
export default function ConfirmDialog() {
  const { open, options, respond } = useConfirmStore()

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') respond(false)
      if (e.key === 'Enter') respond(true)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, respond])

  if (!open || !options) return null

  const {
    title = '請確認',
    message,
    confirmLabel = '確定',
    cancelLabel = '取消',
    danger = false,
  } = options

  return (
    <div className="modal-backdrop" onClick={() => respond(false)}>
      <div className="modal-panel max-w-sm p-5" onClick={e => e.stopPropagation()} role="alertdialog" aria-modal="true">
        <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 mb-2">{title}</h3>
        <p className="text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap leading-relaxed">{message}</p>
        <div className="flex justify-end gap-2 mt-5">
          <button onClick={() => respond(false)} className="btn-secondary text-sm">{cancelLabel}</button>
          <button
            onClick={() => respond(true)}
            className={`${danger ? 'btn-danger' : 'btn-primary'} text-sm`}
            autoFocus
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
