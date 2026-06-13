import { create } from 'zustand'

export interface ConfirmOptions {
  title?: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  danger?: boolean
}

interface ConfirmState {
  open: boolean
  options: ConfirmOptions | null
  resolve: ((ok: boolean) => void) | null
  show: (options: ConfirmOptions) => Promise<boolean>
  respond: (ok: boolean) => void
}

export const useConfirmStore = create<ConfirmState>((set, get) => ({
  open: false,
  options: null,
  resolve: null,
  show: (options) =>
    new Promise<boolean>((resolve) => {
      set({ open: true, options, resolve })
    }),
  respond: (ok) => {
    get().resolve?.(ok)
    set({ open: false, options: null, resolve: null })
  },
}))

/**
 * 取代瀏覽器原生 confirm()。用法：
 *   if (!(await confirm({ message: '確定刪除？', danger: true }))) return
 * 不會帶出「Code」這類來源標題，樣式統一且支援深色模式。
 */
export const confirm = (options: ConfirmOptions): Promise<boolean> =>
  useConfirmStore.getState().show(options)
