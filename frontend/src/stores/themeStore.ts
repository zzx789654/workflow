import { create } from 'zustand'

// ── 外觀三維度（正交可組合）──────────────────────────────────
export type Palette = 'indigo' | 'ocean' | 'forest' | 'sunset' | 'mono'
export type Mode = 'light' | 'dark' | 'system'
export type Fx = 'flat' | 'glass' | 'soft'

export const PALETTES: { id: Palette; label: string; swatch: string }[] = [
  { id: 'indigo', label: '靛藍', swatch: '#4f46e5' },
  { id: 'ocean',  label: '海洋', swatch: '#0891b2' },
  { id: 'forest', label: '森林', swatch: '#059669' },
  { id: 'sunset', label: '暮光', swatch: '#ea580c' },
  { id: 'mono',   label: '極簡', swatch: '#475569' },
]
export const FX_OPTIONS: { id: Fx; label: string; desc: string }[] = [
  { id: 'flat',  label: '扁平', desc: '清楚邊框、實心卡片' },
  { id: 'glass', label: '玻璃', desc: '半透明毛玻璃、氛圍漸層' },
  { id: 'soft',  label: '柔光', desc: '柔和擴散陰影、無硬邊' },
]
export const MODE_OPTIONS: { id: Mode; label: string }[] = [
  { id: 'light',  label: '淺色' },
  { id: 'dark',   label: '深色' },
  { id: 'system', label: '跟隨系統' },
]

const LS = { palette: 'palette', fx: 'fx', motion: 'motion', mode: 'theme' } as const

const read = <T extends string>(key: string, fallback: T, allowed: readonly T[]): T => {
  const v = localStorage.getItem(key) as T | null
  return v && allowed.includes(v) ? v : fallback
}

const prefersDark = () =>
  window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false

// mode -> 實際是否深色
const resolveDark = (mode: Mode) => (mode === 'system' ? prefersDark() : mode === 'dark')

// 把目前狀態套到 <html>（唯一真相落地點）
const apply = (s: Pick<ThemeStore, 'palette' | 'mode' | 'fx' | 'motion'>) => {
  const el = document.documentElement
  el.dataset.palette = s.palette
  el.dataset.fx = s.fx
  el.dataset.motion = s.motion ? 'on' : 'off'
  el.classList.toggle('dark', resolveDark(s.mode))
}

interface ThemeStore {
  palette: Palette
  mode: Mode
  fx: Fx
  motion: boolean
  /** 衍生：目前是否為深色（供 UI icon 等使用） */
  dark: boolean
  setPalette: (p: Palette) => void
  setMode: (m: Mode) => void
  setFx: (f: Fx) => void
  setMotion: (on: boolean) => void
  /** 沿用舊行為：在 light/dark 間切換（保留既有頂欄按鈕語意） */
  toggle: () => void
  reset: () => void
  init: () => void
}

const DEFAULTS = { palette: 'indigo' as Palette, mode: 'light' as Mode, fx: 'flat' as Fx, motion: true }

export const useThemeStore = create<ThemeStore>((set, get) => ({
  palette: read<Palette>(LS.palette, 'indigo', PALETTES.map(p => p.id)),
  // 舊版只存 'dark' | 'light' 於 'theme'，向後相容；未設定則預設 light
  mode: read<Mode>(LS.mode, 'light', ['light', 'dark', 'system']),
  fx: read<Fx>(LS.fx, 'flat', FX_OPTIONS.map(f => f.id)),
  motion: localStorage.getItem(LS.motion) !== 'off',
  dark: false,

  setPalette: (palette) => {
    localStorage.setItem(LS.palette, palette)
    set({ palette })
    apply({ ...get(), palette })
  },
  setMode: (mode) => {
    localStorage.setItem(LS.mode, mode)
    set({ mode, dark: resolveDark(mode) })
    apply({ ...get(), mode })
  },
  setFx: (fx) => {
    localStorage.setItem(LS.fx, fx)
    set({ fx })
    apply({ ...get(), fx })
  },
  setMotion: (on) => {
    localStorage.setItem(LS.motion, on ? 'on' : 'off')
    set({ motion: on })
    apply({ ...get(), motion: on })
  },

  toggle: () => {
    // light <-> dark；若目前為 system 則依當前解析值反向
    const next: Mode = resolveDark(get().mode) ? 'light' : 'dark'
    get().setMode(next)
  },

  reset: () => {
    localStorage.removeItem(LS.palette)
    localStorage.removeItem(LS.fx)
    localStorage.removeItem(LS.motion)
    localStorage.setItem(LS.mode, DEFAULTS.mode)
    set({ ...DEFAULTS, dark: resolveDark(DEFAULTS.mode) })
    apply(DEFAULTS)
  },

  init: () => {
    const s = get()
    set({ dark: resolveDark(s.mode) })
    apply(s)
    // mode=system 時跟隨系統即時變化
    window.matchMedia?.('(prefers-color-scheme: dark)').addEventListener?.('change', () => {
      if (get().mode === 'system') {
        set({ dark: prefersDark() })
        apply(get())
      }
    })
  },
}))
