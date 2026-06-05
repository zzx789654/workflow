import { useToastStore } from '../../stores/toastStore'

const ICONS = {
  success: '✓',
  error:   '✕',
  info:    'ℹ',
  warning: '⚠',
}

export default function ToastContainer() {
  const { toasts, remove } = useToastStore()
  if (!toasts.length) return null

  return (
    <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-2 pointer-events-none">
      {toasts.map(t => (
        <div
          key={t.id}
          className={`toast-${t.type} pointer-events-auto`}
          onClick={() => remove(t.id)}
          role="alert"
        >
          <span className="flex-shrink-0 font-bold text-base leading-none">{ICONS[t.type]}</span>
          <span className="flex-1 leading-snug">{t.message}</span>
          <button
            onClick={e => { e.stopPropagation(); remove(t.id) }}
            className="flex-shrink-0 text-white/60 hover:text-white text-lg leading-none"
            aria-label="關閉"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
