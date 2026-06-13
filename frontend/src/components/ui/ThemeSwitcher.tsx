import { useEffect, useRef, useState } from 'react'
import { useThemeStore, PALETTES, FX_OPTIONS } from '../../stores/themeStore'

/**
 * 頂欄調色盤快切面板。
 * 只讀寫 themeStore（最終落地於 <html> 屬性），不涉及任何業務狀態。
 * 既有的明暗切換按鈕仍保留在 Layout，本元件只負責「配色 + 特效」快切。
 */
export default function ThemeSwitcher() {
  const { palette, fx, setPalette, setFx } = useThemeStore()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onEsc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onEsc)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onEsc)
    }
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(o => !o)}
        className="w-8 h-8 flex items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-800 transition-colors duration-150"
        title="外觀主題"
        aria-haspopup="true"
        aria-expanded={open}
      >
        <span className="text-base">🎨</span>
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-60 card p-3 z-40 shadow-xl"
             style={{ animation: 'slide-up 0.15s ease-out' }}>
          {/* 配色 */}
          <p className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 mb-2 px-0.5">配色主題</p>
          <div className="flex items-center gap-2 mb-3">
            {PALETTES.map(p => (
              <button
                key={p.id}
                onClick={() => setPalette(p.id)}
                title={p.label}
                aria-label={p.label}
                className={`w-7 h-7 rounded-full transition-transform hover:scale-110 ring-offset-2 ring-offset-[rgb(var(--surface-card))] ${
                  palette === p.id ? 'ring-2 ring-gray-400 dark:ring-gray-500 scale-110' : ''
                }`}
                style={{ backgroundColor: p.swatch }}
              />
            ))}
          </div>

          {/* 特效 */}
          <p className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 mb-2 px-0.5">視覺特效</p>
          <div className="grid grid-cols-3 gap-1.5">
            {FX_OPTIONS.map(f => (
              <button
                key={f.id}
                onClick={() => setFx(f.id)}
                title={f.desc}
                className={`text-xs py-1.5 rounded-lg border transition-colors ${
                  fx === f.id
                    ? 'bg-primary-50 text-primary-700 border-primary-200 dark:bg-primary-500/10 dark:text-primary-200 dark:border-primary-500/30'
                    : 'border-gray-200 text-gray-600 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
